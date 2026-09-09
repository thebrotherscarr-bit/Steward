//! atlas-store — state topology owner (SPEC_SQLITE).
//!
//! Seven databases, one concern each. This crate owns schema_migrations for
//! every DB; services never ALTER schema. The SQLite driver dependency
//! lands with the A1-06 stone; the frozen DDL below is the law it will
//! execute, kept verbatim so drift fails review before code exists.

pub mod driver;
pub mod enroll;
pub mod ffi;
pub mod import_export;
pub mod link;
pub mod migrations;
pub mod sync;
pub mod trade;

pub const RULINGS_DDL: &str = "CREATE TABLE IF NOT EXISTS rulings (\n  id INTEGER PRIMARY KEY,\n  dated TEXT NOT NULL,\n  title TEXT UNIQUE NOT NULL,\n  body TEXT NOT NULL)";

pub const CATALOG_DDL: &str = "CREATE TABLE IF NOT EXISTS catalog (\n  ref TEXT PRIMARY KEY,\n  section TEXT NOT NULL,\n  source_path TEXT,\n  source_lines INTEGER,\n  base_language TEXT NOT NULL,\n  artifact TEXT,\n  disposition TEXT NOT NULL CHECK (disposition IN\n    ('PORT','ADAPT','WRAP','KEEP','HARVEST','FOLD','NEW')),\n  stone TEXT,\n  notes TEXT)";

pub const AGENTS_DDL: &str = "CREATE TABLE IF NOT EXISTS agents (\n  id TEXT PRIMARY KEY,\n  us_path TEXT UNIQUE,\n  office TEXT,\n  reports_to TEXT,\n  can_approve INTEGER NOT NULL DEFAULT 0 CHECK (can_approve = 0),\n  enrolled_at TEXT,\n  covenant TEXT)";

pub const JOURNAL_SYNC_DDL: &str = "CREATE TABLE IF NOT EXISTS journal_sync (\n  chain_path TEXT PRIMARY KEY,\n  last_applied_n INTEGER NOT NULL,\n  applied_hash TEXT NOT NULL)";

pub const MIGRATIONS_DDL: &str = "CREATE TABLE IF NOT EXISTS schema_migrations (\n  version INTEGER PRIMARY KEY,\n  name TEXT UNIQUE NOT NULL,\n  applied_at TEXT NOT NULL)";

/// Append-only enforcement template (SPEC_SQLITE §Append-only):
/// event/ledger tables refuse UPDATE and DELETE by trigger.
pub fn append_only_trigger_ddl(table: &str) -> String {
    format!(
        "CREATE TRIGGER IF NOT EXISTS {table}_no_update \
         BEFORE UPDATE ON {table} BEGIN \
         SELECT RAISE(ABORT, 'append-only'); END;\n\
         CREATE TRIGGER IF NOT EXISTS {table}_no_delete \
         BEFORE DELETE ON {table} BEGIN \
         SELECT RAISE(ABORT, 'append-only'); END;"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn journal_sync_shape_matches_spec() {
        assert!(JOURNAL_SYNC_DDL.contains("chain_path TEXT PRIMARY KEY"));
        assert!(JOURNAL_SYNC_DDL.contains("last_applied_n INTEGER NOT NULL"));
        assert!(JOURNAL_SYNC_DDL.contains("applied_hash TEXT NOT NULL"));
    }

    #[test]
    fn agents_cannot_approve() {
        assert!(AGENTS_DDL.contains("CHECK (can_approve = 0)"));
    }

    #[test]
    fn triggers_raise_abort_append_only() {
        let ddl = append_only_trigger_ddl("rulings");
        assert!(ddl.contains("RAISE(ABORT, 'append-only')"));
        assert!(ddl.starts_with("CREATE TRIGGER IF NOT EXISTS rulings_no_update"));
    }
}
