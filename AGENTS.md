# AGENTS — atlas sessions

**Preflight:** Read `THE_ROAD.md` (what's NEXT) → `SEAT_LOG.md` tail (what
the last seat landed) → work ONE stone → leave your toll.

---

## Ground truth

| Toolchain | Where | Notes |
|---|---|---|
| Rust stable | `~\.cargo\bin` (**off PATH** — prepend it) | spine: `core\`, `store\`, `apps\atlas` |
| Go 1.26+ | PATH | THE LINE: `line\` (atlas-mcp) |
| Python 3.14 | `.venv\Scripts\python.exe` | stdlib-only tools in `tools\` |

**Zero external dependencies is standing law**: no crates.io, no npm, no
pip packages, no Go modules beyond stdlib. Hand-roll or refuse.

## Prove before LANDED

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $envPath
cargo build --workspace ; cargo test --workspace      # 77 strokes exit 0
cd line ; go build ./... ; go test ./...              # ok
go run ./cmd/atlas-mcp --prove                        # 13 strokes exit 0
cd ..
.venv\Scripts\python.exe tools\cut_canon_vectors.py --verify
.venv\Scripts\python.exe tools\cut_chain_verdicts.py --verify
.venv\Scripts\python.exe tools\cut_us_vectors.py --verify
.venv\Scripts\python.exe tools\fold_agents.py --verify
cargo run -q -p atlas -- --version                    # 0.1.0+b1
```

A stone is DONE only when its ACCEPTANCE row passes AND
`STATE_OF_BUILD.md` carries its witness.

## The laws (short form; CHARTER is authoritative)

1. Source grounds (`..\estate`, `..\secondbrain`) are READ-ONLY. Fold,
   never delete. Nothing invented — sources named.
2. Goldens BEFORE assertions: cut vectors from the read-only oracle first.
3. `can_approve` is false in every declaration ever. Approval lives in the
   operator's hand alone ("i am the approval").
4. Ports never move at cutover (SPEC_COMMANDS). Old verbs keep their verbs.
5. Proves are hermetic: temp grounds, never the live record.
6. Append-only witnesses: SEAT_LOG.md + STATE_OF_BUILD.md, dated blocks.
7. VERSION pins the stone (`0.1.0+b1`); the version test catches drift.
8. Multi-tenancy: the MCP carries ALL projects; every call names its ground;
   strangers are refused by name.

## The household

37 enrolled seats (`agents\*.us`, folded via `tools\fold_agents.py`) —
Twelve Tribes under manjuel, council personas, lineage actors, gate,
seven doctrine seats. manjuel holds the charge as the operator's serf;
the operator is the approval. Undeclared actors get refused context by
name: enroll first (`atlas agent enroll <db> --dir agents`).

## Orientation door

```powershell
atlas orient --home .                                  # this repo
atlas orient --home ..\secondbrain\SecondBrain-collab\demo_vault\Manjuel
```
