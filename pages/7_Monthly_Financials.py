"""
Page 7: Monthly Financials
Budget vs Actuals, Cash Forecast, and Contract Receivables.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_router import analyze_document, get_api_key, ANTHROPIC_AVAILABLE
from utils.theme import FONT_COLOR, style_chart, inject_css

st.set_page_config(page_title="Monthly Financials | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()

st.title("Monthly Financials")
st.caption("Budget vs Actuals, Cash Forecast, and Contract Receivables")

from utils.data_loader import load_monthly_pnl, load_cash_forecast, load_contract_receivables

# ══════════════════════════════════════════════════════════════════════════
# Section 1: Budget vs Actuals
# ══════════════════════════════════════════════════════════════════════════
st.header("Budget vs Actuals")

pnl = load_monthly_pnl()
months = sorted(pnl["Month"].unique())
selected_month = st.sidebar.selectbox("Select Month", ["Both"] + months, index=0)

if selected_month == "Both":
    filtered = pnl
else:
    filtered = pnl[pnl["Month"] == selected_month]

# Metric cards — use latest month for display
display_month = months[-1] if selected_month == "Both" else selected_month
month_data = pnl[pnl["Month"] == display_month]

rev_row = month_data[(month_data["Category"] == "Revenue") & (month_data["Subcategory"] == "Total")]
exp_row = month_data[(month_data["Category"] == "Expense") & (month_data["Subcategory"] == "Total")]
net_row = month_data[month_data["Category"] == "Net"]

rev_actual = rev_row["Actual"].values[0] if len(rev_row) > 0 else 0
rev_budget = rev_row["Budget"].values[0] if len(rev_row) > 0 else 0
exp_actual = exp_row["Actual"].values[0] if len(exp_row) > 0 else 0
exp_budget = exp_row["Budget"].values[0] if len(exp_row) > 0 else 0
net_actual = net_row["Actual"].values[0] if len(net_row) > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(f"{display_month} Revenue", f"${rev_actual:,.0f}",
              delta=f"${rev_actual - rev_budget:+,.0f} vs budget")
with col2:
    st.metric(f"{display_month} Expenses", f"${exp_actual:,.0f}",
              delta=f"${exp_actual - exp_budget:+,.0f} vs budget",
              delta_color="inverse")
with col3:
    st.metric(f"{display_month} Net Income", f"${net_actual:,.0f}")
with col4:
    variance = (rev_actual - rev_budget) - (exp_actual - exp_budget)
    st.metric("Budget Variance (Net)", f"${variance:+,.0f}",
              delta="Favorable" if variance > 0 else "Unfavorable",
              delta_color="normal" if variance > 0 else "inverse")

# Revenue by subcategory (budget vs actual)
for cat_name, cat_label in [("Revenue", "Revenue"), ("Expense", "Expense")]:
    cat_data = filtered[(filtered["Category"] == cat_name) & (filtered["Subcategory"] != "Total")]
    if cat_data.empty:
        continue

    if selected_month == "Both":
        # Aggregate across months
        agg = cat_data.groupby("Subcategory")[["Actual", "Budget"]].sum().reset_index()
    else:
        agg = cat_data

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=agg["Subcategory"],
        y=agg["Budget"],
        name="Budget",
        marker=dict(color="#8ed1fc", line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:,.0f}" for v in agg["Budget"]],
        textposition="outside",
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate="<b>%{x}</b><br>Budget: $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=agg["Subcategory"],
        y=agg["Actual"],
        name="Actual",
        marker=dict(color="#64ffda" if cat_name == "Revenue" else "#f78da7",
                    line=dict(width=1, color="rgba(255,255,255,0.2)")),
        text=[f"${v:,.0f}" for v in agg["Actual"]],
        textposition="outside",
        textfont=dict(size=9, color=FONT_COLOR),
        hovertemplate="<b>%{x}</b><br>Actual: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"{cat_label} — Budget vs Actual" + (f" ({selected_month})" if selected_month != "Both" else " (Combined)"),
        barmode="group",
        xaxis_tickangle=-20,
        yaxis_title="Amount ($)",
    )
    style_chart(fig, 420)
    st.plotly_chart(fig, use_container_width=True)

# Variance detail table
st.subheader("Variance Detail")
detail = filtered[(filtered["Category"].isin(["Revenue", "Expense"])) & (filtered["Subcategory"] != "Total")].copy()
if selected_month == "Both":
    detail = detail.groupby(["Category", "Subcategory"])[["Actual", "Budget"]].sum().reset_index()
detail["Variance $"] = detail["Actual"] - detail["Budget"]
detail["Variance %"] = (detail["Variance $"] / detail["Budget"] * 100).round(1)

def color_variance(val):
    if pd.isna(val):
        return ""
    if val > 0:
        return "color: #64ffda"
    elif val < 0:
        return "color: #eb144c"
    return ""

st.dataframe(
    detail.style.map(color_variance, subset=["Variance $"]),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Actual": st.column_config.NumberColumn(format="$%,.0f"),
        "Budget": st.column_config.NumberColumn(format="$%,.0f"),
        "Variance $": st.column_config.NumberColumn(format="$%+,.0f"),
        "Variance %": st.column_config.NumberColumn(format="%+.1f%%"),
    },
)

# ══════════════════════════════════════════════════════════════════════════
# Section 2: Cash Forecast
# ══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.header("12-Month Cash Forecast (FY2026)")

cash = load_cash_forecast()

starting_cash = cash["Cumulative Cash"].iloc[0] - cash["Net Cash Flow"].iloc[0]
ending_cash = cash["Cumulative Cash"].iloc[-1]
lowest_month_idx = cash["Cumulative Cash"].idxmin()
lowest_cash = cash["Cumulative Cash"].iloc[lowest_month_idx]
lowest_label = cash["Month"].iloc[lowest_month_idx]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Starting Cash (Jul 2025)", f"${starting_cash:,.0f}")
with col2:
    st.metric("Projected Ending (Jun 2026)", f"${ending_cash:,.0f}",
              delta="Negative" if ending_cash < 0 else "Positive",
              delta_color="inverse" if ending_cash < 0 else "normal")
with col3:
    st.metric(f"Lowest Point ({lowest_label})", f"${lowest_cash:,.0f}",
              delta="Below zero" if lowest_cash < 0 else "Above zero",
              delta_color="inverse" if lowest_cash < 0 else "normal")

# Area chart: revenue vs expenses
fig_flow = go.Figure()
fig_flow.add_trace(go.Scatter(
    x=cash["Month"], y=cash["Revenue"],
    name="Revenue", fill="tozeroy",
    line=dict(color="#64ffda", width=2),
    fillcolor="rgba(100,255,218,0.15)",
    hovertemplate="%{x}<br>Revenue: $%{y:,.0f}<extra></extra>",
))
fig_flow.add_trace(go.Scatter(
    x=cash["Month"],
    y=cash["Expenses"] + cash["Debt Service"] + cash["Property Tax"],
    name="Total Outflows",
    fill="tozeroy",
    line=dict(color="#f78da7", width=2),
    fillcolor="rgba(247,141,167,0.15)",
    hovertemplate="%{x}<br>Total Outflows: $%{y:,.0f}<extra></extra>",
))
fig_flow.update_layout(
    title="Monthly Revenue vs Total Outflows",
    yaxis_title="Amount ($)",
)
style_chart(fig_flow, 400)
st.plotly_chart(fig_flow, use_container_width=True)

# Cumulative cash line chart
fig_cum = go.Figure()
# Red zone fill below $0
fig_cum.add_hrect(y0=-400000, y1=0, fillcolor="rgba(235,20,76,0.08)",
                  line_width=0, annotation_text="Negative Cash Zone",
                  annotation_position="bottom left",
                  annotation=dict(font=dict(color="#eb144c", size=11)))
fig_cum.add_trace(go.Scatter(
    x=cash["Month"], y=cash["Cumulative Cash"],
    name="Cumulative Cash",
    mode="lines+markers",
    line=dict(color="#fcb900", width=3),
    marker=dict(size=8, color=["#eb144c" if v < 0 else "#64ffda" for v in cash["Cumulative Cash"]]),
    text=[f"${v:,.0f}" for v in cash["Cumulative Cash"]],
    textposition="top center",
    hovertemplate="%{x}<br>Cash Balance: $%{y:,.0f}<extra></extra>",
))
fig_cum.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.4)")
# Annotate the lowest point
fig_cum.add_annotation(
    x=lowest_label, y=lowest_cash,
    text=f"Low: ${lowest_cash:,.0f}",
    showarrow=True, arrowhead=2,
    font=dict(color="#eb144c", size=13),
    arrowcolor="#eb144c",
)
# Annotate ending
fig_cum.add_annotation(
    x=cash["Month"].iloc[-1], y=ending_cash,
    text=f"End: ${ending_cash:,.0f}",
    showarrow=True, arrowhead=2,
    font=dict(color="#fcb900", size=13),
    arrowcolor="#fcb900",
)
fig_cum.update_layout(
    title="Cumulative Cash Position",
    yaxis_title="Cash Balance ($)",
)
style_chart(fig_cum, 420)
st.plotly_chart(fig_cum, use_container_width=True)

# Detail table
with st.expander("Cash Forecast Detail Table"):
    st.dataframe(
        cash,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Revenue": st.column_config.NumberColumn(format="$%,.0f"),
            "Expenses": st.column_config.NumberColumn(format="$%,.0f"),
            "Debt Service": st.column_config.NumberColumn(format="$%,.0f"),
            "Property Tax": st.column_config.NumberColumn(format="$%,.0f"),
            "Net Cash Flow": st.column_config.NumberColumn(format="$%+,.0f"),
            "Cumulative Cash": st.column_config.NumberColumn(format="$%,.0f"),
        },
    )

# ══════════════════════════════════════════════════════════════════════════
# Section 3: Contract Receivables
# ══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.header("Contract Receivables")

recv = load_contract_receivables()
totals = recv[recv["Customer"] == "Total"]
customers = recv[recv["Customer"] != "Total"]

if len(totals) > 0:
    t = totals.iloc[0]
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Contracted (Nov)", f"${t['Nov Contracted']:,.0f}")
    with col2:
        st.metric("Collected (Nov)", f"${t['Nov Paid']:,.0f}")
    with col3:
        st.metric("Outstanding (Nov)", f"${t['Nov Owed']:,.0f}",
                  delta=f"${t['Nov Owed'] - t['Sept Owed']:+,.0f} vs Sept",
                  delta_color="normal")

# Stacked horizontal bar: paid vs owed by customer (Nov)
fig_recv = go.Figure()
fig_recv.add_trace(go.Bar(
    y=customers["Customer"],
    x=customers["Nov Paid"],
    name="Paid",
    orientation="h",
    marker=dict(color="#64ffda", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    text=[f"${v:,.0f}" for v in customers["Nov Paid"]],
    textposition="inside",
    textfont=dict(size=10, color="#0a192f"),
    hovertemplate="<b>%{y}</b><br>Paid: $%{x:,.0f}<extra></extra>",
))
fig_recv.add_trace(go.Bar(
    y=customers["Customer"],
    x=customers["Nov Owed"],
    name="Outstanding",
    orientation="h",
    marker=dict(color="#eb144c", line=dict(width=1, color="rgba(255,255,255,0.2)")),
    text=[f"${v:,.0f}" for v in customers["Nov Owed"]],
    textposition="inside",
    textfont=dict(size=10, color="#fff"),
    hovertemplate="<b>%{y}</b><br>Outstanding: $%{x:,.0f}<extra></extra>",
))
fig_recv.update_layout(
    title="Contract Receivables by Customer (November)",
    barmode="stack",
    xaxis_title="Amount ($)",
)
style_chart(fig_recv, 380)
st.plotly_chart(fig_recv, use_container_width=True)

# Collection progress: Sept vs Nov
fig_progress = go.Figure()
fig_progress.add_trace(go.Bar(
    x=["September", "November"],
    y=[totals["Sept Paid"].values[0], totals["Nov Paid"].values[0]] if len(totals) > 0 else [0, 0],
    name="Collected",
    marker=dict(color="#64ffda"),
    text=[f"${v:,.0f}" for v in ([totals["Sept Paid"].values[0], totals["Nov Paid"].values[0]] if len(totals) > 0 else [0, 0])],
    textposition="inside",
    textfont=dict(size=12, color="#0a192f"),
    hovertemplate="%{x}<br>Collected: $%{y:,.0f}<extra></extra>",
))
fig_progress.add_trace(go.Bar(
    x=["September", "November"],
    y=[totals["Sept Owed"].values[0], totals["Nov Owed"].values[0]] if len(totals) > 0 else [0, 0],
    name="Outstanding",
    marker=dict(color="#eb144c"),
    text=[f"${v:,.0f}" for v in ([totals["Sept Owed"].values[0], totals["Nov Owed"].values[0]] if len(totals) > 0 else [0, 0])],
    textposition="inside",
    textfont=dict(size=12, color="#fff"),
    hovertemplate="%{x}<br>Outstanding: $%{y:,.0f}<extra></extra>",
))
fig_progress.update_layout(
    title="Collection Progress — September vs November",
    barmode="stack",
    yaxis_title="Amount ($)",
)
style_chart(fig_progress, 380)
st.plotly_chart(fig_progress, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════
# AI Monthly Analysis
# ══════════════════════════════════════════════════════════════════════════
if ANTHROPIC_AVAILABLE and get_api_key():
    st.markdown("---")
    if st.button("🤖 AI Analysis — Monthly Financial Assessment", type="primary", use_container_width=True):
        # Compile monthly data for the Financial Health Monitor agent
        analysis_data = "NSIA Monthly Financials — Current Data\n\n"

        # Budget vs Actuals
        analysis_data += "=== BUDGET VS ACTUALS ===\n"
        analysis_data += f"Display Month: {display_month}\n"
        analysis_data += f"Revenue Actual: ${rev_actual:,.0f} | Budget: ${rev_budget:,.0f} | Var: ${rev_actual - rev_budget:+,.0f}\n"
        analysis_data += f"Expense Actual: ${exp_actual:,.0f} | Budget: ${exp_budget:,.0f} | Var: ${exp_actual - exp_budget:+,.0f}\n"
        analysis_data += f"Net Income: ${net_actual:,.0f}\n\n"
        analysis_data += "Variance Detail:\n"
        analysis_data += detail.to_csv(index=False)

        # Cash Forecast
        analysis_data += "\n\n=== CASH FORECAST (12-Month) ===\n"
        analysis_data += cash.to_csv(index=False)
        analysis_data += f"\nStarting Cash: ${starting_cash:,.0f}\n"
        analysis_data += f"Projected Ending: ${ending_cash:,.0f}\n"
        analysis_data += f"Lowest Point: ${lowest_cash:,.0f} ({lowest_label})\n"

        # Receivables
        analysis_data += "\n\n=== CONTRACT RECEIVABLES ===\n"
        analysis_data += recv.to_csv(index=False)

        with st.spinner("Running Financial Health Monitor analysis..."):
            result = analyze_document(
                agent_id="financial_health",
                document_content=analysis_data,
                filename="monthly_financials_current.csv",
                additional_context="Provide a plain-language monthly financial assessment for the NSIA board. "
                                   "Compare this month to budget, assess cash runway, flag any receivables "
                                   "concerns, and provide early warning flags. Keep it concise and actionable.",
            )
        if result:
            st.markdown("---")
            st.markdown("### 🤖 AI Monthly Assessment")
            red_flags = result.count("🔴")
            yellow_flags = result.count("🟡")
            if red_flags > 0:
                st.error(f"**{red_flags} critical item(s)** require board attention")
            if yellow_flags > 0:
                st.warning(f"**{yellow_flags} caution item(s)** flagged for review")
            st.markdown(result)
            st.download_button(
                label="📥 Download Monthly Assessment",
                data=result,
                file_name="nsia_monthly_ai_assessment.md",
                mime="text/markdown",
            )
