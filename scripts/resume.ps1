# resume.ps1 - Run this when STARTING work on this computer
# Pulls latest changes and installs dependencies.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "`n=== RESUME ===" -ForegroundColor Cyan
Write-Host "Repo: $(Get-Location)" -ForegroundColor Gray
Write-Host "Branch: $(git branch --show-current)" -ForegroundColor Gray
Write-Host ""

# Pull latest
Write-Host "Pulling latest changes..." -ForegroundColor Yellow
git pull --rebase origin (git branch --show-current)
Write-Host ""

# Set up Python virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "Activating venv and installing dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
} elseif (Test-Path "pyproject.toml") {
    pip install -e .
}
Write-Host ""

Write-Host "Ready! You're up to date." -ForegroundColor Green
