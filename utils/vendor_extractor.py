"""
Vendor extraction, fuzzy deduplication, and merge utilities.

Extracts vendor records from bills_summary.xlsx and general_ledger.xlsx,
performs fuzzy name matching to find duplicates, and supports merging
with an existing vendor master to preserve manual edits.
"""
import uuid
from difflib import SequenceMatcher

import pandas as pd

MANUAL_FIELDS = [
    "contract_start",
    "contract_end",
    "contract_terms",
    "contract_doc_id",
    "compliance_notes",
    "risk_flag",
    "category",
]

HIGH_RISK_KEYWORDS = ["CSCG", "Canlan"]


def _generate_vendor_id() -> str:
    """Generate a deterministic-format UUID for a vendor."""
    return str(uuid.uuid4())


def extract_vendors_from_bills(bills_df: pd.DataFrame) -> pd.DataFrame:
    """Extract vendor master records from bills_summary data.

    Args:
        bills_df: DataFrame with columns Date, Vendor, Amount, Category.

    Returns:
        DataFrame with one row per vendor, aggregated metrics, and empty manual fields.
    """
    if bills_df.empty:
        cols = [
            "vendor_id", "vendor_name", "total_spend_ytd", "payment_count",
            "first_seen", "last_seen", "category", "risk_flag", "aliases",
            "contract_start", "contract_end", "contract_terms",
            "contract_doc_id", "compliance_notes",
        ]
        return pd.DataFrame(columns=cols)

    # Filter out summary rows
    bills_df = bills_df[~bills_df["Vendor"].str.upper().isin(["TOTAL", "GRAND TOTAL"])]

    grouped = bills_df.groupby("Vendor").agg(
        total_spend_ytd=("Amount", "sum"),
        payment_count=("Amount", "count"),
        first_seen=("Date", "min"),
        last_seen=("Date", "max"),
    ).reset_index()

    # Most common category per vendor
    cat_mode = (
        bills_df.groupby("Vendor")["Category"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "Other")
        .reset_index()
    )
    grouped = grouped.merge(cat_mode, on="Vendor", how="left")
    grouped.rename(columns={"Vendor": "vendor_name", "Category": "category"}, inplace=True)

    # Generate IDs
    grouped["vendor_id"] = [_generate_vendor_id() for _ in range(len(grouped))]

    # Pre-flag high-risk vendors
    grouped["risk_flag"] = grouped["vendor_name"].apply(
        lambda name: "High"
        if any(kw.lower() in name.lower() for kw in HIGH_RISK_KEYWORDS)
        else None
    )

    # Aliases column (empty initially)
    grouped["aliases"] = ""

    # Empty manual fields
    for field in ["contract_start", "contract_end", "contract_terms",
                  "contract_doc_id", "compliance_notes"]:
        grouped[field] = None

    return grouped


def extract_vendors_from_gl(gl_df: pd.DataFrame) -> pd.DataFrame:
    """Extract vendor records from the general ledger.

    The GL file has title/note rows at the top. This function finds the header
    row containing 'Payee', sets it as column names, and extracts data below.

    Args:
        gl_df: Raw DataFrame read from general_ledger.xlsx with header=None.

    Returns:
        DataFrame with one row per payee, aggregated spend from Debit column.
    """
    # Find the header row containing "Payee"
    header_row = None
    for idx in range(min(10, len(gl_df))):
        row_vals = gl_df.iloc[idx].astype(str).str.strip()
        if row_vals.str.contains("Payee", case=False, na=False).any():
            header_row = idx
            break

    if header_row is None:
        # Return empty DataFrame if no header found
        cols = [
            "vendor_id", "vendor_name", "total_spend_ytd", "payment_count",
            "first_seen", "last_seen", "category", "risk_flag", "aliases",
            "contract_start", "contract_end", "contract_terms",
            "contract_doc_id", "compliance_notes",
        ]
        return pd.DataFrame(columns=cols)

    # Set header row as columns and extract data below
    gl_clean = gl_df.iloc[header_row + 1:].copy()
    gl_clean.columns = gl_df.iloc[header_row].values

    # Clean up: drop rows where Payee is NaN
    gl_clean = gl_clean.dropna(subset=["Payee"])
    gl_clean = gl_clean[gl_clean["Payee"].astype(str).str.strip() != ""]

    # Convert Debit to numeric
    gl_clean["Debit"] = pd.to_numeric(gl_clean["Debit"], errors="coerce").fillna(0)

    # Group by Payee
    grouped = gl_clean.groupby("Payee").agg(
        total_spend_ytd=("Debit", "sum"),
        payment_count=("Debit", "count"),
    ).reset_index()

    grouped.rename(columns={"Payee": "vendor_name"}, inplace=True)
    grouped["vendor_id"] = [_generate_vendor_id() for _ in range(len(grouped))]
    grouped["category"] = "Other"
    grouped["first_seen"] = None
    grouped["last_seen"] = None
    grouped["aliases"] = ""

    # Pre-flag high-risk vendors
    grouped["risk_flag"] = grouped["vendor_name"].apply(
        lambda name: "High"
        if any(kw.lower() in str(name).lower() for kw in HIGH_RISK_KEYWORDS)
        else None
    )

    # Empty manual fields
    for field in ["contract_start", "contract_end", "contract_terms",
                  "contract_doc_id", "compliance_notes"]:
        grouped[field] = None

    return grouped


def fuzzy_dedup(df: pd.DataFrame, threshold: float = 0.85) -> list[dict]:
    """Find vendor name pairs that are likely duplicates using fuzzy matching.

    Args:
        df: Vendor master DataFrame with vendor_id and vendor_name columns.
        threshold: Minimum SequenceMatcher ratio to consider a match.

    Returns:
        List of dicts with keys: keep, merge, score, name_keep, name_merge.
        The alphabetically earlier vendor name is kept.
    """
    names = df[["vendor_id", "vendor_name"]].drop_duplicates().values.tolist()
    names.sort(key=lambda x: x[1].lower())

    matches = []
    seen_merges = set()

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            id_a, name_a = names[i]
            id_b, name_b = names[j]

            score = SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()
            if score >= threshold:
                # Keep alphabetically earlier name
                if name_a.lower() <= name_b.lower():
                    keep_id, merge_id = id_a, id_b
                    keep_name, merge_name = name_a, name_b
                else:
                    keep_id, merge_id = id_b, id_a
                    keep_name, merge_name = name_b, name_a

                if merge_id not in seen_merges:
                    matches.append({
                        "keep": keep_id,
                        "merge": merge_id,
                        "score": round(score, 4),
                        "name_keep": keep_name,
                        "name_merge": merge_name,
                    })
                    seen_merges.add(merge_id)

    return matches


def apply_merges(df: pd.DataFrame, approved_merges: list[dict]) -> pd.DataFrame:
    """Apply approved fuzzy merges: aggregate spend/count into keep row, drop merged rows.

    Args:
        df: Vendor master DataFrame.
        approved_merges: List of merge dicts from fuzzy_dedup (with keep/merge keys).

    Returns:
        Updated DataFrame with merged rows removed and keep rows updated.
    """
    df = df.copy()

    for merge in approved_merges:
        keep_id = merge["keep"]
        merge_id = merge["merge"]

        keep_mask = df["vendor_id"] == keep_id
        merge_mask = df["vendor_id"] == merge_id

        if not keep_mask.any() or not merge_mask.any():
            continue

        keep_row = df.loc[keep_mask].iloc[0]
        merge_row = df.loc[merge_mask].iloc[0]

        # Aggregate spend and count
        new_spend = (keep_row.get("total_spend_ytd", 0) or 0) + (merge_row.get("total_spend_ytd", 0) or 0)
        new_count = (keep_row.get("payment_count", 0) or 0) + (merge_row.get("payment_count", 0) or 0)

        df.loc[keep_mask, "total_spend_ytd"] = new_spend
        df.loc[keep_mask, "payment_count"] = new_count

        # Add merged vendor name to aliases
        existing_aliases = str(keep_row.get("aliases", "") or "")
        merged_name = str(merge_row.get("vendor_name", ""))
        if existing_aliases:
            new_aliases = f"{existing_aliases};{merged_name}"
        else:
            new_aliases = merged_name
        df.loc[keep_mask, "aliases"] = new_aliases

        # Update first_seen / last_seen
        keep_first = keep_row.get("first_seen")
        merge_first = merge_row.get("first_seen")
        if keep_first is not None and merge_first is not None:
            df.loc[keep_mask, "first_seen"] = min(keep_first, merge_first)
        elif merge_first is not None:
            df.loc[keep_mask, "first_seen"] = merge_first

        keep_last = keep_row.get("last_seen")
        merge_last = merge_row.get("last_seen")
        if keep_last is not None and merge_last is not None:
            df.loc[keep_mask, "last_seen"] = max(keep_last, merge_last)
        elif merge_last is not None:
            df.loc[keep_mask, "last_seen"] = merge_last

        # Drop merged row
        df = df[~merge_mask]

    return df.reset_index(drop=True)


def merge_with_existing(new_df: pd.DataFrame, existing_df: pd.DataFrame) -> pd.DataFrame:
    """Merge new vendor data with existing vendor master, preserving manual fields.

    Manual fields (contract_start, contract_end, contract_terms, contract_doc_id,
    compliance_notes, risk_flag, category) from existing_df are preserved when
    matching by vendor_id.

    Args:
        new_df: Freshly extracted vendor data.
        existing_df: Previously saved vendor master with manual edits.

    Returns:
        Merged DataFrame with updated calculated fields and preserved manual fields.
    """
    if existing_df.empty:
        return new_df.copy()

    if new_df.empty:
        return existing_df.copy()

    result = new_df.copy()

    # Build lookup from existing data by vendor_id
    existing_lookup = existing_df.set_index("vendor_id")

    for idx, row in result.iterrows():
        vid = row["vendor_id"]
        if vid in existing_lookup.index:
            existing_row = existing_lookup.loc[vid]
            for field in MANUAL_FIELDS:
                if field in existing_row.index:
                    existing_val = existing_row[field]
                    if pd.notna(existing_val) and existing_val != "" and existing_val is not None:
                        result.at[idx, field] = existing_val

    return result
