# ARCHITECTURE — Atlas System Design

*The technical architecture of Atlas: a polyglot sovereign agent harnessing
system.*

---

## 1. Design Principles

1. **Rule of One Computer.** Every hash, signature, and seal is computed in
   exactly one place: the Rust core. Services invoke, never reimplement.
2. **Structural enforcement.** Safety is in the grammar, not the config.
   `can_approve:false` is a parser rule. Forbidden verbs are absent-by-
   construction from every route table.
3. **Fold, never delete.** Corrections are new dated entries. The full
   history is always visible.
4. **Prove or it didn't happen.** Every binary ships `--prove`. Every stone
   exits through acceptance rows. Every test runs on temp grounds.
5. **Zero external dependencies.** No crates.io, no npm, no pip. Every
   dependency is vendored or hand-rolled. Supply-chain attack surface: zero.

## 2. System Layers

```
┌──────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                          │
│  atl CLI (TS) · faces/console · skill lint · gm harness      │
├──────────────────────────────────────────────────────────────┤
│                    SERVICE LAYER (Go)                         │
│  atlas-mcp (MCP stdio/HTTP) · atlas-town (beat/flow)         │
│  atlas-door (HTTP :8080) · guard pipeline                    │
├──────────────────────────────────────────────────────────────┤
│                    KERNEL LAYER (C++)                         │
│  libppmi · libdigest · libpredictor                          │
│  Socket-free CLI filters · zero network surface              │
├──────────────────────────────────────────────────────────────┤
│                    CORE LAYER (Rust)                          │
│  SHA-256 · canonical JSON · BIP-340 Schnorr                  │
│  chain verify/recognize · covenant derivation                │
│  .us parser (structural refusal) · SQLite store              │
├──────────────────────────────────────────────────────────────┤
│                    DECLARATION LAYER (.us)                    │
│  Agent registry · module declarations · tool/skill roster    │
│  can_approve:false · reports_to · covenant citation          │
├──────────────────────────────────────────────────────────────┤
│                    STATE LAYER (SQLite + JSONL)               │
│  master.db · ledger.db · trade.db · board.db                 │
│  memory.db · skills.db · gateway.db                          │
│  JSONL hash chains (truth) → SQLite (materialized view)      │
└──────────────────────────────────────────────────────────────┘
```

## 3. Data Flow

### 3a. Chain Verification

```
JSONL file → Rust chain verify → verdict (EMPTY|INTACT|FLIP|TAMPER)
                                → hash chain validated
                                → Merkle tree checked
                                → weld integrity confirmed
```

### 3b. Agent Enrollment

```
.declaration.us → us.rs parse → validate
              → can_approve:false check
              → reports_to resolution
              → covenant citation check
              → master.db enrollment
```

### 3c. MCP Tool Invocation

```
Client → atlas-mcp (stdio) → guard pipeline (scan → gate → fetch)
                             → Rust subprocess (hash/canon/sign)
                             → JSON response
                             → forbidden verb check (absent-by-construction)
```

### 3d. Golden-Master Parity

```
Python cutter → golden vectors (JSON)
                ↓
atl gm run → Python cutter --verify → hash match?
             Rust consumer test → hash match?
             Go consumer test → hash match?
                ↓
             PROVEN (byte-identical) or FAIL (first diff reported)
```

### 3e. Door Search

```
HTTP GET :8080/search?q=... → atlas-door
                              → Rust chain verify (badge truth)
                              → trade record search
                              → JSON response with receipts
```

## 4. Trust Model

### 4a. Structural Refusal

The `.us` parser enforces `can_approve:false` at the grammar level:
- Field present with value `false`: approved
- Field absent: **refused** (UsRefused error)
- Field present with any other value: **refused**

This is stronger than a policy flag because:
- It cannot be overridden at runtime
- It is checked at parse time, before any action
- Absence is explicitly a refusal, not a default

### 4b. Forbidden Verbs

Every server route table is tested for the absence of:
- approve · ascend · merge · commit · push
- delete · reject · promote

These verbs do not exist in the code. No configuration can enable them.
This is structural enforcement, not policy.

### 4c. Guard Pipeline

Every external interaction passes through:
```
User/Agent → guard (injection block)
           → redact (PII strip)
           → scan  (poison flag)
           → gate  (risk-tiered verdict)
           → fetch (egress, private-IP refusal)
```

### 4d. RBAC (Phase 3.2)

Per-tenant role-based access control:
- Policy stored in `<tenant_home>/rbac.json`
- Roles: operator, steward, agent, guest
- Permissions: read, edit, bash, net, tools (allow/deny)
- `tenant_rbac_assign` / `tenant_rbac_check` MCP tools
- Open mode when no assignments (backward compatible)
- `can_approve:false` remains structural — RBAC never grants it
1. **guardscan** — argument scanning for injection, poison, PII
2. **gate** — 5-risk-tier verdict book
3. **guardfetch** — egress with private-IP refusal, allowlist, timeout

### 4d. Hermetic Proves

Every test runs on temporary grounds:
- Temp SQLite databases (created and destroyed)
- Temp JSONL chains (injected tamper, verified)
- Never touches the live record

This means proves are reproducible by anyone, anywhere, with the same result.

## 5. Cross-Language Seam

### 5a. Go ↔ Rust (SPEC_SEAM)

- Invocation: direct exec (no shell), argument array, working dir set
- Contract version handshake: first stdout object carries `"atlas_seam": 1`
- Output: exactly one JSON object on stdout
  - Success: `{"ok": true, ...}` exit 0
  - Refusal: `{"ok": false, "refused": "<reason>"}` exit 2
  - Error: `{"ok": false, "error": "<message>"}` exit 1
- Progress lines: stderr only
- Timeouts: mandatory per call; kill on breach

### 5b. C++ Kernel Filter

- Input: SQLite/JSONL/JSON via `--db/--in` args or stdin
- Output: one JSON result to stdout
- Same ok/refused/error + exit-code shape as Go↔Rust
- No sockets, no egress, no network includes

### 5c. TypeScript Golden-Master (@atl/gm)

- Runs Python original + atlas artifact on identical input
- Canonicalizes outputs, compares byte-for-byte
- Report: `{"pair": ..., "input": sha256, "match": bool}`
- A stone's cutover requires zero mismatches

## 6. State Topology

| Database | Purpose | Derivation |
|---|---|---|
| master.db | Catalog, agent registry, rulings | Seeded from seed_catalog.py |
| ledger.db | Verified imports of all chains | Derived from JSONL chains |
| trade.db | Workorders, properties, inspections | Derived from trade JSONLs |
| board.db | Board ledgers, mail, inbox/outbox | Derived from board sources |
| memory.db | Citation envelopes, 8-tier memory | Derived from memory sources |
| skills.db | Catalog fingerprints, kit, rack | Derived from skill sources |
| gateway.db | Consolidated gateway shards | Derived from user shards |

**All SQLite databases are materialized views.** The JSONL hash chains are
the truth. SQLite is re-derivable from the journals at any time.

## 7. Versioning

- Root `VERSION` file: semver + stone tag (e.g., `0.1.0+f1`)
- Every binary answers `--version` with exactly that string
- Bumps are witnessed per stone in STATE_OF_BUILD.md
- Git history is created only by the operator's hand

## 8. Binary Inventory

| Binary | Language | Purpose | Port |
|---|---|---|---|
| `atlas` | Rust | Provenance core CLI | — |
| `atlas-mcp` | Go | MCP server (stdio) | — |
| `atlas-town` | Go | Town beat/flow/story | — |
| `atlas-door` | Go | HTTP door, search, badge | :8080 |
| `atl` | TypeScript | Agent CLI, faces, skills, gm | — |
