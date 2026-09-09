---
name: prove
description: "Run the full Atlas prove battery across all binaries and verify the system is green."
risk: safe
---

# Prove Skill

Run the full Atlas prove battery across all binaries and verify the system is green.

## When to Use This Skill

Use this skill when:
- Verifying the system is healthy after changes
- Running the full prove before a commit or handoff
- Checking that all tests pass across Rust, Go, and Python
- Diagnosing which component is failing

## Prerequisites

- Rust stable (`~/.cargo/bin` on PATH)
- Go 1.26+ on PATH
- All binaries built in `bin/` directory

## Usage

### Full prove (recommended)

```bash
atlas-tui prove
```

This runs:
1. `atlas --prove` — 10 Rust strokes (version pin, chain verify, store, enroll, orient, link, covenant)
2. `atlas-mcp --prove` — 58 Go strokes (multi-tenant, tools, mesh, rack, guard)
3. `atlas-town --prove` — 11 Go strokes (beat, flow, story)
4. `atlas-door --prove` — 13 Go strokes (search, badge, forms)

### Individual binary proves

```bash
atlas --prove          # Rust spine
atlas-mcp --prove      # MCP server
atlas-town --prove     # Town server
atlas-door --prove     # Door server
```

### Rust tests only

```bash
cargo test --workspace
```

### Go tests only

```bash
cd line && go test ./...
```

### Python verifiers only

```bash
.venv/Scripts/python.exe tools/cut_canon_vectors.py --verify
.venv/Scripts/python.exe tools/cut_chain_verdicts.py --verify
.venv/Scripts/python.exe tools/cut_us_vectors.py --verify
.venv/Scripts/python.exe tools/fold_agents.py --verify
```

## Expected Output

All proves should exit 0 with all strokes PASS. A single FAIL means the system is not green.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All proves green |
| 1 | One or more strokes failed |
