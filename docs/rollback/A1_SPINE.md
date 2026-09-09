# A1 Spine — Rollback Fold Note

**Stone:** A1 (Rust core + store)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

The Rust spine (`atlas` binary) is additive — it provides `chain verify`,
`chain recognize`, `db init/import/export/status`, `agent enroll`, `orient`,
`trade`, `link lay/status`, and now `--prove`. It does NOT replace any
running process. The Python provers (`prove_parity.py`, `us_chain.py`,
`us_canon.py`, `us_read.py`) remain authoritative during the strangler.

## Rollback

No process to stop. The Rust spine is a CLI tool invoked by the MCP and
the `atl` toolchain. If the Rust spine is removed:

1. `atlas chain verify` / `atlas chain recognize` become unavailable
2. `atlas db init/import/export/status` become unavailable
3. `atlas agent enroll` / `atlas orient` become unavailable
4. `atlas trade` / `atlas link` become unavailable
5. The Go MCP (`atlas-mcp`) falls back to honest refusal on `verify_chain`
6. Python provers continue to work independently

**Fold action:** None required. The Rust spine is a tool, not a service.
If it must be retired, remove `apps/atlas/` and re-build the workspace.
The fixture files in `tests/fixtures/` and the cutter tools in `tools/`
are shared and stay.

## Verification

`atl gm run --stone A1` → 8/8 strokes green (cutters + cargo tests)
