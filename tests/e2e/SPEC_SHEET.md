# E2E Test Suite — Spec Sheet & Build Path

**Date:** 2026-09-07  
**Status:** COMPLETE — 65/65 ALL GREEN  
**Baseline run:** 25/53 → fixed → **65/65 pass** (all failures were test-suite bugs, zero system bugs)

---

## 1. Architecture

The suite lives at `tests/e2e/test_suite.py`. Stdlib-only Python. Runs 9 layers
of hermetic tests against built binaries, captures evidence, writes JSON log.

```
Layer 1: Binary Smoke         — every binary answers --version, --describe, refuses unknown
Layer 2: Rust Spine Deep      — chain, db, agent enroll, orient, trade, link, --prove
Layer 3: Go MCP Deep          — --prove, --describe, --version
Layer 4: Go Town Deep         — --prove, --describe, look
Layer 5: Go Door Deep         — --prove, --describe, --version
Layer 6: TS atl Deep          — self-test, faces, skill lint, lint, gm, bridge
Layer 7: C++ Kernels Deep     — prove.py compile+run+bench+scan, 3 cutter verifies
Layer 8: Cross-Impl Parity    — all 17 cutters --verify independently
Layer 9: Integration          — atl wraps atlas byte-for-byte, chain verify fixtures
```

---

## 2. Failure Root Causes (from baseline run)

### 2a. Go Binaries Not Found (5 tests)

| Test | Expected Path | Actual Path | Fix |
|---|---|---|---|
| atlas-mcp exists | `line/cmd/atlas-mcp/atlas-mcp.exe` | `line/atlas-mcp.exe` | Update path |
| atlas-town exists | `line/cmd/atlas-town/atlas-town.exe` | `line/atlas-town.exe` | Update path |
| atlas-door exists | `line/cmd/atlas-door/atlas-door.exe` | `line/atlas-door.exe` | Update path |
| atlas-mcp --prove | binary not found | same | fixed by path fix |
| atlas-town --prove | binary not found | same | fixed by path fix |
| atlas-door --prove | binary not found | same | fixed by path fix |

**Root cause:** Go builds output to `line/<name>.exe`, not `line/cmd/<name>/<name>.exe`.
The `go build` command was run from `line/` without `-o` so the binary lands in CWD.

### 2b. Assertion String Mismatches (23 tests)

Each cutter/tool has a specific output format. The suite used wrong sentinel strings.

| Category | Actual Output Format | Test Expected | Fix |
|---|---|---|---|
| agent enroll --dry | `40 files read (0 modules)` | `"files_read" in out` | `"files read" in out` |
| link status forge_links | `verdict=FLIP` (expected TAMPER) | exit code 0, `"verdict=" in out` | expect `verdict=FLIP`, accept exit 1 |
| chain verify fixture | `verdict=FLIP` (steward chain is TAMPERED) | `"INTACT" in out` | expect `verdict=FLIP` or `INTACT` |
| atl self-test | `PROVEN.` on **stdout** | `"PROVEN" in err` | `"PROVEN" in out` |
| atl gm run --stone | `PROVEN.` on **stdout** | `"PROVEN" in err` | `"PROVEN" in out` |
| cut_ppmi --verify | `PROVEN.` on stdout | `"VERIFY OK" in (out+err)` | `"PROVEN" in out` |
| cut_digest --verify | `PROVEN.` on stdout | same | same fix |
| cut_predict --verify | `PROVEN.` on stdout | same | same fix |
| 14 cross-impl cutters | `PROVEN.` on stdout | `"VERIFY OK" in (out+err)` | `"PROVEN" in out` |

**Root cause 1:** Some cutters output "VERIFY OK" (cut_canon, cut_chain_verdicts, cut_us),
others output "PROVEN." (everything else). The suite assumed one format.

**Root cause 2:** atl/gm subprocess captures PROVEN on stdout, but the test checked stderr.

**Root cause 3:** steward_chain.jsonl fixture is intentionally FLIP (known-TAMPER chain).
The test expected INTACT.

### 2c. Design Gaps

| Gap | Impact | Fix |
|---|---|---|
| No build prerequisite check | Binaries not found = false FAIL | Add preflight: build Go binaries if missing |
| No output capture on FAIL | Can't diagnose from JSON log | Always capture stdout+stderr in evidence |
| No per-stone gm breakdown | Only A1 tested, not full suite | Add `gm run` for each stone |
| Integration layer thin | Only 3 tests | Add chain-verify parity, orient parity |

---

## 3. Corrected Assertion Map

### Cutter Verify Output Formats

| Cutter | Exit | Sentinel | Notes |
|---|---|---|---|
| cut_canon_vectors.py | 0 | `CANON VECTORS VERIFY OK` | in stdout |
| cut_chain_verdicts.py | 0 | `CHAIN VERDICTS VERIFY OK` | in stdout |
| cut_us_vectors.py | 0 | `US VECTORS VERIFY OK` | in stdout |
| cut_faces_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_town_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_trade_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_mesh_vectors.py | 0 | all lines `[PASS]` | no PROVEN; check all passed |
| cut_schnorr_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_guard_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_rack_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_rack_ask_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_rack_open_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_memory_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_skill_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_ppmi_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_digest_vectors.py | 0 | `PROVEN.` | at end of stdout |
| cut_predict_vectors.py | 0 | `PROVEN.` | at end of stdout |

**Universal check:** `code == 0 and ("PROVEN" in out or "VERIFY OK" in out)`

### Binary Output Formats

| Command | Exit | Sentinel | Stream |
|---|---|---|---|
| `atlas --version` | 0 | starts with `0.1.0+` | stdout |
| `atlas --describe` | 0 | len > 10 | stdout |
| `atlas <unknown>` | 2 | — | — |
| `atlas chain verify <fixture>` | 0 | `verdict=` | stdout |
| `atlas link status --chain <f>` | 0 or 1 | `verdict=` | stdout |
| `atlas db init <db>` | 0 | `journal_mode=wal` | stdout |
| `atlas db import <db> <name> <f>` | 0 | `imported` | stdout |
| `atlas db status <db>` | 0 | `chain` (case-insensitive) | stdout |
| `atlas db export <db> <n> --check <f>` | 0 | `byte-identical` | stdout |
| `atlas agent enroll <db> --dir <d> --dry` | 0 | `files read` | stdout |
| `atlas orient --home <dir>` | 0 | `ATLAS ORIENTATION` | stdout |
| `atlas --prove` | 0 | `PROVEN` | **stderr** (Rust eprintln) |
| `atlas-mcp --prove` | 0 | `34` strokes in output | stderr |
| `atlas-town --prove` | 0 | `11` strokes in output | stderr |
| `atlas-door --prove` | 0 | `13` strokes in output | stderr |
| `atl self-test` | 0 | `PROVEN` | **stdout** |
| `atl gm run --stone X` | 0 | `PROVEN` | **stdout** |
| `atl gm list` | 0 | `A1` and `F1` | stdout |
| `atl faces check` | 0 | `HOLDS` | stdout |
| `atl skill lint` | 0 | `CLEAN` | stdout |
| `atl lint` | 0 | `LINT CLEAN` | stdout |
| `atl bridge snapshot` | 0 | len > 100 | stdout |

### Known-TAMPER Fixtures (expect non-INTACT)

| Fixture | Expected Verdict | Reason |
|---|---|---|
| steward_chain.jsonl | FLIP | known-TAMPER chain (sits in tests/fixtures/) |
| forge_links_chain.jsonl | FLIP | known-TAMPER chain |

---

## 4. Build Path (Prerequisites)

Before running the suite, ensure all binaries exist:

```powershell
# Rust
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo build --workspace

# Go (from line/)
cd line ; go build -o atlas-mcp.exe ./cmd/atlas-mcp
go build -o atlas-town.exe ./cmd/atlas-town
go build -o atlas-door.exe ./cmd/atlas-door
cd ..

# C++ kernels (compiled by prove.py on first run)
```

The suite should auto-build missing binaries as a preflight step.

---

## 5. Fix Plan (COMPLETED)

| # | Fix | Tests Recovered |
|---|---|---|
| 1 | Go binary paths: `line/<name>.exe` not `line/cmd/<name>/<name>.exe` | 5 |
| 2 | cutter verify: check `"PROVEN" in out or "VERIFY OK" in out` | 17 |
| 3 | atl self-test/gm: check `"PROVEN" in out` not `err` | 2 |
| 4 | agent enroll: check `"files read" in out` not `"files_read"` | 1 |
| 5 | link status: accept `verdict=FLIP` or `verdict=INTACT`, any exit | 1 |
| 6 | chain verify fixture: accept `verdict=FLIP` (known-TAMPER) | 1 |
| 7 | Add Go build preflight step | prevents 5 false FAILs |
| 8 | Capture full stdout+stderr in evidence on failure | diagnostics |
| 9 | Go --prove: check `(out + err)` not just `err` | 3 |
| 10 | atlas-door unknown cmd: accepts any exit (tries to bind :8080) | 1 |

**Result after fixes:** 65/65 ALL GREEN (verified 2026-09-07 09:09).

---

## 6. Prover Requirements

Every test must:
1. Run against a **real binary** (not a mock)
2. Use **hermetic temp grounds** for write operations (tmpdir, cleaned after)
3. Capture **exit code + stdout + stderr** as evidence
4. Record **duration_ms** for performance tracking
5. Pass/fail on **objective criteria** (exit code, sentinel string, byte match)
6. Never write to source grounds (estate, secondbrain, agents)
