# CLI REFERENCE — every command, every flag

*The complete command reference for all Atlas binaries.*

---

## atlas (Rust Core)

The provenance spine. All hashing, canonicalization, signing, chain
verification, and agent enrollment lives here.

### atlas --version

Print the version string.

```bash
atlas --version
# Output: 0.1.0+f1
```

### atlas --describe

Describe the binary and its capabilities.

```bash
atlas --describe
# Output: atlas 0.1.0+f1 - polyglot reconciliation spine; all provenance lives here.
```

### atlas --prove

Run the full Rust prove battery (10 strokes, hermetic).

```bash
atlas --prove
# Exit 0: all strokes green
# Exit 1: one or more strokes failed
```

Strokes:
1. version pin — VERSION file matches binary
2. version cross — all binaries agree on VERSION
3. chain verify fixtures — 16/21 INTACT, 5 expected TAMPER
4. chain recognize fixtures — 21/21 forms identified
5. store trio — init, import, export
6. db lifecycle — WAL, journal_sync, idempotent seed
7. enroll dry — agent enrollment reads files
8. orient pack — assembles line + road + log tail
9. link lay status — forge chain status
10. covenant repro — construction-A over foundation docs

### atlas chain verify <path>

Verify a JSONL hash chain.

```bash
atlas chain verify tests/fixtures/chains/steward_chain.jsonl
# Output: verdict=FLIP entries=1 flips=[0] broke_at=None appendable=true
```

Verdicts:
- **EMPTY** — chain has no entries
- **INTACT** — all hashes match, chain is sound
- **FLIP** — one or more entries have hash mismatches
- **TAMPER** — chain is broken (prev pointer mismatch)

Options:
- `--roots <dir>` — walk all chains under a directory

### atlas chain recognize <path>

Identify which legacy form a chain uses.

```bash
atlas chain recognize tests/fixtures/chains/forge_links_chain.jsonl
# Output: form=forge_links
```

### atlas db init <path>

Initialize a SQLite database with WAL mode.

```bash
atlas db init my.db
# Output: journal_mode=wal
```

### atlas db import <db> <chain-name> <jsonl-path>

Import a JSONL chain into the database.

```bash
atlas db import my.db agents_seatlog tests/fixtures/chains/agents_seatlog.jsonl
# Output: imported agents_seatlog
```

### atlas db status <db>

Show database status.

```bash
atlas db status my.db
# Output: journal_mode=wal chain=agents_seatlog entries=42
```

### atlas db export <db> <chain-name> --check <jsonl-path>

Export a chain from the database and verify byte-identical match.

```bash
atlas db export my.db agents_seatlog --check tests/fixtures/chains/agents_seatlog.jsonl
# Output: export agents_seatlog byte-identical
```

### atlas agent enroll <db> --dir <agents-dir>

Enroll agents from .us declarations into the database.

```bash
atlas agent enroll data/master.db --dir agents --dry
# Output: 40 files read (0 modules); enrolled 0 agents [DRY RUN]
```

Options:
- `--dry` — dry run, don't write to database

### atlas orient --home <project>

Assemble the orientation pack for a project.

```bash
atlas orient --home .
# Output: ATLAS ORIENTATION + line + road + log tail
```

### atlas trade property <id> --ops <ops-dir>

Look up a property in the trade record.

```bash
atlas trade property P-001 --ops state/ops
# Output: property details
```

### atlas link status --chain <path>

Check the status of a forge chain.

```bash
atlas link status --chain tests/fixtures/chains/forge_links_chain.jsonl
# Output: verdict=FLIP entries=9 links=0 wraps=0
```

### atlas link lay --chain <path> --data <data>

Lay a new entry on a forge chain.

```bash
atlas link lay --chain my_chain.jsonl --data '{"action":"created"}'
```

---

## atlas-mcp (Go MCP Server)

The multi-tenant MCP server. Exposes tools via JSON-RPC 2.0 over stdio.

### atlas-mcp --version

```bash
atlas-mcp --version
# Output: 0.1.0+f1
```

### atlas-mcp --describe

```bash
atlas-mcp --describe
# Output: atlas-mcp 0.1.0+f1 - THE LINE: multi-tenant MCP door; all of atlas in one call.
```

### atlas-mcp --prove

Run the full MCP prove battery (34 strokes, hermetic).

```bash
atlas-mcp --prove
# Exit 0: all strokes green
```

### atlas-mcp --home <project>

Start the MCP server for a specific project.

```bash
atlas-mcp --home .
```

### atlas-mcp --http <addr>

Start as an HTTP server instead of stdio MCP. Exposes `GET /health`,
`GET /tools`, and `POST /rpc` (JSON-RPC 2.0).

```bash
atlas-mcp --home . --http :8090
```

Tools available (30+):
- `get_in_line` — standing law + line + road + log-tail
- `list_doctrine` — carried doctrine by name
- `read_doctrine` — one document with sha256 receipt
- `read_handoffs` — SEAT_LOG whole with receipt
- `read_plan` — HLD/LLD/road documents
- `remember` — sole write tool, staged for operator
- `state_matrix` — state = fold(record) index
- `verify_chain` — chain verdict via Rust spine
- `rack_list` — live tier ladder
- `rack_ask` — routed ask to the rack
- `rack_open` — expanded context bundle
- `check_the_wall` — judge a path before acting
- `muster` — declared projects roll call
- `ask_steward` — weighed ruling with receipts
- `mesh_read` — read channel chain
- `mesh_post` — post signed message
- `mesh_chain` — verify mesh chain
- `mesh_cite` — cite chain hashes
- `memory` — cited answers from local memory
- `us_to_vc` — .us → W3C Verifiable Credential
- `tenant_list` — list tenants and RBAC status
- `tenant_rbac_assign` — assign role to agent
- `tenant_rbac_check` — check agent permission
- `tenant_trust` — grant/revoke cross-tenant trust

Forbidden tools (absent-by-construction):
- approve · ascend · merge · commit · push
- delete · reject · promote

---

## atlas-town (Go Town Server)

The town beat/flow/story server.

### atlas-town --version

```bash
atlas-town --version
# Output: 0.1.0+f1
```

### atlas-town --describe

```bash
atlas-town --describe
# Output: atlas-town — D1 Town: beat (one draft-and-work cycle), flow (a b), story (h), look, prove
```

### atlas-town --prove

Run the full town prove battery (11 strokes).

```bash
atlas-town --prove
# Exit 0: all strokes green
```

### atlas-town beat --home <project>

Run one draft-and-work cycle.

```bash
atlas-town beat --home .
```

### atlas-town flow --home <project> [a b]

Run flow with jitter between pause bounds a and b.

```bash
atlas-town flow --home . 500 2000
```

### atlas-town story --home <project> [hours]

Show the story for the last N hours (default: 24).

```bash
atlas-town story --home . 48
```

### atlas-town look --home <project>

Show the current board state.

```bash
atlas-town look --home .
```

---

## atlas-door (Go Door Server)

The HTTP door on port 8080. Search, badge, forms.

### atlas-door --version

```bash
atlas-door --version
# Output: 0.1.0+f1
```

### atlas-door --describe

```bash
atlas-door --describe
# Output: atlas-door — D2 door: search the trade record with receipts, badge truth, forms.
```

### atlas-door --prove

Run the full door prove battery (13 strokes).

```bash
atlas-door --prove
# Exit 0: all strokes green
```

### atlas-door --port <port>

Start the door on a custom port (default: 8080).

```bash
atlas-door --port 9090
```

Routes:
- `GET /` — badge (chain status)
- `GET /search?q=<query>` — search the trade record
- `GET /badge` — badge truth (hash verification)
- `POST /form` — submit a crew form

---

## atl (TypeScript CLI)

The developer toolchain. Agent management, faces, skills, golden-master.

### atl --version

```bash
node --experimental-strip-types atl/cli.ts --version
# Output: 0.1.0+f1
```

### atl self-test

Run the full toolchain prove battery (11 strokes).

```bash
node --experimental-strip-types atl/cli.ts self-test
# Exit 0: PROVEN
```

Strokes:
- VERSION pinned
- VERSION agrees across root and line
- VERSION agrees across all binaries
- faces check: console+sprites match oracle pins
- bridge snapshot reproduces golden bytes
- bridge leaves ground untouched
- served flags-off face is oracle bytes
- served flags-on face adds loader
- agent enroll wraps atlas byte-for-byte
- lint clean over authored faces
- skill lint matches golden verdicts

### atl agent enroll --db <db> --dir <agents-dir>

Enroll agents (wraps `atlas agent enroll`).

```bash
node --experimental-strip-types atl/cli.ts agent enroll --db data/master.db --dir agents --dry
```

### atl agent orient --home <project>

Assemble orientation pack (wraps `atlas orient`).

```bash
node --experimental-strip-types atl/cli.ts agent orient --home .
```

### atl faces check

Verify faces match oracle pins.

```bash
node --experimental-strip-types atl/cli.ts faces check
# Output: FACE HOLDS (oracle bytes)
```

### atl faces serve --ground <ground> --port <port>

Serve faces from a ground.

```bash
node --experimental-strip-types atl/cli.ts faces serve --ground . --port 7788
```

### atl skill lint

Lint all skills against the SKILL.md spec.

```bash
node --experimental-strip-types atl/cli.ts skill lint
# Output: SKILL LINT CLEAN (9)
```

### atl lint

Lint all authored faces.

```bash
node --experimental-strip-types atl/cli.ts lint
# Output: LINT CLEAN
```

### atl gm list

List all registered stones.

```bash
node --experimental-strip-types atl/cli.ts gm list
# Output: A1 B1 C1 D1 D2 E1 F1
```

### atl gm run [--stone <S>]

Run the golden-master harness for one or all stones.

```bash
node --experimental-strip-types atl/cli.ts gm run --stone A1
# Output: PROVEN. 8/8 strokes green across 1 stone(s).
```

### atl bridge snapshot --ground <ground> --name <name>

Take a bridge snapshot.

```bash
node --experimental-strip-types atl/cli.ts bridge snapshot --ground . --name e2e-test
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success / all proves green |
| 1 | Error / one or more proves failed |
| 2 | Refusal (lawful no, not a bug) |
| -1 | Timeout |
| -2 | Exception (unexpected error) |
