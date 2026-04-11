"""
Page 13: Board Report Generator
One-click board report that synthesizes KPIs, variance alerts, scorecard data,
and financial health into a comprehensive governance report via AI.
"""
import streamlit as st
import sys
import pandas as pd
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import analyze_document, get_api_key, ANTHROPIC_AVAILABLE
from utils.theme import inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_current_month, get_month_label

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

st.markdown("---")

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
    load_vendor_contracts,
    load_cscg_budget_submissions,
    load_bond_documents,
    get_expiring_contracts,
    get_open_action_items,
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

# PDF-extracted sources (populated by pdf_extractor.py)
vendor_contracts = load_vendor_contracts()
budget_submissions = load_cscg_budget_submissions()
bond_docs = load_bond_documents()
expiring = get_expiring_contracts(90)
open_actions = get_open_action_items()

# Preview cards
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("DSCR", f"{kpis['dscr']:.2f}x")
    st.metric("RED Alerts", len(red_alerts))
with col2:
    st.metric("Net Cash Flow (est.)", f"${kpis['net_cash_flow']:,.0f}")
    st.metric("YELLOW Alerts", len(yellow_alerts))
with col3:
    st.metric("Off-Budget Outflows", f"${kpis['hidden_cash_outflows']:,.0f}/yr")
    non_compliant = len(scorecard[scorecard["Status"] == "NON-COMPLIANT"])
    st.metric("Non-Compliant Items", non_compliant)

st.caption("These metrics will be included in the generated report based on your section selections below.")

# ── PDF-Extracted Data Sources Status ─────────────────────────────────────
st.markdown("#### PDF-Extracted Data Sources")
st.caption("Sources populated by PDF extraction. Green indicates data is available for the AI Board Memo.")

_src_status = [
    ("Vendor Contracts", len(vendor_contracts)),
    ("Budget Submissions", len(budget_submissions)),
    ("Bond Documents", len(bond_docs)),
    ("Expiring (90d)", len(expiring)),
    ("Action Items", len(open_actions)),
]
_status_cols = st.columns(len(_src_status))
for _ci, (_lbl, _cnt) in enumerate(_src_status):
    with _status_cols[_ci]:
        _has = _cnt > 0
        st.markdown(
            f'<div class="report-section">'
            f'<h4>{_lbl}</h4>'
            f'<p style="font-size:1.5rem;color:{"#00d084" if _has else "#4a5568"};font-weight:700;margin:4px 0;">'
            f'{"&#10003; " + str(_cnt) if _has else "&mdash;"}</p>'
            f'<p style="font-size:0.78rem;">{"record" if _cnt == 1 else "records"}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Report Options ────────────────────────────────────────────────────────
st.markdown("### Report Options")

col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    meeting_date = st.date_input("Board Meeting Date", value=date.today())
    report_period = st.text_input("Reporting Period", value=f"{get_current_month()['fiscal_year']} — Through {get_month_label()}")
with col_opt2:
    include_sections = st.multiselect(
        "Sections to include",
        [
            "Executive Summary & DSCR",
            "Variance Alerts (RED/YELLOW)",
            "CSCG Scorecard & Compliance",
            "Off-Budget Cash Flows",
            "Cash Forecast & Financial Health",
            "Unauthorized Budget Modifications",
            "Governance Recommendations",
        ],
        default=[
            "Executive Summary & DSCR",
            "Variance Alerts (RED/YELLOW)",
            "CSCG Scorecard & Compliance",
            "Off-Budget Cash Flows",
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
        report_data.append(f"Off-Budget Cash Outflows: ${kpis['hidden_cash_outflows']:,.0f}/yr")
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

    if "Off-Budget Cash Flows" in include_sections:
        report_data.append("=" * 60)
        report_data.append("SECTION: OFF-BUDGET CASH FLOWS")
        report_data.append("=" * 60)
        report_data.append(hidden.to_csv(index=False))
        report_data.append(f"\nTotal Off-Budget Outflows: ${hidden['Annual Impact'].sum():,.0f}/yr")
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

# ── Generate AI Board Memo ────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Generate AI Board Memo")
st.caption(
    "Board memo synthesized from PDF-extracted governing documents, vendor contracts, "
    "and financial submissions — separate from the full Board Report above."
)

_memo_opt1, _memo_opt2 = st.columns(2)
with _memo_opt1:
    memo_sections = st.multiselect(
        "Memo sections to include",
        [
            "Financial Flags (Budget Submissions)",
            "Expiring Contracts",
            "Open Action Items",
            "Bond Covenant Status",
            "Document Red Flags",
        ],
        default=[
            "Financial Flags (Budget Submissions)",
            "Expiring Contracts",
            "Open Action Items",
            "Bond Covenant Status",
            "Document Red Flags",
        ],
        key="memo_sections",
    )
with _memo_opt2:
    memo_date = st.date_input("Memo Date", value=date.today(), key="memo_date")
    memo_notes = st.text_area(
        "Additional context (optional)",
        placeholder="e.g., 'Focus on the CSCG contract renewal discussion'",
        height=80,
        key="memo_notes",
    )

if st.button("Generate AI Board Memo", type="primary", use_container_width=True, key="memo_btn"):

    _memo_data = []
    _memo_data.append(f"NSIA BOARD MEMO — {memo_date.strftime('%B %d, %Y')}")
    _memo_data.append(f"Generated: {date.today().isoformat()}")
    _memo_data.append("")

    if "Financial Flags (Budget Submissions)" in memo_sections and not budget_submissions.empty:
        _memo_data.append("=" * 60)
        _memo_data.append("SECTION: FINANCIAL FLAGS FROM BUDGET SUBMISSIONS")
        _memo_data.append("=" * 60)
        _has_ba = "is_budget_or_actual" in budget_submissions.columns
        for _, _bs in budget_submissions.iterrows():
            _src = str(_bs.get("_source_file") or "Unknown")
            _ba = str(_bs.get("is_budget_or_actual") or "") if _has_ba else ""
            _memo_data.append(f"Document: {_src}" + (f" ({_ba})" if _ba else ""))
            for _field, _label in [
                ("revenue_total", "Revenue"),
                ("expense_total", "Expenses"),
                ("net_income", "Net Income"),
            ]:
                _val = _bs.get(_field)
                if pd.notna(_val):
                    _memo_data.append(f"  {_label}: ${_val:,.0f}")
        _memo_data.append("")

    if "Expiring Contracts" in memo_sections and not expiring.empty:
        _memo_data.append("=" * 60)
        _memo_data.append("SECTION: EXPIRING CONTRACTS (WITHIN 90 DAYS)")
        _memo_data.append("=" * 60)
        for _, _ec in expiring.iterrows():
            _vname = str(_ec.get("vendor_name") or "Unknown")
            _days = int(_ec.get("days_to_expiry", 0))
            _edate = _ec.get("expiry_date")
            _edate_str = _edate.strftime("%b %d, %Y") if pd.notna(_edate) else "Unknown"
            _val = _ec.get("annual_value")
            _val_str = f" — ${_val:,.0f}/yr" if pd.notna(_val) else ""
            _memo_data.append(f"  {_vname}: expires {_edate_str} ({_days} days){_val_str}")
        _memo_data.append("")

    if "Open Action Items" in memo_sections and open_actions:
        _memo_data.append("=" * 60)
        _memo_data.append("SECTION: OPEN BOARD ACTION ITEMS")
        _memo_data.append("=" * 60)
        for _ai in open_actions:
            _desc = str(_ai.get("description") or "")
            _owner = str(_ai.get("owner") or "")
            _due = str(_ai.get("due_date") or "")
            _line = f"  - {_desc}"
            if _owner:
                _line += f" (Owner: {_owner})"
            if _due:
                _line += f" — Due: {_due}"
            _memo_data.append(_line)
        _memo_data.append("")

    if "Bond Covenant Status" in memo_sections and not bond_docs.empty:
        _memo_data.append("=" * 60)
        _memo_data.append("SECTION: BOND COVENANT STATUS")
        _memo_data.append("=" * 60)
        for _, _bd in bond_docs.iterrows():
            _dtype = str(_bd.get("document_type") or "")
            if _dtype:
                _memo_data.append(f"Document type: {_dtype}")
            _dscr_min = _bd.get("dscr_minimum")
            if pd.notna(_dscr_min):
                _memo_data.append(f"  DSCR Covenant Minimum: {_dscr_min:.2f}x")
            _lease_exp = _bd.get("lease_expiry_date")
            if pd.notna(_lease_exp):
                _yrs = int((_lease_exp - pd.Timestamp.now()).days / 365.25)
                _memo_data.append(f"  Lease Expires: {_lease_exp.strftime('%Y')} ({_yrs} years remaining)")
            _bond_mat = _bd.get("bond_maturity_date")
            if pd.notna(_bond_mat):
                _memo_data.append(f"  Bond Maturity: {_bond_mat.strftime('%Y')}")
        _memo_data.append("")

    if "Document Red Flags" in memo_sections:
        _all_doc_flags = []
        for _flag_src, _flag_label, _name_col in [
            (vendor_contracts, "Vendor Contract", "vendor_name"),
            (bond_docs, "Bond Document", "document_type"),
        ]:
            if not _flag_src.empty and "red_flags" in _flag_src.columns:
                for _, _fr in _flag_src.iterrows():
                    _flag_val = str(_fr.get("red_flags") or "")
                    if _flag_val and _flag_val not in ("nan", "None"):
                        _fname = str(_fr.get(_name_col) or "")
                        _all_doc_flags.append(f"  [{_flag_label}] {_fname}: {_flag_val}")
        if _all_doc_flags:
            _memo_data.append("=" * 60)
            _memo_data.append("SECTION: DOCUMENT RED FLAGS")
            _memo_data.append("=" * 60)
            _memo_data.extend(_all_doc_flags)
            _memo_data.append("")

    if memo_notes:
        _memo_data.append("=" * 60)
        _memo_data.append("ADDITIONAL CONTEXT FROM BOARD PRESIDENT")
        _memo_data.append("=" * 60)
        _memo_data.append(memo_notes)
        _memo_data.append("")

    _memo_payload = "\n".join(_memo_data)

    with st.spinner("Generating board memo... This may take 30-60 seconds."):
        _memo_result = analyze_document(
            agent_id="report_generator",
            document_content=_memo_payload,
            filename="board_memo_data.txt",
            additional_context=(
                f"Generate a concise board memo for the NSIA board meeting on "
                f"{memo_date.strftime('%B %d, %Y')}. "
                f"Structure it as: (a) Financial Flags — highlight any revenue shortfalls or "
                f"expense overruns vs budget from submitted financial documents; "
                f"(b) Expiring Contracts — list each vendor, expiry date, annual value, and "
                f"recommended board action; "
                f"(c) Open Action Items — summarize outstanding items from board minutes with "
                f"accountability and next steps; "
                f"(d) Bond Covenant Status — flag any DSCR or reserve fund concerns derived "
                f"from the governing documents; "
                f"(e) Document Red Flags — any governance or legal concerns extracted from "
                f"governing documents and vendor contracts. "
                f"Use plain language suitable for a volunteer nonprofit board. "
                f"Lead with the 2-3 items that need a board vote or immediate decision."
            ),
        )

    if _memo_result:
        st.markdown("---")
        st.markdown("### Generated Board Memo")

        _red_ct = _memo_result.count("🔴")
        _yel_ct = _memo_result.count("🟡")
        if _red_ct > 0:
            st.error(f"**{_red_ct} critical item(s)** identified for board attention")
        if _yel_ct > 0:
            st.warning(f"**{_yel_ct} caution item(s)** flagged for review")

        st.markdown(_memo_result)

        st.markdown("---")
        st.markdown("### Download Memo")
        _dl1, _dl2 = st.columns(2)
        with _dl1:
            st.download_button(
                label="Download as Markdown",
                data=_memo_result,
                file_name=f"nsia_board_memo_{memo_date.isoformat()}.md",
                mime="text/markdown",
                use_container_width=True,
                key="memo_dl_md",
            )
        with _dl2:
            st.download_button(
                label="Download as Plain Text",
                data=_memo_result,
                file_name=f"nsia_board_memo_{memo_date.isoformat()}.txt",
                mime="text/plain",
                use_container_width=True,
                key="memo_dl_txt",
            )

        if "board_memos" not in st.session_state:
            st.session_state.board_memos = []
        st.session_state.board_memos.append({
            "date": memo_date.isoformat(),
            "generated": date.today().isoformat(),
            "result": _memo_result,
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
