"""
Page 20: Inbox

Central view for ingested emails / attachments. Shows:
  - Recent arrivals across all buckets (last 14 days)
  - Unsorted queue — files the router wasn't confident about, with a
    one-click reclassify dropdown
  - Manual drop zone for files Pete wants to file without going through Gmail

Backed by:
  - data/Ingestion/Unsorted/, Statements/, Bonds/, Invoices/, BoardPackets/, Contracts/
  - scripts/route_inbox.py for auto-routing
  - data/Ingestion/_router_log.jsonl for the audit trail

Ingestion flow docs: docs/gmail-ingestion-setup.md
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

# Make utils/ importable (same pattern as other pages)
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.auth import require_auth
from utils.theme import FONT_COLOR, inject_css

st.set_page_config(page_title="Inbox | NSIA", layout="wide", page_icon=":inbox_tray:")

require_auth()
inject_css()

# ── Constants ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INGESTION_DIR = PROJECT_ROOT / "data" / "Ingestion"
ROUTER_LOG = INGESTION_DIR / "_router_log.jsonl"
ROUTER_SCRIPT = PROJECT_ROOT / "scripts" / "route_inbox.py"

BUCKETS = ["Statements", "Bonds", "Invoices", "BoardPackets", "Contracts"]
RECENT_DAYS = 14


# ── Helpers ──────────────────────────────────────────────────────────────
def ensure_dirs() -> None:
    """Create the ingestion folders if this is the first run. Harmless to re-run."""
    for bucket in ["Unsorted"] + BUCKETS + ["_Archive"]:
        (INGESTION_DIR / bucket).mkdir(parents=True, exist_ok=True)


def list_files(bucket: str) -> list[Path]:
    """List files in a bucket, newest first. Skips dotfiles and subdirs."""
    d = INGESTION_DIR / bucket
    if not d.exists():
        return []
    files = [p for p in d.iterdir() if p.is_file() and not p.name.startswith(".")]
    # Sort by modification time, newest first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def recent_across_buckets(days: int) -> list[tuple[str, Path]]:
    """Return (bucket, path) pairs modified within the last N days, newest first."""
    cutoff = datetime.now().timestamp() - (days * 86400)
    hits: list[tuple[str, Path]] = []
    for bucket in BUCKETS:
        for f in list_files(bucket):
            if f.stat().st_mtime >= cutoff:
                hits.append((bucket, f))
    hits.sort(key=lambda t: t[1].stat().st_mtime, reverse=True)
    return hits


def read_router_log(max_entries: int = 50) -> list[dict]:
    """Load the last N router decisions. Tolerant to corrupt lines —
    a bad line shouldn't take out the whole page."""
    if not ROUTER_LOG.exists():
        return []
    entries: list[dict] = []
    with ROUTER_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-max_entries:][::-1]  # newest first


def run_router() -> tuple[bool, str]:
    """Fire scripts/route_inbox.py and capture its output.
    Returns (ok, combined_stdout_stderr)."""
    try:
        result = subprocess.run(
            [sys.executable, str(ROUTER_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "Router timed out after 60s."
    except Exception as err:
        return False, f"Router failed to launch: {err}"


def move_file(src: Path, target_bucket: str) -> Path:
    """Move a file to a new bucket. Appends a timestamp to the name if the
    target already has a file with that name (don't clobber)."""
    target_dir = INGESTION_DIR / target_bucket
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / src.name
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        stamp = datetime.now().strftime("%H%M%S")
        target_path = target_dir / f"{stem}__{stamp}{suffix}"
    shutil.move(str(src), str(target_path))
    return target_path


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def fmt_mtime(ts: float) -> str:
    """Format file mtime as 'YYYY-MM-DD HH:MM' in local time."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


# ── Page ─────────────────────────────────────────────────────────────────
ensure_dirs()

st.title("Inbox")
st.markdown(
    "One forwarding address → attachments land here, get auto-filed, and anything "
    "ambiguous waits in **Unsorted** for one-click review. "
    "Setup: `docs/gmail-ingestion-setup.md`"
)

# Top-line stats
unsorted_files = list_files("Unsorted")
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Unsorted", len(unsorted_files))
col_b.metric("Recent (14d)", len(recent_across_buckets(RECENT_DAYS)))
total = sum(len(list_files(b)) for b in BUCKETS)
col_c.metric("Filed total", total)
log_count = sum(1 for _ in ROUTER_LOG.open(encoding="utf-8")) if ROUTER_LOG.exists() else 0
col_d.metric("Router decisions", log_count)

st.markdown("---")

# ── Unsorted queue ───────────────────────────────────────────────────────
st.subheader(f"Unsorted — needs your review ({len(unsorted_files)})")

action_col, _ = st.columns([1, 5])
with action_col:
    if st.button("Run auto-router", help="Classify Unsorted files using filename rules"):
        with st.spinner("Running router..."):
            ok, output = run_router()
        if ok:
            st.success("Router finished.")
        else:
            st.error("Router hit an error — see details below.")
        with st.expander("Router output"):
            st.code(output or "(no output)")
        st.rerun()

if not unsorted_files:
    st.info("Nothing waiting. Either the router classified everything or nothing has arrived yet.")
else:
    for f in unsorted_files:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            c1.markdown(f"**{f.name}**")
            c1.caption(f"{fmt_bytes(f.stat().st_size)} • arrived {fmt_mtime(f.stat().st_mtime)}")

            chosen = c2.selectbox(
                "Move to",
                ["— pick —"] + BUCKETS,
                key=f"move_{f.name}",
                label_visibility="collapsed",
            )

            if c3.button("File it", key=f"file_{f.name}", disabled=(chosen == "— pick —")):
                new_path = move_file(f, chosen)
                st.toast(f"Filed to {chosen}: {new_path.name}")
                st.rerun()

            if c4.button("Delete", key=f"del_{f.name}", help="Permanently delete — use for spam / non-NSIA email"):
                f.unlink()
                st.toast(f"Deleted {f.name}")
                st.rerun()

st.markdown("---")

# ── Manual drop zone ─────────────────────────────────────────────────────
st.subheader("Manual drop")
st.caption("Skip email — drop a file here and pick where it goes. Useful for one-offs.")

drop_col1, drop_col2 = st.columns([3, 1])
uploaded = drop_col1.file_uploader(
    "File",
    type=None,
    accept_multiple_files=False,
    label_visibility="collapsed",
)
target = drop_col2.selectbox("Bucket", BUCKETS + ["Unsorted"], key="manual_target")

if uploaded is not None:
    if st.button("Save to bucket"):
        target_dir = INGESTION_DIR / target
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / uploaded.name
        if target_path.exists():
            stem, suffix = target_path.stem, target_path.suffix
            stamp = datetime.now().strftime("%H%M%S")
            target_path = target_dir / f"{stem}__{stamp}{suffix}"
        target_path.write_bytes(uploaded.getbuffer())
        st.success(f"Saved to {target}/{target_path.name}")
        st.rerun()

st.markdown("---")

# ── Recent arrivals across buckets ───────────────────────────────────────
st.subheader(f"Recent arrivals (last {RECENT_DAYS} days)")
recent = recent_across_buckets(RECENT_DAYS)

if not recent:
    st.caption("No files filed in the last two weeks.")
else:
    # Simple table layout — bucket, filename, size, when
    for bucket, path in recent[:40]:  # cap the page length
        c1, c2, c3, c4 = st.columns([1.5, 5, 1, 2])
        c1.markdown(f"`{bucket}`")
        c2.markdown(path.name)
        c3.caption(fmt_bytes(path.stat().st_size))
        c4.caption(fmt_mtime(path.stat().st_mtime))

# ── Router audit log ─────────────────────────────────────────────────────
with st.expander("Router audit log (last 50 decisions)"):
    entries = read_router_log(50)
    if not entries:
        st.caption("No router runs logged yet.")
    else:
        for e in entries:
            ts = e.get("ts", "")[:19].replace("T", " ")
            decision = e.get("decision", "?")
            file_ = e.get("file", "?")
            scores = e.get("scores", {})
            top = ", ".join(f"{k}:{v}" for k, v in sorted(scores.items(), key=lambda x: -x[1]) if v > 0) or "no matches"
            line = f"{ts} — **{file_}** → `{decision}`  _({top})_"
            if e.get("error"):
                line = f"{ts} — **{file_}** → ERROR: {e['error']}"
            st.markdown(line)
