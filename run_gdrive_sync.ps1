$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Keep deps fresh. Pip is a no-op when already up-to-date, so safe to run every time.
python -m pip install --upgrade pip | Out-Null
python -m pip install -r .\requirements-gdrive-sync.txt | Out-Null

# Reuse the OAuth client the Document Library page already has. Desktop app
# type, so it works for any scope the user grants on first auth.
$CredsPath = ".\data\documents\client_secret.json"
$TokenPath = ".\token.json"

# 1. Main NSIA Drive root — board meetings, financials, contracts, etc.
#    Mirrors to .\data (recursive).
python .\sync_gdrive_to_local.py sync --once `
    --folder-id 1r0s755LUwwE_s9We3rmtjxad8B5j8xaI `
    --dest .\data `
    --credentials $CredsPath `
    --token $TokenPath `
    --state sync_state.json

# 2. Ingestion drop folder — owned by nsia.inbox@gmail.com, shared with pcecil21@gmail.com.
#    Gmail Apps Script drops attachments here; we mirror to .\data\Ingestion locally.
#    Separate state file so the two syncs don't step on each other.
python .\sync_gdrive_to_local.py sync --once `
    --folder-id 1M29plMEpDVIENzkmltCoXPb6eajVl13K `
    --dest .\data\Ingestion `
    --credentials $CredsPath `
    --token $TokenPath `
    --state sync_state_ingestion.json

# 3. Auto-route newly arrived Unsorted files into the right bucket.
python .\scripts\route_inbox.py
