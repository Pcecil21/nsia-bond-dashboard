"""Archive existing scraped CSV files before re-scraping.

Usage:
    python scripts/archive_data.py              # archive all scraped CSVs
    python scripts/archive_data.py wilmette      # archive only Wilmette
    python scripts/archive_data.py winnetka      # archive only Winnetka
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARCHIVE_DIR = DATA_DIR / "archive"

FILES = {
    "wilmette": "wilmette_weekend_nsia.csv",
    "winnetka": "winnetka_weekend_nsia.csv",
}


def archive(names: list[str] | None = None):
    ARCHIVE_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    targets = {k: v for k, v in FILES.items() if names is None or k in names}

    for label, filename in targets.items():
        src = DATA_DIR / filename
        if not src.exists():
            print(f"  skip  {filename} (not found)")
            continue
        stem = src.stem
        dest = ARCHIVE_DIR / f"{stem}_{stamp}.csv"
        shutil.copy2(src, dest)
        print(f"  saved {dest.name}")

    print("Done.")


if __name__ == "__main__":
    filter_names = None
    if len(sys.argv) > 1:
        filter_names = [a.lower() for a in sys.argv[1:]]
    archive(filter_names)
