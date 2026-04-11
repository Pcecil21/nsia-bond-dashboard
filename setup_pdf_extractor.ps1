# NSIA PDF Extractor Setup
# Run from project root:
#   cd "C:\Users\pceci\Claude\Projects\nsia-bond-dashboard"
#   .\setup_pdf_extractor.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n=== NSIA PDF Extractor Setup ===" -ForegroundColor Cyan

# 1. Install missing dependency
Write-Host "`n[1/3] Installing python-dotenv..." -ForegroundColor Yellow
pip install python-dotenv --quiet
Write-Host "  Done." -ForegroundColor Green

# 2. Create .env if missing
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "`n[2/3] Creating .env template..." -ForegroundColor Yellow
    "# NSIA Bond Dashboard`nANTHROPIC_API_KEY=your_key_here" | Set-Content $envFile -Encoding UTF8
    Write-Host "  Created .env — fill in ANTHROPIC_API_KEY before running extractor." -ForegroundColor Green
} else {
    Write-Host "`n[2/3] .env already exists — skipping." -ForegroundColor Gray
}

# 3. Confirm files exist
Write-Host "`n[3/3] Checking for extractor files..." -ForegroundColor Yellow
$extractor = Join-Path $ProjectRoot "utils\pdf_extractor.py"
$additions = Join-Path $ProjectRoot "utils\data_loader_additions.py"

if (Test-Path $extractor) {
    Write-Host "  FOUND: utils\pdf_extractor.py" -ForegroundColor Green
} else {
    Write-Host "  MISSING: utils\pdf_extractor.py — download from Claude chat and save here" -ForegroundColor Red
}

if (Test-Path $additions) {
    Write-Host "  FOUND: utils\data_loader_additions.py" -ForegroundColor Green
} else {
    Write-Host "  MISSING: utils\data_loader_additions.py — download from Claude chat and save here" -ForegroundColor Red
}

Write-Host "`n=== Next steps ===" -ForegroundColor Cyan
Write-Host "1. Open .env and set ANTHROPIC_API_KEY"
Write-Host "2. Paste data_loader_additions.py content into bottom of utils\data_loader.py"
Write-Host "   (also add 'import json' at top of data_loader.py if not present)"
Write-Host "3. Run dry run:"
Write-Host "   python utils/pdf_extractor.py --all --dry-run" -ForegroundColor Cyan
Write-Host "4. Run real extraction:"
Write-Host "   python utils/pdf_extractor.py --type bond" -ForegroundColor Cyan
Write-Host "   python utils/pdf_extractor.py --type umb" -ForegroundColor Cyan
Write-Host "   python utils/pdf_extractor.py --all" -ForegroundColor Cyan
