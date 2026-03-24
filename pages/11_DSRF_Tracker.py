"""
Page 18: DSRF Tracker — Debt Service Reserve Fund Portfolio
CD/Treasury holdings, maturity ladder, FDIC concentration, and upcoming maturity alerts.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from utils.theme import (
    FONT_COLOR, TITLE_COLOR, VALUE_COLOR, CHART_BG, GRID_COLOR,
    RED, YELLOW, GREEN, BLUE, PURPLE, CYAN, ORANGE, TEAL,
    ACCENT_COLORS, style_chart, inject_css, fmt_dollar,
)
from utils.auth import require_auth

st.set_page_config(page_title="DSRF Tracker | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("DSRF Tracker")
st.caption("Debt Service Reserve Fund — CD & Treasury holdings, maturity ladder, FDIC exposure")

st.info(
    "The Debt Service Reserve Fund (DSRF) is a reserve account required by NSIA's bond agreement. "
    "It holds approximately $650K in FDIC-insured CDs at UMB Bank, serving as a safety cushion for "
    "bond debt payments. When a CD matures, the board works with the trustee (UMB Bank) to reinvest "
    "the proceeds. The alerts below flag upcoming maturities that need attention."
)

# ── Load Data ─────────────────────────────────────────────────────────────

DATA_PATH = "data/dsrf_holdings.csv"
FDIC_LIMIT = 250_000


@st.cache_data
def load_dsrf_holdings() -> pd.DataFrame:
    """Load DSRF holdings from CSV."""
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        st.error(f"DSRF holdings file not found: {DATA_PATH}")
        return pd.DataFrame()

    df["Purchase_Date"] = pd.to_datetime(df["Purchase_Date"], errors="coerce")
    df["Maturity_Date"] = pd.to_datetime(df["Maturity_Date"], errors="coerce")
    df["Par"] = pd.to_numeric(df["Par"], errors="coerce")
    df["Yield"] = pd.to_numeric(df["Yield"], errors="coerce")
    return df


holdings = load_dsrf_holdings()
if holdings.empty:
    st.stop()

today = pd.Timestamp(date.today())

# Separate cash/sweep from dated positions
cash_rows = holdings[holdings["Status"] == "Cash"].copy()
active_all = holdings[holdings["Status"].isin(["Active", "Maturing"])].copy()
matured = holdings[holdings["Status"] == "Matured"].copy()

# Split active into dated (CDs/bonds with maturity) and undated (sweep/treasury)
has_maturity = active_all["Maturity_Date"].notna()
active = active_all[has_maturity].copy()
sweep = active_all[~has_maturity].copy()

# Compute days to maturity for dated positions
active["Days_Remaining"] = (active["Maturity_Date"] - today).dt.days

# ── Maturity Alerts ───────────────────────────────────────────────────────

urgent = active[active["Days_Remaining"] <= 30]
upcoming = active[(active["Days_Remaining"] > 30) & (active["Days_Remaining"] <= 90)]

if not urgent.empty:
    for _, row in urgent.iterrows():
        days = row["Days_Remaining"]
        label = "TODAY" if days == 0 else f"OVERDUE by {abs(days)} days" if days < 0 else f"in {days} days"
        st.error(
            f"**URGENT:** {row['Issuer']} {row['Security_Type']} ({row['CUSIP']}) "
            f"— ${row['Par']:,.0f} matures **{label}** on {row['Maturity_Date'].strftime('%m/%d/%Y')}"
        )

if not upcoming.empty:
    for _, row in upcoming.iterrows():
        st.warning(
            f"**UPCOMING:** {row['Issuer']} {row['Security_Type']} ({row['CUSIP']}) "
            f"— ${row['Par']:,.0f} matures in {row['Days_Remaining']} days "
            f"on {row['Maturity_Date'].strftime('%m/%d/%Y')}"
        )

if not urgent.empty or not upcoming.empty:
    st.markdown(
        ":telephone_receiver: **Trustee Contact:** Gena Mayer, VP Capital Markets, UMB Bank — "
        "314.612.8016 / gena.mayer@umb.com"
    )

# ── KPI Row ───────────────────────────────────────────────────────────────

cash_balance = cash_rows["Par"].sum() if not cash_rows.empty else 0
sweep_balance = sweep["Par"].sum() if not sweep.empty else 0
cd_par = active["Par"].sum()
total_dsrf = cd_par + cash_balance + sweep_balance

yielding = active[active["Yield"].notna() & (active["Yield"] > 0)]
weighted_yield = (yielding["Par"] * yielding["Yield"]).sum() / yielding["Par"].sum() if not yielding.empty else 0
next_maturity = active.loc[active["Days_Remaining"].idxmin()] if not active.empty else None
num_positions = len(active)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total DSRF Balance", fmt_dollar(total_dsrf))
    if cash_balance > 0 or sweep_balance > 0:
        parts = []
        if cd_par > 0:
            parts.append(f"CDs/Bonds: {fmt_dollar(cd_par)}")
        if sweep_balance > 0:
            parts.append(f"Sweep: {fmt_dollar(sweep_balance)}")
        if cash_balance > 0:
            parts.append(f"Cash: {fmt_dollar(cash_balance)}")
        st.caption(" | ".join(parts))
with col2:
    st.metric("Weighted Avg Yield", f"{weighted_yield:.2f}%")
with col3:
    if next_maturity is not None:
        days_val = int(next_maturity["Days_Remaining"])
        delta_color = "inverse" if days_val <= 30 else "normal"
        st.metric(
            "Next Maturity",
            next_maturity["Maturity_Date"].strftime("%m/%d/%Y"),
            delta=f"{days_val} days",
            delta_color=delta_color,
        )
    else:
        st.metric("Next Maturity", "None")
with col4:
    st.metric("Active Positions", num_positions)

# ── Active Holdings Table ─────────────────────────────────────────────────

st.header("Active Holdings")
st.caption("These are the current investments in the DSRF trust account. 'Days Left' shows how long until each CD matures and needs to be reinvested.")

display_active = active[["Issuer", "Security_Type", "CUSIP", "Purchase_Date", "Maturity_Date", "Par", "Yield", "Days_Remaining", "Notes"]].copy()
display_active = display_active.sort_values("Maturity_Date")

st.dataframe(
    display_active,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Issuer": "Issuer",
        "Security_Type": "Type",
        "CUSIP": "CUSIP",
        "Purchase_Date": st.column_config.DateColumn("Purchased", format="MM/DD/YYYY"),
        "Maturity_Date": st.column_config.DateColumn("Maturity", format="MM/DD/YYYY"),
        "Par": st.column_config.NumberColumn("Par Amount", format="$%,.0f"),
        "Yield": st.column_config.NumberColumn("Yield", format="%.2f%%"),
        "Days_Remaining": st.column_config.NumberColumn("Days Left"),
        "Notes": "Notes",
    },
)

# ── Maturity Ladder ───────────────────────────────────────────────────────

st.header("Maturity Ladder")

ladder = active.sort_values("Maturity_Date").copy()
ladder["Label"] = ladder.apply(
    lambda r: f"{r['Issuer']}<br>{r['Security_Type']}<br>${r['Par']:,.0f} @ {r['Yield']:.2f}%", axis=1
)

# Color by urgency
def maturity_color(days):
    if days <= 30:
        return RED
    if days <= 90:
        return YELLOW
    if days <= 180:
        return BLUE
    return GREEN

ladder["Color"] = ladder["Days_Remaining"].apply(maturity_color)

fig_ladder = go.Figure()

for i, (_, row) in enumerate(ladder.iterrows()):
    fig_ladder.add_trace(go.Bar(
        x=[row["Days_Remaining"]],
        y=[row["Label"]],
        orientation="h",
        marker_color=row["Color"],
        text=f"{row['Maturity_Date'].strftime('%m/%d/%Y')} ({row['Days_Remaining']}d)",
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
        hovertemplate=(
            f"<b>{row['Issuer']} {row['Security_Type']}</b><br>"
            f"CUSIP: {row['CUSIP']}<br>"
            f"Par: ${row['Par']:,.0f}<br>"
            f"Yield: {row['Yield']:.2f}%<br>"
            f"Matures: {row['Maturity_Date'].strftime('%m/%d/%Y')}<br>"
            f"Days: {row['Days_Remaining']}<extra></extra>"
        ),
        showlegend=False,
    ))

fig_ladder.update_layout(
    title="Days to Maturity",
    xaxis_title="Days Remaining",
    barmode="stack",
)
style_chart(fig_ladder, height=250 + 60 * len(ladder))
fig_ladder.update_layout(
    yaxis=dict(tickfont=dict(size=11, color=FONT_COLOR)),
    xaxis=dict(gridcolor=GRID_COLOR),
)
st.plotly_chart(fig_ladder, use_container_width=True)

# ── FDIC Concentration ────────────────────────────────────────────────────

st.header("FDIC Concentration by Issuer")
st.caption(f"FDIC insurance limit: {fmt_dollar(FDIC_LIMIT)} per issuer")
st.caption("FDIC insurance covers up to $250,000 per bank. If we hold more than that at one institution and it fails, the excess is uninsured. This chart shows our exposure by issuer.")

issuer_totals = active.groupby("Issuer")["Par"].sum().reset_index()
issuer_totals.columns = ["Issuer", "Total_Par"]
issuer_totals = issuer_totals.sort_values("Total_Par", ascending=False)
issuer_totals["Pct"] = issuer_totals["Total_Par"] / issuer_totals["Total_Par"].sum() * 100
issuer_totals["Over_Limit"] = issuer_totals["Total_Par"] > FDIC_LIMIT

# Flag concentration warnings
over_limit = issuer_totals[issuer_totals["Over_Limit"]]
if not over_limit.empty:
    for _, row in over_limit.iterrows():
        excess = row["Total_Par"] - FDIC_LIMIT
        st.error(
            f"**FDIC WARNING:** {row['Issuer']} total exposure is "
            f"{fmt_dollar(row['Total_Par'])} — exceeds FDIC limit by {fmt_dollar(excess)}"
        )

col1, col2 = st.columns([1, 1])

with col1:
    fig_pie = px.pie(
        issuer_totals,
        names="Issuer",
        values="Total_Par",
        color_discrete_sequence=ACCENT_COLORS,
        hole=0.4,
    )
    fig_pie.update_traces(
        textinfo="label+value",
        texttemplate="%{label}<br>$%{value:,.0f}",
        textfont=dict(color=FONT_COLOR, size=12),
    )
    fig_pie.update_layout(title="Par Amount by Issuer")
    style_chart(fig_pie, height=350)
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    fig_bar = go.Figure()
    colors = [RED if over else GREEN for over in issuer_totals["Over_Limit"]]
    fig_bar.add_trace(go.Bar(
        x=issuer_totals["Issuer"],
        y=issuer_totals["Total_Par"],
        marker_color=colors,
        text=[fmt_dollar(v) for v in issuer_totals["Total_Par"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=12),
    ))
    fig_bar.add_hline(
        y=FDIC_LIMIT,
        line_dash="dash",
        line_color=YELLOW,
        annotation_text=f"FDIC Limit ({fmt_dollar(FDIC_LIMIT)})",
        annotation_font=dict(color=YELLOW, size=12),
        annotation_position="top right",
    )
    fig_bar.update_layout(title="Issuer Exposure vs FDIC Limit")
    style_chart(fig_bar, height=350)
    st.plotly_chart(fig_bar, use_container_width=True)

# ── Annual Income ─────────────────────────────────────────────────────────

st.header("Annual Interest Income")

active_income = active.copy()
active_income["Annual_Interest"] = active_income["Par"] * active_income["Yield"] / 100
total_income = active_income["Annual_Interest"].sum()

col1, col2 = st.columns([2, 1])
with col1:
    st.dataframe(
        active_income[["Issuer", "Security_Type", "Par", "Yield", "Annual_Interest"]].sort_values("Annual_Interest", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Par": st.column_config.NumberColumn("Par Amount", format="$%,.0f"),
            "Yield": st.column_config.NumberColumn("Yield", format="%.2f%%"),
            "Annual_Interest": st.column_config.NumberColumn("Annual Interest", format="$%,.0f"),
            "Security_Type": "Type",
        },
    )
with col2:
    st.metric("Total Annual Interest", fmt_dollar(total_income))
    st.markdown("*Assumes held to maturity*")

# ── Matured / History ─────────────────────────────────────────────────────

if not matured.empty:
    with st.expander(f"Matured Holdings ({len(matured)} positions)", expanded=False):
        st.dataframe(
            matured[["Issuer", "Security_Type", "CUSIP", "Purchase_Date", "Maturity_Date", "Par", "Yield", "Notes"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Security_Type": "Type",
                "Purchase_Date": st.column_config.DateColumn("Purchased", format="MM/DD/YYYY"),
                "Maturity_Date": st.column_config.DateColumn("Matured", format="MM/DD/YYYY"),
                "Par": st.column_config.NumberColumn("Par Amount", format="$%,.0f"),
                "Yield": st.column_config.NumberColumn("Yield", format="%.2f%%"),
            },
        )

# ── Trust Account Info ────────────────────────────────────────────────────

st.divider()
st.markdown(
    "**Trust Account:** 153155.4 &nbsp;|&nbsp; "
    "**Trustee:** UMB Bank, N.A. &nbsp;|&nbsp; "
    "**Contact:** Gena Mayer, VP Capital Markets — "
    "314.612.8016 / gena.mayer@umb.com"
)
