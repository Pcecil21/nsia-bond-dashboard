"""
Bank CSV parser with format detection for Chase, BMO, and generic CSVs.
Normalizes transactions to a standard schema for the NSIA dashboard.
"""
import io
import re
from datetime import datetime

import pandas as pd


# ── Format signatures ────────────────────────────────────────────────────

CHASE_HEADER = "Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #"
BMO_HEADER = "Date,Description,Withdrawals,Deposits,Balance"


def detect_format(file_bytes: bytes) -> str | None:
    """Detect bank CSV format from header row.

    Returns 'chase', 'bmo', 'generic', or None if the file is empty / not CSV.
    """
    try:
        text = file_bytes.decode("utf-8-sig").strip()
    except (UnicodeDecodeError, AttributeError):
        return None

    if not text:
        return None

    first_line = text.split("\n")[0].strip().rstrip(",")

    if first_line == CHASE_HEADER:
        return "chase"
    if first_line == BMO_HEADER:
        return "bmo"

    # Generic: needs at least a date-like and amount-like column
    cols_lower = [c.strip().lower() for c in first_line.split(",")]
    has_date = any(d in c for c in cols_lower for d in ("date",))
    has_amount = any(a in c for c in cols_lower for a in ("amount", "withdrawal", "deposit", "debit", "credit"))
    has_desc = any(d in c for c in cols_lower for d in ("description", "desc", "memo", "payee", "name"))

    if has_date and has_amount and has_desc:
        return "generic"

    return None


def _parse_date(value: str) -> datetime | None:
    """Try MM/DD/YYYY then YYYY-MM-DD."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def parse_bank_csv(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, list[str]]:
    """Parse a bank CSV into standardized columns.

    Returns (DataFrame, list_of_error_messages).
    DataFrame columns: date, description, amount, balance, category, source_file, import_date
    """
    fmt = detect_format(file_bytes)
    if fmt is None:
        return pd.DataFrame(columns=["date", "description", "amount", "balance",
                                      "category", "source_file", "import_date"]), \
               ["Unknown or empty file format"]

    errors: list[str] = []
    rows: list[dict] = []
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        df_raw = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except Exception as e:
        return pd.DataFrame(columns=["date", "description", "amount", "balance",
                                      "category", "source_file", "import_date"]), \
               [f"CSV read error: {e}"]

    if fmt == "chase":
        for idx, row in df_raw.iterrows():
            try:
                dt = _parse_date(row["Posting Date"])
                if dt is None:
                    raise ValueError(f"bad date: {row['Posting Date']}")
                amount = float(row["Amount"])
                balance = float(row["Balance"]) if row.get("Balance", "").strip() else None
                rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "description": row["Description"].strip(),
                    "amount": amount,
                    "balance": balance,
                    "category": "",
                    "source_file": filename,
                    "import_date": today,
                })
            except Exception as e:
                errors.append(f"Row {idx + 2}: {e}")

    elif fmt == "bmo":
        for idx, row in df_raw.iterrows():
            try:
                dt = _parse_date(row["Date"])
                if dt is None:
                    raise ValueError(f"bad date: {row['Date']}")
                withdrawal = float(row["Withdrawals"]) if row.get("Withdrawals", "").strip() else 0.0
                deposit = float(row["Deposits"]) if row.get("Deposits", "").strip() else 0.0
                amount = deposit - withdrawal
                balance = float(row["Balance"]) if row.get("Balance", "").strip() else None
                rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "description": row["Description"].strip(),
                    "amount": amount,
                    "balance": balance,
                    "category": "",
                    "source_file": filename,
                    "import_date": today,
                })
            except Exception as e:
                errors.append(f"Row {idx + 2}: {e}")

    elif fmt == "generic":
        # Find columns by name heuristics
        col_map = {}
        for col in df_raw.columns:
            cl = col.strip().lower()
            if "date" in cl and "date" not in col_map:
                col_map["date"] = col
            elif any(k in cl for k in ("description", "desc", "memo", "payee", "name")) and "description" not in col_map:
                col_map["description"] = col
            elif any(k in cl for k in ("amount", "debit", "credit")) and "amount" not in col_map:
                col_map["amount"] = col
            elif "balance" in cl and "balance" not in col_map:
                col_map["balance"] = col

        for idx, row in df_raw.iterrows():
            try:
                dt = _parse_date(row[col_map["date"]])
                if dt is None:
                    raise ValueError(f"bad date: {row[col_map['date']]}")
                amount = float(row[col_map["amount"]])
                balance = None
                if "balance" in col_map and row.get(col_map["balance"], "").strip():
                    balance = float(row[col_map["balance"]])
                rows.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "description": row[col_map["description"]].strip(),
                    "amount": amount,
                    "balance": balance,
                    "category": "",
                    "source_file": filename,
                    "import_date": today,
                })
            except Exception as e:
                errors.append(f"Row {idx + 2}: {e}")

    result = pd.DataFrame(rows, columns=["date", "description", "amount", "balance",
                                          "category", "source_file", "import_date"])
    return result, errors


def deduplicate(new_df: pd.DataFrame, existing_df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows from new_df that already exist in existing_df.

    Match on exact date + exact amount + case-insensitive description.
    """
    if existing_df.empty or new_df.empty:
        return new_df

    # Build a set of (date, amount, description_lower) from existing
    existing_keys = set()
    for _, row in existing_df.iterrows():
        key = (str(row["date"]), float(row["amount"]), str(row["description"]).lower())
        existing_keys.add(key)

    mask = []
    for _, row in new_df.iterrows():
        key = (str(row["date"]), float(row["amount"]), str(row["description"]).lower())
        mask.append(key not in existing_keys)

    return new_df[mask].reset_index(drop=True)
