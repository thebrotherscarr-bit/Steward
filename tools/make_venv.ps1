# make_venv.ps1 -- create/recreate atlas\.venv from pinned requirements.
# Idempotent; safe to re-run. Never touches any system interpreter state
# beyond creating this project venv (CHARTER section 6).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"

if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    python -m venv $venv
    if (-not $?) { throw "venv creation failed" }
}

$pip = Join-Path $venv "Scripts\python.exe"
& $pip -m pip install --upgrade pip --quiet
$req = Join-Path $PSScriptRoot "requirements.txt"
& $pip -m pip install -r $req --quiet
& $pip --version
& $pip -c "import sys; print('venv ready:', sys.executable)"
