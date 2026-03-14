"""Tests for data_loader helper functions and high-risk loaders."""
import pandas as pd
import pytest

# Import helpers directly — they don't depend on Streamlit at module level
from utils.data_loader import _find_row, _find_rows_between, _find_row_reverse


# ── _find_row ────────────────────────────────────────────────────────────

class TestFindRow:
    def _make_df(self, values):
        return pd.DataFrame({"A": values})

    def test_finds_exact_match(self):
        df = self._make_df(["Header", "Data", "Footer"])
        assert _find_row(df, 0, "Data") == 1

    def test_finds_substring_match(self):
        df = self._make_df(["SUMMARY BY APPROVAL METHOD", "Other"])
        assert _find_row(df, 0, "Approval Method") == 0

    def test_case_insensitive(self):
        df = self._make_df(["fixed obligations", "other"])
        assert _find_row(df, 0, "FIXED OBLIGATIONS") == 0

    def test_returns_none_when_not_found(self):
        df = self._make_df(["Alpha", "Beta", "Gamma"])
        assert _find_row(df, 0, "Delta") is None

    def test_returns_first_match(self):
        df = self._make_df(["Revenue", "Total Revenue", "Revenue Again"])
        assert _find_row(df, 0, "Revenue") == 0

    def test_skips_nan_values(self):
        df = self._make_df([None, float("nan"), "Target"])
        assert _find_row(df, 0, "Target") == 2

    def test_searches_specific_column(self):
        df = pd.DataFrame({"A": ["no", "no"], "B": ["no", "yes match"]})
        assert _find_row(df, 1, "match") == 1
        assert _find_row(df, 0, "match") is None


# ── _find_row_reverse ────────────────────────────────────────────────────

class TestFindRowReverse:
    def _make_df(self, values):
        return pd.DataFrame({"A": values})

    def test_finds_from_bottom(self):
        df = self._make_df(["Hrs/Day", "A", "B", "C", "D", "E", "F", "G", "H", "Hrs/Day", "X"])
        # Should find the second "Hrs/Day" at index 9 (bottom half)
        result = _find_row_reverse(df, 0, "hrs/day")
        assert result == 9

    def test_returns_none_when_not_in_bottom_half(self):
        # 10 rows, only match at index 1 — below midpoint (5), search won't reach it
        values = ["X"] * 10
        values[1] = "Hrs/Day"
        df = self._make_df(values)
        assert _find_row_reverse(df, 0, "hrs/day") is None

    def test_returns_none_when_not_found(self):
        df = self._make_df(["A", "B", "C", "D"])
        assert _find_row_reverse(df, 0, "Z") is None

    def test_custom_start_from(self):
        # 10 rows, midpoint=5. Target at 6 and 8. start_from=7 should find index 6, not 8.
        df = self._make_df(["X", "X", "X", "X", "X", "X", "Target", "X", "Target", "X"])
        assert _find_row_reverse(df, 0, "Target", start_from=7) == 6


# ── _find_rows_between ──────────────────────────────────────────────────

class TestFindRowsBetween:
    def _make_df(self, values):
        return pd.DataFrame({"A": values})

    def test_extracts_rows_between_markers(self):
        df = self._make_df(["FIXED OBLIGATIONS", "Rent", "Insurance", "SUMMARY"])
        result = _find_rows_between(df, 0, "FIXED OBLIGATIONS", ["SUMMARY"])
        assert len(result) == 2
        assert result.iloc[0, 0] == "Rent"
        assert result.iloc[1, 0] == "Insurance"

    def test_returns_empty_when_start_not_found(self):
        df = self._make_df(["Alpha", "Beta", "Gamma"])
        result = _find_rows_between(df, 0, "MISSING", ["Gamma"])
        assert result.empty

    def test_takes_all_after_start_when_no_end_marker(self):
        df = self._make_df(["START", "A", "B", "C"])
        result = _find_rows_between(df, 0, "START", ["NONEXISTENT"])
        assert len(result) == 3

    def test_multiple_end_markers(self):
        df = self._make_df(["START", "A", "B", "KEY FINDINGS", "C"])
        result = _find_rows_between(df, 0, "START", ["SUMMARY", "KEY FINDINGS"])
        assert len(result) == 2
        assert result.iloc[1, 0] == "B"

    def test_empty_between_markers(self):
        df = self._make_df(["START", "SUMMARY"])
        result = _find_rows_between(df, 0, "START", ["SUMMARY"])
        assert len(result) == 0


# ── load_expense_flow_summary (high-risk loader) ────────────────────────
# These tests use monkeypatching to avoid Streamlit dependency and Excel I/O.

class TestLoadExpenseFlowSummary:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        """Remove @st.cache_data decorator effect for testing."""
        import utils.data_loader as dl
        self._dl = dl

    def _make_expense_df(self, rows):
        """Build a minimal DataFrame mimicking expense_flow.xlsx layout."""
        return pd.DataFrame({i: v for i, v in enumerate(zip(*rows))})

    def test_finds_summary_by_primary_marker(self, monkeypatch):
        rows = [
            ("Other stuff", None, None),
            ("SUMMARY BY APPROVAL METHOD", None, None),
            ("Approval Method", "YTD Amount", "% of Total"),
            ("Board Approved", 50000, 0.45),
            ("Management", 60000, 0.55),
            ("TOTAL", 110000, 1.0),
        ]
        df = self._make_expense_df(rows)
        monkeypatch.setattr(self._dl.pd, "read_excel", lambda *a, **kw: df)
        # Clear Streamlit cache decorator — call the underlying function
        fn = self._dl.load_expense_flow_summary.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Board Approved" in result["Approval Method"].values

    def test_returns_empty_when_no_markers(self, monkeypatch):
        df = pd.DataFrame({0: ["A", "B", "C"], 1: [1, 2, 3], 2: [0.1, 0.2, 0.3]})
        monkeypatch.setattr(self._dl.pd, "read_excel", lambda *a, **kw: df)
        fn = self._dl.load_expense_flow_summary.__wrapped__
        result = fn()
        assert result.empty
        assert list(result.columns) == ["Approval Method", "YTD Amount", "% of Total"]


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
        # Demands 6 & 7 are GREEN when no unauthorized mods (correct: absence = compliance)
        # Demand 8 is YELLOW by default (budget-to-actual exists but commentary unverifiable)
        exclude = result[result["Demand"].str.contains(
            "variance explanation|pre-approval|budget-to-actual", case=False)]
        remaining = result.drop(exclude.index)
        assert (remaining["Status"] == "RED").all()

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
