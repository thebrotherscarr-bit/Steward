# Start the door for the E2E suite.
#
# THIS SCRIPT POINTED AT THE WRONG TREE. Until 2026-09-10 all three of its
# lines named C:\Users\novad\Desktop\Archive\atlas -- the pre-split copy. That
# is outside the ground RULE 1 fences, it is not the tree anyone edits, and a
# suite started against it would have proven a repository nobody was changing.
# Every path is now derived from this file's own location, so it follows the
# repository instead of one machine's history. (RUNBOOK's lesson, same day:
# a hard-coded home "worked on exactly one machine and pointed at nothing on
# any other.")
#
# --atlas-bin IS NOT OPTIONAL. THE LINE defaults it to the bare string "atlas"
# and does no built-tree lookup the way atlas-door does, so without this flag
# every tool that shells the Rust spine -- verify_chain among them -- refuses
# with `exec: "atlas": executable file not found in %PATH%`. That is exactly
# what put three of the six workflows in the red on 2026-09-10.

$ErrorActionPreference = "Stop"

$atlas = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$spine = Join-Path $atlas "target\debug\atlas.exe"

if (-not (Test-Path $spine)) {
    Write-Host "Refused: the Rust spine is not built at $spine" -ForegroundColor Red
    Write-Host "  Build it first:  cargo build -p atlas" -ForegroundColor Yellow
    exit 1
}

$env:Path = "$(Join-Path $atlas 'target\debug');$env:USERPROFILE\.cargo\bin;$env:Path"
Set-Location (Join-Path $atlas "line")
go run ./cmd/atlas-mcp --http 127.0.0.1:8090 --atlas-bin "$spine"
