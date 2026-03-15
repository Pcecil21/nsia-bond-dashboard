"""Tests for vendor_extractor utilities."""
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.vendor_extractor import (
    extract_vendors_from_bills,
    extract_vendors_from_gl,
    fuzzy_dedup,
    apply_merges,
    merge_with_existing,
    MANUAL_FIELDS,
)


# ── extract_vendors_from_bills ───────────────────────────────────────────


class TestExtractVendorsFromBills:
    def _make_bills(self, rows):
        return pd.DataFrame(rows, columns=["Date", "Vendor", "Amount", "Category"])

    def test_unique_vendors(self):
        bills = self._make_bills([
            ["2025-08-01", "Vendor A", 100, "Utilities"],
            ["2025-08-02", "Vendor B", 200, "Insurance"],
            ["2025-08-03", "Vendor A", 150, "Utilities"],
        ])
        result = extract_vendors_from_bills(bills)
        assert len(result) == 2
        assert set(result["vendor_name"]) == {"Vendor A", "Vendor B"}

    def test_spend_aggregation(self):
        bills = self._make_bills([
            ["2025-08-01", "Vendor A", 100, "Utilities"],
            ["2025-08-02", "Vendor A", 250, "Utilities"],
            ["2025-08-03", "Vendor B", 300, "Insurance"],
        ])
        result = extract_vendors_from_bills(bills)
        vendor_a = result[result["vendor_name"] == "Vendor A"].iloc[0]
        assert vendor_a["total_spend_ytd"] == 350
        assert vendor_a["payment_count"] == 2

    def test_empty_dataframe(self):
        bills = pd.DataFrame(columns=["Date", "Vendor", "Amount", "Category"])
        result = extract_vendors_from_bills(bills)
        assert len(result) == 0
        assert "vendor_id" in result.columns

    def test_high_risk_flag_cscg(self):
        bills = self._make_bills([
            ["2025-08-01", "CSCG Management", 5000, "Management"],
            ["2025-08-01", "Regular Vendor", 100, "Utilities"],
        ])
        result = extract_vendors_from_bills(bills)
        cscg = result[result["vendor_name"] == "CSCG Management"].iloc[0]
        regular = result[result["vendor_name"] == "Regular Vendor"].iloc[0]
        assert cscg["risk_flag"] == "High"
        assert regular["risk_flag"] is None

    def test_high_risk_flag_canlan(self):
        bills = self._make_bills([
            ["2025-08-01", "Canlan Ice Sports", 3000, "Management"],
        ])
        result = extract_vendors_from_bills(bills)
        assert result.iloc[0]["risk_flag"] == "High"

    def test_manual_fields_present(self):
        bills = self._make_bills([
            ["2025-08-01", "Vendor A", 100, "Utilities"],
        ])
        result = extract_vendors_from_bills(bills)
        for field in ["contract_start", "contract_end", "contract_terms",
                       "contract_doc_id", "compliance_notes"]:
            assert field in result.columns

    def test_most_common_category(self):
        bills = self._make_bills([
            ["2025-08-01", "Vendor A", 100, "Utilities"],
            ["2025-08-02", "Vendor A", 200, "Utilities"],
            ["2025-08-03", "Vendor A", 50, "Insurance"],
        ])
        result = extract_vendors_from_bills(bills)
        assert result.iloc[0]["category"] == "Utilities"


# ── extract_vendors_from_gl ──────────────────────────────────────────────


class TestExtractVendorsFromGL:
    def _make_gl(self):
        """Simulate the raw GL file structure with header on row 3."""
        data = [
            ["NSIA General Ledger", None, None, None, None, None, None, None, None],
            ["Reconstructed from bank", None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None],
            ["Date", "GL #", "GL Account Name", "Type", "Bank", "Description", "Debit", "Credit", "Payee"],
            ["07/01/25", 4300, "Revenue", "Revenue", 3572, "Desc", 100.0, None, "Payee A"],
            ["07/02/25", 5100, "Expense", "Expense", 3572, "Desc", 200.0, None, "Payee A"],
            ["07/03/25", 5200, "Expense", "Expense", 3572, "Desc", 300.0, None, "Payee B"],
        ]
        return pd.DataFrame(data)

    def test_extracts_payees(self):
        gl = self._make_gl()
        result = extract_vendors_from_gl(gl)
        assert len(result) == 2
        assert set(result["vendor_name"]) == {"Payee A", "Payee B"}

    def test_aggregates_debit(self):
        gl = self._make_gl()
        result = extract_vendors_from_gl(gl)
        payee_a = result[result["vendor_name"] == "Payee A"].iloc[0]
        assert payee_a["total_spend_ytd"] == 300.0
        assert payee_a["payment_count"] == 2

    def test_no_payee_header_returns_empty(self):
        data = [
            ["A", "B", "C"],
            ["1", "2", "3"],
        ]
        gl = pd.DataFrame(data)
        result = extract_vendors_from_gl(gl)
        assert len(result) == 0


# ── fuzzy_dedup ──────────────────────────────────────────────────────────


class TestFuzzyDedup:
    def test_merges_similar_names(self):
        df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Acme Services LLC", "Acme Services"],
        })
        matches = fuzzy_dedup(df, threshold=0.85)
        assert len(matches) == 1
        assert matches[0]["name_keep"] == "Acme Services"
        assert matches[0]["name_merge"] == "Acme Services LLC"
        assert matches[0]["score"] >= 0.85

    def test_does_not_merge_different_names(self):
        df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Acme Corp", "Zillow Group"],
        })
        matches = fuzzy_dedup(df, threshold=0.85)
        assert len(matches) == 0

    def test_keeps_alphabetically_earlier(self):
        df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Zebra Services", "Zebra Svc"],
        })
        matches = fuzzy_dedup(df, threshold=0.70)
        assert len(matches) == 1
        assert matches[0]["name_keep"] == "Zebra Services"
        assert matches[0]["keep"] == "id1"

    def test_empty_dataframe(self):
        df = pd.DataFrame({"vendor_id": [], "vendor_name": []})
        matches = fuzzy_dedup(df)
        assert matches == []


# ── apply_merges ─────────────────────────────────────────────────────────


class TestApplyMerges:
    def test_aggregates_spend(self):
        df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Acme Corp", "Acme Corporation"],
            "total_spend_ytd": [1000, 500],
            "payment_count": [3, 2],
            "aliases": ["", ""],
            "first_seen": [None, None],
            "last_seen": [None, None],
        })
        merges = [{"keep": "id1", "merge": "id2", "score": 0.90,
                   "name_keep": "Acme Corp", "name_merge": "Acme Corporation"}]
        result = apply_merges(df, merges)
        assert len(result) == 1
        assert result.iloc[0]["total_spend_ytd"] == 1500
        assert result.iloc[0]["payment_count"] == 5

    def test_adds_aliases(self):
        df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Acme Corp", "Acme Corporation"],
            "total_spend_ytd": [1000, 500],
            "payment_count": [3, 2],
            "aliases": ["", ""],
            "first_seen": [None, None],
            "last_seen": [None, None],
        })
        merges = [{"keep": "id1", "merge": "id2", "score": 0.90,
                   "name_keep": "Acme Corp", "name_merge": "Acme Corporation"}]
        result = apply_merges(df, merges)
        assert "Acme Corporation" in result.iloc[0]["aliases"]

    def test_no_merges(self):
        df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [100],
            "payment_count": [1],
            "aliases": [""],
            "first_seen": [None],
            "last_seen": [None],
        })
        result = apply_merges(df, [])
        assert len(result) == 1

    def test_missing_ids_skipped(self):
        df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [100],
            "payment_count": [1],
            "aliases": [""],
            "first_seen": [None],
            "last_seen": [None],
        })
        merges = [{"keep": "id1", "merge": "id_missing", "score": 0.90,
                   "name_keep": "Vendor A", "name_merge": "Vendor AA"}]
        result = apply_merges(df, merges)
        assert len(result) == 1
        assert result.iloc[0]["total_spend_ytd"] == 100


# ── merge_with_existing ──────────────────────────────────────────────────


class TestMergeWithExisting:
    def test_preserves_manual_fields(self):
        new_df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Vendor A", "Vendor B"],
            "total_spend_ytd": [500, 300],
            "payment_count": [5, 3],
            "category": ["Utilities", "Other"],
            "risk_flag": [None, None],
            "contract_start": [None, None],
            "contract_end": [None, None],
            "contract_terms": [None, None],
            "contract_doc_id": [None, None],
            "compliance_notes": [None, None],
        })
        existing_df = pd.DataFrame({
            "vendor_id": ["id1", "id2"],
            "vendor_name": ["Vendor A", "Vendor B"],
            "total_spend_ytd": [400, 200],
            "payment_count": [4, 2],
            "category": ["Maintenance", "Insurance"],
            "risk_flag": ["High", "Low"],
            "contract_start": ["2025-01-01", None],
            "contract_end": ["2026-01-01", None],
            "contract_terms": ["Annual", None],
            "contract_doc_id": ["doc123", None],
            "compliance_notes": ["Reviewed", None],
        })
        result = merge_with_existing(new_df, existing_df)
        row_a = result[result["vendor_id"] == "id1"].iloc[0]
        # Manual fields preserved from existing
        assert row_a["risk_flag"] == "High"
        assert row_a["category"] == "Maintenance"
        assert row_a["contract_start"] == "2025-01-01"
        assert row_a["contract_terms"] == "Annual"
        # Calculated fields updated from new
        assert row_a["total_spend_ytd"] == 500
        assert row_a["payment_count"] == 5

    def test_updates_calculated_fields(self):
        new_df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [999],
            "payment_count": [10],
            "category": ["Other"],
            "risk_flag": [None],
            "contract_start": [None],
            "contract_end": [None],
            "contract_terms": [None],
            "contract_doc_id": [None],
            "compliance_notes": [None],
        })
        existing_df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [500],
            "payment_count": [5],
            "category": ["Utilities"],
            "risk_flag": ["Medium"],
            "contract_start": [None],
            "contract_end": [None],
            "contract_terms": [None],
            "contract_doc_id": [None],
            "compliance_notes": [None],
        })
        result = merge_with_existing(new_df, existing_df)
        assert result.iloc[0]["total_spend_ytd"] == 999
        assert result.iloc[0]["category"] == "Utilities"
        assert result.iloc[0]["risk_flag"] == "Medium"

    def test_empty_existing(self):
        new_df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [100],
            "payment_count": [1],
            "category": ["Other"],
            "risk_flag": [None],
            "contract_start": [None],
            "contract_end": [None],
            "contract_terms": [None],
            "contract_doc_id": [None],
            "compliance_notes": [None],
        })
        existing_df = pd.DataFrame()
        result = merge_with_existing(new_df, existing_df)
        assert len(result) == 1

    def test_empty_new(self):
        existing_df = pd.DataFrame({
            "vendor_id": ["id1"],
            "vendor_name": ["Vendor A"],
            "total_spend_ytd": [100],
            "payment_count": [1],
            "category": ["Other"],
            "risk_flag": [None],
            "contract_start": [None],
            "contract_end": [None],
            "contract_terms": [None],
            "contract_doc_id": [None],
            "compliance_notes": [None],
        })
        new_df = pd.DataFrame()
        result = merge_with_existing(new_df, existing_df)
        assert len(result) == 1
