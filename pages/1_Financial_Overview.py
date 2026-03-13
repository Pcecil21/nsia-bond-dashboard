"""
Page 1: Financial Overview
Budget vs Actual variance analysis and unauthorized modifications.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Financial Overview | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Financial Overview")
st.caption("FY2026 Budget Reconciliation — Approved Proposal vs. CSCG Operational Budget")

from utils.data_loader import (
    load_revenue_reconciliation,
    load_expense_reconciliation,
    load_unauthorized_modifications,
    load_expense_flow_summary,
)

# ── Summary KPIs ─────────────────────────────────────────────────────────
rev = load_revenue_reconciliation()
exp = load_expense_reconciliation()

rev_items = rev[~rev["Line Item"].str.startswith("Total")]
exp_items = exp[~exp["Line Item"].str.startswith("Total")]

rev_ytd_var = rev_items["YTD Variance $"].sum()
exp_ytd_var = exp_items["YTD Variance $"].sum()
rev_jan_var = rev_items["Jan Variance $"].sum()
exp_jan_var = exp_items["Jan Variance $"].sum()
net_var = rev_ytd_var - exp_ytd_var

k1, k2, k3, k4 = st.columns(4)
k1.metric("Revenue Variance (YTD)", f"${rev_ytd_var:+,.0f}",
          delta=f"Jan: ${rev_jan_var:+,.0f}", delta_color="normal" if rev_jan_var >= 0 else "inverse")
k2.metric("Expense Variance (YTD)", f"${exp_ytd_var:+,.0f}",
          delta=f"Jan: ${exp_jan_var:+,.0f}", delta_color="inverse" if exp_jan_var > 0 else "normal")
k3.metric("Net Budget Impact", f"${net_var:+,.0f}",
          delta="Favorable" if net_var >= 0 else "Unfavorable",
          delta_color="normal" if net_var >= 0 else "inverse")
k4.metric("Items w/ Variance", f"{len(rev_items[rev_items['YTD Variance $'].abs() > 0]) + len(exp_items[exp_items['YTD Variance $'].abs() > 0])}",
          delta=f"of {len(rev_items) + len(exp_items)} total")

st.markdown("---")

# ── Revenue Variance ─────────────────────────────────────────────────────
st.header("Revenue — Budget vs. CSCG Variance")

display_cols = ["Line Item", "Proposal Jan Budget", "CSCG Jan Budget",
                "Jan Variance $", "Proposal YTD Budget", "CSCG YTD Budget",
                "YTD Variance $"]

# Add trend indicator column
rev_display = rev.copy()
def trend_arrow(row):
    jan = row.get("Jan Variance $", 0)
    ytd = row.get("YTD Variance $", 0)
    if pd.isna(jan) or pd.isna(ytd):
        return ""
    # Compare January rate to YTD average rate (7 months)
    monthly_avg = ytd / 7 if ytd != 0 else 0
    if abs(jan) < 1 and abs(monthly_avg) < 1:
        return ""
    if jan > monthly_avg * 1.1:
        return "Worsening" if jan > 0 else "Improving"
    elif jan < monthly_avg * 0.9:
        return "Improving" if jan > 0 else "Worsening"
    return "Stable"

rev_display["Trend"] = rev_display.apply(trend_arrow, axis=1)
display_cols_with_trend = display_cols + ["Trend"]

st.dataframe(
    rev_display[display_cols_with_trend],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Proposal Jan Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "CSCG Jan Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "Jan Variance $": st.column_config.NumberColumn(format="$%,.0f"),
        "Proposal YTD Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "CSCG YTD Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "YTD Variance $": st.column_config.NumberColumn(format="$%,.0f"),
    },
)

# Revenue YTD variance chart
rev_chart = rev_items.dropna(subset=["YTD Variance $"])
if not rev_chart.empty:
    colors = ["#00d084" if v >= 0 else "#eb144c" for v in rev_chart["YTD Variance $"]]
    fig_rev = go.Figure(go.Bar(
        x=rev_chart["Line Item"],
        y=rev_chart["YTD Variance $"],
        marker=dict(
            color=colors,
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
        ),
        text=[f"${v:+,.0f}" for v in rev_chart["YTD Variance $"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
        hovertemplate="<b>%{x}</b><br>Variance: $%{y:,.0f}<extra></extra>",
    ))
    fig_rev.update_layout(title="Revenue YTD Variance by Line Item (Proposal vs CSCG)",
                          xaxis_tickangle=-40, yaxis_title="Variance ($)")
    fig_rev.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    style_chart(fig_rev, 480)
    st.plotly_chart(fig_rev, use_container_width=True)

# ── Expense Variance ─────────────────────────────────────────────────────
st.header("Expenses — Budget vs. CSCG Variance")

exp = load_expense_reconciliation()
st.dataframe(
    exp[display_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Proposal Jan Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "CSCG Jan Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "Jan Variance $": st.column_config.NumberColumn(format="$%,.0f"),
        "Proposal YTD Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "CSCG YTD Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "YTD Variance $": st.column_config.NumberColumn(format="$%,.0f"),
    },
)

# Expense YTD variance chart — top movers
exp_chart = exp.dropna(subset=["YTD Variance $"])
exp_chart = exp_chart[~exp_chart["Line Item"].str.startswith("Total")]
exp_chart = exp_chart[exp_chart["YTD Variance $"].abs() > 0]
if not exp_chart.empty:
    exp_chart = exp_chart.sort_values("YTD Variance $", key=abs, ascending=True).tail(15)
    colors = ["#eb144c" if v > 0 else "#00d084" for v in exp_chart["YTD Variance $"]]
    fig_exp = go.Figure(go.Bar(
        y=exp_chart["Line Item"],
        x=exp_chart["YTD Variance $"],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=1, color="rgba(255,255,255,0.3)"),
        ),
        text=[f"${v:+,.0f}" for v in exp_chart["YTD Variance $"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
        hovertemplate="<b>%{y}</b><br>Variance: $%{x:,.0f}<extra></extra>",
    ))
    fig_exp.update_layout(title="Top Expense YTD Variances (Proposal vs CSCG)",
                          xaxis_title="Variance ($)")
    fig_exp.add_vline(x=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    style_chart(fig_exp, 550)
    st.plotly_chart(fig_exp, use_container_width=True)

# ── Unauthorized Modifications ────────────────────────────────────────────
st.header("Unauthorized Budget Modifications")
st.caption("Line items where CSCG operational budget differs from board-approved FY2026 Budget Proposal")

mods = load_unauthorized_modifications()

# Severity bar chart
mods_chart = mods.dropna(subset=["Annual Variance $", "Severity"])
mods_chart = mods_chart[~mods_chart["Line Item"].str.contains("AGGREGATE|Total|Net Budget", case=False, na=False)]
if not mods_chart.empty:
    severity_colors = {"HIGH": "#eb144c", "CRITICAL": "#ff006e", "MEDIUM": "#fcb900", "LOW": "#00d084"}
    mods_chart = mods_chart.sort_values("Annual Variance $", key=abs, ascending=True)
    fig_mods = go.Figure(go.Bar(
        y=mods_chart["Line Item"],
        x=mods_chart["Annual Variance $"],
        orientation="h",
        marker=dict(
            color=[severity_colors.get(s, "#abb8c3") for s in mods_chart["Severity"]],
            line=dict(width=1, color="rgba(255,255,255,0.2)"),
        ),
        text=[f"${v:+,.0f}" for v in mods_chart["Annual Variance $"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
        hovertemplate="<b>%{y}</b><br>Severity: " +
                      mods_chart["Severity"].values.astype(str) +
                      "<br>Variance: $%{x:,.0f}<extra></extra>",
    ))
    fig_mods.update_layout(title="Unauthorized Modifications by Annual Variance",
                           xaxis_title="Annual Variance ($)")
    fig_mods.add_vline(x=0, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    style_chart(fig_mods, 550)

    # Add severity legend manually
    for sev, color in severity_colors.items():
        fig_mods.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=sev, showlegend=True,
        ))
    fig_mods.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(color=FONT_COLOR),
    ))
    st.plotly_chart(fig_mods, use_container_width=True)

# Severity table
def severity_color(val):
    colors = {"HIGH": "background-color: #eb144c33; color: #ff6b6b",
              "CRITICAL": "background-color: #ff006e33; color: #ff69b4",
              "MEDIUM": "background-color: #fcb90033; color: #fcb900",
              "LOW": "background-color: #00d08433; color: #7bdcb5"}
    return colors.get(val, "")

styled = mods.style.map(severity_color, subset=["Severity"])
st.dataframe(
    styled,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Proposal Annual": st.column_config.NumberColumn(format="$%,.0f"),
        "CSCG Annual (Implied)": st.column_config.NumberColumn(format="$%,.0f"),
        "Annual Variance $": st.column_config.NumberColumn(format="$%,.0f"),
    },
)

# ── Expense Approval Breakdown ────────────────────────────────────────────
st.header("Expense Approval Breakdown")
st.caption("How NSIA expenses are approved (July-December 2025)")

summary = load_expense_flow_summary()

col1, col2 = st.columns([1, 1])

with col1:
    if not summary.empty and "% of Total" in summary.columns:
        fig_donut = go.Figure(go.Pie(
            labels=summary["Approval Method"],
            values=summary["% of Total"],
            hole=0.5,
            marker=dict(
                colors=["#00b894", "#fdcb6e", "#6c5ce7", "#b2bec3"],
                line=dict(color="#0a192f", width=2.5),
            ),
            textinfo="percent+label",
            textfont=dict(size=12, color="#e6f1ff"),
            hovertemplate="<b>%{label}</b><br>%{percent:.1%}<extra></extra>",
        ))
        fig_donut.update_layout(
            title=dict(text="Expense Approval by Method", font=dict(size=16, color=TITLE_COLOR)),
            showlegend=False,
            annotations=[dict(text="<b>25.5%</b><br>Board-Approved",
                              x=0.5, y=0.5, font_size=14, font_color="#e6f1ff", showarrow=False)],
        )
        style_chart(fig_donut, 420)
        st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "YTD Amount": st.column_config.NumberColumn(format="$%,.0f"),
            "% of Total": st.column_config.NumberColumn(format="%.1%%"),
        },
    )
    st.markdown(
        """
        **Key takeaway:** Only **25.5%** of NSIA expenses require individual
        invoice approval by the Board President. The remaining 74.5% flows
        through CSCG auto-pay, fixed contracts, or other channels with
        limited board oversight.
        """
    )
