"""
Page 5: Variance Alerts
Auto-flags line items where CSCG budget deviates from board-approved proposal.
Stoplight system: RED / YELLOW / GREEN with action items view.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import analyze_document, get_api_key, ANTHROPIC_AVAILABLE
from utils.theme import CHART_BG, GRID_COLOR, FONT_COLOR, TITLE_COLOR, style_chart, inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Variance Alerts | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

import os
from datetime import date as _date, timedelta as _timedelta

st.title("Variance Alerts")
st.caption("Automated monitoring: CSCG operational budget vs. board-approved proposal")

# ── Board Action Item Alerts ─────────────────────────────────────────────
try:
    _board_actions_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "board_actions.xlsx")
    if os.path.exists(_board_actions_path):
        _ba_actions = pd.read_excel(_board_actions_path, sheet_name="Action Items", dtype={"id": str})
        if not _ba_actions.empty and "due_date" in _ba_actions.columns:
            _ba_actions["due_date"] = pd.to_datetime(_ba_actions["due_date"]).dt.date
            _today = _date.today()
            _open = _ba_actions[_ba_actions["status"].isin(["Open", "In Progress"])]
            _overdue = _open[_open["due_date"] < _today]
            _due_soon = _open[(_open["due_date"] >= _today) & (_open["due_date"] <= _today + _timedelta(days=7))]

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

from utils.data_loader import compute_variance_alerts

# ── Controls ──────────────────────────────────────────────────────────────
st.sidebar.markdown("### Threshold Presets")
preset_col1, preset_col2, preset_col3 = st.sidebar.columns(3)
if "threshold" not in st.session_state:
    st.session_state.threshold = 5
with preset_col1:
    if st.button("Tight\n3%", use_container_width=True):
        st.session_state.threshold = 3
with preset_col2:
    if st.button("Standard\n5%", use_container_width=True):
        st.session_state.threshold = 5
with preset_col3:
    if st.button("Loose\n10%", use_container_width=True):
        st.session_state.threshold = 10

threshold = st.sidebar.slider("Variance threshold (%)", 1, 25, st.session_state.threshold, 1,
                               help="Flag line items deviating more than this %") / 100

alerts = compute_variance_alerts(threshold_pct=threshold)

# ── Summary metrics ───────────────────────────────────────────────────────
red_count = len(alerts[alerts["Severity"] == "RED"])
yellow_count = len(alerts[alerts["Severity"] == "YELLOW"])
green_count = len(alerts[alerts["Severity"] == "GREEN"])
total_items = len(alerts)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Line Items", total_items)
with col2:
    st.metric("RED Alerts", red_count)
with col3:
    st.metric("YELLOW Alerts", yellow_count)
with col4:
    st.metric("GREEN (OK)", green_count)

# ── Stoplight summary chart ──────────────────────────────────────────────
fig_stop = go.Figure()
fig_stop.add_trace(go.Bar(
    x=["RED"], y=[red_count], name="RED",
    marker=dict(color="#eb144c", line=dict(width=1.5, color="rgba(255,255,255,0.3)")),
    text=[red_count], textposition="inside",
    textfont=dict(color="#fff", size=24, family="Arial Black"),
    hovertemplate="<b>RED Alerts</b><br>%{y} line items<br>>50% variance or >$10K<extra></extra>",
))
fig_stop.add_trace(go.Bar(
    x=["YELLOW"], y=[yellow_count], name="YELLOW",
    marker=dict(color="#fcb900", line=dict(width=1.5, color="rgba(255,255,255,0.3)")),
    text=[yellow_count], textposition="inside",
    textfont=dict(color="#1a1a2e", size=24, family="Arial Black"),
    hovertemplate=f"<b>YELLOW Alerts</b><br>%{{y}} line items<br>>{threshold:.0%} variance or >$2K<extra></extra>",
))
fig_stop.add_trace(go.Bar(
    x=["GREEN"], y=[green_count], name="GREEN",
    marker=dict(color="#00d084", line=dict(width=1.5, color="rgba(255,255,255,0.3)")),
    text=[green_count], textposition="inside",
    textfont=dict(color="#1a1a2e", size=24, family="Arial Black"),
    hovertemplate="<b>GREEN</b><br>%{y} line items<br>Within tolerance<extra></extra>",
))
fig_stop.update_layout(
    title="Budget Variance Stoplight Summary",
    showlegend=False,
    bargap=0.35,
    yaxis_title="Number of Line Items",
)
style_chart(fig_stop, 350)
st.plotly_chart(fig_stop, use_container_width=True)
st.caption("Adjust the threshold in the sidebar to change alert sensitivity")

# ── RED Alerts — Requires Immediate Board Attention ───────────────────────
st.markdown("---")
st.header("RED Alerts — Requires Board Attention")
st.markdown("Line items with **>50% variance** or **>$10,000 deviation** from approved proposal.")

red_alerts = alerts[alerts["Severity"] == "RED"].copy()
if red_alerts.empty:
    st.success("No RED alerts at current threshold.")
else:
    # Horizontal bar chart of RED items
    red_sorted = red_alerts.sort_values("Variance $", key=lambda x: x.abs(), ascending=True)
    colors = ["#ff6b6b" if v and v > 0 else "#ff4757" for v in red_sorted["Variance $"]]
    fig_red = go.Figure(go.Bar(
        y=red_sorted["Category"] + " — " + red_sorted["Line Item"],
        x=red_sorted["Variance $"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:+,.0f}" if pd.notna(v) else "N/A" for v in red_sorted["Variance $"]],
        textposition="outside",
        textfont=dict(color="#ff6b6b", size=12, family="Arial Black"),
        hovertemplate="<b>%{y}</b><br>Variance: $%{x:,.0f}<extra></extra>",
    ))
    fig_red.add_vline(x=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    fig_red.update_layout(title="RED Alert Items — YTD Variance ($)", xaxis_title="Variance ($)")
    style_chart(fig_red, max(350, len(red_sorted) * 40 + 100))
    st.plotly_chart(fig_red, use_container_width=True)

    # Detailed table
    def red_style(val):
        return "background-color: #eb144c22; color: #ff6b6b; font-weight: bold"

    display_red = red_alerts[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                               "Variance $", "Variance %", "Assessment"]].copy()
    st.dataframe(
        display_red.style.map(lambda _: red_style(_), subset=["Variance $"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Proposal YTD": st.column_config.NumberColumn(format="$%,.0f"),
            "CSCG YTD": st.column_config.NumberColumn(format="$%,.0f"),
            "Variance $": st.column_config.NumberColumn(format="$%,.0f"),
            "Variance %": st.column_config.NumberColumn(format="%.1%%"),
        },
    )

# ── AI Assessment ─────────────────────────────────────────────────────────
if ANTHROPIC_AVAILABLE and get_api_key():
    non_green = alerts[alerts["Severity"] != "GREEN"]
    if not non_green.empty:
        st.markdown("")
        if st.button("🤖 AI Assessment — Analyze Variance Alerts", type="primary", use_container_width=True):
            # Build a summary of RED and YELLOW alerts for the agent
            alert_summary = "NSIA Variance Alerts — Current Data\n\n"
            alert_summary += f"Threshold: {threshold:.0%} | RED: {red_count} | YELLOW: {yellow_count} | GREEN: {green_count}\n\n"
            alert_summary += "=== RED & YELLOW ALERTS ===\n"
            alert_summary += non_green[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                                         "Variance $", "Variance %", "Severity", "Assessment"]].to_csv(index=False)
            alert_summary += f"\n\nAggregate Impact:\n"
            alert_summary += f"- Total Favorable Variances: ${non_green[non_green['Variance $'] > 0]['Variance $'].sum():+,.0f}\n"
            alert_summary += f"- Total Unfavorable Variances: ${non_green[non_green['Variance $'] < 0]['Variance $'].sum():+,.0f}\n"
            alert_summary += f"- Net Budget Impact (YTD): ${non_green['Variance $'].sum():+,.0f}\n"

            with st.spinner("Running Alert Monitor analysis..."):
                result = analyze_document(
                    agent_id="alert_monitor",
                    document_content=alert_summary,
                    filename="variance_alerts_current.csv",
                    additional_context="Analyze these budget variance alerts for the NSIA board. "
                                       "Identify the most critical items, recommend board actions, "
                                       "and flag any patterns across the variances.",
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
                    file_name="nsia_variance_ai_assessment.md",
                    mime="text/markdown",
                )
        st.markdown("")

# ── YELLOW Alerts — Monitor Closely ──────────────────────────────────────
st.markdown("---")
st.header("YELLOW Alerts — Monitor Closely")
st.markdown(f"Line items with **>{threshold:.0%} variance** or **>$2,000 deviation**.")

yellow_alerts = alerts[alerts["Severity"] == "YELLOW"].copy()
if yellow_alerts.empty:
    st.success("No YELLOW alerts at current threshold.")
else:
    yellow_sorted = yellow_alerts.sort_values("Variance $", key=lambda x: x.abs(), ascending=True)
    fig_yellow = go.Figure(go.Bar(
        y=yellow_sorted["Category"] + " — " + yellow_sorted["Line Item"],
        x=yellow_sorted["Variance $"],
        orientation="h",
        marker=dict(color="#fcb900", line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:+,.0f}" if pd.notna(v) else "N/A" for v in yellow_sorted["Variance $"]],
        textposition="outside",
        textfont=dict(color="#fcb900", size=11),
        hovertemplate="<b>%{y}</b><br>Variance: $%{x:,.0f}<extra></extra>",
    ))
    fig_yellow.add_vline(x=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    fig_yellow.update_layout(title="YELLOW Alert Items — YTD Variance ($)", xaxis_title="Variance ($)")
    style_chart(fig_yellow, max(350, len(yellow_sorted) * 35 + 100))
    st.plotly_chart(fig_yellow, use_container_width=True)

    display_yellow = yellow_alerts[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                                     "Variance $", "Variance %"]].copy()
    st.dataframe(
        display_yellow,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Proposal YTD": st.column_config.NumberColumn(format="$%,.0f"),
            "CSCG YTD": st.column_config.NumberColumn(format="$%,.0f"),
            "Variance $": st.column_config.NumberColumn(format="$%,.0f"),
            "Variance %": st.column_config.NumberColumn(format="%.1%%"),
        },
    )

# ── GREEN Items — What's Working ──────────────────────────────────────────
st.markdown("---")
st.header("GREEN Items — What's Working Well")

green_alerts = alerts[alerts["Severity"] == "GREEN"].copy()
if green_alerts.empty:
    st.info("No GREEN items at current threshold.")
else:
    # Show top 5 closest-to-budget items as confidence builders
    green_alerts["Abs Variance"] = green_alerts["Variance $"].abs()
    top_green = green_alerts.nsmallest(5, "Abs Variance")

    st.markdown(f"**{green_count} line items** are within tolerance. Here are the top performers:")

    for _, row in top_green.iterrows():
        var_pct = row["Variance %"] * 100 if abs(row["Variance %"]) < 1 else row["Variance %"]
        st.markdown(
            f'<div style="padding:8px 14px;margin:4px 0;border-left:3px solid #00d084;'
            f'background:rgba(0,208,132,0.08);border-radius:4px;">'
            f'<b style="color:#e6f1ff;">{row["Line Item"]}</b> '
            f'<span style="color:#a8b2d1;">({row["Category"]})</span> &nbsp; '
            f'<span style="color:#00d084;font-weight:bold;">${row["Variance $"]:+,.0f} ({var_pct:+.1f}%)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.expander(f"All {green_count} GREEN items"):
        st.dataframe(
            green_alerts[["Category", "Line Item", "Proposal YTD", "CSCG YTD",
                           "Variance $", "Variance %"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Proposal YTD": st.column_config.NumberColumn(format="$%,.0f"),
                "CSCG YTD": st.column_config.NumberColumn(format="$%,.0f"),
                "Variance $": st.column_config.NumberColumn(format="$%,.0f"),
                "Variance %": st.column_config.NumberColumn(format="%.1%%"),
            },
        )

# ── Aggregate Impact ──────────────────────────────────────────────────────
st.markdown("---")
st.header("Aggregate Variance Impact")

non_green = alerts[alerts["Severity"] != "GREEN"].copy()
total_positive = non_green[non_green["Variance $"] > 0]["Variance $"].sum()
total_negative = non_green[non_green["Variance $"] < 0]["Variance $"].sum()
net_impact = non_green["Variance $"].sum()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Favorable Variances", f"${total_positive:+,.0f}",
              delta="Higher than proposal", delta_color="off")
with col2:
    st.metric("Total Unfavorable Variances", f"${total_negative:+,.0f}",
              delta="Lower than proposal", delta_color="off")
with col3:
    st.metric("Net Budget Impact (YTD)", f"${net_impact:+,.0f}",
              delta="Positive" if net_impact > 0 else "Negative",
              delta_color="normal" if net_impact > 0 else "inverse")

st.markdown("---")

st.markdown(
    """**How to use this page:**
- Adjust the **variance threshold** in the sidebar to change sensitivity
- **RED** items require immediate board discussion and possible budget amendment
- **YELLOW** items should be monitored monthly for trend changes
- **GREEN** items are within normal tolerance
- Ask CSCG to provide written justification for all RED and YELLOW items"""
)

from utils import ask_about_this
ask_about_this("Variance Alerts")
