# Contributing to ATLAS

## Ground Rules

1. **Read the newest handoff first.** Never re-derive documented state.
2. **Additive only.** Never patch working firmware. Originals read-only.
3. **Prove before claiming.** A status claim is not evidence — run the command.
4. **One writer per tree, one pen per chain.**
5. **Fold, never delete.**
6. **Zero external dependencies.** No crates.io, no npm, no pip, no Go modules beyond stdlib.
7. **Every agent is declared before it acts.** `.us` file first, or you are unenrolled.

## Development Setup

### Prerequisites

- Rust stable (`~\.cargo\bin`)
- Go 1.26+
- Python 3.14

### Build

```powershell
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
cargo build --workspace
cd line ; go build ./... ; cd ..
```

### Test

```powershell
cargo test --workspace
cd line ; go test ./... ; cd ..
.venv\Scripts\python.exe tools\cut_canon_vectors.py --verify
.venv\Scripts\python.exe tools\cut_chain_verdicts.py --verify
.venv\Scripts\python.exe tools\cut_us_vectors.py --verify
.venv\Scripts\python.exe tools\fold_agents.py --verify
```

All tests must pass before any commit. 92 Go tests, 85 Rust tests, 4 Python verifiers.

## Code Style

### Rust
- Follow existing patterns in `core/`, `store/`, `apps/atlas`
- No external crates — hand-roll or refuse

### Go
- Follow existing patterns in `line/`
- No external modules — stdlib only
- Embed static assets with `go:embed`

### Python
- stdlib-only — no pip packages
- Scripts in `tools/`

### JavaScript
- Vanilla JS — no frameworks
- SPA pattern with History API routing
- Embedded via `go:embed`

## Agent Declarations

Every agent, seat, tool, and skill must have a `.us` declaration file:

```yaml
name: agent-id
office: descriptive-office-name
reports_to: parent-agent-id
can_approve: false
permissions:
  - read
  - write
covenant: "1512741580b7239b"
```

Validation:
```powershell
atlas agent enroll --dry --dir agents
```

## Commits

- Descriptive messages
- Reference issue numbers when applicable
- All tests must pass
- No secrets, keys, or tokens

## Pull Requests

1. Branch from main
2. Write tests for new functionality
3. Update documentation if needed
4. Run full prove before requesting review
5. All CI checks must pass

## Architecture Decisions

Significant changes require an HLD or LLD in `estate/Agents/Plan/`:

- **HLD** — High-Level Design (architecture, rationale)
- **LLD** — Low-Level Design (implementation details)

Format: story first, observed/inferred marked, foundation-priority clause.

## Reporting Issues

Use GitHub Issues. Include:
- What you expected
- What actually happened
- Steps to reproduce
- Environment (OS, Rust version, Go version)
- Relevant logs or output

## Code of Conduct

Be direct. Lead with the finding. Plain technical English. Mark observed / inferred / ruled. The operator's first "no" is law.
