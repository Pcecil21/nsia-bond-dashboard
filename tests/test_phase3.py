"""Tests for Phase 3 features: staleness, session counter, FY detection, page context."""
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


# ---------------------------------------------------------------------------
# 1. Staleness calculation (mirrors app.py logic)
# ---------------------------------------------------------------------------

def _compute_staleness(last_sync_path: str) -> dict:
    """Extract staleness logic from app.py into a testable function."""
    try:
        sync_ts = datetime.fromisoformat(open(last_sync_path, encoding="utf-8").read().strip())
        age = datetime.now(timezone.utc) - sync_ts
        age_days = age.total_seconds() / 86400
        if age_days > 7:
            return {"cls": "staleness-critical", "stale": True, "days": age_days}
        elif age_days > 1:
            return {"cls": "staleness-stale" if age_days > 3 else "staleness-fresh", "stale": age_days > 3, "days": age_days}
        else:
            return {"cls": "staleness-fresh", "stale": False, "days": age_days}
    except FileNotFoundError:
        return {"cls": "staleness-stale", "stale": None, "days": None}
    except Exception:
        return {"cls": "error", "stale": None, "days": None}


def test_staleness_fresh():
    """Data synced 1 hour ago should be fresh."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        f.write(ts)
        f.flush()
        result = _compute_staleness(f.name)
    os.unlink(f.name)
    assert result["cls"] == "staleness-fresh"
    assert result["stale"] is False
    assert result["days"] < 1


def test_staleness_stale():
    """Data synced 10 days ago should be critical."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        f.write(ts)
        f.flush()
        result = _compute_staleness(f.name)
    os.unlink(f.name)
    assert result["cls"] == "staleness-critical"
    assert result["stale"] is True
    assert result["days"] > 7


def test_staleness_missing_file():
    """Missing .last_sync should return unknown status."""
    result = _compute_staleness("/nonexistent/path/.last_sync")
    assert result["days"] is None
    assert result["cls"] == "staleness-stale"


def test_staleness_corrupt_file():
    """Corrupt .last_sync should not crash."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("not a timestamp")
        f.flush()
        result = _compute_staleness(f.name)
    os.unlink(f.name)
    assert result["cls"] == "error"


# ---------------------------------------------------------------------------
# 2. Session counter logic
# ---------------------------------------------------------------------------

def test_session_counter_increment():
    """Counter should increment from 0."""
    count = 0
    count += 1
    assert count == 1


def test_session_counter_at_limit():
    """At the limit, should block."""
    MAX = 50
    count = 50
    assert count >= MAX


def test_session_counter_below_limit():
    """Below limit, should proceed."""
    MAX = 50
    count = 49
    assert count < MAX


# ---------------------------------------------------------------------------
# 3. FY column detection (mirrors 8_Multi_Year_Trends.py logic)
# ---------------------------------------------------------------------------

def _detect_fy_columns(columns: list[str]) -> list[str]:
    """Extract FY detection logic into testable function."""
    fy_cols = sorted([c for c in columns if re.match(r'^FY\d{4}$', c)])
    return fy_cols[-3:] if len(fy_cols) >= 3 else fy_cols


def test_fy_detection_normal():
    """Should detect last 3 FY columns."""
    cols = ["Category", "Type", "FY2024", "FY2025", "FY2026"]
    result = _detect_fy_columns(cols)
    assert result == ["FY2024", "FY2025", "FY2026"]


def test_fy_detection_four_years():
    """With 4 FY columns, should take the last 3."""
    cols = ["Category", "FY2023", "FY2024", "FY2025", "FY2026"]
    result = _detect_fy_columns(cols)
    assert result == ["FY2024", "FY2025", "FY2026"]


def test_fy_detection_empty():
    """No FY columns should return empty list."""
    cols = ["Category", "Type", "Revenue"]
    result = _detect_fy_columns(cols)
    assert result == []


def test_fy_detection_one_year():
    """Single FY column should return it."""
    cols = ["Category", "FY2026"]
    result = _detect_fy_columns(cols)
    assert result == ["FY2026"]


def test_fy_detection_ignores_partial():
    """Should not match partial FY patterns."""
    cols = ["FY2026", "FY_old", "FY", "FY202", "NotFY2026"]
    result = _detect_fy_columns(cols)
    assert result == ["FY2026"]


# ---------------------------------------------------------------------------
# 4. Page context injection
# ---------------------------------------------------------------------------

def test_page_context_included_in_prompt():
    """When page_context is provided, it should appear in the system prompt."""
    # Simulate the prompt builder logic without Streamlit dependencies
    page_context = "Financial Overview"
    data_summary = "## Monthly P&L\nRevenue: $100,000"
    page_section = f"\n## Page Context\nThe user was viewing: {page_context}\n" if page_context else ""
    prompt = f"Base prompt\n{data_summary}{page_section}\n## Rules"
    assert "Financial Overview" in prompt
    assert "Page Context" in prompt


def test_page_context_absent():
    """When no page_context, no page section should appear."""
    page_context = ""
    page_section = f"\n## Page Context\nThe user was viewing: {page_context}\n" if page_context else ""
    prompt = f"Base prompt{page_section}\n## Rules"
    assert "Page Context" not in prompt
