"""
Data context layer for NSIA AI assistant.

Bridges board member questions to the 47 data loaders by:
1. Building a structured text summary for Claude's system prompt
2. Providing tool definitions for on-demand data queries
3. Executing queries and returning formatted text results
"""
import logging

import pandas as pd
import streamlit as st

from utils.data_loader import (
    load_monthly_pnl,
    load_cash_forecast,
    load_contract_receivables,
    load_revenue_reconciliation,
    load_expense_reconciliation,
    compute_kpis,
    compute_variance_alerts,
    compute_cscg_scorecard,
    compute_board_demands,
    compute_board_attention,
    load_expense_flow,
    load_expense_flow_summary,
    load_cscg_relationship,
    load_hidden_cash_flows,
    load_bills_summary,
    load_bills_by_category,
    load_bills_by_vendor,
    load_general_ledger,
    load_gl_account_summary,
)
from utils.fiscal_period import (
    get_current_month,
    get_fiscal_date_range,
    get_latest_receivable_month,
    FISCAL_MONTHS,
)
from utils.variance_engine import compute_monthly_flags, compute_discussion_items

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def build_data_summary() -> str:
    """Build a ~2000 token structured text summary of current NSIA financial state.

    Cached for 5 minutes to avoid redundant string assembly on every question.
    Each section is independently wrapped in try/except so partial data
    failures do not kill the entire summary.
    """
    sections: list[str] = []

    # -- Current Period --
    try:
        m = get_current_month()
        sections.append(
            f"## Current Period\n"
            f"{m['fiscal_year']}, Data through {m['name']} {m['calendar_year']} "
            f"(Month {m['fiscal_month']} of {m['total_months']})"
        )
    except Exception as e:
        logger.warning("data_context: Current Period failed: %s", e)
        m = None

    # -- Monthly P&L --
    try:
        pnl = load_monthly_pnl()
        if m is not None and not pnl.empty:
            abbrev = m["abbrev"]
            month_name = m["name"]
            pnl["Actual"] = pd.to_numeric(pnl["Actual"], errors="coerce").fillna(0)
            pnl["Budget"] = pd.to_numeric(pnl["Budget"], errors="coerce").fillna(0)

            month_data = pnl[pnl["Month"] == abbrev]

            rev_row = month_data[(month_data["Category"] == "Revenue") & (month_data["Subcategory"] == "Total")]
            exp_row = month_data[(month_data["Category"] == "Expense") & (month_data["Subcategory"] == "Total")]
            ni_row = month_data[(month_data["Category"] == "Net Income") | (month_data["Subcategory"] == "Net Income")]

            rev_actual = rev_row["Actual"].sum()
            rev_budget = rev_row["Budget"].sum()
            exp_actual = exp_row["Actual"].sum()
            exp_budget = exp_row["Budget"].sum()

            # Net income: use explicit row if available, else compute
            if not ni_row.empty:
                ni_actual = ni_row["Actual"].sum()
                ni_budget = ni_row["Budget"].sum()
            else:
                ni_actual = rev_actual - exp_actual
                ni_budget = rev_budget - exp_budget

            rev_diff = rev_actual - rev_budget
            rev_word = "beat" if rev_diff >= 0 else "missed"

            lines = [
                f"## Monthly P&L ({month_name})",
                f"Revenue: ${rev_actual:,.0f} (Budget: ${rev_budget:,.0f}) -- {rev_word} by ${abs(rev_diff):,.0f}",
                f"Expenses: ${exp_actual:,.0f} (Budget: ${exp_budget:,.0f})",
                f"Net Income: ${ni_actual:,.0f} (Budget: ${ni_budget:,.0f})",
            ]
            sections.append("\n".join(lines))

            # -- Year-to-Date --
            months_through = FISCAL_MONTHS[:FISCAL_MONTHS.index(abbrev) + 1]
            ytd = pnl[pnl["Month"].isin(months_through)]

            ytd_rev = ytd[(ytd["Category"] == "Revenue") & (ytd["Subcategory"] == "Total")]
            ytd_exp = ytd[(ytd["Category"] == "Expense") & (ytd["Subcategory"] == "Total")]

            ytd_rev_actual = ytd_rev["Actual"].sum()
            ytd_rev_budget = ytd_rev["Budget"].sum()
            ytd_ni_actual = ytd_rev["Actual"].sum() - ytd_exp["Actual"].sum()
            ytd_ni_budget = ytd_rev["Budget"].sum() - ytd_exp["Budget"].sum()
            ni_pct = (ytd_ni_actual / ytd_ni_budget * 100) if ytd_ni_budget != 0 else 0

            ytd_lines = [
                "## Year-to-Date",
                f"Revenue: ${ytd_rev_actual:,.0f} vs ${ytd_rev_budget:,.0f} budget",
                f"Net Income: ${ytd_ni_actual:,.0f} vs ${ytd_ni_budget:,.0f} ({ni_pct:.0f}% of plan)",
            ]
            sections.append("\n".join(ytd_lines))
    except Exception as e:
        logger.warning("data_context: Monthly P&L / YTD failed: %s", e)

    # -- Cash Position --
    try:
        cf = load_cash_forecast()
        if not cf.empty:
            cf["Cumulative Cash"] = pd.to_numeric(cf["Cumulative Cash"], errors="coerce")
            cf["Net Cash Flow"] = pd.to_numeric(cf["Net Cash Flow"], errors="coerce")

            # Current cash = latest month with actual data
            fiscal_month_count = m["fiscal_month"] if m else 1
            actual_rows = cf.head(fiscal_month_count)
            current_cash = actual_rows["Cumulative Cash"].iloc[-1] if not actual_rows.empty else 0
            current_month_label = actual_rows["Month"].iloc[-1] if not actual_rows.empty else "unknown"

            # Negative months
            negative = cf[cf["Cumulative Cash"] < 0]
            if not negative.empty:
                neg_str = ", ".join(negative["Month"].tolist())
            else:
                neg_str = "No negative months forecast"

            # Year-end projection
            year_end = cf["Cumulative Cash"].iloc[-1] if len(cf) > 0 else 0

            cash_lines = [
                "## Cash Position",
                f"Current: ${current_cash:,.0f} as of {current_month_label}",
                f"Forecast: {neg_str}",
                f"Year-end projection: ${year_end:,.0f}",
            ]
            sections.append("\n".join(cash_lines))
    except Exception as e:
        logger.warning("data_context: Cash Position failed: %s", e)

    # -- Contract Receivables --
    try:
        recv = load_contract_receivables()
        latest_prefix = get_latest_receivable_month()
        if not recv.empty and latest_prefix:
            contracted_col = f"{latest_prefix} Contracted"
            paid_col = f"{latest_prefix} Paid"
            if contracted_col in recv.columns and paid_col in recv.columns:
                recv[contracted_col] = pd.to_numeric(recv[contracted_col], errors="coerce").fillna(0)
                recv[paid_col] = pd.to_numeric(recv[paid_col], errors="coerce").fillna(0)

                recv_lines = [f"## Contract Receivables ({latest_prefix})"]
                total_paid = 0
                total_contracted = 0
                for _, row in recv.iterrows():
                    name = row["Customer"]
                    paid = row[paid_col]
                    contracted = row[contracted_col]
                    pct = (paid / contracted * 100) if contracted > 0 else 0
                    if name == "Total":
                        total_paid = paid
                        total_contracted = contracted
                    else:
                        recv_lines.append(f"{name} -- ${paid:,.0f} of ${contracted:,.0f} ({pct:.0f}%)")

                total_pct = (total_paid / total_contracted * 100) if total_contracted > 0 else 0
                recv_lines.append(f"Total collected: ${total_paid:,.0f} of ${total_contracted:,.0f} ({total_pct:.0f}%)")
                sections.append("\n".join(recv_lines))
    except Exception as e:
        logger.warning("data_context: Contract Receivables failed: %s", e)

    # -- Key Flags --
    try:
        flags = compute_monthly_flags()
        if flags:
            flag_lines = ["## Key Flags"]
            for f in flags:
                color = f["color"].upper()
                flag_lines.append(f"{color}: {f['title']}")
            sections.append("\n".join(flag_lines))
    except Exception as e:
        logger.warning("data_context: Key Flags failed: %s", e)

    # -- KPIs --
    try:
        kpis = compute_kpis()
        kpi_lines = [
            "## KPIs",
            f"DSCR: {kpis['dscr']:.2f}x",
            f"Annual Revenue (projected): ${kpis['total_annual_revenue']:,.0f}",
            f"Hidden Cash Outflows: ${kpis['hidden_cash_outflows']:,.0f}",
            f"Board-Approved Expenses: {kpis['pct_board_approved'] * 100:.1f}%",
        ]
        sections.append("\n".join(kpi_lines))
    except Exception as e:
        logger.warning("data_context: KPIs failed: %s", e)

    return "\n\n".join(sections)


def get_tool_definitions() -> list[dict]:
    """Return Claude API tool definitions for on-demand data queries."""
    return [
        {
            "name": "query_financial_data",
            "description": (
                "Query NSIA financial data. Use this to get specific numbers, "
                "breakdowns, or details beyond the summary provided in context."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "monthly_pnl",
                            "cash_forecast",
                            "receivables",
                            "variance_alerts",
                            "vendor_bills",
                            "gl_transactions",
                            "cscg_scorecard",
                            "board_demands",
                            "expense_flow",
                            "kpis",
                        ],
                        "description": "Type of data to query",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Optional filters: month (str), category (str), "
                            "vendor (str), severity (str), limit (int)"
                        ),
                    },
                },
                "required": ["query_type"],
            },
        }
    ]


def query_data(query_type: str, filters: dict = None) -> str:
    """Execute a data query and return formatted text results for Claude."""
    filters = filters or {}

    handlers = {
        "monthly_pnl": _query_monthly_pnl,
        "cash_forecast": _query_cash_forecast,
        "receivables": _query_receivables,
        "variance_alerts": _query_variance_alerts,
        "vendor_bills": _query_vendor_bills,
        "gl_transactions": _query_gl_transactions,
        "cscg_scorecard": _query_cscg_scorecard,
        "board_demands": _query_board_demands,
        "expense_flow": _query_expense_flow,
        "kpis": _query_kpis,
    }

    handler = handlers.get(query_type)
    if not handler:
        return f"Unknown query type: {query_type}. Available: {', '.join(handlers.keys())}"

    try:
        return handler(filters)
    except Exception as e:
        logger.error("query_data(%s) failed: %s", query_type, e)
        return f"Error querying {query_type}: {str(e)}"


# ---------------------------------------------------------------------------
# Internal query handlers
# ---------------------------------------------------------------------------

def _query_monthly_pnl(filters: dict) -> str:
    """Monthly P&L line items with Actual, Budget, Variance."""
    try:
        pnl = load_monthly_pnl()
        if pnl.empty:
            return "No monthly P&L data available."

        pnl["Actual"] = pd.to_numeric(pnl["Actual"], errors="coerce").fillna(0)
        pnl["Budget"] = pd.to_numeric(pnl["Budget"], errors="coerce").fillna(0)

        # Filter by month
        month = filters.get("month")
        if month:
            pnl = pnl[pnl["Month"] == month]
            if pnl.empty:
                return f"No P&L data for month '{month}'."
        else:
            # Default to current month
            month = get_current_month()["abbrev"]
            pnl = pnl[pnl["Month"] == month]

        # Filter by category
        category = filters.get("category")
        if category:
            pnl = pnl[pnl["Category"].str.contains(category, case=False, na=False)]

        pnl["Variance"] = pnl["Actual"] - pnl["Budget"]
        display = pnl[["Category", "Subcategory", "Actual", "Budget", "Variance"]].copy()
        display["Actual"] = display["Actual"].map(lambda x: f"${x:,.0f}")
        display["Budget"] = display["Budget"].map(lambda x: f"${x:,.0f}")
        display["Variance"] = display["Variance"].map(lambda x: f"${x:,.0f}")

        header = f"Monthly P&L -- {month}"
        return f"{header}\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading monthly P&L: {e}"


def _query_cash_forecast(filters: dict) -> str:
    """12-month cash forecast with actual/forecast distinction."""
    try:
        cf = load_cash_forecast()
        if cf.empty:
            return "No cash forecast data available."

        m = get_current_month()
        actual_count = m["fiscal_month"]

        for col in ["Revenue", "Expenses", "Net Cash Flow", "Cumulative Cash"]:
            if col in cf.columns:
                cf[col] = pd.to_numeric(cf[col], errors="coerce").fillna(0)

        cf["Type"] = ["Actual" if i < actual_count else "Forecast" for i in range(len(cf))]

        display = cf[["Month", "Type", "Revenue", "Expenses", "Net Cash Flow", "Cumulative Cash"]].copy()
        for col in ["Revenue", "Expenses", "Net Cash Flow", "Cumulative Cash"]:
            if col in display.columns:
                display[col] = display[col].map(lambda x: f"${x:,.0f}")

        return f"Cash Forecast (FY)\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading cash forecast: {e}"


def _query_receivables(filters: dict) -> str:
    """Contract receivables by customer for the latest (or filtered) month."""
    try:
        recv = load_contract_receivables()
        if recv.empty:
            return "No receivables data available."

        latest_prefix = get_latest_receivable_month()
        if not latest_prefix:
            return "No receivable month detected."

        contracted_col = f"{latest_prefix} Contracted"
        paid_col = f"{latest_prefix} Paid"
        owed_col = f"{latest_prefix} Owed"

        needed = [contracted_col, paid_col]
        missing = [c for c in needed if c not in recv.columns]
        if missing:
            return f"Missing columns: {missing}. Available: {list(recv.columns)}"

        # Optional customer filter
        customer = filters.get("customer")
        if customer:
            recv = recv[recv["Customer"].str.contains(customer, case=False, na=False)]

        cols = ["Customer", contracted_col, paid_col]
        if owed_col in recv.columns:
            cols.append(owed_col)
        display = recv[cols].copy()

        for col in cols[1:]:
            display[col] = pd.to_numeric(display[col], errors="coerce").fillna(0)
            display[col] = display[col].map(lambda x: f"${x:,.0f}")

        return f"Contract Receivables ({latest_prefix})\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading receivables: {e}"


def _query_variance_alerts(filters: dict) -> str:
    """Variance alerts optionally filtered by severity."""
    try:
        alerts = compute_variance_alerts()
        if alerts.empty:
            return "No variance alerts."

        severity = filters.get("severity")
        if severity:
            alerts = alerts[alerts["Severity"].str.upper() == severity.upper()]
            if alerts.empty:
                return f"No {severity.upper()} alerts."

        # Keep output concise
        display_cols = [c for c in ["Line Item", "Source", "Severity", "Variance %", "Variance $"] if c in alerts.columns]
        if not display_cols:
            display_cols = alerts.columns.tolist()

        display = alerts[display_cols].head(30)
        return f"Variance Alerts\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading variance alerts: {e}"


def _query_vendor_bills(filters: dict) -> str:
    """Bills summary, optionally filtered by vendor or category."""
    try:
        vendor = filters.get("vendor")
        category = filters.get("category")

        if category:
            bills = load_bills_by_category()
            if not bills.empty:
                bills = bills[bills["Category"].str.contains(category, case=False, na=False)]
            return f"Bills by Category\n{bills.to_string(index=False)}" if not bills.empty else f"No bills for category '{category}'."

        bills = load_bills_summary()
        if bills.empty:
            return "No bills data available."

        if vendor:
            bills = bills[bills["Vendor"].str.contains(vendor, case=False, na=False)]
            if bills.empty:
                return f"No bills for vendor '{vendor}'."

        limit = filters.get("limit", 30)
        display = bills.head(limit)

        # Format Amount if present
        if "Amount" in display.columns:
            display = display.copy()
            display["Amount"] = pd.to_numeric(display["Amount"], errors="coerce").fillna(0)
            display["Amount"] = display["Amount"].map(lambda x: f"${x:,.0f}")

        return f"Bills Summary ({len(bills)} total, showing {len(display)})\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading vendor bills: {e}"


def _query_gl_transactions(filters: dict) -> str:
    """General ledger transactions, optionally filtered by account or date."""
    try:
        gl = load_general_ledger()
        if gl.empty:
            return "No general ledger data available."

        # Filter by account name or number
        account = filters.get("account")
        if account:
            gl = gl[
                gl["GL Account Name"].str.contains(account, case=False, na=False)
                | gl["GL #"].astype(str).str.contains(account, na=False)
            ]
            if gl.empty:
                return f"No GL transactions matching '{account}'."

        # Filter by month
        month = filters.get("month")
        if month and "Date" in gl.columns:
            gl = gl[gl["Date"].dt.strftime("%b") == month]

        limit = filters.get("limit", 50)
        display = gl.head(limit)

        # Format currency columns
        display = display.copy()
        for col in ["Debit", "Credit"]:
            if col in display.columns:
                display[col] = display[col].map(lambda x: f"${x:,.0f}" if pd.notna(x) and x != 0 else "")

        display_cols = [c for c in ["Date", "GL #", "GL Account Name", "Description", "Debit", "Credit", "Payee"]
                        if c in display.columns]
        result = display[display_cols]
        return f"General Ledger ({len(gl)} matching, showing {len(display)})\n{result.to_string(index=False)}"
    except Exception as e:
        return f"Error loading GL transactions: {e}"


def _query_cscg_scorecard(filters: dict) -> str:
    """Full CSCG compliance scorecard."""
    try:
        scorecard = compute_cscg_scorecard()
        if scorecard.empty:
            return "No CSCG scorecard data available."

        display_cols = [c for c in ["Contract Term", "Contract Amount", "6mo Expected",
                                     "6mo Actual", "Status"]
                        if c in scorecard.columns]
        display = scorecard[display_cols].copy()

        # Format currency columns
        for col in ["Contract Amount", "6mo Expected", "6mo Actual"]:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "At cost"
                )

        return f"CSCG Compliance Scorecard\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading CSCG scorecard: {e}"


def _query_board_demands(filters: dict) -> str:
    """Board demands with status."""
    try:
        demands = compute_board_demands()
        if demands.empty:
            return "No board demands data available."

        # Optional status filter
        status = filters.get("status")
        if status:
            demands = demands[demands["Status"].str.upper() == status.upper()]
            if demands.empty:
                return f"No board demands with status '{status}'."

        display_cols = [c for c in ["Category", "Demand", "Frequency", "Status", "Evidence"]
                        if c in demands.columns]
        display = demands[display_cols]
        return f"Board Demands ({len(display)} items)\n{display.to_string(index=False)}"
    except Exception as e:
        return f"Error loading board demands: {e}"


def _query_expense_flow(filters: dict) -> str:
    """Expense flow analysis showing approval methods."""
    try:
        flow = load_expense_flow()
        if flow.empty:
            return "No expense flow data available."

        # Optional approval method filter
        method = filters.get("approval_method")
        if method:
            flow = flow[flow["Approval Method"].str.contains(method, case=False, na=False)]

        display = flow.copy()
        for col in ["YTD per Financials", "YTD from Invoices", "Variance"]:
            if col in display.columns:
                display[col] = display[col].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else ""
                )

        result = display.to_string(index=False)

        # Append summary if available
        try:
            summary = load_expense_flow_summary()
            if not summary.empty:
                summary_display = summary.copy()
                if "YTD Amount" in summary_display.columns:
                    summary_display["YTD Amount"] = summary_display["YTD Amount"].apply(
                        lambda x: f"${x:,.0f}" if pd.notna(x) else ""
                    )
                if "% of Total" in summary_display.columns:
                    summary_display["% of Total"] = summary_display["% of Total"].apply(
                        lambda x: f"{x * 100:.1f}%" if pd.notna(x) else ""
                    )
                result += f"\n\nApproval Method Summary\n{summary_display.to_string(index=False)}"
        except Exception:
            pass

        return f"Expense Flow Analysis\n{result}"
    except Exception as e:
        return f"Error loading expense flow: {e}"


def _query_kpis(filters: dict) -> str:
    """Computed KPIs."""
    try:
        kpis = compute_kpis()
        lines = [
            "Key Performance Indicators",
            f"DSCR: {kpis['dscr']:.2f}x",
            f"Net Operating Income: ${kpis['net_operating_income']:,.0f}",
            f"Debt Service (annual): ${kpis['debt_service']:,.0f}",
            f"Annual Revenue (projected): ${kpis['total_annual_revenue']:,.0f}",
            f"Annual Expenses (projected): ${kpis['total_annual_expenses']:,.0f}",
            f"Net Cash Flow (after hidden): ${kpis['net_cash_flow']:,.0f}",
            f"Hidden Cash Outflows: ${kpis['hidden_cash_outflows']:,.0f}",
            f"Board-Approved Expenses: {kpis['pct_board_approved'] * 100:.1f}%",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error computing KPIs: {e}"
