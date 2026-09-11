#!/usr/bin/env pwsh
# version.ps1 -- Local version management
#
# PLAIN SEMVER. NO STONE. Through 0.1.1 the version carried a build tag
# naming the stone that cut it (`0.1.1+f1`). The operator struck it
# 2026-09-10: "remove the moniker for the stones, no letters in my versions."
#
# This script used to FORCE one back on: Format-Version always appended
# "+$Stone", and Parse-Version defaulted a stoneless version to "f1". So the
# next `bump patch` after the ruling would have quietly re-written 0.1.2 as
# 0.1.2+f1 and re-broken every pin. The stone is gone from here entirely, and
# Parse-Version now REFUSES a version carrying one.
#
# Usage:
#   .\version.ps1                    # show current version
#   .\version.ps1 bump patch         # 0.1.2 -> 0.1.3
#   .\version.ps1 bump minor         # 0.1.2 -> 0.2.0
#   .\version.ps1 bump major         # 0.1.2 -> 1.0.0
#   .\version.ps1 set 0.2.0          # set explicit version
#   .\version.ps1 sync               # verify all VERSION files match

param(
    [Parameter(Position = 0)]
    [string]$Action = "show",

    [Parameter(Position = 1)]
    [string]$Value = ""
)

$ErrorActionPreference = "Stop"

$VERSION_FILES = @(
    "VERSION",
    "line/VERSION",
    "line/cmd/atlas-mcp/VERSION",
    "line/cmd/atlas-tui/VERSION",
    "line/cmd/atlas-town/VERSION",
    "line/cmd/atlas-door/VERSION"
)

function Get-CurrentVersion {
    return (Get-Content "VERSION" -Raw).Trim()
}

function Parse-Version($v) {
    # Plain major.minor.patch. Nothing else is a version here.
    if ($v -match '^(\d+)\.(\d+)\.(\d+)$') {
        return @{
            Major = [int]$Matches[1]
            Minor = [int]$Matches[2]
            Patch = [int]$Matches[3]
        }
    }
    if ($v -match '\+') {
        Write-Host "Refused: '$v' carries a build tag. The stone moniker was struck 2026-09-10 -- versions are plain semver now." -ForegroundColor Red
        exit 1
    }
    Write-Host "Invalid version format: $v (expected major.minor.patch)" -ForegroundColor Red
    exit 1
}

function Format-Version($parsed) {
    return "$($parsed.Major).$($parsed.Minor).$($parsed.Patch)"
}

function Set-Version($newVersion) {
    foreach ($f in $VERSION_FILES) {
        Set-Content -Path $f -Value $newVersion -NoNewline
    }
    Write-Host "Version updated to $newVersion" -ForegroundColor Green
    Write-Host "Files updated:" -ForegroundColor Cyan
    $VERSION_FILES | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    Write-Host "These are NOT the only pins. Cargo.toml, core/src/version.rs," -ForegroundColor Yellow
    Write-Host "the two Go mains, both webapp handlers and two test harnesses" -ForegroundColor Yellow
    Write-Host "carry the string too. Run 'python tests/prove.py' -- the spine's" -ForegroundColor Yellow
    Write-Host "version-cross stroke names every file still out of step." -ForegroundColor Yellow
}

function Sync-Check {
    $root = Get-CurrentVersion
    $allMatch = $true
    foreach ($f in $VERSION_FILES) {
        $ver = (Get-Content $f -Raw).Trim()
        if ($ver -ne $root) {
            Write-Host "MISMATCH: $f is $ver, expected $root" -ForegroundColor Red
            $allMatch = $false
        }
    }
    if ($root -match '\+') {
        Write-Host "MISMATCH: VERSION is '$root' -- build tags were struck 2026-09-10." -ForegroundColor Red
        $allMatch = $false
    }
    if ($allMatch) {
        Write-Host "All VERSION files in sync: $root" -ForegroundColor Green
    } else {
        exit 1
    }
}

switch ($Action) {
    "show" {
        $v = Get-CurrentVersion
        Write-Host "Current version: $v" -ForegroundColor Cyan
    }
    "bump" {
        if (-not $Value) { Write-Host "Usage: .\version.ps1 bump <patch|minor|major>" -ForegroundColor Red; exit 1 }
        $current = Get-CurrentVersion
        $parsed = Parse-Version $current
        switch ($Value) {
            "patch" { $parsed.Patch++ }
            "minor" { $parsed.Minor++; $parsed.Patch = 0 }
            "major" { $parsed.Major++; $parsed.Minor = 0; $parsed.Patch = 0 }
            default { Write-Host "Unknown bump type: $Value (use patch/minor/major)" -ForegroundColor Red; exit 1 }
        }
        $newVersion = Format-Version $parsed
        Set-Version $newVersion
    }
    "set" {
        if (-not $Value) { Write-Host "Usage: .\version.ps1 set <version>" -ForegroundColor Red; exit 1 }
        $parsed = Parse-Version $Value
        $newVersion = Format-Version $parsed
        Set-Version $newVersion
    }
    "sync" {
        Sync-Check
    }
    default {
        Write-Host "Usage: .\version.ps1 [show|bump|set|sync]" -ForegroundColor Yellow
        Write-Host "  show            Show current version" -ForegroundColor Gray
        Write-Host "  bump <type>     Bump patch/minor/major" -ForegroundColor Gray
        Write-Host "  set <version>   Set explicit version" -ForegroundColor Gray
        Write-Host "  sync            Verify all VERSION files match" -ForegroundColor Gray
    }
}
