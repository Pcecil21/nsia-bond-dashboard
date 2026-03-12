"""
Page 9: Ice Utilization
Weekday/weekend ice allocation and Winnetka usage gap analysis.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, style_chart, inject_css
from utils.auth import require_auth, has_role, get_user_club

st.set_page_config(page_title="Ice Utilization | NSIA", layout="wide", page_icon=":ice_hockey:")

_username = require_auth()
_user_club = get_user_club()  # "Winnetka", "Wilmette", or None (admin/board see all)

CLUB_COLORS = {"NT": "#fcb900", "Winnetka": "#64ffda", "Wilmette": "#f78da7"}

inject_css()

st.title("Ice Utilization")
st.caption("Weekday & weekend ice allocation analysis and Winnetka usage gaps")

from utils.data_loader import (
    load_weekend_ice_summary,
    load_weekend_ice_breakdown,
    load_winnetka_nsia_usage,
    load_wilmette_nsia_usage,
    load_winnetka_weekend_summary,
    load_winnetka_day_level_gaps,
)

# ======================================================================
# Section 1: Weekend Allocation
# ======================================================================
st.header("Weekend Ice Allocation")

weekend = load_weekend_ice_summary()

for wknd in ["Weekend 1", "Weekend 2"]:
    wknd_data = weekend[weekend["Weekend"] == wknd]
    fig_we = go.Figure()

    for club in ["NT", "Winnetka", "Wilmette"]:
        club_row = wknd_data[wknd_data["Club"] == club]
        if club_row.empty:
            continue
        r = club_row.iloc[0]
        days = ["Saturday", "Sunday"]

        fig_we.add_trace(go.Bar(
            x=days,
            y=[r["Current Saturday"], r["Current Sunday"]],
            name=club,
            marker=dict(color=CLUB_COLORS[club],
                        line=dict(width=1, color="rgba(255,255,255,0.2)")),
            text=[f"{v:.1f}" for v in [r["Current Saturday"], r["Current Sunday"]]],
            textposition="outside",
            textfont=dict(size=10, color=FONT_COLOR),
            hovertemplate=f"<b>{club}</b><br>" + "%{x}: %{y:.1f}h<extra></extra>",
        ))

    fig_we.update_layout(
        title=f"{wknd} -- Ice Hours by Club",
        barmode="group",
        yaxis_title="Hours",
    )
    style_chart(fig_we, 380)
    st.plotly_chart(fig_we, use_container_width=True)

# Weekend summary table
with st.expander("Weekend Summary Table"):
    st.dataframe(
        weekend,
        use_container_width=True,
        hide_index=True,
        column_config={c: st.column_config.NumberColumn(format="%.1f")
                       for c in weekend.columns if c not in ("Club", "Weekend")},
    )

# ======================================================================
# Section 2b: Weekend Ice Breakdown (10-min slot detail)
# ======================================================================
st.markdown("---")
st.subheader("Weekend Ice Breakdown — Detailed Allocation")
st.caption("Wilmette & Winnetka contract ice — alternating weekends, Sep 1 - Mar 1")

ice = load_weekend_ice_breakdown()

if not ice.empty:
    org_colors = {"Winnetka": "#64ffda", "Wilmette": "#f78da7", "New Trier": "#fcb900"}

    nt_hrs = ice.loc[ice["Organization"] == "New Trier", "Weekend 1 Total (hrs)"].values[0]
    win_avg = (ice.loc[ice["Organization"] == "Winnetka", "Weekend 1 Total (hrs)"].values[0] +
               ice.loc[ice["Organization"] == "Winnetka", "Weekend 2 Total (hrs)"].values[0]) / 2
    wil_avg = (ice.loc[ice["Organization"] == "Wilmette", "Weekend 1 Total (hrs)"].values[0] +
               ice.loc[ice["Organization"] == "Wilmette", "Weekend 2 Total (hrs)"].values[0]) / 2
    avg_weekend = win_avg + wil_avg + nt_hrs

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg Weekend Hours", f"{avg_weekend:.1f} hrs", "Sat + Sun combined")
    k2.metric("Winnetka (avg)", f"{win_avg:.1f} hrs/wknd", f"{win_avg/avg_weekend*100:.0f}% of ice")
    k3.metric("Wilmette (avg)", f"{wil_avg:.1f} hrs/wknd", f"{wil_avg/avg_weekend*100:.0f}% of ice")
    k4.metric("New Trier", f"{nt_hrs:.1f} hrs/wknd", "Sun evenings only")

    col_w1, col_w2 = st.columns(2)

    with col_w1:
        fig_w1 = go.Figure()
        for _, row in ice.iterrows():
            org = row["Organization"]
            fig_w1.add_trace(go.Bar(
                x=["Saturday", "Sunday"],
                y=[row["Weekend 1 Saturday (hrs)"], row["Weekend 1 Sunday (hrs)"]],
                name=org,
                marker_color=org_colors.get(org, "#abb8c3"),
                text=[f"{row['Weekend 1 Saturday (hrs)']:.1f}h", f"{row['Weekend 1 Sunday (hrs)']:.1f}h"],
                textposition="inside",
                textfont=dict(color="#fff", size=12),
            ))
        fig_w1.update_layout(
            title="Weekend 1 - Ice Hours by Organization",
            barmode="stack", yaxis_title="Hours",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        )
        style_chart(fig_w1, 380)
        st.plotly_chart(fig_w1, use_container_width=True)

    with col_w2:
        fig_w2 = go.Figure()
        for _, row in ice.iterrows():
            org = row["Organization"]
            fig_w2.add_trace(go.Bar(
                x=["Saturday", "Sunday"],
                y=[row["Weekend 2 Saturday (hrs)"], row["Weekend 2 Sunday (hrs)"]],
                name=org,
                marker_color=org_colors.get(org, "#abb8c3"),
                text=[f"{row['Weekend 2 Saturday (hrs)']:.1f}h", f"{row['Weekend 2 Sunday (hrs)']:.1f}h"],
                textposition="inside",
                textfont=dict(color="#fff", size=12),
                showlegend=False,
            ))
        fig_w2.update_layout(
            title="Weekend 2 - Ice Hours by Organization",
            barmode="stack", yaxis_title="Hours",
        )
        style_chart(fig_w2, 380)
        st.plotly_chart(fig_w2, use_container_width=True)

    with st.expander("Weekend Ice Breakdown Table"):
        st.dataframe(
            ice,
            use_container_width=True,
            hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.1f")
                           for c in ice.columns if c != "Organization"},
        )

    st.info(
        "**Schedule Pattern:** Weekends alternate -- Weekend 1 has Winnetka on Saturday AM / "
        "Wilmette on Sunday AM; Weekend 2 reverses. "
        "New Trier gets Sunday evenings (5:30-8:30 PM) on both weekends. "
        "Schedule runs 8:00 AM - 9:20 PM."
    )

# ======================================================================
# Section 2c-shared: Weekend Exceptions Editor (shared by Winnetka & Wilmette)
# ======================================================================
st.markdown("---")
st.subheader("Weekend Exceptions")
st.caption(
    "Flag weekends affected by holidays, away tournaments, etc. "
    "Use date ranges for multi-weekend periods (e.g. Holiday Break). "
    "**Exclude=True** removes the weekend from utilization KPIs; "
    "**Exclude=False** flags it in the chart but still counts it."
)

import os as _os
from datetime import timedelta as _td

_exc_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "data", "weekend_exceptions.csv")
_exc_raw = pd.read_csv(_exc_path)
_exc_raw["StartDate"] = pd.to_datetime(_exc_raw["StartDate"]).dt.date
_exc_raw["EndDate"] = pd.to_datetime(_exc_raw["EndDate"]).dt.date
_exc_raw["Exclude"] = _exc_raw["Exclude"].str.upper() == "YES"
if "Team" not in _exc_raw.columns:
    _exc_raw["Team"] = "Both"
_exc_raw = _exc_raw.sort_values("StartDate").reset_index(drop=True)

if has_role("admin"):
    edited_exc = st.data_editor(
        _exc_raw,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "StartDate": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD", required=True),
            "EndDate": st.column_config.DateColumn("End Date", format="YYYY-MM-DD", required=True),
            "Reason": st.column_config.TextColumn("Reason", required=True),
            "Exclude": st.column_config.CheckboxColumn("Exclude from KPIs", default=False),
            "Team": st.column_config.SelectboxColumn("Applies To", options=["Both", "Winnetka", "Wilmette"], default="Both", required=True),
        },
        key="exc_editor",
    )

    if st.session_state.get("_exc_just_saved"):
        st.success("Exceptions saved successfully.")
        st.session_state["_exc_just_saved"] = False

    if st.button("Save Exceptions", type="primary"):
        save_df = edited_exc.copy()
        save_df["StartDate"] = pd.to_datetime(save_df["StartDate"]).dt.strftime("%Y-%m-%d")
        save_df["EndDate"] = pd.to_datetime(save_df["EndDate"]).dt.strftime("%Y-%m-%d")
        save_df["Exclude"] = save_df["Exclude"].map({True: "Yes", False: "No"})
        if "Team" not in save_df.columns:
            save_df["Team"] = "Both"
        save_df = save_df.sort_values("StartDate").reset_index(drop=True)
        save_df.to_csv(_exc_path, index=False)
        st.session_state["_exc_just_saved"] = True
        st.rerun()
else:
    # Read-only view for non-admin users
    st.dataframe(_exc_raw, use_container_width=True, hide_index=True)
    edited_exc = _exc_raw

# Expand date ranges into per-weekend-Saturday lookup dicts
def _expand_exceptions(exc_df, team: str):
    """Expand date-range exceptions into a dict of {saturday_date: reason} and a set of excluded saturdays.
    Only includes rows where Team matches the given team or is 'Both'."""
    reasons = {}
    excluded = set()
    for _, row in exc_df.iterrows():
        row_team = str(row.get("Team", "Both")).strip()
        if row_team not in ("Both", team):
            continue
        start = pd.Timestamp(row["StartDate"]).date() if not isinstance(row["StartDate"], type(None)) else None
        end = pd.Timestamp(row["EndDate"]).date() if not isinstance(row["EndDate"], type(None)) else None
        if start is None:
            continue
        if end is None or end < start:
            end = start + _td(days=1)
        reason = str(row.get("Reason", ""))
        is_excluded = bool(row.get("Exclude", False))
        d = start
        while d <= end:
            if d.weekday() == 5:  # Saturday
                reasons[d] = reason
                if is_excluded:
                    excluded.add(d)
            elif d.weekday() == 6:  # Sunday -> map to its Saturday
                sat = d - _td(days=1)
                if sat not in reasons:
                    reasons[sat] = reason
                if is_excluded and sat not in excluded:
                    excluded.add(sat)
            d += _td(days=1)
    return reasons, excluded

win_exc_reasons, win_exc_excluded = _expand_exceptions(edited_exc, "Winnetka")
wil_exc_reasons, wil_exc_excluded = _expand_exceptions(edited_exc, "Wilmette")

# ======================================================================
# Section 2c: Winnetka NSIA Ice -- Actual Usage vs Allocation
# ======================================================================
# Club reps only see their own club's section
_show_winnetka = _user_club is None or _user_club == "Winnetka"
_show_wilmette = _user_club is None or _user_club == "Wilmette"

if _show_winnetka:
    st.markdown("---")
    st.subheader("Winnetka Hockey -- NSIA Actual Usage vs Allocation")
    st.caption("Scraped from winnetkahockey.com/schedule -- Sep 2025 to Mar 2026 weekend days")
    st.markdown(
        '*Source: [winnetkahockey.com/schedule](https://www.winnetkahockey.com/schedule)*'
    )

    nsia_usage = load_winnetka_nsia_usage()

    if not nsia_usage.empty:

        # Allocated hours per weekend from the breakdown CSV
        alloc = load_weekend_ice_breakdown()
        win_alloc = alloc[alloc["Organization"] == "Winnetka"].iloc[0]
        alloc_w1_sat = win_alloc["Weekend 1 Saturday (hrs)"]
        alloc_w1_sun = win_alloc["Weekend 1 Sunday (hrs)"]
        alloc_w2_sat = win_alloc["Weekend 2 Saturday (hrs)"]
        alloc_w2_sun = win_alloc["Weekend 2 Sunday (hrs)"]

        # Calculate actual hours per day (add 10-min resurface between events, not after last)
        daily_usage = nsia_usage.groupby(["Date", "Day"]).agg(
            Event_Hours=("Hours", "sum"),
            Event_Count=("Hours", "count"),
        ).reset_index()
        daily_usage["Resurface_Hours"] = (daily_usage["Event_Count"] - 1).clip(lower=0) * (10 / 60)
        daily_usage["Actual_Hours"] = daily_usage["Event_Hours"] + daily_usage["Resurface_Hours"]

        # Determine weekend type (1 or 2) based on alternating pattern
        first_sat = pd.Timestamp("2025-09-06")
        daily_usage["WeekNum"] = ((daily_usage["Date"] - first_sat).dt.days // 7).astype(int)
        daily_usage["WeekendType"] = daily_usage["WeekNum"].apply(lambda w: 1 if (w // 1) % 2 == 0 else 2)

        # Map each day to its weekend Saturday date
        def get_weekend_sat(row):
            if row["Day"] == "Saturday":
                return row["Date"].date()
            else:
                return (row["Date"] - pd.Timedelta(days=1)).date()
        daily_usage["WeekendSat"] = daily_usage.apply(get_weekend_sat, axis=1)

        # Tag exceptions
        daily_usage["Exception"] = daily_usage["WeekendSat"].map(
            lambda d: win_exc_reasons.get(d, "")
        )
        daily_usage["Excluded"] = daily_usage["WeekendSat"].isin(win_exc_excluded)

        # Assign allocated hours based on weekend type and day
        def get_allocated(row):
            if row["WeekendType"] == 1:
                return alloc_w1_sat if row["Day"] == "Saturday" else alloc_w1_sun
            else:
                return alloc_w2_sat if row["Day"] == "Saturday" else alloc_w2_sun
        daily_usage["Allocated_Hours"] = daily_usage.apply(get_allocated, axis=1)
        daily_usage["Gap_Hours"] = daily_usage["Allocated_Hours"] - daily_usage["Actual_Hours"]
        daily_usage["Utilization_Pct"] = (daily_usage["Actual_Hours"] / daily_usage["Allocated_Hours"] * 100).round(1)

        # Split normal vs excluded
        normal = daily_usage[~daily_usage["Excluded"]]
        excluded = daily_usage[daily_usage["Excluded"]]

        # KPIs -- show both overall and normal-weekends-only
        total_actual = daily_usage["Actual_Hours"].sum()
        total_allocated = daily_usage["Allocated_Hours"].sum()
        overall_util = (total_actual / total_allocated * 100) if total_allocated > 0 else 0

        normal_actual = normal["Actual_Hours"].sum()
        normal_allocated = normal["Allocated_Hours"].sum()
        normal_util = (normal_actual / normal_allocated * 100) if normal_allocated > 0 else 0
        normal_gap = normal_allocated - normal_actual

        total_events = len(nsia_usage)
        n_excluded = excluded["WeekendSat"].nunique()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total NSIA Events", f"{total_events}", "Games + Practices")
        k2.metric("Normal Weekend Utilization", f"{normal_util:.0f}%",
                  delta=f"{normal_gap:.1f} hrs gap" if normal_gap > 0 else "On target",
                  delta_color="inverse" if normal_gap > 0 else "normal")
        k3.metric("Overall Utilization (all)", f"{overall_util:.0f}%",
                  f"includes {n_excluded} excluded weekends")
        k4.metric("Actual / Allocated (normal)", f"{normal_actual:.1f} / {normal_allocated:.1f} hrs")

        # Weekly utilization bar chart -- color-coded by exception status
        wknd_usage = daily_usage.groupby("WeekendSat").agg(
            Actual=("Actual_Hours", "sum"),
            Allocated=("Allocated_Hours", "sum"),
            Exception=("Exception", "first"),
            Excluded=("Excluded", "first"),
        ).reset_index().sort_values("WeekendSat")
        wknd_usage["Utilization"] = (wknd_usage["Actual"] / wknd_usage["Allocated"] * 100).round(1)
        wknd_usage["Label"] = wknd_usage["WeekendSat"].apply(lambda d: d.strftime("%b %d"))

        # Split into normal, flagged (exception but not excluded), and excluded
        wk_normal = wknd_usage[(wknd_usage["Exception"] == "") & (~wknd_usage["Excluded"])]
        wk_flagged = wknd_usage[(wknd_usage["Exception"] != "") & (~wknd_usage["Excluded"])]
        wk_excluded = wknd_usage[wknd_usage["Excluded"]]

        fig_wk = go.Figure()

        # Allocated baseline (all weekends)
        fig_wk.add_trace(go.Bar(
            x=wknd_usage["Label"], y=wknd_usage["Allocated"],
            name="Allocated",
            marker=dict(color="rgba(142,209,252,0.3)", line=dict(width=1, color="rgba(255,255,255,0.15)")),
            hovertemplate="<b>%{x}</b><br>Allocated: %{y:.1f}h<extra></extra>",
        ))

        # Normal weekends
        if not wk_normal.empty:
            fig_wk.add_trace(go.Bar(
                x=wk_normal["Label"], y=wk_normal["Actual"],
                name="Used (normal)",
                marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in wk_normal["Utilization"]],
                textposition="outside", textfont=dict(color=FONT_COLOR, size=9),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<extra></extra>",
            ))

        # Flagged weekends (away tournaments etc -- counted but noted)
        if not wk_flagged.empty:
            fig_wk.add_trace(go.Bar(
                x=wk_flagged["Label"], y=wk_flagged["Actual"],
                name="Used (flagged)",
                marker=dict(color="#fcb900", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in wk_flagged["Utilization"]],
                textposition="outside", textfont=dict(color="#fcb900", size=9),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>%{customdata}<extra></extra>",
                customdata=wk_flagged["Exception"],
            ))

        # Excluded weekends (holidays -- grayed out)
        if not wk_excluded.empty:
            fig_wk.add_trace(go.Bar(
                x=wk_excluded["Label"], y=wk_excluded["Actual"],
                name="Used (excluded)",
                marker=dict(color="#636e72", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[r["Exception"][:12] for _, r in wk_excluded.iterrows()],
                textposition="outside", textfont=dict(color="#636e72", size=8),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>EXCLUDED: %{customdata}<extra></extra>",
                customdata=wk_excluded["Exception"],
            ))

        fig_wk.update_layout(
            title="Winnetka NSIA Weekend Ice -- Weekly Allocated vs Actual",
            barmode="overlay", yaxis_title="Hours",
            xaxis=dict(tickangle=-45),
        )
        style_chart(fig_wk, 450)
        st.plotly_chart(fig_wk, use_container_width=True)

        # Monthly utilization chart (normal weekends only)
        normal_monthly = normal.copy()
        normal_monthly["Month"] = normal_monthly["Date"].dt.to_period("M").astype(str)
        monthly = normal_monthly.groupby("Month").agg(
            Actual=("Actual_Hours", "sum"),
            Allocated=("Allocated_Hours", "sum"),
        ).reset_index()
        monthly["Utilization"] = (monthly["Actual"] / monthly["Allocated"] * 100).round(1)

        fig_util = go.Figure()
        fig_util.add_trace(go.Bar(
            x=monthly["Month"], y=monthly["Allocated"],
            name="Allocated Hours",
            marker=dict(color="#8ed1fc", line=dict(width=1, color="rgba(255,255,255,0.2)")),
            hovertemplate="<b>%{x}</b><br>Allocated: %{y:.1f}h<extra></extra>",
        ))
        fig_util.add_trace(go.Bar(
            x=monthly["Month"], y=monthly["Actual"],
            name="Actual Hours Used",
            marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
            text=[f"{v:.0f}%" for v in monthly["Utilization"]],
            textposition="outside",
            textfont=dict(color=FONT_COLOR, size=11),
            hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>Utilization: %{text}<extra></extra>",
        ))
        fig_util.update_layout(
            title="Monthly Allocated vs Actual (normal weekends only)",
            barmode="group", yaxis_title="Hours",
        )
        style_chart(fig_util, 400)
        st.plotly_chart(fig_util, use_container_width=True)

        # Game vs Practice breakdown
        type_counts = nsia_usage.groupby("Type").agg(
            Events=("Hours", "count"),
            Hours=("Hours", "sum"),
        ).reset_index()

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            type_colors = {"Game": "#64ffda", "Practice": "#f78da7", "Unknown": "#abb8c3"}
            fig_type = go.Figure(go.Pie(
                labels=type_counts["Type"],
                values=type_counts["Hours"],
                marker=dict(colors=[type_colors.get(t, "#abb8c3") for t in type_counts["Type"]]),
                textinfo="label+percent",
                textfont=dict(color="#fff"),
                hovertemplate="<b>%{label}</b><br>%{value:.1f} hrs (%{percent})<extra></extra>",
            ))
            fig_type.update_layout(title="Hours by Type (Game vs Practice)")
            style_chart(fig_type, 350)
            st.plotly_chart(fig_type, use_container_width=True)

        with col_t2:
            # Saturday vs Sunday usage (normal only)
            day_summary = normal.groupby("Day").agg(
                Actual=("Actual_Hours", "sum"),
                Allocated=("Allocated_Hours", "sum"),
            ).reset_index()
            day_summary["Utilization"] = (day_summary["Actual"] / day_summary["Allocated"] * 100).round(1)

            fig_day_util = go.Figure()
            fig_day_util.add_trace(go.Bar(
                x=day_summary["Day"], y=day_summary["Allocated"],
                name="Allocated",
                marker=dict(color="#8ed1fc", line=dict(width=1, color="rgba(255,255,255,0.2)")),
            ))
            fig_day_util.add_trace(go.Bar(
                x=day_summary["Day"], y=day_summary["Actual"],
                name="Used",
                marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in day_summary["Utilization"]],
                textposition="outside",
                textfont=dict(color=FONT_COLOR, size=12),
            ))
            fig_day_util.update_layout(
                title="Saturday vs Sunday Utilization (normal weekends)",
                barmode="group", yaxis_title="Hours",
            )
            style_chart(fig_day_util, 350)
            st.plotly_chart(fig_day_util, use_container_width=True)

        # Full event table
        with st.expander("All Winnetka NSIA Weekend Events"):
            display = nsia_usage[["Date", "Day", "StartTime", "EndTime", "Hours", "Location", "Type", "Event"]].copy()
            display["Date"] = display["Date"].dt.strftime("%b %d %Y")
            st.dataframe(display, use_container_width=True, hide_index=True)

# ======================================================================
# Section 2d: Wilmette (Jr. Trevians) NSIA Ice -- Actual Usage vs Allocation
# ======================================================================
if _show_wilmette:
    st.markdown("---")
    st.subheader("Wilmette (Jr. Trevians) -- NSIA Actual Usage vs Allocation")
    st.caption("Scraped from jrtrevianshockey.com/schedule -- Sep 2025 to Mar 2026 weekend days")
    st.markdown(
        '*Source: [jrtrevianshockey.com/schedule](https://www.jrtrevianshockey.com/schedule)*'
    )

    wilmette_usage = load_wilmette_nsia_usage()

    if not wilmette_usage.empty:

        # Allocated hours per weekend from the breakdown CSV
        wil_alloc_df = load_weekend_ice_breakdown()
        wil_alloc_row = wil_alloc_df[wil_alloc_df["Organization"] == "Wilmette"].iloc[0]
        wil_alloc_w1_sat = wil_alloc_row["Weekend 1 Saturday (hrs)"]
        wil_alloc_w1_sun = wil_alloc_row["Weekend 1 Sunday (hrs)"]
        wil_alloc_w2_sat = wil_alloc_row["Weekend 2 Saturday (hrs)"]
        wil_alloc_w2_sun = wil_alloc_row["Weekend 2 Sunday (hrs)"]

        # Calculate actual hours per day (add 10-min resurface between events, not after last)
        wil_daily = wilmette_usage.groupby(["Date", "Day"]).agg(
            Event_Hours=("Hours", "sum"),
            Event_Count=("Hours", "count"),
        ).reset_index()
        wil_daily["Resurface_Hours"] = (wil_daily["Event_Count"] - 1).clip(lower=0) * (10 / 60)
        wil_daily["Actual_Hours"] = wil_daily["Event_Hours"] + wil_daily["Resurface_Hours"]

        # Determine weekend type (1 or 2) based on alternating pattern
        wil_first_sat = pd.Timestamp("2025-09-06")
        wil_daily["WeekNum"] = ((wil_daily["Date"] - wil_first_sat).dt.days // 7).astype(int)
        wil_daily["WeekendType"] = wil_daily["WeekNum"].apply(lambda w: 1 if (w // 1) % 2 == 0 else 2)

        # Map each day to its weekend Saturday date
        def wil_get_weekend_sat(row):
            if row["Day"] == "Saturday":
                return row["Date"].date()
            else:
                return (row["Date"] - pd.Timedelta(days=1)).date()
        wil_daily["WeekendSat"] = wil_daily.apply(wil_get_weekend_sat, axis=1)

        # Tag exceptions (using Wilmette-specific expanded exceptions)
        wil_daily["Exception"] = wil_daily["WeekendSat"].map(
            lambda d: wil_exc_reasons.get(d, "")
        )
        wil_daily["Excluded"] = wil_daily["WeekendSat"].isin(wil_exc_excluded)

        # Assign allocated hours based on weekend type and day
        def wil_get_allocated(row):
            if row["WeekendType"] == 1:
                return wil_alloc_w1_sat if row["Day"] == "Saturday" else wil_alloc_w1_sun
            else:
                return wil_alloc_w2_sat if row["Day"] == "Saturday" else wil_alloc_w2_sun
        wil_daily["Allocated_Hours"] = wil_daily.apply(wil_get_allocated, axis=1)
        wil_daily["Gap_Hours"] = wil_daily["Allocated_Hours"] - wil_daily["Actual_Hours"]
        wil_daily["Utilization_Pct"] = (wil_daily["Actual_Hours"] / wil_daily["Allocated_Hours"] * 100).round(1)

        # Split normal vs excluded
        wil_normal = wil_daily[~wil_daily["Excluded"]]
        wil_excluded_data = wil_daily[wil_daily["Excluded"]]

        # KPIs
        wil_total_actual = wil_daily["Actual_Hours"].sum()
        wil_total_allocated = wil_daily["Allocated_Hours"].sum()
        wil_overall_util = (wil_total_actual / wil_total_allocated * 100) if wil_total_allocated > 0 else 0

        wil_normal_actual = wil_normal["Actual_Hours"].sum()
        wil_normal_allocated = wil_normal["Allocated_Hours"].sum()
        wil_normal_util = (wil_normal_actual / wil_normal_allocated * 100) if wil_normal_allocated > 0 else 0
        wil_normal_gap = wil_normal_allocated - wil_normal_actual

        wil_total_events = len(wilmette_usage)
        wil_n_excluded = wil_excluded_data["WeekendSat"].nunique()

        wk1, wk2, wk3, wk4 = st.columns(4)
        wk1.metric("Total NSIA Events", f"{wil_total_events}", "Games + Practices")
        wk2.metric("Normal Weekend Utilization", f"{wil_normal_util:.0f}%",
                   delta=f"{wil_normal_gap:.1f} hrs gap" if wil_normal_gap > 0 else "On target",
                   delta_color="inverse" if wil_normal_gap > 0 else "normal")
        wk3.metric("Overall Utilization (all)", f"{wil_overall_util:.0f}%",
                   f"includes {wil_n_excluded} excluded weekends")
        wk4.metric("Actual / Allocated (normal)", f"{wil_normal_actual:.1f} / {wil_normal_allocated:.1f} hrs")

        # Weekly utilization bar chart
        wil_wknd = wil_daily.groupby("WeekendSat").agg(
            Actual=("Actual_Hours", "sum"),
            Allocated=("Allocated_Hours", "sum"),
            Exception=("Exception", "first"),
            Excluded=("Excluded", "first"),
        ).reset_index().sort_values("WeekendSat")
        wil_wknd["Utilization"] = (wil_wknd["Actual"] / wil_wknd["Allocated"] * 100).round(1)
        wil_wknd["Label"] = wil_wknd["WeekendSat"].apply(lambda d: d.strftime("%b %d"))

        wil_wk_normal = wil_wknd[(wil_wknd["Exception"] == "") & (~wil_wknd["Excluded"])]
        wil_wk_flagged = wil_wknd[(wil_wknd["Exception"] != "") & (~wil_wknd["Excluded"])]
        wil_wk_excluded = wil_wknd[wil_wknd["Excluded"]]

        fig_wil_wk = go.Figure()

        # Allocated baseline
        fig_wil_wk.add_trace(go.Bar(
            x=wil_wknd["Label"], y=wil_wknd["Allocated"],
            name="Allocated",
            marker=dict(color="rgba(247,141,167,0.3)", line=dict(width=1, color="rgba(255,255,255,0.15)")),
            hovertemplate="<b>%{x}</b><br>Allocated: %{y:.1f}h<extra></extra>",
        ))

        # Normal weekends
        if not wil_wk_normal.empty:
            fig_wil_wk.add_trace(go.Bar(
                x=wil_wk_normal["Label"], y=wil_wk_normal["Actual"],
                name="Used (normal)",
                marker=dict(color="#f78da7", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in wil_wk_normal["Utilization"]],
                textposition="outside", textfont=dict(color=FONT_COLOR, size=9),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<extra></extra>",
            ))

        # Flagged weekends
        if not wil_wk_flagged.empty:
            fig_wil_wk.add_trace(go.Bar(
                x=wil_wk_flagged["Label"], y=wil_wk_flagged["Actual"],
                name="Used (flagged)",
                marker=dict(color="#fcb900", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in wil_wk_flagged["Utilization"]],
                textposition="outside", textfont=dict(color="#fcb900", size=9),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>%{customdata}<extra></extra>",
                customdata=wil_wk_flagged["Exception"],
            ))

        # Excluded weekends
        if not wil_wk_excluded.empty:
            fig_wil_wk.add_trace(go.Bar(
                x=wil_wk_excluded["Label"], y=wil_wk_excluded["Actual"],
                name="Used (excluded)",
                marker=dict(color="#636e72", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[r["Exception"][:12] for _, r in wil_wk_excluded.iterrows()],
                textposition="outside", textfont=dict(color="#636e72", size=8),
                hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>EXCLUDED: %{customdata}<extra></extra>",
                customdata=wil_wk_excluded["Exception"],
            ))

        fig_wil_wk.update_layout(
            title="Wilmette NSIA Weekend Ice -- Weekly Allocated vs Actual",
            barmode="overlay", yaxis_title="Hours",
            xaxis=dict(tickangle=-45),
        )
        style_chart(fig_wil_wk, 450)
        st.plotly_chart(fig_wil_wk, use_container_width=True)

        # Monthly utilization chart (normal weekends only)
        wil_normal_monthly = wil_normal.copy()
        wil_normal_monthly["Month"] = wil_normal_monthly["Date"].dt.to_period("M").astype(str)
        wil_monthly = wil_normal_monthly.groupby("Month").agg(
            Actual=("Actual_Hours", "sum"),
            Allocated=("Allocated_Hours", "sum"),
        ).reset_index()
        wil_monthly["Utilization"] = (wil_monthly["Actual"] / wil_monthly["Allocated"] * 100).round(1)

        fig_wil_util = go.Figure()
        fig_wil_util.add_trace(go.Bar(
            x=wil_monthly["Month"], y=wil_monthly["Allocated"],
            name="Allocated Hours",
            marker=dict(color="#f78da7", opacity=0.4, line=dict(width=1, color="rgba(255,255,255,0.2)")),
            hovertemplate="<b>%{x}</b><br>Allocated: %{y:.1f}h<extra></extra>",
        ))
        fig_wil_util.add_trace(go.Bar(
            x=wil_monthly["Month"], y=wil_monthly["Actual"],
            name="Actual Hours Used",
            marker=dict(color="#f78da7", line=dict(width=1, color="rgba(255,255,255,0.2)")),
            text=[f"{v:.0f}%" for v in wil_monthly["Utilization"]],
            textposition="outside",
            textfont=dict(color=FONT_COLOR, size=11),
            hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<br>Utilization: %{text}<extra></extra>",
        ))
        fig_wil_util.update_layout(
            title="Monthly Allocated vs Actual (normal weekends only)",
            barmode="group", yaxis_title="Hours",
        )
        style_chart(fig_wil_util, 400)
        st.plotly_chart(fig_wil_util, use_container_width=True)

        # Game vs Practice breakdown
        wil_type_counts = wilmette_usage.groupby("Type").agg(
            Events=("Hours", "count"),
            Hours=("Hours", "sum"),
        ).reset_index()

        col_wt1, col_wt2 = st.columns(2)
        with col_wt1:
            wil_type_colors = {"Game": "#f78da7", "Practice": "#64ffda", "Unknown": "#abb8c3"}
            fig_wil_type = go.Figure(go.Pie(
                labels=wil_type_counts["Type"],
                values=wil_type_counts["Hours"],
                marker=dict(colors=[wil_type_colors.get(t, "#abb8c3") for t in wil_type_counts["Type"]]),
                textinfo="label+percent",
                textfont=dict(color="#fff"),
                hovertemplate="<b>%{label}</b><br>%{value:.1f} hrs (%{percent})<extra></extra>",
            ))
            fig_wil_type.update_layout(title="Hours by Type (Game vs Practice)")
            style_chart(fig_wil_type, 350)
            st.plotly_chart(fig_wil_type, use_container_width=True)

        with col_wt2:
            # Saturday vs Sunday usage (normal only)
            wil_day_summary = wil_normal.groupby("Day").agg(
                Actual=("Actual_Hours", "sum"),
                Allocated=("Allocated_Hours", "sum"),
            ).reset_index()
            wil_day_summary["Utilization"] = (wil_day_summary["Actual"] / wil_day_summary["Allocated"] * 100).round(1)

            fig_wil_day = go.Figure()
            fig_wil_day.add_trace(go.Bar(
                x=wil_day_summary["Day"], y=wil_day_summary["Allocated"],
                name="Allocated",
                marker=dict(color="rgba(247,141,167,0.4)", line=dict(width=1, color="rgba(255,255,255,0.2)")),
            ))
            fig_wil_day.add_trace(go.Bar(
                x=wil_day_summary["Day"], y=wil_day_summary["Actual"],
                name="Used",
                marker=dict(color="#f78da7", line=dict(width=1, color="rgba(255,255,255,0.2)")),
                text=[f"{v:.0f}%" for v in wil_day_summary["Utilization"]],
                textposition="outside",
                textfont=dict(color=FONT_COLOR, size=12),
            ))
            fig_wil_day.update_layout(
                title="Saturday vs Sunday Utilization (normal weekends)",
                barmode="group", yaxis_title="Hours",
            )
            style_chart(fig_wil_day, 350)
            st.plotly_chart(fig_wil_day, use_container_width=True)

        # Full event table
        with st.expander("All Wilmette NSIA Weekend Events"):
            wil_display = wilmette_usage[["Date", "Day", "StartTime", "EndTime", "Hours", "Location", "Type", "Event"]].copy()
            wil_display["Date"] = wil_display["Date"].dt.strftime("%b %d %Y")
            st.dataframe(wil_display, use_container_width=True, hide_index=True)

# ======================================================================
# Section 3: Winnetka Usage Gaps
# ======================================================================
if not _show_winnetka:
    st.stop()  # nothing more for non-Winnetka users

st.markdown("---")
st.header("Winnetka Usage Gap Analysis")

wk_summary = load_winnetka_weekend_summary()
day_gaps = load_winnetka_day_level_gaps()

num_weekends = len(wk_summary)
total_gap = wk_summary["Gap_Total"].sum()
pct_underused = (wk_summary["Underused_Weekend"] == "YES").sum() / num_weekends * 100

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Weekends Analyzed", str(num_weekends))
with col2:
    st.metric("Total Gap Hours", f"{total_gap:.1f}h")
with col3:
    st.metric("% Underused Weekends", f"{pct_underused:.0f}%",
              delta="All weekends flagged" if pct_underused == 100 else None,
              delta_color="inverse" if pct_underused > 50 else "normal")

# Bar chart: owned vs used per weekend
fig_gaps = go.Figure()
wk_labels = [pd.Timestamp(d).strftime("%b %d") for d in wk_summary["WeekendStart"]]
fig_gaps.add_trace(go.Bar(
    x=wk_labels,
    y=wk_summary["TotalHours_club"],
    name="Owned Hours",
    marker=dict(color="#8ed1fc", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    hovertemplate="<b>%{x}</b><br>Owned: %{y:.1f}h<extra></extra>",
))
fig_gaps.add_trace(go.Bar(
    x=wk_labels,
    y=wk_summary["TotalHours_FriToSun_WithCut"],
    name="Used Hours",
    marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    hovertemplate="<b>%{x}</b><br>Used: %{y:.1f}h<extra></extra>",
))
fig_gaps.update_layout(
    title="Winnetka: Owned vs Used Hours per Weekend (Fri–Sun)",
    barmode="group",
    yaxis_title="Hours",
    xaxis=dict(tickangle=-45),
)
style_chart(fig_gaps, 420)
st.plotly_chart(fig_gaps, use_container_width=True)

# Day-level breakdown
st.subheader("Day-Level Gap Breakdown")

day_agg = day_gaps.groupby("Day")[["Club_Owned_Hours", "Used_Hours_WithCut", "Unused_Hours"]].sum().reset_index()
day_order = ["Friday", "Saturday", "Sunday"]
day_agg["Day"] = pd.Categorical(day_agg["Day"], categories=day_order, ordered=True)
day_agg = day_agg.sort_values("Day")

fig_day = go.Figure()
fig_day.add_trace(go.Bar(
    x=day_agg["Day"], y=day_agg["Club_Owned_Hours"],
    name="Owned", marker=dict(color="#8ed1fc"),
    hovertemplate="%{x}<br>Owned: %{y:.1f}h<extra></extra>",
))
fig_day.add_trace(go.Bar(
    x=day_agg["Day"], y=day_agg["Used_Hours_WithCut"],
    name="Used", marker=dict(color="#64ffda"),
    hovertemplate="%{x}<br>Used: %{y:.1f}h<extra></extra>",
))
fig_day.add_trace(go.Bar(
    x=day_agg["Day"], y=day_agg["Unused_Hours"],
    name="Gap (Unused)", marker=dict(color="#eb144c"),
    hovertemplate="%{x}<br>Gap: %{y:.1f}h<extra></extra>",
))
fig_day.update_layout(
    title="Usage Gaps by Day of Week (All Weekends Combined)",
    barmode="group",
    yaxis_title="Hours",
)
style_chart(fig_day, 380)
st.plotly_chart(fig_day, use_container_width=True)

# Detail tables in expander
with st.expander("Weekend Summary Detail"):
    st.dataframe(
        wk_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "WeekendStart": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "WeekendEnd": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "Gap_Total": st.column_config.NumberColumn("Gap (hrs)", format="%.1f"),
            "TotalHours_club": st.column_config.NumberColumn("Owned (hrs)", format="%.1f"),
            "TotalHours_FriToSun_WithCut": st.column_config.NumberColumn("Used (hrs)", format="%.1f"),
        },
    )

with st.expander("Day-Level Gap Detail"):
    st.dataframe(
        day_gaps,
        use_container_width=True,
        hide_index=True,
        column_config={
            "WeekendStart": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "WeekendEnd": st.column_config.DateColumn(format="MM/DD/YYYY"),
            "Club_Owned_Hours": st.column_config.NumberColumn(format="%.1f"),
            "Used_Hours_WithCut": st.column_config.NumberColumn(format="%.1f"),
            "Unused_Hours": st.column_config.NumberColumn(format="%.1f"),
        },
    )

# Warning callout
st.warning(
    "**Underutilization Alert:** 100% of analyzed weekends show Winnetka ice time going unused. "
    "Total gap across all weekends: **{:.1f} hours**. Weekend 6 is missing from the sequence. "
    "This represents contracted ice time that Winnetka is paying for but not using — "
    "an opportunity for either schedule optimization or reallocation to other clubs.".format(total_gap)
)
