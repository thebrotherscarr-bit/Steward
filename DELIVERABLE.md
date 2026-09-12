# ATLAS 0.1.5 — Deliverable

**Date:** 2026-09-12
**Version:** 0.1.5
**Covenant:** 1512741580b7239b
**License:** MIT

---

## Proven

Measured on the ground 2026-09-12, at 0.1.5. Every number here was counted
from the disk on that date; where a suite could not be RUN in this ground, it
says so rather than carrying a PASS it did not earn.

| Suite | Count | Status |
|---|---|---|
| Rust tests (`#[test]` under core/ store/ apps/) | 85 | not run here — the spine is not built in this ground |
| Go tests, `line` | 229 fns / 19 pkgs | PASS |
| Go tests, `webapp` | 1 fn / 1 pkg | PASS — and thin; see Known below |
| Python verifier (`tests/prove.py`) | 1 file, 37 legs | 22 held · 15 absent · 0 broke |
| Webapp build + vet | — | PASS |
| Version consistency | 8 VERSION files + Cargo.toml + version.rs | PASS — every binary asked and agreed |

**ABSENT IS NOT A PASS.** All 15 absent legs name the same missing thing: the
private oracle ground (`ATLAS_ORACLE_ROOT`). They are legs that would cut
golden vectors against material this repository does not carry, and on a clone
without it they report ABSENT and exit 0 rather than going red for a checkout
artifact. Nothing is claimed for them.

**Known thin:** the `webapp` module has one test function. ADR-006 measured
this before — the protocol layer and the tenant model were the two least
tested things in the door, and both were given first strokes on 2026-09-11.
The glass has not had that pass yet.

## Binaries

| Binary | Language | Version | Status |
|---|---|---|---|
Every one of these was ASKED on 2026-09-12 and answered; `atlas-vc` is the
fifth command and was missing from this table entirely.

| Binary | Language | Version | Status |
|---|---|---|---|
| `atlas` | Rust | 0.1.5 | not built in this ground |
| `atlas-mcp` | Go | 0.1.5 | answers |
| `atlas-tui` | Go | `atlas-tui 0.1.5` | answers |
| `atlas-town` | Go | 0.1.5 | answers |
| `atlas-door` | Go | 0.1.5 | answers |
| `atlas-vc` | Go | 0.1.5 | answers |
| `atlas-webapp` | Go | 0.1.5 | answers (`/api/health`) |

## MCP Tool Surface (78 tools)

| Tool | Writes | Description |
|---|---|---|
| `get_in_line` | no | Protocol handshake |
| `verify_chain` | no | Chain integrity check |
| `muster` | no | List carried projects |
| `read_handoffs` | no | Read handoff chain |
| `list_doctrine` | no | List doctrine entries |
| `read_doctrine` | no | Read specific doctrine |
| `check_the_wall` | no | Path wall check |
| `state_matrix` | no | Fold record state |
| `read_plan` | no | Read plan with receipt |
| `ask_steward` | yes | Route through engine |
| `remember` | yes | Write testimony |
| `mesh_enroll` | yes | Enroll mesh member |
| `mesh_post` | yes | Post signed message |
| `mesh_read` | no | Read/reveal message |
| `mesh_chain` | no | Walk mesh chain |
| `mesh_cite` | yes | Cite in mesh |
| `rack_list` | no | List voice tiers |
| `rack_ask` | yes | Route voice question |
| `rack_open` | no | Open voice bundle |
| `memory` | no | Citation memory |
| `us_to_vc` | no | US to VC transform |
| `tenant_list` | no | List tenants |
| `tenant_rbac_assign` | yes | Assign RBAC |
| `tenant_rbac_check` | no | Check RBAC |
| `tenant_trust` | yes | Set trust level |

## Webapp API Routes (16 endpoints)

| Method | Route | Description |
|---|---|---|
| GET | `/api/health` | System health + version |
| GET | `/api/agents` | List all 40 agents |
| GET | `/api/agents/{id}` | Agent detail + traces |
| POST | `/api/agents` | Upsert agent |
| GET | `/api/traces` | List traces (filter by agent) |
| GET | `/api/traces/{id}` | Trace detail + evals |
| POST | `/api/traces` | Add trace |
| GET | `/api/evals` | List evals (filter by trace) |
| POST | `/api/evals` | Add eval |
| POST | `/api/tools/call` | Invoke MCP tool |
| GET | `/api/search` | Search agents + traces |
| GET | `/api/messages` | List messages |
| POST | `/api/messages/send` | Send message |
| GET | `/api/settings/{key}` | Get setting |
| POST | `/api/settings/{key}` | Set setting |
| GET | `/api/events` | SSE event stream |

## Webapp Pages (7 SPA routes)

| Route | Description |
|---|---|
| `/` | Dashboard — stats, recent traces, agent roster |
| `/agents` | Agent grid — 40 enrolled seats |
| `/agents/{id}` | Agent detail — declaration + traces |
| `/traces` | Trace log — chronological with SHA-256 hashes |
| `/traces/{id}` | Trace detail — input/output + evals |
| `/tools` | Tool surface — invoke any MCP tool |
| `/evals` | Evaluations — pass/fail scores |
| `/messages` | Messages — Discord/Slack/WhatsApp |
| `/settings` | Settings — MCP connection, evals, provenance |

## Agent System

- **40 .us declarations** validated, enrolled, documented
- `can_approve: false` structural enforcement
- Covenant hash `1512741580b7239b` verified in all
- `reports_to` chains resolvable to root
- Skills: prove, orient, enroll

## E2E Test Suite (84 scenarios + 38 workflow steps)

### 6 CI/CD Pipelines (parallel jobs)

| Pipeline | Stages | Duration | Trigger |
|---|---|---|---|
| SPINE | 12 (Rust core) | ~90s | push/PR |
| LINE | 11 (Go MCP) | ~120s | push/PR |
| GOLDEN | 11 (Python verifiers) | ~60s | push/PR |
| AGENT | 11 (40-seat validation) | ~45s | push/PR |
| WEBAPP | 18 (GUI + API) | ~60s | push/PR |
| OLLAMA | 14 (live integration) | ~180s | manual/nightly |

### 6 Agent Workflows

| Workflow | Steps | Ollama | Description |
|---|---|---|---|
| SCOUT | 5 | no | Read-only survey |
| STEWARD | 5 | yes | Memory + testimony |
| MESH | 7 | no | Encrypted communication |
| GATE | 5 | yes | Security + guard |
| TOWN | 4 | no | Task scheduling |
| OPERATOR | 12 | yes | Full lifecycle |

### Ollama Models Under Test

| Model | Size | Capabilities | Role |
|---|---|---|---|
| qwen3.5:4b | 3.4GB | completion, tools, thinking | Scout tier |
| qwen3.5:9b | 6.6GB | completion, tools, thinking, vision | Voice tier |
| qwen2.5-coder:7b | 4.7GB | completion, tools, insert | Voice tier |
| qwen2.5-coder:14b | 9.0GB | completion, tools, insert | Mind tier |
| llama3.2 | 2.0GB | completion, tools | Scout tier |
| phi4-mini | 2.5GB | completion, tools | Scout tier |
| deepseek-r1:8b | 5.2GB | completion, thinking | Voice tier |
| gemma4:12b | 7.6GB | completion, tools, thinking, vision | Voice tier |
| gemma4:e4b | 9.6GB | completion, tools, thinking | Mind tier |
| qwen3-vl:8b | 6.1GB | vision, completion, tools, thinking | Voice tier |
| nomic-embed-text-v2-moe | 958MB | embedding | Embedder |

### Test Results — A SNAPSHOT OF 0.1.2, VERIFIED 2026-09-08

Kept as the record of what that release proved. It is NOT a claim about
this build: the six pipelines below describe a design CI never ran, and
the counts predate three versions. What is true now is the **Proven**
table at the top of this file, measured on 2026-09-12.

| Suite | Status |
|---|---|
| S1: Binary Smoke | 5/5 PASS |
| S2: MCP Tool Surface | 8/8 PASS |
| S3: Write Tools | 5/5 PASS |
| S4: Mesh B2 | 8/8 PASS |
| S5: Rack F1 | 10/10 PASS |
| S6: Guard | 5/5 PASS |
| S7: Tenant | 4/4 PASS |
| S8: Ollama Integration | 10/10 PASS |
| S9: Webapp | 6/6 PASS |
| S10: Cross-Impl Parity | 4/4 PASS |
| S11: Agent Lifecycle | 6/6 PASS |
| S12: Prove Chains | 3/3 PASS |
| W1-W6: Workflows | 38/38 PASS |
| **TOTAL** | **112/112 PASS** |

## CI/CD

ONE WORKFLOW, AND IT IS THE ONLY ONE. This table named `ci.yml` and
`release.yml` for weeks and NEITHER HAS EVER EXISTED; `docs/PIPELINES.md` went
on describing `ci.yml` orchestrating six parallel jobs. Checked against
`.github/workflows/` 2026-09-12: one file.

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/prove.yml` | push/PR to main | the battery on Windows, plus the Go half off Windows; gofmt gated across BOTH modules |
| `prove.ps1` | local | the full prove suite |
| `version.ps1` | local | version bump/sync/show |
| `release.ps1` | local | prove → bump → commit → tag → push |

**There is no release workflow.** A `v*` tag builds and publishes nothing on
its own; `release.ps1` is the local path and a person runs it. That is a gap,
not a feature — named here so it is a decision rather than a surprise.

## Documentation

| File | Purpose |
|---|---|
| `LICENSE` | MIT license |
| `README.md` | Project overview, architecture, quickstart |
| `CONTRIBUTING.md` | Dev setup, code style, PR process |
| `CHANGELOG.md` | Full version history |
| `SECURITY.md` | Vulnerability reporting, scope |
| `docs/` | 54+ specification and design documents |
| `agents/docs/` | 40 agent documentation files |

## File Inventory

```
atlas/
├── .github/workflows/     prove.yml -- ONE workflow, not two
├── agents/                40 .us declarations + docs/
├── apps/atlas/            Rust CLI
├── core/                  Rust crate (42 tests)
├── data/                  master.db
├── docs/                  58+ documents
│   ├── PIPELINES.md       6 pipeline SPECS (a design; CI runs prove.yml)
│   ├── WORKFLOWS.md       6 agent workflow specs
│   ├── OLLAMA_PROVER.md   Ollama integration prover
│   └── ACCEPTANCE.md      Pass/fail criteria
├── faces/                 Console + bridge
├── kernels/               C++ (prove, digest, foldall, bench)
├── line/                  Go workspace (229 test fns over 19 pkgs)
│   ├── cmd/atlas-mcp/     MCP server (78 tools)
│   ├── cmd/atlas-tui/     Terminal UI
│   ├── cmd/atlas-town/    Town square
│   ├── cmd/atlas-door/    Door gateway
│   └── internal/          guard, mesh, rack, town, ...
├── skills/                prove, orient, enroll
├── specs/                 Specifications
├── store/                 Rust store (25 tests)
├── tests/
│   ├── e2e/
│   │   ├── E2E_SCENARIOS.md       84 scenarios across 12 categories
│   │   ├── ollama_prover.py        Full test harness (stdlib-only)
│   │   └── ollama_prover_results.json  Last run results
│   └── workflows/
│       ├── wf_scout.py             SCOUT workflow (5 steps)
│       ├── wf_steward.py           STEWARD workflow (5 steps)
│       ├── wf_mesh.py              MESH workflow (7 steps)
│       ├── wf_gate.py              GATE workflow (5 steps)
│       ├── wf_town.py              TOWN workflow (4 steps)
│       └── wf_operator.py          OPERATOR workflow (12 steps)
├── tools/                 Python verifiers (17 scripts)
├── webapp/                Observability GUI (port 8091)
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── SECURITY.md
├── VERSION                0.1.5
├── prove.ps1              Local prove suite
├── version.ps1            Version management
└── release.ps1            Release automation
```

## Git History — AS OF 0.1.2

Three commits from the 0.1.0/0.1.1 era. `CHANGELOG.md` is the live
history; this block is a fossil and is left as one.

```
e20da09 ci/cd: consolidated workflows, version management, local + remote pipelines
2781f42 bump version to 0.1.1+f1
35bc0f6 atlas 0.1.0+f1: full release — webapp, CI/CD, docs, 40 agents, 85 Rust + 92 Go tests proven
```

## How to Use

```powershell
# Prove everything
.\prove.ps1

# Show version
.\version.ps1 show

# Bump version
.\version.ps1 bump patch

# Release (prove → bump → commit → tag → push)
# PLAIN SEMVER ONLY -- a build tag is REFUSED (struck 2026-09-10).
.\release.ps1 0.1.6

# Run webapp
cd webapp; go run .
# Open http://localhost:8091

# Run MCP server
cd line; go run ./cmd/atlas-mcp

# Run E2E prover (scenarios only)
python tests/e2e/ollama_prover.py --scenarios

# Run E2E prover (workflows only)
python tests/e2e/ollama_prover.py --workflows

# Run specific workflow
python tests/workflows/wf_operator.py

# Run Ollama integration tests
python tests/e2e/ollama_prover.py --category s8

# Dry run (show what would execute)
python tests/e2e/ollama_prover.py --dry-run
```

## Zero External Dependencies

No crates.io. No npm. No pip. No Go modules beyond stdlib. Hand-rolled or refused.
