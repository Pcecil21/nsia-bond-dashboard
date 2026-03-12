"""
Page 14: New Trier — NSIA Home Games
Hockey schedule for all 6 New Trier teams at North Shore Ice Arena.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css

st.set_page_config(page_title="New Trier | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()

st.title("New Trier Hockey")
st.caption("NSIA home games for all 6 teams")

from utils.data_loader import load_hockey_schedule

st.header("NSIA Home Games — All 6 Teams")
st.caption("Games played at NSIA Main & North Shore Ice Arena")
st.markdown(
    '*Source: [newtrierhockey.com/schedule](https://www.newtrierhockey.com/schedule)*'
)

schedule = load_hockey_schedule()

if schedule.empty:
    st.info("No schedule data available.")
    st.stop()

home = schedule.copy()
home["_date"] = pd.to_datetime(home["Date"], format="%b %d %Y")
today = pd.Timestamp.now().normalize()

played = home[home["_date"] < today]
upcoming = home[home["_date"] >= today]
team_count = home["Team"].nunique()

# ── KPIs ─────────────────────────────────────────────────────────────────
s1, s2, s3 = st.columns(3)
s1.metric("Total NSIA Home Games", len(home), f"across {team_count} teams")
s2.metric("Played", len(played))
s3.metric("Upcoming", len(upcoming))

# ── Games per team bar chart ─────────────────────────────────────────────
team_colors = {
    "Varsity 1 Green": "#00d084", "Varsity 2 Blue": "#0984e3",
    "Varsity 3 White": "#b2bec3", "Varsity 4 Gray": "#636e72",
    "JV 1": "#6c5ce7", "JV 2": "#fdcb6e",
}
team_counts = home["Team"].value_counts().reindex(team_colors.keys()).fillna(0).astype(int)
fig_teams = go.Figure(go.Bar(
    x=team_counts.index,
    y=team_counts.values,
    marker=dict(
        color=[team_colors.get(t, "#abb8c3") for t in team_counts.index],
        line=dict(width=1, color="rgba(255,255,255,0.3)"),
    ),
    text=[str(v) for v in team_counts.values],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=13),
    hovertemplate="<b>%{x}</b><br>%{y} home games<extra></extra>",
))
fig_teams.update_layout(
    title="NSIA Home Games by Team",
    yaxis_title="Number of Games",
    showlegend=False,
)
style_chart(fig_teams, 350)
st.plotly_chart(fig_teams, use_container_width=True)

# ── Monthly distribution ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("Games by Month")

home["Month"] = home["_date"].dt.to_period("M").astype(str)
monthly = home.groupby("Month").size().reset_index(name="Games")

fig_month = go.Figure(go.Bar(
    x=monthly["Month"],
    y=monthly["Games"],
    marker=dict(color="#0984e3", line=dict(width=1, color="rgba(255,255,255,0.3)")),
    text=monthly["Games"].astype(str),
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=13),
    hovertemplate="<b>%{x}</b><br>%{y} games<extra></extra>",
))
fig_month.update_layout(
    title="NSIA Home Games by Month",
    yaxis_title="Number of Games",
    showlegend=False,
)
style_chart(fig_month, 320)
st.plotly_chart(fig_month, use_container_width=True)

# ── Team filter + full schedule ──────────────────────────────────────────
st.markdown("---")
st.subheader("Full Schedule")

all_teams = sorted(home["Team"].unique())
selected_teams = st.multiselect("Filter by team", all_teams, default=all_teams)
filtered = home[home["Team"].isin(selected_teams)].copy()

filtered["Status"] = filtered["_date"].apply(lambda d: "Played" if d < today else "Upcoming")

display_home = filtered[["Team", "Date", "Time", "Opponent", "Type", "Location", "Status"]].copy()

def status_style(val):
    if val == "Played":
        return "color: #a8b2d1;"
    return "color: #0984e3; font-weight: bold"

st.dataframe(
    display_home.style.map(status_style, subset=["Status"]),
    use_container_width=True,
    hide_index=True,
)

# ── Upcoming games callout ───────────────────────────────────────────────
upcoming_filtered = filtered[filtered["Status"] == "Upcoming"].sort_values("_date")
if not upcoming_filtered.empty:
    st.markdown("---")
    st.subheader(f"Upcoming Home Games ({len(upcoming_filtered)})")
    for _, row in upcoming_filtered.iterrows():
        t_color = team_colors.get(row["Team"], "#abb8c3")
        st.markdown(
            f'<div style="padding:6px 12px;margin:4px 0;border-left:3px solid {t_color};'
            f'background:rgba(26,26,46,0.5);border-radius:4px;">'
            f'<span style="color:{t_color};font-weight:bold;">{row["Team"]}</span> &nbsp; '
            f'<span style="color:#e6f1ff;">{row["Date"]}</span> at {row["Time"]} — '
            f'<b style="color:#ccd6f6;">{row["Opponent"]}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )
