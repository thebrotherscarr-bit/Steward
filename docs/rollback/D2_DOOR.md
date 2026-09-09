# D2 Trade+Door — Rollback Fold Note

**Stone:** D2 (Go door :8080 + Rust trade verbs)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

`atlas-door --port 8080` replaces `python door.py --port 8080`. Same
port, same routes (/ page, /ask?q= search, /log POST visit, /work POST
work order). Badge truth proven. Crew forms sealed. Loopback-default
confirmed as doctrine.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| `python door.py --port 8080` | `atlas-door --port 8080` | Same port, same routes |
| `/` (page) | `/` (page) | Same |
| `/ask?q=...` (search) | `/ask?q=...` (search) | Same |
| `/log` (POST visit) | `/log` (POST visit) | Same |
| `/work` (POST work order) | `/work` (POST work order) | Same |
| Badge (green/red) | Badge (green/red) | Same semantics |
| `python door.py --prove` | `atlas-door --prove` | Same prove pattern |

**Port frozen:** 8080 (SPEC_COMMANDS: "ports do not move at cutover")

## Rollback

1. Stop `atlas-door` process (kill the Go binary on :8080)
2. Start `python door.py --port 8080` — it binds the same port
3. Trade ops ground (`state/ops/`) is shared SQLite — Python reads it
4. No data loss — the ops ground is the shared state

**Fold action:** Write a dated fold note. Stop Go binary, start Python
on the same port.

## Verification

`atl gm run --stone D2` → 3/3 strokes green (trade cutter + cargo + go tests)
