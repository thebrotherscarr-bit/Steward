//! Import/export law (SPEC_SQLITE §Export law · ACCEPTANCE A1-04).
//!
//! Import verifies the chain INTACT first (rule 4 inherited), then mirrors
//! raw line bytes plus parsed index columns. Export regenerates JSONL from
//! those bytes by ordinal — byte-identical or it refuses. SQLite is
//! derived; the record remains the chain.

use std::path::Path;

use crate::driver::{Conn, Result, Step, StoreError};
use crate::sync::{pointer_key, replay_chain};
use atlas_core::chain::{read_rows, verify_rows};

#[derive(Debug)]
pub struct ImportReport {
    pub slug: String,
    pub lines: usize,
    pub inserted_now: usize,
    pub wraps_walked: usize,
    pub head: Option<String>,
}

/// Lawful import of one chain into ledger.db.
pub fn import_chain(db_path: &Path, slug: &str, chain_path: &Path) -> Result<ImportReport> {
    // Rule 1/4: the chain speaks before any write lands.
    let text = std::fs::read_to_string(chain_path)
        .map_err(|e| StoreError {
            code: -1,
            msg: format!("cannot read {}: {}", chain_path.display(), e),
        })?;
    let verdict = verify_rows(&read_rows(&text));
    // Two lawful doors, mirroring both provers' semantics:
    //   * a stamped (BODY_V-carrying) chain must verify INTACT/EMPTY;
    //   * a legacy chain is admitted when recognition-by-trial matches
    //     EVERY entry and the weld holds — the V3-world prover reading an
    //     unstamped projection as all-flip is the recorded split, not a break.
    {
        let rows = read_rows(&text);
        let rec = atlas_core::forms::recognize_rows(&rows);
        let lawful = match verdict.verdict {
            atlas_core::chain::Verdict::Intact | atlas_core::chain::Verdict::Empty => true,
            atlas_core::chain::Verdict::Flip => rec.whole && rec.weld_ok,
            atlas_core::chain::Verdict::Tamper => false,
        };
        if !lawful {
            return Err(StoreError {
                code: -1,
                msg: format!(
                    "import refused: verdict {} (flips={:?}, broke_at={:?}); \
                     form={:?} matched {}/{} weld_ok={}",
                    verdict.verdict.as_str(),
                    verdict.flips,
                    verdict.broke_at,
                    rec.form,
                    rec.matched,
                    rec.entries,
                    rec.weld_ok
                ),
            });
        }
    }

    // Open through the law (migrations + connection pragmas), then mirror.
    // replay_chain seeds and folds the derived `chains` row itself, inside
    // its transaction, so FK ordering can never invert.
    let conn = Conn::open(db_path)?;
    conn.apply_connection_law()?;
    crate::migrations::apply_migrations(&conn, &crate::migrations::ledger_migrations())?;
    let key = pointer_key(chain_path);
    let report = replay_chain(&conn, slug, &key, &text)?;

    Ok(ImportReport {
        slug: slug.to_string(),
        lines: report.total_lines,
        inserted_now: report.inserted_now,
        wraps_walked: report.wraps_walked,
        head: report.head,
    })
}

/// Export law: the mirror regurgitates its bytes by ordinal.
pub fn export_chain(db_path: &Path, slug: &str) -> Result<Vec<u8>> {
    let conn = Conn::open_readonly(db_path)?;
    let mut out: Vec<u8> = Vec::new();
    let stmt =
        conn.prepare("SELECT line FROM chain_entries WHERE slug=? ORDER BY n;")?;
    stmt.bind_text(1, slug)?;
    loop {
        match stmt.step()? {
            Step::Row => {
                out.extend_from_slice(&stmt.blob(0));
                out.push(b'\n');
            }
            Step::Done => break,
        }
    }
    Ok(out)
}

/// The A1-04 stroke shape: export must equal the reference file's bytes.
pub fn export_matches(db_path: &Path, slug: &str, reference: &Path) -> Result<bool> {
    let exported = export_chain(db_path, slug)?;
    let want = std::fs::read(reference).map_err(|e| StoreError {
        code: -1,
        msg: format!("cannot read reference {}: {}", reference.display(), e),
    })?;
    Ok(exported == want)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(rel: &str) -> std::path::PathBuf {
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("tests")
            .join("fixtures")
            .join(rel)
    }

    fn temp(tag: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("atlas_ie_{tag}_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn round_trip_is_byte_identical_on_the_approved_trio() {
        let dir = temp("trio");
        let db = dir.join("ledger.db");
        for (slug, file) in [
            ("agents_seatlog", "chains/agents_seatlog.jsonl"),
            ("forge_links_chain", "chains/forge_links_chain.jsonl"),
            ("steward_ledger", "chains/steward_ledger.head46.jsonl"),
        ] {
            let src = fixture(file);
            let rep = import_chain(&db, slug, &src).unwrap();
            assert!(rep.lines > 0, "{}", slug);
            assert!(export_matches(&db, slug, &src).unwrap(), "{} bytes differ", slug);
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn import_refuses_a_flipped_ground_by_name() {
        let dir = temp("flip");
        let db = dir.join("ledger.db");
        // Forge a flipped copy on temp ground: structurally mutate the
        // first entry's actor through our own canon (V2 text, same tree).
        let good = fixture("chains/agents_seatlog.jsonl");
        let text = std::fs::read_to_string(&good).unwrap();
        let flipped_path = dir.join("flipped.jsonl");
        let mut out_lines: Vec<String> = Vec::new();
        for (i, line) in text.lines().enumerate() {
            if i == 0 {
                let mut e = atlas_core::json::parse(line).unwrap();
                if let atlas_core::json::Json::Obj(pairs) = &mut e {
                    for (k, v) in pairs.iter_mut() {
                        if k == "actor" {
                            *v = atlas_core::json::Json::Str("golden-flip".into());
                        }
                    }
                }
                out_lines.push(
                    atlas_core::canon::canon(&e, atlas_core::canon::BODY_V_LINKS).unwrap(),
                );
            } else {
                out_lines.push(line.to_string());
            }
        }
        let mutated = out_lines.join("\n") + "\n";
        std::fs::write(&flipped_path, &mutated).unwrap();
        // Confirm the mutation actually flips under our own prover first.
        let v = verify_rows(&read_rows(&mutated));
        assert_eq!(v.verdict, atlas_core::chain::Verdict::Flip, "fixture mutation did not flip; pick another byte");
        let err = import_chain(&db, "flipped", &flipped_path).unwrap_err();
        assert!(err.msg.contains("import refused"), "{:?}", err);
        assert!(err.msg.contains("FLIP"));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn status_shape_reports_chains_and_pointers() {
        let dir = temp("status");
        let db = dir.join("ledger.db");
        let src = fixture("chains/agents_seatlog.jsonl");
        import_chain(&db, "agents_seatlog", &src).unwrap();

        let conn = Conn::open_readonly(&db).unwrap();
        let q = conn.prepare("SELECT count(*) FROM chains WHERE slug='agents_seatlog';").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 1);
        let q = conn.prepare("SELECT last_applied_n FROM journal_sync;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 2); // the seatlog holds two entries
        std::fs::remove_dir_all(&dir).ok();
    }
}
