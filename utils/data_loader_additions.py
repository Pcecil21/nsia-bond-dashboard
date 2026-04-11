from pathlib import Path
# ─────────────────────────────────────────────────────────────────────────────
# ADD THESE FUNCTIONS TO utils/data_loader.py
# Insert them near the bottom, before the final __all__ or any export block.
# These load the JSON files written by utils/pdf_extractor.py
# ─────────────────────────────────────────────────────────────────────────────

# At the top of data_loader.py, add this import if not already present:
# import json

def _load_json(filename: str) -> list[dict]:
    """Load a JSON file from the data/ directory. Returns empty list if missing."""
   path = Path(DATA_DIR) / filename
    if not path.exists():
        logger.warning("JSON file not found: %s — run pdf_extractor.py first", filename)
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load %s: %s", filename, e)
        return []


def load_umb_reports() -> pd.DataFrame:
    """Load extracted UMB trustee report data.
    
    Requires: data/umb_trustee_reports.json (written by pdf_extractor.py)
    
    Returns DataFrame with columns:
        report_date, dscr, dscr_covenant_min, dscr_in_compliance,
        debt_service_reserve_balance, debt_service_reserve_required,
        reserve_in_compliance, bonds_outstanding, debt_service_paid
    """
    records = _load_json("umb_trustee_reports.json")
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Coerce numeric columns
    numeric_cols = [
        "dscr", "dscr_covenant_min", "bonds_outstanding",
        "debt_service_paid", "debt_service_due",
        "debt_service_reserve_balance", "debt_service_reserve_required",
        "operations_reserve", "capital_reserve"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse dates
    for col in ["report_date", "period_start", "period_end"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "report_date" in df.columns:
        df = df.sort_values("report_date", ascending=False)

    return df


def load_bond_documents() -> pd.DataFrame:
    """Load extracted bond and legal document data.
    
    Requires: data/bond_documents.json (written by pdf_extractor.py)
    
    Returns DataFrame with key bond terms, covenants, and document metadata.
    """
    records = _load_json("bond_documents.json")
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    for col in ["document_date", "effective_date", "bond_maturity_date", "lease_expiry_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in ["bond_principal", "dscr_minimum"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_cscg_budget_submissions() -> pd.DataFrame:
    """Load extracted CSCG budget submission data.
    
    Requires: data/cscg_budget_submissions.json (written by pdf_extractor.py)
    
    Returns DataFrame with revenue, expense, and net income line items
    extracted from CSCG PDF budget documents.
    """
    records = _load_json("cscg_budget_submissions.json")
    if not records:
        return pd.DataFrame()

    # Flatten nested revenue/expense dicts
    flat_records = []
    for r in records:
        flat = {
            "_source_file": r.get("_source_file"),
            "_source_folder": r.get("_source_folder"),
            "_extracted_at": r.get("_extracted_at"),
            "document_type": r.get("document_type"),
            "period_start": r.get("period_start"),
            "period_end": r.get("period_end"),
            "submission_date": r.get("submission_date"),
            "is_budget_or_actual": r.get("is_budget_or_actual"),
            "extraction_confidence": r.get("extraction_confidence"),
        }
        # Flatten revenue
        rev = r.get("revenue") or {}
        for k, v in rev.items():
            flat[f"revenue_{k}"] = v
        # Flatten expenses
        exp = r.get("expenses") or {}
        for k, v in exp.items():
            flat[f"expense_{k}"] = v
        flat["net_income"] = r.get("net_income")
        flat_records.append(flat)

    df = pd.DataFrame(flat_records)

    for col in ["period_start", "period_end", "submission_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    numeric_cols = [c for c in df.columns if c.startswith("revenue_") or c.startswith("expense_") or c == "net_income"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_vendor_contracts() -> pd.DataFrame:
    """Load extracted vendor contract data.
    
    Requires: data/vendor_contracts.json (written by pdf_extractor.py)
    
    Returns DataFrame with contract terms, expiry dates, annual values,
    and any flagged red flags.
    """
    records = _load_json("vendor_contracts.json")
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    for col in ["document_date", "effective_date", "expiry_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "annual_value" in df.columns:
        df["annual_value"] = pd.to_numeric(df["annual_value"], errors="coerce")

    # Flag contracts expiring within 90 days
    if "expiry_date" in df.columns:
        today = pd.Timestamp.now()
        df["days_to_expiry"] = (df["expiry_date"] - today).dt.days
        df["expiry_alert"] = df["days_to_expiry"].apply(
            lambda d: "red" if pd.notna(d) and 0 <= d <= 30
            else ("yellow" if pd.notna(d) and 0 <= d <= 90 else "green")
        )

    return df


def load_board_minutes_extracted() -> pd.DataFrame:
    """Load extracted board meeting minutes data.
    
    Requires: data/board_minutes_extracted.json (written by pdf_extractor.py)
    
    Returns DataFrame with meeting dates, motions, action items, and key decisions.
    """
    records = _load_json("board_minutes_extracted.json")
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if "meeting_date" in df.columns:
        df["meeting_date"] = pd.to_datetime(df["meeting_date"], errors="coerce")
        df = df.sort_values("meeting_date", ascending=False)

    return df


def get_latest_dscr() -> dict:
    """Get the most recent DSCR reading from extracted UMB reports.
    
    Returns dict with keys: dscr, dscr_covenant_min, in_compliance, report_date.
    Returns None if no UMB data is available.
    
    Used by Bond & Debt page and DSRF Tracker.
    """
    df = load_umb_reports()
    if df.empty:
        return None

    latest = df.iloc[0]
    return {
        "dscr": float(latest.get("dscr") or 0),
        "dscr_covenant_min": float(latest.get("dscr_covenant_min") or 1.25),
        "in_compliance": bool(latest.get("dscr_in_compliance", True)),
        "report_date": str(latest.get("report_date", "Unknown")),
        "reserve_balance": float(latest.get("debt_service_reserve_balance") or 0),
        "reserve_required": float(latest.get("debt_service_reserve_required") or 0),
        "reserve_in_compliance": bool(latest.get("reserve_in_compliance", True)),
    }


def get_open_action_items() -> list[dict]:
    """Get all open board action items from extracted minutes.
    
    Returns list of dicts with: description, owner, due_date, meeting_date.
    Used by Board Actions page.
    """
    df = load_board_minutes_extracted()
    if df.empty or "action_items" not in df.columns:
        return []

    open_items = []
    for _, row in df.iterrows():
        items = row.get("action_items") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("status") != "complete":
                    open_items.append({
                        "description": item.get("description", ""),
                        "owner": item.get("owner", ""),
                        "due_date": item.get("due_date", ""),
                        "meeting_date": str(row.get("meeting_date", "")),
                        "status": item.get("status", "open"),
                    })

    return open_items


def get_expiring_contracts(days: int = 90) -> pd.DataFrame:
    """Get contracts expiring within N days.
    
    Used by Board Guide and Variance Alerts pages.
    """
    df = load_vendor_contracts()
    if df.empty or "days_to_expiry" not in df.columns:
        return pd.DataFrame()

    return df[df["days_to_expiry"].between(0, days)].sort_values("days_to_expiry")


def get_pdf_extraction_status() -> dict:
    """Get a summary of what's been extracted and when.
    
    Used by dashboard staleness indicators.
    """
    log_records = _load_json("pdf_extraction_log.json")
    if not log_records:
        return {"total": 0, "success": 0, "error": 0, "last_run": None}

    success = [r for r in log_records if r.get("status") == "success"]
    errors = [r for r in log_records if r.get("status") == "error"]
    timestamps = [r.get("extracted_at") for r in log_records if r.get("extracted_at")]

    return {
        "total": len(log_records),
        "success": len(success),
        "error": len(errors),
        "last_run": max(timestamps) if timestamps else None,
        "docs_by_type": {
            doc_type: len([r for r in success if r.get("doc_type") == doc_type])
            for doc_type in ["umb", "bond", "cscg_budget", "vendor_contract", "board_minutes"]
        }
    }
