"""
Page 16: Vendor Master
Auto-extract vendors from bills and GL data, fuzzy dedup, editable master table.
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.theme import (
    FONT_COLOR, CYAN, RED, YELLOW, GREEN, BG_CARD, BG_CARD_END, BORDER_COLOR,
    TITLE_COLOR, VALUE_COLOR, inject_css, style_chart, fmt_dollar, fmt_compact,
)
from utils.auth import require_auth
from utils.vendor_extractor import (
    extract_vendors_from_bills,
    extract_vendors_from_gl,
    fuzzy_dedup,
    apply_merges,
    merge_with_existing,
    MANUAL_FIELDS,
)

st.set_page_config(page_title="Vendor Master | NSIA", layout="wide", page_icon=":ice_hockey:")
inject_css()
require_auth()

DATA_DIR = Path(__file__).parent.parent / "data"
VENDOR_MASTER_PATH = DATA_DIR / "vendor_master.csv"
BILLS_PATH = DATA_DIR / "bills_summary.xlsx"
GL_PATH = DATA_DIR / "general_ledger.xlsx"

RISK_OPTIONS = [None, "Low", "Medium", "High"]
CATEGORY_OPTIONS = [
    "Utilities", "Insurance", "Management", "Maintenance",
    "Professional Services", "Other",
]

st.title("Vendor Master")
st.caption("Centralized vendor registry with contract tracking, risk flags, and spend analytics")

# ── Sidebar: Extract Vendors ────────────────────────────────────────────
st.sidebar.markdown("### Data Extraction")

if st.sidebar.button("Extract Vendors from Data", type="primary", use_container_width=True):
    with st.spinner("Extracting vendors from bills and GL data..."):
        # Read bills
        if BILLS_PATH.exists():
            bills_df = pd.read_excel(BILLS_PATH)
            bills_vendors = extract_vendors_from_bills(bills_df)
        else:
            bills_vendors = pd.DataFrame()
            st.sidebar.warning("bills_summary.xlsx not found")

        # Only use GL as fallback — GL "Payee" column contains raw bank
        # transaction descriptions (with dates), not clean vendor names.
        # Bills data is the authoritative vendor source.
        if bills_vendors.empty and GL_PATH.exists():
            gl_df = pd.read_excel(GL_PATH, header=None)
            gl_vendors = extract_vendors_from_gl(gl_df)
        else:
            gl_vendors = pd.DataFrame()

        # Use bills as primary source
        if not bills_vendors.empty:
            combined = bills_vendors
        elif not gl_vendors.empty:
            combined = gl_vendors
        else:
            combined = pd.DataFrame()
            st.sidebar.error("No vendor data found")

        if not combined.empty:
            # Merge with existing to preserve manual edits
            if VENDOR_MASTER_PATH.exists():
                existing = pd.read_csv(VENDOR_MASTER_PATH)
                combined = merge_with_existing(combined, existing)

            # Run fuzzy dedup
            proposed_merges = fuzzy_dedup(combined)

            st.session_state["vendor_extracted"] = combined
            st.session_state["vendor_proposed_merges"] = proposed_merges
            st.sidebar.success(
                f"Extracted {len(combined)} vendors. "
                f"{len(proposed_merges)} potential duplicate(s) found."
            )

# ── Fuzzy Match Review ──────────────────────────────────────────────────
if "vendor_proposed_merges" in st.session_state and st.session_state["vendor_proposed_merges"]:
    st.markdown("---")
    st.markdown("### Fuzzy Match Review")
    st.markdown(
        "The following vendor pairs look like potential duplicates. "
        "Check the ones you want to merge, then save."
    )

    merges = st.session_state["vendor_proposed_merges"]
    approved = []

    for i, m in enumerate(merges):
        col1, col2, col3 = st.columns([4, 4, 2])
        with col1:
            st.markdown(f"**Keep:** {m['name_keep']}")
        with col2:
            st.markdown(f"**Merge:** {m['name_merge']}")
        with col3:
            st.markdown(f"Score: **{m['score']:.0%}**")

        checked = st.checkbox(
            f"Approve merge: {m['name_merge']} into {m['name_keep']}",
            value=True,
            key=f"merge_{i}",
        )
        if checked:
            approved.append(m)

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("Apply Merges & Save", type="primary", use_container_width=True):
            df = st.session_state["vendor_extracted"]
            df = apply_merges(df, approved)
            df.to_csv(VENDOR_MASTER_PATH, index=False)
            st.session_state.pop("vendor_proposed_merges", None)
            st.session_state.pop("vendor_extracted", None)
            st.success(f"Saved {len(df)} vendors (merged {len(approved)} duplicates)")
            st.rerun()

    with col_btn2:
        if st.button("Save Without Merging", use_container_width=True):
            df = st.session_state["vendor_extracted"]
            df.to_csv(VENDOR_MASTER_PATH, index=False)
            st.session_state.pop("vendor_proposed_merges", None)
            st.session_state.pop("vendor_extracted", None)
            st.success(f"Saved {len(df)} vendors (no merges applied)")
            st.rerun()

elif "vendor_extracted" in st.session_state:
    # No fuzzy matches found — auto-save
    st.markdown("---")
    st.info("No potential duplicates found.")
    if st.button("Save Vendor Master", type="primary"):
        df = st.session_state["vendor_extracted"]
        df.to_csv(VENDOR_MASTER_PATH, index=False)
        st.session_state.pop("vendor_extracted", None)
        st.success(f"Saved {len(df)} vendors")
        st.rerun()

# ── Display Section ─────────────────────────────────────────────────────
if VENDOR_MASTER_PATH.exists():
    vm = pd.read_csv(VENDOR_MASTER_PATH)

    st.markdown("---")

    # ── Metrics Row ─────────────────────────────────────────────────────
    total_vendors = len(vm)
    total_spend = vm["total_spend_ytd"].sum()
    high_risk_count = len(vm[vm["risk_flag"] == "High"])

    # Expired contracts
    today = date.today()
    today_str = today.isoformat()
    soon_str = (today + timedelta(days=90)).isoformat()

    vm["contract_end_dt"] = pd.to_datetime(vm["contract_end"], errors="coerce")
    today_ts = pd.Timestamp(today)
    soon_ts = pd.Timestamp(today + timedelta(days=90))
    expired = vm[vm["contract_end_dt"].notna() & (vm["contract_end_dt"] < today_ts)]
    expiring_soon = vm[
        vm["contract_end_dt"].notna()
        & (vm["contract_end_dt"] >= today_ts)
        & (vm["contract_end_dt"] <= soon_ts)
    ]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Vendors", total_vendors)
    c2.metric("Total Spend (YTD)", fmt_compact(total_spend))
    c3.metric("High Risk Vendors", high_risk_count)
    c4.metric("Expired Contracts", len(expired))

    # ── Contract Alerts ─────────────────────────────────────────────────
    if not expired.empty:
        for _, row in expired.iterrows():
            st.markdown(
                f'<div style="background:{RED}22;border:1px solid {RED};border-radius:8px;'
                f'padding:8px 16px;margin:4px 0;color:{VALUE_COLOR}">'
                f'<strong>EXPIRED:</strong> {row["vendor_name"]} — '
                f'contract ended {row["contract_end"]}</div>',
                unsafe_allow_html=True,
            )

    if not expiring_soon.empty:
        for _, row in expiring_soon.iterrows():
            st.markdown(
                f'<div style="background:{YELLOW}22;border:1px solid {YELLOW};border-radius:8px;'
                f'padding:8px 16px;margin:4px 0;color:{VALUE_COLOR}">'
                f'<strong>EXPIRING SOON:</strong> {row["vendor_name"]} — '
                f'contract ends {row["contract_end"]}</div>',
                unsafe_allow_html=True,
            )

    # ── Top 10 Vendors by Spend ─────────────────────────────────────────
    st.markdown("### Top 10 Vendors by Spend")

    top10 = vm.nlargest(10, "total_spend_ytd").copy()
    top10["color"] = top10["risk_flag"].apply(
        lambda x: RED if x == "High" else (YELLOW if x == "Medium" else CYAN)
    )

    fig = px.bar(
        top10,
        x="total_spend_ytd",
        y="vendor_name",
        orientation="h",
        color="risk_flag",
        color_discrete_map={"High": RED, "Medium": YELLOW, "Low": CYAN, None: CYAN},
        labels={"total_spend_ytd": "Total Spend (YTD)", "vendor_name": "Vendor"},
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    style_chart(fig, height=400)
    st.plotly_chart(fig, use_container_width=True)

    # ── CSCG Deep-Dive ──────────────────────────────────────────────────
    cscg_rows = vm[vm["vendor_name"].str.contains("CSCG", case=False, na=False)]
    if not cscg_rows.empty:
        st.markdown("### CSCG Deep-Dive")
        cscg_spend = cscg_rows["total_spend_ytd"].sum()
        cscg_count = cscg_rows["payment_count"].sum()
        pct_total = (cscg_spend / total_spend * 100) if total_spend > 0 else 0

        st.markdown(
            f'<div style="background:linear-gradient(135deg,{BG_CARD} 0%,{BG_CARD_END} 100%);'
            f'border:1px solid {BORDER_COLOR};border-radius:12px;padding:20px;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.2)">'
            f'<h4 style="color:{TITLE_COLOR};margin:0 0 12px 0">CSCG — Management Company</h4>'
            f'<div style="display:flex;gap:40px">'
            f'<div><span style="color:{FONT_COLOR}">Total Spend</span><br>'
            f'<span style="color:{VALUE_COLOR};font-size:1.5rem;font-weight:600">'
            f'{fmt_dollar(cscg_spend)}</span></div>'
            f'<div><span style="color:{FONT_COLOR}">Payments</span><br>'
            f'<span style="color:{VALUE_COLOR};font-size:1.5rem;font-weight:600">'
            f'{int(cscg_count)}</span></div>'
            f'<div><span style="color:{FONT_COLOR}">% of Total Spend</span><br>'
            f'<span style="color:{RED};font-size:1.5rem;font-weight:600">'
            f'{pct_total:.1f}%</span></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    # ── Editable Vendor Table ───────────────────────────────────────────
    st.markdown("### Vendor Registry")

    # Prepare display columns
    display_cols = [
        "vendor_id", "vendor_name", "total_spend_ytd", "payment_count",
        "category", "risk_flag", "first_seen", "last_seen",
        "contract_start", "contract_end", "contract_terms",
        "contract_doc_id", "compliance_notes", "aliases",
    ]
    # Only use columns that exist
    display_cols = [c for c in display_cols if c in vm.columns]

    column_config = {
        "vendor_id": st.column_config.TextColumn("ID", width="small", disabled=True),
        "vendor_name": st.column_config.TextColumn("Vendor Name", width="medium"),
        "total_spend_ytd": st.column_config.NumberColumn(
            "Spend (YTD)", format="$%.2f", disabled=True,
        ),
        "payment_count": st.column_config.NumberColumn(
            "Payments", disabled=True,
        ),
        "risk_flag": st.column_config.SelectboxColumn(
            "Risk Flag", options=["Low", "Medium", "High"], width="small",
        ),
        "category": st.column_config.SelectboxColumn(
            "Category", options=CATEGORY_OPTIONS, width="medium",
        ),
        "contract_start": st.column_config.DateColumn("Contract Start", width="small"),
        "contract_end": st.column_config.DateColumn("Contract End", width="small"),
        "contract_terms": st.column_config.TextColumn("Terms"),
        "contract_doc_id": st.column_config.TextColumn("Doc ID"),
        "compliance_notes": st.column_config.TextColumn("Notes", width="large"),
        "aliases": st.column_config.TextColumn("Aliases", disabled=True),
        "first_seen": st.column_config.DateColumn("First Seen", disabled=True),
        "last_seen": st.column_config.DateColumn("Last Seen", disabled=True),
    }

    # Drop the temp column before editing
    edit_df = vm[display_cols].copy()

    # Convert date columns to datetime so st.data_editor DateColumn works.
    # All-NaN columns stay as float64 after to_datetime, so force the dtype.
    for dc in ["contract_start", "contract_end", "first_seen", "last_seen"]:
        if dc in edit_df.columns:
            edit_df[dc] = pd.to_datetime(edit_df[dc], errors="coerce").astype("datetime64[ns]")

    edited = st.data_editor(
        edit_df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="vendor_editor_v2",
    )

    if st.button("Save Changes", type="primary"):
        edited.to_csv(VENDOR_MASTER_PATH, index=False)
        st.success("Vendor master saved successfully")
        st.rerun()

else:
    st.info(
        "No vendor master file found. Click **Extract Vendors from Data** in the sidebar "
        "to build one from your bills and GL data."
    )
