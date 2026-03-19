"""NSIA Fiscal Period Configuration — single source of truth for reporting dates."""
import os
import re
import pandas as pd
import streamlit as st
from calendar import monthrange
from datetime import date

# Fiscal year month order (Jul=1 through Jun=12)
FISCAL_MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
MONTH_FULL = {
    "Jul": "July", "Aug": "August", "Sep": "September", "Oct": "October",
    "Nov": "November", "Dec": "December", "Jan": "January", "Feb": "February",
    "Mar": "March", "Apr": "April", "May": "May", "Jun": "June",
}

# Calendar month numbers for each abbreviation
_CALENDAR_MONTH_NUM = {
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10,
    "Nov": 11, "Dec": 12, "Jan": 1, "Feb": 2,
    "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


# ---------------------------------------------------------------------------
# Core: detect current month from data
# ---------------------------------------------------------------------------

@st.cache_data
def get_current_month() -> dict:
    """Detect the latest reporting month from monthly_pnl.csv and return
    a dict with all fiscal-period metadata other modules need."""
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, "monthly_pnl.csv"))
    except FileNotFoundError:
        # Sensible default: January of current fiscal year
        return _build_month_dict("Jan")

    # Find the last month with actual Revenue > 0
    revenue = df[df["Category"] == "Revenue"].copy()
    revenue["Actual"] = pd.to_numeric(revenue["Actual"], errors="coerce").fillna(0)
    months_with_data = revenue[revenue["Actual"] > 0]["Month"].unique()

    # Walk FISCAL_MONTHS in order; keep the latest that appears in data
    latest = "Jul"  # fallback
    for m in FISCAL_MONTHS:
        if m in months_with_data:
            latest = m

    return _build_month_dict(latest)


def _build_month_dict(abbrev: str) -> dict:
    """Build the canonical period dict for a given month abbreviation."""
    fiscal_month = FISCAL_MONTHS.index(abbrev) + 1  # 1-based
    cal_month = _CALENDAR_MONTH_NUM[abbrev]

    # Determine fiscal year boundaries.
    # Convention: FY label uses the END year (Jun).
    # Jul-Dec belong to fy_start_year; Jan-Jun belong to fy_start_year + 1.
    today = date.today()
    if cal_month >= 7:
        # Jul-Dec: calendar year == fy_start_year
        fy_start = today.year if today.month >= 7 else today.year - 1
    else:
        # Jan-Jun: calendar year == fy_end_year
        fy_start = today.year - 1 if today.month <= 6 else today.year

    fy_end = fy_start + 1
    calendar_year = fy_start if cal_month >= 7 else fy_end

    _, last_day = monthrange(calendar_year, cal_month)
    as_of = date(calendar_year, cal_month, last_day)

    return {
        "name": MONTH_FULL[abbrev],
        "abbrev": abbrev,
        "fiscal_month": fiscal_month,
        "total_months": 12,
        "calendar_year": calendar_year,
        "fiscal_year": f"FY{fy_end}",
        "fy_start_year": fy_start,
        "fy_end_year": fy_end,
        "fy_start": f"July {fy_start}",
        "fy_end": f"June {fy_end}",
        "as_of_date": as_of.strftime("%B %d, %Y").replace(" 0", " "),
    }


# ---------------------------------------------------------------------------
# Derived labels — all call get_current_month() (cached)
# ---------------------------------------------------------------------------

def get_month_label() -> str:
    """e.g. 'January 2026 — Month 7 of 12'"""
    m = get_current_month()
    return f"{m['name']} {m['calendar_year']} \u2014 Month {m['fiscal_month']} of {m['total_months']}"


def get_sidebar_caption() -> str:
    """e.g. 'FY2026 | Data through January 2026 (Month 7 of 12)'"""
    m = get_current_month()
    return (
        f"{m['fiscal_year']} | Data through {m['name']} {m['calendar_year']} "
        f"(Month {m['fiscal_month']} of {m['total_months']})"
    )


def get_fiscal_date_range() -> str:
    """e.g. 'Jul 2025 – Jan 2026'"""
    m = get_current_month()
    return f"Jul {m['fy_start_year']} \u2013 {m['abbrev']} {m['calendar_year']}"


def get_ytd_label() -> str:
    """e.g. 'July–January 2025-26 (7 months)'"""
    m = get_current_month()
    start_short = str(m["fy_start_year"])[-2:]
    end_short = str(m["fy_end_year"])[-2:]
    # If current month is in the same calendar year as fy_start (Jul-Dec),
    # show just one year; otherwise show range.
    if m["calendar_year"] == m["fy_start_year"]:
        year_str = str(m["fy_start_year"])
    else:
        year_str = f"{m['fy_start_year']}-{end_short}"
    return f"July\u2013{m['name']} {year_str} ({m['fiscal_month']} months)"


def get_period_label(months: int = None) -> str:
    """e.g. 'Jul-Jan 2025-26' or for 6 months 'Jul-Dec 2025'.
    If *months* is None, uses current fiscal_month."""
    m = get_current_month()
    if months is None:
        months = m["fiscal_month"]

    end_abbrev = FISCAL_MONTHS[months - 1]
    end_cal_month = _CALENDAR_MONTH_NUM[end_abbrev]
    end_cal_year = m["fy_start_year"] if end_cal_month >= 7 else m["fy_end_year"]

    if end_cal_year == m["fy_start_year"]:
        year_str = str(m["fy_start_year"])
    else:
        end_short = str(m["fy_end_year"])[-2:]
        year_str = f"{m['fy_start_year']}-{end_short}"

    return f"Jul-{end_abbrev} {year_str}"


# ---------------------------------------------------------------------------
# Ice season dates
# ---------------------------------------------------------------------------

def get_season_dates() -> dict:
    """Return ice season (Sep–Mar) boundaries for utilization pages."""
    m = get_current_month()
    start_year = m["fy_start_year"]
    end_year = m["fy_end_year"]

    # First Saturday of September in the start year
    sep1 = pd.Timestamp(year=start_year, month=9, day=1)
    # dayofweek: Mon=0 … Sat=5
    days_until_sat = (5 - sep1.dayofweek) % 7
    first_saturday = sep1 + pd.Timedelta(days=days_until_sat)

    return {
        "start": f"Sep {start_year}",
        "end": f"Mar {end_year}",
        "first_saturday": first_saturday,
        "label": f"Sep {start_year} to Mar {end_year}",
    }


# ---------------------------------------------------------------------------
# Contract receivables helpers
# ---------------------------------------------------------------------------

def get_receivable_months() -> list[str]:
    """Auto-detect month prefixes from contract_receivables.csv columns
    matching the pattern '{Month} Contracted'. Returns e.g. ['Sept', 'Nov', 'Jan']."""
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, "contract_receivables.csv"), nrows=0)
    except FileNotFoundError:
        return []

    pattern = re.compile(r"^(\w+)\s+Contracted$")
    months = []
    for col in df.columns:
        match = pattern.match(col)
        if match:
            months.append(match.group(1))
    return months


def get_latest_receivable_month() -> str:
    """Return the last available receivable month prefix, e.g. 'Jan'."""
    months = get_receivable_months()
    return months[-1] if months else ""


# ---------------------------------------------------------------------------
# Cash forecast helpers
# ---------------------------------------------------------------------------

def get_cash_forecast_months() -> dict:
    """Parse cash_forecast.csv and split months into actuals vs forecast
    based on which months have revenue data in monthly_pnl.csv."""
    m = get_current_month()
    actual_count = m["fiscal_month"]

    try:
        cf = pd.read_csv(os.path.join(DATA_DIR, "cash_forecast.csv"))
        all_months = cf["Month"].tolist()
    except (FileNotFoundError, KeyError):
        all_months = []

    forecast_count = max(0, len(all_months) - actual_count)

    return {
        "actual_count": actual_count,
        "forecast_count": forecast_count,
        "months": all_months,
    }
