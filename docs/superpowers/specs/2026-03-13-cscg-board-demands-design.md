# CSCG Board Demands Section — Design Spec

## Summary

Add a "Board Demands — What NSIA Needs From CSCG" section to Page 6 (CSCG Scorecard). This section presents 15 specific documents, reports, and actions the board should require from the management company, with auto-detected status indicators (GREEN/YELLOW/RED) driven by existing dashboard data.

## Location

Page 6 (`pages/6_CSCG_Scorecard.py`), inserted between the "CSCG Budget Modifications Without Board Approval" section and the "AI Assessment" button. The AI Assessment context (`scorecard_summary`) should be extended to include Board Demands summary data (e.g., "5/15 demands met, 8 outstanding").

## Data Dependencies

All data comes from existing loaders in `utils/data_loader.py`:

- `load_cscg_relationship()` — CSCG payment components (columns: Component, Amount, Approval Required?, Contract Reference)
- `load_unauthorized_modifications()` — budget modifications without board approval (columns: Line Item, Proposal Annual, CSCG Annual (Implied), Annual Variance $, Direction, Severity, Board Governance Impact)
- `load_expense_flow_summary()` — expense approval method breakdown (columns: Approval Method, YTD Amount, % of Total)
- `compute_cscg_scorecard()` — contract compliance status (columns: Contract Term, Contract Amount, 6mo Expected, 6mo Actual, Status)

No new data files or loaders are required.

## Demand Items (15 total, 5 categories)

### Financial Reporting (5)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 1 | Monthly itemized payroll report (names, hours, rates) | Monthly | Check `load_cscg_relationship()` for rows where Component contains "Payroll". GREEN if payroll line items exist (data is being tracked), RED if no payroll data found. Note: current data only has aggregate amounts, not itemized detail — so even GREEN means "aggregate exists, itemized detail still needed." |
| 2 | Monthly expense reimbursement detail with receipts | Monthly | Default RED — "Manual review required". No receipt/reimbursement-level data available in dashboard. |
| 3 | Invoice copies for all vendor payments > $500 | Monthly | Check `load_expense_flow_summary()` for "Board Approved" row (filter where Approval Method contains "Board", case-insensitive). Read its `% of Total` value. GREEN if > 0.80, YELLOW if 0.50-0.80, RED if < 0.50. |
| 4 | Quarterly revenue reconciliation (collected vs. deposited) | Quarterly | Default RED — no revenue reconciliation data currently available. |
| 5 | Monthly bank account transaction log | Monthly | Default RED — no bank transaction data currently available. |

### Budget Accountability (3)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 6 | Written variance explanation for any line item change > $2,500 | As needed | Check `load_unauthorized_modifications()`. Filter to rows where Severity is "HIGH" or "CRITICAL". RED if any such rows exist (unauthorized modifications with no verifiable explanation in data), GREEN if no HIGH/CRITICAL modifications exist. |
| 7 | Board pre-approval before any budget line modification | As needed | Check `load_unauthorized_modifications()` total row count (excluding totals/summaries). RED if any unauthorized modifications exist, GREEN if none. |
| 8 | Quarterly budget-to-actual comparison with CSCG commentary | Quarterly | Default YELLOW — budget-to-actual data exists in dashboard but CSCG commentary is not verifiable from data. |

### Contract Compliance (3)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 9 | Current insurance certificates (GL, workers comp, D&O) | Annual | Default RED — "Manual review required". |
| 10 | Annual management fee reconciliation vs. contract terms | Annual | Check `compute_cscg_scorecard()`. Filter to row where Contract Term contains "Management Fee" (case-insensitive). Map that row's Status: COMPLIANT → GREEN, MINOR VARIANCE → YELLOW, NON-COMPLIANT → RED, AUTO-PAY → YELLOW. If no matching row found, default RED. |
| 11 | Proof of regulatory compliance (health dept, fire, refrigerant) | Annual | Default RED — "Manual review required". |

### Operational Transparency (2)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 12 | Read-only access to operating bank account | One-time | Default RED — "Manual review required". |
| 13 | Monthly auto-pay transaction log with categorization | Monthly | Check `load_expense_flow_summary()`. Filter to rows where Approval Method contains "CSCG" or "Auto" (case-insensitive). RED if such rows exist (auto-pay is happening but no itemized log is available in dashboard data). GREEN if no auto-pay category exists. |

### Board Communication (2)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 14 | Board meeting prep materials delivered 5+ business days in advance | Per meeting | Default RED — "Manual review required". |
| 15 | Written response to board questions within 10 business days | As needed | Default RED — "Manual review required". |

## Status Indicators

Three-state traffic light system consistent with the Variance Alerts page:

| Status | Color | Hex | Meaning |
|--------|-------|-----|---------|
| GREEN | Green | `#00d084` | Received / verified from data |
| YELLOW | Yellow | `#fcb900` | Partial / outdated / unverifiable |
| RED | Red | `#eb144c` | Not received / not in place |

Items that cannot be auto-detected from data default to RED with evidence text "Manual review required".

## UI Components

### Summary KPIs (top of section)

Three `st.metric` columns:
- **Demands Met** — count of GREEN items out of 15
- **Outstanding** — count of RED items
- **Needs Verification** — count of YELLOW items

### Demand Table

Rendered as an HTML table (using `st.markdown` with `unsafe_allow_html=True`) with columns:
- Category
- Demand
- Frequency
- Status (color-coded pill using inline CSS, matching Variance Alerts style)
- Evidence (brief text explaining the status determination)

HTML table preferred over `st.dataframe` because `st.dataframe` does not support inline color styling for status pills.

### Compliance Progress Bar

A Plotly horizontal stacked bar chart (`go.Bar` with `barmode="stack"`, `orientation="h"`) showing GREEN/YELLOW/RED proportions. Single bar with three segments. This is visually distinct from the semicircular gauge used for contract compliance above it.

## Implementation Approach

### New function in `data_loader.py`

```python
@st.cache_data
def compute_board_demands() -> pd.DataFrame:
    """Compute status of 15 board demand items from CSCG.
    Returns DataFrame with columns: Category, Demand, Frequency, Status, Evidence."""
```

This function:
1. Defines the 15 demand items as a list of dicts with category, demand text, and frequency
2. Loads data from existing cached loaders, wrapped in try/except for each (defaulting to RED on failure)
3. Runs auto-detection logic per item using the specific logic defined above
4. Returns a DataFrame ready for display

### Changes to `pages/6_CSCG_Scorecard.py`

1. Import `compute_board_demands` from `data_loader`
2. Add a new section after the "Unauthorized Modifications" section and before the "AI Assessment" button
3. Render summary KPIs, the demand table with status styling, and a compliance progress bar
4. Extend the AI Assessment `scorecard_summary` string to include Board Demands summary (count of GREEN/YELLOW/RED)

### No new files

All logic lives in existing files. No new pages, no new data files.

## Error Handling

- If any underlying loader fails (returns empty DataFrame or raises), the demand item defaults to RED with evidence "Data unavailable — unable to verify"
- Each loader call in `compute_board_demands()` is individually wrapped in try/except to prevent one failure from cascading
- The section renders even if all items are RED — that itself is a useful signal to the board
- Uses `logging.warning` consistent with the data_loader hardening patterns established in this session

## Testing

Add tests for `compute_board_demands()` in `tests/test_data_loader.py`:
- Mock individual loader functions (`load_cscg_relationship`, `load_unauthorized_modifications`, `load_expense_flow_summary`, `compute_cscg_scorecard`) using `monkeypatch.setattr` on the `data_loader` module — not `pd.read_excel`, since this function composes multiple loaders
- Bypass `@st.cache_data` via `compute_board_demands.__wrapped__`
- Test with normal data — verify correct status assignment for auto-detected items
- Test with empty DataFrames from all loaders — verify all 15 items default to RED
- Test status counts — verify GREEN/YELLOW/RED tallies match expected values

## Visual Style

- Matches existing dark theme (`#0a192f` background, `#e6f1ff` text, `#a8b2d1` secondary text)
- Status pills use the same color palette as Variance Alerts page
- Section dividers (`st.markdown("---")`) consistent with rest of page
- Uses `style_chart` and `inject_css` utilities already imported on page 6

## Out of Scope

- Editing demand status from the UI (admin override) — defer to future PR
- Tracking status history over time — defer to future PR
- Email/notification when status changes — not planned
- Adding new demand items from the UI — static list, editable in code only
