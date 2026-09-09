# C1 Faces — Rollback Fold Note

**Stone:** C1 (TypeScript faces + atl toolchain)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

`atl faces serve` replaces `python aurora/server.py` on loopback for
serving the console face. The console.html and sprites.js are vendored
byte-verbatim from the Aurora oracle. `atl faces check` proves parity.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| `python aurora/server.py` (:7788) | `atl faces serve` (loopback, port 0) | Same bytes, different port (atl defaults to random) |
| console.html + sprites.js served | Vendored byte-verbatim | Oracle sha-pinned |

**Note:** The Aurora server (`server.py :7788`) serves the full Aurora
UI. `atl faces serve` serves only the console face on loopback. These
are complementary during strangler, not a full replacement. The full
Aurora cutover is G8 (atlas-glass), which is a future stone.

## Rollback

1. Stop `atl faces serve` (Ctrl+C or kill the process)
2. Aurora `server.py` still runs on :7788 — no action needed
3. `atl faces check` continues to verify byte parity
4. No data loss — the face is stateless

**Fold action:** None required. `atl faces serve` is additive.

## Verification

`atl gm run --stone C1` → 2/2 strokes green (faces cutter + atl self-test)
