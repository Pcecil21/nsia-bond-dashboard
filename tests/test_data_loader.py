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
