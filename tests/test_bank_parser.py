"""Tests for bank_parser utility functions."""
import pandas as pd
import pytest
from utils.bank_parser import detect_format, parse_bank_csv, deduplicate


# ── detect_format ────────────────────────────────────────────────────────

class TestDetectFormat:
    def test_chase(self):
        header = b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        assert detect_format(header) == "chase"

    def test_bmo(self):
        header = b"Date,Description,Withdrawals,Deposits,Balance\n"
        assert detect_format(header) == "bmo"

    def test_generic(self):
        header = b"Transaction Date,Description,Amount\n"
        assert detect_format(header) == "generic"

    def test_unknown(self):
        header = b"foo,bar,baz\n"
        assert detect_format(header) is None

    def test_empty(self):
        assert detect_format(b"") is None
        assert detect_format(b"   ") is None


# ── parse_bank_csv — Chase ───────────────────────────────────────────────

class TestParseChase:
    CHASE_CSV = (
        b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
        b"DEBIT,01/15/2026,RINK SUPPLY CO,-1250.00,ACH_DEBIT,45000.00,\n"
        b"CREDIT,01/20/2026,ICE RENTAL REVENUE,3500.00,ACH_CREDIT,48500.00,\n"
    )

    def test_parses_amounts(self):
        df, errors = parse_bank_csv(self.CHASE_CSV, "chase_jan.csv")
        assert len(errors) == 0
        assert len(df) == 2
        assert df.iloc[0]["amount"] == -1250.00
        assert df.iloc[1]["amount"] == 3500.00

    def test_parses_dates(self):
        df, _ = parse_bank_csv(self.CHASE_CSV, "chase_jan.csv")
        assert df.iloc[0]["date"] == "2026-01-15"
        assert df.iloc[1]["date"] == "2026-01-20"

    def test_source_file(self):
        df, _ = parse_bank_csv(self.CHASE_CSV, "chase_jan.csv")
        assert all(df["source_file"] == "chase_jan.csv")


# ── parse_bank_csv — BMO ────────────────────────────────────────────────

class TestParseBMO:
    BMO_CSV = (
        b"Date,Description,Withdrawals,Deposits,Balance\n"
        b"01/10/2026,UTILITY PAYMENT,500.00,,9500.00\n"
        b"01/12/2026,MEMBERSHIP DUES,,2000.00,11500.00\n"
    )

    def test_withdrawal_is_negative(self):
        df, errors = parse_bank_csv(self.BMO_CSV, "bmo.csv")
        assert len(errors) == 0
        assert df.iloc[0]["amount"] == -500.00  # withdrawal

    def test_deposit_is_positive(self):
        df, _ = parse_bank_csv(self.BMO_CSV, "bmo.csv")
        assert df.iloc[1]["amount"] == 2000.00  # deposit

    def test_balance_parsed(self):
        df, _ = parse_bank_csv(self.BMO_CSV, "bmo.csv")
        assert df.iloc[0]["balance"] == 9500.00
        assert df.iloc[1]["balance"] == 11500.00


# ── parse_bank_csv — Generic ────────────────────────────────────────────

class TestParseGeneric:
    def test_iso_dates(self):
        csv = b"Date,Description,Amount\n2026-02-01,Test Transaction,100.00\n"
        df, errors = parse_bank_csv(csv, "generic.csv")
        assert len(errors) == 0
        assert df.iloc[0]["date"] == "2026-02-01"

    def test_missing_balance_column(self):
        csv = b"Date,Description,Amount\n01/01/2026,No Balance,50.00\n"
        df, errors = parse_bank_csv(csv, "test.csv")
        assert len(errors) == 0
        assert df.iloc[0]["balance"] is None


# ── Error handling ───────────────────────────────────────────────────────

class TestErrorHandling:
    def test_bad_rows_skipped(self):
        csv = (
            b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
            b"DEBIT,01/15/2026,GOOD ROW,-100.00,ACH_DEBIT,5000.00,\n"
            b"DEBIT,BADDATE,BAD ROW,notanumber,ACH_DEBIT,5000.00,\n"
            b"CREDIT,01/20/2026,ANOTHER GOOD,200.00,ACH_CREDIT,5200.00,\n"
        )
        df, errors = parse_bank_csv(csv, "test.csv")
        assert len(df) == 2
        assert len(errors) == 1
        assert "Row 3" in errors[0]

    def test_empty_file(self):
        df, errors = parse_bank_csv(b"", "empty.csv")
        assert df.empty
        assert len(errors) > 0

    def test_unknown_format_returns_empty(self):
        csv = b"foo,bar,baz\n1,2,3\n"
        df, errors = parse_bank_csv(csv, "weird.csv")
        assert df.empty
        assert len(errors) > 0


# ── deduplicate ──────────────────────────────────────────────────────────

class TestDeduplicate:
    def test_removes_exact_matches(self):
        existing = pd.DataFrame({
            "date": ["2026-01-15"],
            "description": ["RINK SUPPLY CO"],
            "amount": [-1250.00],
            "balance": [45000.00],
        })
        new = pd.DataFrame({
            "date": ["2026-01-15", "2026-01-20"],
            "description": ["Rink Supply Co", "NEW TRANSACTION"],
            "amount": [-1250.00, 500.00],
            "balance": [45000.00, 45500.00],
        })
        result = deduplicate(new, existing)
        assert len(result) == 1
        assert result.iloc[0]["description"] == "NEW TRANSACTION"

    def test_empty_existing_returns_all(self):
        new = pd.DataFrame({
            "date": ["2026-01-15"],
            "description": ["TEST"],
            "amount": [100.0],
        })
        existing = pd.DataFrame(columns=["date", "description", "amount"])
        result = deduplicate(new, existing)
        assert len(result) == 1

    def test_empty_new_returns_empty(self):
        existing = pd.DataFrame({
            "date": ["2026-01-15"],
            "description": ["TEST"],
            "amount": [100.0],
        })
        new = pd.DataFrame(columns=["date", "description", "amount"])
        result = deduplicate(new, existing)
        assert len(result) == 0
