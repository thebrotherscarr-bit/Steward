# PARITY PLAN — full build path and cross-language integrity

*Every seam, every parity point, every prove. This is the complete map
of what must hold for Atlas to ship with confidence.*

---

## 1. The Parity Thesis

Atlas is five languages bolted together by math. The hash chain is the
truth. Every language must agree on what the chain says. If Rust says
INTACT and Go says FLIP, someone is wrong — and we must know which one.

Parity is not "the port passes its own tests." Parity is "two independent
implementations of the same contract produce identical output on identical
input." The Python cutter is the oracle. Every other language must match it
byte-for-byte or name the divergence.

---

## 2. The Build Matrix

### 2.1 Language Inventory

| Language | What It Owns | Binaries | Build Command |
|---|---|---|---|
| **Rust** | Core: hash, canon, chain, schnorr, covenant, store, trade, link | `atlas.exe` | `cargo build --workspace` |
| **Go** | Services: MCP, town, door, mesh, rack | `atlas-mcp.exe`, `atlas-town.exe`, `atlas-door.exe` | `go build ./...` (from `line/`) |
| **C++** | Kernels: PPMI, digest, predictor, SHA-256 | `prove`, `foldall`, `bench` | `g++ -std=c++17 -O2` or MSVC |
| **TypeScript** | Toolchain: CLI, faces, skills, golden-master | `atl` (via node) | `tsc --strict --noEmit` |
| **Python** | Cutters, oracles, E2E suite, guard pipeline | 17 cutter scripts | `.venv/Scripts/python.exe` |

### 2.2 Version Pin

Every binary must answer `--version` with the content of `VERSION`:

```
0.1.0+f1
```

The CI pipeline enforces this. If any binary diverges, the build fails.

---

## 3. Internal Parity (Per-Language)

### 3.1 Rust Internal

| Check | Command | What It Proves |
|---|---|---|
| Unit tests | `cargo test --workspace` | 85+ tests across core + store + atlas |
| Canon parity | `cargo test -p atlas-core canon` | BODY_V 1/2/3, JCS UTF-16-be key order |
| Chain verdicts | `cargo test -p atlas-core chain` | INTACT/FLIP/TAMPER on fixtures |
| Schnorr | `cargo test -p atlas-core schnorr` | BIP-340 sign/verify |
| Covenant | `cargo test -p atlas-core covenant` | construction-A over foundation docs |
| Store lifecycle | `cargo test -p atlas-store` | WAL, journal_sync, idempotent seed |
| Enroll | `cargo test -p atlas-store -- enroll` | 40 agents, dry run, temp ground |
| Trade | `cargo test -p atlas-store -- trade` | pyjson canon, 4 grammars |
| Link | `cargo test -p atlas-store -- link` | lay/status, Merkle v1/v2 |
| Full prove | `atlas --prove` | 10 strokes, hermetic |

### 3.2 Go Internal

| Check | Command | What It Proves |
|---|---|---|
| Build | `go build ./...` | All three binaries compile |
| Vet | `go vet ./...` | Static analysis clean |
| Unit tests | `go test ./...` | 14 tests across 7 packages |
| MCP prove | `atlas-mcp --prove` | 34 strokes (tools, mesh, guard) |
| Town prove | `atlas-town --prove` | 11 strokes (beat, flow, story) |
| Door prove | `atlas-door --prove` | 13 strokes (badge, forms, search) |
| Schnorr | `go test ./internal/mesh/` | 9 golden vectors, differential |
| Rack | `go test ./internal/rack/` | 13 tests (list, ask, open, memory) |

### 3.3 C++ Internal

| Check | Command | What It Proves |
|---|---|---|
| Compile | `prove.py` (auto-compile) | Clean build, zero warnings |
| Unit strokes | `prove.py` (13 strokes) | PPMI parity, SHA-256, diet |
| Foldall e2e | `prove.py` (foldall stroke) | End-to-end meal folding |
| Bench | `prove.py` (bench strokes) | 8 answers + speedup ≥10× |
| Socket scan | `prove.py` (scan stroke) | Zero network includes |
| PPMI goldens | `cut_ppmi_vectors.py --verify` | 20 vectors byte-exact |
| Digest goldens | `cut_digest_vectors.py --verify` | Meal marks/vocab/vectors |
| Predict goldens | `cut_predict_vectors.py --verify` | 5 expects + 3 surprises |

### 3.4 TypeScript Internal

| Check | Command | What It Proves |
|---|---|---|
| Type check | `tsc --strict --noEmit` | Zero type errors |
| Lint | `atl lint` | All faces LINT CLEAN |
| Self-test | `atl self-test` | 11 strokes PROVEN |
| Faces check | `atl faces check` | Oracle bytes HOLDS |
| Skill lint | `atl skill lint` | 9/9 CLEAN |
| GM list | `atl gm list` | All stones registered |

### 3.5 Python Internal

| Check | Command | What It Proves |
|---|---|---|
| Cutter verify (×17) | `cut_*.py --verify` for each | Golden vectors match fresh cut |
| Fold agents | `fold_agents.py --verify` | 40 agents born canonical |
| E2E suite | `tests/e2e/test_suite.py` | 65 tests, 9 layers |

---

## 4. Cross-Language Parity (The Seams)

This is where Atlas lives or dies. Two implementations of the same
contract must produce identical output.

### 4.1 Rust ↔ Go: Chain Verification

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **Hash chain format** | `sha256(prev ‖ kind ‖ n ‖ payload)` | Go reads Rust-built chains; both agree on INTACT/FLIP/TAMPER |
| **Canonical JSON** | BODY_V 1/2/3, sorted keys, UTF-16-be | Go envelope.go reproduces Rust canon.rs output |
| **Schnorr signatures** | BIP-340 secp256k1 | Sign Py → verify Go; sign Go → verify Py (9 goldens) |
| **Chain entry format** | 5-key body + sig/pub outside | Both languages parse the same JSONL entries |
| **Merkle wrapping** | v1 (old) + v2 (current) | Both agree on root hash at n=40 boundary |

**Proven by:** `cut_schnorr_vectors.py --verify` (9 goldens), `cut_mesh_vectors.py --verify` (15 goldens), `check_trade_parity.py` (7 checks).

### 4.2 Rust ↔ Go: Trade Books

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **SQLite books** | property/workorder/inspection/report | Rust owns SQLite FFI; Go reads via JSONL mirror |
| **Property lookup** | `atlas trade property P-001` | Identical output shape and values |
| **Work order search** | Door search endpoint | Receipts match Rust export |
| **Report generation** | `atlas trade report WO-001` | File order, typed hashes |

**Proven by:** `cut_trade_vectors.py --verify` (15 goldens), `check_trade_parity.py` (7 checks, bidirectional).

### 4.3 Python → C++: Kernel Goldens

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **PPMI vectors** | Integer counts bit-exact, floats ≤1e-9 | C++ reproduce Python oracle output |
| **Diet/SHA-256** | FIPS 180-4, bit-exact | 5 implementations agree (OpenSSL ×2, CNG ×2, Rust) |
| **Generations** | MT19937 deterministic | C++ replicates Python's MT19937 byte-for-byte |
| **Foldall** | End-to-end meal folding | Records match, vectors worst diff = 0 |
| **Predictor** | 64-dim, seeded weights | 5 expects + 3 surprises from oracle |

**Proven by:** `cut_ppmi_vectors.py --verify`, `cut_digest_vectors.py --verify`, `cut_predict_vectors.py --verify`, `prove.py` (17 strokes).

### 4.4 Python → TypeScript: Face Goldens

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **Console bytes** | Oracle HTML vendored byte-verbatim | sha256 pinned, `atl faces check` confirms |
| **Bridge snapshot** | Read-only fold, canonical JSON | `atl bridge snapshot` matches cutter bytes |
| **Flags loader** | Injected on flags-on, absent off | Server behavior matches oracle |

**Proven by:** `cut_faces_vectors.py --verify`, `atl faces check`, `atl self-test`.

### 4.5 Python → TypeScript: GM Harness

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **Stone registration** | 7 stones (A1/B1/C1/D1/D2/E1/F1) | `atl gm list` shows all |
| **Cutter execution** | 17 cutters run in order | `atl gm run` produces PROVEN |
| **Byte comparison** | Output matches golden fixtures | SHA-256 hash comparison |

**Proven by:** `atl gm run` (28/28 strokes across 7 stones).

### 4.6 Python → Go: Town Decisions

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **Candidate keys** | Month key, slug, vendor fallback | Go reproduces Python oracle decisions |
| **Board state** | tasks.jsonl + worked.jsonl | REVIEW-only, append-only |
| **Dedup** | Approved task not re-posted | Both agree on open/closed |

**Proven by:** `cut_town_vectors.py --verify` (4 goldens).

### 4.7 Python → Go: Mesh Envelopes

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **Envelope format** | 5-key body, sha256(prev‖canon) | Go reproduces Python format |
| **Sealed commitment** | H(salt ‖ plaintext) | Salted, not H(ct) |
| **Marks welding** | sha256(pub)[:16] | Both agree on mark derivation |
| **Chain verdicts** | INTACT/FLIP/TAMPER/FORGERY | Both walkers agree |

**Proven by:** `cut_mesh_vectors.py --verify` (15 goldens).

### 4.8 Cross-Cutting: Guard Pipeline

| Seam | Contract | How Parity Is Proven |
|---|---|---|
| **guardscan** | Injection/poison/PII detection | Go implementation matches Python gate rules |
| **guardfetch** | Egress with private-IP refusal | Loopback-only default confirmed as doctrine |
| **Skill lint** | 5-rule SKILL.md validation | `atl skill lint` matches golden verdicts |

**Proven by:** `cut_guard_vectors.py --verify`, `cut_skill_vectors.py --verify`.

---

## 5. The Full Prove Matrix

Every command that must pass for Atlas to ship. Grouped by layer.

### Layer 0: Preconditions

```bash
# Toolchains present
rustc --version       # stable
go version            # 1.26+
node --version        # 24+
python --version      # 3.14
g++ --version         # 13+ (Linux) or cl.exe (Windows)
```

### Layer 1: Build

```bash
cargo build --workspace                              # Rust
cd line && go build ./... && cd ..                   # Go
cd kernels && python prove.py --compile-only && cd .. # C++ (compile only)
tsc --strict --noEmit                                # TypeScript
```

### Layer 2: Unit Tests

```bash
cargo test --workspace                               # Rust: 85+ tests
cd line && go test ./... && cd ..                     # Go: 14 tests
```

### Layer 3: Binary Proves

```bash
atlas --prove                                        # Rust: 10 strokes
atlas-mcp --prove                                    # Go MCP: 34 strokes
atlas-town --prove                                   # Go Town: 11 strokes
atlas-door --prove                                   # Go Door: 13 strokes
```

### Layer 4: C++ Kernels

```bash
cd kernels && python prove.py && cd ..               # C++: 17 strokes + bench + scan
```

### Layer 5: Golden-Master Cutters

```bash
python tools/cut_canon_vectors.py --verify
python tools/cut_chain_verdicts.py --verify
python tools/cut_us_vectors.py --verify
python tools/cut_faces_vectors.py --verify
python tools/cut_town_vectors.py --verify
python tools/cut_trade_vectors.py --verify
python tools/cut_mesh_vectors.py --verify
python tools/cut_schnorr_vectors.py --verify
python tools/cut_guard_vectors.py --verify
python tools/cut_rack_vectors.py --verify
python tools/cut_rack_ask_vectors.py --verify
python tools/cut_rack_open_vectors.py --verify
python tools/cut_memory_vectors.py --verify
python tools/cut_skill_vectors.py --verify
python tools/cut_ppmi_vectors.py --verify
python tools/cut_digest_vectors.py --verify
python tools/cut_predict_vectors.py --verify
```

### Layer 6: Cross-Impl Parity

```bash
python tools/check_trade_parity.py                  # Rust ↔ Go bidirectional
python tools/fold_agents.py --verify                 # Agent enrollment canonical
```

### Layer 7: TypeScript Toolchain

```bash
node --experimental-strip-types atl/cli.ts self-test       # 11 strokes
node --experimental-strip-types atl/cli.ts faces check     # Oracle HOLDS
node --experimental-strip-types atl/cli.ts skill lint      # 9/9 CLEAN
node --experimental-strip-types atl/cli.ts lint            # LINT CLEAN
node --experimental-strip-types atl/cli.ts gm run          # 28/28 across 7 stones
```

### Layer 8: E2E Suite

```bash
python tests/e2e/test_suite.py                       # 65 tests, 9 layers
```

### Layer 9: Integration

```bash
# atl wraps atlas byte-for-byte
# Chain verify fixture (known-TAMPER detected)
# VERSION consistency across all binaries
atlas --version && atlas-mcp --version && atlas-town --version && atlas-door --version
```

---

## 6. The CI/CD Pipeline

### 6.1 Architecture

```
push/PR to main
  ├─ Stage 1: Lint & Typecheck
  │   ├─ tsc --strict --noEmit
  │   ├─ go vet ./...
  │   └─ atl lint
  │
  ├─ Stage 2: Build (matrix)
  │   ├─ Rust: cargo build --workspace
  │   ├─ Go: go build ./...
  │   ├─ C++: g++ -std=c++17 -O2 (Linux)
  │   └─ Node: (no build needed, interpreted)
  │
  ├─ Stage 3: Unit Tests (matrix)
  │   ├─ Rust: cargo test --workspace
  │   ├─ Go: go test ./...
  │   └─ C++: prove.py (unit strokes only)
  │
  ├─ Stage 4: Binary Proves
  │   ├─ atlas --prove
  │   ├─ atl self-test
  │   ├─ atlas-mcp --prove
  │   ├─ atlas-town --prove
  │   └─ atlas-door --prove
  │
  ├─ Stage 5: Golden-Master Parity
  │   └─ all 17 cutters --verify
  │
  ├─ Stage 6: Cross-Impl Parity
  │   ├─ check_trade_parity.py
  │   └─ fold_agents.py --verify
  │
  └─ Stage 7: E2E Suite
      └─ python tests/e2e/test_suite.py
```

### 6.2 Triggers

| Event | What Runs | Gate |
|---|---|---|
| **Push to main** | Full pipeline (all 7 stages) | All green to merge |
| **Pull request** | Full pipeline (all 7 stages) | All green to merge |
| **Tag push (v*)** | Full pipeline + Docker build + GitHub Release | All green to publish |
| **Manual dispatch** | Full pipeline | Operator-triggered |

### 6.3 Runner

- **Ubuntu latest** (Linux) — primary CI target
- C++ compiles with g++ (no MSVC needed on CI)
- All tools via apt (rustup, go, node, python3, g++)

### 6.4 Artifacts

- Rust binary: `atlas` (Linux x86_64)
- Go binaries: `atlas-mcp`, `atlas-town`, `atlas-door` (Linux x86_64)
- C++ binaries: `prove`, `foldall`, `bench` (Linux x86_64)
- Docker image: `ghcr.io/<owner>/atlas:latest`

---

## 7. Parity Acceptance Criteria

A parity point is ACCEPTED when:

1. **Two independent implementations agree** on the same input/output pair
2. **The golden vector is cut from the Python oracle** (the original, not the port)
3. **SHA-256 hashes match** between the golden and the fresh cut
4. **The test runs hermetically** (temp grounds, never the live record)
5. **The verdict is named** (INTACT/FLIP/TAMPER/etc., not "passed/failed")

A parity point is REJECTED when:

1. The implementations disagree on a given input
2. The golden was cut from the port, not the oracle
3. The test touches live data
4. The verdict is ambiguous

---

## 8. Known Gaps and Follow-Ups

| Gap | Impact | Planned |
|---|---|---|
| C++ kernels Windows CI | MSVC not on GitHub Actions Ubuntu runners | Linux g++ is the CI target; Windows is dev-only |
| WebSocket live transport | Not yet implemented (v1 = THE LINE tools) | Named in B2 follow-ups |
| Registry cross-check for mesh | `.us` registry check in mesh admission | Needs Rust query seam |
| Merkle wrap closing at n=40 | Not yet triggered (no chain that long) | Will close when chains reach 40 entries |
| Dockerfile golang version | Uses 1.22, go.mod requires 1.26 | Fixed in this phase |
| Dockerfile copies live data/ | Source-ground concern | Fixed in this phase |
| `node_modules/` in repo | Pre-existing, not used by Atlas | Cleaned in this phase |

---

## 9. The Law of Parity

From CHARTER §3: *"Model output is testimony, never fact, never instruction."*

The Python cutter's output is not testimony — it is the oracle. It is the
original implementation. Every port must match it. If a port disagrees
with the cutter, the cutter wins. This is not because Python is better;
it is because the cutter was there first and the golden was cut from it.

The parity plan is the proof that the ports are faithful. The CI pipeline
is the automation that keeps them faithful. The operator holds the gate.
