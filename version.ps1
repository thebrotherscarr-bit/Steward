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

# EIGHT, NOT SIX (2026-09-12). This list held six, and the two it was missing
# were the two that printed a HARDCODED literal instead of reading a file:
# atlas-vc had no VERSION beside it at all, and webapp said "0.1.3" by hand in
# /health and in the Prometheus gauge. Both were given one and both now read
# it -- so both belong here, or the next bump leaves them behind exactly the
# way the last one nearly did.
$VERSION_FILES = @(
    "VERSION",
    "line/VERSION",
    "line/cmd/atlas-mcp/VERSION",
    "line/cmd/atlas-tui/VERSION",
    "line/cmd/atlas-town/VERSION",
    "line/cmd/atlas-door/VERSION",
    "line/cmd/atlas-vc/VERSION",
    "webapp/handlers/VERSION"
)

# THE PINS THAT ARE NOT VERSION FILES. `core/src/version.rs` READS the root
# VERSION (include_str!), so its code needs nothing -- but the test beside it
# asserts the expected value, and that assertion is a pin like any other.
# Cargo.toml declares the workspace version and has exactly one `version =`.
#
# These used to be a WARNING telling the reader to run a stroke that does not
# exist ("the spine's version-cross stroke names every file still out of
# step" -- there is no such leg in tests/prove.py). A bump that leaves them
# behind ships a Cargo.toml disagreeing with every binary, and `release.ps1`
# would commit and tag it. So they are moved, not mentioned.
$PIN_PATTERNS = @(
    @{ Path = "Cargo.toml";          Pattern = '(?m)^version = "[^"]*"';      Format = 'version = "{0}"' },
    @{ Path = "core/src/version.rs"; Pattern = 'assert_eq!\(v, "[^"]*"\)';    Format = 'assert_eq!(v, "{0}")' }
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
    # .NET FILE APIS, NOT Get-Content/Set-Content, AND THAT IS LOAD-BEARING.
    # The first draft of this used them and CORRUPTED core/src/version.rs on
    # its first run (2026-09-12): PowerShell 5.1's Get-Content reads a
    # BOM-less file as ANSI, so every multi-byte UTF-8 sequence became
    # separate Latin-1 characters (a section sign became two, an em-dash
    # became three) -- and
    # `Set-Content -Encoding utf8` then re-encoded that mojibake AND added a
    # BOM. A version bump must move a version and touch nothing else.
    #
    # ReadAllText detects UTF-8 properly; UTF8Encoding($false) writes without
    # a BOM. The file's own line terminators survive because only the matched
    # substring is replaced.
    $noBom = New-Object System.Text.UTF8Encoding($false)
    foreach ($pin in $PIN_PATTERNS) {
        $full = (Resolve-Path $pin.Path).Path
        $body = [IO.File]::ReadAllText($full, [Text.Encoding]::UTF8)
        $want = [string]::Format($pin.Format, $newVersion)
        if ($body -notmatch $pin.Pattern) {
            Write-Host "FAIL: no pin matching $($pin.Pattern) in $($pin.Path)" -ForegroundColor Red
            exit 1
        }
        $body = [regex]::Replace($body, $pin.Pattern, $want)
        [IO.File]::WriteAllText($full, $body, $noBom)
    }
    Write-Host "Version updated to $newVersion" -ForegroundColor Green
    Write-Host "Files updated:" -ForegroundColor Cyan
    $VERSION_FILES | ForEach-Object { Write-Host "  $_" }
    $PIN_PATTERNS | ForEach-Object { Write-Host "  $($_.Path)" }
    Write-Host ""
    Write-Host "DOCS ARE STILL YOURS. ACCEPTANCE, PIPELINES, OLLAMA_PROVER," -ForegroundColor Yellow
    Write-Host "WORKFLOWS, E2E_SCENARIOS and AGENTS each ASSERT what a binary" -ForegroundColor Yellow
    Write-Host "prints; they are claims, not pins, and a sweep that moved them" -ForegroundColor Yellow
    Write-Host "would rewrite the CHANGELOG's history with them. Run" -ForegroundColor Yellow
    Write-Host "'.\version.ps1 sync' to prove the pins, then read the docs." -ForegroundColor Yellow
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
    # THE PINS ARE CHECKED TOO, or `sync` says "in sync" over a Cargo.toml
    # that disagrees with every binary -- which is exactly what it did.
    foreach ($pin in $PIN_PATTERNS) {
        $body = Get-Content -Path $pin.Path -Raw
        $want = [string]::Format($pin.Format, $root)
        if ($body -notmatch [regex]::Escape($want)) {
            Write-Host "MISMATCH: $($pin.Path) does not carry '$want'" -ForegroundColor Red
            $allMatch = $false
        }
    }
    if ($root -match '\+') {
        Write-Host "MISMATCH: VERSION is '$root' -- build tags were struck 2026-09-10." -ForegroundColor Red
        $allMatch = $false
    }
    if ($allMatch) {
        $n = $VERSION_FILES.Count + $PIN_PATTERNS.Count
        Write-Host "All $n pins in sync: $root" -ForegroundColor Green
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
