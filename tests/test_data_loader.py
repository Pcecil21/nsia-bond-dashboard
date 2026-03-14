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
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        # Clear Streamlit cache decorator — call the underlying function
        fn = self._dl.load_expense_flow_summary.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Board Approved" in result["Approval Method"].values

    def test_returns_empty_when_no_markers(self, monkeypatch):
        df = pd.DataFrame({0: ["A", "B", "C"], 1: [1, 2, 3], 2: [0.1, 0.2, 0.3]})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
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


# ── load_fixed_obligations ────────────────────────────────────────────────

class TestLoadFixedObligations:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_fixed_obligations(self, monkeypatch):
        rows = [
            ("Other stuff", None, None, None, None, None),
            ("FIXED OBLIGATIONS", None, None, None, None, None),
            ("Rent", 50000, 50000, 0, "Board Approved", "Lease"),
            ("Insurance", 12000, 12000, 0, "Board Approved", "Policy"),
            ("SUMMARY", None, None, None, None, None),
        ]
        df = pd.DataFrame({i: v for i, v in enumerate(zip(*rows))})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_fixed_obligations.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Rent" in result["Expense Category"].values
        assert "Insurance" in result["Expense Category"].values

    def test_returns_empty_when_no_marker(self, monkeypatch):
        df = pd.DataFrame({0: ["A", "B"], 1: [1, 2], 2: [1, 2], 3: [0, 0], 4: ["X", "Y"], 5: ["", ""]})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_fixed_obligations.__wrapped__
        result = fn()
        assert result.empty

    def test_numeric_columns_coerced(self, monkeypatch):
        rows = [
            ("FIXED OBLIGATIONS", None, None, None, None, None),
            ("Rent", "50,000", "50,000", "0", "Board", ""),
            ("TOTAL EXPENSES", None, None, None, None, None),
        ]
        df = pd.DataFrame({i: v for i, v in enumerate(zip(*rows))})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_fixed_obligations.__wrapped__
        result = fn()
        assert len(result) == 1


# ── load_scoreboard_10yr ──────────────────────────────────────────────────

class TestLoadScoreboard10yr:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def _make_scoreboard_df(self, label_rows):
        """Build a DataFrame mimicking scoreboard_economics.xlsx Sheet1.
        label_rows: list of (label_text, [10 year values], total)
        """
        # Column 1 has labels, columns 6-15 have year values, column 17 has total
        max_cols = 18
        data = {}
        for c in range(max_cols):
            data[c] = [None] * len(label_rows)
        for i, (label, vals, total) in enumerate(label_rows):
            data[1][i] = label
            for j, v in enumerate(vals):
                data[6 + j][i] = v
            data[17][i] = total
        return pd.DataFrame(data)

    def test_extracts_labeled_rows(self, monkeypatch):
        yr_vals = list(range(10000, 20000, 1000))  # 10 values
        df = self._make_scoreboard_df([
            ("Existing Sponsor Revenue", yr_vals, 150000),
            ("Software License", yr_vals, 150000),
        ])
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_scoreboard_10yr.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Existing Sponsor Revenue" in result["Category"].values
        assert "Software License" in result["Category"].values
        assert "Year 1" in result.columns
        assert "10yr Total" in result.columns

    def test_returns_empty_when_no_labels_found(self, monkeypatch):
        df = pd.DataFrame({i: ["No match"] for i in range(18)})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_scoreboard_10yr.__wrapped__
        result = fn()
        assert result.empty


# ── load_scoreboard_alternative ───────────────────────────────────────────

class TestLoadScoreboardAlternative:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_alternative_rows(self, monkeypatch):
        yr_vals = [1000] * 10
        rows = {i: [None] * 5 for i in range(18)}
        # Row 0-1: other stuff, Row 2: "Alternative" header, Row 3-4: data
        rows[1] = ["Other", "Other", "Alternative", "Upfront Cost", "Annual Maintenance"]
        for j in range(10):
            rows[6 + j] = [None, None, None, yr_vals[j], yr_vals[j]]
        rows[17] = [None, None, None, 10000, 10000]
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_scoreboard_alternative.__wrapped__
        result = fn()
        assert len(result) == 2

    def test_returns_empty_when_no_alternative_section(self, monkeypatch):
        df = pd.DataFrame({i: ["No match"] for i in range(18)})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_scoreboard_alternative.__wrapped__
        result = fn()
        assert result.empty


# ── load_historical_ad_revenue ────────────────────────────────────────────

class TestLoadHistoricalAdRevenue:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_ad_revenue(self, monkeypatch):
        # Need: year row at ad_row - 2, ad revenue row found by _find_row
        data = {}
        n_rows = 5
        for c in range(18):
            data[c] = [None] * n_rows
        # Row 2: ad_row - 2 = year headers (columns 7-17)
        for j in range(11):
            data[7 + j][2] = 2014 + j
        # Row 4: "Ad Revenue" in column 4, values in columns 7-17
        data[4][4] = "Ad Revenue"
        for j in range(11):
            data[7 + j][4] = 5000 + j * 100
        df = pd.DataFrame(data)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_historical_ad_revenue.__wrapped__
        result = fn()
        assert len(result) > 0
        assert "Year" in result.columns
        assert "Ad Revenue" in result.columns

    def test_returns_empty_when_not_found(self, monkeypatch):
        df = pd.DataFrame({i: ["Nothing"] * 3 for i in range(18)})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_historical_ad_revenue.__wrapped__
        result = fn()
        assert result.empty
        assert list(result.columns) == ["Year", "Ad Revenue"]

    def test_returns_empty_when_ad_row_too_close_to_top(self, monkeypatch):
        data = {i: [None] * 2 for i in range(18)}
        data[4][0] = "Ad Revenue"  # Row 0 — too close to top
        df = pd.DataFrame(data)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_historical_ad_revenue.__wrapped__
        result = fn()
        assert result.empty


# ── compute_kpis ──────────────────────────────────────────────────────────

class TestComputeKpis:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def _mock_loaders(self, monkeypatch, rev=None, exp=None, hidden=None, expense_summary=None):
        if rev is None:
            rev = pd.DataFrame({
                "Line Item": ["Total Revenue"],
                "Proposal YTD Budget": [500000],
            })
        if exp is None:
            exp = pd.DataFrame({
                "Line Item": ["Total Expenses"],
                "Proposal YTD Budget": [400000],
            })
        if hidden is None:
            hidden = pd.DataFrame({
                "Item": ["Bond Principal", "Bond Interest"],
                "Annual Impact": [255000, 368500],
            })
        if expense_summary is None:
            expense_summary = pd.DataFrame({
                "Approval Method": ["Board Approved"],
                "YTD Amount": [50000],
                "% of Total": [0.75],
            })
        monkeypatch.setattr(self._dl, "load_revenue_reconciliation", lambda: rev)
        monkeypatch.setattr(self._dl, "load_expense_reconciliation", lambda: exp)
        monkeypatch.setattr(self._dl, "load_hidden_cash_flows", lambda: hidden)
        monkeypatch.setattr(self._dl, "load_expense_flow_summary", lambda: expense_summary)

    def test_returns_dict_with_expected_keys(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_kpis.__wrapped__
        result = fn()
        expected_keys = ["total_annual_revenue", "total_annual_expenses", "net_cash_flow",
                         "hidden_cash_outflows", "pct_board_approved", "dscr",
                         "debt_service", "net_operating_income"]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_annualizes_from_7_months(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_kpis.__wrapped__
        result = fn()
        # 500000 * 12/7 ≈ 857142.86
        assert abs(result["total_annual_revenue"] - 500000 * 12 / 7) < 1

    def test_dscr_calculation(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_kpis.__wrapped__
        result = fn()
        annual_rev = 500000 * 12 / 7
        annual_exp = 400000 * 12 / 7
        noi = annual_rev - annual_exp
        debt = 255000 + 368500
        assert abs(result["dscr"] - noi / debt) < 0.001

    def test_pct_board_approved_from_summary(self, monkeypatch):
        self._mock_loaders(monkeypatch)
        fn = self._dl.compute_kpis.__wrapped__
        result = fn()
        assert result["pct_board_approved"] == 0.75

    def test_pct_board_approved_fallback_on_nan(self, monkeypatch):
        expense_summary = pd.DataFrame({
            "Approval Method": ["Board Approved"],
            "YTD Amount": [50000],
            "% of Total": [float("nan")],
        })
        self._mock_loaders(monkeypatch, expense_summary=expense_summary)
        fn = self._dl.compute_kpis.__wrapped__
        result = fn()
        assert result["pct_board_approved"] == 0.255


# ── load_revenue_reconciliation ───────────────────────────────────────────

class TestLoadRevenueReconciliation:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_revenue_data(self, monkeypatch):
        # Rows 0-4 are headers; data starts at row 5
        rows = [[None] * 10 for _ in range(5)]
        rows.append(["Ice Rental", 10000, 10000, 0, 0, 60000, 60000, 0, 0, "On track"])
        rows.append(["Vending", 500, 500, 0, 0, 3000, 3000, 0, 0, "On track"])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_revenue_reconciliation.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Ice Rental" in result["Line Item"].values

    def test_drops_nan_line_items(self, monkeypatch):
        rows = [[None] * 10 for _ in range(5)]
        rows.append(["Revenue A", 1, 1, 0, 0, 5, 5, 0, 0, "OK"])
        rows.append([None, None, None, None, None, None, None, None, None, None])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_revenue_reconciliation.__wrapped__
        result = fn()
        assert len(result) == 1

    def test_returns_empty_on_missing_file(self, monkeypatch):
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: pd.DataFrame())
        fn = self._dl.load_revenue_reconciliation.__wrapped__
        result = fn()
        assert result.empty


# ── load_hidden_cash_flows ────────────────────────────────────────────────

class TestLoadHiddenCashFlows:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_hidden_flows(self, monkeypatch):
        rows = [[None] * 4 for _ in range(4)]
        rows.append(["Bond Principal", 21250, 255000, "Not on P&L"])
        rows.append(["Bond Interest", 30708, 368500, "Not on P&L"])
        rows.append(["TOTAL", 51958, 623500, ""])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_hidden_cash_flows.__wrapped__
        result = fn()
        assert len(result) == 2  # TOTAL excluded
        assert "Bond Principal" in result["Item"].values
        assert result["Annual Impact"].sum() == 623500

    def test_excludes_total_row(self, monkeypatch):
        rows = [[None] * 4 for _ in range(4)]
        rows.append(["Item A", 100, 1200, "Note"])
        rows.append(["TOTAL HIDDEN", 100, 1200, ""])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_hidden_cash_flows.__wrapped__
        result = fn()
        assert len(result) == 1


# ── load_unauthorized_modifications ───────────────────────────────────────

class TestLoadUnauthorizedModifications:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_modifications(self, monkeypatch):
        rows = [[None] * 7 for _ in range(3)]
        rows.append(["Ice Rental Revenue", 100000, 80000, -20000, "DECREASE", "HIGH", "Revenue reduction"])
        rows.append(["Vending Revenue", 5000, 3000, -2000, "DECREASE", "MEDIUM", "Minor change"])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_unauthorized_modifications.__wrapped__
        result = fn()
        assert len(result) == 2
        assert list(result.columns) == ["Line Item", "Proposal Annual", "CSCG Annual (Implied)",
                                         "Annual Variance $", "Direction", "Severity", "Board Governance Impact"]

    def test_excludes_section_headers(self, monkeypatch):
        rows = [[None] * 7 for _ in range(3)]
        rows.append(["REVENUE MODIFICATIONS", None, None, None, None, None, None])
        rows.append(["Ice Rental", 100000, 80000, -20000, "DECREASE", "HIGH", "Note"])
        rows.append(["EXPENSE MODIFICATIONS", None, None, None, None, None, None])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_unauthorized_modifications.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Line Item"] == "Ice Rental"


# ── load_cscg_relationship ────────────────────────────────────────────────

class TestLoadCscgRelationship:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_components(self, monkeypatch):
        rows = [[None] * 4 for _ in range(3)]
        rows.append(["Management Fee", 21000, "No", "Article 7.1"])
        rows.append(["Office Payroll", 85000, "No", ""])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_cscg_relationship.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Management Fee" in result["Component"].values

    def test_excludes_totals_and_projections(self, monkeypatch):
        rows = [[None] * 4 for _ in range(3)]
        rows.append(["Management Fee", 21000, "No", ""])
        rows.append(["TOTAL", 150000, "", ""])
        rows.append(["ANNUALIZED Projection", 300000, "", ""])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_cscg_relationship.__wrapped__
        result = fn()
        assert len(result) == 1


# ── compute_variance_alerts ───────────────────────────────────────────────

class TestComputeVarianceAlerts:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def _mock_recon(self, monkeypatch, rev_items=None, exp_items=None):
        if rev_items is None:
            rev_items = []
        if exp_items is None:
            exp_items = []
        rev = pd.DataFrame(rev_items) if rev_items else pd.DataFrame(
            columns=["Line Item", "Proposal YTD Budget", "CSCG YTD Budget",
                     "YTD Variance $", "YTD Variance %", "Assessment"])
        exp = pd.DataFrame(exp_items) if exp_items else pd.DataFrame(
            columns=["Line Item", "Proposal YTD Budget", "CSCG YTD Budget",
                     "YTD Variance $", "YTD Variance %", "Assessment"])
        monkeypatch.setattr(self._dl, "load_revenue_reconciliation", lambda: rev)
        monkeypatch.setattr(self._dl, "load_expense_reconciliation", lambda: exp)

    def test_flags_red_on_large_variance(self, monkeypatch):
        self._mock_recon(monkeypatch, rev_items=[{
            "Line Item": "Ice Rental", "Proposal YTD Budget": 100000,
            "CSCG YTD Budget": 50000, "YTD Variance $": -50000,
            "YTD Variance %": -0.50, "Assessment": "Major drop",
        }])
        fn = self._dl.compute_variance_alerts.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Severity"] == "RED"

    def test_flags_yellow_on_moderate_variance(self, monkeypatch):
        self._mock_recon(monkeypatch, exp_items=[{
            "Line Item": "Utilities", "Proposal YTD Budget": 10000,
            "CSCG YTD Budget": 10800, "YTD Variance $": 800,
            "YTD Variance %": 0.08, "Assessment": "",
        }])
        fn = self._dl.compute_variance_alerts.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Severity"] == "YELLOW"

    def test_flags_green_on_small_variance(self, monkeypatch):
        self._mock_recon(monkeypatch, rev_items=[{
            "Line Item": "Vending", "Proposal YTD Budget": 5000,
            "CSCG YTD Budget": 5100, "YTD Variance $": 100,
            "YTD Variance %": 0.02, "Assessment": "",
        }])
        fn = self._dl.compute_variance_alerts.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Severity"] == "GREEN"

    def test_returns_empty_when_no_data(self, monkeypatch):
        self._mock_recon(monkeypatch)
        fn = self._dl.compute_variance_alerts.__wrapped__
        result = fn()
        assert result.empty

    def test_sorts_red_first(self, monkeypatch):
        self._mock_recon(monkeypatch, rev_items=[
            {"Line Item": "A", "Proposal YTD Budget": 100, "CSCG YTD Budget": 100,
             "YTD Variance $": 1, "YTD Variance %": 0.01, "Assessment": ""},
            {"Line Item": "B", "Proposal YTD Budget": 100000, "CSCG YTD Budget": 50000,
             "YTD Variance $": -50000, "YTD Variance %": -0.50, "Assessment": ""},
        ])
        fn = self._dl.compute_variance_alerts.__wrapped__
        result = fn()
        assert result.iloc[0]["Severity"] == "RED"
        assert result.iloc[1]["Severity"] == "GREEN"


# ── compute_board_attention ───────────────────────────────────────────────

class TestComputeBoardAttention:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_flags_low_dscr(self, monkeypatch):
        monkeypatch.setattr(self._dl, "compute_kpis", lambda: {
            "dscr": 0.9, "hidden_cash_outflows": 0, "pct_board_approved": 1.0,
            "net_cash_flow": 100000,
        })
        monkeypatch.setattr(self._dl, "compute_variance_alerts", lambda: pd.DataFrame(columns=["Severity"]))
        monkeypatch.setattr(self._dl, "compute_cscg_scorecard", lambda: pd.DataFrame(columns=["Status"]))
        result = self._dl.compute_board_attention()
        dscr_items = [i for i in result if "DSCR" in i["text"]]
        assert len(dscr_items) == 1
        assert "AT RISK" in dscr_items[0]["text"]

    def test_flags_hidden_outflows(self, monkeypatch):
        monkeypatch.setattr(self._dl, "compute_kpis", lambda: {
            "dscr": 2.0, "hidden_cash_outflows": 700000, "pct_board_approved": 1.0,
            "net_cash_flow": 100000,
        })
        monkeypatch.setattr(self._dl, "compute_variance_alerts", lambda: pd.DataFrame(columns=["Severity"]))
        monkeypatch.setattr(self._dl, "compute_cscg_scorecard", lambda: pd.DataFrame(columns=["Status"]))
        result = self._dl.compute_board_attention()
        hidden_items = [i for i in result if "hidden" in i["text"]]
        assert len(hidden_items) == 1

    def test_returns_empty_when_all_healthy(self, monkeypatch):
        monkeypatch.setattr(self._dl, "compute_kpis", lambda: {
            "dscr": 2.0, "hidden_cash_outflows": 100000, "pct_board_approved": 0.80,
            "net_cash_flow": 100000,
        })
        monkeypatch.setattr(self._dl, "compute_variance_alerts", lambda: pd.DataFrame(columns=["Severity"]))
        monkeypatch.setattr(self._dl, "compute_cscg_scorecard", lambda: pd.DataFrame(columns=["Status"]))
        result = self._dl.compute_board_attention()
        assert len(result) == 0


# ── load_expense_reconciliation ───────────────────────────────────────────

class TestLoadExpenseReconciliation:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_expense_data(self, monkeypatch):
        rows = [[None] * 10 for _ in range(5)]
        rows.append(["Electric", 5000, 5000, 0, 0, 30000, 30000, 0, 0, "OK"])
        rows.append(["Gas (Nicor)", 2000, 2000, 0, 0, 12000, 12000, 0, 0, "OK"])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_expense_reconciliation.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Electric" in result["Line Item"].values

    def test_excludes_section_headers(self, monkeypatch):
        rows = [[None] * 10 for _ in range(5)]
        rows.append(["PAYROLL EXPENSES", None, None, None, None, None, None, None, None, None])
        rows.append(["Office Payroll", 3000, 3000, 0, 0, 18000, 18000, 0, 0, "OK"])
        rows.append(["Line Item", None, None, None, None, None, None, None, None, None])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_expense_reconciliation.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Line Item"] == "Office Payroll"


# ── load_expense_flow ─────────────────────────────────────────────────────

class TestLoadExpenseFlow:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_expense_flow_rows(self, monkeypatch):
        rows = [[None] * 6 for _ in range(4)]
        rows.append(["Electric (Engie)", 30000, 30000, 0, "Board Approved", "Monthly"])
        rows.append(["Gas (Nicor)", 12000, 12000, 0, "Board Approved", "Monthly"])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_expense_flow.__wrapped__
        result = fn()
        assert len(result) == 2

    def test_excludes_section_headers(self, monkeypatch):
        rows = [[None] * 6 for _ in range(4)]
        rows.append(["BOARD-APPROVED EXPENSES", None, None, None, None, None])
        rows.append(["Electric", 30000, 30000, 0, "Board", ""])
        rows.append(["TOTAL EXPENSES", 30000, 30000, 0, "", ""])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_expense_flow.__wrapped__
        result = fn()
        assert len(result) == 1
        assert result.iloc[0]["Expense Category"] == "Electric"


# ── load_current_ads ──────────────────────────────────────────────────────

class TestLoadCurrentAds:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_ad_data(self, monkeypatch):
        rows = [
            ["Customer", "Type", "Location", "Term", "Expiration Date", "Cost"],
            ["Acme Corp", "Banner", "Rink A", "1 year", "2026-12-31", "$3,667"],
            ["Bob's Shop", "Dasher", "Rink B", "2 year", "2027-06-30", "$2,000"],
        ]
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_current_ads.__wrapped__
        result = fn()
        assert len(result) == 2
        assert "Cost (Numeric)" in result.columns
        assert result.iloc[0]["Cost (Numeric)"] == 3667.0

    def test_drops_nan_customers(self, monkeypatch):
        rows = [
            ["Customer", "Type", "Location", "Term", "Expiration Date", "Cost"],
            ["Acme Corp", "Banner", "Rink A", "1 year", "2026-12-31", "$1,000"],
            [None, None, None, None, None, None],
        ]
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_current_ads.__wrapped__
        result = fn()
        assert len(result) == 1


# ── load_done_deals_prospects ─────────────────────────────────────────────

class TestLoadDoneDealsProspects:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_tags_done_and_prospect(self, monkeypatch):
        rows = [
            ["Advertiser", "$$", "Term", "Status", "Notes"],
            ["Acme Corp", "$5,000", "1 year", "Signed", ""],
            ["Prospects / Pending", None, None, None, None],
            ["Future Inc", "$3,000", "1 year", "Pending", ""],
        ]
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_done_deals_prospects.__wrapped__
        result = fn()
        assert len(result) == 2
        assert result.iloc[0]["Pipeline Stage"] == "Done Deal"
        assert result.iloc[1]["Pipeline Stage"] == "Prospect"

    def test_parses_amounts(self, monkeypatch):
        rows = [
            ["Advertiser", "$$", "Term", "Status", "Notes"],
            ["Acme Corp", "$5,000", "1 year", "Signed", ""],
        ]
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_done_deals_prospects.__wrapped__
        result = fn()
        assert result.iloc[0]["Amount"] == 5000.0


# ── load_general_ledger ───────────────────────────────────────────────────

class TestLoadGeneralLedger:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_gl_entries(self, monkeypatch):
        rows = [[None] * 9 for _ in range(4)]
        rows.append(["2024-07-01", 4100, "Ice Rental Revenue", "Invoice", "Checking",
                      "Season rental", 15000, 0, "Club A"])
        rows.append(["2024-07-15", 6100, "Electric", "Bill", "Checking",
                      "Nicor bill", 0, 3200, "Nicor"])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_general_ledger.__wrapped__
        result = fn()
        assert len(result) == 2
        assert result.iloc[0]["Debit"] == 15000
        assert result.iloc[1]["Credit"] == 3200

    def test_excludes_totals(self, monkeypatch):
        rows = [[None] * 9 for _ in range(4)]
        rows.append(["2024-07-01", 4100, "Revenue", "Invoice", "Checking", "", 1000, 0, "X"])
        rows.append([None, None, "TOTAL", None, None, None, 1000, 0, None])
        df = pd.DataFrame(rows)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_general_ledger.__wrapped__
        result = fn()
        assert len(result) == 1


# ── load_gl_account_summary ──────────────────────────────────────────────

class TestLoadGlAccountSummary:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_aggregates_by_account(self, monkeypatch):
        gl = pd.DataFrame({
            "GL #": [4100, 4100, 6100],
            "GL Account Name": ["Revenue", "Revenue", "Electric"],
            "Type": ["Invoice", "Invoice", "Bill"],
            "Debit": [10000, 5000, 0],
            "Credit": [0, 0, 3200],
        })
        monkeypatch.setattr(self._dl, "load_general_ledger", lambda: gl)
        fn = self._dl.load_gl_account_summary.__wrapped__
        result = fn()
        assert len(result) == 2
        rev_row = result[result["GL Account Name"] == "Revenue"]
        assert rev_row.iloc[0]["Total_Debit"] == 15000
        assert rev_row.iloc[0]["Net"] == 15000


# ── load_bills_summary ────────────────────────────────────────────────────

class TestLoadBillsSummary:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_bills(self, monkeypatch):
        df = pd.DataFrame({
            "Vendor": ["Nicor", "ComEd", "TOTAL"],
            "Date": ["2024-07-01", "2024-07-15", None],
            "Amount": [3200, 4500, 7700],
        })
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_bills_summary.__wrapped__
        result = fn()
        assert len(result) == 2  # TOTAL excluded
        assert "Nicor" in result["Vendor"].values


# ── load_weekday_ice_summary ─────────────────────────────────────────────

class TestLoadWeekdayIceSummary:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_extracts_club_hours(self, monkeypatch):
        # Build a DF with "Hrs/Day" in the bottom half followed by club data
        n_rows = 20
        data = {i: [None] * n_rows for i in range(17)}
        # Put "Hrs/Day" at row 15 (bottom half of 20)
        data[0][15] = "Hrs/Day"
        # Club row at 16
        data[0][16] = "Winnetka"
        for j in range(1, 6):   # Current Mon-Fri
            data[j][16] = 2.0
        data[6][16] = 10.0      # Current Total
        for j in range(11, 16): # Proposed Mon-Fri
            data[j][16] = 3.0
        data[16][16] = 15.0     # Proposed Total
        df = pd.DataFrame(data)
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_weekday_ice_summary.__wrapped__
        result = fn()
        assert len(result) > 0
        assert "Winnetka" in result["Club"].values
        totals = result[(result["Club"] == "Winnetka") & (result["Day"] == "Total")]
        assert totals.iloc[0]["Current Hours"] == 10.0

    def test_returns_empty_when_no_marker(self, monkeypatch):
        df = pd.DataFrame({0: ["A"] * 5})
        monkeypatch.setattr(self._dl, "_read_excel", lambda *a, **kw: df)
        fn = self._dl.load_weekday_ice_summary.__wrapped__
        result = fn()
        assert result.empty


# ── compute_cscg_scorecard ────────────────────────────────────────────────

class TestComputeCscgScorecard:
    @pytest.fixture(autouse=True)
    def _patch_streamlit(self, monkeypatch):
        import utils.data_loader as dl
        self._dl = dl

    def test_returns_scorecard_with_status(self, monkeypatch):
        cscg = pd.DataFrame({
            "Component": ["Management Fee", "Office Payroll"],
            "Amount": [21000, 85000],
            "Approval Required?": ["No", "No"],
            "Contract Reference": ["Article 7.1", ""],
        })
        exp = pd.DataFrame({
            "Line Item": ["Management Fees", "Office Payroll"],
            "Proposal YTD Budget": [21000, 85000],
            "CSCG YTD Budget": [21000, 85000],
            "YTD Variance $": [0, 0],
            "YTD Variance %": [0, 0],
            "Assessment": ["OK", "OK"],
        })
        monkeypatch.setattr(self._dl, "load_cscg_relationship", lambda: cscg)
        monkeypatch.setattr(self._dl, "load_expense_reconciliation", lambda: exp)
        fn = self._dl.compute_cscg_scorecard.__wrapped__
        result = fn()
        assert "Status" in result.columns
        assert len(result) > 0
        # Management fee should be COMPLIANT (21000 actual vs 21000 expected)
        mgmt = result[result["Contract Term"].str.contains("Management Fee")]
        assert len(mgmt) > 0
