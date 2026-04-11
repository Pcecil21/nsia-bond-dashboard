# NSIA Bond Dashboard

## Overview
Multi-page Streamlit app for NSIA board financial analysis, bond tracking, and document management. Syncs with Google Drive.

## Tech Stack
- **Framework:** Streamlit (Python)
- **Data:** Local files synced from Google Drive
- **AI:** Sub-agent system in agents/

## Project Structure
- app.py — Main Streamlit entry point
- pages/ — Streamlit multi-page app pages
- agents/ — AI governance sub-agent prompts
- config/ — Configuration (auth.yaml)
- data/ — Synced data from GDrive
- utils/ — Shared utilities (auth, data_loader)
- scripts/ — Utility scripts

## Key Commands
- streamlit run app.py — Start dashboard
- python sync_gdrive_to_local.py — Sync from Google Drive
- pip install -r requirements.txt — Install dependencies

## Conventions
- New pages go in pages/ following Streamlit multi-page pattern
- Board documents stay in data/, never committed
- Do NOT commit config/auth.yaml
- GDrive sync scheduled task: GDrive-to-NSIA-Sync
- GitHub: pcecil21/nsia-bond-dashboard (if configured)

## Session Rules (Global)
1. Read this file and decisions.md (if it exists) at session start.
2. Ask before creating new patterns — if a similar file/component exists, follow it.
3. Don't refactor unless asked. Fix what's requested, nothing else.
4. Don't install new packages without asking. Use what's in package.json.
5. If stuck after 2 attempts, stop and explain the problem instead of looping.
6. Show the file path of every file you create or modify.
7. Run the project's build/lint command before saying you're done.
8. Use sync/await, never .then() chains.
9. Always wrap Supabase/DB calls in try/catch or check .error.
10. No ny types in TypeScript unless explicitly told.
## Project Skills
Skills library: C:\Users\pceci\Claude\Projects\pete-skills-library\
Load these RIA / Advisory skills when relevant:
- board-memo-from-notes/SKILL.md — Board memos from meeting notes
- compliance-sop-policy/SKILL.md — SOP and policy drafts
- compliance-trade-rationale/SKILL.md — Trade rationale / IC notes
- linkedin-content-creator/SKILL.md — LinkedIn advisor content
- meeting-notes-to-crm-followup/SKILL.md — Meeting notes to CRM tasks + follow-up email
- year-end-tax-checklist/SKILL.md — Year-end tax planning checklist + client email
