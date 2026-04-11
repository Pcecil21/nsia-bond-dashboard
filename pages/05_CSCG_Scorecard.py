"""
Page 6: CSCG Contract Scorecard
Contract compliance checklist, disclosed vs undisclosed payments, and relationship analysis.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import analyze_document, get_api_key, ANTHROPIC_AVAILABLE
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_period_label

st.set_page_config(page_title="CSCG Scorecard | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("CSCG Contract Scorecard")
st.caption("Management agreement compliance and financial relationship transparency")

st.info(
    "This page supports the board's fiduciary oversight of CSCG (Club Sports Consulting Group), "
    "the management company hired to run daily operations. It tracks whether CSCG is operating "
    "within the terms the board approved. Items marked 'non-compliant' or 'unauthorized' mean "
    "they were not formally voted on by the board — this is a governance tracking tool, not an "
    "accusation of wrongdoing."
)

from utils.data_loader import (
    compute_board_demands,
    compute_cscg_scorecard,
    load_cscg_budget_submissions,
    load_cscg_relationship,
    load_expense_flow_summary,
    load_unauthorized_modifications,
)

# ── Contract Compliance Table ─────────────────────────────────────────────
st.header("Contract Compliance Checklist")
st.markdown("Verifying CSCG payments against management agreement terms.")

scorecard = compute_cscg_scorecard()

# Status styling
def status_style(val):
    styles = {
        "COMPLIANT": "background-color: #00d08433; color: #7bdcb5; font-weight: bold",
        "AUTO-PAY": "background-color: #0984e333; color: #74b9ff; font-weight: bold",
        "MINOR VARIANCE": "background-color: #fcb90033; color: #fcb900; font-weight: bold",
        "NON-COMPLIANT": "background-color: #eb144c33; color: #ff6b6b; font-weight: bold",
    }
    return styles.get(val, "")

st.dataframe(
    scorecard.style.map(status_style, subset=["Status"]),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Contract Amount": st.column_config.NumberColumn(format="$%,.0f"),
        "6mo Expected": st.column_config.NumberColumn(format="$%,.0f"),
        "6mo Actual": st.column_config.NumberColumn(format="$%,.0f"),
    },
)

# Compliance summary
compliant = len(scorecard[scorecard["Status"] == "COMPLIANT"])
auto_pay = len(scorecard[scorecard["Status"] == "AUTO-PAY"])
minor = len(scorecard[scorecard["Status"] == "MINOR VARIANCE"])
non_compliant = len(scorecard[scorecard["Status"] == "NON-COMPLIANT"])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Compliant", compliant)
with col2:
    st.metric("Auto-Pay (no contract cap)", auto_pay)
with col3:
    st.metric("Minor Variance", minor)
with col4:
    st.metric("Non-Compliant", non_compliant)

st.markdown("")

# ── Compliance Gauge ──────────────────────────────────────────────────────
verifiable = scorecard[scorecard["Status"] != "AUTO-PAY"]
if len(verifiable) > 0:
    compliance_pct = len(verifiable[verifiable["Status"] == "COMPLIANT"]) / len(verifiable) * 100
else:
    compliance_pct = 100

fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=compliance_pct,
    number=dict(suffix="%", font=dict(size=48, color="#e6f1ff")),
    title=dict(text="Contract Compliance Rate (verifiable terms)", font=dict(size=16, color=TITLE_COLOR)),
    gauge=dict(
        axis=dict(range=[0, 100], tickfont=dict(color="#a8b2d1"), tickcolor="#a8b2d1", dtick=25),
        bar=dict(color="#00d084" if compliance_pct >= 80 else "#fcb900" if compliance_pct >= 60 else "#eb144c",
                 thickness=0.75),
        bgcolor="rgba(168,178,209,0.1)",
        bordercolor="rgba(168,178,209,0.3)",
        steps=[
            dict(range=[0, 60], color="rgba(235,20,76,0.2)"),
            dict(range=[60, 80], color="rgba(252,185,0,0.2)"),
            dict(range=[80, 100], color="rgba(0,208,132,0.2)"),
        ],
    ),
))
fig_gauge.update_layout(
    height=280,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#a8b2d1"),
    margin=dict(t=60, b=20, l=30, r=30),
)
st.plotly_chart(fig_gauge, use_container_width=True)

# ── Disclosed vs Undisclosed ──────────────────────────────────────────────
st.markdown("---")
st.header("Disclosed vs. Undisclosed CSCG Payments")
st.caption("Payments or compensation arrangements not included in the management fee disclosure to the board.")
st.markdown(
    "The management agreement discloses a **$42,000/year management fee**. "
    "But the total CSCG financial relationship is significantly larger."
)

cscg = load_cscg_relationship()
total_cscg = cscg["Amount"].sum()
mgmt_fee = cscg[cscg["Component"].str.contains("Management Fee", case=False, na=False)]["Amount"].sum()
undisclosed = total_cscg - mgmt_fee

col1, col2 = st.columns(2)

with col1:
    # Stacked bar showing disclosed vs undisclosed
    fig_disc = go.Figure()
    fig_disc.add_trace(go.Bar(
        x=[f"CSCG Relationship ({get_period_label(6)})"],
        y=[mgmt_fee],
        name="Disclosed (Management Fee)",
        marker=dict(color="#00d084", line=dict(width=1.5, color="rgba(255,255,255,0.3)")),
        text=f"${mgmt_fee:,.0f}",
        textposition="inside",
        textfont=dict(color="#fff", size=14, family="Arial Black"),
        hovertemplate="<b>Disclosed</b><br>Management Fee: $%{y:,.0f}<extra></extra>",
    ))
    fig_disc.add_trace(go.Bar(
        x=[f"CSCG Relationship ({get_period_label(6)})"],
        y=[undisclosed],
        name="Undisclosed (Payroll + Other)",
        marker=dict(color="#eb144c", line=dict(width=1.5, color="rgba(255,255,255,0.3)")),
        text=f"${undisclosed:,.0f}",
        textposition="inside",
        textfont=dict(color="#fff", size=14, family="Arial Black"),
        hovertemplate="<b>Undisclosed</b><br>Payroll + Workers Comp + Referees: $%{y:,.0f}<extra></extra>",
    ))
    fig_disc.update_layout(
        title="CSCG Payments: Disclosed vs. Undisclosed",
        barmode="stack",
        yaxis_title="6-Month Amount ($)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        bargap=0.5,
    )
    style_chart(fig_disc, 420)
    st.plotly_chart(fig_disc, use_container_width=True)

with col2:
    # Pie showing proportion
    fig_pie = go.Figure(go.Pie(
        labels=["Disclosed<br>(Mgmt Fee)", "Undisclosed<br>(Auto-Pay)"],
        values=[mgmt_fee, undisclosed],
        hole=0.55,
        marker=dict(
            colors=["#00d084", "#eb144c"],
            line=dict(color="#0a192f", width=2.5),
        ),
        textinfo="percent+label",
        textfont=dict(size=13, color="#e6f1ff"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent:.1%}<extra></extra>",
    ))
    fig_pie.update_layout(
        title=dict(text="CSCG Payment Transparency", font=dict(size=16, color=TITLE_COLOR)),
        showlegend=False,
        annotations=[dict(text=f"<b>${total_cscg:,.0f}</b><br>Total",
                          x=0.5, y=0.5, font_size=15, font_color="#e6f1ff", showarrow=False)],
    )
    style_chart(fig_pie, 420)
    st.plotly_chart(fig_pie, use_container_width=True)

# Key stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Disclosed Management Fee (6 mo)", f"${mgmt_fee:,.0f}")
with col2:
    st.metric("Undisclosed Auto-Pay (6 mo)", f"${undisclosed:,.0f}")
with col3:
    pct_undisclosed = undisclosed / total_cscg * 100 if total_cscg > 0 else 0
    st.metric("% Undisclosed", f"{pct_undisclosed:.0f}%",
              delta="of total CSCG payments", delta_color="off")

# ── CSCG Payment Detail ──────────────────────────────────────────────────
st.markdown("---")
st.header("CSCG Payment Components — Detail")

# Horizontal bar with labels
cscg_sorted = cscg.sort_values("Amount", ascending=True)
bar_colors = ["#6c5ce7", "#0984e3", "#00b894", "#fdcb6e", "#e17055"]

fig_detail = go.Figure(go.Bar(
    y=cscg_sorted["Component"],
    x=cscg_sorted["Amount"],
    orientation="h",
    marker=dict(
        color=bar_colors[:len(cscg_sorted)],
        line=dict(width=1.5, color="rgba(255,255,255,0.2)"),
    ),
    text=[f"${v:,.0f}" for v in cscg_sorted["Amount"]],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=12),
    hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
))
fig_detail.update_layout(
    title=f"CSCG Payment Components ({get_period_label(6)})",
    xaxis_title="Amount ($)",
)
style_chart(fig_detail, 380)
st.plotly_chart(fig_detail, use_container_width=True)

# ── Unauthorized Modifications by CSCG ────────────────────────────────────
st.markdown("---")
st.header("CSCG Budget Modifications Without Board Approval")
st.caption("Budget changes made by CSCG that were not formally approved by board vote.")
st.markdown(
    "Line items where CSCG changed the operational budget without a formal board amendment. "
    "These modifications represent CSCG exercising budget authority beyond their contract scope."
)

mods = load_unauthorized_modifications()
# Filter to actual modifications (exclude totals/summaries)
mods_filtered = mods[~mods["Line Item"].str.contains("AGGREGATE|Total|Net Budget", case=False, na=False)].copy()
mods_filtered = mods_filtered.dropna(subset=["Severity"])

if not mods_filtered.empty:
    # Count by severity
    sev_counts = mods_filtered["Severity"].value_counts().reset_index()
    sev_counts.columns = ["Severity", "Count"]
    sev_color_map = {"CRITICAL": "#ff006e", "HIGH": "#eb144c", "MEDIUM": "#fcb900", "LOW": "#00d084"}

    fig_sev = go.Figure(go.Pie(
        labels=sev_counts["Severity"],
        values=sev_counts["Count"],
        hole=0.55,
        marker=dict(
            colors=[sev_color_map.get(s, "#abb8c3") for s in sev_counts["Severity"]],
            line=dict(color="#0a192f", width=2),
        ),
        textinfo="label+value",
        textfont=dict(size=13, color="#e6f1ff"),
    ))
    fig_sev.update_layout(
        title=dict(text="Unauthorized Modifications by Severity", font=dict(size=16, color=TITLE_COLOR)),
        showlegend=False,
        annotations=[dict(text=f"<b>{len(mods_filtered)}</b><br>Total",
                          x=0.5, y=0.5, font_size=18, font_color="#e6f1ff", showarrow=False)],
    )
    style_chart(fig_sev, 380)
    st.plotly_chart(fig_sev, use_container_width=True)

    # Total financial impact
    total_rev_mod = mods[mods["Line Item"].str.contains("Total Revenue", case=False, na=False)]["Annual Variance $"].sum()
    total_exp_mod = mods[mods["Line Item"].str.contains("Total Expense", case=False, na=False)]["Annual Variance $"].sum()
    net_mod = mods[mods["Line Item"].str.contains("Net Budget Impact", case=False, na=False)]["Annual Variance $"].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Revenue Modifications (Annual)", f"${total_rev_mod:+,.0f}")
    with col2:
        st.metric("Expense Modifications (Annual)", f"${total_exp_mod:+,.0f}")
    with col3:
        st.metric("Net Impact on Board's Budget", f"${net_mod:+,.0f}",
                  delta="Unfavorable" if net_mod < 0 else "Favorable",
                  delta_color="inverse" if net_mod < 0 else "normal")

# ── Board Demands ─────────────────────────────────────────────────────────
st.markdown("---")
st.header("Board Demands — What NSIA Needs From CSCG")
st.caption("Action items the board has formally requested from CSCG, with current status.")
st.markdown(
    "Specific documents, reports, and actions the board should require from the management company. "
    "Status is auto-detected from dashboard data where possible."
)

demands = compute_board_demands()
n_green = len(demands[demands["Status"] == "GREEN"])
n_yellow = len(demands[demands["Status"] == "YELLOW"])
n_red = len(demands[demands["Status"] == "RED"])

# Summary KPIs
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Demands Met", f"{n_green} / {len(demands)}")
with col2:
    st.metric("Outstanding", n_red)
with col3:
    st.metric("Needs Verification", n_yellow)

# Compliance progress bar
fig_prog = go.Figure()
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_green],
    name=f"Met ({n_green})",
    orientation="h",
    marker=dict(color="#00d084"),
    text=f"{n_green}" if n_green > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Met: {n_green}<extra></extra>",
))
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_yellow],
    name=f"Verify ({n_yellow})",
    orientation="h",
    marker=dict(color="#fcb900"),
    text=f"{n_yellow}" if n_yellow > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Needs Verification: {n_yellow}<extra></extra>",
))
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_red],
    name=f"Outstanding ({n_red})",
    orientation="h",
    marker=dict(color="#eb144c"),
    text=f"{n_red}" if n_red > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Outstanding: {n_red}<extra></extra>",
))
fig_prog.update_layout(
    barmode="stack",
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                font=dict(color="#a8b2d1")),
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
)
style_chart(fig_prog, 120)
st.plotly_chart(fig_prog, use_container_width=True)

# Demand table as styled HTML
status_colors = {"GREEN": "#00d084", "YELLOW": "#fcb900", "RED": "#eb144c"}

html_rows = ""
for _, row in demands.iterrows():
    color = status_colors.get(row["Status"], "#eb144c")
    pill = (f'<span style="background:{color}33;color:{color};padding:2px 10px;'
            f'border-radius:10px;font-weight:bold;font-size:0.85rem;">{row["Status"]}</span>')
    html_rows += (
        f'<tr style="border-bottom:1px solid rgba(168,178,209,0.15);">'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.85rem;">{row["Category"]}</td>'
        f'<td style="padding:8px 12px;color:#e6f1ff;">{row["Demand"]}</td>'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.85rem;">{row["Frequency"]}</td>'
        f'<td style="padding:8px 12px;text-align:center;">{pill}</td>'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.8rem;">{row["Evidence"]}</td>'
        f'</tr>'
    )

html_table = f'''
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;background:rgba(10,25,47,0.5);border-radius:8px;">
<thead>
<tr style="border-bottom:2px solid rgba(168,178,209,0.3);">
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Category</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Demand</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Frequency</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Status</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Evidence</th>
</tr>
</thead>
<tbody>
{html_rows}
</tbody>
</table>
</div>
'''
st.markdown(html_table, unsafe_allow_html=True)

# ── AI Assessment ─────────────────────────────────────────────────────────
if ANTHROPIC_AVAILABLE and get_api_key():
    st.markdown("")
    if st.button("🤖 AI Assessment — Analyze CSCG Performance", type="primary", use_container_width=True):
        # Build scorecard data for the agent
        scorecard_summary = "NSIA CSCG Contract Scorecard — Current Data\n\n"
        scorecard_summary += "=== CONTRACT COMPLIANCE ===\n"
        scorecard_summary += scorecard.to_csv(index=False)
        scorecard_summary += f"\n\nCompliance Rate: {compliance_pct:.0f}%\n"
        scorecard_summary += f"Compliant: {compliant} | Auto-Pay: {auto_pay} | Minor Variance: {minor} | Non-Compliant: {non_compliant}\n"
        scorecard_summary += f"\n=== CSCG PAYMENT BREAKDOWN (6 months) ===\n"
        scorecard_summary += cscg.to_csv(index=False)
        scorecard_summary += f"\nTotal CSCG Payments: ${total_cscg:,.0f}\n"
        scorecard_summary += f"Disclosed (Mgmt Fee): ${mgmt_fee:,.0f}\n"
        scorecard_summary += f"Undisclosed (Auto-Pay): ${undisclosed:,.0f} ({pct_undisclosed:.0f}%)\n"
        if not mods_filtered.empty:
            scorecard_summary += f"\n=== UNAUTHORIZED BUDGET MODIFICATIONS ===\n"
            scorecard_summary += mods_filtered.to_csv(index=False)

        # Add Board Demands summary
        scorecard_summary += f"\n=== BOARD DEMANDS STATUS ===\n"
        scorecard_summary += f"Met: {n_green}/15 | Needs Verification: {n_yellow} | Outstanding: {n_red}\n"
        scorecard_summary += demands.to_csv(index=False)

        with st.spinner("Running Management Company Performance Scorer analysis..."):
            result = analyze_document(
                agent_id="mgmt_scorer",
                document_content=scorecard_summary,
                filename="cscg_scorecard_current.csv",
                additional_context="Evaluate CSCG management company performance against contract terms. "
                                   "Score their compliance, flag governance concerns, and recommend "
                                   "specific board actions for the next board meeting.",
            )
        if result:
            st.markdown("---")
            st.markdown("### 🤖 AI Assessment")
            red_flags = result.count("🔴")
            yellow_flags = result.count("🟡")
            if red_flags > 0:
                st.error(f"**{red_flags} critical item(s)** require board attention")
            if yellow_flags > 0:
                st.warning(f"**{yellow_flags} caution item(s)** flagged for review")
            st.markdown(result)
            st.download_button(
                label="📥 Download AI Assessment",
                data=result,
                file_name="nsia_cscg_ai_assessment.md",
                mime="text/markdown",
            )
    st.markdown("")

# ── Governance Recommendations ────────────────────────────────────────────
st.markdown("---")
st.header("Governance Recommendations")

st.markdown("""
| # | Recommendation | Priority | Status |
|---|---------------|----------|--------|
| 1 | **Require board vote for any budget line change >$2,500** | HIGH | Not in place |
| 2 | **Monthly CSCG payment reconciliation** — itemized report of all payroll and expense reimbursements | HIGH | Not in place |
| 3 | **Quarterly contract compliance review** — verify all payments match agreement terms | MEDIUM | Not in place |
| 4 | **Annual management fee benchmark** — compare $42K fee to market rates for similar facilities | MEDIUM | Not in place |
| 5 | **Form 990 disclosure** — Part VI Line 3 should report management delegation to CSCG | HIGH | Verify |
| 6 | **Separate bank account visibility** — board should have read-only access to operating account | HIGH | Not in place |
| 7 | **Auto-pay cap** — set maximum monthly auto-pay amount requiring board pre-approval above threshold | MEDIUM | Not in place |
| 8 | **Budget amendment policy** — formal written process for modifying approved budget mid-year | HIGH | Not in place |

---
*These recommendations are based on the analysis of actual financial data and the CSCG management agreement.
Implementing even items 1, 2, and 8 would significantly improve board oversight.*
""")

# ── Source Documents ───────────────────────────────────────────────────────
st.markdown("---")
st.header("Source Documents (PDF-Extracted)")
st.caption("Financial data extracted from CSCG budget submissions and periodic reports.")

_docs = load_cscg_budget_submissions()
if _docs.empty:
    st.info(
        "No extracted budget submission data found. "
        "Run PDF extraction to populate this section."
    )
else:
    # Budget baseline: mean revenue/expense across all budget-type rows
    _has_ba_col = "is_budget_or_actual" in _docs.columns
    _budget_mask = _docs["is_budget_or_actual"].str.lower().eq("budget") if _has_ba_col else pd.Series(False, index=_docs.index)
    _budget_rows = _docs[_budget_mask]
    _budget_rev = (
        _budget_rows["revenue_total"].dropna().mean()
        if not _budget_rows.empty and "revenue_total" in _budget_rows.columns
        else None
    )
    _budget_exp = (
        _budget_rows["expense_total"].dropna().mean()
        if not _budget_rows.empty and "expense_total" in _budget_rows.columns
        else None
    )

    def _pill(label, color):
        return (
            f'<span style="background:{color}33;color:{color};padding:2px 10px;'
            f'border-radius:10px;font-weight:bold;font-size:0.85rem;">{label}</span>'
        )

    def _variance_pill(actual, budget, is_revenue=True):
        """Return a colored pill showing % variance vs budget, or '' if not computable."""
        if budget is None or not pd.notna(actual) or not pd.notna(budget) or budget == 0:
            return ""
        pct = (actual - budget) / abs(budget) * 100
        if is_revenue:
            color = "#00d084" if pct >= -5 else ("#fcb900" if pct >= -15 else "#eb144c")
        else:
            color = "#00d084" if pct <= 5 else ("#fcb900" if pct <= 15 else "#eb144c")
        return _pill(f"{pct:+.1f}%", color)

    # ── Summary table ─────────────────────────────────────────────────────
    _rows_html = ""
    for _, _d in _docs.iterrows():
        _file = str(_d.get("_source_file") or "Unknown")
        _dtype = str(_d.get("document_type") or "—")

        _ps, _pe = _d.get("period_start"), _d.get("period_end")
        _period = (
            f"{_ps.strftime('%b %Y')} \u2013 {_pe.strftime('%b %Y')}"
            if pd.notna(_ps) and pd.notna(_pe)
            else (_ps.strftime("%b %Y") if pd.notna(_ps) else "—")
        )

        _ba_raw = str(_d.get("is_budget_or_actual") or "—")
        _is_actual = _ba_raw.lower() == "actual"
        _ba_color = "#0984e3" if _is_actual else "#6c5ce7"
        _ba_cell = _pill(_ba_raw.capitalize(), _ba_color)

        _net = _d.get("net_income")
        _net_str = f"${_net:,.0f}" if pd.notna(_net) else "—"
        _net_color = "#00d084" if (pd.notna(_net) and _net >= 0) else "#eb144c"

        _conf = _d.get("extraction_confidence")
        _conf_map = {"high": "High", "medium": "Medium", "low": "Low"}
        _conf_str = _conf_map.get(str(_conf).lower(), str(_conf)) if pd.notna(_conf) else "—"
        _conf_color = (
            "#00d084" if _conf_str == "High"
            else ("#fcb900" if _conf_str == "Medium" else "#eb144c")
        )

        _rev_pill = _variance_pill(_d.get("revenue_total"), _budget_rev, is_revenue=True) if _is_actual else ""
        _exp_pill = _variance_pill(_d.get("expense_total"), _budget_exp, is_revenue=False) if _is_actual else ""

        _rows_html += (
            f'<tr style="border-bottom:1px solid rgba(168,178,209,0.15);">'
            f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.8rem;">{_file}</td>'
            f'<td style="padding:8px 12px;color:#e6f1ff;">{_dtype}</td>'
            f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.85rem;">{_period}</td>'
            f'<td style="padding:8px 12px;text-align:center;">{_ba_cell}</td>'
            f'<td style="padding:8px 12px;color:{_net_color};font-weight:600;">{_net_str}</td>'
            f'<td style="padding:8px 12px;text-align:center;">{_rev_pill or "—"}</td>'
            f'<td style="padding:8px 12px;text-align:center;">{_exp_pill or "—"}</td>'
            f'<td style="padding:8px 12px;color:{_conf_color};text-align:center;">{_conf_str}</td>'
            f'</tr>'
        )

    st.markdown(
        f'''
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;background:rgba(10,25,47,0.5);border-radius:8px;">
<thead>
<tr style="border-bottom:2px solid rgba(168,178,209,0.3);">
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Source File</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Type</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Period</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Budget / Actual</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Net Income</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Revenue vs Budget</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Expense vs Budget</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Confidence</th>
</tr>
</thead>
<tbody>
{_rows_html}
</tbody>
</table>
</div>
''',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Per-document line-item expanders ───────────────────────────────────
    st.markdown("#### Document Detail")

    _all_rev_cols = [c for c in _docs.columns if c.startswith("revenue_")]
    _all_exp_cols = [c for c in _docs.columns if c.startswith("expense_")]

    def _line_items_html(items, accent_color):
        if not items:
            return '<p style="color:#a8b2d1;font-size:0.85rem;">No data extracted</p>'
        html = ""
        for _lbl, _val in items:
            _is_total = "Total" in _lbl
            _vc = accent_color if _is_total else "#e6f1ff"
            _fw = "bold" if _is_total else "normal"
            html += (
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:4px 0;border-bottom:1px solid rgba(168,178,209,0.1);">'
                f'<span style="color:#a8b2d1;font-size:0.85rem;">{_lbl}</span>'
                f'<span style="color:{_vc};font-weight:{_fw};font-size:0.85rem;">${_val:,.0f}</span>'
                f'</div>'
            )
        return html

    for _i, (_, _d) in enumerate(_docs.iterrows()):
        _file = str(_d.get("_source_file") or f"Document {_i + 1}")
        _dtype = str(_d.get("document_type") or "")
        _ba = str(_d.get("is_budget_or_actual") or "").capitalize()
        _exp_label = "  |  ".join(p for p in [_file, _dtype, _ba] if p)

        with st.expander(_exp_label, expanded=False):
            _rev_data = [
                (c.replace("revenue_", "").replace("_", " ").title(), _d[c])
                for c in _all_rev_cols
                if c in _d.index and pd.notna(_d[c])
            ]
            _exp_data = [
                (c.replace("expense_", "").replace("_", " ").title(), _d[c])
                for c in _all_exp_cols
                if c in _d.index and pd.notna(_d[c])
            ]

            _col_l, _col_r = st.columns(2)
            with _col_l:
                st.markdown(
                    '<p style="color:#64ffda;font-weight:700;font-size:0.9rem;margin-bottom:8px;">Revenue</p>'
                    + _line_items_html(_rev_data, "#64ffda"),
                    unsafe_allow_html=True,
                )
            with _col_r:
                st.markdown(
                    '<p style="color:#eb144c;font-weight:700;font-size:0.9rem;margin-bottom:8px;">Expenses</p>'
                    + _line_items_html(_exp_data, "#eb144c"),
                    unsafe_allow_html=True,
                )

            _net = _d.get("net_income")
            if pd.notna(_net):
                _nc = "#00d084" if _net >= 0 else "#eb144c"
                st.markdown(
                    f'<div style="margin-top:12px;padding:10px 14px;'
                    f'background:rgba(10,25,47,0.5);border-radius:8px;'
                    f'display:flex;justify-content:space-between;">'
                    f'<span style="color:#e6f1ff;font-weight:700;">Net Income</span>'
                    f'<span style="color:{_nc};font-weight:700;font-size:1.1rem;">${_net:,.0f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

from utils import ask_about_this
ask_about_this("CSCG Scorecard")
