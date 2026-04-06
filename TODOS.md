# TODOS

## P1 — High Priority

### Rotate cookie key and passwords
The old cookie key (`nsia_bond_dashboard_auth_key`) and bcrypt password hashes are in git history from prior commits. The cookie key has been moved to `st.secrets`, but the old value should be rotated to prevent session forgery by anyone with repo access. Passwords should also be rotated as a precaution.
- **Effort:** S (5 min operational task)
- **Impact:** Existing sessions invalidated; users re-login once

### Email digest system
**What:** Weekly email to board members with RED/YELLOW flags, cash position, and dashboard CTA link.
**Why:** Board members who don't log in still get visibility into urgent financial issues.
**Pros:** Proactive communication, increases dashboard engagement.
**Cons:** New subsystem — SMTP/SendGrid creds, scheduling, recipient management, delivery monitoring. ~2 new files + credential setup.
**Context:** Data layer already exists (variance_engine, data_context, fiscal_period). Building the email template + delivery is the only new work. Deferred during Phase 3 eng review (2026-03-23) because it's orthogonal to the dashboard itself.
**Depends on:** Phase 3 completion (staleness indicator feeds into "data freshness" in email).
- **Effort:** M-L

## P2 — Medium Priority

### Expand test coverage to remaining data loaders
`tests/test_data_loader.py` now has 85 tests covering 31 functions. Remaining ~7 trivial loaders (CSV readers with no parsing logic) have no dedicated tests: `load_hockey_schedule`, `load_weekend_ice_breakdown`, `load_winnetka_nsia_usage`, `load_wilmette_nsia_usage`, `load_monthly_pnl`, `load_cash_forecast`, `load_contract_receivables`.
- **Effort:** S
- **Priority:** Low — these are thin wrappers around `pd.read_csv` with minimal logic

### Test backfill for fiscal_period.py and variance_engine.py
**What:** Add unit tests for the two core utility modules that currently have zero test coverage.
**Why:** These are the foundation of the entire dynamic dashboard — if fiscal_period misdetects the month, every page shows wrong data.
**Pros:** Catches regressions in month detection, FY boundary logic (Jul/Jun edges), flag threshold calculations.
**Cons:** ~150 lines of test code across 2 files. The modules have been stable since 2026-03-19.
**Context:** `test_data_loader.py` has 85 tests as a good pattern to follow. fiscal_period has edge cases around Jul/Jun FY boundaries. variance_engine has threshold logic worth pinning.
**Depends on:** Nothing — can be done independently.
- **Effort:** M

### Full mobile audit
**What:** Test all 17 pages on mobile viewport, fix custom HTML that doesn't stack.
**Why:** Board members check the dashboard on phones before meetings.
**Pros:** Better accessibility, professional appearance on all devices.
**Cons:** Streamlit has limited CSS control; some pages use native components that already adapt. Effort is ~1 session for diminishing returns beyond the home page.
**Context:** Phase 3 adds responsive CSS to app.py's verdict cards and payment bars (the established pattern). Other pages with custom HTML (Revenue & Ads, Operations) may need similar treatment.
**Depends on:** Phase 3 completion (home page CSS serves as the pattern to follow).
- **Effort:** M

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
