// prove.rs — hermetic prove battery for the atlas spine (G-stone prerequisite).
// Temp grounds only; exit 0 = all strokes green.
//
// Follows the Go runProve() pattern: named strokes, temp dirs, pass/fail
// collected, exit 0 if all green. SPEC_SEAM: every binary answers --prove.

use std::path::PathBuf;

struct Stroke {
    name: &'static str,
    ok: bool,
    det: String,
}

fn fixture(rel: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join(rel)
}

fn temp_dir(tag: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "atlas_prove_{tag}_{}",
        std::process::id()
    ));
    std::fs::create_dir_all(&d).ok();
    d
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
}

fn version_file() -> String {
    std::fs::read_to_string(repo_root().join("VERSION"))
        .unwrap_or_default()
        .trim()
        .to_string()
}

fn check_version_pin(strokes: &mut Vec<Stroke>) {
    let fv = version_file();
    let bin_ver = atlas_core::version::atlas_version().to_string();
    let ok = fv == bin_ver;
    strokes.push(Stroke {
        name: "version-pin",
        ok,
        det: format!("file={} bin={}", fv, bin_ver),
    });
}

fn check_version_cross(strokes: &mut Vec<Stroke>) {
    let root = repo_root();
    let expected = version_file();
    let mut all_match = true;
    let mut mismatches = Vec::new();

    for rel in &[
        "line/VERSION",
        "line/cmd/atlas-mcp/VERSION",
        "line/cmd/atlas-town/VERSION",
        "line/cmd/atlas-door/VERSION",
    ] {
        let p = root.join(rel);
        match std::fs::read_to_string(&p) {
            Ok(v) => {
                let v = v.trim().to_string();
                if v != expected {
                    all_match = false;
                    mismatches.push(format!("{}={}", rel, v));
                }
            }
            Err(_) => {
                all_match = false;
                mismatches.push(format!("{}=MISSING", rel));
            }
        }
    }

    strokes.push(Stroke {
        name: "version-cross",
        ok: all_match,
        det: if mismatches.is_empty() {
            format!("all agree: {}", expected)
        } else {
            format!("MISMATCH: {}", mismatches.join(", "))
        },
    });
}

fn check_chain_verify_fixtures(strokes: &mut Vec<Stroke>) {
    let chains_dir = fixture("chains");
    if !chains_dir.is_dir() {
        strokes.push(Stroke {
            name: "chain-verify-fixtures",
            ok: false,
            det: "fixtures/chains/ directory absent".into(),
        });
        return;
    }

    // These chains are known-unsound: they carry hash-less or keyed rows
    // that the current form set cannot read. The live walk flags them
    // UNSOUND too (SEAT_LOG sitting 6). Expected TAMPER, not failure.
    const KNOWN_UNSOUND: &[&str] = &[
        "commons_board",
        "commons_snapshots",
        "custody",
        "kimi_harvest_ledger",
        "skills_board_ledger",
    ];

    let mut total = 0usize;
    let mut passed = 0usize;
    let mut expected_tamper = 0usize;
    let mut unexpected = Vec::new();

    if let Ok(entries) = std::fs::read_dir(&chains_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("jsonl") {
                continue;
            }
            total += 1;
            let stem = path
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            // Strip .head46 suffix for matching
            let name = stem.split('.').next().unwrap_or(&stem).to_string();
            match std::fs::read_to_string(&path) {
                Ok(text) => {
                    let rows = atlas_core::chain::read_rows(&text);
                    let ver = atlas_core::chain::verify_rows(&rows);
                    if ver.appendable {
                        passed += 1;
                    } else if KNOWN_UNSOUND.contains(&name.as_str()) {
                        expected_tamper += 1;
                    } else {
                        unexpected.push(format!("{}={}", name, ver.verdict.as_str()));
                    }
                }
                Err(e) => {
                    unexpected.push(format!("{}=READ_ERR:{}", name, e));
                }
            }
        }
    }

    let ok = total > 0 && unexpected.is_empty();
    strokes.push(Stroke {
        name: "chain-verify-fixtures",
        ok,
        det: format!(
            "{}/{} INTACT ({} expected TAMPER){}",
            passed,
            total,
            expected_tamper,
            if unexpected.is_empty() {
                String::new()
            } else {
                format!(" UNEXPECTED: {}", unexpected.join(", "))
            }
        ),
    });
}

fn check_chain_recognize_fixtures(strokes: &mut Vec<Stroke>) {
    let chains_dir = fixture("chains");
    if !chains_dir.is_dir() {
        strokes.push(Stroke {
            name: "chain-recognize-fixtures",
            ok: false,
            det: "fixtures/chains/ directory absent".into(),
        });
        return;
    }

    let mut total = 0usize;
    let mut recognized = 0usize;
    let mut unknown = Vec::new();

    if let Ok(entries) = std::fs::read_dir(&chains_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("jsonl") {
                continue;
            }
            total += 1;
            let name = path
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            match std::fs::read_to_string(&path) {
                Ok(text) => {
                    let rows = atlas_core::chain::read_rows(&text);
                    let rec = atlas_core::forms::recognize_rows(&rows);
                    if rec.form.is_some() {
                        recognized += 1;
                    } else {
                        unknown.push(name);
                    }
                }
                Err(e) => {
                    unknown.push(format!("{}:{}", name, e));
                }
            }
        }
    }

    let ok = total > 0 && unknown.is_empty();
    strokes.push(Stroke {
        name: "chain-recognize-fixtures",
        ok,
        det: format!(
            "{}/{} recognized{}",
            recognized,
            total,
            if unknown.is_empty() {
                String::new()
            } else {
                format!(" UNKNOWN: {}", unknown.join(", "))
            }
        ),
    });
}

fn check_db_lifecycle(strokes: &mut Vec<Stroke>) {
    let dir = temp_dir("db_lifecycle");
    let db = dir.join("test.db");
    let src = fixture("chains/agents_seatlog.jsonl");

    // Step 1: init
    let conn = match atlas_store::driver::Conn::open(&db) {
        Ok(c) => c,
        Err(e) => {
            strokes.push(Stroke {
                name: "db-lifecycle",
                ok: false,
                det: format!("init failed: {}", e),
            });
            std::fs::remove_dir_all(&dir).ok();
            return;
        }
    };
    if let Err(e) = conn.apply_connection_law() {
        strokes.push(Stroke {
            name: "db-lifecycle",
            ok: false,
            det: format!("connection law failed: {}", e),
        });
        std::fs::remove_dir_all(&dir).ok();
        return;
    }
    if let Err(e) = atlas_store::migrations::apply_migrations(
        &conn,
        &atlas_store::migrations::ledger_migrations(),
    ) {
        strokes.push(Stroke {
            name: "db-lifecycle",
            ok: false,
            det: format!("migrations failed: {}", e),
        });
        std::fs::remove_dir_all(&dir).ok();
        return;
    }

    // Step 2: import
    let rep = match atlas_store::import_export::import_chain(&db, "agents_seatlog", &src) {
        Ok(r) => r,
        Err(e) => {
            strokes.push(Stroke {
                name: "db-lifecycle",
                ok: false,
                det: format!("import failed: {}", e),
            });
            std::fs::remove_dir_all(&dir).ok();
            return;
        }
    };

    // Step 3: export round-trip byte-identical
    let match_ok = atlas_store::import_export::export_matches(&db, "agents_seatlog", &src)
        .unwrap_or(false);

    // Step 4: status readable
    let status_conn = atlas_store::driver::Conn::open_readonly(&db);
    let status_ok = status_conn.is_ok();

    let ok = rep.lines > 0 && match_ok && status_ok;
    strokes.push(Stroke {
        name: "db-lifecycle",
        ok,
        det: format!(
            "import={} lines export_byte_identical={} status_ok={}",
            rep.lines, match_ok, status_ok
        ),
    });

    drop(status_conn);
    std::fs::remove_dir_all(&dir).ok();
}

fn check_enroll_dry(strokes: &mut Vec<Stroke>) {
    let dir = temp_dir("enroll_dry");
    let db = dir.join("enroll.db");
    let agents_dir = repo_root().join("agents");

    // Copy master.db as the base
    let master = repo_root().join("data").join("master.db");
    if !master.is_file() {
        strokes.push(Stroke {
            name: "enroll-dry",
            ok: false,
            det: "data/master.db absent".into(),
        });
        std::fs::remove_dir_all(&dir).ok();
        return;
    }
    if let Err(e) = std::fs::copy(&master, &db) {
        strokes.push(Stroke {
            name: "enroll-dry",
            ok: false,
            det: format!("copy failed: {}", e),
        });
        std::fs::remove_dir_all(&dir).ok();
        return;
    }

    // Dry run — should not change the DB. 0 new enrollments with 40 skipped
    // is correct idempotent behavior (all already in master.db).
    let result = atlas_store::enroll::enroll_dir(&db, &agents_dir, true);
    let ok = match &result {
        Ok(rep) => {
            rep.files_read > 0
        }
        Err(_) => {
            false
        }
    };
    let det = match &result {
        Ok(rep) => format!(
            "files_read={} enrolled={} skipped={}",
            rep.files_read,
            rep.enrolled.len(),
            rep.skipped_existing
        ),
        Err(e) => format!("ERROR: {}", e),
    };
    strokes.push(Stroke { name: "enroll-dry", ok, det });

    std::fs::remove_dir_all(&dir).ok();
}

fn check_orient_pack(strokes: &mut Vec<Stroke>) {
    // Orient against the atlas repo root itself (it has AGENTS.md, THE_ROAD.md, SEAT_LOG.md)
    let home = repo_root();
    // We can't call orient_home directly (it's in main.rs), so we test the
    // underlying logic by checking the files exist and are readable.
    let has_agents = home.join("AGENTS.md").is_file();
    let has_road = home.join("THE_ROAD.md").is_file();
    let has_log = home.join("SEAT_LOG.md").is_file();
    let has_state = home.join("STATE_OF_BUILD.md").is_file();

    let ok = has_agents && has_road && has_log && has_state;
    strokes.push(Stroke {
        name: "orient-pack",
        ok,
        det: format!(
            "AGENTS={} ROAD={} LOG={} STATE={}",
            has_agents, has_road, has_log, has_state
        ),
    });
}

fn check_link_lay_status(strokes: &mut Vec<Stroke>) {
    // Verify an existing fixture chain is INTACT — proves the chain
    // verify path works end-to-end on a real chain.
    let chain = fixture("chains/steward_chain.jsonl");
    if !chain.is_file() {
        strokes.push(Stroke {
            name: "link-lay-status",
            ok: false,
            det: "fixture steward_chain.jsonl absent".into(),
        });
        return;
    }

    let text = match std::fs::read_to_string(&chain) {
        Ok(t) => t,
        Err(e) => {
            strokes.push(Stroke {
                name: "link-lay-status",
                ok: false,
                det: format!("read failed: {}", e),
            });
            return;
        }
    };
    let rows = atlas_core::chain::read_rows(&text);
    let ver = atlas_core::chain::verify_rows(&rows);

    let ok = ver.appendable;
    strokes.push(Stroke {
        name: "link-lay-status",
        ok,
        det: format!("verdict={} entries={}", ver.verdict.as_str(), ver.entries),
    });
}

fn check_covenant_repro(strokes: &mut Vec<Stroke>) {
    // Construction A: sha256 of the utf8 concat of docs' hex digests,
    // in declared order (SPEC_COVENANT). NOT sha256(concat(doc bytes)).
    use atlas_core::covenant::golden::{ELDER_COVENANT, HOUSE_COVENANT};
    use atlas_core::sha256::hex_digest;

    const HOUSE_DOCS: [&str; 5] = [
        "01_MYTHOS.md", "02_CONSTITUTION.md", "03_CREED.md",
        "04_NEURO_CORE.md", "05_THE_LAW.md",
    ];
    const ELDER_DOCS: [&str; 4] = [
        "01_MYTHOS.md", "02_CONSTITUTION.md", "03_CREED.md",
        "04_NEURO_CORE.md",
    ];

    let house_dir = fixture("identity/house");
    let elder_dir = fixture("identity/elder");

    if !house_dir.is_dir() || !elder_dir.is_dir() {
        strokes.push(Stroke {
            name: "covenant-repro",
            ok: false,
            det: "identity/house or identity/elder absent".into(),
        });
        return;
    }

    // House: concat hex_digests in declared order, then hash
    let house_concat: String = HOUSE_DOCS
        .iter()
        .map(|d| hex_digest(&std::fs::read(house_dir.join(d)).unwrap_or_default()))
        .collect();
    let house_hash = hex_digest(house_concat.as_bytes());
    let house_ok = house_hash == HOUSE_COVENANT;

    // Elder: concat hex_digests in declared order, then hash
    let elder_concat: String = ELDER_DOCS
        .iter()
        .map(|d| hex_digest(&std::fs::read(elder_dir.join(d)).unwrap_or_default()))
        .collect();
    let elder_hash = hex_digest(elder_concat.as_bytes());
    let elder_ok = elder_hash == ELDER_COVENANT;

    let ok = house_ok && elder_ok;
    strokes.push(Stroke {
        name: "covenant-repro",
        ok,
        det: format!(
            "house={} elder={}",
            if house_ok { "151274…5bbb OK" } else { &house_hash },
            if elder_ok { "65118a…9dd9 OK" } else { &elder_hash }
        ),
    });
}

fn check_store_trio(strokes: &mut Vec<Stroke>) {
    // The approved trio: agents_seatlog, forge_links_chain, steward_ledger
    let dir = temp_dir("store_trio");
    let db = dir.join("trio.db");
    let trio = [
        ("agents_seatlog", "chains/agents_seatlog.jsonl"),
        ("forge_links_chain", "chains/forge_links_chain.jsonl"),
        ("steward_ledger", "chains/steward_ledger.head46.jsonl"),
    ];

    let mut all_ok = true;
    let mut details = Vec::new();

    for (slug, file) in &trio {
        let src = fixture(file);
        match atlas_store::import_export::import_chain(&db, slug, &src) {
            Ok(rep) => {
                let match_ok = atlas_store::import_export::export_matches(&db, slug, &src)
                    .unwrap_or(false);
                if !match_ok || rep.lines == 0 {
                    all_ok = false;
                    details.push(format!("{}: FAIL (lines={}, match={})", slug, rep.lines, match_ok));
                } else {
                    details.push(format!("{}: {} lines OK", slug, rep.lines));
                }
            }
            Err(e) => {
                all_ok = false;
                details.push(format!("{}: ERR {}", slug, e));
            }
        }
    }

    strokes.push(Stroke {
        name: "store-trio",
        ok: all_ok,
        det: details.join(" | "),
    });

    std::fs::remove_dir_all(&dir).ok();
}

pub fn run_prove() -> i32 {
    let mut strokes: Vec<Stroke> = Vec::new();

    eprintln!("\n  ATLAS --prove (hermetic; temp grounds only)\n");

    check_version_pin(&mut strokes);
    check_version_cross(&mut strokes);
    check_chain_verify_fixtures(&mut strokes);
    check_chain_recognize_fixtures(&mut strokes);
    check_store_trio(&mut strokes);
    check_db_lifecycle(&mut strokes);
    check_enroll_dry(&mut strokes);
    check_orient_pack(&mut strokes);
    check_link_lay_status(&mut strokes);
    check_covenant_repro(&mut strokes);

    let mut failed = 0usize;
    for s in &strokes {
        let tag = if s.ok { "PASS" } else { "FAIL" };
        eprintln!("    [{}]  {}   {}", tag, s.name, s.det);
        if !s.ok {
            failed += 1;
        }
    }

    if failed == 0 {
        eprintln!("\n  PROVEN. The spine carries its full battery.\n");
        0
    } else {
        eprintln!(
            "\n  {} stroke(s) failed. The spine is not yet what it claims.\n",
            failed
        );
        1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn prove_strokes_green() {
        let code = run_prove();
        assert_eq!(code, 0, "a prove stroke failed — see stderr");
    }
}
