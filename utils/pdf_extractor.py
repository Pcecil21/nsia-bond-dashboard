"""
NSIA PDF Extractor
==================
Reads locally-synced PDF documents from the project's document folders,
extracts structured data via Claude API, and writes results to data/ as
CSV/JSON files that data_loader.py can consume.

PyMuPDF is already in requirements.txt. anthropic is already in requirements.txt.
No new dependencies needed.

Usage (from project root):
    python utils/pdf_extractor.py --type umb
    python utils/pdf_extractor.py --type bond
    python utils/pdf_extractor.py --all
    python utils/pdf_extractor.py --file "NSIA Bond Documents/indenture.pdf"

Output files written to data/:
    umb_trustee_reports.json      → UMB report history, DSCR, reserve balances
    bond_covenants.json           → Extracted covenant terms from bond documents
    cscg_budget_submissions.json  → Budget submissions from CSCG PDFs
    extraction_log.json           → What was processed and when
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Map document folder names → extractor type
# These match the actual folder names in the project root
FOLDER_TYPE_MAP = {
    "Bond Documents": "bond",
    "Financials and Budgets": "cscg_budget",
    "Budgets": "cscg_budget",
    "Bank Statements": "bank",
    "Board Meetings": "board_minutes",
    "Club Sports Consulting Group Contract": "vendor_contract",
    "Chiller contract": "vendor_contract",
    "Energy contracts": "vendor_contract",
    "Insurance contract": "vendor_contract",
    "Ground Leases": "bond",  # treat ground lease as bond doc
    "Operating Agreement": "bond",
    "Audit Docs": "cscg_budget",
    "NSIA Corporate Records": "bond",  # Articles, 501C3 letter, bylaws, EIN — legal formation docs
    "Ice utilization": "ice_util",
    "2024 Chiller Contract and related matters": "vendor_contract",
}

MAX_TEXT_CHARS = 160_000


# ─────────────────────────────────────────────
# PDF TEXT EXTRACTION (PyMuPDF)
# ─────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using PyMuPDF."""
    text_parts = []
    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                text_parts.append(f"[Page {i+1}]\n{text}")
    full_text = "\n\n".join(text_parts)
    if len(full_text) > MAX_TEXT_CHARS:
        log.warning("Truncating %s from %d to %d chars", pdf_path.name, len(full_text), MAX_TEXT_CHARS)
        full_text = full_text[:MAX_TEXT_CHARS] + "\n\n[TRUNCATED]"
    return full_text


# ─────────────────────────────────────────────
# EXTRACTION PROMPTS
# ─────────────────────────────────────────────

PROMPTS = {

    "umb": """
You are extracting structured data from a UMB Bank trustee report for North Shore Ice Arena (NSIA).

NSIA context:
- Bond: $8.49M Illinois Finance Authority Sports Facility Revenue Bonds (2008)
- Bond trustee: UMB Bank
- Key covenant: DSCR minimum (extract exact value from document)
- Fiscal year: July 1 – June 30
- Tax status: 501(c)(3)

Extract all available fields. Set missing fields to null. Do not estimate.

Return ONLY valid JSON:
{
  "report_date": "YYYY-MM-DD or null",
  "period_start": "YYYY-MM-DD or null",
  "period_end": "YYYY-MM-DD or null",
  "bonds_outstanding": 0.00,
  "debt_service_paid": 0.00,
  "debt_service_due": 0.00,
  "dscr": 0.0000,
  "dscr_covenant_min": 0.0000,
  "dscr_in_compliance": true,
  "debt_service_reserve_balance": 0.00,
  "debt_service_reserve_required": 0.00,
  "reserve_in_compliance": true,
  "operations_reserve": 0.00,
  "capital_reserve": 0.00,
  "covenant_notes": "any covenant language or null",
  "extraction_confidence": "high | medium | low",
  "extraction_notes": "anything unusual or missing"
}
Return ONLY the JSON. No preamble, no markdown fences.
""",

    "bond": """
You are extracting key terms from a legal document related to North Shore Ice Arena (NSIA).

NSIA context:
- Bond: $8.49M Illinois Finance Authority Sports Facility Revenue Bonds (2008)
- Ground lease: Divine Word / Society of the Divine Word (Techny property)
- Trustee: UMB Bank

Extract all key governance terms. Set missing fields to null.

Return ONLY valid JSON:
{
  "document_type": "indenture | ground_lease | operating_agreement | amendment | other",
  "document_date": "YYYY-MM-DD or null",
  "effective_date": "YYYY-MM-DD or null",
  "parties": ["Party Name — Role"],
  "bond_principal": 0.00,
  "bond_maturity_date": "YYYY-MM-DD or null",
  "dscr_minimum": 0.0000,
  "lease_expiry_date": "YYYY-MM-DD or null",
  "reserve_requirements": {"fund name": "amount or formula"},
  "event_of_default_triggers": ["each trigger as stated"],
  "reporting_requirements": ["each requirement"],
  "board_vote_thresholds": ["any items requiring board vote"],
  "key_dates": {"event": "YYYY-MM-DD"},
  "key_clauses": {"section": "2-sentence summary"},
  "red_flags": ["anything unusual or one-sided"],
  "extraction_confidence": "high | medium | low",
  "extraction_notes": "anything unusual or missing"
}
Return ONLY the JSON. No preamble, no markdown fences.
""",

    "cscg_budget": """
You are extracting budget and financial data from a CSCG (Club Sports Consulting Group) document
for North Shore Ice Arena (NSIA). NSIA fiscal year is July 1 – June 30.

CSCG is the operations manager. The board uses these figures for budget vs actual variance analysis.
Extract every line item with precision — discrepancies will be investigated.

Return ONLY valid JSON:
{
  "document_type": "annual_budget | quarterly_report | pnl | audit | other",
  "period_start": "YYYY-MM-DD or null",
  "period_end": "YYYY-MM-DD or null",
  "submission_date": "YYYY-MM-DD or null",
  "revenue": {
    "ice_rental": 0.00,
    "pro_shop": 0.00,
    "food_beverage": 0.00,
    "lessons_programs": 0.00,
    "skating_admission": 0.00,
    "other": 0.00,
    "total": 0.00
  },
  "expenses": {
    "payroll": 0.00,
    "management_fee": 0.00,
    "utilities": 0.00,
    "maintenance": 0.00,
    "insurance": 0.00,
    "supplies": 0.00,
    "marketing": 0.00,
    "debt_service": 0.00,
    "other": 0.00,
    "total": 0.00
  },
  "net_income": 0.00,
  "line_items_verbatim": {"line label as written": 0.00},
  "is_budget_or_actual": "budget | actual | both | unknown",
  "extraction_confidence": "high | medium | low",
  "extraction_notes": "completeness assessment — note if this appears partial"
}
Return ONLY the JSON. No preamble, no markdown fences.
""",

    "vendor_contract": """
You are extracting key terms from a vendor contract for North Shore Ice Arena (NSIA).

Focus on: commercial terms, obligations, termination rights, automatic renewals, and any
clauses that require board notification or approval per the NSIA operating agreement.

Return ONLY valid JSON:
{
  "document_type": "management_agreement | service_contract | equipment_lease | insurance | other",
  "vendor_name": "primary vendor",
  "document_date": "YYYY-MM-DD or null",
  "effective_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "auto_renewal": true,
  "renewal_notice_days": 0,
  "annual_value": 0.00,
  "payment_terms": "description",
  "scope_summary": "2-sentence plain English scope",
  "termination_for_cause": "summary or null",
  "termination_for_convenience": "summary or null",
  "performance_obligations": ["each key vendor obligation"],
  "reporting_obligations": ["what vendor must report and when"],
  "board_approval_required": ["items requiring board action"],
  "red_flags": ["unusual, one-sided, or risky clauses"],
  "extraction_confidence": "high | medium | low",
  "extraction_notes": "missing pages, unclear terms, sections needing legal review"
}
Return ONLY the JSON. No preamble, no markdown fences.
""",

    "board_minutes": """
You are extracting governance data from NSIA board meeting minutes.

NSIA context: Six-member board (3 WHA, 3 WKC), fiscal year July 1 – June 30,
managed by CSCG under Don Lapato. Board president is Pete Cecil.

Return ONLY valid JSON:
{
  "meeting_date": "YYYY-MM-DD or null",
  "meeting_type": "regular | special | emergency | unknown",
  "quorum_present": true,
  "attendees": ["name"],
  "absent": ["name"],
  "motions": [
    {
      "motion_text": "full text",
      "moved_by": "name",
      "seconded_by": "name",
      "result": "passed | failed | tabled | withdrawn",
      "vote": "X-Y-Z (yes-no-abstain)"
    }
  ],
  "action_items": [
    {
      "description": "what needs done",
      "owner": "who",
      "due_date": "YYYY-MM-DD or next meeting or null",
      "status": "open | complete"
    }
  ],
  "key_decisions": ["plain English summary"],
  "financial_items": ["any financial matter discussed"],
  "cscg_items": ["anything re CSCG performance or disputes"],
  "legal_items": ["legal matters, demand letters, counsel"],
  "open_issues": ["unresolved items"],
  "extraction_confidence": "high | medium | low",
  "extraction_notes": "unusual items or formatting issues"
}
Return ONLY the JSON. No preamble, no markdown fences.
""",

}


# ─────────────────────────────────────────────
# CLAUDE EXTRACTION
# ─────────────────────────────────────────────

def extract_with_claude(client: anthropic.Anthropic, text: str, doc_type: str, file_name: str) -> dict:
    prompt = PROMPTS.get(doc_type)
    if not prompt:
        raise ValueError(f"No prompt for doc_type: {doc_type}")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\nFILE: {file_name}\n\nDOCUMENT:\n{text}"
        }]
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("JSON parse error for %s: %s", file_name, e)
        log.error("Raw: %s", raw[:300])
        return {
            "extraction_confidence": "low",
            "extraction_notes": f"JSON parse failed: {e}. Raw: {raw[:200]}",
            "parse_error": True
        }


# ─────────────────────────────────────────────
# OUTPUT WRITERS
# ─────────────────────────────────────────────

def load_output(output_file: Path) -> list:
    if output_file.exists():
        try:
            return json.loads(output_file.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_output(output_file: Path, records: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    output_file.write_text(
        json.dumps(records, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8"
    )
    log.info("Saved %d records to %s", len(records), output_file)


OUTPUT_FILES = {
    "umb": DATA_DIR / "umb_trustee_reports.json",
    "bond": DATA_DIR / "bond_documents.json",
    "cscg_budget": DATA_DIR / "cscg_budget_submissions.json",
    "vendor_contract": DATA_DIR / "vendor_contracts.json",
    "board_minutes": DATA_DIR / "board_minutes_extracted.json",
}

EXTRACTION_LOG = DATA_DIR / "pdf_extraction_log.json"


def log_extraction(file_path: Path, doc_type: str, status: str, error: str = None) -> None:
    log_records = load_output(EXTRACTION_LOG)
    log_records.append({
        "file": str(file_path.name),
        "folder": str(file_path.parent.name),
        "doc_type": doc_type,
        "status": status,
        "error": error,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    })
    save_output(EXTRACTION_LOG, log_records)


# ─────────────────────────────────────────────
# ALREADY PROCESSED CHECK
# ─────────────────────────────────────────────

def already_processed(file_path: Path) -> bool:
    """Check if this file has already been successfully extracted."""
    log_records = load_output(EXTRACTION_LOG)
    return any(
        r.get("file") == file_path.name and r.get("status") == "success"
        for r in log_records
    )


# ─────────────────────────────────────────────
# MAIN EXTRACTION PIPELINE
# ─────────────────────────────────────────────

def process_file(client: anthropic.Anthropic, pdf_path: Path, doc_type: str, force: bool = False) -> bool:
    """Extract structured data from a single PDF and append to the output JSON."""
    if not force and already_processed(pdf_path):
        log.info("Skipping (already processed): %s", pdf_path.name)
        return True

    log.info("Processing: %s [%s]", pdf_path.name, doc_type)

    try:
        text = extract_pdf_text(pdf_path)
        if not text.strip():
            log.warning("No text extracted from %s — may be scanned/image PDF", pdf_path.name)
            log_extraction(pdf_path, doc_type, "skipped", "No text — likely scanned PDF")
            return False

        log.info("  Extracted %d chars from %s", len(text), pdf_path.name)

        data = extract_with_claude(client, text, doc_type, pdf_path.name)
        data["_source_file"] = pdf_path.name
        data["_source_folder"] = pdf_path.parent.name
        data["_extracted_at"] = datetime.now(timezone.utc).isoformat()

        output_file = OUTPUT_FILES.get(doc_type)
        if output_file:
            records = load_output(output_file)
            # Avoid exact duplicate file entries
            records = [r for r in records if r.get("_source_file") != pdf_path.name]
            records.append(data)
            save_output(output_file, records)

        log_extraction(pdf_path, doc_type, "success")
        log.info("  Done. Confidence: %s", data.get("extraction_confidence", "unknown"))
        return True

    except Exception as e:
        log.error("  ERROR: %s", e)
        log_extraction(pdf_path, doc_type, "error", str(e))
        return False


def detect_type(folder_name: str, file_name: str) -> str | None:
    for folder_pattern, doc_type in FOLDER_TYPE_MAP.items():
        if folder_pattern.lower() in folder_name.lower():
            return doc_type
    return None


def run_extraction(
    doc_type_filter: str = None,
    specific_file: str = None,
    force: bool = False,
    dry_run: bool = False
):
    """Main extraction runner."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    if specific_file:
        pdf_path = PROJECT_ROOT / specific_file
        if not pdf_path.exists():
            log.error("File not found: %s", pdf_path)
            return
        doc_type = doc_type_filter or detect_type(pdf_path.parent.name, pdf_path.name)
        if not doc_type:
            log.error("Cannot detect doc type for %s — use --type", specific_file)
            return
        if dry_run:
            log.info("[DRY RUN] Would process: %s as %s", pdf_path.name, doc_type)
            return
        process_file(client, pdf_path, doc_type, force=force)
        return

    # Walk all document folders in project root
    total = 0
    success = 0
    skipped = 0

    for folder_name, doc_type in FOLDER_TYPE_MAP.items():
        if doc_type_filter and doc_type != doc_type_filter:
            continue

        folder_path = PROJECT_ROOT / folder_name
        if not folder_path.exists():
            continue

        pdfs = list(folder_path.rglob("*.pdf")) + list(folder_path.rglob("*.PDF"))
        if not pdfs:
            continue

        log.info("Folder: %s (%d PDFs)", folder_name, len(pdfs))

        for pdf_path in sorted(pdfs):
            total += 1
            if dry_run:
                log.info("  [DRY RUN] %s → %s", pdf_path.name, doc_type)
                continue
            if not force and already_processed(pdf_path):
                skipped += 1
                continue
            ok = process_file(client, pdf_path, doc_type, force=force)
            if ok:
                success += 1

    if not dry_run:
        log.info("Done. %d processed, %d succeeded, %d skipped (already done)", total, success, skipped)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="NSIA PDF Extractor")
    parser.add_argument("--type", help="Filter: umb | bond | cscg_budget | vendor_contract | board_minutes")
    parser.add_argument("--all", action="store_true", help="Process all document types")
    parser.add_argument("--file", help="Process a single file (relative path from project root)")
    parser.add_argument("--force", action="store_true", help="Re-process already-extracted files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without calling Claude")
    args = parser.parse_args()

    if args.all or args.type or args.file:
        run_extraction(
            doc_type_filter=args.type,
            specific_file=args.file,
            force=args.force,
            dry_run=args.dry_run,
        )
    else:
        parser.print_help()
