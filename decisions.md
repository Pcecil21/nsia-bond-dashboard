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
