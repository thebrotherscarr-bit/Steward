# D1 Town — Rollback Fold Note

**Stone:** D1 (Go town + beat/flow/story/look)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

`atlas-town` replaces `python town.py` for beat/flow/story/look/prove.
The beat posts REVIEW-gated trade tasks to the same board files
(tasks.jsonl + worked.jsonl). No auto-approve path exists by construction.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| `python town.py beat` | `atlas-town beat` | Same verb, same board files |
| `python town.py flow [a b]` | `atlas-town flow [min max]` | Same verb, same jitter semantics |
| `python town.py story [h]` | `atlas-town story [hours]` | Same verb |
| `python town.py look` | `atlas-town look` | Same verb |
| `python town.py prove` | `atlas-town --prove` | Same prove pattern |

**No port** — town is a CLI tool, not a server. It runs on-demand.

## Rollback

1. `atlas-town` is a CLI — no long-lived process to stop
2. Board files (`tasks.jsonl`, `worked.jsonl`) are shared — Python town.py
   reads the same files
3. If `atlas-town beat` has written tasks, `python town.py beat` will see
   them and respect their REVIEW status
4. No data loss — the board files are the shared state

**Fold action:** None required. The Go binary is additive.

## Verification

`atl gm run --stone D1` → 3/3 strokes green (town cutter + go tests)
