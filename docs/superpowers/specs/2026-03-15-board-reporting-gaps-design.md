# Board Financial Reporting Gaps — Design Spec

**Date:** 2026-03-15
**Status:** Approved
**Author:** Pete Ceci / Claude

## Problem

The NSIA board dashboard has strong budget reconciliation, variance alerting, and ice utilization data but lacks three critical data sources for full governance: bank-level cash visibility, a board decision/action tracker, and a vendor master with contract compliance.

## Solution

Three new features across two new pages and two page enhancements.

---

## Feature 1: Bank Transaction Upload & Cash Position

**Location:** New section on Page 7 (Monthly Financials)

### Data Model

File: `data/bank_transactions.csv`

Header row: `date,description,amount,balance,category,source_file,import_date`

| Column | Type | Description |
|--------|------|-------------|
| date | date (YYYY-MM-DD) | Transaction date |
| description | string | Payee/memo from bank |
| amount | float (2 decimal) | Positive = deposit, negative = withdrawal |
| balance | float (2 decimal) | Running balance. If bank CSV lacks balance, calculate as cumulative sum from amounts |
| category | string | Auto-classified or manual (optional, nullable) |
| source_file | string | Original upload filename |
| import_date | date (YYYY-MM-DD) | When imported |

### Upload Flow

1. User uploads CSV from bank portal
2. System auto-detects format: Chase, BMO, generic
3. Parser normalizes to standard schema (UTF-8, US date format MM/DD/YYYY tried first, then ISO YYYY-MM-DD)
4. Deduplication: match on exact date + exact amount + case-insensitive description. Same-day same-amount transactions with different descriptions are kept (legitimate duplicates like two $50 payments to different vendors)
5. Append to `data/bank_transactions.csv`
6. Uploads are always append (cumulative). Never overwrite.

### Display

- **Daily cash position line chart** — running balance over time
- **Weekly cash summary table** — opening balance, deposits, withdrawals, closing balance
- **Large transaction alerts** — flag any single transaction where abs(amount) > $5,000 (configurable threshold)
- **Cash vs forecast overlay** — plot actual bank balance against `cash_forecast.csv` projections. Bank data is source of truth for actual cash position; GL is the accounting record. If they diverge, flag the gap.

### Parser Details

Support these common bank CSV formats:
- **Chase:** "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #"
- **BMO:** "Date,Description,Withdrawals,Deposits,Balance" — combine Withdrawals (negative) + Deposits (positive) into single amount column
- **Generic:** Any CSV with columns containing "date", "description"/"memo"/"payee", "amount"/"debit"/"credit", optionally "balance"

If balance column is missing, calculate running balance from amounts (requires user to specify starting balance on upload).

Parser function: `utils/bank_parser.py` with `parse_bank_csv(file_bytes, filename) -> pd.DataFrame`

### Error Handling

- Malformed CSV (missing required columns): show st.error listing which columns were found vs expected, return None
- Unparseable dates: skip row, log to `parse_errors` list, show st.warning with count of skipped rows
- Non-numeric amounts: skip row, same warning behavior
- Empty file: show st.warning "File is empty"

---

## Feature 2: Board Actions Log

**Location:** New page — Page 15: "Board Actions"

### Data Model

File: `data/board_actions.xlsx` with two sheets:

**Sheet 1: Motions**

| Column | Type | Description |
|--------|------|-------------|
| id | string | UUID, auto-generated |
| meeting_date | date | Board meeting date |
| motion | string | Motion text |
| category | string | Financial / Operations / Governance / Personnel / Other |
| outcome | string | Passed / Failed / Tabled / Withdrawn |
| votes_for | int | Yes votes |
| votes_against | int | No votes |
| votes_abstain | int | Abstentions |
| notes | string | Discussion notes (nullable) |
| minutes_doc_id | string | Link to Document Library catalog ID (nullable) |

**Sheet 2: Action Items**

| Column | Type | Description |
|--------|------|-------------|
| id | string | UUID, auto-generated |
| motion_id | string | FK to Motions sheet (nullable — standalone action items allowed) |
| created_date | date | When created |
| description | string | What needs to be done |
| assignee | string | Person responsible |
| due_date | date | Deadline |
| status | string | Open / In Progress / Done |
| completed_date | date | Required when status = Done, must be <= today. Nullable otherwise. |
| notes | string | Updates/progress notes (nullable) |

### Validation Rules

- When status changes to "Done": `completed_date` is auto-set to today if not provided
- `completed_date` must be >= `created_date`
- `due_date` must be >= `created_date`

### Page Layout

- **Input:** Upload Excel or use inline form (st.form) to add motions and action items
- **Motions table:** Sortable/filterable by date, category, outcome using st.dataframe
- **Action items tracker:** Table layout with 3 filtered sections (Open, In Progress, Done) using st.columns(3). Each section shows filtered items with colored status pills. No drag-drop (not native to Streamlit).
- **Overdue dashboard:** Items past due_date highlighted in red
- **Meeting minutes link:** If minutes_doc_id is set, show link button to Document Library page

### Variance Alerts Integration

Surface on Page 5 (Variance Alerts) as a new "Board Actions" section:
- Red flag: Action items > 14 days overdue (overdue = status != "Done" AND due_date < today)
- Yellow flag: Action items due within 7 days (status != "Done" AND due_date between today and today+7)
- Show as `st.metric("Overdue Board Actions", count)` at top of Variance Alerts page

---

## Feature 3: Vendor Master (Hybrid Auto-Extract)

**Location:** New page — Page 16: "Vendor Master"

(Moved from Page 10 Reconciliation — Page 10 is already dense with 5 sections.)

### Data Model

File: `data/vendor_master.csv`

| Column | Type | Description |
|--------|------|-------------|
| vendor_id | string | UUID. Generated on first extraction, frozen thereafter. On re-extraction, match by fuzzy vendor_name to preserve existing UUID. |
| vendor_name | string | Canonical name |
| aliases | string | Semicolon-separated alternate names from GL (using `;` not `|` to avoid CSV issues) |
| total_spend_ytd | float | Calculated from GL on extraction |
| payment_count | int | Number of GL transactions |
| first_seen | date | Earliest GL transaction |
| last_seen | date | Most recent GL transaction |
| contract_start | date | Manual entry (nullable) |
| contract_end | date | Manual entry (nullable) |
| contract_terms | string | Manual entry — payment terms, rate, etc. (nullable) |
| contract_doc_id | string | Reference to Document Library catalog ID (nullable) |
| compliance_notes | string | Manual entry (nullable) |
| risk_flag | string | None / Low / Medium / High |
| category | string | Utilities / Insurance / Management / Maintenance / Professional Services / Other |

### Display Rules

- Row highlighted red if `contract_end` is non-null and < today (expired contract)
- Row highlighted yellow if `contract_end` is within 90 days (upcoming renewal)
- CSCG pre-flagged as High risk on initial extraction

### Auto-Extract Flow

1. Read `general_ledger.xlsx` and `bills_summary.xlsx`
2. Extract unique payee/vendor names from relevant columns
3. Fuzzy dedup using difflib.SequenceMatcher (ratio threshold 0.85, configurable)
4. Before merging: show "Review Fuzzy Matches" table with proposed merges and confidence scores. User confirms or rejects each merge.
5. On merge: keep the earlier UUID, combine aliases, aggregate spend
6. Calculate total spend, payment count, date range per vendor
7. Pre-flag CSCG as High risk
8. Merge with existing `data/vendor_master.csv` preserving all manual fields (contract_start, contract_end, contract_terms, contract_doc_id, compliance_notes, risk_flag, category)
9. Write updated file

### Display

- **Vendor summary table** — sortable by spend, risk, category via st.dataframe
- **Top 10 vendors by spend** — horizontal bar chart
- **Contract expiration timeline** — upcoming renewals within 90 days
- **CSCG deep-dive card** — total spend, payment frequency
- **Edit mode** — st.data_editor for contract terms, compliance notes, risk flags, category

### Extract Utility

`utils/vendor_extractor.py` with:
- `extract_vendors(gl_path, bills_path) -> pd.DataFrame` — initial extraction
- `fuzzy_dedup(df, threshold=0.85) -> list[dict]` — returns proposed merges with confidence scores for user review
- `apply_merges(df, approved_merges) -> pd.DataFrame` — apply user-confirmed merges
- `merge_with_existing(new_df, existing_path) -> pd.DataFrame` — preserve manual edits by matching on vendor_id

### Error Handling

- Missing GL/bills files: show st.warning, skip extraction, allow manual vendor entry only
- Fuzzy match conflicts (>2 vendors matching at threshold): show all candidates to user, let them pick
- Empty GL: show st.info "No vendor data found"

---

## Data Refresh Policy

- **Bank transactions:** Append-only uploads. All historical data retained for audit trail. No auto-refresh.
- **Board actions:** Manual upload/edit only. No auto-refresh. All data retained permanently.
- **Vendor master:** Manual re-extraction via button on Vendor Master page. Auto-calculated fields (spend, count, dates) refresh on extraction. Manual fields preserved across re-extractions.

---

## Files to Create

| File | Purpose |
|------|---------|
| `utils/bank_parser.py` | Bank CSV format detection and parsing |
| `utils/vendor_extractor.py` | GL/bills vendor extraction and fuzzy dedup |
| `data/board_actions.xlsx` | Starter template with empty Motions and Action Items sheets |
| `data/bank_transactions.csv` | Empty with header row |
| `data/vendor_master.csv` | Auto-populated from initial extract |
| `pages/15_Board_Actions.py` | New page — board motions and action items |
| `pages/16_Vendor_Master.py` | New page — vendor list with contract compliance |

## Files to Modify

| File | Change |
|------|--------|
| `pages/7_Monthly_Financials.py` | Add bank transactions upload and cash position section |
| `pages/5_Variance_Alerts.py` | Add overdue action item alerts as st.metric at top |

## Non-Goals

- No bank API integration (Plaid etc.) — CSV upload only
- No automated vendor risk scoring — manual flags only
- No meeting minutes generation — just linking to existing docs
- No multi-user editing — single-user (Pete) workflow
- No drag-drop Kanban — Streamlit doesn't support it natively
- No sidebar badge on page name — use st.metric on Variance Alerts instead
