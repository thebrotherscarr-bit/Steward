# QUICKSTART — Atlas in 5 minutes

*Get Atlas built, proven, and running on your machine.*

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Rust | stable | `rustc --version` |
| Go | 1.26+ | `go version` |
| Node.js | 24+ | `node --version` |
| Python | 3.14 | `python --version` |

Install Rust: [rustup.rs](https://rustup.rs)  
Install Go: [go.dev/dl](https://go.dev/dl/)  
Install Node: [nodejs.org](https://nodejs.org)  
Install Python: [python.org](https://python.org)

## 1. Clone and Build (2 minutes)

```bash
git clone https://github.com/atlas-dev/atlas.git
cd atlas

# Build Rust core
cargo build --workspace

# Build Go services
cd line && go build ./... && cd ..
```

## 2. Verify Everything (1 minute)

```bash
# Rust tests (85+ tests)
cargo test --workspace

# Go tests (7 packages)
go test ./line/...

# Atlas binary
atlas --version
atlas --describe
```

Expected:
```
atlas 0.1.0+f1 - polyglot reconciliation spine; all provenance lives here.
```

## 3. Run the Full Prove (1 minute)

```bash
atlas --prove
```

Expected (10 strokes, all PASS):
```
[1/10] version pin
[2/10] version cross
[3/10] chain verify fixtures
[4/10] chain recognize fixtures
[5/10] store trio
[6/10] db lifecycle
[7/10] enroll dry
[8/10] orient pack
[9/10] link lay status
[10/10] covenant repro

PROVEN. 10/10 strokes green.
```

## 4. Run the E2E Suite (30 seconds)

```bash
python tests/e2e/test_suite.py
```

Expected: 65/65 ALL GREEN across 9 layers.

## 5. Make Your First Agent Declaration

Create a file `my-agent.us`:

```
# My Agent

A helpful assistant that reads documents and answers questions.

```json us
{
  "us": 1,
  "id": "my-agent",
  "kind": "module",
  "body_v": 1,
  "generation": 1,
  "office": "reader",
  "reports_to": "operator",
  "can_approve": false,
  "ledger": "my-agent-ledger",
  "covenant": "1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb"
}
```
```

The critical line: `"can_approve": false`. This agent cannot approve its own
actions. The operator (you) holds the gate.

## What's Next?

- [WALKTHROUGH.md](WALKTHROUGH.md) — the full system tour
- [TUTORIAL.md](TUTORIAL.md) — learn by doing (5 exercises)
- [CLI_REFERENCE.md](CLI_REFERENCE.md) — every command, every flag
- [ARCHITECTURE.md](ARCHITECTURE.md) — how the system is designed

## Troubleshooting

**"cargo: not found"**  
Add Rust to PATH: `export PATH="$HOME/.cargo/bin:$PATH"`

**"go test" fails with module errors**  
Run from the `line/` directory: `cd line && go test ./...`

**"node: experimental-strip-types"**  
You need Node 24+. Earlier versions don't support TypeScript stripping.

**"python: No module named venv"**  
Use the system Python 3.14, not a distribution that strips venv.
