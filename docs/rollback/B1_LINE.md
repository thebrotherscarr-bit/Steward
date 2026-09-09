# B1 THE LINE — Rollback Fold Note

**Stone:** B1 (Go MCP, multi-tenant)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

`atlas-mcp` replaces `seat_mcp.py` (steward-line MCP) and `us_mcp.py`
(Agents/Neiro MCP) as the single MCP door. The `.mcp.json` file is
re-pointed from `seat_mcp.py` to `atlas-mcp --home "Steward 1.0"`.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| `.mcp.json` → `seat_mcp.py` | `.mcp.json` → `atlas-mcp --home "Steward 1.0"` | Same JSON-RPC protocol, same tool names |
| `us_mcp.py --home .` | `atlas-mcp --home <module>` | Same protocol, multi-tenant |
| Protocol: newline JSON-RPC 2025-06-18 | Same protocol | Exact match |

## Rollback

1. Stop `atlas-mcp` process (if running as a long-lived server)
2. Re-point `.mcp.json` back to `seat_mcp.py`:
   ```json
   { "command": "python", "args": ["seat_mcp.py", "--home", "Steward 1.0"] }
   ```
3. `us_mcp.py` remains available for Agents/Neiro single-seat usage
4. No data loss — the MCP is stateless; the record lives in SQLite + JSONL

**Fold action:** Write a dated fold note in `.mcp.json` comments.
Re-point, don't delete `atlas-mcp`.

## Verification

`atl gm run --stone B1` → 1/1 stroke green (go test ./...)
