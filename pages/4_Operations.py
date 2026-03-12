"""
Page 4: Operations
Full revenue breakdown, CSCG management relationship, expense approval, and hockey schedule.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, TITLE_COLOR, style_chart, inject_css

st.set_page_config(page_title="Operations | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()

st.title("Operations")
st.caption("Revenue breakdown, CSCG management relationship, expense oversight, and facility activity")

from utils.data_loader import (
    load_revenue_reconciliation,
    load_cscg_relationship,
    load_expense_flow_summary,
    load_expense_flow,
)

# ── Revenue KPIs ─────────────────────────────────────────────────────────
st.header("Revenue Breakdown")
st.caption("All revenue sources — YTD through January 2026")

rev = load_revenue_reconciliation()

# Separate totals from line items
rev_items = rev[~rev["Line Item"].str.startswith("Total")].copy()

# Categorize revenue streams
contract_ice = ["New Trier Boys", "New Trier Girls", "Wilmette Hockey", "Winnetka Hockey"]
programs = ["Youth Programs", "Men's League", "Rink Rentals"]
other_rev = [item for item in rev_items["Line Item"].tolist()
             if item not in contract_ice and item not in programs]

# Use CSCG YTD where available, fall back to Proposal YTD
rev_items["YTD Actual"] = rev_items["CSCG YTD Budget"].fillna(rev_items["Proposal YTD Budget"])

# KPI row
total_ytd = rev_items["YTD Actual"].sum()
contract_total = rev_items[rev_items["Line Item"].isin(contract_ice)]["YTD Actual"].sum()
program_total = rev_items[rev_items["Line Item"].isin(programs)]["YTD Actual"].sum()
other_total = rev_items[rev_items["Line Item"].isin(other_rev)]["YTD Actual"].sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue YTD", f"${total_ytd:,.0f}")
k2.metric("Contract Ice", f"${contract_total:,.0f}", f"{contract_total/total_ytd*100:.0f}% of total" if total_ytd else None)
k3.metric("Programs & Rentals", f"${program_total:,.0f}", f"{program_total/total_ytd*100:.0f}% of total" if total_ytd else None)
k4.metric("Other Revenue", f"${other_total:,.0f}", f"{other_total/total_ytd*100:.0f}% of total" if total_ytd else None)

# Full revenue treemap
rev_plot = rev_items[rev_items["YTD Actual"] > 0].copy()
rev_plot["Category"] = rev_plot["Line Item"].apply(
    lambda x: "Contract Ice" if x in contract_ice
    else ("Programs & Rentals" if x in programs else "Other Revenue")
)
rev_plot = rev_plot.sort_values("YTD Actual", ascending=False)

fig_tree = px.treemap(
    rev_plot,
    path=["Category", "Line Item"],
    values="YTD Actual",
    color="Category",
    color_discrete_map={"Contract Ice": "#0984e3", "Programs & Rentals": "#00b894", "Other Revenue": "#6c5ce7"},
    custom_data=["YTD Actual"],
)
fig_tree.update_traces(
    texttemplate="<b>%{label}</b><br>$%{customdata[0]:,.0f}",
    hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
)
fig_tree.update_layout(
    title="Revenue Sources by Category (YTD)",
    margin=dict(t=50, b=10, l=10, r=10),
)
style_chart(fig_tree, 420)
st.plotly_chart(fig_tree, use_container_width=True)

# ── Contract Ice: Proposal vs CSCG ──────────────────────────────────────
st.subheader("Contract Ice — Proposal vs. CSCG Budget")

ice_programs = rev_items[rev_items["Line Item"].isin(contract_ice)].copy()

if not ice_programs.empty:
    fig_ice = go.Figure()
    fig_ice.add_trace(go.Bar(
        x=ice_programs["Line Item"],
        y=ice_programs["Proposal YTD Budget"],
        name="Board Proposal",
        marker=dict(color="#0984e3", line=dict(width=1, color="rgba(255,255,255,0.3)")),
        text=[f"${v:,.0f}" for v in ice_programs["Proposal YTD Budget"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
    ))
    fig_ice.add_trace(go.Bar(
        x=ice_programs["Line Item"],
        y=ice_programs["CSCG YTD Budget"],
        name="CSCG Actual",
        marker=dict(color="#00b894", line=dict(width=1, color="rgba(255,255,255,0.3)")),
        text=[f"${v:,.0f}" for v in ice_programs["CSCG YTD Budget"]],
        textposition="outside",
        textfont=dict(color=FONT_COLOR, size=11),
    ))
    fig_ice.update_layout(
        barmode="group",
        yaxis_title="YTD Budget ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    style_chart(fig_ice, 400)
    st.plotly_chart(fig_ice, use_container_width=True)

    total_proposal = ice_programs["Proposal YTD Budget"].sum()
    total_cscg = ice_programs["CSCG YTD Budget"].sum()
    variance = total_cscg - total_proposal
    var_color = "#00d084" if variance >= 0 else "#eb144c"
    st.markdown(
        f"**Total Contract Ice YTD:** Proposal **${total_proposal:,.0f}** vs. "
        f"CSCG **${total_cscg:,.0f}** &nbsp; "
        f'<span style="color:{var_color};font-weight:bold;">(Variance: ${variance:+,.0f})</span>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── CSCG Relationship ─────────────────────────────────────────────────────
st.header("CSCG Management Relationship")
st.caption("Financial summary of disclosed vs. undisclosed payment flows (Jul-Dec 2025)")

cscg = load_cscg_relationship()

col1, col2 = st.columns([2, 1])

with col1:
    st.dataframe(
        cscg,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn(format="$%,.0f"),
        },
    )

with col2:
    total_cscg_rel = cscg["Amount"].sum()
    st.metric("Total CSCG Relationship (6 mo)", f"${total_cscg_rel:,.0f}")
    st.metric("Annualized", f"${total_cscg_rel * 2:,.0f}")
    # Percentage of total revenue
    if total_ytd > 0:
        cscg_pct = (total_cscg_rel * 2) / (total_ytd * 12 / 7) * 100
        st.metric("% of Annual Revenue", f"{cscg_pct:.1f}%")

# CSCG breakdown — side-by-side donut and stacked bar
cscg_detail = cscg[cscg["Amount"] > 0].copy()
if not cscg_detail.empty:
    chart_left, chart_right = st.columns(2)

    with chart_left:
        fig_cscg = go.Figure(go.Pie(
            labels=cscg_detail["Component"],
            values=cscg_detail["Amount"],
            hole=0.5,
            marker=dict(
                colors=["#6c5ce7", "#0984e3", "#00b894", "#fdcb6e", "#e17055"],
                line=dict(color="#0a192f", width=2.5),
            ),
            textinfo="label+percent",
            textfont=dict(size=12, color="#e6f1ff"),
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent:.1%}<extra></extra>",
        ))
        fig_cscg.update_layout(
            title=dict(text="Payment Components (6-Month)", font=dict(size=16, color=TITLE_COLOR)),
            showlegend=False,
            annotations=[dict(text=f"<b>${total_cscg_rel:,.0f}</b>",
                              x=0.5, y=0.5, font_size=16, font_color="#e6f1ff", showarrow=False)],
        )
        style_chart(fig_cscg, 380)
        st.plotly_chart(fig_cscg, use_container_width=True)

    with chart_right:
        # Board-visible vs auto-pay summary
        # Management Fee is visible in budget; auto-pay items are less visible
        visible = cscg_detail[cscg_detail["Component"].str.contains("Management Fee", case=False, na=False)]["Amount"].sum()
        auto_pay = total_cscg_rel - visible

        fig_disc = go.Figure()
        fig_disc.add_trace(go.Bar(
            y=["CSCG Payments"], x=[visible], name="Board-Visible",
            orientation="h", marker_color="#00b894",
            text=f"Board-Visible ${visible:,.0f}", textposition="inside",
            textfont=dict(color="#fff", size=13),
        ))
        fig_disc.add_trace(go.Bar(
            y=["CSCG Payments"], x=[auto_pay], name="Auto-Pay",
            orientation="h", marker_color="#eb144c",
            text=f"Auto-Pay ${auto_pay:,.0f}", textposition="inside",
            textfont=dict(color="#fff", size=13),
        ))
        fig_disc.update_layout(
            barmode="stack",
            title=dict(text="Board-Visible vs. Auto-Pay", font=dict(size=16, color=TITLE_COLOR)),
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        style_chart(fig_disc, 380)
        st.plotly_chart(fig_disc, use_container_width=True)

st.markdown("---")

# ── Expense Approval Summary ──────────────────────────────────────────────
st.header("Expense Approval Overview")

summary = load_expense_flow_summary()
flow = load_expense_flow()

col_chart, col_detail = st.columns([1, 1])

with col_chart:
    if not summary.empty:
        bar_colors = ["#00b894", "#fdcb6e", "#6c5ce7", "#b2bec3"]
        fig_bar = go.Figure(go.Bar(
            x=summary["Approval Method"],
            y=summary["YTD Amount"],
            marker=dict(
                color=bar_colors[:len(summary)],
                line=dict(width=1.5, color="rgba(255,255,255,0.3)"),
            ),
            text=[f"${v:,.0f}" for v in summary["YTD Amount"]],
            textposition="inside",
            textfont=dict(color="#fff", size=14, family="Arial Black"),
            hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
        ))
        fig_bar.update_layout(
            title="Expenses by Approval Method (Jul-Dec 2025)",
            yaxis_title="6-Month Amount ($)",
            showlegend=False,
            bargap=0.3,
        )
        style_chart(fig_bar, 420)
        st.plotly_chart(fig_bar, use_container_width=True)

with col_detail:
    # Top expenses without invoice trail
    if not flow.empty:
        no_trail = flow[flow["Variance"].abs() > 500].sort_values("Variance", ascending=False, key=abs)
        if not no_trail.empty:
            st.subheader("Largest Invoice Variances")
            st.caption("Expense categories where financials vs. invoices differ by >$500")
            for _, row in no_trail.head(8).iterrows():
                var = row["Variance"]
                color = "#eb144c" if abs(var) > 5000 else "#fcb900"
                st.markdown(
                    f'<div style="padding:6px 12px;margin:4px 0;border-left:3px solid {color};'
                    f'background:rgba(26,26,46,0.5);border-radius:4px;">'
                    f'<b>{row["Expense Category"]}</b> &nbsp; '
                    f'<span style="color:{color};">${var:+,.0f} variance</span><br>'
                    f'<span style="color:#a8b2d1;font-size:0.85rem;">'
                    f'Financials: ${row["YTD per Financials"]:,.0f} vs Invoices: ${row["YTD from Invoices"]:,.0f}'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )

st.markdown(
    """
---
### CSCG Disclosure Summary

| Category | Amount (6 mo) | Board Visibility |
|----------|--------------|-----------------|
| **Management Fee** | $21,000 | Visible in Budget vs. Actuals |
| **Payroll Reimbursement** | $205,550 | Visible but auto-approved |
| **Total CSCG Payments** | $226,550 | Only 9.3% requires invoice approval |

The CSCG management relationship represents a significant portion of NSIA expenses
that flows without individual invoice approval. Per the management agreement,
payroll costs are reimbursed automatically as CSCG employees serve the rink.
    """
)

