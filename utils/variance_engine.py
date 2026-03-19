"""NSIA Variance Engine — computes dynamic flags and discussion items from actual data."""
import logging

import pandas as pd

from utils.data_loader import (
    load_monthly_pnl,
    load_cash_forecast,
    load_contract_receivables,
    compute_board_demands,
)
from utils.fiscal_period import (
    get_current_month,
    get_latest_receivable_month,
    FISCAL_MONTHS,
    MONTH_FULL,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag severity ordering for sort
# ---------------------------------------------------------------------------
_COLOR_SORT = {"red": 0, "yellow": 1, "green": 2}


# ---------------------------------------------------------------------------
# Monthly variance flags
# ---------------------------------------------------------------------------

def compute_monthly_flags(month: str = None) -> list[dict]:
    """Compute red/yellow/green flags by comparing each line item's Actual vs Budget.

    Parameters
    ----------
    month : str, optional
        Month abbreviation (e.g. "Jan"). If None, uses the latest month
        detected from monthly_pnl.csv.

    Returns
    -------
    list[dict]
        Each dict has keys: color, title, detail.
        Sorted: red first, then yellow, then green.
    """
    try:
        if month is None:
            month = get_current_month()["abbrev"]

        month_name = MONTH_FULL.get(month, month)
        pnl = load_monthly_pnl()

        if pnl.empty:
            return []

        # Coerce Actual and Budget to numeric
        pnl["Actual"] = pd.to_numeric(pnl["Actual"], errors="coerce").fillna(0)
        pnl["Budget"] = pd.to_numeric(pnl["Budget"], errors="coerce").fillna(0)

        # --- Monthly line items for the target month ---
        month_data = pnl[pnl["Month"] == month]
        expenses = month_data[
            (month_data["Category"] == "Expense") & (month_data["Subcategory"] != "Total")
        ]
        revenues = month_data[
            (month_data["Category"] == "Revenue") & (month_data["Subcategory"] != "Total")
        ]

        # --- YTD: sum all months through the target month ---
        months_through = _months_through(month)
        ytd_data = pnl[pnl["Month"].isin(months_through)]
        ytd_expenses = (
            ytd_data[(ytd_data["Category"] == "Expense") & (ytd_data["Subcategory"] != "Total")]
            .groupby("Subcategory")[["Actual", "Budget"]]
            .sum()
        )
        ytd_revenues = (
            ytd_data[(ytd_data["Category"] == "Revenue") & (ytd_data["Subcategory"] != "Total")]
            .groupby("Subcategory")[["Actual", "Budget"]]
            .sum()
        )

        flags: list[dict] = []

        # --- Expense flags (overspending = bad) ---
        for _, row in expenses.iterrows():
            actual, budget, sub = row["Actual"], row["Budget"], row["Subcategory"]
            pct = _safe_pct(actual, budget)
            variance = actual - budget
            ytd_actual, ytd_budget = _ytd_lookup(ytd_expenses, sub)

            # RED: way over budget
            if actual > budget * 1.5 and variance > 3000:
                flags.append({
                    "color": "red",
                    "title": f"{sub} is {pct:.0f}% of budget",
                    "detail": (
                        f"${actual:,.0f} in {month_name} vs ${budget:,.0f} budgeted ({pct:.0f}%). "
                        f"Year-to-date: ${ytd_actual:,.0f} vs ${ytd_budget:,.0f} budget."
                    ),
                })
            # YELLOW: moderately over budget
            elif actual > budget * 1.2 and variance > 1000:
                flags.append({
                    "color": "yellow",
                    "title": f"{sub} is {pct:.0f}% of budget",
                    "detail": (
                        f"${actual:,.0f} in {month_name} vs ${budget:,.0f} budgeted ({pct:.0f}%). "
                        f"Year-to-date: ${ytd_actual:,.0f} vs ${ytd_budget:,.0f} budget."
                    ),
                })

        # --- Revenue flags ---
        for _, row in revenues.iterrows():
            actual, budget, sub = row["Actual"], row["Budget"], row["Subcategory"]
            pct = _safe_pct(actual, budget)
            variance = actual - budget
            ytd_actual, ytd_budget = _ytd_lookup(ytd_revenues, sub)

            # GREEN: revenue outperformance
            if actual > budget * 1.5 and variance > 2000:
                flags.append({
                    "color": "green",
                    "title": f"{sub} revenue way ahead of plan",
                    "detail": (
                        f"${actual:,.0f} in {month_name} vs ${budget:,.0f} budget ({pct:.0f}%). "
                        f"YTD ${ytd_actual:,.0f} vs ${ytd_budget:,.0f}."
                    ),
                })
            # RED: revenue underperformance
            elif budget > 0 and actual < budget * 0.5 and (budget - actual) > 3000:
                flags.append({
                    "color": "red",
                    "title": f"{sub} collecting half of budget",
                    "detail": (
                        f"${actual:,.0f} in {month_name} vs ${budget:,.0f} budget ({pct:.0f}%). "
                        f"YTD ${ytd_actual:,.0f} vs ${ytd_budget:,.0f}."
                    ),
                })

        # Sort: red first, then yellow, then green
        flags.sort(key=lambda f: _COLOR_SORT.get(f["color"], 9))
        return flags

    except Exception as e:
        logger.warning("compute_monthly_flags failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Discussion items
# ---------------------------------------------------------------------------

def compute_discussion_items() -> list[str]:
    """Auto-generate board meeting discussion items from data.

    Sources:
        1. RED flags from variance analysis
        2. Cash forecast negative-cash months
        3. Board demands with RED status
        4. Collection shortfalls (< 60% collected)

    Returns
    -------
    list[str]
        Plain-English discussion items for board meeting agendas.
    """
    items: list[str] = []

    # --- 1. RED flags -> discussion points ---
    try:
        flags = compute_monthly_flags()
        for flag in flags:
            if flag["color"] == "red":
                # Build a board-friendly discussion point from the flag
                title = flag["title"]
                # Extract YTD variance from detail text for the discussion point
                ytd_variance = _extract_ytd_variance(flag)
                if "collecting half" in title.lower():
                    items.append(
                        f"Revenue shortfall: {title} — need collection plan or budget adjustment"
                    )
                else:
                    variance_note = f" on ${ytd_variance:,.0f} YTD budget blow" if ytd_variance else ""
                    sub = title.split(" is ")[0] if " is " in title else title
                    items.append(
                        f"{sub} overage — need explanation from CSCG{variance_note}"
                    )
    except Exception as e:
        logger.warning("Discussion items: flag computation failed: %s", e)

    # --- 2. Cash forecast negative months ---
    try:
        cf = load_cash_forecast()
        if not cf.empty:
            cf["Cumulative Cash"] = pd.to_numeric(cf["Cumulative Cash"], errors="coerce")
            negative = cf[cf["Cumulative Cash"] < 0]
            if not negative.empty:
                neg_months = ", ".join(negative["Month"].tolist())
                items.append(f"Cash forecast — plan for {neg_months} cash crunch")
    except Exception as e:
        logger.warning("Discussion items: cash forecast failed: %s", e)

    # --- 3. Board demands with RED status ---
    try:
        demands = compute_board_demands()
        if not demands.empty and "Status" in demands.columns:
            red_demands = demands[demands["Status"] == "RED"]
            for _, row in red_demands.iterrows():
                items.append(f"Request: {row['Demand']}")
    except Exception as e:
        logger.warning("Discussion items: board demands failed: %s", e)

    # --- 4. Collection shortfalls ---
    try:
        recv = load_contract_receivables()
        if not recv.empty:
            latest_prefix = get_latest_receivable_month()
            if latest_prefix:
                contracted_col = f"{latest_prefix} Contracted"
                paid_col = f"{latest_prefix} Paid"
                if contracted_col in recv.columns and paid_col in recv.columns:
                    recv[contracted_col] = pd.to_numeric(recv[contracted_col], errors="coerce").fillna(0)
                    recv[paid_col] = pd.to_numeric(recv[paid_col], errors="coerce").fillna(0)
                    # Exclude Total row
                    clubs = recv[recv["Customer"] != "Total"].copy()
                    for _, row in clubs.iterrows():
                        contracted = row[contracted_col]
                        paid = row[paid_col]
                        if contracted > 0:
                            pct = paid / contracted
                            if pct < 0.60:
                                items.append(
                                    f"Collection follow-up: {row['Customer']} at {pct:.0%} collected"
                                )
    except Exception as e:
        logger.warning("Discussion items: receivables failed: %s", e)

    return items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _months_through(month: str) -> list[str]:
    """Return fiscal month abbreviations from Jul through the given month (inclusive)."""
    try:
        idx = FISCAL_MONTHS.index(month)
        return FISCAL_MONTHS[:idx + 1]
    except ValueError:
        return [month]


def _safe_pct(actual: float, budget: float) -> float:
    """Compute actual/budget as a percentage, handling zero budget."""
    if budget == 0:
        return 0.0 if actual == 0 else 999.0
    return (actual / budget) * 100


def _ytd_lookup(ytd_df: pd.DataFrame, subcategory: str) -> tuple[float, float]:
    """Look up YTD actual and budget for a subcategory from a grouped DataFrame."""
    if ytd_df.empty or subcategory not in ytd_df.index:
        return 0.0, 0.0
    row = ytd_df.loc[subcategory]
    return float(row["Actual"]), float(row["Budget"])


def _extract_ytd_variance(flag: dict) -> float | None:
    """Parse the YTD variance from a flag's detail text.

    Looks for 'Year-to-date: $X vs $Y budget' and returns X - Y (for expenses)
    or Y - X (for revenue shortfalls).
    """
    import re
    detail = flag.get("detail", "")

    # Match patterns like "Year-to-date: $123,456 vs $100,000 budget"
    # or "YTD $123,456 vs $100,000"
    patterns = [
        r"Year-to-date:\s*\$([\d,]+)\s*vs\s*\$([\d,]+)",
        r"YTD\s*\$([\d,]+)\s*vs\s*\$([\d,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, detail)
        if match:
            ytd_actual = float(match.group(1).replace(",", ""))
            ytd_budget = float(match.group(2).replace(",", ""))
            variance = abs(ytd_actual - ytd_budget)
            return variance if variance > 0 else None
    return None
