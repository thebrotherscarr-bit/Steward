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

## Prove before LANDED — ONE command

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo build -p atlas                    # the door battery shells this binary
python tests\prove.py                   # THE BALL: all eight legs, one verdict
python tests\prove.py --live            # + the legs needing :8090 and Ollama
```

THE BALL gathers every prover atlas has — the Rust spine, both Go modules,
the two shipped batteries, **twenty-seven** golden verifiers (this file used
to name four), the six workflows and the E2E suite. Read `tests/PROVING.md`
for the map.

It answers in **three** verdicts, not two. `ABSENT` means a leg named a
dependency this ground does not hold — the read-only source grounds
(`estate\`, `secondbrain\`) fourteen cutters were cut from, a binary not
built, a door not answering. ABSENT is never a pass and never a silent skip:
it prints the exact path that would answer it. Only `FAIL` exits red.

The legs also still run on their own:

```powershell
cargo test --workspace                                # 56 strokes
cd line ; go build ./... ; go test ./... ; cd ..
cd line ; go run ./cmd/atlas-mcp --prove ; cd ..      # 125 strokes exit 0
python tools\<any_cutter>.py --verify
cargo run -q -p atlas -- --version                    # 0.1.1+f1
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
