"""
Page 10: Budget vs Financials Reconciliation
4-way match across Budget, Financials, GL, and Invoices.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.theme import FONT_COLOR, style_chart, inject_css

st.set_page_config(page_title="Reconciliation | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()


st.title("Budget vs Financials Reconciliation")
st.caption("4-way match: Budget → Financials → GL → Invoices")

from utils.data_loader import (
    build_reconciliation_master,
    load_proposed_entries,
    load_general_ledger,
    load_gl_account_summary,
    load_bills_summary,
    load_bills_by_category,
    load_expense_flow_summary,
    load_expense_flow,
)

# Load data
recon = build_reconciliation_master()
entries = load_proposed_entries()
flow = load_expense_flow()
flow_summary = load_expense_flow_summary()

# ══════════════════════════════════════════════════════════════════════════
# Section 1: Reconciliation Overview
# ══════════════════════════════════════════════════════════════════════════
st.header("Reconciliation Overview")

total_budget = recon["Budget Amount"].sum()
total_actual = recon["Financial (Actual)"].sum()
total_invoice = recon["Invoice Total"].sum()
n_discrepancies = len(recon[recon["Status"].isin(["Major Variance", "Minor Variance", "No Invoice Trail"])])
n_matched = len(recon[recon["Status"] == "Matched"])
pct_traceable = n_matched / len(recon) * 100 if len(recon) > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Budget (YTD)", f"${total_budget:,.0f}")
c2.metric("Total Actuals (YTD)", f"${total_actual:,.0f}")
c3.metric("Total Invoiced", f"${total_invoice:,.0f}")
c4.metric("Discrepancies", f"{n_discrepancies}")
c5.metric("Fully Traceable", f"{pct_traceable:.0f}%")

# Waterfall chart: Budget → variance → Actuals → gap → Invoiced
budget_actual_var = total_actual - total_budget
actual_invoice_gap = total_invoice - total_actual

fig_waterfall = go.Figure(go.Waterfall(
    name="Flow",
    orientation="v",
    measure=["absolute", "relative", "total", "relative", "total"],
    x=["Budget (YTD)", "Budget→Actual<br>Variance", "Actuals (YTD)",
       "Actual→Invoice<br>Gap", "Invoiced Total"],
    y=[total_budget, budget_actual_var, total_actual,
       actual_invoice_gap, total_invoice],
    text=[f"${total_budget:,.0f}", f"${budget_actual_var:+,.0f}",
          f"${total_actual:,.0f}", f"${actual_invoice_gap:+,.0f}",
          f"${total_invoice:,.0f}"],
    textposition="outside",
    textfont=dict(color=FONT_COLOR),
    connector=dict(line=dict(color="rgba(168,178,209,0.3)")),
    increasing=dict(marker=dict(color="#00b894")),
    decreasing=dict(marker=dict(color="#ff6b6b")),
    totals=dict(marker=dict(color="#6c5ce7")),
))
fig_waterfall.update_layout(title="Budget → Actuals → Invoiced Flow")
style_chart(fig_waterfall, height=400)
st.plotly_chart(fig_waterfall, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# Section 2: Line-Item Reconciliation Table
# ══════════════════════════════════════════════════════════════════════════
st.header("Line-Item Reconciliation Table")

# Sidebar filters
status_options = recon["Status"].unique().tolist()
selected_statuses = st.sidebar.multiselect(
    "Filter by Status", status_options, default=status_options
)
search_term = st.sidebar.text_input("Search Line Item", "")

filtered = recon[recon["Status"].isin(selected_statuses)]
if search_term:
    filtered = filtered[filtered["Line Item"].str.contains(search_term, case=False, na=False)]

# Color-code by status
def color_status(status):
    colors = {
        "Matched": "background-color: rgba(0,184,148,0.2)",
        "Minor Variance": "background-color: rgba(253,203,110,0.2)",
        "Major Variance": "background-color: rgba(255,107,107,0.2)",
        "No Invoice Trail": "background-color: rgba(108,92,231,0.2)",
        "Budget-Only": "background-color: rgba(168,178,209,0.1)",
        "Actual-Only": "background-color: rgba(9,132,227,0.2)",
    }
    return colors.get(status, "")


def highlight_row(row):
    color = color_status(row["Status"])
    return [color] * len(row)


display_cols = ["Line Item", "Budget Amount", "Financial (Actual)", "Invoice Total",
                "Budget-Actual Variance", "Actual-Invoice Variance", "Approval Method", "Status"]
display_df = filtered[display_cols].copy()

# Format dollar columns
dollar_cols = ["Budget Amount", "Financial (Actual)", "Invoice Total",
               "Budget-Actual Variance", "Actual-Invoice Variance"]
format_dict = {col: "${:,.0f}" for col in dollar_cols}

styled = display_df.style.apply(highlight_row, axis=1).format(
    format_dict, na_rep="—"
)
st.dataframe(styled, use_container_width=True, height=500)

st.markdown(f"**{len(filtered)}** line items shown | "
            f"Matched: {len(filtered[filtered['Status']=='Matched'])} | "
            f"Variances: {len(filtered[filtered['Status'].isin(['Minor Variance','Major Variance'])])} | "
            f"No Trail: {len(filtered[filtered['Status']=='No Invoice Trail'])}")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# Section 3: Discrepancy Analysis
# ══════════════════════════════════════════════════════════════════════════
st.header("Discrepancy Analysis")

col_left, col_right = st.columns(2)

with col_left:
    # Top 15 discrepancies by dollar amount
    disc = recon[recon["Budget-Actual Variance"].notna()].copy()
    disc["Abs Variance"] = disc["Budget-Actual Variance"].abs()
    top15 = disc.nlargest(15, "Abs Variance")

    fig_bars = go.Figure(go.Bar(
        y=top15["Line Item"],
        x=top15["Budget-Actual Variance"],
        orientation="h",
        marker=dict(
            color=[("#ff6b6b" if v < 0 else "#00b894") for v in top15["Budget-Actual Variance"]],
        ),
        text=[f"${v:+,.0f}" for v in top15["Budget-Actual Variance"]],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig_bars.update_layout(
        title="Top 15 Discrepancies (Budget vs Actual)",
        xaxis_title="Variance ($)",
        yaxis=dict(autorange="reversed"),
    )
    style_chart(fig_bars, height=500)
    st.plotly_chart(fig_bars, use_container_width=True)

with col_right:
    # Donut chart of line items by traceability status
    status_counts = recon["Status"].value_counts()
    status_colors = {
        "Matched": "#00b894",
        "Minor Variance": "#fdcb6e",
        "Major Variance": "#ff6b6b",
        "No Invoice Trail": "#6c5ce7",
        "Budget-Only": "#636e72",
        "Actual-Only": "#0984e3",
    }

    fig_donut = go.Figure(go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        hole=0.5,
        marker=dict(
            colors=[status_colors.get(s, "#b2bec3") for s in status_counts.index],
            line=dict(color="#0a192f", width=2),
        ),
        textinfo="label+value",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>%{value} items<br>%{percent:.1%}<extra></extra>",
    ))
    fig_donut.update_layout(
        title="Line Items by Traceability Status",
        showlegend=False,
        annotations=[dict(text=f"<b>{len(recon)}</b><br>Items",
                          x=0.5, y=0.5, font_size=16, font_color="#e6f1ff",
                          showarrow=False)],
    )
    style_chart(fig_donut, height=500)
    st.plotly_chart(fig_donut, use_container_width=True)

# Stacked bar: discrepancy counts + dollars by type
st.subheader("Discrepancy Summary by Type")
status_summary = recon.groupby("Status").agg(
    Count=("Line Item", "count"),
    Total_Budget=("Budget Amount", "sum"),
    Total_Actual=("Financial (Actual)", "sum"),
    Total_Variance=("Budget-Actual Variance", lambda x: x.abs().sum()),
).reset_index()

fig_stacked = go.Figure()
fig_stacked.add_trace(go.Bar(
    x=status_summary["Status"],
    y=status_summary["Total_Budget"],
    name="Budget",
    marker_color="#6c5ce7",
))
fig_stacked.add_trace(go.Bar(
    x=status_summary["Status"],
    y=status_summary["Total_Actual"],
    name="Actuals",
    marker_color="#00b894",
))
fig_stacked.add_trace(go.Bar(
    x=status_summary["Status"],
    y=status_summary["Total_Variance"],
    name="|Variance|",
    marker_color="#ff6b6b",
))
fig_stacked.update_layout(
    title="Dollar Amounts by Status Category",
    barmode="group",
    xaxis_title="Status",
    yaxis_title="Amount ($)",
    yaxis=dict(tickprefix="$", tickformat=","),
)
style_chart(fig_stacked, height=400)
st.plotly_chart(fig_stacked, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# Section 4: GL Adjusting Entries Impact
# ══════════════════════════════════════════════════════════════════════════
st.header("GL Adjusting Entries Impact")

entry_nums = entries["Num"].unique()
total_debits = entries["Debit"].sum()
total_credits = entries["Credit"].sum()

# Count unique accounts
accounts_affected = entries["Account"].nunique()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Entries", f"{len(entry_nums)}")
m2.metric("Total Debits", f"${total_debits:,.0f}")
m3.metric("Total Credits", f"${total_credits:,.0f}")
m4.metric("Accounts Affected", f"{accounts_affected}")

# Categorize accounts for the grouped bar
def categorize_account(account):
    acct = str(account).lower()
    if any(k in acct for k in ["asset", "cash", "receivable", "equipment", "fixed",
                                "prepaid", "right of use", "accumulated"]):
        return "Assets"
    if any(k in acct for k in ["liability", "payable", "lease liability", "accrued",
                                "bond", "deferred"]):
        return "Liabilities"
    if any(k in acct for k in ["revenue", "income", "contribution"]):
        return "Revenue"
    return "Expenses"


entries_cat = entries.copy()
entries_cat["Category"] = entries_cat["Account"].apply(categorize_account)
cat_summary = entries_cat.groupby("Category").agg(
    Debits=("Debit", "sum"),
    Credits=("Credit", "sum"),
).reset_index()

fig_gl = go.Figure()
fig_gl.add_trace(go.Bar(
    x=cat_summary["Category"],
    y=cat_summary["Debits"],
    name="Debits",
    marker_color="#ff6b6b",
))
fig_gl.add_trace(go.Bar(
    x=cat_summary["Category"],
    y=cat_summary["Credits"],
    name="Credits",
    marker_color="#00b894",
))
fig_gl.update_layout(
    title="Adjusting Entries: Debits vs Credits by Account Category",
    barmode="group",
    yaxis=dict(tickprefix="$", tickformat=","),
)
style_chart(fig_gl, height=400)
st.plotly_chart(fig_gl, use_container_width=True)

# Key entries callout
st.info(
    "**Key Entries Affecting Budget-to-Actual Reconciliation:**\n\n"
    "- **MV2025-9** — \\$632K fixed asset capitalization (reclassifies capital expenditures "
    "from operating expenses to the balance sheet, reducing reported expenses)\n\n"
    "- **MV2025-16** — \\$107K insurance reclassification (moves insurance payments between "
    "prepaid assets and expense accounts, affecting period expenses)\n\n"
    "- **MV2025-17** — \\$7.5K accrued scoreboard expense (recognizes scoreboard obligation "
    "not yet invoiced, increasing liabilities and expenses)"
)

# Detail table in expander
with st.expander("View All Adjusting Entries"):
    display_entries = entries[["Num", "Date", "Memo", "Account", "Debit", "Credit"]].copy()
    display_entries["Debit"] = display_entries["Debit"].apply(
        lambda x: f"${x:,.2f}" if x > 0 else "")
    display_entries["Credit"] = display_entries["Credit"].apply(
        lambda x: f"${x:,.2f}" if x > 0 else "")
    display_entries["Date"] = display_entries["Date"].dt.strftime("%m/%d/%Y").fillna("")
    st.dataframe(display_entries, use_container_width=True, height=400)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# Section 5: Approval Method & Traceability
# ══════════════════════════════════════════════════════════════════════════
st.header("Approval Method & Traceability")

col_a, col_b = st.columns(2)

with col_a:
    # Stacked bar of approval methods
    fig_approval = go.Figure(go.Bar(
        x=flow_summary["Approval Method"],
        y=flow_summary["YTD Amount"],
        marker_color=["#00b894", "#fdcb6e", "#6c5ce7", "#b2bec3"],
        text=[f"${v:,.0f}" for v in flow_summary["YTD Amount"]],
        textposition="outside",
        textfont=dict(size=11),
    ))
    fig_approval.update_layout(
        title="Spending by Approval Method",
        yaxis=dict(tickprefix="$", tickformat=","),
        xaxis_title="Approval Method",
    )
    style_chart(fig_approval, height=400)
    st.plotly_chart(fig_approval, use_container_width=True)

with col_b:
    # Overlay bar chart: Financial Actual vs Invoice Total per expense category
    flow_data = flow[["Expense Category", "YTD per Financials", "YTD from Invoices"]].dropna(
        subset=["YTD per Financials"])
    # Take top 12 by financials
    flow_top = flow_data.nlargest(12, "YTD per Financials")

    fig_overlay = go.Figure()
    fig_overlay.add_trace(go.Bar(
        name="Financial (Actual)",
        x=flow_top["Expense Category"],
        y=flow_top["YTD per Financials"],
        marker_color="#6c5ce7",
    ))
    fig_overlay.add_trace(go.Bar(
        name="Invoice Total",
        x=flow_top["Expense Category"],
        y=flow_top["YTD from Invoices"].fillna(0),
        marker_color="#00b894",
    ))
    fig_overlay.update_layout(
        title="Actual vs Invoiced by Category",
        barmode="group",
        yaxis=dict(tickprefix="$", tickformat=","),
        xaxis=dict(tickangle=-45),
    )
    style_chart(fig_overlay, height=400)
    st.plotly_chart(fig_overlay, use_container_width=True)

# Verification metrics
invoice_gap = total_actual - total_invoice
verification_rate = (total_invoice / total_actual * 100) if total_actual > 0 else 0

vm1, vm2, vm3 = st.columns(3)
vm1.metric("Invoice Verification Rate", f"{verification_rate:.1f}%")
vm2.metric("Verified by Invoice", f"${total_invoice:,.0f}")
vm3.metric("Uninvoiced Gap", f"${invoice_gap:,.0f}")

gap_msg = (
    f"**Invoice Gap: \\${invoice_gap:,.0f}**\n\n"
    f"Only {verification_rate:.1f}% of YTD expenses (\\${total_actual:,.0f}) can be traced to "
    f"board-reviewed invoices (\\${total_invoice:,.0f}). The remaining \\${invoice_gap:,.0f} "
    "flows through CSCG auto-pay, fixed obligations, or categories without individual "
    "invoice verification. This limits the board's ability to verify dollar-for-dollar spending."
)
st.warning(gap_msg)
