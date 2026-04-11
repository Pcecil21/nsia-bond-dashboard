"""
Page 2: Bond & Debt Obligations
Off-budget cash flows, debt service, fixed obligations, and scoreboard economics.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.theme import (
    FONT_COLOR, TITLE_COLOR, VALUE_COLOR, style_chart, inject_css,
    RED, YELLOW, GREEN, BG_CARD, BG_CARD_END, BORDER_COLOR,
)
from utils.auth import require_auth
from utils.fiscal_period import get_period_label

st.set_page_config(page_title="Bond & Debt | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

st.title("Bond & Debt Obligations")
st.caption("Cash flow items managed outside the board's primary operating budget")

from utils.data_loader import (
    load_bond_documents,
    load_hidden_cash_flows,
    load_fixed_obligations,
    load_scoreboard_10yr,
    load_scoreboard_alternative,
)

# ── Off-Budget Cash Flows ─────────────────────────────────────────────────
st.header("Off-Budget Cash Flows")
st.markdown(
    "These items impact NSIA's cash position but are managed outside the board's "
    "primary operating budget. They include debt service, ground lease, and trustee "
    "fees — all fully documented but tracked separately from CSCG's operating budget."
)

hidden = load_hidden_cash_flows()

col1, col2 = st.columns([2, 1])

with col1:
    st.dataframe(
        hidden,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Monthly Amount": st.column_config.NumberColumn(format="$%,.0f"),
            "Annual Impact": st.column_config.NumberColumn(format="$%,.0f"),
        },
    )

with col2:
    total_hidden = hidden["Annual Impact"].sum()
    st.metric("Total Annual Off-Budget Outflows", f"${total_hidden:,.0f}")
    st.markdown("**Per year** tracked outside the primary operating budget")

# Waterfall chart
st.subheader("Annual Debt Service Waterfall")
st.caption("Cumulative annual cash outflows managed outside the primary operating budget")
hidden_sorted = hidden.sort_values("Annual Impact", ascending=False)
items = hidden_sorted["Item"].tolist()
values = hidden_sorted["Annual Impact"].tolist()

waterfall_colors = ["#ff6b6b", "#ee5a24", "#f0932b", "#ffbe76", "#6ab04c", "#22a6b3"]

fig_waterfall = go.Figure(go.Waterfall(
    name="Annual Impact",
    orientation="v",
    measure=["relative"] * len(items) + ["total"],
    x=items + ["Total"],
    y=values + [None],
    textposition="outside",
    text=[f"${v:,.0f}" if pd.notna(v) else "" for v in values] + [f"${total_hidden:,.0f}"],
    textfont=dict(color=FONT_COLOR, size=12, family="Arial Black"),
    connector={"line": {"color": "rgba(168,178,209,0.3)", "width": 1.5, "dash": "dot"}},
    increasing={"marker": {"color": "#ff6b6b",
                            "line": {"color": "rgba(255,255,255,0.3)", "width": 1}}},
    totals={"marker": {"color": "#6c5ce7",
                        "line": {"color": "rgba(255,255,255,0.3)", "width": 1}}},
))
fig_waterfall.update_layout(
    title="Off-Budget Cash Outflows — Annual Impact",
    yaxis_title="Dollars",
    showlegend=False,
    xaxis_tickangle=-25,
)
style_chart(fig_waterfall, 500)
st.plotly_chart(fig_waterfall, use_container_width=True)

st.markdown("---")

# ── Fixed Obligations ─────────────────────────────────────────────────────
st.header(f"Fixed Obligations (6 Months: {get_period_label(6)})")
st.caption("Contractual obligations from the Expense Flow Analysis")

fixed = load_fixed_obligations()
st.dataframe(
    fixed[["Expense Category", "YTD per Financials", "Approval Method", "Notes"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "YTD per Financials": st.column_config.NumberColumn("6-Month Amount", format="$%,.0f"),
    },
)

fixed_total = fixed["YTD per Financials"].sum()
st.metric("Total Fixed Obligations (6 months)", f"${fixed_total:,.0f}")

# Bar chart of fixed obligations
fixed_sorted = fixed.sort_values("YTD per Financials", ascending=True)
bar_colors = ["#00b894", "#00cec9", "#0984e3", "#6c5ce7", "#a29bfe", "#fd79a8", "#e17055"]
fig_fixed = go.Figure(go.Bar(
    y=fixed_sorted["Expense Category"],
    x=fixed_sorted["YTD per Financials"],
    orientation="h",
    marker=dict(
        color=bar_colors[:len(fixed_sorted)],
        line=dict(width=1, color="rgba(255,255,255,0.2)"),
    ),
    text=[f"${v:,.0f}" for v in fixed_sorted["YTD per Financials"]],
    textposition="outside",
    textfont=dict(color=FONT_COLOR, size=12),
    hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
))
fig_fixed.update_layout(title="Fixed Obligations Breakdown (6-Month Period)",
                         xaxis_title="Dollars")
style_chart(fig_fixed, 420)
st.plotly_chart(fig_fixed, use_container_width=True)

st.markdown("---")

# ── Scoreboard Economics ──────────────────────────────────────────────────
st.header("Scoreboard Economics — 10-Year NPV Comparison")
st.markdown(
    "Comparing the **current ScoreVision deal** (lease with sponsorship revenue share) "
    "against a **cheaper purchase alternative**."
)

sb_current = load_scoreboard_10yr()
sb_alt = load_scoreboard_alternative()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Current Deal")
    current_ncf = sb_current[sb_current["Category"] == "Net Cash Flow (Current Deal)"]
    if not current_ncf.empty:
        total_current = current_ncf.iloc[0].get("10yr Total", None)
        st.metric("10-Year Net Cash Flow", f"${total_current:,.0f}" if pd.notna(total_current) else "N/A",
                  delta="Negative" if total_current and total_current < 0 else None,
                  delta_color="inverse")

    st.dataframe(
        sb_current,
        use_container_width=True,
        hide_index=True,
        column_config={col: st.column_config.NumberColumn(format="$%,.0f")
                       for col in sb_current.columns if col != "Category"},
    )

with col2:
    st.subheader("Cheaper Alternative")
    alt_ncf = sb_alt[sb_alt["Category"] == "Net Cash Flow (Cheaper Alt)"]
    if not alt_ncf.empty:
        total_alt = alt_ncf.iloc[0].get("10yr Total", None)
        st.metric("10-Year Net Cash Flow", f"${total_alt:,.0f}" if pd.notna(total_alt) else "N/A",
                  delta="Positive" if total_alt and total_alt > 0 else None,
                  delta_color="normal")

    st.dataframe(
        sb_alt,
        use_container_width=True,
        hide_index=True,
        column_config={col: st.column_config.NumberColumn(format="$%,.0f")
                       for col in sb_alt.columns if col != "Category"},
    )

st.markdown("")

# Comparison area chart
st.subheader("Net Cash Flow Comparison Over 10 Years")
st.caption("Year-by-year cash flow comparison showing cumulative impact of each deal structure")
current_vals = sb_current[sb_current["Category"] == "Net Cash Flow (Current Deal)"]
alt_vals = sb_alt[sb_alt["Category"] == "Net Cash Flow (Cheaper Alt)"]

if not current_vals.empty and not alt_vals.empty:
    years = list(range(1, 11))
    current_data = [current_vals.iloc[0].get(f"Year {y}", 0) for y in years]
    alt_data = [alt_vals.iloc[0].get(f"Year {y}", 0) for y in years]

    fig_compare = go.Figure()
    fig_compare.add_trace(go.Scatter(
        x=years, y=current_data, mode="lines+markers",
        name="Current Deal",
        line=dict(color="#eb144c", width=3),
        marker=dict(size=9, color="#eb144c", line=dict(width=2, color="#fff")),
        fill="tozeroy",
        fillcolor="rgba(235,20,76,0.15)",
        hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>Current Deal</extra>",
    ))
    fig_compare.add_trace(go.Scatter(
        x=years, y=alt_data, mode="lines+markers",
        name="Cheaper Alternative",
        line=dict(color="#00d084", width=3),
        marker=dict(size=9, color="#00d084", line=dict(width=2, color="#fff")),
        fill="tozeroy",
        fillcolor="rgba(0,208,132,0.15)",
        hovertemplate="Year %{x}<br>$%{y:,.0f}<extra>Cheaper Alt</extra>",
    ))
    fig_compare.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.4)", line_width=1.5)
    fig_compare.update_layout(
        title="Annual Net Cash Flow: Current Deal vs. Cheaper Alternative",
        xaxis_title="Year", yaxis_title="Net Cash Flow ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    style_chart(fig_compare, 450)
    st.plotly_chart(fig_compare, use_container_width=True)

    diff = total_alt - total_current
    st.success(
        f"**Current deal** 10-year total: **${total_current:,.0f}** | "
        f"**Cheaper alternative** 10-year total: **${total_alt:,.0f}** | "
        f"**Savings: ${diff:,.0f}** in favor of the cheaper alternative"
    )

# ── Governing Documents ────────────────────────────────────────────────────
st.markdown("---")
st.header("Governing Documents")
st.caption("Key terms and obligations extracted from NSIA's legal and bond documents.")

_bond_docs = load_bond_documents()
if _bond_docs.empty:
    st.info("No extracted bond document data found. Run PDF extraction to populate this section.")
else:
    _bond_docs = _bond_docs.copy()
    _today_ts = pd.Timestamp.now()

    # Sort: ground_lease → indenture → operating_agreement → others
    _TYPE_ORDER = {"ground_lease": 0, "indenture": 1, "operating_agreement": 2}
    if "document_type" in _bond_docs.columns:
        _bond_docs["_sort"] = _bond_docs["document_type"].apply(
            lambda t: _TYPE_ORDER.get(str(t).lower() if pd.notna(t) else "", 99)
        )
        _bond_docs = _bond_docs.sort_values("_sort")

    def _coerce_str(val):
        """Flatten list/dict/str to a display string."""
        if isinstance(val, list):
            return " | ".join(str(v) for v in val if v)
        return str(val).strip() if val and str(val).strip() not in ("nan", "None") else ""

    # ── Priority summary cards ─────────────────────────────────────────────
    _PRIORITY = ["ground_lease", "indenture", "operating_agreement"]
    _priority_rows = {}
    for _pt in _PRIORITY:
        if "document_type" in _bond_docs.columns:
            _priority_rows[_pt] = _bond_docs[
                _bond_docs["document_type"].str.lower().eq(_pt)
            ]
        else:
            _priority_rows[_pt] = pd.DataFrame()

    _populated = [t for t in _PRIORITY if not _priority_rows[t].empty]
    if _populated:
        _card_cols = st.columns(len(_populated))
        for _ci, _dtype in enumerate(_populated):
            _doc = _priority_rows[_dtype].iloc[0]
            with _card_cols[_ci]:
                if _dtype == "ground_lease":
                    _exp = _doc.get("lease_expiry_date")
                    _exp_yr = _exp.strftime("%Y") if pd.notna(_exp) else "—"
                    if pd.notna(_exp):
                        _yrs = int((_exp - _today_ts).days / 365.25)
                        _yr_color = GREEN if _yrs > 20 else (YELLOW if _yrs > 10 else RED)
                        _yr_label = f"{_yrs} years remaining"
                    else:
                        _yr_color = VALUE_COLOR
                        _yr_label = ""
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,{BG_CARD} 0%,{BG_CARD_END} 100%);'
                        f'border:1px solid {BORDER_COLOR};border-radius:12px;padding:20px;'
                        f'box-shadow:0 4px 15px rgba(0,0,0,0.2);">'
                        f'<h4 style="color:{TITLE_COLOR};margin:0 0 14px 0;">Ground Lease</h4>'
                        f'<p style="color:{FONT_COLOR};font-size:0.78rem;margin:0 0 2px 0;'
                        f'text-transform:uppercase;letter-spacing:.05em;">Lease Expires</p>'
                        f'<p style="color:{_yr_color};font-size:2.2rem;font-weight:700;margin:0;">{_exp_yr}</p>'
                        f'<p style="color:{FONT_COLOR};font-size:0.875rem;margin:6px 0 0 0;">'
                        f'<b style="color:{_yr_color};">{_yr_label}</b></p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                elif _dtype == "indenture":
                    _dscr_min = _doc.get("dscr_minimum")
                    _principal = _doc.get("bond_principal")
                    _maturity = _doc.get("bond_maturity_date")
                    _dscr_str = f"{_dscr_min:.2f}x" if pd.notna(_dscr_min) else "—"
                    _prin_str = f"${_principal:,.0f}" if pd.notna(_principal) else "—"
                    _mat_str = _maturity.strftime("%Y") if pd.notna(_maturity) else "—"
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,{BG_CARD} 0%,{BG_CARD_END} 100%);'
                        f'border:1px solid {BORDER_COLOR};border-radius:12px;padding:20px;'
                        f'box-shadow:0 4px 15px rgba(0,0,0,0.2);">'
                        f'<h4 style="color:{TITLE_COLOR};margin:0 0 14px 0;">Bond Indenture</h4>'
                        f'<p style="color:{FONT_COLOR};font-size:0.78rem;margin:0 0 2px 0;'
                        f'text-transform:uppercase;letter-spacing:.05em;">DSCR Covenant Minimum</p>'
                        f'<p style="color:{VALUE_COLOR};font-size:2.2rem;font-weight:700;margin:0 0 12px 0;">{_dscr_str}</p>'
                        f'<div style="display:flex;gap:24px;">'
                        f'<div><p style="color:{FONT_COLOR};font-size:0.78rem;margin:0;">Principal</p>'
                        f'<p style="color:{VALUE_COLOR};font-weight:600;font-size:0.95rem;margin:0;">{_prin_str}</p></div>'
                        f'<div><p style="color:{FONT_COLOR};font-size:0.78rem;margin:0;">Bond Matures</p>'
                        f'<p style="color:{VALUE_COLOR};font-weight:600;font-size:0.95rem;margin:0;">{_mat_str}</p></div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                elif _dtype == "operating_agreement":
                    _parties = _coerce_str(_doc.get("parties"))
                    _eff = _doc.get("effective_date")
                    _eff_str = _eff.strftime("%b %d, %Y") if pd.notna(_eff) else "—"
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,{BG_CARD} 0%,{BG_CARD_END} 100%);'
                        f'border:1px solid {BORDER_COLOR};border-radius:12px;padding:20px;'
                        f'box-shadow:0 4px 15px rgba(0,0,0,0.2);">'
                        f'<h4 style="color:{TITLE_COLOR};margin:0 0 14px 0;">Operating Agreement</h4>'
                        f'<p style="color:{FONT_COLOR};font-size:0.78rem;margin:0 0 2px 0;'
                        f'text-transform:uppercase;letter-spacing:.05em;">Effective Date</p>'
                        f'<p style="color:{VALUE_COLOR};font-size:1.3rem;font-weight:700;margin:0 0 12px 0;">{_eff_str}</p>'
                        f'<p style="color:{FONT_COLOR};font-size:0.78rem;margin:0 0 2px 0;">Parties</p>'
                        f'<p style="color:{VALUE_COLOR};font-size:0.85rem;margin:0;">{_parties or "—"}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("")

    # ── Red flags (collapsible) ────────────────────────────────────────────
    _flagged = []
    for _, _d in _bond_docs.iterrows():
        _flag_str = _coerce_str(_d.get("red_flags"))
        if _flag_str:
            _dt_label = _coerce_str(_d.get("document_type") or "Unknown").replace("_", " ").title()
            _flagged.append((_dt_label, _flag_str))

    if _flagged:
        with st.expander(f"Document Red Flags — {len(_flagged)} document(s)", expanded=False):
            for _dt_label, _flag_str in _flagged:
                st.markdown(
                    f'<div style="background:{RED}22;border:1px solid {RED};border-radius:8px;'
                    f'padding:10px 14px;margin-bottom:8px;">'
                    f'<span style="color:{RED};font-weight:700;font-size:0.9rem;">{_dt_label}</span>'
                    f'<p style="color:{FONT_COLOR};font-size:0.875rem;margin:4px 0 0 0;">{_flag_str}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Per-document expanders — key clauses ──────────────────────────────
    st.markdown("#### Document Detail — Key Clauses")

    def _render_clauses(val):
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    for k, v in item.items():
                        st.markdown(f"- **{k}:** {v}")
                elif str(item).strip():
                    st.markdown(f"- {item}")
        elif isinstance(val, str) and val.strip() and val not in ("nan", "None"):
            for line in val.split(";"):
                if line.strip():
                    st.markdown(f"- {line.strip()}")
        else:
            st.caption("No key clauses extracted.")

    for _, _d in _bond_docs.iterrows():
        _dt_label = _coerce_str(_d.get("document_type") or "Document").replace("_", " ").title()
        _src = str(_d.get("_source_file") or "")
        _exp_label = f"{_dt_label}  |  {_src}" if _src and _src not in ("nan", "None") else _dt_label
        with st.expander(_exp_label, expanded=False):
            _render_clauses(_d.get("key_clauses"))

from utils import ask_about_this
ask_about_this("Bond and Debt")
