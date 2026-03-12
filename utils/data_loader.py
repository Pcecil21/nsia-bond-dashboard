"""
Data loading and cleaning utilities for the NSIA Bond Dashboard.
All functions use @st.cache_data for performance.
"""
import os
import re
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


def _clean_dollar(val):
    """Parse dollar values that may contain annotations like '$3,667 ($500 for Dasher Board)'."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s.upper() in ("TBD", "", "$200/MONTH", "$200/MONTH"):
        return None
    # Grab the first dollar-like number
    m = re.match(r"^\$?([\d,]+\.?\d*)", s.replace("$", "", 1) if s.startswith("$") else s)
    if m:
        return float(m.group(1).replace(",", ""))
    # Try plain numeric
    try:
        return float(s.replace(",", "").replace("$", ""))
    except ValueError:
        return None


# ── Budget Reconciliation ────────────────────────────────────────────────

@st.cache_data
def load_revenue_reconciliation() -> pd.DataFrame:
    """Revenue Reconciliation sheet — row 4 is the header, data starts row 5."""
    df = pd.read_excel(_path("budget_reconciliation.xlsx"),
                       sheet_name="Revenue Reconciliation", header=None)
    # Header is in row 4 (0-indexed)
    headers = [
        "Line Item", "Proposal Jan Budget", "CSCG Jan Budget",
        "Jan Variance $", "Jan Variance %",
        "Proposal YTD Budget", "CSCG YTD Budget",
        "YTD Variance $", "YTD Variance %", "Assessment"
    ]
    data = df.iloc[5:].copy()
    data.columns = headers[:len(data.columns)]
    # Drop section-header / blank rows
    data = data.dropna(subset=["Line Item"])
    data = data[~data["Line Item"].str.contains("TOTAL|NaN|CONTRACT ICE|PUBLIC PROGRAM|OTHER BUILDING|LEASE INCOME|TOTAL INCOME",
                                                 case=False, na=False) |
                data["Line Item"].str.startswith("Total")]
    data = data.reset_index(drop=True)
    # Convert numeric cols
    for col in headers[1:9]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_expense_reconciliation() -> pd.DataFrame:
    """Expense Reconciliation sheet — multiple header rows at 4, 13, 34."""
    df = pd.read_excel(_path("budget_reconciliation.xlsx"),
                       sheet_name="Expense Reconciliation", header=None)
    headers = [
        "Line Item", "Proposal Jan Budget", "CSCG Jan Budget",
        "Jan Variance $", "Jan Variance %",
        "Proposal YTD Budget", "CSCG YTD Budget",
        "YTD Variance $", "YTD Variance %", "Assessment"
    ]
    data = df.iloc[5:].copy()
    data.columns = headers[:len(data.columns)]
    # Keep only actual line items (exclude repeated sub-headers and blanks)
    data = data.dropna(subset=["Line Item"])
    skip_patterns = r"^(PAYROLL EXPENSES|OPERATIONS EXPENSES|OFFICE, INSURANCE|PROGRAM SERVICE|Line Item|NaN)"
    data = data[~data["Line Item"].str.match(skip_patterns, case=False, na=False)]
    data = data.reset_index(drop=True)
    for col in headers[1:9]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_unauthorized_modifications() -> pd.DataFrame:
    """Unauthorized Modifications sheet."""
    df = pd.read_excel(_path("budget_reconciliation.xlsx"),
                       sheet_name="Unauthorized Modifications", header=None)
    headers = ["Line Item", "Proposal Annual", "CSCG Annual (Implied)",
               "Annual Variance $", "Direction", "Severity", "Board Governance Impact"]
    data = df.iloc[3:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Line Item"])
    # Remove section headers
    data = data[~data["Line Item"].str.contains("REVENUE MOD|EXPENSE MOD|Line Item",
                                                 case=False, na=False)]
    data = data.reset_index(drop=True)
    for col in ["Proposal Annual", "CSCG Annual (Implied)", "Annual Variance $"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_hidden_cash_flows() -> pd.DataFrame:
    """Hidden Cash Flows sheet."""
    df = pd.read_excel(_path("budget_reconciliation.xlsx"),
                       sheet_name="Hidden Cash Flows", header=None)
    headers = ["Item", "Monthly Amount", "Annual Impact", "Governance Concern"]
    data = df.iloc[4:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Item"])
    # Remove total row to avoid double-counting
    data = data[~data["Item"].str.contains("TOTAL", case=False, na=False)]
    data = data.reset_index(drop=True)
    for col in ["Monthly Amount", "Annual Impact"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


# ── Expense Flow ─────────────────────────────────────────────────────────

@st.cache_data
def load_expense_flow() -> pd.DataFrame:
    """Expense Flow Analysis sheet."""
    df = pd.read_excel(_path("expense_flow.xlsx"),
                       sheet_name="Expense Flow Analysis", header=None)
    headers = ["Expense Category", "YTD per Financials", "YTD from Invoices",
               "Variance", "Approval Method", "Notes"]
    data = df.iloc[4:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Expense Category"])
    # Remove section headers and summary rows
    skip = r"^(Expense Category|BOARD-APPROVED|CSCG-MANAGED|FIXED OBLIGATIONS|SUMMARY|TOTAL|KEY|1\.|2\.|3\.|4\.|5\.|DISCLOSURE|The current|CSCG has|This supports|The Form)"
    data = data[~data["Expense Category"].str.match(skip, case=False, na=False)]
    data = data.reset_index(drop=True)
    for col in ["YTD per Financials", "YTD from Invoices", "Variance"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


@st.cache_data
def load_expense_flow_summary() -> pd.DataFrame:
    """Expense approval summary breakdown from Expense Flow Analysis."""
    df = pd.read_excel(_path("expense_flow.xlsx"),
                       sheet_name="Expense Flow Analysis", header=None)
    # Rows 35-39 contain the summary
    summary = df.iloc[35:40].copy()
    summary.columns = ["Approval Method", "YTD Amount", "% of Total", "Board Oversight",
                        "_col4", "_col5"]
    summary = summary[["Approval Method", "YTD Amount", "% of Total"]].dropna(subset=["Approval Method"])
    summary = summary[summary["Approval Method"] != "Approval Method"]
    summary["YTD Amount"] = pd.to_numeric(summary["YTD Amount"], errors="coerce")
    summary["% of Total"] = pd.to_numeric(summary["% of Total"], errors="coerce")
    summary = summary.reset_index(drop=True)
    return summary


@st.cache_data
def load_cscg_relationship() -> pd.DataFrame:
    """CSCG Relationship sheet."""
    df = pd.read_excel(_path("expense_flow.xlsx"),
                       sheet_name="CSCG Relationship", header=None)
    headers = ["Component", "Amount", "Approval Required?", "Contract Reference"]
    data = df.iloc[3:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Component"])
    # Remove header echo, total, and projection rows
    data = data[~data["Component"].str.contains(
        "Component|TOTAL|ANNUALIZED|6-Month|Projected|Undisclosed|vs\\. Current",
        case=False, na=False)]
    data["Amount"] = pd.to_numeric(data["Amount"], errors="coerce")
    data = data.reset_index(drop=True)
    return data


# ── Expense Flow — Fixed Obligations ─────────────────────────────────────

@st.cache_data
def load_fixed_obligations() -> pd.DataFrame:
    """Fixed obligations section from Expense Flow Analysis (rows 24-31)."""
    df = pd.read_excel(_path("expense_flow.xlsx"),
                       sheet_name="Expense Flow Analysis", header=None)
    headers = ["Expense Category", "YTD per Financials", "YTD from Invoices",
               "Variance", "Approval Method", "Notes"]
    data = df.iloc[25:32].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Expense Category"])
    for col in ["YTD per Financials", "YTD from Invoices", "Variance"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.reset_index(drop=True)
    return data


# ── Scoreboard Economics ─────────────────────────────────────────────────

@st.cache_data
def load_scoreboard_10yr() -> pd.DataFrame:
    """10-year scoreboard economics projection (Sheet1)."""
    df = pd.read_excel(_path("scoreboard_economics.xlsx"),
                       sheet_name="Sheet1", header=None)
    years = list(range(1, 11))
    rows_of_interest = {
        "Existing Sponsor Revenue": 10,
        "Referral Sponsorship Revenue to NSIA": 18,
        "Non-Referral Revenue to NSIA": 23,
        "Total NSIA Sponsorship Revenue": 25,
        "Software License": 29,
        "Maintenance & Repair": 30,
        "Total Annual Costs": 31,
        "Net Cash Flow (Current Deal)": 33,
    }
    records = []
    for label, row_idx in rows_of_interest.items():
        vals = df.iloc[row_idx, 6:16].tolist()
        total = df.iloc[row_idx, 17]
        records.append({"Category": label, **{f"Year {y}": v for y, v in zip(years, vals)},
                        "10yr Total": total})
    return pd.DataFrame(records)


@st.cache_data
def load_scoreboard_alternative() -> pd.DataFrame:
    """Alternative cheaper scoreboard option (Sheet1 rows 43-46)."""
    df = pd.read_excel(_path("scoreboard_economics.xlsx"),
                       sheet_name="Sheet1", header=None)
    years = list(range(1, 11))
    rows = {
        "Upfront Cost": 43,
        "Annual Maintenance": 44,
        "Sponsorship Revenue": 45,
        "Net Cash Flow (Cheaper Alt)": 46,
    }
    records = []
    for label, row_idx in rows.items():
        vals = df.iloc[row_idx, 6:16].tolist()
        total = df.iloc[row_idx, 17]
        records.append({"Category": label, **{f"Year {y}": v for y, v in zip(years, vals)},
                        "10yr Total": total})
    return pd.DataFrame(records)


@st.cache_data
def load_historical_ad_revenue() -> pd.DataFrame:
    """Historical ad revenue from Sheet2 row 20."""
    df = pd.read_excel(_path("scoreboard_economics.xlsx"),
                       sheet_name="Sheet2", header=None)
    # Row 18 has years (2014-2024), row 20 has ad revenue
    year_row = df.iloc[18, 7:18].tolist()
    rev_row = df.iloc[20, 7:18].tolist()
    result = pd.DataFrame({"Year": [int(y) for y in year_row if pd.notna(y)],
                           "Ad Revenue": [r for r, y in zip(rev_row, year_row) if pd.notna(y)]})
    result["Ad Revenue"] = pd.to_numeric(result["Ad Revenue"], errors="coerce")
    return result


# ── Advertising ──────────────────────────────────────────────────────────

@st.cache_data
def load_current_ads() -> pd.DataFrame:
    """Current NSIA advertisers."""
    df = pd.read_excel(_path("current_ads.xlsx"), header=None)
    headers = ["Customer", "Type", "Location/Notes", "Term", "Expiration Date", "Cost"]
    data = df.iloc[1:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Customer"])
    # Clean expiration dates
    data["Expiration Date"] = pd.to_datetime(data["Expiration Date"], errors="coerce")
    # Clean cost column
    data["Cost (Numeric)"] = data["Cost"].apply(_clean_dollar)
    data = data.reset_index(drop=True)
    return data


@st.cache_data
def load_done_deals_prospects() -> pd.DataFrame:
    """Done deals and prospects pipeline."""
    df = pd.read_excel(_path("done_deals_prospects.xlsx"), header=None)
    headers = ["Advertiser", "$$", "Term", "Status", "Notes"]
    data = df.iloc[1:].copy()
    data.columns = headers[:len(data.columns)]
    data = data.dropna(subset=["Advertiser"])
    # Remove separator rows
    data = data[~data["Advertiser"].str.contains("Prospects / Pending", case=False, na=False)]
    data["Amount"] = data["$$"].apply(_clean_dollar)
    data = data.reset_index(drop=True)
    # Tag as Done or Prospect based on original position
    # In the source: rows 1-12 are Done, rows after "Prospects / Pending" are prospects
    done_idx = df[df[0].str.contains("Prospects / Pending", case=False, na=False)].index
    if len(done_idx) > 0:
        cutoff = done_idx[0]
    else:
        cutoff = len(df)
    # Map back: original row indices
    orig_indices = df.iloc[1:].dropna(subset=[0]).index
    orig_indices = orig_indices[~df.loc[orig_indices, 0].str.contains("Prospects / Pending", case=False, na=False)]
    data["Pipeline Stage"] = ["Done Deal" if idx < cutoff else "Prospect" for idx in orig_indices[:len(data)]]
    return data


# ── Hockey Schedule ──────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_hockey_schedule() -> pd.DataFrame:
    """Hockey schedule — all 6 New Trier teams, NSIA home games only."""
    df = pd.read_csv(_path("nt_hockey_all_teams.csv"))
    return df


# ── Weekend Ice Breakdown ────────────────────────────────────────────────

@st.cache_data
def load_weekend_ice_breakdown() -> pd.DataFrame:
    """Weekend ice allocation hours — Wilmette, Winnetka, New Trier (Sep-Mar)."""
    df = pd.read_csv(_path("weekend_ice_breakdown.csv"))
    return df


@st.cache_data(ttl=60)
def load_winnetka_nsia_usage() -> pd.DataFrame:
    """Winnetka Hockey Club weekend NSIA ice usage (scraped schedule)."""
    df = pd.read_csv(_path("winnetka_weekend_nsia.csv"))
    df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data(ttl=60)
def load_wilmette_nsia_usage() -> pd.DataFrame:
    """Wilmette Jr. Trevians weekend NSIA ice usage (scraped schedule)."""
    df = pd.read_csv(_path("wilmette_weekend_nsia.csv"))
    df["Date"] = pd.to_datetime(df["Date"])
    return df


# ── Derived KPIs ─────────────────────────────────────────────────────────

@st.cache_data
def compute_kpis() -> dict:
    """Compute top-level KPI values for the home page."""
    rev = load_revenue_reconciliation()
    exp = load_expense_reconciliation()
    hidden = load_hidden_cash_flows()

    # Total annual revenue: sum of Proposal YTD * 12/7 (annualize 7-month data)
    total_rev_ytd = rev[rev["Line Item"].str.startswith("Total")]["Proposal YTD Budget"].sum()
    # Use the total rows
    rev_totals = rev[rev["Line Item"].str.startswith("Total")]
    if len(rev_totals) == 0:
        total_rev_ytd = rev["Proposal YTD Budget"].sum()
    else:
        total_rev_ytd = rev_totals["Proposal YTD Budget"].sum()

    exp_totals = exp[exp["Line Item"].str.startswith("Total")]
    if len(exp_totals) == 0:
        total_exp_ytd = exp["Proposal YTD Budget"].sum()
    else:
        total_exp_ytd = exp_totals["Proposal YTD Budget"].sum()

    # Annualize from 7 months
    annual_rev = total_rev_ytd * 12 / 7
    annual_exp = total_exp_ytd * 12 / 7

    hidden_total = hidden["Annual Impact"].sum()

    # DSCR = Net Operating Income / Annual Debt Service
    # Debt service = Bond Principal ($255K) + Bond Interest ($368.5K) + Techny Loan ($62.5K + $12.8K)
    debt_service = hidden[hidden["Item"].str.contains(
        "Bond|Techny Loan", case=False, na=False)]["Annual Impact"].sum()
    net_operating_income = annual_rev - annual_exp
    dscr = net_operating_income / debt_service if debt_service > 0 else 0

    return {
        "total_annual_revenue": annual_rev,
        "total_annual_expenses": annual_exp,
        "net_cash_flow": annual_rev - annual_exp - hidden_total,
        "hidden_cash_outflows": hidden_total,
        "pct_board_approved": 0.255,
        "dscr": dscr,
        "debt_service": debt_service,
        "net_operating_income": net_operating_income,
    }


def compute_board_attention() -> list[dict]:
    """Generate board attention items based on current KPIs and variance alerts."""
    kpis = compute_kpis()
    items = []

    # DSCR warning
    if kpis["dscr"] < 1.25:
        severity = "AT RISK" if kpis["dscr"] < 1.0 else "CAUTION"
        items.append({
            "icon": "🔴" if kpis["dscr"] < 1.0 else "🟡",
            "text": f"DSCR at {kpis['dscr']:.2f}x — {severity}",
            "page": "Variance Alerts",
        })

    # Hidden cash outflows
    if kpis["hidden_cash_outflows"] > 500_000:
        items.append({
            "icon": "🔴",
            "text": f"${kpis['hidden_cash_outflows']:,.0f}/yr in hidden cash outflows not on board P&L",
            "page": "Bond & Debt",
        })

    # Low board approval percentage
    if kpis["pct_board_approved"] < 0.50:
        items.append({
            "icon": "🟡",
            "text": f"Only {kpis['pct_board_approved']*100:.1f}% of expenses require board invoice approval",
            "page": "CSCG Scorecard",
        })

    # Negative net cash flow
    if kpis["net_cash_flow"] < 0:
        items.append({
            "icon": "🔴",
            "text": f"Projected negative net cash flow: ${kpis['net_cash_flow']:,.0f}",
            "page": "Monthly Financials",
        })

    # RED variance alerts
    try:
        alerts = compute_variance_alerts()
        red_count = len(alerts[alerts["Severity"] == "RED"])
        if red_count > 0:
            items.append({
                "icon": "🔴",
                "text": f"{red_count} RED variance alert{'s' if red_count > 1 else ''} requiring review",
                "page": "Variance Alerts",
            })
    except Exception:
        pass

    # CSCG non-compliance
    try:
        scorecard = compute_cscg_scorecard()
        non_compliant = len(scorecard[scorecard["Status"] == "NON-COMPLIANT"])
        if non_compliant > 0:
            items.append({
                "icon": "🟡",
                "text": f"{non_compliant} CSCG contract term{'s' if non_compliant > 1 else ''} non-compliant",
                "page": "CSCG Scorecard",
            })
    except Exception:
        pass

    return items


# ── Variance Alerts ──────────────────────────────────────────────────────

@st.cache_data
def compute_variance_alerts(threshold_pct: float = 0.05) -> pd.DataFrame:
    """Flag all revenue and expense lines where CSCG deviates from proposal by more than threshold."""
    rev = load_revenue_reconciliation()
    exp = load_expense_reconciliation()

    rows = []
    for source, df in [("Revenue", rev), ("Expense", exp)]:
        for _, r in df.iterrows():
            item = r["Line Item"]
            if pd.isna(item) or str(item).startswith("Total"):
                continue

            proposal_ytd = r.get("Proposal YTD Budget")
            cscg_ytd = r.get("CSCG YTD Budget")
            variance = r.get("YTD Variance $")
            pct = r.get("YTD Variance %")
            assessment = r.get("Assessment", "")

            if pd.isna(proposal_ytd) and pd.isna(cscg_ytd):
                continue

            # Compute pct if missing
            if pd.isna(pct) and pd.notna(proposal_ytd) and proposal_ytd != 0:
                pct = (cscg_ytd - proposal_ytd) / abs(proposal_ytd) if pd.notna(cscg_ytd) else None

            abs_pct = abs(pct) if pd.notna(pct) else 0
            abs_var = abs(variance) if pd.notna(variance) else 0

            # Severity
            if abs_pct >= 0.50 or abs_var >= 10000:
                severity = "RED"
            elif abs_pct >= threshold_pct or abs_var >= 2000:
                severity = "YELLOW"
            else:
                severity = "GREEN"

            rows.append({
                "Category": source,
                "Line Item": item,
                "Proposal YTD": proposal_ytd,
                "CSCG YTD": cscg_ytd,
                "Variance $": variance,
                "Variance %": pct,
                "Severity": severity,
                "Assessment": assessment,
            })

    result = pd.DataFrame(rows)
    # Sort: RED first, then YELLOW, then GREEN
    sev_order = {"RED": 0, "YELLOW": 1, "GREEN": 2}
    result["_sort"] = result["Severity"].map(sev_order)
    result = result.sort_values(["_sort", "Variance $"], ascending=[True, True]).drop(columns="_sort")
    result = result.reset_index(drop=True)
    return result


# ── CSCG Contract Scorecard ──────────────────────────────────────────────

@st.cache_data
def compute_cscg_scorecard() -> pd.DataFrame:
    """Build CSCG contract compliance scorecard."""
    cscg = load_cscg_relationship()
    exp = load_expense_reconciliation()

    # Contract terms from the management agreement
    contract_terms = [
        {
            "Contract Term": "Management Fee (Article 7.1)",
            "Contract Amount": 42000,
            "Period": "Annual",
            "6mo Expected": 21000,
            "6mo Actual": cscg[cscg["Component"].str.contains("Management Fee", case=False, na=False)]["Amount"].sum(),
            "Source": "CSCG Relationship sheet",
        },
        {
            "Contract Term": "Office Payroll Reimbursement (Article 10.1)",
            "Contract Amount": None,
            "Period": "At cost",
            "6mo Expected": None,
            "6mo Actual": cscg[cscg["Component"].str.contains("Office Payroll", case=False, na=False)]["Amount"].sum(),
            "Source": "CSCG Relationship sheet",
        },
        {
            "Contract Term": "Operations Payroll Reimbursement (Article 10.1)",
            "Contract Amount": None,
            "Period": "At cost",
            "6mo Expected": None,
            "6mo Actual": cscg[cscg["Component"].str.contains("Operations Payroll", case=False, na=False)]["Amount"].sum(),
            "Source": "CSCG Relationship sheet",
        },
        {
            "Contract Term": "Workers Comp Insurance (Article 10.1)",
            "Contract Amount": None,
            "Period": "At cost",
            "6mo Expected": None,
            "6mo Actual": cscg[cscg["Component"].str.contains("Workers Comp", case=False, na=False)]["Amount"].sum(),
            "Source": "CSCG Relationship sheet",
        },
        {
            "Contract Term": "Land Lease — Techny (Ground Lease)",
            "Contract Amount": 385000,
            "Period": "Annual",
            "6mo Expected": 192500,
            "6mo Actual": 192500.35,
            "Source": "Expense Flow — Fixed Obligations",
        },
        {
            "Contract Term": "Bond Interest — DSRF (Bond Indenture)",
            "Contract Amount": 376356,
            "Period": "Annual",
            "6mo Expected": 188178,
            "6mo Actual": 188205.35,
            "Source": "Expense Flow — Fixed Obligations",
        },
        {
            "Contract Term": "Trustee Admin Fee — UMB",
            "Contract Amount": 6000,
            "Period": "Annual",
            "6mo Expected": 3000,
            "6mo Actual": 3000,
            "Source": "Expense Flow — Fixed Obligations",
        },
    ]

    df = pd.DataFrame(contract_terms)

    # Compliance check
    def check_compliance(row):
        if pd.isna(row["6mo Expected"]) or row["6mo Expected"] is None:
            return "AUTO-PAY"
        diff = abs(row["6mo Actual"] - row["6mo Expected"])
        pct = diff / row["6mo Expected"] if row["6mo Expected"] > 0 else 0
        if pct <= 0.02:
            return "COMPLIANT"
        elif pct <= 0.10:
            return "MINOR VARIANCE"
        else:
            return "NON-COMPLIANT"

    df["Status"] = df.apply(check_compliance, axis=1)
    return df


# ── Phase 2: Monthly Financials ─────────────────────────────────────────

@st.cache_data
def load_monthly_pnl() -> pd.DataFrame:
    """Monthly P&L budget vs actuals from financial summary PDFs."""
    return pd.read_csv(_path("monthly_pnl.csv"))


@st.cache_data
def load_cash_forecast() -> pd.DataFrame:
    """12-month cash forecast Jul 2025 - Jun 2026."""
    return pd.read_csv(_path("cash_forecast.csv"))


@st.cache_data
def load_contract_receivables() -> pd.DataFrame:
    """Contract receivables by customer (Sept and Nov snapshots)."""
    return pd.read_csv(_path("contract_receivables.csv"))


# ── Phase 2: Multi-Year Trends ──────────────────────────────────────────

@st.cache_data
def load_multiyear_revenue() -> pd.DataFrame:
    """3-year revenue and expense by category from Budget Rev 4 + Form 990."""
    return pd.read_csv(_path("multiyear_revenue.csv"))


@st.cache_data
def load_payroll_benchmarks() -> pd.DataFrame:
    """NSIA vs peer park district payroll benchmarks."""
    return pd.read_csv(_path("payroll_benchmarks.csv"))


# ── Phase 2: Ice Utilization ────────────────────────────────────────────

@st.cache_data
def load_weekday_ice_summary() -> pd.DataFrame:
    """Weekday ice allocation summary (rows 46-49 of Sheet1)."""
    df = pd.read_excel(_path("ice_weekday_breakdown.xlsx"),
                       sheet_name="Sheet1", header=None)
    # Summary at rows 46-49: row 46 is header, 47-49 are clubs
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    records = []
    for row_idx in range(47, 50):
        club = str(df.iloc[row_idx, 0])
        current_vals = [pd.to_numeric(df.iloc[row_idx, c], errors="coerce") for c in range(1, 6)]
        current_total = pd.to_numeric(df.iloc[row_idx, 6], errors="coerce")
        proposed_vals = [pd.to_numeric(df.iloc[row_idx, c], errors="coerce") for c in range(11, 16)]
        proposed_total = pd.to_numeric(df.iloc[row_idx, 16], errors="coerce")
        for i, day in enumerate(days):
            records.append({
                "Club": club,
                "Day": day,
                "Current Hours": current_vals[i],
                "Proposed Hours": proposed_vals[i],
            })
        records.append({
            "Club": club,
            "Day": "Total",
            "Current Hours": current_total,
            "Proposed Hours": proposed_total,
        })
    return pd.DataFrame(records)


@st.cache_data
def load_weekend_ice_summary() -> pd.DataFrame:
    """Weekend ice allocation summary (rows 91-94)."""
    df = pd.read_excel(_path("ice_weekend_breakdown.xlsx"), header=None)
    # Row 91 header, 92-94 clubs
    # Current: cols 1-2 (Wknd1 Sat/Sun), col 3 (Total W1), cols 5-6 (Wknd2 Sat/Sun), col 7 (Total W2)
    # Proposed: cols 10-11, 12, cols 14-15, 16
    records = []
    for row_idx in range(92, 95):
        club = str(df.iloc[row_idx, 0])
        records.append({
            "Club": club,
            "Weekend": "Weekend 1",
            "Current Saturday": pd.to_numeric(df.iloc[row_idx, 1], errors="coerce"),
            "Current Sunday": pd.to_numeric(df.iloc[row_idx, 2], errors="coerce"),
            "Current Total": pd.to_numeric(df.iloc[row_idx, 3], errors="coerce"),
            "Proposed Saturday": pd.to_numeric(df.iloc[row_idx, 10], errors="coerce"),
            "Proposed Sunday": pd.to_numeric(df.iloc[row_idx, 11], errors="coerce"),
            "Proposed Total": pd.to_numeric(df.iloc[row_idx, 12], errors="coerce"),
        })
        records.append({
            "Club": club,
            "Weekend": "Weekend 2",
            "Current Saturday": pd.to_numeric(df.iloc[row_idx, 5], errors="coerce"),
            "Current Sunday": pd.to_numeric(df.iloc[row_idx, 6], errors="coerce"),
            "Current Total": pd.to_numeric(df.iloc[row_idx, 7], errors="coerce"),
            "Proposed Saturday": pd.to_numeric(df.iloc[row_idx, 14], errors="coerce"),
            "Proposed Sunday": pd.to_numeric(df.iloc[row_idx, 15], errors="coerce"),
            "Proposed Total": pd.to_numeric(df.iloc[row_idx, 16], errors="coerce"),
        })
    return pd.DataFrame(records)


@st.cache_data
def load_winnetka_weekend_summary() -> pd.DataFrame:
    """Winnetka usage gaps — weekend summary."""
    return pd.read_excel(_path("winnetka_usage_gaps.xlsx"),
                         sheet_name="Weekend_Summary_WithCut")


@st.cache_data
def load_winnetka_day_level_gaps() -> pd.DataFrame:
    """Winnetka usage gaps — day-level detail."""
    return pd.read_excel(_path("winnetka_usage_gaps.xlsx"),
                         sheet_name="Day_Level_Gaps_WithCut")


# ── Phase 3: Reconciliation ───────────────────────────────────────────────

@st.cache_data
def load_proposed_entries() -> pd.DataFrame:
    """Parse 19 adjusting journal entries from proposed_entries.xlsx.
    Layout: cols B(1)/D(3)/F(5)/H(7)/J(9)/L(11) hold data; odd cols are spacers.
    Header rows repeat at 2, 35, 67.
    """
    df = pd.read_excel(_path("proposed_entries.xlsx"),
                       sheet_name="Proposed Entries", header=None)
    # Use the meaningful columns
    data = df[[1, 3, 5, 7, 9, 11]].copy()
    data.columns = ["Num", "Date", "Memo", "Account", "Debit", "Credit"]
    # Drop header rows (repeated at 0-2, 35, 67) and all-NaN rows
    header_rows = {0, 1, 2, 35, 67}
    data = data.drop(index=[i for i in header_rows if i in data.index], errors="ignore")
    # Drop rows where Account is NaN (blank separator rows)
    data = data.dropna(subset=["Account"])
    # Drop rows that echo the header text
    data = data[data["Account"] != "Account"]
    # Forward-fill Num, Date, Memo from the first line of each entry
    data["Num"] = data["Num"].ffill()
    data["Date"] = data["Date"].infer_objects(copy=False).ffill()
    data["Memo"] = data["Memo"].ffill()
    # Convert numerics
    data["Debit"] = pd.to_numeric(data["Debit"], errors="coerce").fillna(0)
    data["Credit"] = pd.to_numeric(data["Credit"], errors="coerce").fillna(0)
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.reset_index(drop=True)
    return data


@st.cache_data
def load_general_ledger() -> pd.DataFrame:
    """Read General_Ledger sheet — row 3 = headers, row 4+ = data."""
    df = pd.read_excel(_path("general_ledger.xlsx"),
                       sheet_name="General_Ledger", header=None)
    headers = ["Date", "GL #", "GL Account Name", "Type", "Bank",
               "Description", "Debit", "Credit", "Payee"]
    data = df.iloc[4:].copy()
    data.columns = headers[:len(data.columns)]
    # Drop the TOTALS row and blanks
    data = data.dropna(subset=["GL Account Name"])
    data = data[~data["GL Account Name"].str.contains("TOTAL", case=False, na=False)]
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["Debit"] = pd.to_numeric(data["Debit"], errors="coerce").fillna(0)
    data["Credit"] = pd.to_numeric(data["Credit"], errors="coerce").fillna(0)
    data["GL #"] = pd.to_numeric(data["GL #"], errors="coerce")
    data = data.reset_index(drop=True)
    return data


@st.cache_data
def load_gl_account_summary() -> pd.DataFrame:
    """Aggregate GL transactions by account — sum debits, credits, count."""
    gl = load_general_ledger()
    summary = gl.groupby(["GL #", "GL Account Name", "Type"]).agg(
        Total_Debit=("Debit", "sum"),
        Total_Credit=("Credit", "sum"),
        Transaction_Count=("Debit", "count"),
    ).reset_index()
    summary["Net"] = summary["Total_Debit"] - summary["Total_Credit"]
    return summary


@st.cache_data
def load_bills_summary() -> pd.DataFrame:
    """Read All Bills sheet — row 0 = header, 111 invoice rows."""
    df = pd.read_excel(_path("bills_summary.xlsx"),
                       sheet_name="All Bills", header=0)
    # Drop the TOTAL row
    df = df.dropna(subset=["Vendor"])
    df = df[~df["Vendor"].str.contains("TOTAL", case=False, na=False)]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.reset_index(drop=True)
    return df


@st.cache_data
def load_bills_by_category() -> pd.DataFrame:
    """Read Category Summary sheet — 7 categories."""
    df = pd.read_excel(_path("bills_summary.xlsx"),
                       sheet_name="Category Summary", header=0)
    df = df.dropna(subset=["Category"])
    df["Total Amount"] = pd.to_numeric(df["Total Amount"], errors="coerce")
    df["% of Total"] = pd.to_numeric(df["% of Total"], errors="coerce")
    df = df.reset_index(drop=True)
    return df


@st.cache_data
def load_bills_by_vendor() -> pd.DataFrame:
    """Read Vendor Summary sheet — 28 vendors."""
    df = pd.read_excel(_path("bills_summary.xlsx"),
                       sheet_name="Vendor Summary", header=0)
    df = df.dropna(subset=["Vendor"])
    df["Total Amount"] = pd.to_numeric(df["Total Amount"], errors="coerce")
    df = df.reset_index(drop=True)
    return df


@st.cache_data
def build_reconciliation_master() -> pd.DataFrame:
    """Core 4-way reconciliation: merge budget expenses + expense flow financials on line item.
    Computes Budget-Actual Variance, Actual-Invoice Variance, and Status.
    """
    budget = load_expense_reconciliation()
    flow = load_expense_flow()

    # Explicit name mapping: budget line item → expense flow category
    budget_to_flow = {
        "Electric": "Electric (Engie)",
        "Gas (Nicor)": "Gas (Nicor)",
        "Janitorial Supplies": "Janitorial Supplies (Ramrod)",
        "Insurance (Liab/Prop/D&O)": "Insurance - Liab, Prop, D&O",
        "Snowplow": "Landscaping/Snow",
        "Landscaping": "Landscaping/Snow",
        "Propane": "Propane",
        "Building Maintenance": "Building Maintenance",
        "Outside Consultants": "Auditor/Consultants",
        "Legal Fees": "Auditor/Consultants",
        "Cable/Internet": "Cable/Internet",
        "Security": "Security",
        "Operation Supplies": "Operation Supplies",
        "Office Payroll": "Office Payroll",
        "Operations Payroll": "Operations Payroll",
        "Workers Comp Insurance": "Workers Comp Insurance",
        "Men's League Payroll": "Men's League Payroll",
        "Management Fees": "Management Fees",
        "Land Lease": "Land Lease (Techny)",
        "Techny Loan Interest": "Techny Loan Interest",
        "Interest Expense (DSRF)": "Bond Interest (DSRF)",
        "Property Taxes": "Property Taxes",
        "Trustee Admin Fee": "Trustee Admin Fee (UMB)",
        "Scrubber Lease": "Scrubber Lease",
        "Scoreboard Software (Expense)": "Scoreboard Software",
        "On Ice Instruction": "Youth Programs (instruction)",
        "Off Ice Instruction": "Youth Programs (instruction)",
        "Advertising/Marketing (Youth)": "Youth Programs (instruction)",
        "Youth Program Supplies": "Youth Programs (instruction)",
    }

    # Build flow lookup by category name
    flow_lookup = {}
    for _, row in flow.iterrows():
        cat = str(row["Expense Category"]).strip()
        flow_lookup[cat] = row

    # Group budget items by their mapped flow category to handle many-to-one
    from collections import defaultdict
    flow_groups = defaultdict(list)  # flow_cat -> list of budget rows
    unmatched_budget = []

    for _, br in budget.iterrows():
        item = str(br["Line Item"]).strip()
        if item.startswith("Total") or not item:
            continue
        mapped = budget_to_flow.get(item)
        if mapped and mapped in flow_lookup:
            flow_groups[mapped].append(br)
        elif item in flow_lookup:
            flow_groups[item].append(br)
        else:
            unmatched_budget.append(br)

    rows = []
    seen_flow_cats = set()

    # Process grouped items (many budget → one flow category)
    for flow_cat, budget_rows in flow_groups.items():
        seen_flow_cats.add(flow_cat)
        fr = flow_lookup[flow_cat]
        actual_val = float(fr["YTD per Financials"]) if pd.notna(fr.get("YTD per Financials")) else 0
        invoice_val = float(fr["YTD from Invoices"]) if pd.notna(fr.get("YTD from Invoices")) else 0
        approval = str(fr.get("Approval Method", ""))

        if len(budget_rows) == 1:
            # One-to-one: show the budget item name
            br = budget_rows[0]
            budget_amt = br.get("CSCG YTD Budget")
            if pd.isna(budget_amt):
                budget_amt = br.get("Proposal YTD Budget")
            budget_val = float(budget_amt) if pd.notna(budget_amt) else 0
            label = str(br["Line Item"]).strip()
        else:
            # Many-to-one: combine budget items, use flow category name
            budget_val = 0
            names = []
            for br in budget_rows:
                amt = br.get("CSCG YTD Budget")
                if pd.isna(amt):
                    amt = br.get("Proposal YTD Budget")
                budget_val += float(amt) if pd.notna(amt) else 0
                names.append(str(br["Line Item"]).strip())
            label = flow_cat + " (" + " + ".join(names) + ")"

        ba_var = actual_val - budget_val
        ai_var = invoice_val - actual_val

        if actual_val == 0 and invoice_val == 0 and budget_val > 0:
            status = "Budget-Only"
        elif invoice_val == 0 and actual_val > 0:
            status = "No Invoice Trail"
        elif abs(ba_var) > 5000:
            status = "Major Variance"
        elif abs(ba_var) > 500:
            status = "Minor Variance"
        else:
            status = "Matched"

        rows.append({
            "Line Item": label,
            "Budget Amount": budget_val,
            "Financial (Actual)": actual_val,
            "Invoice Total": invoice_val,
            "Budget-Actual Variance": ba_var,
            "Actual-Invoice Variance": ai_var,
            "Approval Method": approval,
            "Status": status,
        })

    # Unmatched budget items (budget-only)
    for br in unmatched_budget:
        item = str(br["Line Item"]).strip()
        budget_amt = br.get("CSCG YTD Budget")
        if pd.isna(budget_amt):
            budget_amt = br.get("Proposal YTD Budget")
        budget_val = float(budget_amt) if pd.notna(budget_amt) else 0
        rows.append({
            "Line Item": item,
            "Budget Amount": budget_val,
            "Financial (Actual)": 0,
            "Invoice Total": 0,
            "Budget-Actual Variance": -budget_val if budget_val else None,
            "Actual-Invoice Variance": None,
            "Approval Method": "",
            "Status": "Budget-Only",
        })

    # Add any expense flow categories that didn't match budget items
    for _, fr in flow.iterrows():
        cat = str(fr["Expense Category"]).strip()
        if cat not in seen_flow_cats:
            actual = fr.get("YTD per Financials")
            invoice = fr.get("YTD from Invoices")
            actual_val = float(actual) if pd.notna(actual) else 0
            invoice_val = float(invoice) if pd.notna(invoice) else 0
            if actual_val == 0 and invoice_val == 0:
                continue  # skip empty summary rows
            ai_var = invoice_val - actual_val
            rows.append({
                "Line Item": cat,
                "Budget Amount": 0,
                "Financial (Actual)": actual_val,
                "Invoice Total": invoice_val,
                "Budget-Actual Variance": actual_val,
                "Actual-Invoice Variance": ai_var,
                "Approval Method": fr.get("Approval Method", ""),
                "Status": "Actual-Only",
            })

    result = pd.DataFrame(rows)
    # Sort by absolute variance descending
    result["_sort"] = result["Budget-Actual Variance"].abs().fillna(0)
    result = result.sort_values("_sort", ascending=False).drop(columns="_sort")
    result = result.reset_index(drop=True)
    return result
