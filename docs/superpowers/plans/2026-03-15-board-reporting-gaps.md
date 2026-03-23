# Board Reporting Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three missing board governance features: bank transaction upload with cash position charts, board actions/motions tracker with overdue alerts, and auto-extracted vendor master with contract compliance editing.

**Architecture:** Three independent features built as utility modules + Streamlit pages. Bank parser and vendor extractor are pure Python (no Streamlit dependency) for testability. Each feature reads/writes its own CSV/XLSX file in `data/`. Pages follow existing patterns: `inject_css()`, `require_auth()`, dark theme, Plotly charts.

**Tech Stack:** Python, Streamlit, Pandas, Plotly, openpyxl, difflib (stdlib for fuzzy matching)

**Spec:** `docs/superpowers/specs/2026-03-15-board-reporting-gaps-design.md`

---

## Chunk 1: Bank Transaction Parser & Upload

### Task 1: Bank CSV Parser Utility

**Files:**
- Create: `utils/bank_parser.py`
- Create: `tests/test_bank_parser.py`

- [ ] **Step 1: Write failing tests for bank parser**

```python
# tests/test_bank_parser.py
"""Tests for bank CSV parser — format detection and normalization."""
import pandas as pd
import pytest
from utils.bank_parser import parse_bank_csv, detect_format


class TestDetectFormat:
    def test_chase_format(self):
        csv = b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\nDEBIT,01/15/2026,COMED ELECTRIC,-250.00,ACH_DEBIT,45000.00,\n"
        assert detect_format(csv) == "chase"

    def test_bmo_format(self):
        csv = b"Date,Description,Withdrawals,Deposits,Balance\n01/15/2026,COMED ELECTRIC,250.00,,45000.00\n"
        assert detect_format(csv) == "bmo"

    def test_generic_format(self):
        csv = b"date,memo,amount,balance\n2026-01-15,COMED ELECTRIC,-250.00,45000.00\n"
        assert detect_format(csv) == "generic"

    def test_unknown_format_returns_none(self):
        csv = b"foo,bar,baz\n1,2,3\n"
        assert detect_format(csv) is None


class TestParseBankCsv:
    def test_chase_parses_correctly(self):
        csv = (
            b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
            b"DEBIT,01/15/2026,COMED ELECTRIC,-250.00,ACH_DEBIT,45000.00,\n"
            b"CREDIT,01/16/2026,ICE RENTAL DEPOSIT,5000.00,ACH_CREDIT,50000.00,\n"
        )
        df, errors = parse_bank_csv(csv, "chase_jan.csv")
        assert len(df) == 2
        assert list(df.columns) == ["date", "description", "amount", "balance", "category", "source_file", "import_date"]
        assert df.iloc[0]["amount"] == -250.00
        assert df.iloc[1]["amount"] == 5000.00
        assert df.iloc[0]["source_file"] == "chase_jan.csv"
        assert len(errors) == 0

    def test_bmo_combines_withdrawals_deposits(self):
        csv = (
            b"Date,Description,Withdrawals,Deposits,Balance\n"
            b"01/15/2026,COMED ELECTRIC,250.00,,45000.00\n"
            b"01/16/2026,ICE RENTAL,,5000.00,50000.00\n"
        )
        df, errors = parse_bank_csv(csv, "bmo_jan.csv")
        assert len(df) == 2
        assert df.iloc[0]["amount"] == -250.00  # withdrawal is negative
        assert df.iloc[1]["amount"] == 5000.00  # deposit is positive

    def test_generic_with_iso_dates(self):
        csv = b"date,memo,amount,balance\n2026-01-15,COMED,-250.00,45000.00\n"
        df, errors = parse_bank_csv(csv, "generic.csv")
        assert len(df) == 1
        assert str(df.iloc[0]["date"]) == "2026-01-15"

    def test_missing_balance_returns_nan(self):
        csv = b"date,description,amount\n2026-01-15,COMED,-250.00\n"
        df, errors = parse_bank_csv(csv, "no_balance.csv")
        assert len(df) == 1
        assert pd.isna(df.iloc[0]["balance"])

    def test_bad_rows_skipped_with_errors(self):
        csv = (
            b"date,description,amount,balance\n"
            b"2026-01-15,COMED,-250.00,45000.00\n"
            b"not-a-date,BAD ROW,xyz,abc\n"
            b"2026-01-16,GOOD ROW,-100.00,44900.00\n"
        )
        df, errors = parse_bank_csv(csv, "mixed.csv")
        assert len(df) == 2  # bad row skipped
        assert len(errors) == 1

    def test_empty_file_returns_empty(self):
        csv = b""
        df, errors = parse_bank_csv(csv, "empty.csv")
        assert len(df) == 0

    def test_unknown_format_returns_empty_with_error(self):
        csv = b"foo,bar,baz\n1,2,3\n"
        df, errors = parse_bank_csv(csv, "weird.csv")
        assert len(df) == 0
        assert len(errors) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\nsia-bond-dashboard && python -m pytest tests/test_bank_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.bank_parser'`

- [ ] **Step 3: Implement bank parser**

```python
# utils/bank_parser.py
"""Bank CSV format detection and parsing for NSIA dashboard."""
import io
import pandas as pd
from datetime import date


# Column name patterns for format detection
CHASE_COLS = {"details", "posting date", "description", "amount", "type", "balance"}
BMO_COLS = {"date", "description", "withdrawals", "deposits", "balance"}
GENERIC_DATE = {"date", "posting date", "trans date", "transaction date"}
GENERIC_DESC = {"description", "memo", "payee", "narrative"}
GENERIC_AMT = {"amount", "debit", "credit"}

# Standard output columns
OUTPUT_COLS = ["date", "description", "amount", "balance", "category", "source_file", "import_date"]


def detect_format(file_bytes: bytes) -> str | None:
    """Detect bank CSV format from header row. Returns 'chase', 'bmo', 'generic', or None."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        first_line = text.split("\n")[0].strip().lower()
        cols = {c.strip().strip('"') for c in first_line.split(",")}
    except Exception:
        return None

    if CHASE_COLS.issubset(cols):
        return "chase"
    if BMO_COLS.issubset(cols):
        return "bmo"
    # Generic: needs at least a date-like and description-like column
    if cols & GENERIC_DATE and cols & GENERIC_DESC:
        return "generic"
    # Try amount columns too
    if cols & GENERIC_DATE and cols & GENERIC_AMT:
        return "generic"
    return None


def _find_col(df_cols: list[str], candidates: set[str]) -> str | None:
    """Find the first column name matching any candidate (case-insensitive)."""
    for col in df_cols:
        if col.strip().lower() in candidates:
            return col
    return None


def _parse_dates(series: pd.Series) -> pd.Series:
    """Try US format first (MM/DD/YYYY), then ISO (YYYY-MM-DD)."""
    try:
        return pd.to_datetime(series, format="%m/%d/%Y").dt.date
    except (ValueError, TypeError):
        pass
    try:
        return pd.to_datetime(series, format="%Y-%m-%d").dt.date
    except (ValueError, TypeError):
        pass
    return pd.to_datetime(series, format="mixed", dayfirst=False).dt.date


def parse_bank_csv(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse a bank CSV into standardized format.

    Returns:
        (DataFrame with OUTPUT_COLS, list of error messages for skipped rows)
    """
    errors = []
    empty = pd.DataFrame(columns=OUTPUT_COLS)

    if not file_bytes or not file_bytes.strip():
        return empty, errors

    fmt = detect_format(file_bytes)
    if fmt is None:
        return empty, ["Unrecognized CSV format. Expected Chase, BMO, or generic (date + description + amount columns)."]

    try:
        raw = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        return empty, [f"Could not read CSV: {e}"]

    if raw.empty:
        return empty, errors

    # Normalize column names for matching
    raw.columns = [c.strip() for c in raw.columns]
    cols_lower = [c.lower() for c in raw.columns]

    today = date.today().isoformat()
    rows = []

    for idx, row in raw.iterrows():
        try:
            if fmt == "chase":
                dt = pd.to_datetime(row.iloc[1], format="%m/%d/%Y").date()
                desc = str(row.iloc[2]).strip()
                amt = float(row.iloc[3])
                bal = float(row.iloc[5]) if pd.notna(row.iloc[5]) and row.iloc[5] != "" else None
            elif fmt == "bmo":
                dt = pd.to_datetime(row.iloc[0], format="%m/%d/%Y").date()
                desc = str(row.iloc[1]).strip()
                withdrawal = float(row.iloc[2]) if pd.notna(row.iloc[2]) and row.iloc[2] != "" else 0.0
                deposit = float(row.iloc[3]) if pd.notna(row.iloc[3]) and row.iloc[3] != "" else 0.0
                amt = deposit - withdrawal  # deposits positive, withdrawals negative
                bal = float(row.iloc[4]) if pd.notna(row.iloc[4]) and row.iloc[4] != "" else None
            else:  # generic
                # Find date column
                date_col = _find_col(raw.columns, GENERIC_DATE)
                desc_col = _find_col(raw.columns, GENERIC_DESC)
                amt_col = _find_col(raw.columns, GENERIC_AMT)
                bal_col = _find_col(raw.columns, {"balance", "running balance", "bal"})

                date_val = row[date_col] if date_col else None
                if date_val is None:
                    raise ValueError("No date column found")

                # Try parsing date
                try:
                    dt = pd.to_datetime(date_val, format="%m/%d/%Y").date()
                except (ValueError, TypeError):
                    dt = pd.to_datetime(date_val, format="%Y-%m-%d").date()

                desc = str(row[desc_col]).strip() if desc_col else ""
                amt = float(row[amt_col]) if amt_col else 0.0
                bal = float(row[bal_col]) if bal_col and pd.notna(row.get(bal_col)) and row.get(bal_col) != "" else None

            rows.append({
                "date": dt,
                "description": desc,
                "amount": round(amt, 2),
                "balance": round(bal, 2) if bal is not None else None,
                "category": None,
                "source_file": filename,
                "import_date": today,
            })
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")

    if not rows:
        return empty, errors

    df = pd.DataFrame(rows, columns=OUTPUT_COLS)
    return df, errors


def deduplicate(new_df: pd.DataFrame, existing_df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows from new_df that already exist in existing_df.
    Match on exact date + exact amount + case-insensitive description."""
    if existing_df.empty:
        return new_df

    existing_keys = set()
    for _, row in existing_df.iterrows():
        key = (str(row["date"]), float(row["amount"]), str(row["description"]).lower().strip())
        existing_keys.add(key)

    mask = []
    for _, row in new_df.iterrows():
        key = (str(row["date"]), float(row["amount"]), str(row["description"]).lower().strip())
        mask.append(key not in existing_keys)

    return new_df[mask].reset_index(drop=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Projects\nsia-bond-dashboard && python -m pytest tests/test_bank_parser.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/bank_parser.py tests/test_bank_parser.py
git commit -m "feat: add bank CSV parser with Chase/BMO/generic format detection"
```

### Task 2: Bank Transactions Section on Monthly Financials Page

**Files:**
- Create: `data/bank_transactions.csv` (empty with headers)
- Modify: `pages/7_Monthly_Financials.py` — add Section 4 at end

- [ ] **Step 1: Create empty bank_transactions.csv**

```csv
date,description,amount,balance,category,source_file,import_date
```

- [ ] **Step 2: Add bank transactions section to Page 7**

Add after the AI Monthly Analysis section (line ~388) in `pages/7_Monthly_Financials.py`:

```python
# ══════════════════════════════════════════════════════════════════════════
# Section 4: Bank Transactions & Cash Position
# ══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.header("Bank Transactions & Cash Position")
st.caption("Upload bank statement CSVs to track actual cash position vs forecast")

from utils.bank_parser import parse_bank_csv, deduplicate

BANK_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bank_transactions.csv")

# Upload widget
uploaded_bank = st.file_uploader(
    "Upload bank statement CSV",
    type=["csv"],
    help="Supported formats: Chase, BMO, or generic (date + description + amount columns)",
    key="bank_upload",
)

if uploaded_bank is not None:
    file_bytes = uploaded_bank.read()
    new_txns, parse_errors = parse_bank_csv(file_bytes, uploaded_bank.name)

    if parse_errors:
        for err in parse_errors:
            st.warning(err)

    if not new_txns.empty:
        # Load existing and deduplicate
        try:
            existing = pd.read_csv(BANK_CSV_PATH)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            existing = pd.DataFrame()

        deduped = deduplicate(new_txns, existing)
        st.info(f"Parsed **{len(new_txns)}** transactions, **{len(deduped)}** are new (after dedup)")

        if not deduped.empty and st.button("Import Transactions", type="primary", key="import_bank"):
            # Append to CSV
            header = existing.empty
            deduped.to_csv(BANK_CSV_PATH, mode="a", header=header, index=False)
            st.success(f"Imported {len(deduped)} transactions.")
            st.rerun()

# Display existing transactions
try:
    bank_df = pd.read_csv(BANK_CSV_PATH)
except (FileNotFoundError, pd.errors.EmptyDataError):
    bank_df = pd.DataFrame()

if not bank_df.empty:
    bank_df["date"] = pd.to_datetime(bank_df["date"])
    bank_df = bank_df.sort_values("date")

    # Metric cards
    latest_balance = bank_df.dropna(subset=["balance"])
    if not latest_balance.empty:
        current_bal = latest_balance.iloc[-1]["balance"]
        total_deposits = bank_df[bank_df["amount"] > 0]["amount"].sum()
        total_withdrawals = bank_df[bank_df["amount"] < 0]["amount"].sum()
        large_txns = bank_df[bank_df["amount"].abs() > 5000]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Balance", f"${current_bal:,.0f}")
        with col2:
            st.metric("Total Deposits", f"${total_deposits:,.0f}")
        with col3:
            st.metric("Total Withdrawals", f"${abs(total_withdrawals):,.0f}")
        with col4:
            st.metric("Large Transactions (>$5K)", len(large_txns))

    # Cash position chart
    balance_data = bank_df.dropna(subset=["balance"])
    if not balance_data.empty:
        fig_bank = go.Figure()
        fig_bank.add_trace(go.Scatter(
            x=balance_data["date"], y=balance_data["balance"],
            name="Bank Balance",
            mode="lines+markers",
            line=dict(color="#64ffda", width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%b %d}<br>Balance: $%{y:,.0f}<extra></extra>",
        ))

        # Overlay cash forecast if available
        try:
            forecast = load_cash_forecast()
            # Map forecast months to approximate dates
            month_map = {
                "Jul": "2025-07-15", "Aug": "2025-08-15", "Sep": "2025-09-15",
                "Oct": "2025-10-15", "Nov": "2025-11-15", "Dec": "2025-12-15",
                "Jan": "2026-01-15", "Feb": "2026-02-15", "Mar": "2026-03-15",
                "Apr": "2026-04-15", "May": "2026-05-15", "Jun": "2026-06-15",
            }
            forecast["date"] = forecast["Month"].map(month_map)
            forecast["date"] = pd.to_datetime(forecast["date"])
            fig_bank.add_trace(go.Scatter(
                x=forecast["date"], y=forecast["Cumulative Cash"],
                name="Forecast",
                mode="lines",
                line=dict(color="#fcb900", width=2, dash="dash"),
                hovertemplate="%{x|%b %d}<br>Forecast: $%{y:,.0f}<extra></extra>",
            ))
        except Exception:
            pass

        fig_bank.update_layout(
            title="Actual Cash Position vs Forecast",
            yaxis_title="Balance ($)",
        )
        style_chart(fig_bank, 420)
        st.plotly_chart(fig_bank, use_container_width=True)

    # Large transaction alerts
    if not large_txns.empty:
        st.subheader("Large Transactions (> $5,000)")
        st.dataframe(
            large_txns[["date", "description", "amount", "balance"]].sort_values("date", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "amount": st.column_config.NumberColumn(format="$%,.2f"),
                "balance": st.column_config.NumberColumn(format="$%,.2f"),
            },
        )

    # Full transaction table
    with st.expander(f"All Transactions ({len(bank_df)} rows)"):
        st.dataframe(
            bank_df[["date", "description", "amount", "balance", "source_file"]].sort_values("date", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "amount": st.column_config.NumberColumn(format="$%,.2f"),
                "balance": st.column_config.NumberColumn(format="$%,.2f"),
            },
        )
else:
    st.info("No bank transactions imported yet. Upload a CSV above to get started.")
```

Also add `import os` at top of page if not already present (it's not — the page uses `Path` but not `os`).

- [ ] **Step 3: Test manually — load Page 7, verify section appears with upload widget**

- [ ] **Step 4: Commit**

```bash
git add data/bank_transactions.csv pages/7_Monthly_Financials.py
git commit -m "feat: add bank transaction upload and cash position to Monthly Financials"
```

---

## Chunk 2: Board Actions Log

### Task 3: Board Actions Data Template

**Files:**
- Create: `data/board_actions.xlsx` (empty template with Motions and Action Items sheets)

- [ ] **Step 1: Create starter Excel template**

```python
# Run once to create template:
import pandas as pd

motions_cols = ["id", "meeting_date", "motion", "category", "outcome",
                "votes_for", "votes_against", "votes_abstain", "notes", "minutes_doc_id"]
actions_cols = ["id", "motion_id", "created_date", "description", "assignee",
                "due_date", "status", "completed_date", "notes"]

with pd.ExcelWriter("data/board_actions.xlsx", engine="openpyxl") as writer:
    pd.DataFrame(columns=motions_cols).to_excel(writer, sheet_name="Motions", index=False)
    pd.DataFrame(columns=actions_cols).to_excel(writer, sheet_name="Action Items", index=False)
```

- [ ] **Step 2: Commit**

```bash
git add data/board_actions.xlsx
git commit -m "feat: add board_actions.xlsx starter template"
```

### Task 4: Board Actions Page

**Files:**
- Create: `pages/15_Board_Actions.py`

- [ ] **Step 1: Create Board Actions page**

```python
# pages/15_Board_Actions.py
"""
Page 15: Board Actions
Track board motions, votes, and action items with overdue alerting.
"""
import streamlit as st
import pandas as pd
import uuid
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.theme import inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Board Actions | NSIA", layout="wide", page_icon=":ice_hockey:")
inject_css()
require_auth()

st.title("Board Actions")
st.caption("Board motions, votes, and action items with deadline tracking")

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "board_actions.xlsx")

MOTION_CATEGORIES = ["Financial", "Operations", "Governance", "Personnel", "Other"]
MOTION_OUTCOMES = ["Passed", "Failed", "Tabled", "Withdrawn"]
ACTION_STATUSES = ["Open", "In Progress", "Done"]


# ── Data loading ─────────────────────────────────────────────────────────
def load_motions() -> pd.DataFrame:
    try:
        df = pd.read_excel(DATA_PATH, sheet_name="Motions", dtype={"id": str, "minutes_doc_id": str})
        if "meeting_date" in df.columns:
            df["meeting_date"] = pd.to_datetime(df["meeting_date"]).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "meeting_date", "motion", "category", "outcome",
                                      "votes_for", "votes_against", "votes_abstain", "notes", "minutes_doc_id"])


def load_actions() -> pd.DataFrame:
    try:
        df = pd.read_excel(DATA_PATH, sheet_name="Action Items", dtype={"id": str, "motion_id": str})
        for col in ["created_date", "due_date", "completed_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "motion_id", "created_date", "description", "assignee",
                                      "due_date", "status", "completed_date", "notes"])


def save_data(motions: pd.DataFrame, actions: pd.DataFrame):
    with pd.ExcelWriter(DATA_PATH, engine="openpyxl") as writer:
        motions.to_excel(writer, sheet_name="Motions", index=False)
        actions.to_excel(writer, sheet_name="Action Items", index=False)


motions = load_motions()
actions = load_actions()

# ── Upload existing Excel ────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload board_actions.xlsx (or add entries with the forms below)",
    type=["xlsx"],
    key="board_actions_upload",
)
if uploaded:
    try:
        new_motions = pd.read_excel(uploaded, sheet_name="Motions", dtype={"id": str, "minutes_doc_id": str})
        new_actions = pd.read_excel(uploaded, sheet_name="Action Items", dtype={"id": str, "motion_id": str})
        save_data(new_motions, new_actions)
        st.success("Imported board actions data.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not read uploaded file: {e}")

# ── Summary metrics ──────────────────────────────────────────────────────
today = date.today()
open_actions = actions[actions["status"].isin(["Open", "In Progress"])] if not actions.empty else pd.DataFrame()
overdue = open_actions[open_actions["due_date"] < today] if not open_actions.empty and "due_date" in open_actions.columns else pd.DataFrame()
due_soon = open_actions[
    (open_actions["due_date"] >= today) & (open_actions["due_date"] <= today + timedelta(days=7))
] if not open_actions.empty and "due_date" in open_actions.columns else pd.DataFrame()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Motions", len(motions))
with col2:
    st.metric("Open Action Items", len(open_actions))
with col3:
    st.metric("Overdue", len(overdue))
with col4:
    st.metric("Due This Week", len(due_soon))

# ── Overdue alerts ───────────────────────────────────────────────────────
if not overdue.empty:
    st.error(f"**{len(overdue)} overdue action item(s):**")
    for _, row in overdue.iterrows():
        days_late = (today - row["due_date"]).days
        st.markdown(
            f'<div style="padding:8px 14px;margin:4px 0;border-left:3px solid #eb144c;'
            f'background:rgba(235,20,76,0.08);border-radius:4px;">'
            f'<b style="color:#ff6b6b;">{row["description"]}</b> '
            f'<span style="color:#a8b2d1;">({row["assignee"]}) — {days_late} days overdue</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

if not due_soon.empty:
    st.warning(f"**{len(due_soon)} action item(s) due this week**")

st.markdown("---")

# ── Motions ──────────────────────────────────────────────────────────────
st.header("Board Motions")

if not motions.empty:
    display_motions = motions[["meeting_date", "motion", "category", "outcome", "votes_for", "votes_against"]].copy()
    st.dataframe(
        display_motions.sort_values("meeting_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Add New Motion"):
    with st.form("add_motion", clear_on_submit=True):
        m_date = st.date_input("Meeting Date", value=today)
        m_motion = st.text_area("Motion Text")
        m_category = st.selectbox("Category", MOTION_CATEGORIES)
        m_outcome = st.selectbox("Outcome", MOTION_OUTCOMES)
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            m_for = st.number_input("Votes For", min_value=0, value=0)
        with m_col2:
            m_against = st.number_input("Votes Against", min_value=0, value=0)
        with m_col3:
            m_abstain = st.number_input("Abstentions", min_value=0, value=0)
        m_notes = st.text_input("Notes (optional)")

        if st.form_submit_button("Add Motion", type="primary"):
            if m_motion.strip():
                new_row = pd.DataFrame([{
                    "id": str(uuid.uuid4()),
                    "meeting_date": m_date,
                    "motion": m_motion.strip(),
                    "category": m_category,
                    "outcome": m_outcome,
                    "votes_for": m_for,
                    "votes_against": m_against,
                    "votes_abstain": m_abstain,
                    "notes": m_notes,
                    "minutes_doc_id": None,
                }])
                motions = pd.concat([motions, new_row], ignore_index=True)
                save_data(motions, actions)
                st.success("Motion added.")
                st.rerun()
            else:
                st.warning("Please enter motion text.")

st.markdown("---")

# ── Action Items ─────────────────────────────────────────────────────────
st.header("Action Items")

# Three-column status view
if not actions.empty:
    col_open, col_progress, col_done = st.columns(3)

    with col_open:
        st.subheader("Open")
        open_items = actions[actions["status"] == "Open"].sort_values("due_date")
        for _, row in open_items.iterrows():
            is_overdue = pd.notna(row["due_date"]) and row["due_date"] < today
            border_color = "#eb144c" if is_overdue else "#0984e3"
            st.markdown(
                f'<div style="padding:10px;margin:6px 0;border-left:3px solid {border_color};'
                f'background:rgba(9,132,227,0.08);border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row["description"]}</b><br>'
                f'<span style="color:#a8b2d1;font-size:0.85rem;">{row["assignee"]} | Due: {row["due_date"]}'
                f'{"  ⚠️ OVERDUE" if is_overdue else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_progress:
        st.subheader("In Progress")
        progress_items = actions[actions["status"] == "In Progress"].sort_values("due_date")
        for _, row in progress_items.iterrows():
            is_overdue = pd.notna(row["due_date"]) and row["due_date"] < today
            border_color = "#eb144c" if is_overdue else "#fcb900"
            st.markdown(
                f'<div style="padding:10px;margin:6px 0;border-left:3px solid {border_color};'
                f'background:rgba(252,185,0,0.08);border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row["description"]}</b><br>'
                f'<span style="color:#a8b2d1;font-size:0.85rem;">{row["assignee"]} | Due: {row["due_date"]}'
                f'{"  ⚠️ OVERDUE" if is_overdue else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_done:
        st.subheader("Done")
        done_items = actions[actions["status"] == "Done"].sort_values("completed_date", ascending=False)
        for _, row in done_items.iterrows():
            st.markdown(
                f'<div style="padding:10px;margin:6px 0;border-left:3px solid #00d084;'
                f'background:rgba(0,208,132,0.08);border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row["description"]}</b><br>'
                f'<span style="color:#a8b2d1;font-size:0.85rem;">{row["assignee"]} | Completed: {row.get("completed_date", "—")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info("No action items yet. Add one below.")

# Add action item form
with st.expander("Add New Action Item"):
    with st.form("add_action", clear_on_submit=True):
        a_desc = st.text_area("Description")
        a_assignee = st.text_input("Assignee")
        a_due = st.date_input("Due Date", value=today + timedelta(days=14))
        a_status = st.selectbox("Status", ACTION_STATUSES)
        a_notes = st.text_input("Notes (optional)")

        if st.form_submit_button("Add Action Item", type="primary"):
            if a_desc.strip() and a_assignee.strip():
                completed = today if a_status == "Done" else None
                new_row = pd.DataFrame([{
                    "id": str(uuid.uuid4()),
                    "motion_id": None,
                    "created_date": today,
                    "description": a_desc.strip(),
                    "assignee": a_assignee.strip(),
                    "due_date": a_due,
                    "status": a_status,
                    "completed_date": completed,
                    "notes": a_notes,
                }])
                actions = pd.concat([actions, new_row], ignore_index=True)
                save_data(motions, actions)
                st.success("Action item added.")
                st.rerun()
            else:
                st.warning("Please enter description and assignee.")

# Update status
if not actions.empty:
    st.markdown("---")
    with st.expander("Update Action Item Status"):
        action_options = {
            f"{row['description'][:50]} ({row['assignee']})": row["id"]
            for _, row in actions[actions["status"] != "Done"].iterrows()
        }
        if action_options:
            selected = st.selectbox("Select item", list(action_options.keys()))
            new_status = st.selectbox("New status", ACTION_STATUSES, key="update_status")
            if st.button("Update", type="primary", key="update_action_btn"):
                action_id = action_options[selected]
                idx = actions[actions["id"] == action_id].index[0]
                actions.at[idx, "status"] = new_status
                if new_status == "Done":
                    actions.at[idx, "completed_date"] = today
                save_data(motions, actions)
                st.success("Updated.")
                st.rerun()
        else:
            st.info("All action items are done!")
```

- [ ] **Step 2: Test manually — load Page 15, add a motion and action item**

- [ ] **Step 3: Commit**

```bash
git add pages/15_Board_Actions.py
git commit -m "feat: add Board Actions page with motions, action items, and overdue tracking"
```

### Task 5: Overdue Alerts on Variance Alerts Page

**Files:**
- Modify: `pages/5_Variance_Alerts.py` — add board actions alert section after title

- [ ] **Step 1: Add overdue action items section**

Insert after line 23 (`st.caption(...)`) and before line 25 (`from utils.data_loader...`):

```python
# ── Board Action Item Alerts ─────────────────────────────────────────────
try:
    _board_actions_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "board_actions.xlsx")
    if os.path.exists(_board_actions_path):
        _ba_actions = pd.read_excel(_board_actions_path, sheet_name="Action Items", dtype={"id": str})
        if not _ba_actions.empty and "due_date" in _ba_actions.columns:
            _ba_actions["due_date"] = pd.to_datetime(_ba_actions["due_date"]).dt.date
            _today = __import__("datetime").date.today()
            _open = _ba_actions[_ba_actions["status"].isin(["Open", "In Progress"])]
            _overdue = _open[_open["due_date"] < _today]
            _due_soon = _open[(_open["due_date"] >= _today) & (_open["due_date"] <= _today + __import__("datetime").timedelta(days=7))]

            if not _overdue.empty or not _due_soon.empty:
                ba_col1, ba_col2 = st.columns(2)
                with ba_col1:
                    if not _overdue.empty:
                        st.metric("Overdue Board Actions", len(_overdue))
                with ba_col2:
                    if not _due_soon.empty:
                        st.metric("Due This Week", len(_due_soon))
                st.markdown("---")
except Exception:
    pass  # Don't break variance page if board actions file is missing
```

Also add `import os` at top if not present.

- [ ] **Step 2: Test manually — verify alerts show on Variance Alerts page when overdue items exist**

- [ ] **Step 3: Commit**

```bash
git add pages/5_Variance_Alerts.py
git commit -m "feat: surface overdue board action items on Variance Alerts page"
```

---

## Chunk 3: Vendor Master

### Task 6: Vendor Extractor Utility

**Files:**
- Create: `utils/vendor_extractor.py`
- Create: `tests/test_vendor_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vendor_extractor.py
"""Tests for vendor extractor — extraction, fuzzy dedup, merge."""
import pandas as pd
import pytest
from utils.vendor_extractor import extract_vendors_from_bills, fuzzy_dedup, merge_with_existing


class TestExtractVendorsFromBills:
    def test_extracts_unique_vendors(self):
        bills = pd.DataFrame({
            "Date": ["2025-08-01", "2025-08-02", "2025-09-01"],
            "Vendor": ["ComEd", "CSCG", "ComEd"],
            "Amount": [250.00, 5000.00, 300.00],
            "Category": ["Utilities", "Management", "Utilities"],
        })
        result = extract_vendors_from_bills(bills)
        assert len(result) == 2
        comed = result[result["vendor_name"] == "ComEd"].iloc[0]
        assert comed["total_spend_ytd"] == 550.00
        assert comed["payment_count"] == 2

    def test_empty_df_returns_empty(self):
        bills = pd.DataFrame(columns=["Date", "Vendor", "Amount", "Category"])
        result = extract_vendors_from_bills(bills)
        assert len(result) == 0


class TestFuzzyDedup:
    def test_merges_similar_names(self):
        df = pd.DataFrame({
            "vendor_id": ["a", "b"],
            "vendor_name": ["Commonwealth Edison", "COMMONWEALTH EDISON CO"],
            "total_spend_ytd": [100.0, 200.0],
            "payment_count": [1, 2],
        })
        proposals = fuzzy_dedup(df, threshold=0.8)
        assert len(proposals) >= 1
        assert proposals[0]["keep"] == "a" or proposals[0]["keep"] == "b"

    def test_does_not_merge_different_names(self):
        df = pd.DataFrame({
            "vendor_id": ["a", "b"],
            "vendor_name": ["ComEd", "Zamboni Company"],
            "total_spend_ytd": [100.0, 200.0],
            "payment_count": [1, 2],
        })
        proposals = fuzzy_dedup(df, threshold=0.8)
        assert len(proposals) == 0


class TestMergeWithExisting:
    def test_preserves_manual_fields(self):
        new_df = pd.DataFrame({
            "vendor_id": ["abc"],
            "vendor_name": ["ComEd"],
            "total_spend_ytd": [999.0],
            "payment_count": [5],
            "risk_flag": ["None"],
            "contract_terms": [None],
        })
        existing = pd.DataFrame({
            "vendor_id": ["abc"],
            "vendor_name": ["ComEd"],
            "total_spend_ytd": [500.0],
            "payment_count": [3],
            "risk_flag": ["High"],
            "contract_terms": ["Net 30"],
        })
        result = merge_with_existing(new_df, existing)
        row = result[result["vendor_id"] == "abc"].iloc[0]
        assert row["total_spend_ytd"] == 999.0  # updated
        assert row["risk_flag"] == "High"  # preserved
        assert row["contract_terms"] == "Net 30"  # preserved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Projects\nsia-bond-dashboard && python -m pytest tests/test_vendor_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement vendor extractor**

```python
# utils/vendor_extractor.py
"""Vendor extraction from GL and bills data with fuzzy dedup."""
import uuid
from difflib import SequenceMatcher
from datetime import date
import pandas as pd


MANUAL_FIELDS = ["contract_start", "contract_end", "contract_terms", "contract_doc_id",
                 "compliance_notes", "risk_flag", "category"]


def extract_vendors_from_bills(bills_df: pd.DataFrame) -> pd.DataFrame:
    """Extract unique vendors from bills_summary.xlsx DataFrame."""
    if bills_df.empty or "Vendor" not in bills_df.columns:
        return pd.DataFrame()

    bills_df = bills_df.copy()
    bills_df["Amount"] = pd.to_numeric(bills_df["Amount"], errors="coerce").fillna(0)
    if "Date" in bills_df.columns:
        bills_df["Date"] = pd.to_datetime(bills_df["Date"], errors="coerce")

    grouped = bills_df.groupby("Vendor").agg(
        total_spend_ytd=("Amount", "sum"),
        payment_count=("Amount", "count"),
        first_seen=("Date", "min"),
        last_seen=("Date", "max"),
        category=("Category", lambda x: x.mode().iloc[0] if not x.mode().empty else "Other"),
    ).reset_index()

    grouped.rename(columns={"Vendor": "vendor_name"}, inplace=True)
    grouped["vendor_id"] = [str(uuid.uuid4()) for _ in range(len(grouped))]
    grouped["aliases"] = ""
    grouped["first_seen"] = grouped["first_seen"].dt.date if "first_seen" in grouped.columns else None
    grouped["last_seen"] = grouped["last_seen"].dt.date if "last_seen" in grouped.columns else None

    # Pre-flag CSCG
    grouped["risk_flag"] = "None"
    cscg_mask = grouped["vendor_name"].str.contains("CSCG|Canlan", case=False, na=False)
    grouped.loc[cscg_mask, "risk_flag"] = "High"

    for field in ["contract_start", "contract_end", "contract_terms", "contract_doc_id", "compliance_notes"]:
        grouped[field] = None

    return grouped


def extract_vendors_from_gl(gl_df: pd.DataFrame) -> pd.DataFrame:
    """Extract unique payees from general_ledger.xlsx DataFrame.
    GL has headers on row 2 (0-indexed), with Payee in the last column."""
    if gl_df.empty:
        return pd.DataFrame()

    # Find the header row
    for i in range(min(5, len(gl_df))):
        row_vals = [str(v).strip().lower() for v in gl_df.iloc[i] if pd.notna(v)]
        if "payee" in row_vals or "description" in row_vals:
            headers = [str(v).strip() if pd.notna(v) else f"col_{j}" for j, v in enumerate(gl_df.iloc[i])]
            gl_df.columns = headers
            gl_df = gl_df.iloc[i + 1:].reset_index(drop=True)
            break

    if "Payee" not in gl_df.columns:
        return pd.DataFrame()

    gl_df = gl_df.dropna(subset=["Payee"])
    gl_df["Payee"] = gl_df["Payee"].astype(str).str.strip()
    gl_df = gl_df[gl_df["Payee"] != ""]

    # Parse amounts
    for col in ["Debit", "Credit"]:
        if col in gl_df.columns:
            gl_df[col] = pd.to_numeric(gl_df[col].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce").fillna(0)

    if "Debit" in gl_df.columns:
        gl_df["amount"] = gl_df.get("Debit", 0)
    else:
        gl_df["amount"] = 0

    grouped = gl_df.groupby("Payee").agg(
        total_spend_ytd=("amount", "sum"),
        payment_count=("amount", "count"),
    ).reset_index()

    grouped.rename(columns={"Payee": "vendor_name"}, inplace=True)
    grouped["vendor_id"] = [str(uuid.uuid4()) for _ in range(len(grouped))]
    grouped["aliases"] = ""
    grouped["risk_flag"] = "None"
    grouped["category"] = "Other"

    return grouped


def fuzzy_dedup(df: pd.DataFrame, threshold: float = 0.85) -> list[dict]:
    """Find vendor name pairs that are likely duplicates.
    Returns list of proposed merges: [{"keep": id1, "merge": id2, "score": float, "name_keep": str, "name_merge": str}]"""
    if len(df) < 2:
        return []

    proposals = []
    names = df["vendor_name"].tolist()
    ids = df["vendor_id"].tolist()
    seen = set()

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if j in seen:
                continue
            score = SequenceMatcher(None, names[i].lower(), names[j].lower()).ratio()
            if score >= threshold:
                proposals.append({
                    "keep": ids[i],
                    "merge": ids[j],
                    "score": round(score, 3),
                    "name_keep": names[i],
                    "name_merge": names[j],
                })
                seen.add(j)

    return proposals


def apply_merges(df: pd.DataFrame, approved_merges: list[dict]) -> pd.DataFrame:
    """Apply approved fuzzy merges. Keep row, aggregate spend, add alias."""
    df = df.copy()
    for merge in approved_merges:
        keep_mask = df["vendor_id"] == merge["keep"]
        merge_mask = df["vendor_id"] == merge["merge"]

        if keep_mask.sum() == 0 or merge_mask.sum() == 0:
            continue

        keep_idx = df[keep_mask].index[0]
        merge_row = df[merge_mask].iloc[0]

        # Aggregate spend
        df.at[keep_idx, "total_spend_ytd"] = df.at[keep_idx, "total_spend_ytd"] + merge_row["total_spend_ytd"]
        df.at[keep_idx, "payment_count"] = df.at[keep_idx, "payment_count"] + merge_row["payment_count"]

        # Add alias
        existing_aliases = str(df.at[keep_idx, "aliases"]) if pd.notna(df.at[keep_idx, "aliases"]) else ""
        new_alias = merge_row["vendor_name"]
        if existing_aliases:
            df.at[keep_idx, "aliases"] = f"{existing_aliases};{new_alias}"
        else:
            df.at[keep_idx, "aliases"] = new_alias

        # Drop merged row
        df = df[~merge_mask]

    return df.reset_index(drop=True)


def merge_with_existing(new_df: pd.DataFrame, existing_df: pd.DataFrame) -> pd.DataFrame:
    """Merge new extraction with existing vendor master, preserving manual edits."""
    if existing_df.empty:
        return new_df

    result = new_df.copy()

    for field in MANUAL_FIELDS:
        if field not in result.columns:
            result[field] = None

    # For each existing vendor, preserve manual fields
    for _, existing_row in existing_df.iterrows():
        match_mask = result["vendor_id"] == existing_row["vendor_id"]
        if match_mask.sum() > 0:
            idx = result[match_mask].index[0]
            for field in MANUAL_FIELDS:
                if field in existing_df.columns and pd.notna(existing_row.get(field)):
                    result.at[idx, field] = existing_row[field]

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Projects\nsia-bond-dashboard && python -m pytest tests/test_vendor_extractor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add utils/vendor_extractor.py tests/test_vendor_extractor.py
git commit -m "feat: add vendor extractor with fuzzy dedup and merge-with-existing"
```

### Task 7: Vendor Master Page

**Files:**
- Create: `pages/16_Vendor_Master.py`

- [ ] **Step 1: Create Vendor Master page**

```python
# pages/16_Vendor_Master.py
"""
Page 16: Vendor Master
Auto-extracted vendor list with contract compliance tracking.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.theme import FONT_COLOR, style_chart, inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Vendor Master | NSIA", layout="wide", page_icon=":ice_hockey:")
inject_css()
require_auth()

st.title("Vendor Master")
st.caption("Vendor list with spend analysis and contract compliance tracking")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
VENDOR_CSV = os.path.join(DATA_DIR, "vendor_master.csv")
BILLS_PATH = os.path.join(DATA_DIR, "bills_summary.xlsx")
GL_PATH = os.path.join(DATA_DIR, "general_ledger.xlsx")

from utils.vendor_extractor import (
    extract_vendors_from_bills,
    extract_vendors_from_gl,
    fuzzy_dedup,
    apply_merges,
    merge_with_existing,
)


# ── Load existing vendor master ──────────────────────────────────────────
def load_vendor_master() -> pd.DataFrame:
    try:
        return pd.read_csv(VENDOR_CSV)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


vendor_df = load_vendor_master()

# ── Extract / Re-extract ─────────────────────────────────────────────────
st.sidebar.header("Vendor Extraction")

if st.sidebar.button("Extract Vendors from Data", type="primary"):
    with st.spinner("Extracting vendors from GL and bills..."):
        vendors = pd.DataFrame()

        # Extract from bills (clean data)
        if os.path.exists(BILLS_PATH):
            bills = pd.read_excel(BILLS_PATH)
            bills_vendors = extract_vendors_from_bills(bills)
            if not bills_vendors.empty:
                vendors = bills_vendors

        # Extract from GL (messier data)
        if os.path.exists(GL_PATH):
            gl = pd.read_excel(GL_PATH)
            gl_vendors = extract_vendors_from_gl(gl)
            if not gl_vendors.empty:
                if vendors.empty:
                    vendors = gl_vendors
                else:
                    # Combine — bills data is cleaner, use it as primary
                    for _, gl_row in gl_vendors.iterrows():
                        if not any(vendors["vendor_name"].str.lower() == gl_row["vendor_name"].lower()):
                            vendors = pd.concat([vendors, gl_row.to_frame().T], ignore_index=True)

        if vendors.empty:
            st.warning("No vendor data found in GL or bills files.")
        else:
            # Merge with existing to preserve manual edits
            if not vendor_df.empty:
                vendors = merge_with_existing(vendors, vendor_df)

            st.session_state["extracted_vendors"] = vendors
            st.success(f"Extracted {len(vendors)} vendors. Review fuzzy matches below.")

# Fuzzy dedup review
if "extracted_vendors" in st.session_state:
    extracted = st.session_state["extracted_vendors"]
    proposals = fuzzy_dedup(extracted)

    if proposals:
        st.subheader("Review Fuzzy Matches")
        st.caption("These vendors have similar names and may be duplicates. Approve merges or skip.")

        approved = []
        for i, prop in enumerate(proposals):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.markdown(f"**{prop['name_keep']}**")
            with col2:
                st.markdown(f"~ **{prop['name_merge']}** ({prop['score']:.0%} match)")
            with col3:
                if st.checkbox("Merge", key=f"merge_{i}", value=True):
                    approved.append(prop)

        if st.button("Apply Merges & Save", type="primary"):
            result = apply_merges(extracted, approved)
            result.to_csv(VENDOR_CSV, index=False)
            st.session_state.pop("extracted_vendors", None)
            st.success(f"Saved {len(result)} vendors (merged {len(approved)} duplicates).")
            st.rerun()

        if st.button("Save Without Merging"):
            extracted.to_csv(VENDOR_CSV, index=False)
            st.session_state.pop("extracted_vendors", None)
            st.success(f"Saved {len(extracted)} vendors.")
            st.rerun()
    else:
        # No fuzzy matches — save directly
        extracted.to_csv(VENDOR_CSV, index=False)
        st.session_state.pop("extracted_vendors", None)
        st.success(f"Saved {len(extracted)} vendors (no duplicates found).")
        st.rerun()

st.markdown("---")

# ── Vendor Display ───────────────────────────────────────────────────────
vendor_df = load_vendor_master()  # Reload after potential save

if vendor_df.empty:
    st.info("No vendor data yet. Click **Extract Vendors from Data** in the sidebar to get started.")
    st.stop()

# Metrics
today = date.today()
total_spend = vendor_df["total_spend_ytd"].sum()
vendor_count = len(vendor_df)
high_risk = len(vendor_df[vendor_df["risk_flag"] == "High"]) if "risk_flag" in vendor_df.columns else 0

# Contract expiration check
expired = pd.DataFrame()
expiring_soon = pd.DataFrame()
if "contract_end" in vendor_df.columns:
    vendor_df["contract_end"] = pd.to_datetime(vendor_df["contract_end"], errors="coerce")
    has_end = vendor_df.dropna(subset=["contract_end"])
    if not has_end.empty:
        expired = has_end[has_end["contract_end"].dt.date < today]
        expiring_soon = has_end[
            (has_end["contract_end"].dt.date >= today) &
            (has_end["contract_end"].dt.date <= today + pd.Timedelta(days=90))
        ]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Vendors", vendor_count)
with col2:
    st.metric("Total Spend (YTD)", f"${total_spend:,.0f}")
with col3:
    st.metric("High Risk Vendors", high_risk)
with col4:
    st.metric("Expired Contracts", len(expired))

if not expired.empty:
    st.error(f"**{len(expired)} expired contract(s):** {', '.join(expired['vendor_name'].tolist())}")
if not expiring_soon.empty:
    st.warning(f"**{len(expiring_soon)} contract(s) expiring within 90 days:** {', '.join(expiring_soon['vendor_name'].tolist())}")

# Top 10 vendors by spend
st.subheader("Top Vendors by Spend")
top10 = vendor_df.nlargest(10, "total_spend_ytd")
fig = go.Figure(go.Bar(
    y=top10["vendor_name"],
    x=top10["total_spend_ytd"],
    orientation="h",
    marker=dict(
        color=["#eb144c" if r == "High" else "#fcb900" if r == "Medium" else "#64ffda"
               for r in top10.get("risk_flag", ["None"] * len(top10))],
        line=dict(width=1, color="rgba(255,255,255,0.2)"),
    ),
    text=[f"${v:,.0f}" for v in top10["total_spend_ytd"]],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=11),
    hovertemplate="<b>%{y}</b><br>Spend: $%{x:,.0f}<extra></extra>",
))
fig.update_layout(title="Top 10 Vendors by YTD Spend", xaxis_title="Total Spend ($)")
style_chart(fig, 450)
st.plotly_chart(fig, use_container_width=True)

# CSCG deep-dive
cscg = vendor_df[vendor_df["vendor_name"].str.contains("CSCG|Canlan", case=False, na=False)]
if not cscg.empty:
    st.subheader("CSCG Deep Dive")
    cscg_row = cscg.iloc[0]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("CSCG Total Spend", f"${cscg_row['total_spend_ytd']:,.0f}")
    with c2:
        st.metric("Payment Count", int(cscg_row["payment_count"]))
    with c3:
        pct = cscg_row["total_spend_ytd"] / total_spend * 100 if total_spend > 0 else 0
        st.metric("% of Total Spend", f"{pct:.1f}%")

# Editable vendor table
st.markdown("---")
st.subheader("Vendor Details (Editable)")
st.caption("Edit contract terms, risk flags, and compliance notes directly in the table.")

display_cols = ["vendor_name", "total_spend_ytd", "payment_count", "category", "risk_flag",
                "contract_start", "contract_end", "contract_terms", "compliance_notes"]
available_cols = [c for c in display_cols if c in vendor_df.columns]

edited = st.data_editor(
    vendor_df[available_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "total_spend_ytd": st.column_config.NumberColumn("YTD Spend", format="$%,.0f", disabled=True),
        "payment_count": st.column_config.NumberColumn("Payments", disabled=True),
        "risk_flag": st.column_config.SelectboxColumn("Risk", options=["None", "Low", "Medium", "High"]),
        "category": st.column_config.SelectboxColumn("Category", options=[
            "Utilities", "Insurance", "Management", "Maintenance", "Professional Services", "Other"
        ]),
        "contract_start": st.column_config.DateColumn("Contract Start"),
        "contract_end": st.column_config.DateColumn("Contract End"),
    },
    key="vendor_editor",
)

if st.button("Save Changes", type="primary"):
    for col in available_cols:
        vendor_df[col] = edited[col]
    vendor_df.to_csv(VENDOR_CSV, index=False)
    st.success("Vendor data saved.")
    st.rerun()
```

- [ ] **Step 2: Test manually — extract vendors, review fuzzy matches, edit table**

- [ ] **Step 3: Commit**

```bash
git add pages/16_Vendor_Master.py
git commit -m "feat: add Vendor Master page with auto-extract, fuzzy dedup, and editable table"
```

---

## Execution Checklist

- [ ] Task 1: Bank CSV parser utility + tests
- [ ] Task 2: Bank transactions section on Monthly Financials
- [ ] Task 3: Board actions Excel template
- [ ] Task 4: Board Actions page
- [ ] Task 5: Overdue alerts on Variance Alerts page
- [ ] Task 6: Vendor extractor utility + tests
- [ ] Task 7: Vendor Master page
