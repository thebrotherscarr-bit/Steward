#!/usr/bin/env python3
"""seed_catalog.py -- create/verify atlas\\data\\master.db from THE_CATALOG.

Idempotent: rows key on `ref`; re-runs insert nothing new. --verify checks
row counts, disposition vocabulary, and the journal_sync schema. Stdlib only;
runs inside atlas\\.venv per CHARTER section 6.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "master.db"

DISPOSITIONS = {"PORT", "ADAPT", "WRAP", "KEEP", "HARVEST", "FOLD", "NEW"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS rulings (
  id INTEGER PRIMARY KEY,
  dated TEXT NOT NULL,
  title TEXT UNIQUE NOT NULL,
  body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalog (
  ref TEXT PRIMARY KEY,
  section TEXT NOT NULL,
  source_path TEXT,
  source_lines INTEGER,
  base_language TEXT NOT NULL,
  artifact TEXT,
  disposition TEXT NOT NULL CHECK (disposition IN
    ('PORT','ADAPT','WRAP','KEEP','HARVEST','FOLD','NEW')),
  stone TEXT,
  notes TEXT);
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  us_path TEXT UNIQUE,
  office TEXT,
  reports_to TEXT,
  can_approve INTEGER NOT NULL DEFAULT 0 CHECK (can_approve = 0),
  enrolled_at TEXT,
  covenant TEXT);
CREATE TABLE IF NOT EXISTS journal_sync (
  chain_path TEXT PRIMARY KEY,
  last_applied_n INTEGER NOT NULL,
  applied_hash TEXT NOT NULL);
"""

RULINGS = [
    ("2026-08-24", "Best-fit per component",
     "Each subsystem lives in its strongest language: Rust provenance, Go "
     "services, C++ kernels, TypeScript faces/tooling, JSON interchange, "
     "SQLite state."),
    ("2026-08-24", "Atlas lives beside the grounds",
     "C:\\Users\\novad\\Desktop\\Archive\\atlas\\ ; estate\\ and "
     "secondbrain\\ are read-only sources."),
    ("2026-08-24", "Strangler migration",
     "Python estate keeps running; golden-master byte-parity required before "
     "any per-service cutover through the same ports/commands."),
    ("2026-08-24", "Harvest the second brain",
     "Adopt patterns natively (Memory API v1 + split SQLite topology, "
     "SKILL.md spec, Guard/Redact/Scan, declarative deploys); no repo ported "
     "wholesale or wrapped."),
    ("2026-08-24", "Build discipline",
     "Implementation and testing move together; Python inside atlas\\.venv; "
     "every prove hermetic on temp ground; source grounds never written."),
]

# ref, section, source_path, lines, base_language, artifact, disposition, stone, notes
CATALOG = [
    # RUST
    ("R1","rust","estate\\Neiro\\lib\\us_canon.py",327,"rust","core/src/canon.rs","PORT","A1","BODY_V 1/2/3; JCS UTF-16-be keys; +-2^53-1 ints"),
    ("R2","rust","estate\\Neiro\\lib\\us_chain.py",609,"rust","core/src/chain.rs","PORT","A1","entry shape; EMPTY|INTACT|FLIP|TAMPER; wraps-every-40 Merkle"),
    ("R3","rust","estate\\Neiro\\lib\\prove_parity.py",287,"rust","core/src/forms.rs","PORT","A1","13 legacy FORMS recognition by trial"),
    ("R4","rust","estate\\Neiro\\lib\\us_read.py",434,"rust","core/src/us.rs","PORT","A1",".us grammar; can_approve:false refusal-not-default"),
    ("R5","rust","estate\\forge\\links\\bip340.py + jesster.py",694,"rust","core/src/schnorr.rs + keys.rs","PORT","A1","BIP-340; five-key derivation, halves never co-stored"),
    ("R6","rust","estate\\Steward 1.0\\link.py + neiro\\custody.py",None,"rust","cmd/link","ADAPT","D1","character-chain pen + custody signatures"),
    ("R7","rust","estate\\Manjuel manjuel.py fold + 5.0 fold.py",259,"rust","core/src/fold.rs","PORT","A1","secp256k1 relaxed-R1CS accumulator; domain tags kept"),
    ("R8","rust","estate\\Neiro\\Archive\\neiro\\merkle.py + 5.0 memory.py",335,"rust","core/src/merkle_dag.rs","PORT","A1","git-style body DAG; tamper pinpoint"),
    ("R9","rust","estate\\foundation (four docs)",41,"rust","core/src/covenant.rs","NEW","A1","construction A declared order; House mark 1512741580b7239b default; Elder 65118a147dd49ed9 legacy-only (--epoch elder)"),
    ("R10","rust","estate\\builder\\engine\\prove.py",53,"rust","core/src/blanks.rs","PORT","A2","no-placeholder scaffold proof"),
    ("R11","rust","estate\\Agent Skills\\board.py (ledger half)",451,"rust","store/src/import_board.rs","ADAPT","A1","escaped-ASCII V1 divergent form import"),
    ("R12","rust","estate\\forge\\gateway\\gateway.py",84,"rust","store/src/import_gateway.rs","ADAPT","A1","blake2b-32 events; shards consolidated"),
    ("R13","rust","36 live JSONL chains + workorders.db + mail_cache.sqlite3",None,"rust","store migrations + atlas db import/verify/export","NEW","A1","export regenerates byte-identical JSONL"),
    ("R14","rust","estate\\Neiro skills ark.py + scripts checkpoint.py",316,"rust","cmd/ark + cmd/deposit","PORT","F1","backups; token-ledger deposits"),
    ("R15","rust","estate\\vault.py + Manjuel auth.py cores",502,"rust","core/src/vault.rs","PORT","G-stone","pbkdf2 verbatim; HMAC session mint"),
    # GO
    ("G1","go","seat_mcp.py + Neiro lib us_mcp.py",None,"go","cmd/atlas-mcp","PORT","B1","one stdio MCP server; 10+ tool parity; forbidden verbs absent"),
    ("G2","go","estate\\Steward 1.0\\door.py (:8080)",453,"go","cmd/atlas-door","PORT","D2","badge rewalks chains via Rust verify"),
    ("G3","go","town.py + trade_tasks.py + river/clock/chancery",None,"go","cmd/atlas-town","PORT","D1","beat/flow jitter; REVIEW-gated; static no-approve check"),
    ("G4","go","estate\\Neiro Archive steward bob.py",328,"go","pkg/queue (atlas-town)","PORT","D1","durable claims; refusal escalates to morning review"),
    ("G5","go","commons board.py + Agent Skills board.py kit/mail",1370,"go","cmd/atlas-board","ADAPT","D1","three offices one ethics; two modes; separate chains"),
    ("G6","go","gatehouse.py + guardscan.py + fetch.py",1273,"go","pkg/gate + guardscan + guardfetch","PORT","B1","risk tiers chained; arg scan; private-IP refusal egress"),
    ("G7","go","watch.py sentinel + radar.py",864,"go","cmd/atlas-watch","PORT","C1","fingerprint/drift loops; SSE feed"),
    ("G8","go","aurora server.py (:7788)",518,"go","cmd/atlas-glass","KEEP","G-stone","strangler until G8; identical routes; console untouched"),
    ("G9","go","forge_server.py (:7375)",271,"go","cmd/atlas-forge","PORT","F1","HMAC token; /ascend 403-by-name"),
    ("G10","go","gateway.py + gateway.js twins",176,"go","cmd/atlas-gateway","ADAPT","F1","one broker absorbs both twins"),
    ("G11","go","wall.py (:HTTP MCP bearer)",724,"go","cmd/atlas-wall","PORT","G-stone","Streamable HTTP, loopback + bearer"),
    ("G12","go","harvest.py OAI-PMH daemon",56,"go","cmd/atlas-harvest","PORT","F1","resumable; 503-polite"),
    ("G13","go","CARR kernel message/bus/router/scheduler/service",467,"go","pkg/kernel","PORT","D3","Message protocol verbatim; asyncio->goroutines"),
    ("G14","go","CARR civic core town/citizen/quest/tribunal",776,"go","pkg/carr","PORT","D3","Citizen->Steward->Nerio->Operator ladder enforced"),
    ("G15","go","CARR offices + harness + shape + sandbox",915,"go","pkg/carr/offices","PORT","D3","planner/generator/evaluator/arbiter roots"),
    ("G16","go","CARR frontends.web (:8760 + WS)",573,"go","cmd/atlas-townweb","PORT","D3","zero-dep IDE served; bus-tap WebSocket"),
    ("G17","go","CARR spine (gated GitHub egress)",188,"go","cmd/atlas-spine","PORT","D3","world.egress witnessed; operator gate"),
    ("G18","go","platform runner/scheduler/cron/prompt/mcp_client",983,"go","pkg/runner + cron + mcpclient","PORT","G-stone","bounded loop; sub-agents one level deep"),
    ("G19","go","platform api handlers (~3300) + sessions",3300,"go","cmd/atlas-platform","PORT","G-stone","route-table pattern; sessions via R15"),
    ("G20","go","llm connectors + remote.py + scale.py",725,"go","pkg/llm","PORT","B1","Ollama :11434 first; testimony law both racks"),
    ("G21","go","victor Discord stack",1586,"go","cmd/atlas-victor","PORT","F1","pure-socket gateway, no SDK"),
    ("G22","go","panel.py load arithmetic",406,"go","cmd/atlas-panel","PORT","F1","breaker-box switching"),
    ("G23","go","puller.py doc extraction",210,"go","pkg/extract","ADAPT","F1","zip+xml natives"),
    ("G24","go","manjuel_us.py serve-half",540,"go","cmd/atlas-mirror","ADAPT","G-stone","read-only public mirror; append stays operator-hand"),
    ("G25","go","weigh pipeline + scale ask-pipeline + rack_router judge",None,"go","pkg/weigh","ADAPT","B1","settling; two-register sense floor; scoring via K1"),
    # CPP
    ("K1","cpp","manjuel grown models + 5.0 models.py",550,"cpp","kernels/libppmi","PORT","E1","PPMI embedder/trigram; int bit-exact, float tolerance specced"),
    ("K2","cpp","digest.py + Jesster library.py",1396,"cpp","kernels/libdigest","PORT","E1","streamed meal-folding; links via Rust pen"),
    ("K3","cpp","predictor.py",2201,"cpp","kernels/libpredictor","PORT","E1","64-dim expectation; >=10x benchmark"),
    ("K4","cpp","lexicon nearness + etymon scoring",452,"cpp","kernels/libsense","ADAPT","E1","morpheme tables to JSON; scoring native"),
    ("K5","cpp","steward library.py fold-at-scale",277,"cpp","kernels/foldall","ADAPT","E1","parallel N-reader batch"),
    ("K6","cpp","bench stations + mathwright contests",918,"cpp","kernels/bench","HARVEST","E1","proving target for speed claims"),
    # TS
    ("T1","ts","console.html + sprites.js",None,"ts","faces/console-v2","ADAPT","C1","additive behind flags; no second face"),
    ("T2","ts","Studio hub/ide html + Codex dashboards",None,"ts","faces/studio","ADAPT","C1","PIN-gate hub; consumes G16"),
    ("T3","ts","builder engine space/ask/fit/scaffold",571,"ts","@atl/builder","PORT","A2","enroll/interview; writes .us decls"),
    ("T4","ts","golden-master needs (new)",None,"ts","@atl/gm","NEW","A1","Python-vs-atlas hash differ"),
    ("T5","ts","23 opencode agent defs + skills.paths",None,"ts","@atl/wire","ADAPT","C1","reconciles opencode.json + 3x .mcp.json"),
    ("T6","ts","skills-main validate-skills.mjs pattern",None,"ts","@atl/skill lint","HARVEST","F1","SKILL.md spec enforced"),
    ("T7","ts","billboard worker.js (deployed edge)",125,"ts","(kept as deployed worker)","KEEP","G-stone","edge mirror, no authority"),
    # JSON
    ("J1","json","Agents.us + Neiro.us + observed behavior",None,"json","agents/*.us (~30 declarations)","NEW","A2","registry enrollment set"),
    ("J2","json","kit.json + SKILL.md frontmatter + fingerprints",None,"json","skills.db seed + shelf JSON","ADAPT","F1","feeds lint"),
    ("J3","json","opencode.json + 3x .mcp.json",None,"json","repointed configs","ADAPT","G-stone","operator-hand apply"),
    ("J4","json","superagent Guard/Redact/Scan templates",None,"json","packs/guard/*.json","HARVEST","F1","pipeline stages"),
    ("J5","json","SecondBrain Memory API v1 contract",None,"json","packs/memory_api.json","HARVEST","F1","citation envelopes"),
    ("J6","json","agentrun declarative deploy manifests",None,"json","packs/deploy.schema.json","HARVEST","F1","apply-style deploys"),
    ("J7","json","golden-master fixtures",None,"json","tests/fixtures/*","NEW","A1","cut from live chains BEFORE forms asserted"),
    ("J8","json","morpheme/sense rule tables",None,"json","packs/etymon.json","ADAPT","E1","data for K4"),
    # SQLITE DBs
    ("S1","sqlite","platform db.py P1-P6 (30 tables) + catalog",425,"sqlite","master.db","PORT","P0","append-only event tables; triggers refuse UPDATE/DELETE"),
    ("S2","sqlite","all live chains (derived index)",None,"sqlite","ledger.db","NEW","A1","JSONL stays canonical"),
    ("S3","sqlite","workorders.db + property/inspection/report",None,"sqlite","trade.db","ADAPT","D2","owner-report walks all three chains"),
    ("S4","sqlite","board ledgers + mail_cache.sqlite3",None,"sqlite","board.db","ADAPT","D1","mission mail rebuilt"),
    ("S5","sqlite","CARR 8-tier memory + SecondBrain topology",249,"sqlite","memory.db","HARVEST","F1","working/episodic/knowledge + citations"),
    ("S6","sqlite","catalog fingerprints + kit + rack",None,"sqlite","skills.db","NEW","F1","lint source of truth"),
    ("S7","sqlite","users/<id>/ledger.sqlite shards",None,"sqlite","gateway.db","ADAPT","A1","consolidated; user_id column"),
    # KEEP / FOLD
    ("KF1","keepfold","sealed heart manjuel.py 3.2.0 + kernel",1537,"python","(no twin; reached ask-only)","KEEP",None,"never edited; new engines call through the door"),
    ("KF2","keepfold","foundation + Doctrine + SEAT_LOG/THE_ROAD/WEIGH_RUNS",None,"md","(the record itself)","FOLD",None,"read-only law and history"),
    ("KF3","keepfold","attics, Manjuel-1, frozen mirrors, old gens",None,"mixed","(folded records)","FOLD",None,"kept whole, never ported"),
    ("KF4","keepfold","clawverse game + Aurora game + open-genspark app",None,"mixed","(reference only)","FOLD",None,"patterns at most"),
    ("KF5","keepfold","live Python estate processes during strangler",None,"python","(retired per G-stone)","KEEP","G-stone","fold note retires each, operator hand"),
]


def seed(conn: sqlite3.Connection) -> dict:
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    for dated, title, body in RULINGS:
        cur.execute(
            "INSERT OR IGNORE INTO rulings (dated, title, body) VALUES (?,?,?)",
            (dated, title, body),
        )
    for row in CATALOG:
        if row[6] not in DISPOSITIONS:
            raise ValueError(f"ref {row[0]}: disposition {row[6]!r} not in vocabulary")
        cur.execute(
            "INSERT OR IGNORE INTO catalog (ref, section, source_path,"
            " source_lines, base_language, artifact, disposition, stone, notes)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            row,
        )
    inserted = cur.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]
    if inserted < len(CATALOG):
        missing = {r[0] for r in CATALOG} - {
            x[0] for x in cur.execute("SELECT ref FROM catalog").fetchall()
        }
        raise ValueError(f"seed incomplete; refused/missing refs: {sorted(missing)}")
    conn.commit()
    return {
        "rulings": cur.execute("SELECT COUNT(*) FROM rulings").fetchone()[0],
        "catalog": cur.execute("SELECT COUNT(*) FROM catalog").fetchone()[0],
        "agents": cur.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
    }


def verify(conn: sqlite3.Connection) -> list:
    problems = []
    cur = conn.cursor()
    n_cat = cur.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]
    if n_cat < len(CATALOG):
        problems.append(f"catalog rows {n_cat} < expected {len(CATALOG)}")
    bad = cur.execute(
        "SELECT ref, disposition FROM catalog WHERE disposition NOT IN "
        "('PORT','ADAPT','WRAP','KEEP','HARVEST','FOLD','NEW')"
    ).fetchall()
    if bad:
        problems.append(f"bad dispositions: {bad}")
    dups = cur.execute(
        "SELECT source_path, COUNT(*) c FROM catalog WHERE source_path IS NOT"
        " NULL GROUP BY source_path HAVING c > 1"
    ).fetchall()
    if dups:
        problems.append(f"duplicate source paths: {dups}")
    names = {
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = {"rulings", "catalog", "agents", "journal_sync"} - names
    if missing:
        problems.append(f"missing tables: {sorted(missing)}")
    mode = cur.execute("PRAGMA journal_mode").fetchone()[0]
    if str(mode).lower() != "wal":
        problems.append(f"journal_mode is {mode}, expected wal")
    return problems


def reset(conn: sqlite3.Connection) -> None:
    """Drop everything. P0-only convenience while master.db holds no record
    of weight; after A1 lands, schema changes ride forward migrations."""
    cur = conn.cursor()
    names = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for n in names:
        cur.execute(f"DROP TABLE IF EXISTS {n}")
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="check only")
    ap.add_argument(
        "--reset", action="store_true",
        help="drop tables then reseed (P0 scratch only)")
    args = ap.parse_args()
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        if args.reset:
            reset(conn)
        counts = seed(conn)
        problems = verify(conn)
        print(
            f"master.db: rulings={counts['rulings']} catalog={counts['catalog']}"
            f" agents={counts['agents']} (empty until A2)"
        )
        if problems:
            for p in problems:
                print(f"VERIFY FAIL: {p}", file=sys.stderr)
            return 1
        print("VERIFY OK: dispositions valid, no dupes, schema complete, WAL on")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
