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
