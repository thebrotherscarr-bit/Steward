//! Journaled-ledger sync (THE_CATALOG S-row · SPEC_SQLITE §Journaled-ledger
//! sync). Every rule of the write path lands here as named code:
//!
//!   1 record-first   — nothing reaches SQLite unless the chain verified;
//!                      refusals happen BEFORE any transaction opens.
//!   2 sync pointer   — journal_sync advances inside the same transaction
//!                      as the mirrored lines.
//!   3 replay-on-open — entries past the pointer replay idempotently
//!                      (INSERT OR IGNORE keyed by ordinal); a second
//!                      replay is a no-op.
//!   4 refuse-on-break— FLIP/TAMPER ground opens READ-ONLY carrying the why.
//!   5 checkpoint     — after any wrap crosses, wal_checkpoint(PASSIVE) is
//!                      issued AND the wrap's Merkle consistency proof is
//!                      walked before continuing.
//!   6 crash window   — healed by rule 3 (proven by simulating an entry
//!                      appended-but-not-mirrored).

use std::path::Path;

use crate::driver::{Conn, Result, Step};
use crate::migrations::{apply_migrations, ledger_migrations};
use atlas_core::chain::{read_rows, verify_rows, Row, VerifyReport};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ServiceMode {
    ReadWrite,
    /// Refuse-on-break: reads only, carrying the reason until ruled.
    ReadOnly(String),
}

#[derive(Debug, Clone)]
pub struct ReplayReport {
    pub total_lines: usize,
    pub inserted_now: usize,
    pub already_mirrored: usize,
    pub wraps_walked: usize,
    pub head: Option<String>,
}

/// One lawful open of a derived store against a chain ground.
pub struct LedgerService {
    pub conn: Conn,
    pub mode: ServiceMode,
    pub verdict: VerifyReport,
}

pub fn pointer_key(chain_path: &Path) -> String {
    // SPEC_SQLITE keys journal_sync by chain_path; canonicalize so the
    // same ground reached by two spellings shares one pointer.
    chain_path
        .canonicalize()
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_else(|_| chain_path.to_string_lossy().into_owned())
}

pub fn open_service(
    db_path: &Path,
    slug: &str,
    chain_path: &Path,
) -> Result<LedgerService> {
    let text = std::fs::read_to_string(chain_path)
        .map_err(|e| crate::driver::StoreError {
            code: -1,
            msg: format!("cannot read chain {}: {}", chain_path.display(), e),
        })?;
    let rows = read_rows(&text);
    let verdict = verify_rows(&rows);

    let conn = Conn::open(db_path)?;
    conn.apply_connection_law()?;
    apply_migrations(&conn, &ledger_migrations())?;

    let mode = match verdict.verdict {
        atlas_core::chain::Verdict::Empty => ServiceMode::ReadWrite,
        atlas_core::chain::Verdict::Intact => ServiceMode::ReadWrite,
        atlas_core::chain::Verdict::Flip => ServiceMode::ReadOnly(format!(
            "refuse-on-break: chain FLIP at {:?} — serve reads only until the operator rules",
            verdict.flips
        )),
        atlas_core::chain::Verdict::Tamper => ServiceMode::ReadOnly(format!(
            "refuse-on-break: chain TAMPER at {:?} — serve reads only until the operator rules",
            verdict.broke_at
        )),
    };

    if mode == ServiceMode::ReadWrite {
        replay_chain(&conn, slug, &pointer_key(chain_path), &text)?;
    }

    Ok(LedgerService {
        conn,
        mode,
        verdict,
    })
}

pub fn read_pointer(conn: &Conn, key: &str) -> Result<Option<(i64, String)>> {
    let stmt =
        conn.prepare("SELECT last_applied_n, applied_hash FROM journal_sync WHERE chain_path=?;")?;
    stmt.bind_text(1, key)?;
    let out = match stmt.step()? {
        Step::Row => Some((stmt.int64(0), stmt.text(1)?)),
        Step::Done => None,
    };
    drop(stmt);
    Ok(out)
}

/// Rules 2+3: idempotent mirror of every RAW line byte (the record stays
/// canonical — no re-serialisation), pointer advanced inside the same
/// transaction, then rule 5 across any wrap the replay crossed.
pub fn replay_chain(conn: &Conn, slug: &str, key: &str, chain_text: &str) -> Result<ReplayReport> {
    // Raw segments first: the mirror stores what the record says, verbatim —
    // including CRLF endings where the estate wrote them (split on \n keeps
    // each segment's trailing \r; export rejoins with \n and reproduces it).
    let raw_segments: Vec<&str> = chain_text
        .split('\n')
        .filter(|l| !l.trim().is_empty())
        .collect();

    let prior = read_pointer(conn, key)?;
    let start_at = prior.as_ref().map(|(n, _)| *n as usize).unwrap_or(0);

    let mut inserted = 0usize;
    let mut wraps_crossed: Vec<usize> = Vec::new();

    conn.exec("BEGIN IMMEDIATE;")?;
    // Ensure the derived parent row exists BEFORE entries land (FK law);
    // it is refreshed with the final head/count inside this same txn.
    {
        let seed = conn.prepare(
            "INSERT INTO chains (slug, source_path, imported_at, head, entries) \
             VALUES (?, ?, ?, '', 0) ON CONFLICT(slug) DO NOTHING;",
        );
        let seed = match seed {
            Ok(s) => s,
            Err(e) => {
                let _ = conn.exec("ROLLBACK;");
                return Err(e);
            }
        };
        seed.bind_text(1, slug)?;
        seed.bind_text(2, key)?;
        seed.bind_text(3, &crate::migrations::rfc3339_now())?;
        let r = seed.step();
        drop(seed);
        r?;
    }
    let ins = conn.prepare(
        "INSERT OR IGNORE INTO chain_entries (slug, n, line, ts, kind, actor, prev, hash, body_v) \
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
    );
    let ins = match ins {
        Ok(s) => s,
        Err(e) => {
            let _ = conn.exec("ROLLBACK;");
            return Err(e);
        }
    };

    for (idx, raw) in raw_segments.iter().enumerate() {
        let ordinal = (idx + 1) as i64;
        // Parse for the index columns; the stored bytes stay raw.
        let e = match atlas_core::json::parse(raw.trim()) {
            Ok(e) => e,
            Err(_) => {
                let _ = conn.exec("ROLLBACK;");
                return Err(crate::driver::StoreError {
                    code: -1,
                    msg: format!("mirror refuses unparsable line {}", idx + 1),
                });
            }
        };
        let g = |k: &str| e.get(k).and_then(atlas_core::json::Json::as_str);
        let ts = g("ts").unwrap_or("").to_string();
        let kind = g("kind").unwrap_or("").to_string();
        let actor = g("actor").unwrap_or("").to_string();
        let prev = g("prev").unwrap_or("").to_string();
        let hash = g("hash").unwrap_or("").to_string();
        let body_v = match e.get("body_v") {
            Some(atlas_core::json::Json::Int(v)) => *v,
            _ => 3,
        };

        ins.reset().ok();
        bind_row(&ins, slug, ordinal, raw.as_bytes(), &ts, &kind, &actor, &prev, &hash, body_v)?;
        match ins.step() {
            Ok(Step::Done) | Ok(Step::Row) => {}
            Err(err) => {
                let _ = conn.exec("ROLLBACK;");
                return Err(err);
            }
        }
        if conn.changes() > 0 {
            inserted += 1;
        }
        if kind == "wrap" && ordinal > start_at as i64 {
            wraps_crossed.push(idx);
        }
    }
    drop(ins);

    // Rule 2: the pointer moves inside THIS transaction, to the full length.
    let head = raw_segments
        .iter()
        .rev()
        .find_map(|l| {
            atlas_core::json::parse(l.trim())
                .ok()
                .and_then(|e| e.get("hash").and_then(atlas_core::json::Json::as_str).map(str::to_string))
        })
        .unwrap_or_default();
    let up = conn.prepare(
        "INSERT INTO journal_sync (chain_path, last_applied_n, applied_hash) VALUES (?, ?, ?) \
         ON CONFLICT(chain_path) DO UPDATE SET last_applied_n=excluded.last_applied_n, \
         applied_hash=excluded.applied_hash;",
    );
    let up = match up {
        Ok(s) => s,
        Err(e) => {
            let _ = conn.exec("ROLLBACK;");
            return Err(e);
        }
    };
    up.bind_text(1, key)?;
    up.bind_int64(2, raw_segments.len() as i64)?;
    up.bind_text(3, &head)?;
    let step_r = up.step();
    drop(up);
    if let Err(e) = step_r {
        let _ = conn.exec("ROLLBACK;");
        return Err(e);
    }
    // Derived summary folds to the record's shape inside the same txn.
    let refresh = conn.prepare(
        "UPDATE chains SET head=?, entries=? WHERE slug=?;",
    );
    let refresh = match refresh {
        Ok(s) => s,
        Err(e) => {
            let _ = conn.exec("ROLLBACK;");
            return Err(e);
        }
    };
    refresh.bind_text(1, &head)?;
    refresh.bind_int64(2, raw_segments.len() as i64)?;
    refresh.bind_text(3, slug)?;
    let step_r = refresh.step();
    drop(refresh);
    if let Err(e) = step_r {
        let _ = conn.exec("ROLLBACK;");
        return Err(e);
    }
    conn.exec("COMMIT;")?;

    // Rule 5: checkpoint + Merkle proof walk for every crossed wrap.
    let mut wraps_walked = 0usize;
    for idx in wraps_crossed {
        walk_wrap_proof(chain_text, idx)?;
        conn.wal_checkpoint_passive()?;
        wraps_walked += 1;
    }

    Ok(ReplayReport {
        total_lines: raw_segments.len(),
        inserted_now: inserted,
        already_mirrored: raw_segments.len().saturating_sub(inserted),
        wraps_walked,
        head: if head.is_empty() { None } else { Some(head) },
    })
}

#[allow(clippy::too_many_arguments)]
fn bind_row(
    ins: &crate::driver::Statement<'_>,
    slug: &str,
    ordinal: i64,
    line: &[u8],
    ts: &str,
    kind: &str,
    actor: &str,
    prev: &str,
    hash: &str,
    body_v: i64,
) -> Result<()> {
    ins.bind_text(1, slug)?;
    ins.bind_int64(2, ordinal)?;
    ins.bind_blob(3, line)?;
    ins.bind_text(4, ts)?;
    ins.bind_text(5, kind)?;
    ins.bind_text(6, actor)?;
    ins.bind_text(7, prev)?;
    ins.bind_text(8, hash)?;
    ins.bind_int64(9, body_v)?;
    Ok(())
}

/// Rule 5's proof half: recompute the wrap root by recognition-by-trial
/// across the estate's named trees (forge/links text-v1, us_chain binary-v1,
/// domain-separated v2), climb one sampled leaf by path alone, and refuse
/// loudly if either disagrees. Windows count LINK ORDINALS — the writers
/// appended link hashes in order, and the Jesster lineage carries no `n`.
fn walk_wrap_proof(chain_text: &str, wrap_idx: usize) -> Result<()> {
    let rows = read_rows(chain_text);
    let parsed: Vec<&atlas_core::json::Json> = rows
        .iter()
        .filter_map(|r| match r {
            atlas_core::chain::Row::Parsed(e) => Some(e),
            Row::Unparsable => None,
        })
        .collect();
    let wrap = match parsed.get(wrap_idx) {
        Some(e) => *e,
        None => {
            return Err(crate::driver::StoreError {
                code: -1,
                msg: format!("wrap line {} out of range", wrap_idx + 1),
            })
        }
    };
    let payload = wrap.get("payload");
    let get_i = |k: &str| -> Option<i64> {
        match payload.and_then(|p| p.get(k)) {
            Some(atlas_core::json::Json::Int(v)) => Some(*v),
            _ => None,
        }
    };
    let (from, to) = match (get_i("from"), get_i("to")) {
        (Some(f), Some(t)) => (f, t),
        _ => return Ok(()), // no window: nothing to prove here
    };
    let root = match payload.and_then(|p| p.get("root")).and_then(atlas_core::json::Json::as_str) {
        Some(r) => r.to_string(),
        None => return Ok(()), // not a Merkle wrap (harvest-domain kinds)
    };
    let stamped_mv = match payload.and_then(|p| p.get("mv")) {
        Some(atlas_core::json::Json::Int(v)) => Some(*v as u8),
        _ => None,
    };

    // Links, in order; the window indexes into them positionally.
    let links: Vec<&atlas_core::json::Json> = parsed
        .iter()
        .filter(|e| e.get("kind").and_then(atlas_core::json::Json::as_str) != Some("wrap"))
        .copied()
        .collect();
    let start = (from.max(1) - 1) as usize;
    let end = (to as usize).min(links.len());
    let leaves: Vec<String> = links[start..end]
        .iter()
        .filter_map(|e| e.get("hash").and_then(atlas_core::json::Json::as_str).map(str::to_string))
        .collect();

    let (tree, got) =
        atlas_core::merkle::verify_wrap_root(&leaves, &root, stamped_mv).map_err(|why| {
            crate::driver::StoreError {
                code: -1,
                msg: format!("wrap proof refused: {} (window {}..{})", why, from, to),
            }
        })?;

    // The consistency half: one leaf must climb to the same root by path.
    if !leaves.is_empty() {
        let climbed = match tree {
            atlas_core::merkle::Tree::LinksV1Text => {
                let path = atlas_core::merkle::merkle_path_links_v1(&leaves, 0);
                atlas_core::merkle::climb_links_v1(&leaves[0], &path)
            }
            _ => {
                let path = atlas_core::merkle::merkle_path(&leaves, 0, 2);
                atlas_core::merkle::climb(&leaves[0], &path, 2)
            }
        };
        if climbed != got {
            return Err(crate::driver::StoreError {
                code: -1,
                msg: format!(
                    "wrap proof refused: leaf 0 climbs to {} under {}, recorded root {}",
                    climbed,
                    tree.name(),
                    got
                ),
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::driver::Conn;

    fn temp(tag: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let dir = std::env::temp_dir().join(format!("atlas_sync_{tag}_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        (dir.clone(), dir.join("ledger.db"))
    }

    fn three_entry_chain() -> String {
        // Lawful V3 chain built through core's own canon + sha256.
        let mut prev = atlas_core::chain::GENESIS.to_string();
        let mut out = String::new();
        for i in 0..3 {
            let entry = atlas_core::json::Json::Obj(vec![
                ("ts".into(), atlas_core::json::Json::Str(format!("2026-08-25T00:00:0{i}Z"))),
                ("kind".into(), atlas_core::json::Json::Str(format!("beat{i}"))),
                ("n".into(), atlas_core::json::Json::Int(i + 1)),
                ("payload".into(), atlas_core::json::Json::Obj(vec![])),
                ("prev".into(), atlas_core::json::Json::Str(prev.clone())),
                ("actor".into(), atlas_core::json::Json::Str("kyler".into())),
                ("body_v".into(), atlas_core::json::Json::Int(3)),
            ]);
            let proj = atlas_core::chain::project(&entry);
            let text = atlas_core::canon::canon(&proj, 3).unwrap();
            let hash = atlas_core::sha256::hex_digest(format!("{prev}{text}").as_bytes());
            let mut pairs = match entry {
                atlas_core::json::Json::Obj(p) => p,
                _ => unreachable!(),
            };
            pairs.push(("hash".into(), atlas_core::json::Json::Str(hash.clone())));
            let line = atlas_core::canon::canon(&atlas_core::json::Json::Obj(pairs), 2).unwrap();
            out.push_str(&line);
            out.push('\n');
            prev = hash;
        }
        out
    }

    #[test]
    fn replay_is_idempotent_and_pointer_moves_inside_the_txn() {
        let (dir, db) = temp("idem");
        let chain = dir.join("chain.jsonl");
        std::fs::write(&chain, three_entry_chain()).unwrap();

        let svc = open_service(&db, "test_seatlog", &chain).unwrap();
        assert_eq!(svc.mode, ServiceMode::ReadWrite);
        let key = pointer_key(&chain);
        let ptr = read_pointer(&svc.conn, &key).unwrap().unwrap();
        assert_eq!(ptr.0, 3);

        // Second open replays nothing new.
        let svc2 = open_service(&db, "test_seatlog", &chain).unwrap();
        // (mode stays ReadWrite; the mirror count below proves idempotence)
        let q = svc2.conn.prepare("SELECT count(*) FROM chain_entries;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 3);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn crash_window_healed_by_replay_on_open() {
        let (dir, db) = temp("crash");
        let chain = dir.join("chain.jsonl");
        let text = three_entry_chain();
        std::fs::write(&chain, &text).unwrap();

        // Simulate: only the FIRST line was mirrored before the crash.
        {
            let conn = Conn::open(&db).unwrap();
            conn.apply_connection_law().unwrap();
            apply_migrations(&conn, &ledger_migrations()).unwrap();
            let first = text.lines().next().unwrap();
            replay_partial_for_crash_simulation(
                &conn,
                "test_seatlog",
                &pointer_key(&chain),
                first,
            );
        }

        // Reopen: rule 3 heals the gap.
        let svc = open_service(&db, "test_seatlog", &chain).unwrap();
        let q = svc.conn.prepare("SELECT count(*) FROM chain_entries;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 3, "replay filled the crash gap");
        std::fs::remove_dir_all(&dir).ok();
    }

    fn replay_partial_for_crash_simulation(conn: &Conn, slug: &str, key: &str, first_line: &str) {
        let mut partial = String::from(first_line);
        partial.push('\n');
        replay_chain(conn, slug, key, &partial).unwrap();
    }

    #[test]
    fn refuse_on_break_opens_read_only_carrying_the_why() {
        let (dir, db) = temp("break");
        let chain = dir.join("broken.jsonl");
        // TAMPER: successor still points at a removed entry.
        let good = three_entry_chain();
        let lines: Vec<&str> = good.lines().collect();
        std::fs::write(&chain, format!("{}\n{}\n", lines[0], lines[2])).unwrap();

        let svc = open_service(&db, "test_broken", &chain).unwrap();
        match &svc.mode {
            ServiceMode::ReadOnly(why) => {
                assert!(why.contains("TAMPER"), "{why}");
            }
            other => panic!("expected read-only, got {:?}", other),
        }
        // The broken chain wrote NOTHING to the mirror.
        let q = svc.conn.prepare("SELECT count(*) FROM chain_entries;").unwrap();
        assert!(matches!(q.step().unwrap(), Step::Row));
        assert_eq!(q.int64(0), 0);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn record_first_refusal_leaves_the_db_byte_identical() {
        let (dir, db) = temp("recfirst");
        let good_chain = dir.join("good.jsonl");
        std::fs::write(&good_chain, three_entry_chain()).unwrap();
        let svc = open_service(&db, "test_good", &good_chain).unwrap();
        drop(svc);
        let before = std::fs::read(&db).unwrap();

        // A tampered ground must never reach SQLite.
        let bad_chain = dir.join("bad.jsonl");
        let bad_text = three_entry_chain();
        let lines: Vec<&str> = bad_text.lines().collect();
        std::fs::write(&bad_chain, format!("{}\n{}\n", lines[0], lines[2])).unwrap();
        let svc2 = open_service(&db, "test_bad", &bad_chain).unwrap();
        assert!(matches!(svc2.mode, ServiceMode::ReadOnly(_)));
        drop(svc2);

        let after = std::fs::read(&db).unwrap();
        assert_eq!(before, after, "refused ground moved the DB bytes");
        std::fs::remove_dir_all(&dir).ok();
    }
}
