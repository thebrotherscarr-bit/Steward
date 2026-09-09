#!/usr/bin/env pwsh
# release.ps1 — Cut a release: prove, bump, commit, tag, push
# Usage:
#   .\release.ps1                    # interactive: ask for version
#   .\release.ps1 0.1.2+f2           # explicit version
#   .\release.ps1 --dry-run          # show what would happen

param(
    [Parameter(Position = 0)]
    [string]$Version = "",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# --- Get target version ---
$current = (Get-Content VERSION -Raw).Trim()
Write-Host "=== ATLAS RELEASE ===" -ForegroundColor Cyan
Write-Host "Current version: $current" -ForegroundColor Gray

if (-not $Version) {
    Write-Host ""
    Write-Host "Bump types:" -ForegroundColor Yellow
    Write-Host "  patch  — $current -> increment patch (e.g. 0.1.2+f2)" -ForegroundColor Gray
    Write-Host "  minor  — $current -> increment minor (e.g. 0.2.0+f1)" -ForegroundColor Gray
    Write-Host "  major  — $current -> increment major (e.g. 1.0.0+f1)" -ForegroundColor Gray
    Write-Host "  <ver>  — explicit version (e.g. 0.2.0+f3)" -ForegroundColor Gray
    Write-Host ""
    $Version = Read-Host "Enter bump type or version"
}

# --- Parse version ---
function Parse-Version($v) {
    if ($v -match '^(\d+)\.(\d+)\.(\d+)\+(.+)$') {
        return @{ Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3]; Stone = $Matches[4] }
    }
    if ($v -match '^(\d+)\.(\d+)\.(\d+)$') {
        return @{ Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3]; Stone = "f1" }
    }
    Write-Host "Invalid version: $v" -ForegroundColor Red; exit 1
}

$parsed = Parse-Version $current
switch ($Version) {
    "patch" { $parsed.Patch++ }
    "minor" { $parsed.Minor++; $parsed.Patch = 0 }
    "major" { $parsed.Major++; $parsed.Minor = 0; $parsed.Patch = 0 }
    default {
        $parsed = Parse-Version $Version
    }
}
$target = "$($parsed.Major).$($parsed.Minor).$($parsed.Patch)+$($parsed.Stone)"
$tag = "v$target"

Write-Host ""
Write-Host "Release plan:" -ForegroundColor Yellow
Write-Host "  Current:  $current" -ForegroundColor Gray
Write-Host "  Target:   $target" -ForegroundColor Green
Write-Host "  Tag:      $tag" -ForegroundColor Green

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN — no changes made" -ForegroundColor Yellow
    exit 0
}

# --- Confirm ---
$confirm = Read-Host "Proceed? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Aborted." -ForegroundColor Red
    exit 0
}

# --- Step 1: Run prove ---
Write-Host ""
Write-Host "[1/4] Running full prove..." -ForegroundColor Yellow
.\prove.ps1
if ($LASTEXITCODE -ne 0) { Write-Host "PROVE FAILED — aborting release" -ForegroundColor Red; exit 1 }

# --- Step 2: Bump version ---
Write-Host ""
Write-Host "[2/4] Setting version to $target..." -ForegroundColor Yellow
.\version.ps1 set $target
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: version set" -ForegroundColor Red; exit 1 }

# --- Step 3: Commit ---
Write-Host ""
Write-Host "[3/4] Committing..." -ForegroundColor Yellow
git add -A
git commit -m "release: $target"

# --- Step 4: Tag ---
Write-Host ""
Write-Host "[4/4] Tagging $tag..." -ForegroundColor Yellow
git tag -a $tag -m "Release $target"

# --- Push ---
Write-Host ""
$pushConfirm = Read-Host "Push commit and tag to origin? (y/N)"
if ($pushConfirm -eq "y" -or $pushConfirm -eq "Y") {
    git push origin main
    git push origin $tag
    Write-Host "Pushed." -ForegroundColor Green
} else {
    Write-Host "Skipped push. Run manually:" -ForegroundColor Yellow
    Write-Host "  git push origin main" -ForegroundColor Gray
    Write-Host "  git push origin $tag" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== RELEASE $target COMPLETE ===" -ForegroundColor Cyan
Write-Host "GitHub Actions will build binaries and create the release." -ForegroundColor Green
