"""
NSIA Board Dashboard — Home Page
Plain-english monthly summary for board members.
"""
import streamlit as st
import plotly.graph_objects as go
import os
import logging
import pandas as pd
from datetime import datetime, timezone

from utils.fiscal_period import get_current_month, get_month_label, get_sidebar_caption, get_latest_receivable_month, get_cash_forecast_months
from utils.variance_engine import compute_monthly_flags, compute_discussion_items
from utils.theme import inject_css, style_chart, FONT_COLOR, GRID_COLOR

st.set_page_config(
    page_title="NSIA Board Dashboard",
    page_icon=":ice_hockey:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Authentication ───────────────────────────────────────────────────────
from utils.auth import init_authenticator, get_user_role, get_user_club

authenticator = init_authenticator()
authenticator.login(location="sidebar")

authentication_status = st.session_state.get("authentication_status")
name = st.session_state.get("name", "")
username = st.session_state.get("username", "")

if authentication_status is False:
    st.sidebar.error("Username or password is incorrect.")
elif authentication_status is None:
    st.sidebar.info("Please log in to access the dashboard.")

if authentication_status:
    authenticator.logout("Logout", "sidebar")
    role = get_user_role()
    st.sidebar.markdown(f"**Logged in as:** {name} (`{role}`)")
    st.sidebar.markdown("---")

inject_css()

# ── Custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    div[data-testid="stSidebarContent"] {
        background: linear-gradient(180deg, #0a192f 0%, #112240 100%);
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ccd6f6;
    }
    .verdict-card {
        border-radius: 12px;
        padding: 24px 28px;
        margin: 4px 0 12px 0;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .verdict-good {
        background: linear-gradient(135deg, #0d3320 0%, #1a5c3a 100%);
        border: 1px solid #2d8a56;
    }
    .verdict-ok {
        background: linear-gradient(135deg, #3d2e00 0%, #5c4a0a 100%);
        border: 1px solid #8a7a2d;
    }
    .verdict-bad {
        background: linear-gradient(135deg, #3d0a0a 0%, #5c1a1a 100%);
        border: 1px solid #8a2d2d;
    }
    .verdict-number {
        font-size: 2.8rem;
        font-weight: 700;
        color: #e6f1ff;
        line-height: 1.1;
    }
    .verdict-label {
        font-size: 1.0rem;
        color: #a8b2d1;
        margin-top: 4px;
    }
    .verdict-context {
        font-size: 0.85rem;
        color: #8892b0;
        margin-top: 8px;
    }
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #ccd6f6;
        margin-top: 24px;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
        border-bottom: 2px solid #1a3a5c;
        padding-bottom: 6px;
    }
    .flag-row {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        border-left: 4px solid;
    }
    .flag-red { border-left-color: #eb144c; }
    .flag-yellow { border-left-color: #fcb900; }
    .flag-green { border-left-color: #00d084; }
    .flag-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e6f1ff;
    }
    .flag-detail {
        font-size: 0.85rem;
        color: #a8b2d1;
        margin-top: 2px;
    }
    .plain-text {
        font-size: 0.95rem;
        color: #a8b2d1;
        line-height: 1.6;
    }
    .discuss-item {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
        color: #ccd6f6;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .discuss-item:before {
        content: "\25B8  ";
        color: #64ffda;
    }
    .staleness-fresh {
        color: #00d084;
        font-size: 0.8rem;
    }
    .staleness-stale {
        color: #fcb900;
        font-size: 0.8rem;
    }
    .staleness-critical {
        color: #eb144c;
        font-size: 0.8rem;
        font-weight: 600;
    }
    @media (max-width: 768px) {
        .verdict-card {
            padding: 16px 14px;
            margin: 4px 0 8px 0;
        }
        .verdict-number {
            font-size: 1.8rem;
        }
        .verdict-label {
            font-size: 0.85rem;
        }
        .verdict-context {
            font-size: 0.75rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ── Gate content behind login ────────────────────────────────────────────
if not authentication_status:
    st.title("North Shore Ice Arena")
    st.subheader("Board Dashboard")
    st.info("Please log in using the sidebar to access the dashboard.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────
logo_path = os.path.join(os.path.dirname(__file__), "data", "nsia_logo.png")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=200)
st.sidebar.title("NSIA Board Dashboard")
st.sidebar.markdown(
    """
**Start Here**
- **Home** — Monthly summary (this page)

**Dig Deeper**
- **Financial Overview** — Budget variances
- **Monthly Financials** — P&L, Cash, Receivables
- **Variance Alerts** — Stoplight flags
- **Operations** — Ice Revenue & CSCG

**Oversight**
- **CSCG Scorecard** — Contract compliance
- **Reconciliation** — 4-way audit trail
- **Board Actions** — Motions & action items

**Reference**
- **Bond & Debt** — Obligations & hidden flows
- **Revenue & Ads** — Advertising pipeline
- **Multi-Year Trends** — 3yr Analysis
- **Ice Utilization** — Allocation & Gaps
- **Vendor Master** — Vendor registry
- **Document Library** — Board documents
- **Ask NSIA** — AI Q&A
    """
)
st.sidebar.markdown("---")
st.sidebar.caption(get_sidebar_caption())

# ── Load Data ────────────────────────────────────────────────────────────
from utils.data_loader import (
    load_cash_forecast,
    load_contract_receivables,
    load_monthly_pnl,
)

cash = load_cash_forecast()
pnl = load_monthly_pnl()
receivables = load_contract_receivables()

# ── Compute key numbers from the data ────────────────────────────────────
period = get_current_month()
cur_month = period["abbrev"]

# Current month P&L
month_pnl = pnl[pnl["Month"] == cur_month]
month_revenue = month_pnl[
    (month_pnl["Category"] == "Revenue") & (month_pnl["Subcategory"] == "Total")
]["Actual"].sum()
month_expenses = month_pnl[
    (month_pnl["Category"] == "Expense") & (month_pnl["Subcategory"] == "Total")
]["Actual"].sum()
month_net = month_pnl[
    (month_pnl["Category"] == "Net") & (month_pnl["Subcategory"] == "Net Income")
]["Actual"].sum()
month_budget_net = month_pnl[
    (month_pnl["Category"] == "Net") & (month_pnl["Subcategory"] == "Net Income")
]["Budget"].sum()

# YTD
ytd_revenue = month_pnl[month_pnl["Category"] == "YTD Revenue"]["Actual"].sum()
ytd_expenses = month_pnl[month_pnl["Category"] == "YTD Expense"]["Actual"].sum()
ytd_net = month_pnl[month_pnl["Category"] == "YTD Net"]["Actual"].sum()
ytd_budget_net = month_pnl[month_pnl["Category"] == "YTD Net"]["Budget"].sum()
ytd_pct = (ytd_net / ytd_budget_net * 100) if ytd_budget_net else 0

# Cash position (from cash forecast — actuals through current month)
cf_info = get_cash_forecast_months()
actual_months = cash.head(cf_info["actual_count"])
total_cash = actual_months["Cumulative Cash"].iloc[-1] if len(actual_months) > 0 else 0

# Contract receivables — use latest available month columns
latest_recv = get_latest_receivable_month()
contracted_col = f"{latest_recv} Contracted"
paid_col = f"{latest_recv} Paid"
owed_col = f"{latest_recv} Owed"
if contracted_col in receivables.columns:
    total_contracted = receivables[receivables["Customer"] == "Total"][contracted_col].sum()
    total_paid = receivables[receivables["Customer"] == "Total"][paid_col].sum()
    total_owed = receivables[receivables["Customer"] == "Total"][owed_col].sum()
    collection_pct = (total_paid / total_contracted * 100) if total_contracted else 0
else:
    total_contracted = total_paid = total_owed = 0
    collection_pct = 0

# ── HEADER ───────────────────────────────────────────────────────────────
st.title("North Shore Ice Arena")
st.markdown(
    f'<span style="color:#a8b2d1;font-size:1.1rem;">Monthly Board Summary</span>'
    ' &nbsp; '
    f'<span style="background:#0f3460;padding:3px 12px;border-radius:10px;'
    f'font-size:0.85rem;color:#64ffda;">{get_month_label()}</span>',
    unsafe_allow_html=True,
)

# ── Data Freshness Indicator ──────────────────────────────────────────────
_last_sync_path = os.path.join(os.path.dirname(__file__), "data", ".last_sync")
try:
    _sync_ts = datetime.fromisoformat(open(_last_sync_path, encoding="utf-8").read().strip())
    _age = datetime.now(timezone.utc) - _sync_ts
    _age_days = _age.total_seconds() / 86400
    if _age_days > 7:
        _cls, _label = "staleness-critical", f"Data last synced {_age_days:.0f} days ago — may be stale"
    elif _age_days > 1:
        _label = f"Data synced {_age_days:.0f} day{'s' if _age_days >= 2 else ''} ago"
        _cls = "staleness-stale" if _age_days > 3 else "staleness-fresh"
    else:
        _hours = _age.total_seconds() / 3600
        _label = f"Data synced {_hours:.0f}h ago" if _hours >= 1 else "Data synced just now"
        _cls = "staleness-fresh"
    st.markdown(f'<span class="{_cls}">{_label}</span>', unsafe_allow_html=True)
except FileNotFoundError:
    st.markdown('<span class="staleness-stale">Data sync status unknown</span>', unsafe_allow_html=True)
except Exception as e:
    logging.getLogger(__name__).warning("Failed to read .last_sync: %s", e)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════
# SECTION 1: THE VERDICT
# ═════════════════════════════════════════════════════════════════════════
verdict_class = "verdict-good" if month_net > month_budget_net else (
    "verdict-ok" if month_net > 0 else "verdict-bad"
)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f'<div class="verdict-card {verdict_class}">'
        f'<div class="verdict-number">${month_net:,.0f}</div>'
        f'<div class="verdict-label">{period["name"]} Net Income</div>'
        f'<div class="verdict-context">Budget was ${month_budget_net:,.0f} — {"beat it" if month_net > month_budget_net else "fell short"}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col2:
    cash_class = "verdict-good" if total_cash > 50000 else ("verdict-ok" if total_cash > 0 else "verdict-bad")
    st.markdown(
        f'<div class="verdict-card {cash_class}">'
        f'<div class="verdict-number">${total_cash:,.0f}</div>'
        f'<div class="verdict-label">Cash on Hand</div>'
        f'<div class="verdict-context">As of {period["as_of_date"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col3:
    ytd_class = "verdict-good" if ytd_pct >= 100 else ("verdict-ok" if ytd_pct >= 90 else "verdict-bad")
    st.markdown(
        f'<div class="verdict-card {ytd_class}">'
        f'<div class="verdict-number">{ytd_pct:.0f}%</div>'
        f'<div class="verdict-label">YTD vs Plan</div>'
        f'<div class="verdict-context">${ytd_net:,.0f} actual vs ${ytd_budget_net:,.0f} budget</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# Plain english summary
if month_net > month_budget_net:
    summary_text = f"{period['name']} was a strong month. We netted <b>${month_net:,.0f}</b>, beating the budget by <b>${month_net - month_budget_net:,.0f}</b>. Revenue came in at ${month_revenue:,.0f} against ${month_expenses:,.0f} in expenses."
elif month_net > 0:
    summary_text = f"{period['name']} was positive but came in slightly under plan. We netted <b>${month_net:,.0f}</b> against a budget of ${month_budget_net:,.0f}."
else:
    summary_text = f"{period['name']} was a loss month. We lost <b>${abs(month_net):,.0f}</b> against a planned profit of ${month_budget_net:,.0f}."

ytd_text = f"Year-to-date, we're at <b>{ytd_pct:.0f}% of plan</b> — ${ytd_net:,.0f} actual vs ${ytd_budget_net:,.0f} budgeted."

st.markdown(f'<div class="plain-text">{summary_text}<br><br>{ytd_text}</div>', unsafe_allow_html=True)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════
# SECTION 2: CAN WE PAY OUR BILLS?
# ═════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Can We Pay Our Bills?</div>', unsafe_allow_html=True)

# Cash position bar chart — green when positive, red when negative
months_short = [m.replace(" 2025", "").replace(" 2026", "") for m in cash["Month"]]
cash_colors = ["#eb144c" if v < 0 else "#00d084" for v in cash["Cumulative Cash"]]

# Mark actual vs forecast
n_actual = cf_info["actual_count"]
n_forecast = cf_info["forecast_count"]
bar_opacity = [1.0] * n_actual + [0.5] * n_forecast

fig_cash = go.Figure()

# Actual months
fig_cash.add_trace(go.Bar(
    x=months_short[:n_actual],
    y=cash["Cumulative Cash"].iloc[:n_actual],
    marker_color=cash_colors[:n_actual],
    name="Actual",
    text=[f"${v:,.0f}" for v in cash["Cumulative Cash"].iloc[:n_actual]],
    textposition="outside",
    textfont=dict(size=10, color="#a8b2d1"),
))

# Forecast months
fig_cash.add_trace(go.Bar(
    x=months_short[n_actual:],
    y=cash["Cumulative Cash"].iloc[n_actual:],
    marker_color=cash_colors[n_actual:],
    marker_pattern_shape="/",
    name="Forecast",
    text=[f"${v:,.0f}" for v in cash["Cumulative Cash"].iloc[n_actual:]],
    textposition="outside",
    textfont=dict(size=10, color="#a8b2d1"),
    opacity=0.6,
))

# Red zone below zero
min_cash = cash["Cumulative Cash"].min()
if min_cash < 0:
    fig_cash.add_shape(
        type="rect", x0=-0.5, x1=len(cash) - 0.5,
        y0=min_cash - 20000, y1=0,
        fillcolor="rgba(235,20,76,0.1)", line_width=0,
    )

style_chart(fig_cash, height=300)
fig_cash.update_layout(
    yaxis=dict(tickformat="$,.0f"),
    margin=dict(t=30, b=40, l=60, r=20),
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11, color=FONT_COLOR)),
    bargap=0.2,
)
st.plotly_chart(fig_cash, use_container_width=True)
st.caption("Solid bars = actuals | Hatched bars = forecast. Red zone indicates negative cash balance.")

# Plain english cash explanation
negative_months = []
for i, row in cash.iterrows():
    if row["Cumulative Cash"] < 0:
        negative_months.append(row["Month"])

if negative_months:
    cash_warning = f"We're OK right now at ${total_cash:,.0f}. But the forecast shows cash going <b>negative</b> in <b>{', '.join(negative_months)}</b>. "
    if "May" in str(negative_months) or "Apr" in str(negative_months):
        cash_warning += "That's driven by the spring debt service payments and property taxes. We end the fiscal year projected at roughly <b>${:,.0f}</b>.".format(cash["Cumulative Cash"].iloc[-1])
else:
    cash_warning = f"Cash position looks solid at ${total_cash:,.0f}. No months forecast below zero."

st.markdown(f'<div class="plain-text">{cash_warning}</div>', unsafe_allow_html=True)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════
# SECTION 3: WHAT'S WRONG (Variance Flags)
# ═════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">What Needs Attention</div>', unsafe_allow_html=True)

flags = compute_monthly_flags()

if not flags:
    st.markdown(
        '<div class="flag-row flag-green">'
        '<div class="flag-title">&#x1F7E2; All Clear</div>'
        '<div class="flag-detail">No variance flags this month.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

for flag in flags:
    icon = '&#x1F534;' if flag['color'] == 'red' else '&#x1F7E1;' if flag['color'] == 'yellow' else '&#x1F7E2;'
    st.markdown(
        f'<div class="flag-row flag-{flag["color"]}">'
        f'<div class="flag-title">{icon} {flag["title"]}</div>'
        f'<div class="flag-detail">{flag["detail"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════
# SECTION 4: CLUB PAYMENTS
# ═════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Club Payments — Are They Paying?</div>', unsafe_allow_html=True)

if contracted_col in receivables.columns:
    clubs = receivables[receivables["Customer"] != "Total"].copy()
    clubs = clubs.sort_values(contracted_col, ascending=False)

    for _, club in clubs.iterrows():
        contracted = club[contracted_col]
        paid = club[paid_col]
        owed = club[owed_col]
        pct = (paid / contracted * 100) if contracted > 0 else 0
        bar_color = "#00d084" if pct >= 70 else ("#fcb900" if pct >= 50 else "#eb144c")
        customer = club["Customer"]

        st.markdown(
            f'<div style="margin:8px 0 12px 0;">'
            f'<div style="display:flex;justify-content:space-between;color:#ccd6f6;font-size:0.9rem;margin-bottom:4px;">'
            f'<span><b>{customer}</b></span>'
            f'<span>${paid:,.0f} of ${contracted:,.0f} ({pct:.0f}%) &mdash; '
            f'<span style="color:#a8b2d1;">${owed:,.0f} remaining</span></span>'
            f'</div>'
            f'<div style="background:rgba(168,178,209,0.1);border-radius:6px;height:14px;overflow:hidden;">'
            f'<div style="background:{bar_color};width:{min(pct, 100):.0f}%;height:100%;border-radius:6px;'
            f'transition:width 0.3s ease;"></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="plain-text" style="margin-top:14px;">'
        f'<b>Total:</b> ${total_paid:,.0f} collected of ${total_contracted:,.0f} '
        f'({collection_pct:.0f}%) through Month {period["fiscal_month"]}. '
        f'${total_owed:,.0f} still outstanding.'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════
# SECTION 5: WHAT WE NEED TO DISCUSS
# ═════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">Items for Next Board Meeting</div>', unsafe_allow_html=True)

discussion_items = compute_discussion_items()

if not discussion_items:
    st.info("No discussion items flagged for the upcoming meeting.")

for item in discussion_items:
    st.markdown(f'<div class="discuss-item">{item}</div>', unsafe_allow_html=True)

st.markdown("")
st.markdown("---")

# ── Footer ───────────────────────────────────────────────────────────────
with st.expander("Detailed Financial Pages", expanded=False):
    st.markdown("""
Use the sidebar to access detailed analysis pages:

| Page | What It Shows |
|------|---------------|
| **Financial Overview** | Budget vs CSCG variance analysis |
| **Bond & Debt** | Hidden cash flows, fixed obligations, scoreboard economics |
| **Revenue & Ads** | Advertising pipeline, contract receivables |
| **Operations** | Ice revenue breakdown, CSCG relationship |
| **Variance Alerts** | RED/YELLOW/GREEN stoplight on every budget line |
| **CSCG Scorecard** | Contract compliance checklist |
| **Monthly Financials** | Monthly P&L, cash forecast, receivables |
| **Multi-Year Trends** | 3-year revenue/expense trends |
| **Ice Utilization** | Weekend ice allocation by club |
| **Reconciliation** | Budget-to-invoice 4-way match |
| **Board Actions** | Motion tracking, action items |
| **Vendor Master** | Vendor registry and spend analysis |
    """)
