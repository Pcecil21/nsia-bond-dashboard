"""
Page 8: Multi-Year Trends
3-year revenue/expense trends, Form 990 highlights, and payroll benchmarking.
FY columns are detected dynamically from CSV headers.
"""
import re
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, style_chart, inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_current_month

st.set_page_config(page_title="Multi-Year Trends | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Multi-Year Trends")
st.caption("3-year revenue & expense analysis, Form 990 highlights, and payroll benchmarking")

from utils.data_loader import load_multiyear_revenue, load_payroll_benchmarks

st.markdown("---")

# ── Detect FY columns dynamically ────────────────────────────────────────
data = load_multiyear_revenue()
_fy_cols = sorted([c for c in data.columns if re.match(r'^FY\d{4}$', c)])
years = _fy_cols[-3:] if len(_fy_cols) >= 3 else _fy_cols  # last 3 FY columns

if not years:
    st.warning("No fiscal year columns found in multi-year data.")
    st.stop()

# Color palettes — cycle if more/fewer than 3
_REV_PALETTE = ["#8ed1fc", "#64ffda", "#fcb900", "#7bdcb5", "#f78da7"]
_EXP_PALETTE = ["#f78da7", "#eb144c", "#ff6900", "#fcb900", "#8ed1fc"]
year_colors = {yr: _REV_PALETTE[i % len(_REV_PALETTE)] for i, yr in enumerate(years)}
exp_colors = {yr: _EXP_PALETTE[i % len(_EXP_PALETTE)] for i, yr in enumerate(years)}

# ── Section 1: 3-Year Revenue ────────────────────────────────────────────
st.header(f"{len(years)}-Year Revenue Trend")

rev = data[data["Type"] == "Revenue"]
exp = data[data["Type"] == "Expense"]

# Revenue totals — dynamic per FY column
rev_totals = rev[rev["Category"] == "Total Revenue"]
fy_rev = {yr: rev_totals[yr].values[0] if len(rev_totals) > 0 and yr in rev_totals.columns else 0 for yr in years}

cols = st.columns(len(years))
for i, yr in enumerate(years):
    with cols[i]:
        if i == 0:
            st.metric(f"{yr} Revenue", f"${fy_rev[yr]:,.0f}")
        else:
            prev_yr = years[i - 1]
            delta = (fy_rev[yr] - fy_rev[prev_yr]) / fy_rev[prev_yr] * 100 if fy_rev[prev_yr] else 0
            st.metric(f"{yr} Revenue", f"${fy_rev[yr]:,.0f}", delta=f"{delta:+.1f}% YoY")

# Grouped bar: revenue categories across years
rev_categories = rev[rev["Category"] != "Total Revenue"]

fig_rev = go.Figure()
for yr in years:
    fig_rev.add_trace(go.Bar(
        x=rev_categories["Category"],
        y=rev_categories[yr],
        name=yr,
        marker=dict(color=year_colors[yr], line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:,.0f}" for v in rev_categories[yr]],
        textposition="outside",
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate="<b>%{x}</b><br>" + yr + ": $%{y:,.0f}<extra></extra>",
    ))
fig_rev.update_layout(
    title=f"Revenue by Category — {len(years)}-Year Comparison",
    barmode="group",
    xaxis_tickangle=-20,
    yaxis_title="Revenue ($)",
)
style_chart(fig_rev, 480)
st.plotly_chart(fig_rev, use_container_width=True)

# Stacked area: revenue composition
fig_area = go.Figure()
area_colors = ["#64ffda", "#f78da7", "#fcb900", "#7bdcb5", "#8ed1fc"]
for i, (_, row) in enumerate(rev_categories.iterrows()):
    fig_area.add_trace(go.Scatter(
        x=years,
        y=[row[yr] for yr in years],
        name=row["Category"],
        mode="lines",
        stackgroup="one",
        line=dict(width=0.5),
        fillcolor=area_colors[i % len(area_colors)],
        hovertemplate="<b>" + row["Category"] + "</b><br>%{x}: $%{y:,.0f}<extra></extra>",
    ))
fig_area.update_layout(
    title="Revenue Composition Shift (Stacked)",
    yaxis_title="Revenue ($)",
)
style_chart(fig_area, 420)
st.plotly_chart(fig_area, use_container_width=True)

# ── Section 2: 3-Year Expenses ──────────────────────────────────────────
st.markdown("---")
st.header(f"{len(years)}-Year Expense Trend")

exp_categories = exp[exp["Category"] != "Total Expenses"]

fig_exp = go.Figure()
for yr in years:
    fig_exp.add_trace(go.Bar(
        x=exp_categories["Category"],
        y=exp_categories[yr],
        name=yr,
        marker=dict(color=exp_colors[yr], line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:,.0f}" for v in exp_categories[yr]],
        textposition="outside",
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate="<b>%{x}</b><br>" + yr + ": $%{y:,.0f}<extra></extra>",
    ))
fig_exp.update_layout(
    title=f"Expenses by Category — {len(years)}-Year Comparison",
    barmode="group",
    xaxis_tickangle=-20,
    yaxis_title="Expenses ($)",
)
style_chart(fig_exp, 480)
st.plotly_chart(fig_exp, use_container_width=True)

# Revenue vs Expenses line chart
exp_totals = exp[exp["Category"] == "Total Expenses"]
fy_exp = {yr: exp_totals[yr].values[0] if len(exp_totals) > 0 and yr in exp_totals.columns else 0 for yr in years}

fig_gap = go.Figure()
fig_gap.add_trace(go.Scatter(
    x=years,
    y=[fy_rev[yr] for yr in years],
    name="Total Revenue",
    mode="lines+markers",
    line=dict(color="#64ffda", width=3),
    marker=dict(size=10),
    hovertemplate="Revenue: $%{y:,.0f}<extra></extra>",
))
fig_gap.add_trace(go.Scatter(
    x=years,
    y=[fy_exp[yr] for yr in years],
    name="Total Expenses",
    mode="lines+markers",
    line=dict(color="#eb144c", width=3),
    marker=dict(size=10),
    hovertemplate="Expenses: $%{y:,.0f}<extra></extra>",
))
# Shade the gap
rev_vals = [fy_rev[yr] for yr in years]
exp_vals = [fy_exp[yr] for yr in years]
fig_gap.add_trace(go.Scatter(
    x=years + years[::-1],
    y=rev_vals + exp_vals[::-1],
    fill="toself",
    fillcolor="rgba(100,255,218,0.1)",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip",
))
for i, yr in enumerate(years):
    r, e = rev_vals[i], exp_vals[i]
    fig_gap.add_annotation(
        x=yr, y=(r + e) / 2,
        text=f"Gap: ${r - e:+,.0f}",
        showarrow=False,
        font=dict(color="#e6f1ff", size=12),
    )
fig_gap.update_layout(
    title="Total Revenue vs Total Expenses — Operating Gap",
    yaxis_title="Amount ($)",
)
style_chart(fig_gap, 420)
st.plotly_chart(fig_gap, use_container_width=True)

# ── Section 3: Form 990 Highlights ──────────────────────────────────────
st.markdown("---")
st.header(f"Form 990 Highlights (FY ending June {get_current_month()['fy_start_year']})")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Revenue", "$2,426,454", delta="+13.1% vs PY")
with col2:
    st.metric("Expenses", "$2,492,763", delta="+8.6% vs PY")
with col3:
    st.metric("Net Loss", "-$66,309", delta="Improved from -$148K")
with col4:
    st.metric("Net Assets", "-$2,939,532")
with col5:
    st.metric("Bonds Outstanding", "$5,702,800")

st.markdown("""
| 990 Item | Detail |
|----------|--------|
| **Revenue** | $2,426,454 (PY $2,145,818) — 13.1% increase |
| **Expenses** | $2,492,763 (PY $2,294,335) — 8.6% increase |
| **Net** | -$66,309 (PY -$148,517) — loss narrowed by $82K |
| **Net Assets** | -$2,939,532 — deep negative equity from bond debt |
| **Total Liabilities** | Bonds payable $5,702,800 + other obligations |
| **Governance** | Part VI: management delegation to CSCG should be disclosed |
| **Compensation** | No officer compensation reported (CSCG model) |
""")

# ── Section 4: Payroll Benchmarking ─────────────────────────────────────
st.markdown("---")
st.header("Payroll Benchmarking — NSIA vs Peer Park Districts")

bench = load_payroll_benchmarks()

# Horizontal bar: payroll % by entity
bench_sorted = bench.sort_values("Payroll Pct", ascending=True)

fig_pct = go.Figure(go.Bar(
    y=bench_sorted["Entity"] + " (" + bench_sorted["Fiscal Year"] + ")",
    x=bench_sorted["Payroll Pct"],
    orientation="h",
    marker=dict(
        color=["#64ffda" if "NSIA" in e else "#f78da7" for e in bench_sorted["Entity"]],
        line=dict(width=1, color="rgba(255,255,255,0.2)"),
    ),
    text=[f"{v:.1f}%" for v in bench_sorted["Payroll Pct"]],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=12),
    hovertemplate="<b>%{y}</b><br>Payroll: %{x:.1f}% of revenue<extra></extra>",
))
fig_pct.update_layout(
    title="Payroll as % of Revenue — NSIA vs Peer Districts",
    xaxis_title="Payroll % of Revenue",
    xaxis=dict(range=[0, 60]),
)
style_chart(fig_pct, 380)
st.plotly_chart(fig_pct, use_container_width=True)

# Grouped bar: revenue vs payroll by entity
entities = bench["Entity"] + " (" + bench["Fiscal Year"] + ")"

fig_comp = go.Figure()
fig_comp.add_trace(go.Bar(
    x=entities,
    y=bench["Revenue"],
    name="Gross Revenue",
    marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    text=[f"${v:,.0f}" for v in bench["Revenue"]],
    textposition="outside",
    textfont=dict(size=9, color=FONT_COLOR),
    hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
))
fig_comp.add_trace(go.Bar(
    x=entities,
    y=bench["Payroll"],
    name="Payroll",
    marker=dict(color="#f78da7", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    text=[f"${v:,.0f}" for v in bench["Payroll"]],
    textposition="outside",
    textfont=dict(size=9, color=FONT_COLOR),
    hovertemplate="<b>%{x}</b><br>Payroll: $%{y:,.0f}<extra></extra>",
))
fig_comp.update_layout(
    title="Gross Revenue vs Payroll by Entity",
    barmode="group",
    yaxis_title="Amount ($)",
    xaxis_tickangle=-20,
)
style_chart(fig_comp, 450)
st.plotly_chart(fig_comp, use_container_width=True)

# Callout
st.info(
    "**Why is NSIA's payroll so low?** NSIA uses the CSCG management model where "
    "arena operations staff are employed by CSCG (a third-party management company), not NSIA directly. "
    "This means NSIA's payroll line only reflects minimal direct employees, while peer park districts "
    "employ all staff in-house. The CSCG management fee and payroll reimbursements (~$227K/6 months) "
    "are separate line items not captured in the payroll benchmark."
)

# Data table
st.subheader("Benchmark Data")
st.dataframe(
    bench,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Revenue": st.column_config.NumberColumn(format="$%,.0f"),
        "Payroll": st.column_config.NumberColumn(format="$%,.0f"),
        "Payroll Pct": st.column_config.NumberColumn("Payroll %", format="%.2f%%"),
    },
)

from utils import ask_about_this
ask_about_this("Multi-Year Trends")
