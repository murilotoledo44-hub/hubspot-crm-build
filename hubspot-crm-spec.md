# HubSpot CRM Build — Specification

**Project:** Turning pipeline analysis into CRM guardrails
**Author:** Murilo Toledo
**Status:** Built — see §11 for what changed during implementation
**Related project:** [B2B Sales Pipeline Analysis](https://github.com/murilotoledo44-hub/b2b-sales-pipeline-analysis)

---

## 1. Why this build exists

My pipeline analysis of a B2B CRM (~8,800 opportunities) found three problems that a better CRM setup should prevent:

| Finding from the analysis | What it cost | Guardrail in this build |
|---|---|---|
| 92% of Engaging deals were open for 90+ days — twice the 45-day median cycle | The open pipeline overstated the forecast | Clear stage exit criteria, a required next step, and an automatic stale-deal alert (§3, §5) |
| Product names (`GTXPro` vs `GTX Pro`) and sector labels (`technolgy`) were inconsistent | Joins and reports broke silently | Dropdown properties instead of free text (§4) |
| No structured reason for lost deals | Lost-deal reviews and coaching had nothing to work with | Required, standardized lost reason (§3, §4) |

**Goal:** a pipeline a sales leader can forecast from, with data clean enough to report on without manual fixes.

## 2. Environment and assumptions

- **Platform:** HubSpot Sales Hub Professional features (via a developer test account or a Professional trial). Workflows, deal rotation and custom reports are not available on the free CRM.
- **Company modeled:** a B2B company selling 7 products through 3 regional offices (Central, East, West), based on the Kaggle "CRM + Sales + Opportunities" dataset.
- **Baseline numbers used in the design:** 63.2% win rate on closed deals, 45-day median sales cycle.
- **Users:** a test account won't hold the dataset's full sales team, so deals are assigned to 2–3 demo users, and the original rep name is kept in a separate property for reporting (§4).

## 3. Pipeline: "New Business"

### 3.1 Stages

| # | Stage | Win probability | Enters when… | Exits when… (exit criteria) |
|---|---|---|---|---|
| 1 | Prospecting | 5% | Target account identified and contacted | A first meeting is booked |
| 2 | Discovery | 15% | First meeting booked | Pain, budget range and decision maker confirmed |
| 3 | Solution Fit | 35% | Qualification confirmed | Product fit validated and buyer agrees to receive a proposal |
| 4 | Proposal Sent | 60% | Proposal delivered | Buyer engages on terms or pricing |
| 5 | Negotiation | 80% | Terms under discussion | Contract signed (Won) or deal lost |
| 6 | Closed Won | 100% | Contract signed | — |
| 7 | Closed Lost | 0% | Deal lost at any stage | — |

> **Note on probabilities:** these are starting assumptions. After one full quarter of data, they should be recalibrated from the actual conversion rate of each stage.

### 3.2 Required properties by stage

HubSpot blocks the stage change until these fields are filled ("conditional stage properties").

| Moving into… | Required properties |
|---|---|
| Discovery | Product, Deal source, Next step, Next step date |
| Solution Fit | Amount, Close date, Decision maker identified (Yes/No) |
| Proposal Sent | Proposal sent date |
| Negotiation | Discount %, Next step, Next step date |
| Closed Won | Amount, Close date |
| Closed Lost | Lost reason (+ Lost reason details if "Other") |

**Design choice:** requirements grow with the deal. Early stages ask for little, so reps aren't slowed down during prospecting, while later stages protect the forecast.

## 4. Properties and data governance

### 4.1 Deal properties

| Property | Type | Options / rule | Why |
|---|---|---|---|
| Product | Dropdown | GTX Basic, GTX Pro, GTX Plus Basic, GTX Plus Pro, MG Special, MG Advanced, GTK 500 | Prevents the `GTXPro` / `GTX Pro` mismatch |
| Deal source | Dropdown | Outbound, Inbound, Partner, Referral | Pipeline attribution |
| Next step | Single-line text | Short description of the next agreed action | Keeps every open deal moving |
| Next step date | Date | Must be today or later | Source for stale-deal checks |
| Decision maker identified | Yes/No | — | Qualification checkpoint |
| Proposal sent date | Date | — | Measures proposal-to-close time |
| List price | Number (currency) | Filled from the product's list price | Base for pricing analysis |
| Discount % | Number | 0–100 | Tracks pricing discipline |
| Lost reason | Dropdown | Price, Competitor, No decision / timing, No budget, Product fit, Unresponsive, Other | Enables lost-deal reviews |
| Lost reason details | Multi-line text | Required when Lost reason = Other | Keeps "Other" from becoming a catch-all |
| Stale deal | Yes/No | Set only by automation (§5) | Powers the stale-deal report |
| Regional office | Dropdown | Central, East, West | Team reporting |
| Legacy sales agent | Single-line text | Original rep name from the dataset | Keeps rep-level history after import |

### 4.2 Company properties

| Property | Type | Options |
|---|---|---|
| Industry | Dropdown | Retail, Technology, Medical, Software, Finance, Marketing, Entertainment, Telecommunications, Services, Employment |
| Annual revenue | Number (currency) | — |
| Number of employees | Number | — |
| Country | Dropdown | From the dataset's office locations |

### 4.3 Conventions

- **Deal name:** `[Company] – [Product] – [MMM YYYY]`, for example `Acme Corp – GTX Pro – Mar 2017`.
- **No new dropdown options without RevOps approval.** Free-text alternatives to dropdowns are not allowed.

## 5. Automations (workflows)

### W1 — Stale deal alert
- **Type:** Deal-based
- **Enrollment:** Deal stage is any open stage **AND** Create date is more than 90 days ago **AND** Stale deal is not Yes
- **Actions:**
  1. Set Stale deal = Yes
  2. Create task for deal owner: *"Stale deal — advance with a dated next step or close as lost"*, due in 3 business days
  3. Send internal notification to the owner's manager
- **Why 90 days:** twice the 45-day median cycle. Deals past this point rarely close on the original timeline.

### W2 — Overdue next step
- **Type:** Deal-based, re-enrollment on
- **Enrollment:** Deal stage is any open stage **AND** Next step date is before today
- **Actions:** create task for the owner: *"Next step is overdue — update Next step and Next step date"*, due today
- **Why:** catches drift weeks before a deal becomes stale.

### W3 — Clear the stale flag
- **Type:** Deal-based, re-enrollment on
- **Enrollment:** Stale deal = Yes **AND** Deal stage has changed
- **Actions:** set Stale deal = No
- **Why:** the flag should reflect current status, not history.

### W4 — Stage-entry tasks
- **Type:** Deal-based, re-enrollment on
- **Enrollment:** Deal stage changes to one of the stages below
- **Actions:**

| Stage | Task for owner | Due |
|---|---|---|
| Discovery | Confirm pain, budget range and decision maker | 5 business days |
| Proposal Sent | Follow up on proposal | 3 business days |
| Negotiation | Confirm contract signers and target signature date | 2 business days |

### W5 — New deal assignment
- **Type:** Deal-based
- **Enrollment:** Deal is created **AND** Deal owner is unknown
- **Actions:** rotate the deal among the reps of the deal's Regional office (round robin)
- **Why:** no unowned deals, and an even workload across the team.

## 6. Data import plan

1. **Clean first:** apply the same fixes as the analysis (`GTXPro` → `GTX Pro`, `technolgy` → `technology`) so imported values match the dropdown options exactly.
2. **Companies:** import `accounts.csv` → Company name, Industry, Annual revenue, Number of employees, Country.
3. **Deals:** import a sample of about 500 rows from `sales_pipeline.csv`, associated with companies by name.

| Dataset field | HubSpot property |
|---|---|
| `deal_stage` = Prospecting | Prospecting |
| `deal_stage` = Engaging | Discovery *(the dataset has no finer stages)* |
| `deal_stage` = Won / Lost | Closed Won / Closed Lost |
| `close_value` (won) or product list price (open) | Amount |
| `close_date` | Close date |
| `product` | Product |
| `sales_agent` | Legacy sales agent |
| Team's regional office | Regional office |

4. **Lost reason:** the dataset has none, so imported lost deals get `Other` with the detail *"Imported — reason not recorded"*. This keeps the rule consistent and makes the historical gap visible in reports.

## 7. Dashboard: "Pipeline Health"

| Report | Visualization | Answers |
|---|---|---|
| Open pipeline by stage | Bar (count and amount) | Where are the deals? |
| Weighted forecast | Single value | What will likely close? |
| Win rate by quarter | Line | Are we closing better or worse? |
| Stale deals by owner | Table | Who needs to clean their pipeline? |
| Deals with overdue next step | Table | What is drifting right now? |
| Lost reasons | Bar | Why do we lose? |
| Average discount by product | Bar | Is pricing holding? |

## 8. Acceptance tests

Each rule is tested with a demo deal before screenshots are taken.

| # | Test | Expected result |
|---|---|---|
| 1 | Move a deal to Discovery without Next step date | HubSpot blocks the change and asks for the field |
| 2 | Move a deal to Closed Lost without Lost reason | Blocked |
| 3 | Set Lost reason = Other with no details | Blocked |
| 4 | Open deal created 90+ days ago | Stale deal = Yes, task created, manager notified |
| 5 | Move that stale deal to the next stage | Stale deal returns to No |
| 6 | Set Next step date to yesterday | Overdue task created |
| 7 | Move a deal to Proposal Sent | Follow-up task due in 3 business days |
| 8 | Create a deal with no owner in the East office | Deal assigned to an East rep |
| 9 | Try typing a new product name | Not possible — dropdown only |

## 9. Deliverables

- This specification
- Screenshots: pipeline settings, required properties, each workflow, the dashboard, and one blocked stage change (test 1)
- README with the problem, design decisions, screenshots and results of the acceptance tests
- Optional: a 3-minute Loom walkthrough

## 10. Out of scope (future improvements)

- Email sequences for outbound cadences
- Lead scoring on contacts
- Separate pipeline for renewals and upsells
- Recalibrating stage probabilities from real conversion data after one quarter


## 11. Implementation notes (as built)

The build followed this spec. Four things changed once it met the platform:

1. **W1 notification.** HubSpot's in-app notification action only accepts named users or teams, not "deal owner". The notification is sent to a fixed user; the task created in the same workflow is still assigned dynamically to the deal owner.
2. **W3 trigger.** HubSpot offers no "deal stage has changed" operator in filter-criteria triggers. W3 therefore triggers on *Stale deal = True AND deal stage is any of the later stages* (Solution Fit, Proposal Sent, Negotiation, Closed Won, Closed Lost). Including earlier stages made the workflow unflag deals as fast as W1 flagged them.
3. **Retroactive enrollment.** Workflows do not enroll records that already match the criteria at creation. The imported deals were 90+ days old on arrival, so W1 needed a one-time manual enrollment — standard practice when a rule goes live on existing data.
4. **Deal source left blank on import.** The source dataset has no equivalent field. Historic deals therefore don't meet the new standard, which is visible in reporting by design; the requirement binds deals moving forward.

### Acceptance tests — results

| # | Test | Result |
|---|---|---|
| 1 | Move a deal to Discovery without the required fields | Blocked ✅ |
| 2 | Move a deal to Closed Lost without a lost reason | Blocked ✅ |
| 4 | Open deal older than 90 days | Flagged, task created, notification sent ✅ |
| 8 | Deal created with no owner | Assigned by round robin ✅ |
| 9 | Type a new product name | Not possible — dropdown only ✅ |
