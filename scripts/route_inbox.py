"""
NSIA Inbox Router

Scans data/Ingestion/Unsorted/ for files and moves them into the right bucket
(Statements, Bonds, Invoices, BoardPackets, Contracts) based on filename
heuristics. Anything we can't confidently classify stays in Unsorted/ for the
Inbox page to handle manually.

Usage:
    # Dry run — show what would move without moving anything
    python scripts/route_inbox.py --dry-run

    # Actually move the files
    python scripts/route_inbox.py

    # Point at a different root (testing)
    python scripts/route_inbox.py --ingestion-dir some/other/path

Wire into the scheduled sync:
    After GDrive-to-NSIA-Sync completes, run this script. The sync mirrors
    Drive -> data/Ingestion/Unsorted/, then this router classifies.

Confidence model:
    Each rule returns a (bucket, score) tuple. Highest-scoring bucket wins if
    score >= CONFIDENCE_THRESHOLD. Otherwise the file stays in Unsorted/ for
    human review on the Inbox page.

    Rules are intentionally filename-based (cheap, predictable, auditable).
    If filename rules aren't enough, add content inspection later — but
    start here because 90% of what Pete receives has a predictable filename
    from the sender.
"""

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INGESTION_DIR = PROJECT_ROOT / "data" / "Ingestion"
ROUTING_LOG = PROJECT_ROOT / "data" / "Ingestion" / "_router_log.jsonl"

# Rule confidence above this threshold = auto-route. Below = stay in Unsorted.
CONFIDENCE_THRESHOLD = 2

BUCKETS = ["Statements", "Bonds", "Invoices", "BoardPackets", "Contracts"]

# Each rule: (bucket_name, list of (regex_pattern, score_weight))
# Score weights: strong signal = 3, medium = 2, weak = 1.
# A filename that matches multiple strong signals in one bucket is high-confidence.
CATEGORY_RULES = {
    "Statements": [
        (r"\bstatement\b", 3),
        (r"\bbank\b", 2),
        (r"\bmonthly\b", 1),
        (r"first[_\s-]?bank", 2),
        (r"northshore", 2),
        (r"\baccount\b.*\bactivity\b", 2),
    ],
    "Bonds": [
        (r"\btrustee\b", 3),
        (r"\bumb\b", 3),
        (r"\bdsrf\b", 3),
        (r"\bbond\b", 2),
        (r"\bdebt[_\s-]?service\b", 2),
        (r"series[_\s-]?20\d{2}", 2),
    ],
    "Invoices": [
        (r"\binvoice\b", 3),
        (r"\bbill\b", 2),
        (r"\bremittance\b", 2),
        (r"\bamount[_\s-]?due\b", 2),
        (r"inv[_\s-]?\d{3,}", 2),  # inv-12345, inv_987
    ],
    "BoardPackets": [
        (r"\bboard[_\s-]?packet\b", 3),
        (r"\bboard[_\s-]?meeting\b", 3),
        (r"\bagenda\b", 2),
        (r"\bminutes\b", 2),
        (r"\bresolution\b", 2),
        (r"board[_\s-]?memo", 2),
    ],
    "Contracts": [
        (r"\bcontract\b", 3),
        (r"\bagreement\b", 2),
        (r"\bmsa\b", 2),
        (r"\bsow\b", 2),
        (r"\blease\b", 2),
        (r"executed", 1),
        (r"amendment", 2),
    ],
}


def score_filename(filename: str) -> dict[str, int]:
    """Return a {bucket: total_score} dict for a given filename.

    Normalize before matching:
      - lowercase (rules are lowercase so \\b works predictably)
      - swap underscores / hyphens for spaces (Python's \\b treats `_` as a
        word char, so `_invoice-` has no word boundary — normalization fixes
        that across all rules instead of rewriting every pattern).
    """
    name = filename.lower()
    name = re.sub(r"[_\-]+", " ", name)
    scores = {bucket: 0 for bucket in BUCKETS}
    for bucket, rules in CATEGORY_RULES.items():
        for pattern, weight in rules:
            if re.search(pattern, name):
                scores[bucket] += weight
    return scores


def classify(filename: str) -> tuple[Optional[str], dict[str, int]]:
    """Pick the best bucket for a filename, if any.

    Returns (bucket_name_or_None, full_score_breakdown).
    bucket_name is None when no bucket hits CONFIDENCE_THRESHOLD.
    """
    scores = score_filename(filename)
    if not scores:
        return None, scores

    top_bucket = max(scores, key=scores.get)
    top_score = scores[top_bucket]

    if top_score < CONFIDENCE_THRESHOLD:
        return None, scores

    # Tie-break: if two buckets share the top score, stay in Unsorted.
    # Better to ask Pete than guess wrong.
    tied = [b for b, s in scores.items() if s == top_score]
    if len(tied) > 1:
        return None, scores

    return top_bucket, scores


def append_log(entry: dict) -> None:
    """Append one JSON line to the routing log. Safe for concurrent runs —
    each line is self-contained so partial writes don't corrupt history."""
    ROUTING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ROUTING_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def route_one(file_path: Path, ingestion_dir: Path, dry_run: bool) -> dict:
    """Classify a single file and move it if confident. Returns a log entry."""
    bucket, scores = classify(file_path.name)
    timestamp = datetime.now(timezone.utc).isoformat()

    entry = {
        "ts": timestamp,
        "file": file_path.name,
        "scores": scores,
        "decision": bucket or "unsorted",
        "dry_run": dry_run,
    }

    if bucket is None:
        logging.info("KEEP IN UNSORTED: %s (scores=%s)", file_path.name, scores)
        return entry

    target_dir = ingestion_dir / bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file_path.name

    # Don't clobber — if the same filename already exists, append a short
    # suffix so we keep both copies and Pete can reconcile.
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        short_ts = datetime.now().strftime("%H%M%S")
        target_path = target_dir / f"{stem}__{short_ts}{suffix}"
        entry["renamed_to"] = target_path.name

    if dry_run:
        logging.info("WOULD MOVE: %s -> %s", file_path.name, bucket)
    else:
        shutil.move(str(file_path), str(target_path))
        logging.info("MOVED: %s -> %s", file_path.name, bucket)

    entry["target"] = str(target_path.relative_to(ingestion_dir))
    return entry


def route_inbox(ingestion_dir: Path, dry_run: bool = False) -> list[dict]:
    """Scan Unsorted/ and route every file. Returns list of log entries."""
    unsorted_dir = ingestion_dir / "Unsorted"
    if not unsorted_dir.exists():
        logging.warning("Unsorted directory does not exist: %s", unsorted_dir)
        return []

    # Only loop files, not subdirs. Ignore dotfiles (.DS_Store, .gitkeep, etc).
    files = [p for p in unsorted_dir.iterdir() if p.is_file() and not p.name.startswith(".")]

    if not files:
        logging.info("Unsorted is empty — nothing to do.")
        return []

    logging.info("Found %d file(s) in Unsorted/", len(files))
    results = []
    for f in files:
        try:
            entry = route_one(f, ingestion_dir, dry_run)
            results.append(entry)
            if not dry_run:
                append_log(entry)
        except Exception as err:
            logging.error("Failed to route %s: %s", f.name, err)
            results.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "file": f.name,
                "error": str(err),
                "dry_run": dry_run,
            })

    return results


def parse_args():
    parser = argparse.ArgumentParser(description="Route NSIA ingestion inbox.")
    parser.add_argument(
        "--ingestion-dir",
        default=str(DEFAULT_INGESTION_DIR),
        help="Root ingestion directory (contains Unsorted/ and bucket subfolders)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would move without moving anything",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ingestion_dir = Path(args.ingestion_dir).resolve()
    # Create the tree on first run so the router is safe to schedule
    # before the Gmail-side setup is complete.
    for sub in ["Unsorted"] + BUCKETS + ["_Archive"]:
        (ingestion_dir / sub).mkdir(parents=True, exist_ok=True)

    results = route_inbox(ingestion_dir, dry_run=args.dry_run)

    # Summary line for scheduled-task logs
    moved = sum(1 for r in results if r.get("decision") not in ("unsorted", None) and not r.get("error"))
    kept = sum(1 for r in results if r.get("decision") == "unsorted")
    errors = sum(1 for r in results if r.get("error"))
    logging.info("Summary: %d moved, %d kept in Unsorted, %d errors", moved, kept, errors)


if __name__ == "__main__":
    main()
