# F1 Harvest — Rollback Fold Note

**Stone:** F1 (rack trio + envelopes + guard + skill lint)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

The rack tools (`rack_list`, `rack_ask`, `rack_open`, `memory`) are
wired into the MCP (THE LINE) and route to local Ollama on loopback.
The guard pipeline (block/redact/scan) is wired into `rack_ask`. These
replace any manual Ollama curling with cited, guarded answers.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| Manual `curl localhost:11434/api/tags` | `rack_list` via MCP | Same Ollama, same loopback |
| Manual `curl localhost:11434/api/generate` | `rack_ask` via MCP | Same Ollama, guarded |
| No envelope API | `memory` via MCP | New capability (cited answers) |

**Port:** Ollama stays on :11434 (loopback). Rack tools are MCP tools,
not servers — they route through the MCP door.

## Rollback

1. `rack_list`, `rack_ask`, `rack_open`, `memory` are MCP tools — they
   stop when the MCP is stopped or re-pointed to the old MCP
2. Ollama continues running on :11434 — no action needed
3. `rack_ask` falls back to honest refusal when Ollama is unreachable
4. The guard pipeline is wired into `rack_ask` — disabling it is a
   config change, not a code change
5. No data loss — the rack is stateless; the ledger is append-only

**Fold action:** Re-point `.mcp.json` to the old MCP (B1 rollback).
Rack tools become unavailable through the MCP but Ollama remains
accessible directly.

## Verification

`atl gm run --stone F1` → 8/8 strokes green (6 cutters + go tests + atl self-test)
