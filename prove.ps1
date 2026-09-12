#!/usr/bin/env pwsh
# prove.ps1 -- Full ATLAS prove suite
# Usage: .\prove.ps1
# Exit 0 = all green. Any non-zero = something failed.

$ErrorActionPreference = "Stop"

Write-Host "=== ATLAS PROVE ===" -ForegroundColor Cyan
Write-Host "Version: $(Get-Content VERSION -Raw)" -ForegroundColor Gray
Write-Host ""

# --- Rust ---
Write-Host "[1/6] Rust tests..." -ForegroundColor Yellow
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo test --workspace
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Rust tests" -ForegroundColor Red; exit 1 }
Write-Host "  PASS" -ForegroundColor Green

# --- Go ---
Write-Host "[2/6] Go tests..." -ForegroundColor Yellow
Push-Location line
go test ./...
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "FAIL: Go tests" -ForegroundColor Red; exit 1 }
Pop-Location
Write-Host "  PASS" -ForegroundColor Green

# --- Python ---
Write-Host "[3/6] Python verifiers..." -ForegroundColor Yellow
.venv\Scripts\python.exe tools\cut_canon_vectors.py --verify
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: canon vectors" -ForegroundColor Red; exit 1 }
.venv\Scripts\python.exe tools\cut_chain_verdicts.py --verify
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: chain verdicts" -ForegroundColor Red; exit 1 }
.venv\Scripts\python.exe tools\cut_us_vectors.py --verify
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: US vectors" -ForegroundColor Red; exit 1 }
.venv\Scripts\python.exe tools\fold_agents.py --verify
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: agent fold" -ForegroundColor Red; exit 1 }
Write-Host "  PASS" -ForegroundColor Green

# --- MCP prove ---
Write-Host "[4/6] MCP prove (58 strokes)..." -ForegroundColor Yellow
Push-Location line
go run ./cmd/atlas-mcp --prove
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "FAIL: MCP prove" -ForegroundColor Red; exit 1 }
Pop-Location
Write-Host "  PASS" -ForegroundColor Green

# --- Agent enrollment ---
Write-Host "[5/6] Agent enrollment validation..." -ForegroundColor Yellow
$tmpDir = "$env:TEMP\atlas_prove_$([guid]::NewGuid().ToString('N').Substring(0,8))"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$tmpDb = "$tmpDir\master_copy.db"
Copy-Item "data\master.db" $tmpDb
cargo run -q -p atlas -- agent enroll $tmpDb --dir agents --dry
if ($LASTEXITCODE -ne 0) { Remove-Item $tmpDir -Recurse -ErrorAction SilentlyContinue; Write-Host "FAIL: agent enrollment" -ForegroundColor Red; exit 1 }
Remove-Item $tmpDir -Recurse -ErrorAction SilentlyContinue
Write-Host "  PASS" -ForegroundColor Green

# --- Webapp build ---
Write-Host "  Webapp build..." -ForegroundColor Yellow
Push-Location webapp
go build ./...
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "FAIL: webapp build" -ForegroundColor Red; exit 1 }
go vet ./...
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "FAIL: webapp vet" -ForegroundColor Red; exit 1 }
Pop-Location
Write-Host "  PASS" -ForegroundColor Green

# --- Version consistency ---
Write-Host "[6/6] Version consistency..." -ForegroundColor Yellow
$root = (Get-Content VERSION -Raw).Trim()
$files = @("line/VERSION", "line/cmd/atlas-mcp/VERSION", "line/cmd/atlas-tui/VERSION", "line/cmd/atlas-town/VERSION", "line/cmd/atlas-door/VERSION")
$versionOk = $true
foreach ($f in $files) {
    $ver = (Get-Content $f -Raw).Trim()
    if ($ver -ne $root) {
        Write-Host "  MISMATCH: $f is $ver, expected $root" -ForegroundColor Red
        $versionOk = $false
    }
}
if (-not $versionOk) { Write-Host "FAIL: version mismatch" -ForegroundColor Red; exit 1 }
Write-Host "  All VERSION files: $root" -ForegroundColor Green
Write-Host "  PASS" -ForegroundColor Green

Write-Host ""
Write-Host "=== ALL PROVEN ===" -ForegroundColor Cyan
Write-Host "Version: $root" -ForegroundColor Cyan
Write-Host "Rust: 85+ tests PASS" -ForegroundColor Green
Write-Host "Go: 92+ tests PASS" -ForegroundColor Green
Write-Host "Python: 4 verifiers PASS" -ForegroundColor Green
Write-Host "MCP: 58 strokes PASS" -ForegroundColor Green
Write-Host "Agents: 40/40 enroll PASS" -ForegroundColor Green
Write-Host "Webapp: build + vet PASS" -ForegroundColor Green
Write-Host "Version: consistent PASS" -ForegroundColor Green
