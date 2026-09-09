//! Agent enrollment (THE_CATALOG R-row · SPEC_US §Atlas additions ·
//! ACCEPTANCE A2-03).
//!
//! Enrollment requires: parse clean · validate pass · covenant cited ·
//! `can_approve:false` · resolvable `reports_to`. The agents table's own
//! CHECK backs the door structurally (can_approve = 0, no exceptions —
//! even the operator's row). Undeclared actors are refused context by name.

use std::path::{Path, PathBuf};

use crate::driver::{Conn, Result, Step, StoreError};
#[cfg(test)]
use std::fs;
use crate::migrations::rfc3339_now;
use atlas_core::json::Json;
use atlas_core::us;

pub struct EnrollReport {
    pub files_read: usize,
    pub modules: usize,
    pub enrolled: Vec<String>,
    pub skipped_existing: usize,
    pub refused: Vec<String>,
    pub dry_run: bool,
}

struct Loaded {
    path: PathBuf,
    module_id: Option<String>,
    agents: Vec<Json>,
}

fn collect(dir: &Path) -> Result<Vec<Loaded>> {
    let mut out = Vec::new();
    let mut paths: Vec<PathBuf> = std::fs::read_dir(dir)
        .map_err(|e| StoreError {
            code: -1,
            msg: format!("cannot read agents dir {}: {}", dir.display(), e),
        })?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("us"))
        .collect();
    paths.sort();
    if paths.is_empty() {
        return Err(StoreError {
            code: -1,
            msg: format!("no .us declarations under {}", dir.display()),
        });
    }
    for p in paths {
        let doc = us::load(&p).map_err(|e| StoreError {
            code: -1,
            msg: format!("{}: {}", p.display(), e),
        })?;
        let module_id = match us::declaration(&doc) {
            Ok(m) => m.get("id").and_then(Json::as_str).map(str::to_string),
            Err(_) => None,
        };
        let agents = us::roster(&doc).map_err(|e| StoreError {
            code: -1,
            msg: format!("{}: {}", p.display(), e),
        })?;
        out.push(Loaded { path: p, module_id, agents });
    }
    Ok(out)
}

/// Enroll every declared agent under `dir` into the master DB.
/// Idempotent: existing ids are left untouched (fold, never overwrite).
pub fn enroll_dir(db_path: &Path, dir: &Path, dry_run: bool) -> Result<EnrollReport> {
    let loaded = collect(dir)?;

    // Registry universe for reports_to resolution: every module id and
    // agent id across ALL declarations, plus the operator (who needs no
    // one's leave).
    let mut universe: Vec<String> = vec!["operator".to_string()];
    for l in &loaded {
        if let Some(m) = &l.module_id {
            universe.push(m.clone());
        }
        for a in &l.agents {
            if let Some(id) = a.get("id").and_then(Json::as_str) {
                universe.push(id.to_string());
            }
        }
    }

    let conn = Conn::open(db_path)?;
    conn.apply_connection_law()?;

    // The registry lives in master.db's agents table (P0 seed schema).
    let have_agents = {
        let q = conn.prepare(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='agents';",
        )?;
        matches!(q.step()?, Step::Row) && q.int64(0) > 0
    };
    if !have_agents {
        return Err(StoreError {
            code: -1,
            msg: "master db has no agents table (run the P0 seed first)"
                .into(),
        });
    }

    let mut report = EnrollReport {
        files_read: loaded.len(),
        modules: loaded.iter().filter(|l| l.module_id.is_some()).count(),
        enrolled: Vec::new(),
        skipped_existing: 0,
        refused: Vec::new(),
        dry_run: dry_run,
    };

    // A dry run is a real transaction that answers to ROLLBACK - the only
    // way the would-list can be trusted.
    conn.exec("BEGIN IMMEDIATE;")?;

    let ins_result = (|| -> Result<()> {
        let ins = conn.prepare(
            "INSERT INTO agents (id, us_path, office, reports_to, can_approve, \
             enrolled_at, covenant) VALUES (?, ?, ?, ?, 0, ?, ?) \
             ON CONFLICT(id) DO NOTHING;",
        )?;
        for l in &loaded {
            for a in &l.agents {
                let id = a.get("id").and_then(Json::as_str).unwrap_or("").to_string();
                let office =
                    a.get("office").and_then(Json::as_str).unwrap_or("").to_string();
                let reports_to =
                    a.get("reports_to").and_then(Json::as_str).unwrap_or("");
                let covenant =
                    a.get("covenant").and_then(Json::as_str).unwrap_or("");

                // Enrollment law beyond validate(): covenant cited and
                // reports_to resolvable within the declared universe.
                if covenant.is_empty() {
                    report.refused.push(format!(
                        "{}: no covenant cited",
                        id
                    ));
                    continue;
                }
                if !universe.iter().any(|u| u == reports_to) {
                    report.refused.push(format!(
                        "{}: reports_to {:?} resolves to nothing",
                        id, reports_to
                    ));
                    continue;
                }

                ins.reset().ok();
                ins.bind_text(1, &id)?;
                ins.bind_text(2, &l.path.to_string_lossy())?;
                ins.bind_text(3, &office)?;
                ins.bind_text(4, reports_to)?;
                ins.bind_text(5, &rfc3339_now())?;
                ins.bind_text(6, covenant)?;
                match ins.step() {
                    Ok(Step::Done) | Ok(Step::Row) => {}
                    Err(e) => return Err(e),
                }
                if conn.changes() > 0 {
                    report.enrolled.push(id);
                } else {
                    report.skipped_existing += 1;
                }
            }
        }
        Ok(())
    })();

    match ins_result {
        Ok(()) => {
            if dry_run {
                conn.exec("ROLLBACK;")?;
            } else {
                conn.exec("COMMIT;")?;
            }
        }
        Err(e) => {
            let _ = conn.exec("ROLLBACK;");
            return Err(e);
        }
    }
    Ok(report)
}

/// The context door: an undeclared actor is refused, by name.
pub fn require_enrolled(conn: &Conn, actor: &str) -> Result<()> {
    let q = conn.prepare("SELECT count(*) FROM agents WHERE id=?;")?;
    q.bind_text(1, actor)?;
    let known = matches!(q.step()?, Step::Row) && q.int64(0) > 0;
    drop(q);
    if known {
        Ok(())
    } else {
        Err(StoreError {
            code: -1,
            msg: format!(
                "actor {:?} is not enrolled: no context without a declaration \
                 (atlas agent enroll first)",
                actor
            ),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::Conn;

    fn master_copy(tag: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let src = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("data")
            .join("master.db");
        let dir = std::env::temp_dir()
            .join(format!("atlas_enroll_{}_{}", tag, std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let dst = dir.join("master_copy.db");
        fs::copy(&src, &dst).expect("master.db present");
        (dir, dst)
    }

    fn agents_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("agents")
    }

    #[test]
    fn household_enrolls_into_a_master_copy_and_is_idempotent() {
        let (dir, db) = master_copy("t");
        // Hermetic: the live master.db already carries the household, so start
        // the copy empty — the test proves enrollment, not the live DB's past.
        Conn::open(&db).unwrap().exec("DELETE FROM agents;").unwrap();
        let rep = enroll_dir(&db, &agents_dir(), false).unwrap();
        assert_eq!(rep.files_read, 40, "40 enrollable single-seat files");
        assert!(
            rep.enrolled.len() >= 30,
            "enrolled {} refused {:?}",
            rep.enrolled.len(),
            rep.refused
        );
        assert!(rep.refused.is_empty(), "{:?}", rep.refused);

        let conn = Conn::open_readonly(&db).unwrap();
        let after_first = {
            let q = conn.prepare("SELECT count(*) FROM agents;").unwrap();
            assert!(matches!(q.step().unwrap(), Step::Row));
            q.int64(0)
        };

        // Re-run: fold, never overwrite; counts unchanged.
        drop(conn);
        let rep2 = enroll_dir(&db, &agents_dir(), false).unwrap();
        assert!(rep2.enrolled.is_empty());
        assert_eq!(rep2.skipped_existing as i64, after_first);

        let conn = Conn::open_readonly(&db).unwrap();
        let q = conn
            .prepare("SELECT count(*) FROM agents WHERE can_approve != 0;")
            .unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 0, "invariant 6: nobody approves");

        // The tribes sit under manjuel; the operator row exists.
        let q = conn
            .prepare("SELECT count(*) FROM agents WHERE office LIKE 'MANJUEL/%';")
            .unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 12, "the Twelve Tribes");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn dry_run_writes_nothing() {
        let (dir, db) = master_copy("d");
        Conn::open(&db).unwrap().exec("DELETE FROM agents;").unwrap();
        // The dry-run promise: no ROW lands. (The connection law itself may
        // touch WAL state - what must not change is the registry.)
        let count = |p: &PathBuf| {
            let c = Conn::open_readonly(p).unwrap();
            let q = c.prepare("SELECT count(*) FROM agents;").unwrap();
            matches!(q.step().unwrap(), Step::Row);
            q.int64(0)
        };
        let before = count(&db);
        let rep = enroll_dir(&db, &agents_dir(), true).unwrap();
        assert!(!rep.enrolled.is_empty(), "dry run still reports would-list");
        let after = count(&db);
        assert_eq!(before, after, "dry run enrolled rows");
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn undeclared_actors_are_refused_context_by_name() {
        let (dir, db) = master_copy("u");
        Conn::open(&db).unwrap().exec("DELETE FROM agents;").unwrap();
        enroll_dir(&db, &agents_dir(), false).unwrap();
        let conn = Conn::open_readonly(&db).unwrap();
        assert!(require_enrolled(&conn, "levi").is_ok());
        let err = require_enrolled(&conn, "stranger").unwrap_err();
        assert!(err.msg.contains("not enrolled"), "{:?}", err);
        assert!(err.msg.contains("stranger"));
        std::fs::remove_dir_all(&dir).ok();
    }
}
