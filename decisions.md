# Decisions Log

> Strategic decisions made outside this project (Claude.ai conversations, calls, meetings).
> Claude Code: read this file before starting any task. Flag conflicts with CLAUDE.md.

---

<!-- TEMPLATE - copy this block for each new decision:

## YYYY-MM-DD - [Short title]
**Source:** Claude.ai / meeting / call / email
**Decision:** [What was decided]
**Why:** [1-2 sentences on reasoning]
**Impact on this project:**
- [Specific change to code/architecture/scope]
- [What to stop, start, or change]
**Status:** Active / Superseded by [date]

-->

## 2026-04-24 — Email-to-dashboard ingestion pipeline shipped

Decision: Build an end-to-end pipeline so anyone can forward NSIA mail to a single address and have attachments auto-land in the right permanent Drive folder with extraction feeding the Ask NSIA brain.

Rationale:
- Privacy isolation: dedicated `nsia.inbox@gmail.com` handles all Gmail + Apps Script — personal `pcecil21@gmail.com` never grants the script Gmail read access. If automation is compromised, blast radius is NSIA-only.
- Classification in code, not Gmail UI: skipped the 6-Gmail-filter design. Everything lands in `NSIA Ingestion/Unsorted/`; local Python + Claude does all classification. Rules are version-controlled and editable without touching the cloud.
- Two-tier model strategy: `pdf_extractor.py` uses Sonnet 4.6 for high-stakes extraction (DSCR, covenants → brain JSON); `filename_suggester.py` uses Haiku 4.5 for filename/folder suggestions (~$0.001/file). Right model per task.
- Folder taxonomy cleanup: dropped `NSIA` prefix from most Drive folders. Kept `NSIA Corporate Records` as a new folder for foundational legal docs (Articles of Organization, 501C3 letter, bylaws, EIN) — existing Operating Agreement/Audit Docs folders were muddling governance amendments vs formation docs.
- Active Initiatives context: `data/active_initiatives.md` gives Ask NSIA brain context for fluid projects (e.g. Ice Shack / Nick Larkin concession) that live outside formal documents. Edit the markdown; no code changes.
- Signature-image filter at both layers: Apps Script skips `image\d+\.(png|jpg)` under 50KB at ingestion; Inbox page has batch-delete button for historical noise. Real photos (IMG_1234.jpg) are untouched.

Constraints:
- Apps Script has full Gmail read on the account it runs in — non-negotiable, which is why `nsia.inbox@gmail.com` must be dedicated.
- Google Cloud Console no longer allows re-downloading existing OAuth client secrets (policy change). Rotation requires "add new → disable old" flow, not "re-download."
- `run_gdrive_sync.ps1` uses `--once` so it can be wired into Windows Task Scheduler later; currently manual.

Next steps:
- Schedule `run_gdrive_sync.ps1` in Task Scheduler so the local mirror refreshes automatically (not manual).
- Monitor AI folder-routing accuracy for 2-4 weeks; if Unsorted gets noisy or Claude misroutes on particular patterns, tune `FOLDER_DESCRIPTIONS` in `utils/filename_suggester.py`.
- Decide whether to extend `pdf_extractor.py` with new extraction types for Board Meetings minutes or Insurance docs (brain currently doesn't learn these).
- Commit today's work (12+ files changed — not yet committed at session end).

Status: Approved — live and in use.

---

## 2026-04-17 — Planka evaluated as potential NSIA board collaboration tool

**Status:** Tabled / parked for future consideration

**Context:**
Came across Planka (github.com/plankanban/planka) — open-source, self-hosted Trello alternative. Node.js + React, Docker Compose deploy, real-time collaboration, v2.1.0 released March 2026, 11.9k stars, 156 contributors, dual-licensed (AGPL + commercial).

**Evaluation:**
Not a fit for Paperclip / Ice Scheduler / LaxVerse / brain-mcp / RIA work — Claude Code + Obsidian + GitHub Issues + Redtail already cover those workflows, and adding another system creates source-of-truth drift.

Potential fit: NSIA board governance. Gives non-technical board members a shared visual view of initiatives, committee work, and bond-related tasks without requiring them to touch Obsidian or GitHub. Could coexist with the bond dashboard on the same VPS infrastructure.

**Decision:**
Do not deploy now. Revisit if/when board collaboration surface area grows beyond what email + bond dashboard + board packets can handle, or if a specific board initiative creates demand for shared task tracking.

**If revisited, implementation sketch:**
- Deploy via Docker Compose on existing VPS
- Subdomain: planka.nsia.* or similar
- Separate from bond-dashboard Streamlit app (different port/container)
- Board structure: one board per standing committee + one for full-board initiatives
- User provisioning: board members only (not staff/operations)
- Review compliance/data-handling implications before storing any sensitive governance items

**Owner:** Pete
**Next review trigger:** Board asks for shared task visibility, OR bond dashboard scope expands to include non-financial governance tracking.
