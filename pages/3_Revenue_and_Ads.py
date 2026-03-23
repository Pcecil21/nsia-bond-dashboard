"""
Page 3: Revenue & Advertising
Current advertisers, sales pipeline, historical ad revenue, scoreboard model, and contract receivables.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_receivable_months, get_latest_receivable_month

st.set_page_config(page_title="Revenue & Ads | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Revenue & Advertising")
st.caption("Advertiser tracking, sales pipeline, contract receivables, and historical trends")

from utils.data_loader import (
    load_current_ads,
    load_done_deals_prospects,
    load_historical_ad_revenue,
    load_scoreboard_10yr,
    load_contract_receivables,
)

# ── Pipeline KPIs ────────────────────────────────────────────────────────
pipeline = load_done_deals_prospects()
ads = load_current_ads()
recv = load_contract_receivables()

done = pipeline[pipeline["Pipeline Stage"] == "Done Deal"]
prospects = pipeline[pipeline["Pipeline Stage"] == "Prospect"]
done_total = done["Amount"].sum()
prospect_total = prospects["Amount"].sum()
total_pipeline = done_total + prospect_total

k1, k2, k3, k4 = st.columns(4)
k1.metric("Done Deals", f"${done_total:,.0f}", f"{len(done)} deals")
k2.metric("Prospect Pipeline", f"${prospect_total:,.0f}", f"{len(prospects)} prospects")
k3.metric("Total Pipeline", f"${total_pipeline:,.0f}", f"{len(pipeline)} total")
k4.metric("Active Advertisers", len(ads), f"${ads['Cost (Numeric)'].sum():,.0f} contract value")

st.markdown("---")

# ── Current Advertisers ──────────────────────────────────────────────────
st.header("Current Advertisers")

now = pd.Timestamp.now()

def get_status(row):
    exp = row["Expiration Date"]
    if pd.isna(exp):
        return "TBD"
    if exp < now:
        return "Expired"
    elif exp < now + pd.Timedelta(days=90):
        return "Expiring Soon"
    return "Active"

ads["Status"] = ads.apply(get_status, axis=1)

def status_style(val):
    styles = {
        "Expired": "background-color: #eb144c33; color: #ff6b6b; font-weight: bold",
        "Expiring Soon": "background-color: #fcb90033; color: #fcb900; font-weight: bold",
        "Active": "background-color: #00d08433; color: #7bdcb5; font-weight: bold",
    }
    return styles.get(val, "")

display_ads = ads[["Customer", "Type", "Location/Notes", "Term", "Expiration Date", "Cost", "Status"]].copy()

col_table, col_donut = st.columns([2, 1])

with col_table:
    st.dataframe(
        display_ads.style.map(status_style, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )

with col_donut:
    status_counts = ads["Status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    status_color_map = {"Active": "#00d084", "Expiring Soon": "#fcb900", "Expired": "#eb144c", "TBD": "#b2bec3"}
    fig_status = go.Figure(go.Pie(
        labels=status_counts["Status"],
        values=status_counts["Count"],
        hole=0.55,
        marker=dict(
            colors=[status_color_map.get(s, "#abb8c3") for s in status_counts["Status"]],
            line=dict(color="#0a192f", width=2),
        ),
        textinfo="label+value",
        textfont=dict(size=13, color="#e6f1ff"),
    ))
    fig_status.update_layout(
        title=dict(text="Status Breakdown", font=dict(size=16, color=TITLE_COLOR)),
        showlegend=False,
    )
    style_chart(fig_status, 320)
    st.plotly_chart(fig_status, use_container_width=True)

    # Action items for expired/expiring
    expired = ads[ads["Status"] == "Expired"]
    expiring = ads[ads["Status"] == "Expiring Soon"]
    if not expired.empty or not expiring.empty:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);'
            f'border-left:4px solid #fcb900;border-radius:8px;padding:12px 16px;">'
            f'<b style="color:#fcb900;">Action Needed</b><br>'
            + (f'<span style="color:#ff6b6b;">{len(expired)} expired</span> — contact for renewal<br>' if not expired.empty else '')
            + (f'<span style="color:#fcb900;">{len(expiring)} expiring soon</span> — schedule renewal discussion' if not expiring.empty else '')
            + '</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Sales Pipeline ────────────────────────────────────────────────────────
st.header("Sales Pipeline — Done Deals vs. Prospects")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Done Deals")
    done_display = done[["Advertiser", "$$", "Term"]].copy()
    st.dataframe(done_display, use_container_width=True, hide_index=True)
    st.metric("Total Done Deals", f"${done_total:,.0f}")

with col2:
    st.subheader("Prospects")
    prospect_display = prospects[["Advertiser", "$$", "Term", "Status"]].copy()
    prospect_display.columns = ["Advertiser", "$$", "Term", "Notes"]
    st.dataframe(prospect_display, use_container_width=True, hide_index=True)
    st.metric("Total Prospect Pipeline", f"${prospect_total:,.0f}")

# Pipeline visualization — by term length
fig_funnel = go.Figure()

for stage, color in [("Done Deal", "#00d084"), ("Prospect", "#0984e3")]:
    stage_data = pipeline[pipeline["Pipeline Stage"] == stage]
    term_groups = stage_data.groupby("Term")["Amount"].agg(["sum", "count"]).reset_index()
    term_groups.columns = ["Term", "Value", "Count"]
    term_groups = term_groups.sort_values("Value", ascending=False)

    fig_funnel.add_trace(go.Bar(
        x=term_groups["Term"],
        y=term_groups["Value"],
        name=stage,
        marker=dict(color=color, line=dict(width=1, color="rgba(255,255,255,0.3)")),
        text=[f"${v:,.0f} ({c})" for v, c in zip(term_groups["Value"], term_groups["Count"])],
        textposition="inside",
        textfont=dict(color="#fff", size=12),
    ))

fig_funnel.update_layout(
    title="Pipeline Value by Term Length",
    barmode="group",
    yaxis_title="Total Value ($)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    bargap=0.3,
)
style_chart(fig_funnel, 380)
st.plotly_chart(fig_funnel, use_container_width=True)

# Conversion rate insight
if len(pipeline) > 0:
    conversion = len(done) / len(pipeline) * 100
    avg_deal = done_total / len(done) if len(done) > 0 else 0
    avg_prospect = prospect_total / len(prospects) if len(prospects) > 0 else 0
    st.info(
        f"**Conversion rate:** {conversion:.0f}% of pipeline is closed | "
        f"**Avg deal size:** ${avg_deal:,.0f} (done) vs. ${avg_prospect:,.0f} (prospect) | "
        f"**If all prospects close:** ${total_pipeline:,.0f} total revenue"
    )

st.markdown("---")

# ── Contract Receivables ─────────────────────────────────────────────────
st.header("Contract Receivables")
_recv_months = get_receivable_months()
_recv_first = _recv_months[0] if len(_recv_months) > 0 else "Sept"
_recv_last = _recv_months[-1] if len(_recv_months) > 0 else "Nov"
st.caption(f"Collection progress by major customer — {_recv_first} vs. {_recv_last} snapshots")

recv_data = recv[recv["Customer"] != "Total"].copy()

if not recv_data.empty:
    # Collection progress chart
    fig_recv = go.Figure()

    fig_recv.add_trace(go.Bar(
        x=recv_data["Customer"],
        y=recv_data[f"{_recv_last} Paid"],
        name="Paid",
        marker_color="#00d084",
        text=[f"${v:,.0f}" for v in recv_data[f"{_recv_last} Paid"]],
        textposition="inside",
        textfont=dict(color="#fff", size=11),
    ))
    fig_recv.add_trace(go.Bar(
        x=recv_data["Customer"],
        y=recv_data[f"{_recv_last} Owed"],
        name="Outstanding",
        marker_color="#eb144c",
        text=[f"${v:,.0f}" for v in recv_data[f"{_recv_last} Owed"]],
        textposition="inside",
        textfont=dict(color="#fff", size=11),
    ))

    fig_recv.update_layout(
        title=f"Collection Status by Customer ({_recv_last})",
        barmode="stack",
        yaxis_title="Contract Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    style_chart(fig_recv, 420)
    st.plotly_chart(fig_recv, use_container_width=True)

    # Collection rate metrics
    totals = recv[recv["Customer"] == "Total"]
    if not totals.empty:
        t = totals.iloc[0]
        first_rate = t[f"{_recv_first} Paid"] / t[f"{_recv_first} Contracted"] * 100 if t[f"{_recv_first} Contracted"] > 0 else 0
        last_rate = t[f"{_recv_last} Paid"] / t[f"{_recv_last} Contracted"] * 100 if t[f"{_recv_last} Contracted"] > 0 else 0
        delta = last_rate - first_rate

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Total Contracted", f"${t[f'{_recv_last} Contracted']:,.0f}")
        r2.metric("Total Collected", f"${t[f'{_recv_last} Paid']:,.0f}")
        r3.metric("Outstanding", f"${t[f'{_recv_last} Owed']:,.0f}")
        r4.metric("Collection Rate", f"{last_rate:.1f}%", f"{delta:+.1f}pp vs {_recv_first} ({first_rate:.1f}%)")

    # Collection progress: first → last receivable month
    recv_data[f"{_recv_first} Collection %"] = (recv_data[f"{_recv_first} Paid"] / recv_data[f"{_recv_first} Contracted"] * 100).round(1)
    recv_data[f"{_recv_last} Collection %"] = (recv_data[f"{_recv_last} Paid"] / recv_data[f"{_recv_last} Contracted"] * 100).round(1)

    fig_progress = go.Figure()
    fig_progress.add_trace(go.Bar(
        x=recv_data["Customer"],
        y=recv_data[f"{_recv_first} Collection %"],
        name=_recv_first,
        marker_color="#636e72",
    ))
    fig_progress.add_trace(go.Bar(
        x=recv_data["Customer"],
        y=recv_data[f"{_recv_last} Collection %"],
        name=_recv_last,
        marker_color="#0984e3",
        text=[f"{v:.0f}%" for v in recv_data[f"{_recv_last} Collection %"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
    ))
    fig_progress.update_layout(
        title=f"Collection Rate Progress: {_recv_first} \u2192 {_recv_last}",
        barmode="group",
        yaxis_title="% Collected",
        yaxis=dict(range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    style_chart(fig_progress, 380)
    st.plotly_chart(fig_progress, use_container_width=True)

st.markdown("---")

# ── Historical Ad Revenue ─────────────────────────────────────────────────
st.header("Historical Ad Revenue (2014-2024)")

hist = load_historical_ad_revenue()
if not hist.empty:
    avg = hist["Ad Revenue"].mean()
    max_year = int(hist.loc[hist["Ad Revenue"].idxmax(), "Year"])

    colors = []
    for _, row in hist.iterrows():
        if row["Ad Revenue"] >= avg * 1.5:
            colors.append("#00d084")
        elif row["Ad Revenue"] >= avg:
            colors.append("#0984e3")
        else:
            colors.append("#636e72")

    fig_hist = go.Figure(go.Bar(
        x=hist["Year"],
        y=hist["Ad Revenue"],
        marker=dict(
            color=colors,
            line=dict(width=1, color="rgba(255,255,255,0.2)"),
        ),
        text=[f"${v:,.0f}" for v in hist["Ad Revenue"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
        hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
    ))
    fig_hist.add_hline(y=avg, line_dash="dash", line_color="#fcb900", line_width=2,
                       annotation=dict(text=f"Avg: ${avg:,.0f}", font=dict(color="#fcb900", size=13)))
    fig_hist.update_layout(
        title="Annual Advertising Revenue (2014-2024)",
        yaxis_title="Revenue ($)",
        xaxis=dict(dtick=1),
    )
    style_chart(fig_hist, 430)
    st.plotly_chart(fig_hist, use_container_width=True)

    # Budget comparison
    current_budget = 12300
    gap = avg - current_budget
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);'
        f'border:1px solid #0f3460;border-radius:12px;padding:16px 20px;">'
        f'<span style="color:#a8b2d1;">10-year average:</span> '
        f'<b style="color:#e6f1ff;font-size:1.2rem;">${avg:,.0f}/yr</b> &nbsp;|&nbsp; '
        f'<span style="color:#a8b2d1;">Peak:</span> '
        f'<b style="color:#00d084;">${hist["Ad Revenue"].max():,.0f}</b> ({max_year}) &nbsp;|&nbsp; '
        f'<span style="color:#a8b2d1;">Current budget:</span> '
        f'<b style="color:#fcb900;">${current_budget:,.0f}/yr</b> &nbsp;|&nbsp; '
        f'<span style="color:#eb144c;">Gap to avg: ${gap:,.0f}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Scoreboard Sponsorship Model ─────────────────────────────────────────
st.header("Scoreboard Sponsorship Revenue Model")
st.caption("10-year projection from the ScoreVision deal")

sb = load_scoreboard_10yr()
revenue_rows = sb[sb["Category"].str.contains("Revenue", case=False)]

if not revenue_rows.empty:
    years_cols = [c for c in sb.columns if c.startswith("Year")]
    melted = revenue_rows.melt(id_vars=["Category"], value_vars=years_cols,
                                var_name="Year", value_name="Amount")
    melted["Year Num"] = melted["Year"].str.extract(r"(\d+)").astype(int)

    color_map = {
        "Existing Sponsor Revenue": "#ff6b6b",
        "Referral Sponsorship Revenue to NSIA": "#00d084",
        "Non-Referral Revenue to NSIA": "#0984e3",
        "Total NSIA Sponsorship Revenue": "#fcb900",
    }

    fig_sb = go.Figure()
    for cat in revenue_rows["Category"].unique():
        cat_data = melted[melted["Category"] == cat]
        fig_sb.add_trace(go.Scatter(
            x=cat_data["Year Num"],
            y=cat_data["Amount"],
            mode="lines+markers",
            name=cat,
            line=dict(color=color_map.get(cat, "#abb8c3"), width=3),
            marker=dict(size=8, line=dict(width=2, color="#fff")),
            hovertemplate=f"<b>{cat}</b><br>Year %{{x}}<br>${{y:,.0f}}<extra></extra>",
        ))

    fig_sb.update_layout(
        title="Scoreboard Sponsorship Revenue Projections (10-Year)",
        xaxis_title="Year",
        yaxis_title="Revenue ($)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )
    style_chart(fig_sb, 450)
    st.plotly_chart(fig_sb, use_container_width=True)
