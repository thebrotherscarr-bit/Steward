<#
.SYNOPSIS
  Runs eval sets for their bar: each set as its own process, one after another, with a log and a progress file.

.DESCRIPTION
  For each set named in -Sets (a set file's name in harness/steward/evals/, e.g. small, steps, heldout), runs
  `evals.py <set>` -Runs times, each run its own process (Start-Job), waiting for it before the next: one model at a
  time. Each run's output goes to a UTF-8 log under storage/evals/runs/<Tag>/ (gitignored), and progress.txt there
  gets a line as each run starts and ends. After each run, one summary line is read from storage/evals/history.jsonl
  (the line the run appended). At the end, `evals.py bar <set>` says for each set whether its bar is met, and the last
  line is "BAR DONE". A run is stopped after -RunMinutes.

.EXAMPLE
  powershell -File harness/steward/evals/run-bar.ps1 -Sets small,heldout -Tag nightly
#>
param(
    [Parameter(Mandatory = $true)][string[]]$Sets,
    [Parameter(Mandatory = $true)][string]$Tag,
    [int]$Runs = 2,
    [int]$RunMinutes = 60
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$evals = Join-Path $repo 'harness\steward\step04_production_ready\evals.py'
$history = Join-Path $repo 'storage\evals\history.jsonl'
$Sets = @($Sets | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($Tag -notmatch '^[\w.-]+$') { throw "Tag '$Tag' must be letters, digits, '.', '-' or '_'." }
$folder = Join-Path $repo "storage\evals\runs\$Tag"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$progress = Join-Path $folder 'progress.txt'
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Say([string]$line) {
    $stamped = "$(Get-Date -Format s) $line"
    [System.IO.File]::AppendAllText($progress, "$stamped`r`n", $utf8)
    Write-Output $stamped
}

function Last-HistoryLine([string]$set) {
    if (-not (Test-Path $history)) { return $null }
    $lines = [System.IO.File]::ReadAllLines($history, $utf8)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        try { $run = $lines[$i] | ConvertFrom-Json } catch { continue }
        if ($run.set -eq $set) { return $run }
    }
    return $null
}

$valid = & $python -W ignore $evals validate 2>&1
if ($LASTEXITCODE -ne 0) { Say "validate failed: $($valid -join ' | ')"; Say 'BAR DONE'; exit 1 }
Say "bar $Tag : sets $($Sets -join ', '), $Runs run(s) each"

foreach ($set in $Sets) {
    for ($n = 1; $n -le $Runs; $n++) {
        $log = Join-Path $folder "$set-$n.log"
        $before = Last-HistoryLine $set
        Say "start $set run $n -> $log"
        $job = Start-Job -ScriptBlock {
            param($python, $evals, $set, $repo)
            Set-Location $repo
            $env:PYTHONIOENCODING = 'utf-8'
            & $python -W ignore $evals $set 2>&1 | ForEach-Object { "$_" }
            "EXIT $LASTEXITCODE"
        } -ArgumentList $python, $evals, $set, $repo
        $finished = Wait-Job $job -Timeout ($RunMinutes * 60)
        if (-not $finished) { Stop-Job $job; Say "stopped $set run $n after $RunMinutes min" }
        $output = Receive-Job $job
        Remove-Job $job -Force
        [System.IO.File]::WriteAllLines($log, [string[]]@($output), $utf8)
        $after = Last-HistoryLine $set
        if ($after -and (-not $before -or $after.ts -ne $before.ts)) {
            Say ("done  {0} v{1} ({2}) run {3}: {4}/{5} cases, {6}/{7} checks, exit {8}, head {9}" -f `
                $set, $after.set_version, $after.tier, $n, $after.passed, $after.total, $after.checks_passed, `
                $after.checks_total, $after.exit_code, $after.git_head)
        } else {
            Say "done  $set run $n : no history line written (see $log)"
        }
    }
}

foreach ($set in $Sets) { Say ((& $python -W ignore $evals bar $set 2>&1) -join ' ') }
Say 'BAR DONE'
