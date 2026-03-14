# TODOS

## P1 — High Priority

### Rotate cookie key and passwords
The old cookie key (`nsia_bond_dashboard_auth_key`) and bcrypt password hashes are in git history from prior commits. The cookie key has been moved to `st.secrets`, but the old value should be rotated to prevent session forgery by anyone with repo access. Passwords should also be rotated as a precaution.
- **Effort:** S (5 min operational task)
- **Impact:** Existing sessions invalidated; users re-login once

## P2 — Medium Priority

### Expand test coverage to remaining data loaders
`tests/test_data_loader.py` now covers helpers, `load_expense_flow_summary`, `compute_board_demands`, `load_fixed_obligations`, `load_scoreboard_10yr`, `load_scoreboard_alternative`, `load_historical_ad_revenue`, and `compute_kpis` (44 tests). Remaining ~30 loader functions have no test coverage.
- **Effort:** M
- **Depends on:** Test infrastructure established in prior PRs

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
