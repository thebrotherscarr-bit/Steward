#!/usr/bin/env pwsh
# release.ps1 -- Cut a release: prove, bump, commit, tag, push
#
# PLAIN SEMVER. NO STONE. version.ps1 was cured of the moniker on 2026-09-10
# ("remove the moniker for the stones, no letters in my versions") and THIS
# FILE, ITS ONLY CALLER, WAS NOT. It computed `0.1.5+f1`, handed that to
# `version.ps1 set`, and version.ps1 now REFUSES a version carrying a tag --
# so the only release path this repository has did not merely cut a bad tag,
# it DIED at step 2 of 4, after running the whole prove suite. Found
# 2026-09-12 by reading it; it had been broken since the day the other half
# was fixed.
#
# Usage:
#   .\release.ps1                    # interactive: ask for version
#   .\release.ps1 0.1.5              # explicit version
#   .\release.ps1 0.1.5 -DryRun      # show what would happen
#
# AND IT WOULD NOT PARSE AT ALL until 2026-09-12. This file is UTF-8 with NO
# BOM and carried em-dashes; PowerShell 5.1 reads a BOM-less file as ANSI, so
# the dash became three bytes of nonsense and broke the string on the `<ver>`
# line -- "The '<' operator is reserved for future use". The moniker fault
# below it had never been reachable, because the script could not load.
# `prove.ps1`, which step 1 calls, had the same single dash and the same
# fault. Both are pure ASCII now, so no BOM has to survive a future edit.
#
# `--dry-run` was also never a thing: PowerShell takes `-DryRun`.

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
    Write-Host "  patch  -- $current -> increment patch (e.g. 0.1.5)" -ForegroundColor Gray
    Write-Host "  minor  -- $current -> increment minor (e.g. 0.2.0)" -ForegroundColor Gray
    Write-Host "  major  -- $current -> increment major (e.g. 1.0.0)" -ForegroundColor Gray
    Write-Host "  <ver>  -- explicit version (e.g. 0.2.0)" -ForegroundColor Gray
    Write-Host ""
    $Version = Read-Host "Enter bump type or version"
}

# --- Parse version ---
function Parse-Version($v) {
    # Plain major.minor.patch. Nothing else is a version here -- the same
    # shape, and the same refusal, as version.ps1's own parser. A tag is
    # REFUSED rather than stripped: a caller that typed one meant something,
    # and quietly dropping it is how a pin gets rewritten behind somebody.
    if ($v -match '^(\d+)\.(\d+)\.(\d+)$') {
        return @{ Major = [int]$Matches[1]; Minor = [int]$Matches[2]; Patch = [int]$Matches[3] }
    }
    if ($v -match '\+') {
        Write-Host "Refused: '$v' carries a build tag. The stone moniker was struck 2026-09-10 -- versions are plain semver now." -ForegroundColor Red
        exit 1
    }
    Write-Host "Invalid version: $v (expected major.minor.patch)" -ForegroundColor Red; exit 1
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
$target = "$($parsed.Major).$($parsed.Minor).$($parsed.Patch)"
$tag = "v$target"

Write-Host ""
Write-Host "Release plan:" -ForegroundColor Yellow
Write-Host "  Current:  $current" -ForegroundColor Gray
Write-Host "  Target:   $target" -ForegroundColor Green
Write-Host "  Tag:      $tag" -ForegroundColor Green

if ($DryRun) {
    Write-Host ""
    Write-Host "DRY RUN -- no changes made" -ForegroundColor Yellow
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
if ($LASTEXITCODE -ne 0) { Write-Host "PROVE FAILED -- aborting release" -ForegroundColor Red; exit 1 }

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
# THIS SAID "GitHub Actions will build binaries and create the release."
# NOTHING DOES. `.github/workflows/` holds one file, prove.yml, and it runs on
# push/PR -- not on a tag. There has never been a release workflow, and
# DELIVERABLE.md named one for weeks. A script that tells the operator work is
# happening somewhere else, when it is not, is worse than one that says
# nothing: he stops looking.
Write-Host "The tag is pushed. NOTHING BUILDS IT FOR YOU -- there is no release" -ForegroundColor Yellow
Write-Host "workflow; prove.yml runs on push/PR, not on tags. Binaries and a" -ForegroundColor Yellow
Write-Host "GitHub release are still a hand's work from here." -ForegroundColor Yellow
