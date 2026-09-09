# SPEC_SQLITE — state topology reference

*Frozen reference for A1/A2 and all service stones. Seven databases, one
concern each.*

## Databases

| DB | Path | Absorbs | Notes |
|---|---|---|---|
| master.db | `atlas\data\master.db` | platform db.py P1–P6 (30 tables), catalog dispositions, agent registry | append-only event tables |
| ledger.db | `data\ledger.db` | verified imports of all live chains | derived index; JSONL stays canonical |
| trade.db | `data\trade.db` | workorders.db + property/inspection/report records | owner-report walks all chains |
| board.db | `data\board.db` | commons/taskmaster ledgers, mail_cache.sqlite3, inbox/outbox | mission mail rebuilt here |
| memory.db | `data\memory.db` | CARR 8-tier memory + SecondBrain split-topology pattern | working/episodic/knowledge + citation envelopes |
| skills.db | `data\skills.db` | catalog fingerprints, kit.json, rack installs | feeds @atl skill lint |
| gateway.db | `data\gateway.db` | sharded users\<id>\ledger.sqlite | consolidated; user_id column |

## Disposition vocabulary

`PORT` rewrite natively · `ADAPT` port reshaped · `WRAP` keep running,
bridge to it · `KEEP` strangler (Python until its cutover stone) · `HARVEST`
adopt pattern only · `FOLD` record/history, never ported · `NEW` written
fresh (no direct source module). The seeder validates vocabulary BEFORE
insert and refuses loudly on any row outside it — a CHECK-only guard fails
silently under INSERT OR IGNORE (paid lesson, P0).

## Connection law

WAL mode (`PRAGMA journal_mode=WAL`) · `synchronous=FULL` for DBs that sit on
the write path of a chain · foreign_keys ON · busy_timeout set · single
writer per DB (mirrors the estate's one-hash-chain caution). Services open
read-only connections wherever possible.

## Journaled-ledger sync (the write path)

SQLite state and the JSONL journals are one system, bound by this order:

1. **Record first, state second.** Every mutation appends its entry to the
   journaled ledger (the JSONL chain, through the Rust pen) BEFORE the
   SQLite transaction commits. If the append refuses, nothing lands in
   SQLite.
2. **Sync pointer.** Each DB carries a `journal_sync` table:
   `(chain_path TEXT PRIMARY KEY, last_applied_n INTEGER, applied_hash TEXT)`.
   A commit updates the pointer in the same transaction.
3. **Replay on open.** At service start: verify Manjuel (must be INTACT),
   read the sync pointer, replay every entry past `last_applied_n` into the
   derived tables idempotently (keyed by entry `n`), advance the pointer.
   State is always re-derivable: state = fold(record).
4. **Refuse on break.** Chain verdict FLIP or TAMPER → the service serves
   reads only, names the break, and accepts no writes until the operator
   rules.
5. **Checkpointing.** WAL autocheckpoint stays default; after each wrap
   close (every 40 links) the writer issues an explicit `wal_checkpoint
   (PASSIVE)` and walks the wrap's Merkle consistency proof before
   continuing.
6. **Crash window.** A crash between journal append and SQLite commit is
   healed by rule 3 on next open; a crash mid-SQLite-transaction rolls back
   and replays. Either way the record never contains a state the journal
   does not justify.

## Append-only enforcement

- Event/ledger tables get triggers: `BEFORE UPDATE` and `BEFORE DELETE`
  → `RAISE(ABORT, 'append-only')`.
- The store API exposes append + read paths only; corrections are new
  entries (fold, never delete).
- CI lint: no UPDATE/DELETE against protected tables anywhere in the tree.

## Migration ownership

`atlas-store` (Rust) owns schema_migrations for every DB. Services never
ALTER schema; they consume migrations' resulting shapes. Migrations are
forward-only; a bad migration is folded by a corrective forward migration.

## master.db seed schema (P0)

```sql
CREATE TABLE IF NOT EXISTS rulings (
  id INTEGER PRIMARY KEY, dated TEXT NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalog (
  ref TEXT PRIMARY KEY,              -- R1..R15, G1..G25, K1..K6, T1..T7, J1..J8, S1..S7
  section TEXT NOT NULL,             -- rust|go|cpp|ts|json|sqlite|keepfold
  source_path TEXT, source_lines INTEGER,
  base_language TEXT NOT NULL,
  artifact TEXT,
  disposition TEXT NOT NULL CHECK (disposition IN
    ('PORT','ADAPT','WRAP','KEEP','HARVEST','FOLD','NEW')),
  stone TEXT,                        -- P0,A1,A2,B1,C1,D1,D2,E1,F1,G1,G-stone
  notes TEXT);
CREATE TABLE IF NOT EXISTS agents (   -- filled at A2
  id TEXT PRIMARY KEY, us_path TEXT UNIQUE, office TEXT,
  reports_to TEXT, can_approve INTEGER NOT NULL DEFAULT 0 CHECK (can_approve = 0),
  enrolled_at TEXT, covenant TEXT);
CREATE TABLE IF NOT EXISTS journal_sync (
  chain_path TEXT PRIMARY KEY,
  last_applied_n INTEGER NOT NULL,
  applied_hash TEXT NOT NULL);
```

## Export law

Every imported chain keeps its export view; `atlas db export <chain>` must
regenerate byte-identical JSONL (golden-master asserted). SQLite is derived;
the record remains Manjuel.

## Prove requirements

Triggers refuse UPDATE/DELETE (named abort) · WAL+FK settings observed ·
seed re-runs idempotent · export round-trips three sampled chains.
