$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

python -m pip install --upgrade pip
python -m pip install -r .\requirements-gdrive-sync.txt
python .\sync_gdrive_to_local.py
