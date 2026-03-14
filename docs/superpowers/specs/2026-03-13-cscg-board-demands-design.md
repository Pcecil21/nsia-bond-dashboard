# CSCG Board Demands Section — Design Spec

## Summary

Add a "Board Demands — What NSIA Needs From CSCG" section to Page 6 (CSCG Scorecard). This section presents 15 specific documents, reports, and actions the board should require from the management company, with auto-detected status indicators (GREEN/YELLOW/RED) driven by existing dashboard data.

## Location

Page 6 (`pages/6_CSCG_Scorecard.py`), inserted between the "Unauthorized Modifications" section and the "Governance Recommendations" section.

## Data Dependencies

All data comes from existing loaders in `utils/data_loader.py`:

- `load_cscg_relationship()` — CSCG payment components
- `load_unauthorized_modifications()` — budget modifications without board approval
- `load_fixed_obligations()` — fixed obligations with variance data
- `load_expense_flow_summary()` — expense approval method breakdown
- `compute_cscg_scorecard()` — contract compliance status

No new data files or loaders are required.

## Demand Items (15 total, 5 categories)

### Financial Reporting (5)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 1 | Monthly itemized payroll report (names, hours, rates) | Monthly | Check `load_cscg_relationship()` for payroll line items. GREEN if data has itemized breakdown, YELLOW if aggregated single line, RED if no payroll data found. |
| 2 | Monthly expense reimbursement detail with receipts | Monthly | Check `load_fixed_obligations()` variance column. GREEN if all variances < $500 (suggests invoice backup exists), RED if variances > $500. |
| 3 | Invoice copies for all vendor payments > $500 | Monthly | Check `load_expense_flow_summary()` for non-board-approved amount. GREEN if board-approved % > 80%, YELLOW if 50-80%, RED if < 50%. |
| 4 | Quarterly revenue reconciliation (collected vs. deposited) | Quarterly | Default RED — no revenue reconciliation data currently available. |
| 5 | Monthly bank account transaction log | Monthly | Default RED — no bank transaction data currently available. |

### Budget Accountability (3)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 6 | Written variance explanation for any line item change > $2,500 | As needed | Check `load_unauthorized_modifications()`. Count HIGH/CRITICAL items. RED if any exist without explanatory notes, YELLOW if notes are partial, GREEN if none or all have notes. |
| 7 | Board pre-approval before any budget line modification | As needed | Check `load_unauthorized_modifications()` count. RED if any unauthorized modifications exist, GREEN if none. |
| 8 | Quarterly budget-to-actual comparison with CSCG commentary | Quarterly | Default YELLOW — budget-to-actual data exists but CSCG commentary is not verifiable from data. |

### Contract Compliance (3)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 9 | Current insurance certificates (GL, workers comp, D&O) | Annual | Default RED — "Manual review required". |
| 10 | Annual management fee reconciliation vs. contract terms | Annual | Check `compute_cscg_scorecard()` for management fee compliance status. Map COMPLIANT to GREEN, MINOR VARIANCE to YELLOW, NON-COMPLIANT to RED. |
| 11 | Proof of regulatory compliance (health dept, fire, refrigerant) | Annual | Default RED — "Manual review required". |

### Operational Transparency (2)

| # | Demand | Frequency | Auto-Detection Logic |
|---|--------|-----------|---------------------|
| 12 | Read-only access to operating bank account | One-time | Default RED — "Manual review required". |
| 13 | Monthly auto-pay transaction log with categorization | Monthly | Check `load_expense_flow_summary()` for auto-pay category. RED if auto-pay exists without itemized log data, YELLOW if partial. |

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

Rendered as a styled `st.dataframe` or HTML table with columns:
- Category
- Demand
- Frequency
- Status (color-coded pill)
- Evidence (brief text explaining the status determination)

### Compliance Progress Bar

A horizontal stacked bar showing GREEN/YELLOW/RED proportions, similar to the existing compliance gauge on this page.

## Implementation Approach

### New function in `data_loader.py`

```python
def compute_board_demands() -> pd.DataFrame:
    """Compute status of 15 board demand items from CSCG.
    Returns DataFrame with columns: Category, Demand, Frequency, Status, Evidence."""
```

This function:
1. Defines the 15 demand items as a list of dicts
2. Runs auto-detection logic for each item using existing cached loaders
3. Returns a DataFrame ready for display

### Changes to `pages/6_CSCG_Scorecard.py`

1. Import `compute_board_demands` from `data_loader`
2. Add a new section between "Unauthorized Modifications" and "Governance Recommendations"
3. Render summary KPIs, the demand table with status styling, and a compliance progress bar

### No new files

All logic lives in existing files. No new pages, no new data files.

## Error Handling

- If any underlying loader fails (returns empty DataFrame), the demand item defaults to RED with evidence "Data unavailable — unable to verify"
- The section renders even if all items are RED — that itself is a useful signal to the board
- Uses `logging.warning` consistent with the data_loader hardening patterns established in this session

## Testing

Add tests for `compute_board_demands()` in `tests/test_data_loader.py`:
- Test with normal data — verify correct status assignment
- Test with empty DataFrames — verify all items default to RED
- Test status counts — verify GREEN/YELLOW/RED tallies match expected

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
