//! Schema ownership (SPEC_SQLITE §Migration ownership).
//!
//! atlas-store owns schema_migrations for every DB. Migrations are
//! forward-only, recorded with an applied_at stamp, and executed verbatim
//! from frozen constants so drift fails before code runs. Services never
//! ALTER schema.

use crate::driver::{Conn, Result, Step};
use crate::JOURNAL_SYNC_DDL;

/// RFC 3339 UTC, seconds — same shape us_chain stamps, computed without
/// external crates (days-from-civil inverse, Howard Hinnant's algorithm).
pub fn rfc3339_now() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0) as i64;
    let days = secs.div_euclid(86_400);
    let sod = secs.rem_euclid(86_400);
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y,
        m,
        d,
        sod / 3600,
        (sod % 3600) / 60,
        sod % 60
    )
}

pub const CHAINS_DDL: &str = "CREATE TABLE IF NOT EXISTS chains (\n  slug TEXT PRIMARY KEY,\n  source_path TEXT NOT NULL,\n  imported_at TEXT NOT NULL,\n  head TEXT NOT NULL,\n  entries INTEGER NOT NULL)";

pub const CHAIN_ENTRIES_DDL: &str = "CREATE TABLE IF NOT EXISTS chain_entries (\n  slug TEXT NOT NULL REFERENCES chains(slug),\n  n INTEGER NOT NULL,\n  line BLOB NOT NULL,\n  ts TEXT,\n  kind TEXT,\n  actor TEXT,\n  prev TEXT,\n  hash TEXT,\n  body_v INTEGER,\n  PRIMARY KEY (slug, n))";

#[derive(Debug, Clone)]
pub struct Migration {
    pub version: i64,
    pub name: &'static str,
    pub statements: Vec<String>,
}

/// The ledger.db core: chain mirror + sync pointer + append-only law.
/// `chain_entries` is the lawful mirror and refuses UPDATE/DELETE;
/// `chains` is DERIVED summary state (fold(record)) and stays mutable
/// by definition — the replay refreshes it inside each transaction.
pub fn ledger_migrations() -> Vec<Migration> {
    vec![Migration {
        version: 1,
        name: "ledger_core",
        statements: vec![
            CHAINS_DDL.to_string(),
            CHAIN_ENTRIES_DDL.to_string(),
            JOURNAL_SYNC_DDL.to_string(),
            crate::append_only_trigger_ddl("chain_entries"),
        ],
    }]
}

fn have_table(conn: &Conn, table: &str) -> Result<bool> {
    let stmt = conn.prepare(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?;",
    )?;
    stmt.bind_text(1, table)?;
    let yes = match stmt.step()? {
        Step::Row => stmt.int64(0) > 0,
        Step::Done => false,
    };
    drop(stmt);
    Ok(yes)
}

fn ensure_registry(conn: &Conn) -> Result<()> {
    if !have_table(conn, "schema_migrations")? {
        conn.exec(crate::MIGRATIONS_DDL)?;
    }
    Ok(())
}

/// Forward-only application of every migration not yet recorded.
/// Each migration runs inside one transaction; its row is recorded inside
/// the same transaction (the registry cannot lie about a half-applied set).
pub fn apply_migrations(conn: &Conn, migrations: &[Migration]) -> Result<Vec<(i64, &'static str)>> {
    ensure_registry(conn)?;
    let mut done = Vec::new();
    for m in migrations {
        let stmt = conn.prepare("SELECT count(*) FROM schema_migrations WHERE version=?;")?;
        stmt.bind_int64(1, m.version)?;
        let already = match stmt.step()? {
            Step::Row => stmt.int64(0) > 0,
            Step::Done => false,
        };
        drop(stmt);
        if already {
            continue;
        }
        conn.exec("BEGIN IMMEDIATE;")?;
        for sql in &m.statements {
            if let Err(e) = conn.exec(sql) {
                let _ = conn.exec("ROLLBACK;");
                return Err(e);
            }
        }
        let ins = conn.prepare(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
        )?;
        ins.bind_int64(1, m.version)?;
        ins.bind_text(2, m.name)?;
        ins.bind_text(3, &rfc3339_now())?;
        let step_r = ins.step();
        drop(ins);
        step_r?;
        conn.exec("COMMIT;")?;
        done.push((m.version, m.name));
    }
    Ok(done)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::Conn;

    fn temp(tag: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let dir = std::env::temp_dir().join(format!("atlas_mig_{tag}_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        (dir.clone(), dir.join("ledger.db"))
    }

    #[test]
    fn migrations_apply_forward_only_and_idempotent() {
        let (dir, path) = temp("idem");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        let migs = ledger_migrations();
        assert_eq!(apply_migrations(&conn, &migs).unwrap().len(), 1);
        // Second run: nothing new.
        assert_eq!(apply_migrations(&conn, &migs).unwrap().len(), 0);
        // Registry says v1 once.
        let q = conn
            .prepare("SELECT count(*) FROM schema_migrations WHERE version=1 AND name='ledger_core';")
            .unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn triggers_refuse_update_and_delete_by_name() {
        let (dir, path) = temp("trig");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        apply_migrations(&conn, &ledger_migrations()).unwrap();
        // Parent row first: the mirror's FK demands it exist.
        conn.exec("INSERT INTO chains (slug, source_path, imported_at, head, entries) VALUES ('s', 'p', '2026-08-25T00:00:00Z', 'h', 0);").unwrap();
        conn.exec("INSERT INTO chain_entries (slug, n, line) VALUES ('s', 1, x'7b7d');").unwrap();

        let up2 = conn.exec("UPDATE chain_entries SET line=x'00';").unwrap_err();
        assert!(up2.msg.contains("append-only"), "{:?}", up2);
        let de = conn.exec("DELETE FROM chain_entries;").unwrap_err();
        assert!(de.msg.contains("append-only"), "{:?}", de);
        // The DERIVED summary stays mutable — state folds from the record.
        conn.exec("UPDATE chains SET entries=1 WHERE slug='s';").unwrap();
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rust_sqlite_reads_what_python_wrote_master_copy_stroke() {
        // Cross-version proof: 3.51.1 opens the DB Python's 3.50.4 wrote,
        // and P0's seed law still holds behind Rust eyes.
        let src = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("data")
            .join("master.db");
        let dir = std::env::temp_dir().join(format!("atlas_master_copy_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let copy = dir.join("master_copy.db");
        std::fs::copy(&src, &copy).expect("master.db present");
        let ro = Conn::open_readonly(&copy).unwrap();
        for (table, want) in [("catalog", 73i64), ("rulings", 5)] {
            let q = ro.prepare(&format!("SELECT count(*) FROM {table};")).unwrap();
            assert!(matches!(q.step().unwrap(), Step::Row), "{table}");
            assert_eq!(q.int64(0), want, "{table}");
        }
        // WAL survived the trip (P0-02's observation, re-seen through FFI).
        {
            let q = ro.prepare("PRAGMA journal_mode;").unwrap();
            assert!(matches!(q.step().unwrap(), Step::Row));
            assert_eq!(q.text(0).unwrap(), "wal");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn foreign_keys_law_enforces_the_entry_side_of_the_mirror() {
        let (dir, path) = temp("fk");
        let _ = std::fs::remove_file(&path);
        let conn = Conn::open(&path).unwrap();
        conn.apply_connection_law().unwrap();
        apply_migrations(&conn, &ledger_migrations()).unwrap();
        // No chains row named 'ghost' exists: FK ON refuses the orphan.
        let err = conn.exec("INSERT INTO chain_entries (slug, n, line) VALUES ('ghost', 1, x'7b7d');").unwrap_err();
        assert!(err.msg.to_lowercase().contains("foreign key"), "{:?}", err);
        std::fs::remove_dir_all(&dir).ok();
    }
}
