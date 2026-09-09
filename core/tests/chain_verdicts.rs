//! A1-02 / A1-03 — chain verdicts and form recognition meet the oracle.
//!
//! Every expectation in tests/fixtures/canon/chain_verdicts.json was cut
//! from the two read-only Python provers (us_chain.verify, prove_parity
//! .read_chain) BEFORE forms.rs/chain.rs existed, including eight injection
//! recipes run on temp ground. Rust re-runs both provers over the same
//! fixture bytes and must land on the same words every time. The injections
//! are re-applied here to fresh temp copies — never to the fixtures.

use std::fs;
use std::path::PathBuf;

use atlas_core::chain::{read_rows, verify_rows, Verdict};
use atlas_core::forms::recognize_rows;
use atlas_core::json::{self, Json};

fn fixture(rel: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join(rel)
}

fn load_doc() -> Json {
    let text = fs::read_to_string(fixture("canon/chain_verdicts.json"))
        .expect("chain_verdicts.json present (run tools/cut_chain_verdicts.py)");
    json::parse(&text).expect("chain_verdicts.json parses")
}

fn s<'a>(v: &'a Json, key: &str) -> Option<&'a str> {
    v.get(key).and_then(Json::as_str)
}

fn usize_of(v: &Json, key: &str) -> usize {
    match v.get(key) {
        Some(Json::Int(n)) => *n as usize,
        other => panic!("expected int at {:?}, got {:?}", key, other),
    }
}

fn opt_usize(v: &Json, key: &str) -> Option<usize> {
    match v.get(key) {
        Some(Json::Int(n)) => Some(*n as usize),
        _ => None,
    }
}

fn assert_parity(golden: &Json, got: &atlas_core::forms::Recognition, ctx: &str) {
    assert_eq!(got.entries, usize_of(golden, "entries"), "{} entries", ctx);
    assert_eq!(
        got.hex_width, usize_of(golden, "hex_width"),
        "{} hex_width",
        ctx
    );
    assert_eq!(
        got.form.as_deref(),
        s(golden, "form"),
        "{} form",
        ctx
    );
    assert_eq!(got.matched, usize_of(golden, "matched"), "{} matched", ctx);
    assert_eq!(
        got.whole,
        golden.get("whole") == Some(&Json::Bool(true)),
        "{} whole",
        ctx
    );
    assert_eq!(
        got.weld_ok,
        golden.get("weld_ok") == Some(&Json::Bool(true)),
        "{} weld_ok",
        ctx
    );
    assert_eq!(got.weld_broke, opt_usize(golden, "weld_broke"), "{} weld_broke", ctx);
    assert_eq!(got.head, s(golden, "head").unwrap_or(""), "{} head", ctx);
}

fn assert_verify(golden: &Json, got: &atlas_core::chain::VerifyReport, ctx: &str) {
    let want = match s(golden, "verdict") {
        Some(v) => v,
        None => panic!("{}: golden carries no verdict (skipped case?)", ctx),
    };
    assert_eq!(got.verdict.as_str(), want, "{} verdict", ctx);
    assert_eq!(got.entries, usize_of(golden, "entries"), "{} entries", ctx);
    let flips: Vec<usize> = match golden.get("flips") {
        Some(Json::Arr(items)) => items
            .iter()
            .map(|x| match x {
                Json::Int(n) => *n as usize,
                other => panic!("bad flip {:?}", other),
            })
            .collect(),
        _ => Vec::new(),
    };
    assert_eq!(got.flips, flips, "{} flips", ctx);
    assert_eq!(got.broke_at, opt_usize(golden, "broke_at"), "{} broke_at", ctx);
    assert_eq!(
        got.appendable,
        golden.get("appendable") == Some(&Json::Bool(true)),
        "{} appendable",
        ctx
    );
    if let Some(head) = s(golden, "head") {
        assert_eq!(got.head.as_deref(), Some(head), "{} head", ctx);
    }
}

#[test]
fn every_fixture_chain_matches_both_oracle_provers() {
    let doc = load_doc();
    let chains = match doc.get("chains") {
        Some(Json::Arr(c)) => c,
        other => panic!("chains missing: {:?}", other),
    };
    assert!(chains.len() >= 21, "expected the full cut of 21 chains");

    for c in chains {
        let file = s(c, "file").expect("file");
        // The pinned bytes first: a drifted fixture invalidates its own goldens.
        let bytes = fs::read(fixture(file)).unwrap();
        let want_sha = s(c, "sha256").expect("sha256");
        assert_eq!(
            atlas_core::sha256::hex_digest(&bytes),
            want_sha,
            "{}: fixture bytes moved since the cut",
            file
        );

        let rows = read_rows(&String::from_utf8_lossy(&bytes));
        let rec = recognize_rows(&rows);
        let ver = verify_rows(&rows);
        assert_parity(c.get("parity").unwrap(), &rec, file);

        match c.get("verify") {
            Some(v) if v.get("verdict").is_some() => {
                assert_verify(v, &ver, file)
            }
            Some(v) if v.get("verify_skipped").is_some() => {
                // Oracle cannot run here (hash-less rows). Assert our read
                // agrees on WHY: at least one parsed row without a hash str.
                let hashless = rows.iter().any(|r| match r {
                    atlas_core::chain::Row::Parsed(e) => {
                        !matches!(e.get("hash"), Some(Json::Str(_)))
                    }
                    _ => false,
                });
                assert!(hashless, "{}: expected hash-less rows", file);
                assert!(!ver.appendable, "{}: hash-less ground is not appendable", file);
            }
            other => panic!("{}: odd verify block {:?}", file, other),
        }
    }

    // The headline stroke of A1-02: the stamped BODY_V3 ledger verifies
    // INTACT end to end under the real prover semantics.
    let seatlog = chains
        .iter()
        .find(|c| s(c, "file") == Some("chains/agents_seatlog.jsonl"))
        .unwrap();
    assert_eq!(
        s(seatlog.get("verify").unwrap(), "verdict"),
        Some("INTACT")
    );
}

fn apply_recipe(lines: &mut Vec<String>, recipe: &Json) {
    let op = s(recipe, "op").expect("op").to_string();
    let idx = opt_usize(recipe, "index");
    match op.as_str() {
        "mutate_hashed_material" => {
            let i = idx.expect("index");
            let mut entry = json::parse(&lines[i]).expect("entry parses");
            let mut done = false;
            if let Json::Obj(pairs) = &mut entry {
                for (k, v) in pairs.iter_mut() {
                    if (k == "payload" || k == "body") && matches!(v, Json::Obj(_)) {
                        // Merge, exactly as the oracle's mutate does.
                        if let Json::Obj(inner) = v {
                            match inner
                                .iter_mut()
                                .find(|(k2, _)| k2 == "__golden_flip__")
                            {
                                Some(slot) => {
                                    slot.1 =
                                        Json::Str("oracle was here".into())
                                }
                                None => inner.push((
                                    "__golden_flip__".into(),
                                    Json::Str("oracle was here".into()),
                                )),
                            }
                        }
                        done = true;
                    }
                }
            }
            if !done {
                if let Json::Obj(pairs) = &mut entry {
                    for (k, v) in pairs.iter_mut() {
                        if k == "kind" {
                            *v = Json::Str(format!(
                                "{}X",
                                match v {
                                    Json::Str(s2) => s2.clone(),
                                    _ => String::new(),
                                }
                            ));
                            done = true;
                        }
                    }
                }
            }
            assert!(done, "recipe mutate found no material to change");
            // Re-serialise with canon V2 — valid JSON carrying the identical
            // value tree; verdicts depend on content, never spacing.
            lines[i] = atlas_core::canon::canon(&entry, atlas_core::canon::BODY_V_LINKS)
                .expect("mutated entry canonicalises under V2");
        }
        "drop_entry" => {
            lines.remove(idx.expect("index"));
        }
        "truncate_to" => {
            let keep = match recipe.get("keep") {
                Some(Json::Int(n)) => *n as usize,
                other => panic!("keep: {:?}", other),
            };
            lines.truncate(keep);
        }
        "corrupt_json_line" => {
            let i = idx.expect("index");
            lines[i] = "{broken".to_string();
        }
        other => panic!("unknown recipe op {}", other),
    }
}

#[test]
fn injections_on_temp_ground_reproduce_the_oracle_words() {
    let doc = load_doc();
    let injections = match doc.get("injections") {
        Some(Json::Arr(a)) => a,
        other => panic!("injections missing: {:?}", other),
    };
    assert!(injections.len() >= 8, "expected the full cut of 8 injections");

    let mut flipped_named_appendable = false;
    let mut tamper_located_refuses_append = false;
    let mut prefix_reads_intact = false;

    for inj in injections {
        let source = s(inj, "source").expect("source").to_string();
        let recipe = inj.get("recipe").expect("recipe").clone();

        let bytes = fs::read(fixture(&source)).unwrap();
        let mut lines: Vec<String> = String::from_utf8_lossy(&bytes)
            .lines()
            .filter(|l| !l.trim().is_empty())
            .map(|l| l.to_string())
            .collect();

        apply_recipe(&mut lines, &recipe);

        let mut path = std::env::temp_dir();
        path.push(format!(
            "atlas_a1_{}_{}_{}.jsonl",
            source.replace(['/', '\\', '.'], "_"),
            s(&recipe, "op").unwrap(),
            std::process::id()
        ));
        fs::write(&path, lines.join("\n") + "\n").expect("temp copy writes");

        let text = fs::read_to_string(&path).unwrap();
        let rows = read_rows(&text);
        let rec = recognize_rows(&rows);
        let ver = verify_rows(&rows);
        fs::remove_file(&path).ok();

        let ctx = format!("{} {:?}", source, recipe);
        assert_parity(inj.get("parity").unwrap(), &rec, &ctx);
        assert_verify(inj.get("verify").unwrap(), &ver, &ctx);

        // A1-03 semantics, asserted directly rather than only by table:
        let op = s(&recipe, "op").unwrap();
        if op == "mutate_hashed_material" && source.contains("agents_seatlog") {
            assert_eq!(ver.verdict, Verdict::Flip);
            assert_eq!(ver.flips, vec![1]);
            assert!(ver.appendable);
            flipped_named_appendable = true;
        }
        if op == "drop_entry" && source.contains("steward_board") {
            assert_eq!(ver.verdict, Verdict::Tamper);
            assert_eq!(ver.broke_at, Some(1));
            assert!(!ver.appendable);
            tamper_located_refuses_append = true;
        }
        if op == "truncate_to" && source.contains("agents_seatlog") {
            assert_eq!(ver.verdict, Verdict::Intact);
            prefix_reads_intact = true;
        }
    }

    assert!(flipped_named_appendable, "FLIP stroke missing");
    assert!(tamper_located_refuses_append, "TAMPER stroke missing");
    assert!(prefix_reads_intact, "prefix-intact stroke missing");
}
