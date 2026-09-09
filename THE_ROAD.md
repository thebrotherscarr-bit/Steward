# THE ROAD — ATLAS build path

*One NEXT at a time. A stone opens only when the previous one carries its
witness in STATE_OF_BUILD.md. Rows cite ACCEPTANCE.md.*

## Status snapshot (2026-09-08, sitting 83; cutover complete)

| Stone | State |
|---|---|
| P0 Groundwork | ✓ COMPLETE (docs, catalog seed, venv law) |
| A1 Spine | ✓ COMPLETE — sha256, canon, forms, chain verdicts, covenant, merkle, store, export (77 strokes) |
| A2 Registry | ✓ COMPLETE — .us grammar parity, 40 seats folded + enrolled, orientation pack (re-sealed sitting 13) |
| B1 THE LINE | ✓ COMPLETE — multi-tenant MCP; 16/19 tools real, manifest + engine wired; + zero-write guard (B1-05, 24 strokes at close) |
| B2 THE MESH | ✓ COMPLETE (gate passed sitting 15) — SPEC_US_MESH corrected + frozen; hand-rolled Go Schnorr with differential Py↔Go prove (9 goldens); mesh_enroll/post/read/chain/cite over THE LINE; deciphering ledger (env keys + salts); `--prove` 34 strokes exit 0; follow-ups named (registry cross-check, wrap closing, websocket) |
| C1 Faces | ✓ COMPLETE (gate passed sitting 16) — oracle face vendored byte-verbatim + flags loader; read-only bridge (golden byte-match); atl toolchain (wrap/serve/check/lint/self-test 9/9); VERSION 0.1.0+c1 |
| D1 Town | ✓ COMPLETE (gate passed sitting 17) — oracle decision goldens (4); atlas-town beat/flow/story/look/prove (11 strokes); REVIEW-only board; static no-approve check; VERSION 0.1.0+d1 |
| D2 Trade+Door | ✓ COMPLETE (gate passed sitting 18) — trade goldens (15) + books; Rust trade verbs + pyjson canon; atlas-door :8080 badge/forms (13 strokes); bidirectional parity; loopback-default CONFIRMED as doctrine; VERSION 0.1.0+d2 |
| E1 Kernels | ✓ COMPLETE (gate passed sitting 20) — libppmi 13/13 + diet bit-exact + foldall e2e via Rust pen + bench 51.5× + socket scan; Rust link lay/status + Merkle v1/v2; VERSION 0.1.0+e1 |
| F1 Harvest | ✓ COMPLETE (gate passed sitting 26) — rack trio awake + envelopes + guard + skill lint 9/9 CLEAN; VERSION 0.1.0+f1 |
| G Cutovers | ✓ COMPLETE (sitting 26) — Rust --prove (10 strokes) + @atl/gm (28/28 green) + Gx-02 port verified + Gx-03 rollback notes (7) |
| **Cutover** | **✓ FLIPPED (sitting 83)** — all 7 switches formally flipped per operator ruling "formally flip em" |

## All switches FLIPPED (2026-09-08)

| Switch | Port | Rollback |
|---|---|---|
| A1 Spine | binary | `docs/rollback/A1_SPINE.md` |
| B1 MCP | `:8090` | `docs/rollback/B1_LINE.md` |
| C1 Faces | vendored | `docs/rollback/C1_FACES.md` |
| D1 Town | binary | `docs/rollback/D1_TOWN.md` |
| D2 Door | `:8080` | `docs/rollback/D2_DOOR.md` |
| E1 Kernels | C++ | `docs/rollback/E1_KERNELS.md` |
| F1 Harvest | MCP | `docs/rollback/F1_HARVEST.md` |

Additional live: Webapp `:8091` · Ollama `:11434` · 112/112 E2E proven.

## PARKED (named, not forgotten)

- `atl --refresh` enrollment verb idea (updates propagate) — needs ruling
- gateway sqlite shards (R12/S7), remote manjuel.us ledger — deferred sources
- core stubs awaiting stones: schnorr/keys (A-later), merkle_dag, blanks,
  vault, fold, us-render CLI face
- estate ALIGNMENT.md interview pattern — harvest candidate for seat intake

## Standing workflow for every seat (how work happens here)

1. Orient: `atlas orient --home <project>` (or read AGENTS.md + this file).
2. Bank the operator's ruling in SEAT_LOG before touching anything.
3. Cut goldens from the read-only oracle BEFORE writing assertions.
4. Implement stdlib-only. Prove hermetic. Full suite green.
5. Witness in SEAT_LOG.md + STATE_OF_BUILD.md (dated, append-only).
6. Stop at review gates — they belong to the operator.
