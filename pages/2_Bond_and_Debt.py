"""
Page 2: Bond & Debt Obligations
Hidden cash flows, debt service, fixed obligations, and scoreboard economics.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_period_label

st.set_page_config(page_title="Bond & Debt | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Bond & Debt Obligations")
st.caption("Cash flow items excluded from the board's primary Budget vs. Actuals report")

from utils.data_loader import (
    load_hidden_cash_flows,
    load_fixed_obligations,
    load_scoreboard_10yr,
    load_scoreboard_alternative,
)

# ── Hidden Cash Flows ─────────────────────────────────────────────────────
st.header("Hidden Cash Flows")
st.markdown(
    "These items impact NSIA's cash position but are **invisible** in the "
    "board's primary Budget vs. Actuals performance tracking report."
)

hidden = load_hidden_cash_flows()

col1, col2 = st.columns([2, 1])

with col1:
    st.dataframe(
        hidden,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Monthly Amount": st.column_config.NumberColumn(format="$%,.0f"),
            "Annual Impact": st.column_config.NumberColumn(format="$%,.0f"),
        },
    )

with col2:
    total_hidden = hidden["Annual Impact"].sum()
    st.metric("Total Annual Hidden Outflows", f"${total_hidden:,.0f}")
    st.markdown("**Per year** not visible in Budget vs. Actuals")

# Waterfall chart
st.subheader("Annual Debt Service Waterfall")
st.caption("Cumulative annual cash outflows not visible in the board's primary performance report")
hidden_sorted = hidden.sort_values("Annual Impact", ascending=False)
items = hidden_sorted["Item"].tolist()
values = hidden_sorted["Annual Impact"].tolist()

waterfall_colors = ["#ff6b6b", "#ee5a24", "#f0932b", "#ffbe76", "#6ab04c", "#22a6b3"]

fig_waterfall = go.Figure(go.Waterfall(
    name="Annual Impact",
    orientation="v",
    measure=["relative"] * len(items) + ["total"],
    x=items + ["Total"],
    y=values + [None],
    textposition="outside",
    text=[f"${v:,.0f}" if pd.notna(v) else "" for v in values] + [f"${total_hidden:,.0f}"],
    textfont=dict(color=FONT_COLOR, size=12, family="Arial Black"),
    connector={"line": {"color": "rgba(168,178,209,0.3)", "width": 1.5, "dash": "dot"}},
    increasing={"marker": {"color": "#ff6b6b",
                            "line": {"color": "rgba(255,255,255,0.3)", "width": 1}}},
    totals={"marker": {"color": "#6c5ce7",
                        "line": {"color": "rgba(255,255,255,0.3)", "width": 1}}},
))
fig_waterfall.update_layout(
    title="Hidden Cash Outflows — Annual Impact",
    yaxis_title="Dollars",
    showlegend=False,
    xaxis_tickangle=-25,
)
style_chart(fig_waterfall, 500)
st.plotly_chart(fig_waterfall, use_container_width=True)

st.markdown("---")

# ── Fixed Obligations ─────────────────────────────────────────────────────
st.header(f"Fixed Obligations (6 Months: {get_period_label(6)})")
st.caption("Contractual obligations from the Expense Flow Analysis")

fixed = load_fixed_obligations()
st.dataframe(
    fixed[["Expense Category", "YTD per Financials", "Approval Method", "Notes"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "YTD per Financials": st.column_config.NumberColumn("6-Month Amount", format="$%,.0f"),
    },
)

fixed_total = fixed["YTD per Financials"].sum()
st.metric("Total Fixed Obligations (6 months)", f"${fixed_total:,.0f}")

# Bar chart of fixed obligations
fixed_sorted = fixed.sort_values("YTD per Financials", ascending=True)
bar_colors = ["#00b894", "#00cec9", "#0984e3", "#6c5ce7", "#a29bfe", "#fd79a8", "#e17055"]
fig_fixed = go.Figure(go.Bar(
    y=fixed_sorted["Expense Category"],
    x=fixed_sorted["YTD per Financials"],
    orientation="h",
    marker=dict(
        color=bar_colors[:len(fixed_sorted)],
        line=dict(width=1, color="rgba(255,255,255,0.2)"),
    ),
    text=[f"${v:,.0f}" for v in fixed_sorted["YTD per Financials"]],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=12),
    hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
))
fig_fixed.update_layout(title="Fixed Obligations Breakdown (6-Month Period)",
                         xaxis_title="Dollars")
style_chart(fig_fixed, 420)
st.plotly_chart(fig_fixed, use_container_width=True)

st.markdown("---")

# ── Scoreboard Economics ──────────────────────────────────────────────────
st.header("Scoreboard Economics — 10-Year NPV Comparison")
st.markdown(
    "Comparing the **current ScoreVision deal** (lease with sponsorship revenue share) "
    "against a **cheaper purchase alternative**."
)

sb_current = load_scoreboard_10yr()
sb_alt = load_scoreboard_alternative()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Deal")
    current_ncf = sb_current[sb_current["Category"] == "Net Cash Flow (Current Deal)"]
    if not current_ncf.empty:
        total_current = current_ncf.iloc[0].get("10yr Total", None)
        st.metric("10-Year Net Cash Flow", f"${total_current:,.0f}" if pd.notna(total_current) else "N/A",
                  delta="Negative" if total_current and total_current < 0 else None,
                  delta_color="inverse")

    st.dataframe(
        sb_current,
        use_container_width=True,
        hide_index=True,
        column_config={col: st.column_config.NumberColumn(format="$%,.0f")
                       for col in sb_current.columns if col != "Category"},
    )

with col2:
    st.subheader("Cheaper Alternative")
    alt_ncf = sb_alt[sb_alt["Category"] == "Net Cash Flow (Cheaper Alt)"]
    if not alt_ncf.empty:
        total_alt = alt_ncf.iloc[0].get("10yr Total", None)
        st.metric("10-Year Net Cash Flow", f"${total_alt:,.0f}" if pd.notna(total_alt) else "N/A",
                  delta="Positive" if total_alt and total_alt > 0 else None,
                  delta_color="normal")

    st.dataframe(
        sb_alt,
        use_container_width=True,
        hide_index=True,
        column_config={col: st.column_config.NumberColumn(format="$%,.0f")
                       for col in sb_alt.columns if col != "Category"},
    )

st.markdown("")

# Comparison area chart
st.subheader("Net Cash Flow Comparison Over 10 Years")
st.caption("Year-by-year cash flow comparison showing cumulative impact of each deal structure")
current_vals = sb_current[sb_current["Category"] == "Net Cash Flow (Current Deal)"]
alt_vals = sb_alt[sb_alt["Category"] == "Net Cash Flow (Cheaper Alt)"]

if not current_vals.empty and not alt_vals.empty:
    years = list(range(1, 11))
    current_data = [current_vals.iloc[0].get(f"Year {y}", 0) for y in years]
    alt_data = [alt_vals.iloc[0].get(f"Year {y}", 0) for y in years]

    fig_compare = go.Figure()
    fig_compare.add_trace(go.Scatter(
        x=years, y=current_data, mode="lines+markers",
        name="Current Deal",
        line=dict(color="#eb144c", width=3),
        marker=dict(size=9, color="#eb144c", line=dict(width=2, color="#fff")),
        fill="tozeroy",
        fillcolor="rgba(235,20,76,0.15)",
        hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>Current Deal</extra>",
    ))
    fig_compare.add_trace(go.Scatter(
        x=years, y=alt_data, mode="lines+markers",
        name="Cheaper Alternative",
        line=dict(color="#00d084", width=3),
        marker=dict(size=9, color="#00d084", line=dict(width=2, color="#fff")),
        fill="tozeroy",
        fillcolor="rgba(0,208,132,0.15)",
        hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>Cheaper Alt</extra>",
    ))
    fig_compare.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.4)", line_width=1.5)
    fig_compare.update_layout(
        title="Annual Net Cash Flow: Current Deal vs. Cheaper Alternative",
        xaxis_title="Year", yaxis_title="Net Cash Flow ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    style_chart(fig_compare, 450)
    st.plotly_chart(fig_compare, use_container_width=True)

    diff = total_alt - total_current
    st.success(
        f"**Current deal** 10-year total: **${total_current:,.0f}** | "
        f"**Cheaper alternative** 10-year total: **${total_alt:,.0f}** | "
        f"**Savings: ${diff:,.0f}** in favor of the cheaper alternative"
    )

from utils import ask_about_this
ask_about_this("Bond and Debt")
