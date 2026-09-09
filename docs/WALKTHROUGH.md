# WALKTHROUGH — the whole system, end to end

*For the reader who wants to understand what Atlas is, why it is shaped
this way, and how every piece connects. Read once; keep as reference.*

---

## 1. The Problem Atlas Solves

You have AI agents. They access your files, call your APIs, make decisions.
But:

- **Can you prove what they did?** Not "the log says so" — cryptographic proof.
- **Can you prove they stayed within bounds?** Not "the policy says so" — structural proof.
- **Can you prove no one tampered with the record?** Not "we trust the server" — hash-chain proof.

Atlas answers all three with math, not trust.

## 2. The Five Laws

These shape every design decision in the system:

### Law 1: state = fold(record)

The JSONL hash chains are the truth. SQLite is a materialized view. If the
chain says X happened, X happened. If Manjuel is tampered, the hash breaks.
If Manjuel is empty, nothing happened.

```
entry[n].hash = SHA-256(prev || kind || n || payload)
```

If `entry[n].hash` doesn't match, the verdict is FLIP or TAMPER. Period.

### Law 2: The Operator Holds the Gate

No `approve`, `ascend`, `commit`, `push`, `delete`, `reject`, or `promote`
path exists in code. These verbs are absent-by-construction from every route
table. Every server has a test asserting their absence.

You are the approval. Not the code. Not the agent.

### Law 3: Testimony, Never Fact

Model output is stamped testimony. It is outranked by the record. If a model
says "I did X" but the record doesn't show X, the record wins.

### Law 4: Prove or It Didn't Happen

Every binary ships `--prove`. Every stone exits through acceptance rows in
ACCEPTANCE.md. Every test runs on temporary grounds, never the live record.

A status claim is not evidence — run the command.

### Law 5: Fold, Never Delete

Nothing is erased. Corrections are new dated entries. The full history is
always visible. This is what auditors want. This is what regulators require.

## 3. The Grounds

```
Archive/
  estate/         READ-ONLY source (the living Python ecosystem)
  secondbrain/    READ-ONLY source (6 harvested repos)
  atlas/          THE BUILD (this folder)
```

Atlas lives beside the grounds it reconciles. The grounds are read-only —
walked, hashed, and copied from; never written.

## 4. The Eleven Stones

The build proceeds in stones. Each stone has acceptance criteria in
ACCEPTANCE.md and proven commands in SPEC_COMMANDS.md.

| Stone | What It Built | Key Proof |
|---|---|---|
| P0 | Docs, catalog, venv | Catalog seeds idempotently |
| A1 | Rust core (hash, chain, canon, schnorr, covenant, store) | `atlas --prove` (10 strokes) |
| A2 | .us registry (40 agents enrolled) | Round-trip render(parse(x)) == x |
| B1 | Go MCP server (30+ tools, forbidden verbs absent) | `atlas-mcp --prove` (34 strokes) |
| B2 | Go mesh (Schnorr signatures, differential Py↔Go) | 9 golden vectors byte-identical |
| C1 | TS faces + atl CLI (wrap/serve/check/lint/self-test) | 9/9 strokes green |
| D1 | Go town (beat/flow/story, no-approve check) | 4 oracle decisions, 11 strokes |
| D2 | Go door + Rust trade (badge truth, forms, parity) | 13 strokes, bidirectional parity |
| E1 | C++ kernels (PPMI, digest, predictor, 50× speed) | 13/13 parity, socket scan clean |
| F1 | Harvest (rack, envelopes, guard, skill lint) | 9/9 strokes, rack tools awake |
| G | Cutovers (gm harness, port verification, rollback notes) | 28/28 green, 7 rollback notes |

## 5. Every Layer, One Command

```bash
# Rust core
atlas --prove              # 10 strokes
atlas chain verify --roots . # live walk

# Go services
atlas-mcp --prove          # 34 strokes (MCP tools)
atlas-town --prove         # 11 strokes (beat/flow)
atlas-door --prove         # 13 strokes (HTTP door)

# TypeScript tooling
atl self-test              # 11 strokes (faces, lint, gm)
atl gm run                 # 28 strokes (full golden-master)

# C++ kernels
python kernels/prove.py    # compile + run + bench + socket scan

# Cross-impl parity
python tests/e2e/test_suite.py  # 65 tests, 9 layers
```

## 6. The .us Declaration

Every agent, tool, skill, and module is declared in a `.us` file. The critical
rule: `can_approve: false` must be explicit. Absence is a refusal.

```json
{
  "us": 1,
  "id": "my-agent",
  "kind": "module",
  "body_v": 1,
  "generation": 1,
  "office": "reader",
  "reports_to": "operator",
  "can_approve": false,
  "ledger": "my-agent",
  "covenant": "1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb"
}
```

The parser refuses declarations that don't explicitly say safe. This is
structural enforcement — the strongest safety guarantee in the market.

## 7. The Guard Pipeline

Every external interaction passes through three stages:

1. **guardscan** — scans arguments for injection, poison, PII
2. **gate** — 5-risk-tier verdict book
3. **guardfetch** — egress with private-IP refusal, allowlist, timeout

If any stage refuses, the interaction is blocked. No exceptions.

## 8. The Golden-Master Harness

`@atl/gm` proves byte-parity between the Python original and the polyglot
replacement. Before any service cutover:

1. Python cutter produces golden vectors (JSON)
2. Atlas artifact produces its output on identical input
3. SHA-256 hashes are compared
4. Zero mismatches required

This is not "the port passes its own tests." The Python cutter is the oracle.

## 9. The Record

| Document | Purpose | Rule |
|---|---|---|
| SEAT_LOG.md | Who did what, when | Append-only |
| STATE_OF_BUILD.md | What's done, what's next | Append-only |
| THE_ROAD.md | Build path, status | Append-only |
| THE_CATALOG.md | Module dictionary | Append-only |
| ACCEPTANCE.md | Testable criteria | Rows added, not rewritten |

Every entry is dated. Every correction is a new entry. The record is the memory.

## 10. What You Can Do

- **Make an agent that won't wreck your stuff.** Write a `.us` declaration.
  The parser enforces safety structurally.
- **Prove what your agent did.** Every action is hash-chained. Every chain
  is verifiable.
- **Migrate safely.** Golden-master parity proves the replacement is
  identical before any cutover.
- **Trust the math, not the vendor.** Zero external dependencies. Every
  prove is hermetic. Every test is reproducible.

That's Atlas. The whole system. One walk.
