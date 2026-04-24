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
import os
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

# pdf_extractor is optional at import — it pulls anthropic + PyMuPDF.
# If those aren't available (fresh clone, no API key), the Archive flow
# still works, just without the extraction step.
try:
    from utils import pdf_extractor
    PDF_EXTRACTOR_AVAILABLE = True
except Exception as _e:
    PDF_EXTRACTOR_AVAILABLE = False
    _EXTRACTOR_IMPORT_ERROR = str(_e)

# filename_suggester is also optional — falls back to light regex cleanup
# if anthropic SDK isn't installed or the API key is missing.
try:
    from utils import filename_suggester
    RENAME_AVAILABLE = True
except Exception:
    RENAME_AVAILABLE = False

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

# Permanent NSIA folders (the real Drive mirror dirs under data/).
# Keys from pdf_extractor.FOLDER_TYPE_MAP have an extraction pipeline;
# others file without extracting. We show the extraction-capable ones
# first in the dropdown so Pete defaults to the brain-aware destinations.
EXTRACTION_TARGETS = (
    list(pdf_extractor.FOLDER_TYPE_MAP.keys()) if PDF_EXTRACTOR_AVAILABLE else []
)

# A few common Drive folders that don't (yet) have an extraction type but
# Pete may still want to archive to. Add more here as needed.
ARCHIVE_ONLY_TARGETS = [
    "Capital Improvements",
    "Invoices and Bills",
    "Ice resurfacer Quotes",
    "Club Sports Payroll issue",
    "Restaurant",
    "Website",
    "Scoreboard Contract",
    "Current Ice contracts",
]


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


def append_log(entry: dict) -> None:
    """Write one JSON-lines row to the router audit log. Mirrors the writer
    in scripts/route_inbox.py so we have a single source of truth for what's
    in Ingestion history — router runs AND manual archive actions end up here."""
    ROUTER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ROUTER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


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


def archive_to_permanent(src: Path, dest_folder: str) -> Path:
    """Move file from Ingestion into the real NSIA Drive-mirror folder under data/.
    Same no-clobber semantics as move_file."""
    target_dir = PROJECT_ROOT / "data" / dest_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / src.name
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        stamp = datetime.now().strftime("%H%M%S")
        target_path = target_dir / f"{stem}__{stamp}{suffix}"
    shutil.move(str(src), str(target_path))
    return target_path


def try_extract(archived_path: Path, dest_folder: str) -> tuple[str, str]:
    """Try to run pdf_extractor on a freshly-archived file.

    Returns (status, detail) where status is one of:
      "extracted" — brain updated via JSON output
      "skipped_not_pdf" — file isn't a PDF, nothing to extract
      "skipped_no_mapping" — folder has no extraction type registered
      "skipped_no_api_key" — ANTHROPIC_API_KEY not set
      "skipped_no_extractor" — pdf_extractor module unavailable
      "error" — extractor crashed, file is still archived (detail has reason)
    """
    if not PDF_EXTRACTOR_AVAILABLE:
        return "skipped_no_extractor", _EXTRACTOR_IMPORT_ERROR

    if archived_path.suffix.lower() != ".pdf":
        return "skipped_not_pdf", f"{archived_path.suffix} — extractor only handles PDFs"

    doc_type = pdf_extractor.detect_type(dest_folder, archived_path.name)
    if not doc_type:
        return "skipped_no_mapping", f"No extraction type registered for '{dest_folder}'"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Also check Streamlit secrets — pdf_extractor reads env var only,
        # so we fall back to promoting secrets into the env.
        try:
            secret_key = st.secrets.get("anthropic", {}).get("api_key")
            if secret_key:
                os.environ["ANTHROPIC_API_KEY"] = secret_key
                api_key = secret_key
        except Exception:
            pass

    if not api_key:
        return "skipped_no_api_key", "Set ANTHROPIC_API_KEY env var or add [anthropic]api_key to st.secrets"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        ok = pdf_extractor.process_file(client, archived_path, doc_type, force=False)
        if ok:
            return "extracted", f"Updated {doc_type} JSON"
        return "error", "Extraction returned False — check extractor logs"
    except Exception as err:
        return "error", str(err)


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

# Signature-image pattern: email clients auto-name these "image001.png" etc.
# Real photos come through with meaningful names (IMG_1234.jpg, repair_photo.png).
# 50KB threshold comfortably clears logos while sparing even low-res real photos.
import re as _re_img
SIGNATURE_IMAGE_RE = _re_img.compile(r"^image\d+\.(png|jpe?g|gif|bmp)$", _re_img.IGNORECASE)
SIGNATURE_IMAGE_SIZE_MAX = 50 * 1024  # 50 KB


def is_signature_image(path: Path) -> bool:
    """True if file looks like an auto-generated email signature logo."""
    if not SIGNATURE_IMAGE_RE.match(path.name):
        return False
    try:
        return path.stat().st_size <= SIGNATURE_IMAGE_SIZE_MAX
    except OSError:
        return False


# Count files where AI has already proposed a folder (from session state).
# Used by the "Archive all AI-proposed" button below — only ever triggers on
# files where Claude picked something, so the action can't invent a folder.
ai_ready_files = [
    p for p in unsorted_files
    if st.session_state.get(f"ai_folder_{p.name}")
]

a_col1, a_col2, a_col3, a_col4, _ = st.columns([1, 1.5, 1.4, 1.5, 0.6])
with a_col1:
    if st.button("Run auto-router", help="Classify Unsorted files using filename rules (no AI)"):
        with st.spinner("Running router..."):
            ok, output = run_router()
        if ok:
            st.success("Router finished.")
        else:
            st.error("Router hit an error — see details below.")
        with st.expander("Router output"):
            st.code(output or "(no output)")
        st.rerun()

with a_col2:
    # Batch AI classifier — reads every Unsorted file, proposes folder + name
    # for each, and stashes results in session state so the per-row widgets
    # below pre-populate. Pete then scrolls and clicks Archive + Extract
    # on each (or overrides the suggestion first).
    batch_disabled = not RENAME_AVAILABLE or len(unsorted_files) == 0
    if st.button(
        f"AI: Identify all Unsorted ({len(unsorted_files)})",
        help="Run Claude on every Unsorted file — pre-fills folder and filename for each row. ~$0.01 per 10 files.",
        disabled=batch_disabled,
        type="primary",
    ):
        candidates = list(EXTRACTION_TARGETS) + list(ARCHIVE_ONLY_TARGETS)
        progress = st.progress(0.0, text="Reading files…")
        summary = []
        total_files = len(unsorted_files)
        for i, f in enumerate(unsorted_files):
            progress.progress((i + 0.1) / total_files, text=f"Reading {f.name}…")
            folder, filename, source, reasoning = filename_suggester.suggest_destination_and_name(f, candidates)
            if folder:
                if folder in EXTRACTION_TARGETS:
                    label = f"{folder}  (extracts → brain)"
                else:
                    label = f"{folder}  (archive only)"
                st.session_state[f"arch_{f.name}"] = label
            # Track AI's original pick for override-vs-confirm logging
            st.session_state[f"ai_folder_{f.name}"] = folder
            st.session_state[f"ai_name_{f.name}"] = filename
            st.session_state[f"rename_{f.name}"] = filename
            summary.append({
                "file": f.name,
                "folder": folder or "(no pick — review manually)",
                "proposed_name": filename,
                "source": source,
                "reasoning": reasoning,
            })
            progress.progress((i + 1) / total_files, text=f"Done {i + 1}/{total_files}")

        progress.empty()
        claude_hits = sum(1 for s in summary if s["source"] == "claude" and s["folder"] != "(no pick — review manually)")
        st.success(f"Classified {claude_hits}/{total_files} files. Review each row below and click Archive + Extract.")
        with st.expander("AI classification summary", expanded=True):
            for s in summary:
                st.markdown(f"**{s['file']}** → `{s['folder']}`")
                st.caption(f"Proposed name: `{s['proposed_name']}` — {s['reasoning']}")
        st.rerun()

# Signature-image cleanup — separate column so it doesn't steal focus
# but lives alongside the other batch actions.
with a_col3:
    sig_candidates = [p for p in unsorted_files if is_signature_image(p)]
    if st.button(
        f"Delete signature images ({len(sig_candidates)})",
        help="Remove auto-named email signature logos (imageNNN.png under 50KB). "
             "Real photos with meaningful filenames are never touched.",
        disabled=(len(sig_candidates) == 0),
    ):
        deleted = []
        for p in sig_candidates:
            try:
                p.unlink()
                deleted.append(p.name)
            except OSError as err:
                st.warning(f"Couldn't delete {p.name}: {err}")
        if deleted:
            append_log({
                "ts": datetime.now(timezone.utc).isoformat(),
                "file": "(batch)",
                "decision": "signature_images_deleted",
                "deleted_count": len(deleted),
                "deleted_files": deleted,
                "scores": {},
            })
            st.success(f"Deleted {len(deleted)} signature image(s).")
        st.rerun()

# Batch archive — commits everything the AI already classified. Only operates
# on files where ai_folder_{name} is populated; anything the AI wasn't sure
# about stays in Unsorted for manual review.
with a_col4:
    if st.button(
        f"Archive all AI-proposed ({len(ai_ready_files)})",
        help="For every Unsorted file where Claude already picked a folder, "
             "apply the proposed name + move to that folder + extract to brain. "
             "Files without a folder pick stay in Unsorted.",
        disabled=(len(ai_ready_files) == 0),
        type="primary",
    ):
        progress = st.progress(0.0, text="Archiving in batch…")
        batch_summary = []
        total = len(ai_ready_files)

        for i, f in enumerate(ai_ready_files):
            progress.progress((i + 0.1) / total, text=f"Archiving {f.name}…")
            original_name = f.name
            folder_name = st.session_state.get(f"ai_folder_{original_name}")
            proposed_name = st.session_state.get(f"ai_name_{original_name}") or original_name

            # Defensive: folder disappeared from session state? Skip.
            if not folder_name:
                batch_summary.append({"file": original_name, "status": "skipped", "reason": "no ai_folder"})
                continue

            try:
                # Apply the renamed name if it differs. Preserve original on failure.
                src = f
                if proposed_name and proposed_name != original_name:
                    try:
                        renamed = f.with_name(proposed_name)
                        f.rename(renamed)
                        src = renamed
                    except Exception as rn_err:
                        # Keep going with original name — archive is more important
                        batch_summary.append({
                            "file": original_name, "status": "rename_failed",
                            "reason": str(rn_err),
                        })

                archived = archive_to_permanent(src, folder_name)

                if folder_name in EXTRACTION_TARGETS:
                    status, detail = try_extract(archived, folder_name)
                else:
                    status, detail = "skipped_no_mapping", "Archive-only destination"

                append_log({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "file": archived.name,
                    "original_name": original_name,
                    "decision": f"archived_to:{folder_name}",
                    "ai_suggested_folder": folder_name,
                    "ai_suggested_name": proposed_name,
                    "folder_override": False,
                    "name_override": False,
                    "extract_status": status,
                    "extract_detail": detail,
                    "batch": True,
                    "scores": {},
                })

                batch_summary.append({
                    "file": original_name,
                    "archived_as": archived.name,
                    "folder": folder_name,
                    "extract": status,
                    "status": "ok",
                })

                # Clean up session state for this file so it doesn't linger
                st.session_state.pop(f"ai_folder_{original_name}", None)
                st.session_state.pop(f"ai_name_{original_name}", None)
                st.session_state.pop(f"arch_{original_name}", None)
                st.session_state.pop(f"rename_{original_name}", None)

            except Exception as err:
                batch_summary.append({"file": original_name, "status": "error", "reason": str(err)})

            progress.progress((i + 1) / total, text=f"Done {i + 1}/{total}")

        progress.empty()
        ok_count = sum(1 for s in batch_summary if s.get("status") == "ok")
        extracted_count = sum(
            1 for s in batch_summary
            if s.get("status") == "ok" and s.get("extract") == "extracted"
        )
        err_count = sum(1 for s in batch_summary if s.get("status") == "error")
        st.success(
            f"Archived {ok_count}/{total} files. "
            f"Brain updated on {extracted_count}. {err_count} errors."
        )
        with st.expander("Batch archive summary", expanded=(err_count > 0)):
            for s in batch_summary:
                if s.get("status") == "ok":
                    st.markdown(f"✓ **{s['file']}** → `{s['folder']}` as `{s['archived_as']}` _(extract: {s['extract']})_")
                elif s.get("status") == "error":
                    st.markdown(f"✗ **{s['file']}** — {s['reason']}")
                else:
                    st.caption(f"⚠ {s['file']} — {s.get('reason', s.get('status'))}")
        st.rerun()

if not unsorted_files:
    st.info("Nothing waiting. Either the router classified everything or nothing has arrived yet.")
else:
    # Build the "Archive to" dropdown options. One alphabetical list so it's
    # easy to scan; the (extracts → brain) vs (archive only) suffix makes it
    # obvious which destinations feed the brain.
    _labeled = [(n, f"{n}  (extracts → brain)") for n in EXTRACTION_TARGETS]
    _labeled += [(n, f"{n}  (archive only)") for n in ARCHIVE_ONLY_TARGETS]
    _labeled.sort(key=lambda t: t[0].lower())
    archive_options = ["— pick —"] + [label for _, label in _labeled]

    for f in unsorted_files:
        with st.container(border=True):
            # Row 1 — filename + quick actions (staging bucket, delete)
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            c1.markdown(f"**{f.name}**")
            c1.caption(f"{fmt_bytes(f.stat().st_size)} • arrived {fmt_mtime(f.stat().st_mtime)}")

            staging_choice = c2.selectbox(
                "Stage in",
                ["— stage in bucket —"] + BUCKETS,
                key=f"stage_{f.name}",
                label_visibility="collapsed",
            )

            if c3.button("Stage", key=f"stagebtn_{f.name}",
                         disabled=(staging_choice == "— stage in bucket —"),
                         help="Move to a staging bucket for later review"):
                new_path = move_file(f, staging_choice)
                st.toast(f"Staged in {staging_choice}: {new_path.name}")
                st.rerun()

            if c4.button("Delete", key=f"del_{f.name}",
                         help="Permanently delete — use for spam / non-NSIA email"):
                f.unlink()
                st.toast(f"Deleted {f.name}")
                st.rerun()

            # Row 2 — identify + pick destination
            a1, a2 = st.columns([4, 2])

            # "Suggest destination & name" — Claude reads content, proposes
            # BOTH folder and filename in one pass. Populates both widgets
            # below so Pete just confirms with Archive + Extract.
            if a1.button(
                "Suggest destination & name (AI reads the file)",
                key=f"sug_{f.name}",
                disabled=(not RENAME_AVAILABLE),
                help="Read the document, pick the best permanent folder AND propose a clean filename",
            ):
                # Build the same folder list the dropdown uses, but without UI suffixes
                candidates = list(EXTRACTION_TARGETS) + list(ARCHIVE_ONLY_TARGETS)
                with st.spinner("Reading document, choosing folder, proposing name…"):
                    folder, filename, source, reasoning = filename_suggester.suggest_destination_and_name(f, candidates)

                # Stash suggestions in session state; widgets below pick them up on rerun
                if folder:
                    # Re-add the UI suffix so the dropdown matches exactly
                    if folder in EXTRACTION_TARGETS:
                        label = f"{folder}  (extracts → brain)"
                    else:
                        label = f"{folder}  (archive only)"
                    st.session_state[f"arch_{f.name}"] = label
                # Stash AI's original pick separately so Archive step can log
                # override-vs-confirm for future rule tuning.
                st.session_state[f"ai_folder_{f.name}"] = folder
                st.session_state[f"ai_name_{f.name}"] = filename
                st.session_state[f"rename_{f.name}"] = filename

                if source == "claude":
                    if folder:
                        st.toast(f"→ {folder}: {reasoning}")
                    else:
                        st.toast(f"Proposed name: {filename} (no clear folder match — pick manually)")
                else:
                    st.toast(f"Fallback cleanup: {filename} ({reasoning})")
                st.rerun()

            archive_choice = a2.selectbox(
                "Archive to permanent NSIA folder",
                archive_options,
                key=f"arch_{f.name}",
                label_visibility="collapsed",
            )

            # Row 3 — rename field + archive button
            r1, r2 = st.columns([4, 2])
            # Pre-fill with prior suggestion if we have one, else the original name
            default_name = st.session_state.get(f"rename_{f.name}", f.name)
            new_name = r1.text_input(
                "Filename on archive",
                value=default_name,
                key=f"name_{f.name}",
                label_visibility="collapsed",
                help="Edit freely. This is the name the file will have in the permanent folder.",
            )

            if r2.button("Archive + Extract", key=f"archbtn_{f.name}",
                         disabled=(archive_choice == "— pick —"),
                         type="primary",
                         help="Move to the real NSIA folder (with this filename) AND teach the brain"):
                folder_name = archive_choice.split("  (")[0]

                # Step 1: apply rename in place before the move. Keep the
                # original for the audit log so we can trace it back.
                original_name = f.name
                renamed_source = f
                if new_name and new_name != original_name:
                    try:
                        renamed_source = f.with_name(new_name)
                        f.rename(renamed_source)
                    except Exception as rename_err:
                        # Rename failed — proceed with original name rather than block archiving
                        st.warning(f"Rename failed ({rename_err}); archiving with original name.")
                        renamed_source = f

                # Step 2: move to permanent folder
                with st.spinner(f"Archiving to {folder_name}…"):
                    archived = archive_to_permanent(renamed_source, folder_name)

                    # Step 3: feed the brain if the destination supports it
                    if folder_name in EXTRACTION_TARGETS:
                        with st.spinner("Teaching the brain (this can take 10-30s)…"):
                            status, detail = try_extract(archived, folder_name)
                    else:
                        status, detail = "skipped_no_mapping", "Archive-only destination"

                if status == "extracted":
                    st.success(f"✓ Archived as `{archived.name}` to `data/{folder_name}/` and brain updated.")
                elif status.startswith("skipped"):
                    st.info(f"Archived as `{archived.name}` to `data/{folder_name}/`. Extraction skipped: {detail}")
                else:
                    st.warning(f"Archived as `{archived.name}` to `data/{folder_name}/` but extraction failed: {detail}")

                # Audit log captures AI pick vs final choice so we can spot
                # systematic misroutes. Grep the jsonl for `folder_override: true`
                # to see where rules need tuning.
                ai_folder = st.session_state.get(f"ai_folder_{original_name}")
                ai_name = st.session_state.get(f"ai_name_{original_name}")
                folder_override = bool(ai_folder) and ai_folder != folder_name
                name_override = bool(ai_name) and ai_name != archived.name
                append_log({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "file": archived.name,
                    "original_name": original_name,
                    "decision": f"archived_to:{folder_name}",
                    "ai_suggested_folder": ai_folder,
                    "ai_suggested_name": ai_name,
                    "folder_override": folder_override,
                    "name_override": name_override,
                    "extract_status": status,
                    "extract_detail": detail,
                    "scores": {},
                })

                # Clean up the session-state rename key so the widget doesn't
                # carry a stale suggestion on the next file that happens to
                # have the same name (unlikely but defensive).
                st.session_state.pop(f"rename_{original_name}", None)
                st.session_state.pop(f"ai_folder_{original_name}", None)
                st.session_state.pop(f"ai_name_{original_name}", None)
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
