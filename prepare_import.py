"""Prepare HubSpot import files from the Kaggle CRM dataset.

Applies the same cleaning as the pipeline analysis (product names, sector labels)
and maps the dataset onto the New Business pipeline built in HubSpot.
"""
import numpy as np
import pandas as pd

RAW = "raw/"   # folder with the four Kaggle CSVs
OUT = "/mnt/user-data/outputs/"
SAMPLE = 500
SEED = 7

accounts = pd.read_csv(RAW + "accounts.csv")
products = pd.read_csv(RAW + "products.csv")
teams = pd.read_csv(RAW + "sales_teams.csv")
pipe = pd.read_csv(RAW + "sales_pipeline.csv", parse_dates=["engage_date", "close_date"])

# ---------- cleaning (same fixes as the analysis) ----------
norm = lambda s: s.str.replace(r"\s+", "", regex=True).str.lower()
catalog = dict(zip(norm(products["product"]), products["product"]))
pipe["product"] = norm(pipe["product"]).map(catalog).fillna(pipe["product"])
accounts["sector"] = accounts["sector"].replace({"technolgy": "technology"}).str.title()

# ---------- companies ----------
companies = pd.DataFrame({
    "Company name": accounts["account"],
    "Sector": accounts["sector"],
    "Annual revenue": (accounts["revenue"] * 1_000_000).round(0).astype("Int64"),  # dataset is in millions
    "Number of employees": accounts["employees"],
    "Country/Region": accounts["office_location"],
    "Year founded": accounts["year_established"],
})
companies.to_csv(OUT + "hubspot_companies.csv", index=False)

# ---------- deals ----------
df = (pipe.merge(teams, on="sales_agent", how="left")
          .merge(products[["product", "sales_price"]], on="product", how="left"))

# stratified sample so every stage is represented in the same proportion
rng = np.random.default_rng(SEED)
share = df["deal_stage"].value_counts(normalize=True)
parts = []
for stage, frac in share.items():
    block = df[df["deal_stage"] == stage]
    parts.append(block.sample(n=min(len(block), max(1, round(SAMPLE * frac))), random_state=SEED))
df = pd.concat(parts).sort_values("engage_date", na_position="first").reset_index(drop=True)

STAGE = {"Prospecting": "Prospecting", "Engaging": "Discovery",
         "Won": "Closed Won", "Lost": "Closed Lost"}
df["stage"] = df["deal_stage"].map(STAGE)

# Amount: what was actually closed on won deals, list price on everything else
df["amount"] = np.where(df["deal_stage"] == "Won", df["close_value"], df["sales_price"]).round(2)

# Discount only makes sense on won deals
df["discount"] = np.where(df["deal_stage"] == "Won",
                          ((1 - df["close_value"] / df["sales_price"]) * 100).round(1), np.nan)

# Create date drives the 90-day stale rule: use the engagement date, falling back
# to the earliest engagement in the dataset for Prospecting deals (which have none).
earliest = df["engage_date"].min()
df["create_date"] = df["engage_date"].fillna(earliest)

# Deal name: [Company] - [Product] - [MMM YYYY]
month = df["create_date"].dt.strftime("%b %Y")
df["deal_name"] = (df["account"].fillna("Unassigned account") + " - " + df["product"] + " - " + month)

open_mask = df["stage"].isin(["Prospecting", "Discovery"])
df["next_step"] = np.where(open_mask, "Imported - confirm current status with the rep", "")
# A past date, so the overdue-next-step workflow picks these up
df["next_step_date"] = np.where(open_mask, df["create_date"] + pd.Timedelta(days=30), pd.NaT)

lost = df["stage"] == "Closed Lost"
df["lost_reason"] = np.where(lost, "Other", "")
df["lost_reason_details"] = np.where(lost, "Imported - reason not recorded in the legacy system", "")

deals = pd.DataFrame({
    "Deal name": df["deal_name"],
    "Deal stage": df["stage"],
    "Pipeline": "New Business",
    "Amount": df["amount"],
    "Close date": df["close_date"].dt.strftime("%Y-%m-%d"),
    "Create date": df["create_date"].dt.strftime("%Y-%m-%d"),
    "Company name": df["account"],
    "Product": df["product"],
    "List price": df["sales_price"],
    "Discount %": df["discount"],
    "Regional office": df["regional_office"],
    "Legacy sales agent": df["sales_agent"],
    "Next step": df["next_step"],
    "Next step date": pd.to_datetime(df["next_step_date"]).dt.strftime("%Y-%m-%d"),
    "Lost reason": df["lost_reason"],
    "Lost reason details": df["lost_reason_details"],
})
deals.to_csv(OUT + "hubspot_deals.csv", index=False)

print(f"companies: {len(companies)} rows")
print(f"deals:     {len(deals)} rows")
print(deals["Deal stage"].value_counts().to_string())
print("\ndeals with no company (Prospecting):", deals["Company name"].isna().sum())
print("open deals older than 90 days:",
      (pd.to_datetime(deals["Create date"]) < pd.Timestamp.today() - pd.Timedelta(days=90))[
          deals["Deal stage"].isin(["Prospecting", "Discovery"])].sum())
print("\nSample rows:")
print(deals.head(3).to_string())
