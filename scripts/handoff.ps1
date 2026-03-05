# handoff.ps1 - Run this when STOPPING work on this computer
# Stages, commits, and pushes your current work so you can resume on another machine.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "`n=== HANDOFF ===" -ForegroundColor Cyan
Write-Host "Repo: $(Get-Location)" -ForegroundColor Gray
Write-Host "Branch: $(git branch --show-current)" -ForegroundColor Gray
Write-Host ""

# Show status
git status --short
Write-Host ""

# Check for changes
$changes = git status --porcelain
if (-not $changes) {
    Write-Host "No changes to commit. Pushing any unpushed commits..." -ForegroundColor Yellow
    git push origin (git branch --show-current) 2>&1
    Write-Host "`nHandoff complete (nothing new to commit)." -ForegroundColor Green
    exit 0
}

# Ask for commit message
$msg = Read-Host "Commit message (default: 'wip: progress')"
if (-not $msg) { $msg = "wip: progress" }

# Stage, commit, push
git add -A
git commit -m $msg
git push origin (git branch --show-current)

Write-Host "`nHandoff complete! Safe to switch computers." -ForegroundColor Green
