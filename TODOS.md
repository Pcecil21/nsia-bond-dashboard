# TODOS

## P1 — High Priority

### Rotate cookie key and passwords
The old cookie key (`nsia_bond_dashboard_auth_key`) and bcrypt password hashes are in git history from prior commits. The cookie key has been moved to `st.secrets`, but the old value should be rotated to prevent session forgery by anyone with repo access. Passwords should also be rotated as a precaution.
- **Effort:** S (5 min operational task)
- **Impact:** Existing sessions invalidated; users re-login once

## P2 — Medium Priority

### Expand test coverage to all data loaders
`tests/test_data_loader.py` covers `_find_row`, `_find_rows_between`, `_find_row_reverse`, and `load_expense_flow_summary`. Remaining ~35 loader functions have no test coverage. Priority loaders: `load_fixed_obligations`, `load_scoreboard_10yr`, `load_scoreboard_alternative`, `load_historical_ad_revenue`, `compute_kpis`.
- **Effort:** M
- **Depends on:** Test infrastructure established in this PR

## P3 — Low Priority

### Consider exact-match or anchored matching in _find_row
`_find_row` uses substring matching (`text in str(val)`), which could match the wrong row if labels become similar (e.g., "Revenue" matching "Total Revenue"). Currently safe because spreadsheet labels are distinct enough. Revisit if label collisions emerge.
- **Effort:** S
- **Trigger:** When a loader returns wrong data due to ambiguous substring match

### Migrate all auth config to st.secrets
Currently `auth.yaml` is tracked in git with sanitized placeholder values; real cookie key lives in `st.secrets`. Full migration would move credentials entirely to `st.secrets` with a local-dev fallback, eliminating the config file for auth.
- **Effort:** M
- **Depends on:** Streamlit Cloud secrets management being the primary deploy target

### Add FileNotFoundError handling for missing Excel files
All loaders call `pd.read_excel()` without catching `FileNotFoundError`. If a data file is missing (e.g., after a fresh clone without GDrive sync), the app shows an unhandled Streamlit error page. Could wrap in a common decorator or try/except returning empty DataFrames.
- **Effort:** S
- **Note:** Pre-existing gap, not introduced by the data_loader refactor
