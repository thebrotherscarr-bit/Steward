# PROVING — how atlas is proven, and where it isn't

*Written 2026-09-10. The map for `tests/prove.py` — THE BALL. If you change
what proves atlas, change this file in the same hand.*

atlas proves itself in **eight places**. They had never been gathered into
one command, and two of the eight had been quietly red for weeks because
nothing ran them. `python tests/prove.py` runs all eight and gives one
verdict.

```
python tests/prove.py          the hermetic legs — no server, no model
python tests/prove.py --check  the fast legs — skips cargo
python tests/prove.py --live   adds the legs that need :8090 and Ollama
python tests/prove.py --quiet  one line per leg
```

---

## Three verdicts, not two

This is the part that matters. A leg is **PASS**, **FAIL**, or **ABSENT**.

**ABSENT** means the leg named a dependency this ground does not hold — a
read-only source ground that was never copied in, a binary not yet built, a
door not answering. ABSENT is never counted as a pass and never silently
skipped. It prints with the exact path or command that would answer it, and
it does **not** set a red exit, because nothing is broken — something is
missing, and the difference is the whole point.

Only a **FAIL** sets a red exit. That is the discipline the rest of atlas
already holds (`prove refused: no working atlas binary behind "atlas"` —
the door battery has always refused by name rather than fabricate). THE
BALL just makes every leg answer the same way.

---

## The oracle ground, and why 14 legs are ABSENT on a fresh clone

**The goldens travel. The cutters do not.** Every golden in
`tests/fixtures/` is committed, and the Rust implementation is proved against
them on any machine. What needs the oracle is the RE-CUT — the leg that asks
whether the golden still matches the reference implementation it was cut from.
Those references live in a private ground that does not ship and never will
(CLAUDE.md RULE 1: the Archive never goes on GitHub, ever).

So on a fresh clone those 14 legs report **ABSENT**, and that is correct. They
are not failures and they are not skips — the battery says what it could not
ask and refuses to count it as an answer.

**Set `ATLAS_ORACLE_ROOT`** to the ground holding the oracles and they run:

    $env:ATLAS_ORACLE_ROOT = "<the ground with estate\ and secondbrain\>"
    python tests\prove.py --check

Unset, the cutters still try their historical location, so nothing that
worked stops working.

**This was wrong until 2026-09-11.** Every cutter computed its oracle root as
`ATLAS.parent`. Before the 2026-09-10 split that was true — atlas sat beside
the grounds it was folded from. After the split the parent is the manjuel
core, so the legs reported ABSENT naming paths that **have never existed on
any machine**. Right verdict, phantom reason, and nothing a reader could act
on. ADR-006 item 6.

## The eight legs

| # | Leg | What it proves | Costs | Needs |
|---|---|---|---|---|
| 1 | **TOOLCHAIN** | rust, go, python, and the built `atlas` binary are here | instant | — |
| 2 | **SPINE** — `cargo test --workspace` | the Rust core: sha256, canon, chain verdicts, covenant, merkle, store, `.us` grammar | ~1s | one stroke wants the read-only oracle |
| 3 | **LINE** — `go build`/`go test` in `line/` | THE LINE: 15 packages with provers | ~5s | `target/debug/atlas` for the door battery |
| 4 | **GLASS** — `go build`/`go test` in `webapp/` | the face: 1 package with a prover | ~2s | — |
| 5 | **BATTERY** — `atlas-mcp --prove` | 125 strokes over temp grounds and loopback — the shipped battery inside the binary | ~2s | — |
| 6 | **GOLDENS** — 27 × `--verify` | law 2: every vector re-cut and compared against the pinned fixture | ~4s | 14 of them want an oracle not in this ground |
| 7 | **WORKFLOWS** — 6 × `wf_*.py` | the seat journeys end to end through the live door | minutes | `:8090` answering |
| 8 | **E2E** — `test_suite.py` | 84 scenarios in 12 categories | minutes | `:8090` + Ollama on `:11434` |

The **door battery** is not a ninth leg — it lives *inside* leg 3, as
`TestDoorProveStrokesGreen` in `cmd/atlas-door`. It shells the Rust binary
over a real loopback socket against a temp book: phone-form writes, the
badge going red on a flipped byte, a wrong path refused. It is the reason
leg 3 needs `cargo build -p atlas` first.

---

## Where atlas stands right now

```
22 held · 15 absent · 0 broke
```

**Nothing is broken.** Every absence is one of two kinds:

### The source grounds are gone (14 verifiers + 1 Rust stroke)

Fourteen cutters and one Rust stroke were cut from read-only oracles that
do not exist in this ground:

| Missing oracle | Verifiers it silences |
|---|---|
| `estate/Neiro/lib/us_read.py` | `cut_us_vectors`, `fold_agents` |
| `estate/Neiro/lib/us_canon.py` | `cut_canon_vectors` |
| `estate/Neiro/lib/us_chain.py` | `cut_chain_verdicts` |
| `estate/Neiro/Archive/neiro/digest.py` | `cut_digest_vectors` |
| `estate/Neiro/Archive/neiro/gatehouse.py` | `cut_guard_vectors` |
| `estate/Neiro/Archive/neiro/predictor.py` | `cut_predict_vectors` |
| `estate/forge/links/jesster.py` | `cut_faces_vectors`, `cut_jesster_vectors`, `cut_schnorr_vectors` |
| `estate/Steward 1.0/skills/property.py` | `cut_trade_vectors`, `check_trade_parity` |
| `estate/Steward 1.0/trade_tasks.py` | `cut_town_vectors` |
| `secondbrain/…/manjuel5/models.py` | `cut_ppmi_vectors` |
| `estate/Agents/.us/Agents.us` + 3 more | `us_parity::every_declaration_file_meets_the_oracle_bytes` |

**The goldens themselves are all here and green.** What is gone is the
ability to *re-cut* them and to notice the source drifting. The other three
strokes of `us_parity` run entirely on the vectors and pass. So the
contracts are still proven; only the tie back to the original source is
cut.

This is a ruling for the operator, not a bug to work around. Either the
source grounds come back (read-only, per law 1), or these fourteen get
formally retired with their goldens frozen as the authority. Inventing
substitutes would break law 2 outright.

### The live legs need a running system (7 legs)

`--live` needs `atlas-mcp` on `:8090`, and the E2E suite also needs Ollama.
Without them the legs report ABSENT with the command that would fix it —
never a pass.

---

## The real gap: 16 packages carry no prover

`go test ./...` says `[no test files]` sixteen times. That is not an absence
— it is untested code.

**`internal/tools` came off this list on 2026-09-10**, and is now the
best-covered package in THE LINE with **34 strokes**:

- `gitctl_test.go` (19) — the wall's one-level-up reading and its bound, branch
  names that would become flags, path jailing, credential-free remote hosts,
  saves that refuse without a message, sending and fetching that refuse by name
  through a shut wall, and a line of work that refuses to be closed while it
  holds work found nowhere else.
- `tools_test.go` (15) — the three READERS, where a quiet wrong answer does the
  most damage: `records` sorting by what a document is and keeping the law above
  the seats, law marked sealed, **a name matched against the listing and never
  joined onto a path** (so `../.env` is not defended against — it simply is not
  in the list), only markdown served, the sha256 receipt matching the bytes;
  `proofs` folding a closing sitting line over its opening one, surviving the
  half-written last line a killed process leaves, and naming the counts the core
  owns rather than recounting them; `seats` reading whatever fields a
  declaration carries rather than a schema that would drift.

Every one is hermetic: its own ground in `t.TempDir()`, nothing touching the
record, no network.

**`runstream.go` is still uncovered, deliberately.** `RunStream`, `AnswerStream`
and `ListenStream` all need a live engine on an open sitting, which is not a
thing a hermetic stroke can stand up. A mock there would prove the mock.

**THE LINE (8):**

| Package | Why it matters |
|---|---|
| `internal/tenant` | the multi-tenancy law (law 8): every call names its ground, strangers refused by name |
| `internal/rbac` | who may do what |
| `internal/protocol` | the wire shape |
| `internal/httpserver` | 4 source files serving the door |
| `internal/ground` | the ground resolver |
| `internal/orient` | the orientation pack |
| `internal/vc` / `cmd/atlas-vc` | version control |

**THE GLASS (8):** `webapp`, `agents`, `db`, `evals`, `messaging`,
`search`, `server`, `traces` — only `handlers` has a prover.

Ranked by what would hurt most if it broke silently:
1. `internal/tenant` — a leak here crosses projects
2. `internal/rbac` — a leak here crosses permissions
3. `webapp/db` — the face's persistence
4. the rest

`internal/tools` now covers its git verbs and all three readers. What is left
there is `runstream.go` (needs a live engine) and the bulk of `tools.go`'s own
handlers — though the registry contract itself is now pinned: a tool that
writes must declare it, which is the flag the read-only table refuses by.

---

## The workflows (leg 7)

Six seat journeys in `tests/workflows/`, each driving the live door over
JSON-RPC through `_mcp_client.py`. They are not unit tests; they are the
question *"can a seat actually do its job today?"*

| Workflow | The journey | Writes? |
|---|---|---|
| `wf_scout` | read-only survey — `get_in_line`, `muster`, `read_handoffs`, `state_matrix`, `tenant_list` | no |
| `wf_town` | scheduling — folds the record, remembers a work order, verifies a chain | yes |
| `wf_steward` | asks a voice, records the testimony, verifies the chain holds after | yes |
| `wf_gate` | the guard: prompt injection blocked, PII stripped, zero-width characters survived, the wall refuses a path outside the ground | no |
| `wf_mesh` | enrols two actors, posts plain and sealed, walks the chain, reads both ways | yes |
| `wf_operator` | the full lifecycle — all of the above plus a release post to `releases` | yes |

Each exits `0` green, `1` red, `3` door-not-answering. THE BALL reads that
`3` and reports ABSENT, not FAIL.

---

## What changed on 2026-09-10

Three things were wrong. All three are closed.

1. **`internal/rack` had been red since the repo split.** Four strokes
   wanted `tests/fixtures/rack_open_ground/state/rack_ledger.jsonl`. Git
   does not track empty directories, so the fixture ground came over empty
   in the H0 pull and nothing said so. Rebuilt — and the right fix was not
   a hand-written file but *running its own cutter*,
   `tools/cut_rack_open_vectors.py`, which builds that ground by
   definition. The five tracked goldens then judged it byte-exact.

2. **`TestDoorProveStrokesGreen` had nothing to shell.** The Rust binary
   was never built in this ground. `cargo build -p atlas`. The prover was
   behaving correctly the whole time — refusing by name.

3. **`cut_flow_vectors.py` was behind its own fixture.** Commit `ce9c390`
   added the `run` node kind to the flow contract and updated the Go code
   *and* the fixture — but not the cutter that owns the fixture. So
   `--verify` had been red since, and worse: running the cutter **without**
   `--verify` would have overwritten `flow_vectors.json`, stripped `run`
   back out, and turned `internal/flow` red with no obvious cause. The
   cutter now carries the seven-kind contract and refuses a `run` node with
   no objective, exactly as `flow.go` does. A full re-cut is now a no-op.

The lesson under all three: **a prover nobody runs is not a prover.**
AGENTS.md named four verifiers; there are twenty-seven. That is why THE
BALL exists.

---

## What `--live` found the first time it was run

`25 held · 15 absent · 4 broke`. The four are two root causes, and **neither
is a broken test** — both are the system telling the truth about itself.

### The live door could not reach the Rust spine (3 reds) — FIXED IN THE LAUNCH

`wf_town`, `wf_steward` and `wf_operator` all failed on the same step:

```
verify_chain: FAIL — exec: "atlas": executable file not found in %PATH%
```

`line/cmd/atlas-mcp/main.go:54` defaults `--atlas-bin` to the bare string
`"atlas"`. The door's own `findAtlas()` (`cmd/atlas-door/door.go:33`) walks
up to four levels looking for `target/debug/atlas`, and falls back to
`ATLAS_BIN` and `PATH` before that. **THE LINE does neither.** So unless the
launch passes `--atlas-bin`, every tool that shells the spine refuses.

The door was relaunched with `--atlas-bin` and `verify_chain` now answers
`verdict=INTACT`. `tests/e2e/_start_mcp.ps1` carries the flag too, with the
reason written beside it.

**The code default is still a trap**, and that part is a ruling, not a patch:
either `atlas-mcp` grows the same built-tree walk `atlas-door` already has —
one small function, and the two binaries stop disagreeing — or every launch
recipe must remember the flag forever. RUNBOOK's own start line still does
not carry it.

### E2E layer 7 tests a directory that no longer exists (1 red)

`tests/e2e/test_suite.py:583` looks for `kernels/prove.py`. There is no
`kernels/` in atlas — E1 Kernels is COMPLETE and the C++ kernels were
ported to Rust (`libppmi`, per THE_ROAD). The layer is a fossil of the
pre-port tree and has been failing ever since the port landed. It should be
retired or repointed at the Rust bench.

### Two flaws in the workflows themselves

1. **They pass on refusals.** Every step checks `lambda r: len(r) > 0`, so
   a refusal counts as a pass. `wf_town`'s `remember` step reported PASS on
   `rbac: agent "town" (role "guest") denied tool "remember"`. A workflow
   that goes green when the system refuses it is not proving anything.

2. **They write to the live record**, which breaks law 5 (*proves are
   hermetic: temp grounds, never the live record*). One `--live` run
   appended five real `rack_ask` lines to `state/rack_ledger.jsonl` and
   posted to the mesh. Every other leg of THE BALL is hermetic; leg 7 is
   not. It should run against a temp home the way the door and MCP
   batteries already do.

---

## What it needs next, ranked

1. **`atlas-mcp` must find the spine the way the door does.** Three of the
   six workflows are red on it today, and every chain verification through
   THE LINE is dead until it is answered. One small function, or a launch
   flag — the operator's call which.
2. **A ruling on the fourteen absent oracles.** Restore the source grounds
   read-only, or formally retire those cutters with the goldens frozen as
   the authority. Until then atlas cannot detect source drift in a third of
   its contracts.
3. **The workflows must assert, not just receive.** `len(r) > 0` passes on
   refusals. Each step needs to name what a right answer looks like — the
   way `wf_town`'s `verify_chain` step already does with `"INTACT" in r`.
4. **The workflows must run hermetic.** Leg 7 is the only leg that writes to
   the live record. Give it a temp home like the batteries have.
5. **Strokes for `internal/tools`.** Six files, every tool handler, zero
   coverage. Start with the wall: a path outside the tenant home must be
   refused by name.
6. **Strokes for `internal/tenant` and `internal/rbac`.** Law 8 has no
   prover of its own.
7. **Retire or repoint E2E layer 7.** It tests `kernels/`, which the Rust
   port replaced.
8. **`cut_flow_vectors` should also pin the eval-ref refusal.** `flow.go`
   refuses an `eval` node that names no node to check; the cutter's oracle
   does not test that case. One more refusal vector closes it.
9. **Wire THE BALL into the gate.** `prove.py --check` belongs in whatever
   runs before a commit lands, so a red leg is caught by the machine rather
   than by a seat happening to look.
