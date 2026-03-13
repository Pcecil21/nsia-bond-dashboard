"""
Page 13: Board Report Generator
One-click board report that synthesizes KPIs, variance alerts, scorecard data,
and financial health into a comprehensive governance report via AI.
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import analyze_document, get_api_key, ANTHROPIC_AVAILABLE
from utils.theme import inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Board Report | NSIA", layout="wide", page_icon=":ice_hockey:")

# ── Dark theme CSS ────────────────────────────────────────────────────────
inject_css()
require_auth()

st.markdown("""
<style>
    .report-section {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .report-section h4 { color: #ccd6f6; margin: 0 0 8px 0; }
    .report-section p { color: #a8b2d1; margin: 0; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("Board Report Generator")
st.caption("One-click comprehensive governance report for board meetings")

# ── Preflight ─────────────────────────────────────────────────────────────
if not ANTHROPIC_AVAILABLE:
    st.error(
        "The `anthropic` Python package is not installed. "
        "Run `pip install anthropic` in your terminal, then restart the app."
    )
    st.stop()

if not get_api_key():
    st.error(
        "No API key found. Add your key to `.streamlit/secrets.toml`:\n\n"
        '```\nANTHROPIC_API_KEY = "sk-ant-your-key-here"\n```'
    )
    st.stop()

# ── Data Collection ───────────────────────────────────────────────────────
from utils.data_loader import (
    compute_kpis,
    compute_variance_alerts,
    compute_cscg_scorecard,
    load_hidden_cash_flows,
    load_cscg_relationship,
    load_unauthorized_modifications,
    load_cash_forecast,
    load_expense_flow_summary,
    load_monthly_pnl,
    load_contract_receivables,
)

st.markdown("---")

# Show what data will be included
st.markdown("### Report Data Sources")
st.markdown(
    "The report generator synthesizes data from across the dashboard into a single "
    "board-ready document. Review the sections below, then click **Generate Report**."
)

# Collect all data
kpis = compute_kpis()
alerts = compute_variance_alerts()
scorecard = compute_cscg_scorecard()
hidden = load_hidden_cash_flows()
cscg = load_cscg_relationship()
mods = load_unauthorized_modifications()
cash = load_cash_forecast()
expense_summary = load_expense_flow_summary()

red_alerts = alerts[alerts["Severity"] == "RED"]
yellow_alerts = alerts[alerts["Severity"] == "YELLOW"]

# Preview cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("DSCR", f"{kpis['dscr']:.2f}x")
    st.metric("RED Alerts", len(red_alerts))
with col2:
    st.metric("Net Cash Flow (est.)", f"${kpis['net_cash_flow']:,.0f}")
    st.metric("YELLOW Alerts", len(yellow_alerts))
with col3:
    st.metric("Hidden Outflows", f"${kpis['hidden_cash_outflows']:,.0f}/yr")
    non_compliant = len(scorecard[scorecard["Status"] == "NON-COMPLIANT"])
    st.metric("Non-Compliant Items", non_compliant)

st.markdown("---")

# ── Report Options ────────────────────────────────────────────────────────
st.markdown("### Report Options")

col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    meeting_date = st.date_input("Board Meeting Date", value=date.today())
    report_period = st.text_input("Reporting Period", value="FY2026 — Through January 2026 (Month 7)")
with col_opt2:
    include_sections = st.multiselect(
        "Sections to include",
        [
            "Executive Summary & DSCR",
            "Variance Alerts (RED/YELLOW)",
            "CSCG Scorecard & Compliance",
            "Hidden Cash Flows",
            "Cash Forecast & Financial Health",
            "Unauthorized Budget Modifications",
            "Governance Recommendations",
        ],
        default=[
            "Executive Summary & DSCR",
            "Variance Alerts (RED/YELLOW)",
            "CSCG Scorecard & Compliance",
            "Hidden Cash Flows",
            "Cash Forecast & Financial Health",
            "Unauthorized Budget Modifications",
            "Governance Recommendations",
        ],
    )
    additional_notes = st.text_area(
        "Additional notes for the report (optional)",
        placeholder="e.g., 'Include discussion of chiller contract renewal' or 'Flag upcoming insurance renewal'",
        height=100,
    )

st.markdown("---")

# ── Generate Report ───────────────────────────────────────────────────────
if st.button("Generate Board Report", type="primary", use_container_width=True):

    # Build comprehensive data payload for the Report Generator agent
    report_data = []
    report_data.append(f"NSIA BOARD REPORT — {meeting_date.strftime('%B %d, %Y')}")
    report_data.append(f"Reporting Period: {report_period}")
    report_data.append(f"Generated: {date.today().isoformat()}")
    report_data.append("")

    if "Executive Summary & DSCR" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: EXECUTIVE SUMMARY & KEY METRICS")
        report_data.append("=" * 60)
        report_data.append(f"DSCR: {kpis['dscr']:.2f}x")
        report_data.append(f"Net Operating Income: ${kpis['net_operating_income']:,.0f}")
        report_data.append(f"Annual Debt Service: ${kpis['debt_service']:,.0f}")
        report_data.append(f"Total Annual Revenue (est.): ${kpis['total_annual_revenue']:,.0f}")
        report_data.append(f"Total Annual Expenses (est.): ${kpis['total_annual_expenses']:,.0f}")
        report_data.append(f"Net Cash Flow (est.): ${kpis['net_cash_flow']:,.0f}")
        report_data.append(f"Hidden Cash Outflows: ${kpis['hidden_cash_outflows']:,.0f}/yr")
        report_data.append(f"Board-Approved Expenses: {kpis['pct_board_approved']*100:.1f}%")
        report_data.append("")

    if "Variance Alerts (RED/YELLOW)" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: VARIANCE ALERTS")
        report_data.append("=" * 60)
        report_data.append(f"RED Alerts: {len(red_alerts)} | YELLOW Alerts: {len(yellow_alerts)}")
        if not red_alerts.empty:
            report_data.append("\nRED ALERTS (require board attention):")
            report_data.append(red_alerts[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                                            "Variance $", "Variance %", "Assessment"]].to_csv(index=False))
        if not yellow_alerts.empty:
            report_data.append("\nYELLOW ALERTS (monitor closely):")
            report_data.append(yellow_alerts[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                                               "Variance $", "Variance %"]].to_csv(index=False))
        non_green = alerts[alerts["Severity"] != "GREEN"]
        report_data.append(f"\nNet Budget Impact (YTD): ${non_green['Variance $'].sum():+,.0f}")
        report_data.append("")

    if "CSCG Scorecard & Compliance" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: CSCG CONTRACT COMPLIANCE")
        report_data.append("=" * 60)
        report_data.append(scorecard.to_csv(index=False))
        total_cscg = cscg["Amount"].sum()
        mgmt_fee = cscg[cscg["Component"].str.contains("Management Fee", case=False, na=False)]["Amount"].sum()
        report_data.append(f"\nTotal CSCG Payments (6 mo): ${total_cscg:,.0f}")
        report_data.append(f"Disclosed (Mgmt Fee): ${mgmt_fee:,.0f}")
        report_data.append(f"Undisclosed (Auto-Pay): ${total_cscg - mgmt_fee:,.0f}")
        report_data.append("")

    if "Hidden Cash Flows" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: HIDDEN CASH FLOWS")
        report_data.append("=" * 60)
        report_data.append(hidden.to_csv(index=False))
        report_data.append(f"\nTotal Hidden Outflows: ${hidden['Annual Impact'].sum():,.0f}/yr")
        report_data.append("")

    if "Cash Forecast & Financial Health" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: CASH FORECAST")
        report_data.append("=" * 60)
        report_data.append(cash.to_csv(index=False))
        end_cash = cash["Cumulative Cash"].iloc[-1]
        min_cash = cash["Cumulative Cash"].min()
        min_month = cash.loc[cash["Cumulative Cash"].idxmin(), "Month"]
        report_data.append(f"\nEnding Cash Position: ${end_cash:,.0f}")
        report_data.append(f"Lowest Cash Point: ${min_cash:,.0f} ({min_month})")
        report_data.append("")

    if "Unauthorized Budget Modifications" in include_sections:
        mods_filtered = mods[~mods["Line Item"].str.contains(
            "AGGREGATE|Total|Net Budget", case=False, na=False)].copy()
        mods_filtered = mods_filtered.dropna(subset=["Severity"])
        if not mods_filtered.empty:
            report_data.append("=" * 60)
            report_data.append("SECTION: UNAUTHORIZED BUDGET MODIFICATIONS")
            report_data.append("=" * 60)
            report_data.append(mods_filtered.to_csv(index=False))
            report_data.append("")

    if "Governance Recommendations" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: GOVERNANCE CONTEXT")
        report_data.append("=" * 60)
        report_data.append("Expense approval breakdown:")
        report_data.append(expense_summary.to_csv(index=False))
        report_data.append("")

    if additional_notes:
        report_data.append("=" * 60)
        report_data.append("ADDITIONAL NOTES FROM BOARD PRESIDENT")
        report_data.append("=" * 60)
        report_data.append(additional_notes)
        report_data.append("")

    full_payload = "\n".join(report_data)

    with st.spinner("Generating board report... This may take 30-60 seconds."):
        result = analyze_document(
            agent_id="report_generator",
            document_content=full_payload,
            filename="board_report_data.txt",
            additional_context=(
                f"Generate a comprehensive board governance report for the NSIA board meeting "
                f"on {meeting_date.strftime('%B %d, %Y')}. "
                f"Reporting period: {report_period}. "
                f"Structure the report with: Executive Summary, Key Metrics, "
                f"Critical Findings (RED items first), Financial Health Assessment, "
                f"CSCG Performance Evaluation, and Recommended Board Actions. "
                f"Use clear, direct language suitable for a volunteer nonprofit board. "
                f"Flag the 3-5 most important items that require a board vote or discussion."
            ),
        )

    if result:
        st.markdown("---")
        st.markdown("### Generated Board Report")

        # Alert banners
        red_flags = result.count("🔴")
        yellow_flags = result.count("🟡")
        if red_flags > 0:
            st.error(f"**{red_flags} critical item(s)** identified for board attention")
        if yellow_flags > 0:
            st.warning(f"**{yellow_flags} caution item(s)** flagged for review")

        # Display the report
        st.markdown(result)

        # Download options
        st.markdown("---")
        st.markdown("### Download Report")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="📥 Download as Markdown",
                data=result,
                file_name=f"nsia_board_report_{meeting_date.isoformat()}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            # Plain text version for email
            st.download_button(
                label="📥 Download as Plain Text",
                data=result,
                file_name=f"nsia_board_report_{meeting_date.isoformat()}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        # Store in session for cross-page use
        if "board_reports" not in st.session_state:
            st.session_state.board_reports = []
        st.session_state.board_reports.append({
            "date": meeting_date.isoformat(),
            "generated": date.today().isoformat(),
            "result": result,
        })

# ── Previous Reports (session) ────────────────────────────────────────────
if "board_reports" in st.session_state and st.session_state.board_reports:
    st.markdown("---")
    with st.expander(
        f"Previous Reports ({len(st.session_state.board_reports)} this session)",
        expanded=False,
    ):
        for i, report in enumerate(reversed(st.session_state.board_reports)):
            st.markdown(f"**{i + 1}.** Meeting: {report['date']} | Generated: {report['generated']}")
        if st.button("Clear Report History"):
            st.session_state.board_reports = []
            st.rerun()
