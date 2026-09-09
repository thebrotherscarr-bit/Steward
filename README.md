# ATLAS — Sovereign Agent Harness

A polyglot agent provenance system with cryptographic chain integrity, structural governance, and a modern observability webapp.

**Version:** 0.1.0+f1  
**Covenant:** 1512741580b7239b  
**License:** MIT

## What This Is

ATLAS is an operator-first agent harness that treats every tool call, trace, and agent declaration as a cryptographically chained, append-only record. It is not a framework — it is a governance layer that sits on top of any agent runtime and refuses to let the system lie about what happened.

### Core Properties

| Property | Enforcement |
|---|---|
| `can_approve` is always `false` | Structural grammar — approval lives in the operator's hand alone |
| Append-only | Fold, never delete — every change leaves a witness |
| Chain integrity | SHA-256 hashing links traces to their inputs/outputs |
| Forbidden verbs | Absent by construction — never written, never parsed |
| Multi-tenancy | MCP carries ALL projects; every call names its ground |
| Zero external deps | No crates.io, no npm, no pip, no Go modules beyond stdlib |

## Architecture

```
atlas/
├── core/           Rust crate: store, prov-hash, ground-prove, atlas-api
├── store/          Rust crate: sqlite persistence
├── apps/atlas/     Rust CLI binary
├── line/           Go workspace: atlas-mcp, atlas-tui, atlas-town, atlas-door
├── webapp/         Go + vanilla JS: observability GUI (port 8091)
├── tools/          Python: verifier scripts (stdlib-only)
├── specs/          Specification documents
├── agents/         .us agent declarations (40 seats)
├── skills/         Prove, orient, enroll skills
├── docs/           Full documentation
└── tests/          Integration tests
```

## Binaries

| Binary | Language | Description |
|---|---|---|
| `atlas` | Rust | CLI: version, ground-init, ground-prove |
| `atlas-mcp` | Go | MCP server: 25 tools + HTTP + GUI on :8090 |
| `atlas-tui` | Go | Terminal UI: dashboard, traces, agents, chain view |
| `atlas-town` | Go | Town square: multi-agent coordination |
| `atlas-door` | Go | Door: per-module MCP gateway |
| `atlas-webapp` | Go | Observability webapp on :8091 |

## Quick Start

### Prerequisites

- Rust stable (`~\.cargo\bin`)
- Go 1.26+
- Python 3.14 (`.venv\Scripts\python.exe`)

### Build

```powershell
# Rust
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo build --workspace

# Go
cd line ; go build ./... ; cd ..

# Webapp
cd webapp ; go build -o atlas-webapp.exe . ; cd ..
```

### Run

```powershell
# MCP server
cd line ; go run ./cmd/atlas-mcp

# TUI
cd line ; go run ./cmd/atlas-tui

# Webapp
cd webapp ; go run .
# Open http://localhost:8091
```

### Prove

```powershell
cargo test --workspace
cd line ; go test ./... ; cd ..
go run ./cmd/atlas-mcp --prove
.venv\Scripts\python.exe tools\cut_canon_vectors.py --verify
.venv\Scripts\python.exe tools\cut_chain_verdicts.py --verify
.venv\Scripts\python.exe tools\cut_us_vectors.py --verify
.venv\Scripts\python.exe tools\fold_agents.py --verify
```

## Webapp Features

- **Dashboard** — real-time stats, recent traces, agent roster
- **Agent Registry** — browse all 40 enrolled seats with full .us declarations
- **Trace Log** — chronological tool call history with SHA-256 hashes
- **Tool Surface** — invoke any MCP tool with JSON args
- **Evaluations** — score and pass/fail traces against criteria
- **Messages** — Discord/Slack/WhatsApp adapter framework
- **Settings** — MCP connection, eval thresholds, provenance config
- **SSE** — real-time event stream for live updates

## Agent System

40 `.us` agent declaration files, validated by `atlas agent enroll --dry`:

- **manjuel** — Operator's serf, record keeper
- **Twelve Tribes** — Core household (aria, rex, mason, luna, quinn, alex, scout, courier, scribe, steward, neiro, builder)
- **Council personas** — Advisory seats
- **Lineage actors** — Historical chain
- **Gate** — Access control
- **Doctrine seats** — Law and foundation

Every agent carries:
- `can_approve: false` (structural, not configurable)
- `reports_to` chain (resolvable to root)
- Covenant hash `1512741580b7239b`
- Permissions declaration

## Specifications

| Spec | Location | Status |
|---|---|---|
| SPEC.md | `specs/SPEC.md` | Current |
| SPEC_STORE.md | `specs/SPEC_STORE.md` | Current |
| SPEC_US.md | `specs/SPEC_US.md` | Current |
| SPEC_COMMANDS.md | `specs/SPEC_COMMANDS.md` | Current |
| SPEC_TUI.md | `specs/SPEC_TUI.md` | Current |
| THE_ROAD.md | `THE_ROAD.md` | Active roadmap |

## The Laws

1. Source grounds are READ-ONLY. Fold, never delete.
2. Goldens BEFORE assertions.
3. `can_approve` is false in every declaration ever.
4. Ports never move at cutover.
5. Proves are hermetic: temp grounds, never the live record.
6. Append-only witnesses.
7. VERSION pins the stone.
8. Multi-tenancy: strangers refused by name.

## Documentation

See `docs/README.md` for the full index (54+ documents).

## Contributing

See `CONTRIBUTING.md`.

## License

MIT — see `LICENSE`.
