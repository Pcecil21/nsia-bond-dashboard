"""
NSIA Bond Dashboard — Home Page (Executive Briefing)
North Shore Ice Arena financial transparency dashboard.
"""
import streamlit as st
import plotly.graph_objects as go
import os
import pandas as pd

st.set_page_config(
    page_title="NSIA Bond Dashboard",
    page_icon=":ice_hockey:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    [data-testid="stMetric"] label {
        color: #a8b2d1 !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #e6f1ff !important;
        font-size: 1.8rem !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ccd6f6;
    }
    div[data-testid="stSidebarContent"] {
        background: linear-gradient(180deg, #0a192f 0%, #112240 100%);
    }
    .attention-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-left: 4px solid #eb144c;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 8px 0;
    }
    .attention-item {
        padding: 8px 0;
        border-bottom: 1px solid rgba(168,178,209,0.1);
        color: #ccd6f6;
        font-size: 0.95rem;
    }
    .attention-item:last-child {
        border-bottom: none;
    }
    .verdict-healthy {
        color: #00d084;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .verdict-caution {
        color: #fcb900;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .verdict-risk {
        color: #eb144c;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────
logo_path = os.path.join(os.path.dirname(__file__), "data", "nsia_logo.png")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=200)
st.sidebar.title("NSIA Bond Dashboard")
st.sidebar.markdown(
    """
**📋 Action Required**
- **Home** — Executive Briefing
- **Variance Alerts** — Stoplight flags
- **CSCG Scorecard** — Contract compliance

**📊 Monthly Review**
- **Monthly Financials** — P&L, Cash, Receivables
- **Operations** — Ice Revenue & CSCG
- **Ice Utilization** — Allocation & Gaps

**📈 Reference**
- **Financial Overview** — Budget variances
- **Bond & Debt** — Obligations & hidden flows
- **Revenue & Ads** — Advertising pipeline
- **Multi-Year Trends** — 3yr Analysis
- **Reconciliation** — 4-way audit trail
- **Document Library** — Board documents & files
    """
)
st.sidebar.markdown("---")
st.sidebar.caption("FY2026 | Data through January 2026 (Month 7)")

# ── Data ─────────────────────────────────────────────────────────────────
from utils.data_loader import (
    compute_kpis,
    load_hidden_cash_flows,
    load_expense_flow_summary,
    load_cash_forecast,
    compute_board_attention,
)

kpis = compute_kpis()
cash = load_cash_forecast()
dscr = kpis["dscr"]

# ── Header ───────────────────────────────────────────────────────────────
st.title("North Shore Ice Arena")
st.subheader("Executive Briefing")
st.markdown(
    "**Fiscal Year 2026** | July 2025 – June 2026 | "
    "Data through January 2026 &nbsp; "
    '<span style="background:#0f3460;padding:2px 10px;border-radius:10px;'
    'font-size:0.8rem;color:#a8b2d1;">Month 7 of 12</span>',
    unsafe_allow_html=True,
)

st.markdown("---")

# ── HERO: DSCR Gauge ────────────────────────────────────────────────────
dscr_color = "#00d084" if dscr >= 1.25 else ("#fcb900" if dscr >= 1.0 else "#eb144c")
if dscr >= 1.25:
    verdict_text, verdict_class = "HEALTHY", "verdict-healthy"
elif dscr >= 1.0:
    verdict_text, verdict_class = "CAUTION", "verdict-caution"
else:
    verdict_text, verdict_class = "AT RISK", "verdict-risk"

hero_left, hero_right = st.columns([2, 3])

with hero_left:
    fig_dscr = go.Figure(go.Indicator(
        mode="gauge+number",
        value=dscr,
        number=dict(suffix="x", font=dict(size=56, color="#e6f1ff")),
        title=dict(text="Debt Service Coverage Ratio", font=dict(size=18, color="#ccd6f6")),
        gauge=dict(
            axis=dict(range=[0, 3], tickfont=dict(color="#a8b2d1"), tickcolor="#a8b2d1",
                      dtick=0.5),
            bar=dict(color=dscr_color, thickness=0.75),
            bgcolor="rgba(168,178,209,0.1)",
            bordercolor="rgba(168,178,209,0.3)",
            steps=[
                dict(range=[0, 1.0], color="rgba(235,20,76,0.2)"),
                dict(range=[1.0, 1.25], color="rgba(252,185,0,0.2)"),
                dict(range=[1.25, 3], color="rgba(0,208,132,0.2)"),
            ],
            threshold=dict(
                line=dict(color="#e6f1ff", width=3),
                thickness=0.8,
                value=1.0,
            ),
        ),
    ))
    fig_dscr.update_layout(
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a8b2d1"),
        margin=dict(t=70, b=20, l=30, r=30),
    )
    st.plotly_chart(fig_dscr, use_container_width=True)
    st.markdown(
        f'<div style="text-align:center;margin-top:-20px;">'
        f'<span class="{verdict_class}">{verdict_text}</span></div>',
        unsafe_allow_html=True,
    )

with hero_right:
    st.markdown("")
    st.markdown("")
    with st.expander("DSCR Breakdown & Interpretation", expanded=False):
        st.markdown(f"""
| Component | Amount |
|-----------|--------|
| **Net Operating Income** (Revenue – Expenses) | **${kpis['net_operating_income']:,.0f}** |
| **Annual Debt Service** (Bonds + Techny Loan) | **${kpis['debt_service']:,.0f}** |
| **DSCR** (NOI / Debt Service) | **{dscr:.2f}x** |

**What this means:**
- **Above 1.25x** — Healthy. Comfortable margin to cover debt obligations.
- **1.0x – 1.25x** — Caution. Minimal buffer; any revenue shortfall threatens debt payments.
- **Below 1.0x** — Operating income alone cannot cover debt service.

*Note: {kpis.get("annualization_note", "Linear 7→12 month projection")}. Actual DSCR may vary
based on seasonal revenue patterns and timing of debt payments.*
        """)

st.markdown("---")

# ── Supporting KPIs with Mini Charts ─────────────────────────────────────
col_rev, col_exp, col_cash = st.columns(3)

# Revenue KPI + mini chart
with col_rev:
    annual_rev = kpis["total_annual_revenue"]
    ytd_rev = cash["Revenue"].sum()
    st.metric(
        label="Total Annual Revenue (est.)",
        value=f"${annual_rev:,.0f}",
        delta=f"${ytd_rev:,.0f} YTD actual",
        delta_color="off",
    )
    fig_rev = go.Figure(go.Bar(
        x=cash["Month"],
        y=cash["Revenue"],
        marker_color="#00b4d8",
    ))
    fig_rev.update_layout(
        height=80, margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        bargap=0.3,
    )
    st.plotly_chart(fig_rev, use_container_width=True)

# Expenses KPI + mini chart
with col_exp:
    annual_exp = kpis["total_annual_expenses"]
    ytd_exp = cash["Expenses"].sum()
    st.metric(
        label="Total Annual Expenses (est.)",
        value=f"${annual_exp:,.0f}",
        delta=f"${ytd_exp:,.0f} YTD actual",
        delta_color="off",
    )
    fig_exp = go.Figure(go.Bar(
        x=cash["Month"],
        y=cash["Expenses"],
        marker_color="#ff6b6b",
    ))
    fig_exp.update_layout(
        height=80, margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        bargap=0.3,
    )
    st.plotly_chart(fig_exp, use_container_width=True)

# Cash Position KPI + mini chart with red zone
with col_cash:
    ncf = kpis["net_cash_flow"]
    end_cash = cash["Cumulative Cash"].iloc[-1]
    st.metric(
        label="Net Cash Flow (est.)",
        value=f"${ncf:,.0f}",
        delta=f"{'Positive' if ncf > 0 else 'Negative'} — ending ${end_cash:,.0f}",
        delta_color="normal" if ncf > 0 else "inverse",
    )
    # Cash position line with red zone shading below zero
    fig_cash = go.Figure()
    fig_cash.add_shape(
        type="rect", x0=-0.5, x1=len(cash) - 0.5, y0=cash["Cumulative Cash"].min() - 5000, y1=0,
        fillcolor="rgba(235,20,76,0.15)", line_width=0,
    )
    cash_colors = ["#eb144c" if v < 0 else "#00d084" for v in cash["Cumulative Cash"]]
    fig_cash.add_trace(go.Bar(
        x=cash["Month"],
        y=cash["Cumulative Cash"],
        marker_color=cash_colors,
    ))
    fig_cash.update_layout(
        height=80, margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        bargap=0.3,
    )
    st.plotly_chart(fig_cash, use_container_width=True)

st.markdown("---")

# ── Board Attention Required ─────────────────────────────────────────────
attention_items = compute_board_attention()

if attention_items:
    st.markdown("### Board Attention Required")
    items_html = ""
    for item in attention_items:
        items_html += f'<div class="attention-item">{item["icon"]} &nbsp; {item["text"]} &nbsp; <span style="color:#64ffda;font-size:0.8rem;">→ {item["page"]}</span></div>'

    st.markdown(
        f'<div class="attention-box">{items_html}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

st.markdown("---")

# ── Governance Snapshot ──────────────────────────────────────────────────
st.markdown("### Governance Snapshot")
gov_left, gov_right = st.columns(2)

with gov_left:
    # Hidden cash flows donut (kept — unique and valuable)
    hidden = load_hidden_cash_flows()
    fig_hidden = go.Figure(go.Pie(
        labels=hidden["Item"],
        values=hidden["Annual Impact"],
        hole=0.5,
        marker=dict(
            colors=["#ff6b6b", "#ee5a24", "#f0932b", "#ffbe76", "#6ab04c", "#22a6b3"],
            line=dict(color="#0a192f", width=2),
        ),
        textinfo="label+value",
        texttemplate="%{label}<br>$%{value:,.0f}",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent:.1%}<extra></extra>",
    ))
    fig_hidden.update_layout(
        title=dict(text="Hidden Cash Outflows Breakdown", font=dict(size=16, color="#ccd6f6")),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a8b2d1"),
        showlegend=False,
        annotations=[dict(text=f"<b>${hidden['Annual Impact'].sum():,.0f}</b><br>Total/yr",
                          x=0.5, y=0.5, font_size=16, font_color="#e6f1ff", showarrow=False)],
    )
    st.plotly_chart(fig_hidden, use_container_width=True)

with gov_right:
    # CSCG Oversight — compact stacked bar replacing donut
    summary = load_expense_flow_summary()
    pct_board = kpis["pct_board_approved"]
    pct_display = pct_board if pct_board > 1 else pct_board * 100  # handle both 0.255 and 25.5

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
     border:1px solid #0f3460;border-radius:12px;padding:20px;margin-top:10px;">
<div style="color:#a8b2d1;font-size:0.85rem;margin-bottom:4px;">Board-Approved Expenses</div>
<div style="color:#e6f1ff;font-size:2.2rem;font-weight:700;">{pct_display:.1f}%</div>
<div style="color:#a8b2d1;font-size:0.8rem;margin-bottom:12px;">of total spending requires board invoice approval</div>
</div>
    """, unsafe_allow_html=True)

    # Stacked horizontal bar
    if len(summary) > 0:
        bar_colors = ["#00b894", "#fdcb6e", "#6c5ce7", "#b2bec3"]
        fig_bar = go.Figure()
        for i, (_, row) in enumerate(summary.iterrows()):
            pct_val = row["% of Total"]
            # Handle both decimal and percentage formats
            display_pct = pct_val if pct_val > 1 else pct_val * 100
            fig_bar.add_trace(go.Bar(
                y=["Expense Approval"],
                x=[display_pct],
                name=str(row["Approval Method"]),
                orientation="h",
                marker_color=bar_colors[i % len(bar_colors)],
                text=f"{row['Approval Method']}<br>{display_pct:.0f}%",
                textposition="inside",
                textfont=dict(size=11, color="#0a192f"),
                hovertemplate=f"<b>{row['Approval Method']}</b><br>{display_pct:.1f}%<extra></extra>",
            ))
        fig_bar.update_layout(
            barmode="stack",
            height=80,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False, range=[0, 100]),
            yaxis=dict(visible=False),
            margin=dict(t=0, b=0, l=0, r=0),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ── Key Findings (condensed in expander) ─────────────────────────────────
with st.expander("Key Findings", expanded=False):
    st.markdown(
        """
| Finding | Detail |
|---------|--------|
| **Hidden cash outflows** | ~$916K/year in debt service and cash obligations excluded from the board's primary Budget vs. Actuals report |
| **Limited board approval** | Only 25.5% of expenses require individual invoice approval by the Board President |
| **CSCG auto-pay** | 21% of expenses ($227K/6mo) flow through CSCG without invoice-level approval |
| **Unauthorized modifications** | Multiple budget line items changed by CSCG without formal board amendment |
| **Scoreboard economics** | Current deal projects negative NPV of -$14.6K over 10 years vs. +$17.5K for a cheaper alternative |

---
*Use the sidebar to navigate to detailed pages.*
        """
    )
