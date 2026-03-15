"""
Page 15: Board Actions
Track motions, votes, and action items from NSIA board meetings.
"""
import streamlit as st
import pandas as pd
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.theme import inject_css
from utils.auth import require_auth

st.set_page_config(page_title="Board Actions | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Board Actions")
st.caption("Track motions, votes, and action items from NSIA board meetings")

# ── Constants ────────────────────────────────────────────────────────────
MOTION_CATEGORIES = ["Financial", "Operations", "Governance", "Personnel", "Other"]
MOTION_OUTCOMES = ["Passed", "Failed", "Tabled", "Withdrawn"]
ACTION_STATUSES = ["Open", "In Progress", "Done"]

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "board_actions.xlsx")


# ── Data functions ───────────────────────────────────────────────────────
def load_motions() -> pd.DataFrame:
    """Load motions from the Motions sheet."""
    try:
        df = pd.read_excel(DATA_PATH, sheet_name="Motions", dtype={"id": str, "minutes_doc_id": str})
        if "meeting_date" in df.columns:
            df["meeting_date"] = pd.to_datetime(df["meeting_date"]).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "meeting_date", "motion", "category", "outcome",
                                     "votes_for", "votes_against", "votes_abstain", "notes", "minutes_doc_id"])


def load_actions() -> pd.DataFrame:
    """Load action items from the Action Items sheet."""
    try:
        df = pd.read_excel(DATA_PATH, sheet_name="Action Items", dtype={"id": str, "motion_id": str})
        for col in ["created_date", "due_date", "completed_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "motion_id", "created_date", "description",
                                     "assignee", "due_date", "status", "completed_date", "notes"])


def save_data(motions: pd.DataFrame, actions: pd.DataFrame):
    """Write both sheets back to the Excel file."""
    with pd.ExcelWriter(DATA_PATH, engine="openpyxl") as writer:
        motions.to_excel(writer, sheet_name="Motions", index=False)
        actions.to_excel(writer, sheet_name="Action Items", index=False)


# ── File uploader ────────────────────────────────────────────────────────
uploaded = st.file_uploader("Import board_actions.xlsx", type=["xlsx"], help="Upload an existing board actions file to import data")
if uploaded is not None:
    try:
        motions_up = pd.read_excel(uploaded, sheet_name="Motions", dtype={"id": str, "minutes_doc_id": str})
        actions_up = pd.read_excel(uploaded, sheet_name="Action Items", dtype={"id": str, "motion_id": str})
        save_data(motions_up, actions_up)
        st.success("Data imported successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error importing file: {e}")

# ── Load data ────────────────────────────────────────────────────────────
motions = load_motions()
actions = load_actions()

# ── Summary metrics ──────────────────────────────────────────────────────
today = date.today()

total_motions = len(motions)
open_actions = actions[actions["status"].isin(["Open", "In Progress"])] if not actions.empty and "status" in actions.columns else pd.DataFrame()

overdue_actions = pd.DataFrame()
due_soon_actions = pd.DataFrame()
if not open_actions.empty and "due_date" in open_actions.columns:
    open_actions_valid = open_actions.dropna(subset=["due_date"])
    overdue_actions = open_actions_valid[open_actions_valid["due_date"] < today]
    due_soon_actions = open_actions_valid[
        (open_actions_valid["due_date"] >= today) &
        (open_actions_valid["due_date"] <= today + timedelta(days=7))
    ]

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Total Motions", total_motions)
with m2:
    st.metric("Open Action Items", len(open_actions))
with m3:
    st.metric("Overdue", len(overdue_actions))
with m4:
    st.metric("Due This Week", len(due_soon_actions))

# ── Overdue alert cards ──────────────────────────────────────────────────
if not overdue_actions.empty:
    st.markdown("### Overdue Action Items")
    for _, row in overdue_actions.iterrows():
        days_late = (today - row["due_date"]).days
        assignee = row.get("assignee", "Unassigned") or "Unassigned"
        desc = row.get("description", "No description")
        st.markdown(
            f'<div style="padding:10px 14px;margin:6px 0;border-left:4px solid #eb144c;'
            f'background:rgba(235,20,76,0.08);border-radius:4px;">'
            f'<b style="color:#e6f1ff;">{desc}</b><br>'
            f'<span style="color:#a8b2d1;">Assignee: {assignee}</span> &nbsp; '
            f'<span style="color:#eb144c;font-weight:bold;">{days_late} day(s) late</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Due soon warning ────────────────────────────────────────────────────
if not due_soon_actions.empty:
    st.markdown("### Due This Week")
    for _, row in due_soon_actions.iterrows():
        days_until = (row["due_date"] - today).days
        assignee = row.get("assignee", "Unassigned") or "Unassigned"
        desc = row.get("description", "No description")
        label = "Today" if days_until == 0 else f"in {days_until} day(s)"
        st.markdown(
            f'<div style="padding:10px 14px;margin:6px 0;border-left:4px solid #fcb900;'
            f'background:rgba(252,185,0,0.08);border-radius:4px;">'
            f'<b style="color:#e6f1ff;">{desc}</b><br>'
            f'<span style="color:#a8b2d1;">Assignee: {assignee}</span> &nbsp; '
            f'<span style="color:#fcb900;font-weight:bold;">Due {label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Motions section ──────────────────────────────────────────────────────
st.markdown("---")
st.header("Motions")

if not motions.empty:
    st.dataframe(
        motions,
        use_container_width=True,
        hide_index=True,
        column_config={
            "meeting_date": st.column_config.DateColumn("Meeting Date"),
            "votes_for": st.column_config.NumberColumn("For"),
            "votes_against": st.column_config.NumberColumn("Against"),
            "votes_abstain": st.column_config.NumberColumn("Abstain"),
        },
    )
else:
    st.info("No motions recorded yet. Add one below.")

with st.expander("Add New Motion"):
    with st.form("add_motion_form", clear_on_submit=True):
        mot_date = st.date_input("Meeting Date", value=today)
        mot_text = st.text_area("Motion Text")
        mot_cat = st.selectbox("Category", MOTION_CATEGORIES)
        mot_outcome = st.selectbox("Outcome", MOTION_OUTCOMES)
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            mot_for = st.number_input("Votes For", min_value=0, value=0, step=1)
        with mc2:
            mot_against = st.number_input("Votes Against", min_value=0, value=0, step=1)
        with mc3:
            mot_abstain = st.number_input("Votes Abstain", min_value=0, value=0, step=1)
        mot_notes = st.text_input("Notes")
        mot_doc_id = st.text_input("Minutes Doc ID")
        mot_submit = st.form_submit_button("Add Motion")

        if mot_submit and mot_text.strip():
            new_motion = pd.DataFrame([{
                "id": str(uuid.uuid4())[:8],
                "meeting_date": mot_date,
                "motion": mot_text.strip(),
                "category": mot_cat,
                "outcome": mot_outcome,
                "votes_for": mot_for,
                "votes_against": mot_against,
                "votes_abstain": mot_abstain,
                "notes": mot_notes,
                "minutes_doc_id": mot_doc_id,
            }])
            motions = pd.concat([motions, new_motion], ignore_index=True)
            save_data(motions, actions)
            st.success("Motion added!")
            st.rerun()

# ── Action Items section ─────────────────────────────────────────────────
st.markdown("---")
st.header("Action Items")

if not actions.empty:
    open_items = actions[actions["status"] == "Open"]
    in_progress_items = actions[actions["status"] == "In Progress"]
    done_items = actions[actions["status"] == "Done"]

    col_open, col_prog, col_done = st.columns(3)

    with col_open:
        st.subheader(f"Open ({len(open_items)})")
        for _, row in open_items.iterrows():
            is_overdue = pd.notna(row.get("due_date")) and row["due_date"] < today
            border_color = "#eb144c" if is_overdue else "#0984e3"
            bg_color = "rgba(235,20,76,0.08)" if is_overdue else "rgba(9,132,227,0.08)"
            due_str = f"Due: {row['due_date']}" if pd.notna(row.get("due_date")) else "No due date"
            overdue_tag = f' <span style="color:#eb144c;font-weight:bold;">OVERDUE</span>' if is_overdue else ""
            st.markdown(
                f'<div style="padding:10px 14px;margin:6px 0;border-left:4px solid {border_color};'
                f'background:{bg_color};border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row.get("description", "")}</b><br>'
                f'<span style="color:#a8b2d1;">{row.get("assignee", "Unassigned") or "Unassigned"}</span> &nbsp; '
                f'<span style="color:#a8b2d1;">{due_str}</span>{overdue_tag}'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_prog:
        st.subheader(f"In Progress ({len(in_progress_items)})")
        for _, row in in_progress_items.iterrows():
            is_overdue = pd.notna(row.get("due_date")) and row["due_date"] < today
            border_color = "#eb144c" if is_overdue else "#fcb900"
            bg_color = "rgba(235,20,76,0.08)" if is_overdue else "rgba(252,185,0,0.08)"
            due_str = f"Due: {row['due_date']}" if pd.notna(row.get("due_date")) else "No due date"
            overdue_tag = f' <span style="color:#eb144c;font-weight:bold;">OVERDUE</span>' if is_overdue else ""
            st.markdown(
                f'<div style="padding:10px 14px;margin:6px 0;border-left:4px solid {border_color};'
                f'background:{bg_color};border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row.get("description", "")}</b><br>'
                f'<span style="color:#a8b2d1;">{row.get("assignee", "Unassigned") or "Unassigned"}</span> &nbsp; '
                f'<span style="color:#a8b2d1;">{due_str}</span>{overdue_tag}'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_done:
        st.subheader(f"Done ({len(done_items)})")
        for _, row in done_items.iterrows():
            completed = f"Completed: {row['completed_date']}" if pd.notna(row.get("completed_date")) else ""
            st.markdown(
                f'<div style="padding:10px 14px;margin:6px 0;border-left:4px solid #00d084;'
                f'background:rgba(0,208,132,0.08);border-radius:4px;">'
                f'<b style="color:#e6f1ff;">{row.get("description", "")}</b><br>'
                f'<span style="color:#a8b2d1;">{row.get("assignee", "Unassigned") or "Unassigned"}</span> &nbsp; '
                f'<span style="color:#a8b2d1;">{completed}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.info("No action items recorded yet. Add one below.")

# ── Add New Action Item ──────────────────────────────────────────────────
with st.expander("Add New Action Item"):
    with st.form("add_action_form", clear_on_submit=True):
        act_motion_id = st.text_input("Motion ID (optional)", help="Link to a motion by its ID")
        act_desc = st.text_area("Description")
        act_assignee = st.text_input("Assignee")
        act_due = st.date_input("Due Date", value=today + timedelta(days=14))
        act_status = st.selectbox("Status", ACTION_STATUSES)
        act_notes = st.text_input("Notes")
        act_submit = st.form_submit_button("Add Action Item")

        if act_submit and act_desc.strip():
            completed_dt = today if act_status == "Done" else None
            new_action = pd.DataFrame([{
                "id": str(uuid.uuid4())[:8],
                "motion_id": act_motion_id or None,
                "created_date": today,
                "description": act_desc.strip(),
                "assignee": act_assignee,
                "due_date": act_due,
                "status": act_status,
                "completed_date": completed_dt,
                "notes": act_notes,
            }])
            actions = pd.concat([actions, new_action], ignore_index=True)
            save_data(motions, actions)
            st.success("Action item added!")
            st.rerun()

# ── Update Action Item Status ────────────────────────────────────────────
open_or_ip = actions[actions["status"].isin(["Open", "In Progress"])] if not actions.empty and "status" in actions.columns else pd.DataFrame()

if not open_or_ip.empty:
    with st.expander("Update Action Item Status"):
        item_options = {
            f"{row['description'][:60]} ({row['assignee'] or 'Unassigned'})": row["id"]
            for _, row in open_or_ip.iterrows()
        }
        with st.form("update_status_form"):
            selected_label = st.selectbox("Select Action Item", list(item_options.keys()))
            new_status = st.selectbox("New Status", ACTION_STATUSES)
            update_submit = st.form_submit_button("Update Status")

            if update_submit and selected_label:
                selected_id = item_options[selected_label]
                idx = actions.index[actions["id"] == selected_id]
                if not idx.empty:
                    actions.loc[idx[0], "status"] = new_status
                    if new_status == "Done":
                        actions.loc[idx[0], "completed_date"] = today
                    save_data(motions, actions)
                    st.success(f"Status updated to {new_status}!")
                    st.rerun()
