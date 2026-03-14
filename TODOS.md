# TODOS

## P1 — High Priority

### Rotate cookie key and passwords
The old cookie key (`nsia_bond_dashboard_auth_key`) and bcrypt password hashes are in git history from prior commits. The cookie key has been moved to `st.secrets`, but the old value should be rotated to prevent session forgery by anyone with repo access. Passwords should also be rotated as a precaution.
- **Effort:** S (5 min operational task)
- **Impact:** Existing sessions invalidated; users re-login once

## P2 — Medium Priority

### Expand test coverage to remaining data loaders
`tests/test_data_loader.py` now has 85 tests covering 31 functions. Remaining ~7 trivial loaders (CSV readers with no parsing logic) have no dedicated tests: `load_hockey_schedule`, `load_weekend_ice_breakdown`, `load_winnetka_nsia_usage`, `load_wilmette_nsia_usage`, `load_monthly_pnl`, `load_cash_forecast`, `load_contract_receivables`.
- **Effort:** S
- **Priority:** Low — these are thin wrappers around `pd.read_csv` with minimal logic

## P3 — Low Priority

### Consider exact-match or anchored matching in _find_row
`_find_row` uses substring matching (`text in str(val)`), which could match the wrong row if labels become similar (e.g., "Revenue" matching "Total Revenue"). Currently safe because spreadsheet labels are distinct enough. Revisit if label collisions emerge.
- **Effort:** S
- **Trigger:** When a loader returns wrong data due to ambiguous substring match

### Migrate all auth config to st.secrets
Currently `auth.yaml` is tracked in git with sanitized placeholder values; real cookie key lives in `st.secrets`. Full migration would move credentials entirely to `st.secrets` with a local-dev fallback, eliminating the config file for auth.
- **Effort:** M
- **Depends on:** Streamlit Cloud secrets management being the primary deploy target

### ~~Add FileNotFoundError handling for missing Excel files~~ DONE
All loaders now use `_read_excel()` wrapper that catches `FileNotFoundError` and returns empty DataFrame with a warning log.
