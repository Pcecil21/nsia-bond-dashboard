# CSCG Board Demands Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Board Demands" section to Page 6 showing 15 specific items the board should require from CSCG, with auto-detected GREEN/YELLOW/RED status from existing data.

**Architecture:** New `compute_board_demands()` function in `data_loader.py` composes existing cached loaders to evaluate 15 demand items. Page 6 renders the results as summary KPIs, an HTML status table, and a Plotly progress bar.

**Tech Stack:** Python, Streamlit, Plotly, Pandas

**Spec:** `docs/superpowers/specs/2026-03-13-cscg-board-demands-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `utils/data_loader.py` | Modify (add function after `compute_cscg_scorecard()`, ~line 697) | `compute_board_demands()` — evaluates 15 demand items against existing loaders |
| `tests/test_data_loader.py` | Modify (append tests) | Tests for `compute_board_demands()` with mocked loaders |
| `pages/6_CSCG_Scorecard.py` | Modify (insert section + extend AI context) | Board Demands UI section + AI Assessment context update |

---

## Chunk 1: compute_board_demands() — Tests and Implementation

### Task 1: Write failing tests for compute_board_demands

**Files:**
- Modify: `tests/test_data_loader.py` (append at end of file)

- [ ] **Step 1: Write tests for compute_board_demands**

Append to `tests/test_data_loader.py`:

```python
# ── compute_board_demands ────────────────────────────────────────────────

class TestComputeBoardDemands:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def _mock_loaders(self, monkeypatch, cscg_rel=None, mods=None, expense_summary=None, scorecard=None):
        """Set up mocked loaders. None means use empty DataFrame."""
        if cscg_rel is None:
            cscg_rel = pd.DataFrame(columns=["Component", "Amount", "Approval Required?", "Contract Reference"])
        if mods is None:
            mods = pd.DataFrame(columns=["Line Item", "Proposal Annual", "CSCG Annual (Implied)",
                                         "Annual Variance $", "Direction", "Severity", "Board Governance Impact"])
        if expense_summary is None:
            expense_summary = pd.DataFrame(columns=["Approval Method", "YTD Amount", "% of Total"])
        if scorecard is None:
            scorecard = pd.DataFrame(columns=["Contract Term", "Contract Amount", "6mo Expected", "6mo Actual", "Status"])

        monkeypatch.setattr(self._dl, "load_cscg_relationship", lambda: cscg_rel)
        monkeypatch.setattr(self._dl, "load_unauthorized_modifications", lambda: mods)
        monkeypatch.setattr(self._dl, "load_expense_flow_summary", lambda: expense_summary)
        monkeypatch.setattr(self._dl, "compute_cscg_scorecard", lambda: scorecard)

    def test_returns_15_items(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        assert len(result) == 15

    def test_has_required_columns(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        assert list(result.columns) == ["Category", "Demand", "Frequency", "Status", "Evidence"]

    def test_all_red_when_loaders_empty(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        # All should be RED when no data available
        assert (result["Status"] == "RED").all()

    def test_demand_1_green_when_payroll_exists(self, monkeypatch):
        cscg_rel = pd.DataFrame({
            "Component": ["Office Payroll", "Management Fee"],
            "Amount": [100000, 21000],
            "Approval Required?": ["No", "Yes"],
            "Contract Reference": ["", ""],
        })
        self._mock_loaders(monkeypatch, cscg_rel=cscg_rel)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_1 = result[result["Demand"].str.contains("payroll report", case=False)]
        assert demand_1.iloc[0]["Status"] == "GREEN"

    def test_demand_3_green_when_board_approved_high(self, monkeypatch):
        expense_summary = pd.DataFrame({
            "Approval Method": ["Board Approved", "CSCG Auto-Pay"],
            "YTD Amount": [90000, 10000],
            "% of Total": [0.90, 0.10],
        })
        self._mock_loaders(monkeypatch, expense_summary=expense_summary)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_3 = result[result["Demand"].str.contains("Invoice copies", case=False)]
        assert demand_3.iloc[0]["Status"] == "GREEN"

    def test_demand_3_yellow_when_board_approved_medium(self, monkeypatch):
        expense_summary = pd.DataFrame({
            "Approval Method": ["Board Approved", "CSCG Auto-Pay"],
            "YTD Amount": [60000, 40000],
            "% of Total": [0.60, 0.40],
        })
        self._mock_loaders(monkeypatch, expense_summary=expense_summary)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_3 = result[result["Demand"].str.contains("Invoice copies", case=False)]
        assert demand_3.iloc[0]["Status"] == "YELLOW"

    def test_demand_6_red_when_high_severity_mods_exist(self, monkeypatch):
        mods = pd.DataFrame({
            "Line Item": ["Ice Rental Revenue"],
            "Proposal Annual": [100000],
            "CSCG Annual (Implied)": [80000],
            "Annual Variance $": [-20000],
            "Direction": ["DECREASE"],
            "Severity": ["HIGH"],
            "Board Governance Impact": ["Revenue reduction without board vote"],
        })
        self._mock_loaders(monkeypatch, mods=mods)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_6 = result[result["Demand"].str.contains("variance explanation", case=False)]
        assert demand_6.iloc[0]["Status"] == "RED"

    def test_demand_7_green_when_no_mods(self, monkeypatch):
        self._mock_loaders(monkeypatch, mods=pd.DataFrame(columns=[
            "Line Item", "Proposal Annual", "CSCG Annual (Implied)",
            "Annual Variance $", "Direction", "Severity", "Board Governance Impact"]))
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_7 = result[result["Demand"].str.contains("pre-approval", case=False)]
        assert demand_7.iloc[0]["Status"] == "GREEN"

    def test_demand_10_green_when_mgmt_fee_compliant(self, monkeypatch):
        scorecard = pd.DataFrame({
            "Contract Term": ["Management Fee", "Land Lease"],
            "Contract Amount": [42000, 1],
            "6mo Expected": [21000, 1],
            "6mo Actual": [21000, 1],
            "Status": ["COMPLIANT", "COMPLIANT"],
        })
        self._mock_loaders(monkeypatch, scorecard=scorecard)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_10 = result[result["Demand"].str.contains("management fee reconciliation", case=False)]
        assert demand_10.iloc[0]["Status"] == "GREEN"

    def test_demand_13_red_when_autopay_exists(self, monkeypatch):
        expense_summary = pd.DataFrame({
            "Approval Method": ["Board Approved", "CSCG Auto-Pay"],
            "YTD Amount": [50000, 50000],
            "% of Total": [0.50, 0.50],
        })
        self._mock_loaders(monkeypatch, expense_summary=expense_summary)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        demand_13 = result[result["Demand"].str.contains("auto-pay transaction log", case=False)]
        assert demand_13.iloc[0]["Status"] == "RED"

    def test_category_counts(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_board_demands.__wrapped__
        result = fn()
        cats = result["Category"].value_counts()
        assert cats["Financial Reporting"] == 5
        assert cats["Budget Accountability"] == 3
        assert cats["Contract Compliance"] == 3
        assert cats["Operational Transparency"] == 2
        assert cats["Board Communication"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_loader.py::TestComputeBoardDemands -v`
Expected: FAIL — `compute_board_demands` not found in `data_loader`

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_data_loader.py
git commit -m "test: add failing tests for compute_board_demands"
```

---

### Task 2: Implement compute_board_demands

**Files:**
- Modify: `utils/data_loader.py` (add function near other `compute_*` functions, around line 620)

- [ ] **Step 4: Implement compute_board_demands in data_loader.py**

Add after `compute_cscg_scorecard()` in `utils/data_loader.py`:

```python
@st.cache_data
def compute_board_demands() -> pd.DataFrame:
    """Compute status of 15 board demand items from CSCG.
    Returns DataFrame with columns: Category, Demand, Frequency, Status, Evidence.

    Status values: GREEN (received/verified), YELLOW (partial/unverifiable), RED (not received).
    Auto-detects status from existing data loaders where possible; defaults to RED otherwise.
    """
    # Load data from existing loaders — each wrapped individually
    try:
        cscg_rel = load_cscg_relationship()
    except Exception:
        logger.warning("compute_board_demands: load_cscg_relationship failed")
        cscg_rel = pd.DataFrame()

    try:
        mods = load_unauthorized_modifications()
        # Filter to actual modifications (exclude totals/summaries)
        mods = mods[~mods["Line Item"].str.contains(
            "AGGREGATE|Total|Net Budget", case=False, na=False)].copy()
        mods = mods.dropna(subset=["Severity"])
    except Exception:
        logger.warning("compute_board_demands: load_unauthorized_modifications failed")
        mods = pd.DataFrame()

    try:
        expense_summary = load_expense_flow_summary()
    except Exception:
        logger.warning("compute_board_demands: load_expense_flow_summary failed")
        expense_summary = pd.DataFrame()

    try:
        scorecard = compute_cscg_scorecard()
    except Exception:
        logger.warning("compute_board_demands: compute_cscg_scorecard failed")
        scorecard = pd.DataFrame()

    # --- Auto-detection helpers ---

    def _detect_payroll_report():
        """Demand 1: Monthly itemized payroll report."""
        if cscg_rel.empty:
            return "RED", "No CSCG relationship data available"
        payroll = cscg_rel[cscg_rel["Component"].str.contains("Payroll", case=False, na=False)]
        if len(payroll) > 0:
            return "GREEN", f"Payroll tracked ({len(payroll)} line items) — itemized detail still needed"
        return "RED", "No payroll data found in CSCG relationship"

    def _detect_invoice_coverage():
        """Demand 3: Invoice copies for vendor payments > $500."""
        if expense_summary.empty:
            return "RED", "No expense summary data available"
        board_row = expense_summary[expense_summary["Approval Method"].str.contains("Board", case=False, na=False)]
        if board_row.empty:
            return "RED", "No board-approved category found"
        pct = board_row["% of Total"].iloc[0]
        if pd.isna(pct):
            return "RED", "Board approval percentage unavailable"
        if pct > 0.80:
            return "GREEN", f"Board-approved: {pct:.0%} of expenses"
        if pct >= 0.50:
            return "YELLOW", f"Board-approved: {pct:.0%} of expenses — below 80% target"
        return "RED", f"Board-approved: only {pct:.0%} of expenses"

    def _detect_variance_explanations():
        """Demand 6: Written variance explanation for changes > $2,500."""
        if mods.empty:
            return "GREEN", "No unauthorized budget modifications found"
        high_crit = mods[mods["Severity"].str.contains("HIGH|CRITICAL", case=False, na=False)]
        if len(high_crit) > 0:
            return "RED", f"{len(high_crit)} HIGH/CRITICAL modifications without verifiable explanation"
        return "GREEN", "No HIGH/CRITICAL unauthorized modifications"

    def _detect_preapproval():
        """Demand 7: Board pre-approval before budget modifications."""
        if mods.empty:
            return "GREEN", "No unauthorized budget modifications found"
        return "RED", f"{len(mods)} budget modifications made without board pre-approval"

    def _detect_mgmt_fee():
        """Demand 10: Management fee reconciliation vs. contract."""
        if scorecard.empty:
            return "RED", "No scorecard data available"
        fee_row = scorecard[scorecard["Contract Term"].str.contains("Management Fee", case=False, na=False)]
        if fee_row.empty:
            return "RED", "Management Fee not found in scorecard"
        status = fee_row.iloc[0]["Status"]
        status_map = {"COMPLIANT": "GREEN", "MINOR VARIANCE": "YELLOW", "NON-COMPLIANT": "RED", "AUTO-PAY": "YELLOW"}
        color = status_map.get(status, "RED")
        return color, f"Management fee status: {status}"

    def _detect_autopay_log():
        """Demand 13: Auto-pay transaction log."""
        if expense_summary.empty:
            return "RED", "No expense summary data available"
        autopay = expense_summary[expense_summary["Approval Method"].str.contains("CSCG|Auto", case=False, na=False)]
        if len(autopay) > 0:
            total = autopay["YTD Amount"].sum()
            return "RED", f"${total:,.0f} in auto-pay with no itemized transaction log"
        return "GREEN", "No auto-pay category detected"

    # --- Build the 15 demand items ---

    d1_status, d1_evidence = _detect_payroll_report()
    d3_status, d3_evidence = _detect_invoice_coverage()
    d6_status, d6_evidence = _detect_variance_explanations()
    d7_status, d7_evidence = _detect_preapproval()
    d10_status, d10_evidence = _detect_mgmt_fee()
    d13_status, d13_evidence = _detect_autopay_log()

    demands = [
        # Financial Reporting
        {"Category": "Financial Reporting", "Demand": "Monthly itemized payroll report (names, hours, rates)",
         "Frequency": "Monthly", "Status": d1_status, "Evidence": d1_evidence},
        {"Category": "Financial Reporting", "Demand": "Monthly expense reimbursement detail with receipts",
         "Frequency": "Monthly", "Status": "RED", "Evidence": "Manual review required"},
        {"Category": "Financial Reporting", "Demand": "Invoice copies for all vendor payments > $500",
         "Frequency": "Monthly", "Status": d3_status, "Evidence": d3_evidence},
        {"Category": "Financial Reporting", "Demand": "Quarterly revenue reconciliation (collected vs. deposited)",
         "Frequency": "Quarterly", "Status": "RED", "Evidence": "No revenue reconciliation data available"},
        {"Category": "Financial Reporting", "Demand": "Monthly bank account transaction log",
         "Frequency": "Monthly", "Status": "RED", "Evidence": "No bank transaction data available"},
        # Budget Accountability
        {"Category": "Budget Accountability", "Demand": "Written variance explanation for any line item change > $2,500",
         "Frequency": "As needed", "Status": d6_status, "Evidence": d6_evidence},
        {"Category": "Budget Accountability", "Demand": "Board pre-approval before any budget line modification",
         "Frequency": "As needed", "Status": d7_status, "Evidence": d7_evidence},
        {"Category": "Budget Accountability", "Demand": "Quarterly budget-to-actual comparison with CSCG commentary",
         "Frequency": "Quarterly", "Status": "YELLOW", "Evidence": "Budget-to-actual data exists but CSCG commentary not verifiable"},
        # Contract Compliance
        {"Category": "Contract Compliance", "Demand": "Current insurance certificates (GL, workers comp, D&O)",
         "Frequency": "Annual", "Status": "RED", "Evidence": "Manual review required"},
        {"Category": "Contract Compliance", "Demand": "Annual management fee reconciliation vs. contract terms",
         "Frequency": "Annual", "Status": d10_status, "Evidence": d10_evidence},
        {"Category": "Contract Compliance", "Demand": "Proof of regulatory compliance (health dept, fire, refrigerant)",
         "Frequency": "Annual", "Status": "RED", "Evidence": "Manual review required"},
        # Operational Transparency
        {"Category": "Operational Transparency", "Demand": "Read-only access to operating bank account",
         "Frequency": "One-time", "Status": "RED", "Evidence": "Manual review required"},
        {"Category": "Operational Transparency", "Demand": "Monthly auto-pay transaction log with categorization",
         "Frequency": "Monthly", "Status": d13_status, "Evidence": d13_evidence},
        # Board Communication
        {"Category": "Board Communication", "Demand": "Board meeting prep materials delivered 5+ business days in advance",
         "Frequency": "Per meeting", "Status": "RED", "Evidence": "Manual review required"},
        {"Category": "Board Communication", "Demand": "Written response to board questions within 10 business days",
         "Frequency": "As needed", "Status": "RED", "Evidence": "Manual review required"},
    ]

    return pd.DataFrame(demands)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_loader.py::TestComputeBoardDemands -v`
Expected: All 11 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: All 29 tests PASS (18 existing + 11 new)

- [ ] **Step 7: Commit**

```bash
git add utils/data_loader.py tests/test_data_loader.py
git commit -m "feat: add compute_board_demands() with 15 auto-detected demand items"
```

---

## Chunk 2: Page 6 UI — Board Demands Section

### Task 3: Add Board Demands section to Page 6

**Files:**
- Modify: `pages/6_CSCG_Scorecard.py` (insert between line 271 and line 273)

- [ ] **Step 8: Add import for compute_board_demands**

In `pages/6_CSCG_Scorecard.py`, add `compute_board_demands` to the import block at line 24-29:

```python
from utils.data_loader import (
    compute_board_demands,
    compute_cscg_scorecard,
    load_cscg_relationship,
    load_expense_flow_summary,
    load_unauthorized_modifications,
)
```

- [ ] **Step 9: Insert Board Demands section before AI Assessment**

Insert the following between the end of the "Unauthorized Modifications" section (after line 271) and the "AI Assessment" section (line 273). The new section goes right before `# ── AI Assessment`:

```python
# ── Board Demands ─────────────────────────────────────────────────────────
st.markdown("---")
st.header("Board Demands — What NSIA Needs From CSCG")
st.markdown(
    "Specific documents, reports, and actions the board should require from the management company. "
    "Status is auto-detected from dashboard data where possible."
)

demands = compute_board_demands()
n_green = len(demands[demands["Status"] == "GREEN"])
n_yellow = len(demands[demands["Status"] == "YELLOW"])
n_red = len(demands[demands["Status"] == "RED"])

# Summary KPIs
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Demands Met", f"{n_green} / {len(demands)}")
with col2:
    st.metric("Outstanding", n_red)
with col3:
    st.metric("Needs Verification", n_yellow)

# Compliance progress bar
fig_prog = go.Figure()
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_green],
    name=f"Met ({n_green})",
    orientation="h",
    marker=dict(color="#00d084"),
    text=f"{n_green}" if n_green > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Met: {n_green}<extra></extra>",
))
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_yellow],
    name=f"Verify ({n_yellow})",
    orientation="h",
    marker=dict(color="#fcb900"),
    text=f"{n_yellow}" if n_yellow > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Needs Verification: {n_yellow}<extra></extra>",
))
fig_prog.add_trace(go.Bar(
    y=["Board Demands"],
    x=[n_red],
    name=f"Outstanding ({n_red})",
    orientation="h",
    marker=dict(color="#eb144c"),
    text=f"{n_red}" if n_red > 0 else "",
    textposition="inside",
    textfont=dict(color="#fff", size=14, family="Arial Black"),
    hovertemplate=f"Outstanding: {n_red}<extra></extra>",
))
fig_prog.update_layout(
    barmode="stack",
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                font=dict(color="#a8b2d1")),
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
)
style_chart(fig_prog, 120)
st.plotly_chart(fig_prog, use_container_width=True)

# Demand table as styled HTML
status_colors = {"GREEN": "#00d084", "YELLOW": "#fcb900", "RED": "#eb144c"}

html_rows = ""
for _, row in demands.iterrows():
    color = status_colors.get(row["Status"], "#eb144c")
    pill = (f'<span style="background:{color}33;color:{color};padding:2px 10px;'
            f'border-radius:10px;font-weight:bold;font-size:0.85rem;">{row["Status"]}</span>')
    html_rows += (
        f'<tr style="border-bottom:1px solid rgba(168,178,209,0.15);">'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.85rem;">{row["Category"]}</td>'
        f'<td style="padding:8px 12px;color:#e6f1ff;">{row["Demand"]}</td>'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.85rem;">{row["Frequency"]}</td>'
        f'<td style="padding:8px 12px;text-align:center;">{pill}</td>'
        f'<td style="padding:8px 12px;color:#a8b2d1;font-size:0.8rem;">{row["Evidence"]}</td>'
        f'</tr>'
    )

html_table = f'''
<div style="overflow-x:auto;">
<table style="width:100%;border-collapse:collapse;background:rgba(10,25,47,0.5);border-radius:8px;">
<thead>
<tr style="border-bottom:2px solid rgba(168,178,209,0.3);">
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Category</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Demand</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Frequency</th>
    <th style="padding:10px 12px;text-align:center;color:#64ffda;font-size:0.85rem;">Status</th>
    <th style="padding:10px 12px;text-align:left;color:#64ffda;font-size:0.85rem;">Evidence</th>
</tr>
</thead>
<tbody>
{html_rows}
</tbody>
</table>
</div>
'''
st.markdown(html_table, unsafe_allow_html=True)
```

- [ ] **Step 10: Extend AI Assessment context with Board Demands summary**

In the same file, find the AI Assessment section where `scorecard_summary` is built. The Board Demands context must be added **outside** the `if not mods_filtered.empty:` block (which ends after `scorecard_summary += mods_filtered.to_csv(index=False)`) and **before** the `with st.spinner(...)` line. It should always run, not conditionally. The indentation should be 8 spaces (inside the `if st.button(...)` block but outside the `if not mods_filtered.empty:` block):

```python
        # Add Board Demands summary
        scorecard_summary += f"\n=== BOARD DEMANDS STATUS ===\n"
        scorecard_summary += f"Met: {n_green}/15 | Needs Verification: {n_yellow} | Outstanding: {n_red}\n"
        scorecard_summary += demands.to_csv(index=False)
```

- [ ] **Step 11: Verify the page loads**

Run: `python -c "from pages import *; print('imports OK')"` — this won't fully work since Streamlit pages need a running server. Instead:

Run: `python -c "from utils.data_loader import compute_board_demands; print('import OK')"`
Expected: `import OK`

Then manually verify by running `streamlit run app.py` and navigating to the CSCG Scorecard page.

- [ ] **Step 12: Commit**

```bash
git add pages/6_CSCG_Scorecard.py
git commit -m "feat: add Board Demands section to CSCG Scorecard page"
```

---

## Chunk 3: Final Verification and Cleanup

### Task 4: Run full test suite and verify

- [ ] **Step 13: Run full test suite**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: All 29 tests PASS

- [ ] **Step 14: Verify import chain is clean**

Run: `python -c "from utils.data_loader import compute_board_demands; r = compute_board_demands.__wrapped__(); print(f'{len(r)} demands, columns: {list(r.columns)}')"`
Expected: `15 demands, columns: ['Category', 'Demand', 'Frequency', 'Status', 'Evidence']`

- [ ] **Step 15: Push**

```bash
git push
```
