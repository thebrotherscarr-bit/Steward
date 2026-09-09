//! A2-01 / A2-02 — `.us` grammar meets the Python oracle.
//!
//! Every expectation in tests/fixtures/canon/us_vectors.json was cut from
//! the read-only oracle (estate/Neiro/lib/us_read.py) BEFORE core/src/us.rs
//! existed: four tool-born declarations with their exact render bytes, the
//! refusal battery as input-blocks plus named classes, document-level
//! failure shapes, and derive_tools folds incl. what they lose.

use std::fs;
use std::path::PathBuf;

use atlas_core::json::{self, Json};
use atlas_core::us::{declaration, derive_tools, parse, render, validate};

fn archive_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
}

fn load_vectors() -> Json {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("canon")
        .join("us_vectors.json");
    let text = fs::read_to_string(path).expect("us_vectors present");
    json::parse(&text).expect("vectors parse")
}

fn s<'a>(v: &'a Json, key: &str) -> Option<&'a str> {
    v.get(key).and_then(Json::as_str)
}

#[test]
fn every_declaration_file_meets_the_oracle_bytes() {
    let doc = load_vectors();
    let files = match doc.get("files") {
        Some(Json::Arr(f)) => f,
        other => panic!("files missing: {:?}", other),
    };
    assert_eq!(files.len(), 4, "the lawful set is four declarations");

    for case in files {
        let rel = s(case, "file").unwrap();
        let want_sha = s(case, "sha256").unwrap();
        let raw = fs::read(archive_root().join(rel))
            .unwrap_or_else(|e| panic!("{}: {}", rel, e));
        assert_eq!(
            atlas_core::sha256::hex_digest(&raw),
            want_sha,
            "{}: bytes moved since the cut",
            rel
        );

        let text = String::from_utf8_lossy(&raw).into_owned();
        let got = parse(&text);
        assert!(got.errors.is_empty(), "{}: {:?}", rel, got.errors);

        // Prose parity.
        assert_eq!(got.prose, s(case, "prose").unwrap(), "{} prose", rel);

        // Block parity, deep and ordered.
        let want_blocks = match case.get("blocks") {
            Some(Json::Arr(b)) => b,
            other => panic!("{} blocks missing: {:?}", rel, other),
        };
        assert_eq!(got.blocks.len(), want_blocks.len(), "{} block count", rel);
        for (i, (g, w)) in got.blocks.iter().zip(want_blocks.iter()).enumerate() {
            assert_eq!(g, w, "{} block {} diverges", rel, i);
        }

        // THE ROUND TRIP: our render must equal the oracle's render, byte
        // for byte — which the cutter proved equals the original file too.
        let rendered = render(&got.prose, &got.blocks);
        assert_eq!(
            rendered,
            s(case, "render_text").unwrap(),
            "{} render diverges from the oracle",
            rel
        );
        assert_eq!(
            rendered.as_bytes(),
            raw.as_slice(),
            "{} byte round-trip broken",
            rel
        );
    }
}

#[test]
fn refusals_carry_the_oracle_classes_on_identical_inputs() {
    let doc = load_vectors();
    let refusals = match doc.get("refusals") {
        Some(Json::Arr(r)) => r,
        other => panic!("refusals missing: {:?}", other),
    };
    assert!(refusals.len() >= 14, "expected the full refusal battery");

    for case in refusals {
        let name = s(case, "name").unwrap();
        let want_class = s(case, "expect_class").unwrap();
        match s(case, "target").unwrap() {
            "validate" => {
                let block = case.get("block").cloned().expect("input block");
                let stem = s(case, "stem");
                let err = validate(&block, stem)
                    .err()
                    .unwrap_or_else(|| panic!("{}: ACCEPTED", name));
                assert_eq!(
                    err.class(),
                    want_class,
                    "{}: refusal class mismatch",
                    name
                );
            }
            "declaration_doc" => {
                let text = s(case, "input_text").unwrap();
                let err = declaration(&parse(text))
                    .err()
                    .unwrap_or_else(|| panic!("{}: ACCEPTED", name));
                assert_eq!(err.class(), want_class, "{}", name);
            }
            other => panic!("{}: unknown target {}", name, other),
        }
    }
}

#[test]
fn document_level_failures_are_named_not_swallowed() {
    let doc = load_vectors();
    let docs = match doc.get("docs") {
        Some(Json::Arr(d)) => d,
        other => panic!("docs missing: {:?}", other),
    };

    for case in docs {
        let name = s(case, "name").unwrap();
        let text = s(case, "input_text").unwrap();
        let got = parse(text);

        if case.get("expect_errors_nonempty") == Some(&Json::Bool(true)) {
            assert!(!got.errors.is_empty(), "{}: no errors raised", name);
        }
        if let Some(line) = case.get("first_error_mentions_line").and_then(|v| match v {
            Json::Int(n) => Some(*n as usize),
            _ => None,
        }) {
            assert!(
                got.errors[0].contains(&format!("line {}", line)),
                "{}: first error should mention line {}: {:?}",
                name,
                line,
                got.errors[0]
            );
        }
        if case.get("first_error_says_never_closed") == Some(&Json::Bool(true)) {
            assert!(
                got.errors[0].contains("never closed"),
                "{}: {:?}",
                name,
                got.errors[0]
            );
        }
        if let Some(prose_bit) = s(case, "prose_contains") {
            assert!(
                got.prose.contains(prose_bit),
                "{}: stray fence content must stay prose",
                name
            );
        }
    }
}

#[test]
fn derive_tools_folds_match_the_oracle_including_losses() {
    let doc = load_vectors();
    let cases = match doc.get("derive") {
        Some(Json::Arr(d)) => d,
        other => panic!("derive missing: {:?}", other),
    };
    assert!(cases.len() >= 7, "expected the full derive battery");

    for case in cases {
        let name = s(case, "name").unwrap();
        let perm = case.get("permission").cloned().expect("permission");
        let got = derive_tools(&perm);

        let want_tools: Vec<String> = match case.get("tools") {
            Some(Json::Arr(t)) => t
                .iter()
                .filter_map(|x| x.as_str().map(str::to_string))
                .collect(),
            _ => Vec::new(),
        };
        assert_eq!(got.tools, want_tools, "{} tools", name);

        let want_lost: Vec<String> = match case.get("lost") {
            Some(Json::Arr(l)) => l
                .iter()
                .filter_map(|x| x.as_str().map(str::to_string))
                .collect(),
            _ => Vec::new(),
        };
        assert_eq!(got.lost, want_lost, "{} lost reports", name);
    }

    // The headline stroke of A2-01 on real ground: the four lawful files
    // were all renderer-born, so the round-trip law holds universally now.
}
