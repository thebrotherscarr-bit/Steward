//! A1-01 — canon vectors byte-parity (SPEC_CANON).
//!
//! Every case in tests/fixtures/canon/vectors.json was cut from the Python
//! oracle (estate/Neiro/lib/us_canon.py, SPEC_CANON's named source of truth)
//! BEFORE canon.rs existed. This file meets those bytes; it never meets an
//! opinion. The vectors file is itself parsed by atlas_core::json — the
//! parser's first customer — but the expectations are oracle-made, so a
//! mis-parse here can only fail loudly, never pass falsely.

use std::fs;
use std::path::PathBuf;

use atlas_core::canon::{canon, canon_bytes, CanonRefused};
use atlas_core::json::{self, Json};

fn vectors_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("canon")
        .join("vectors.json")
}

fn load_vectors() -> Json {
    let text = fs::read_to_string(vectors_path())
        .expect("canon vectors present (run tools/cut_canon_vectors.py)");
    json::parse(&text).expect("vectors.json parses under atlas_core::json")
}

fn obj_field<'a>(case: &'a Json, key: &str) -> &'a Json {
    case.get(key)
        .unwrap_or_else(|| panic!("vector case missing field {:?}", key))
}

fn refusal_class(err: &CanonRefused) -> &'static str {
    match err {
        CanonRefused::Float => "float",
        CanonRefused::IntRange(_) => "int_range",
        CanonRefused::UnknownBodyV(_) => "unknown_body_v",
    }
}

#[test]
fn every_canon_vector_meets_the_oracle_bytes() {
    let doc = load_vectors();

    let oracle_sha = doc
        .get("oracle")
        .and_then(|o| o.get("sha256"))
        .and_then(Json::as_str)
        .expect("vectors carry the oracle sha256");
    assert_eq!(oracle_sha.len(), 64, "oracle sha256 is a full digest");

    let cases = match doc.get("cases") {
        Some(Json::Arr(cases)) => cases,
        other => panic!("vectors.cases missing: {:?}", other),
    };
    assert!(
        cases.len() >= 89,
        "expected the full cut (>=89 cases), got {}",
        cases.len()
    );

    let mut outputs = 0usize;
    let mut refusals = 0usize;

    for case in cases {
        let id = obj_field(case, "id").as_str().expect("case.id");
        let input_text = obj_field(case, "input_text")
            .as_str()
            .expect("case.input_text");

        let parsed = json::parse(input_text)
            .unwrap_or_else(|e| panic!("case {}: parser refused its own vector input: {}", id, e));

        let forms = match obj_field(case, "forms") {
            Json::Obj(pairs) => pairs,
            other => panic!("case {}: bad forms block: {:?}", id, other),
        };

        for (form_key, vec_obj) in forms {
            let body_v: u8 = form_key
                .parse()
                .unwrap_or_else(|_| panic!("case {}: bad form key {}", id, form_key));

            match vec_obj
                .get("expect")
                .and_then(Json::as_str)
                .unwrap_or_else(|| panic!("case {} form {}: missing expect", id, body_v))
            {
                "output" => {
                    let want_text = vec_obj
                        .get("text")
                        .and_then(Json::as_str)
                        .unwrap_or_else(|| {
                            panic!("case {} form {}: output vector missing text", id, body_v)
                        });
                    // Byte parity first: this is what a hash is taken over.
                    let got_bytes = canon_bytes(&parsed, body_v).unwrap_or_else(|e| {
                        panic!(
                            "case {} form {}: refused {:?} but the oracle produced bytes",
                            id, body_v, e
                        )
                    });
                    assert_eq!(
                        got_bytes,
                        want_text.as_bytes(),
                        "case {} form {}: bytes diverge from the oracle",
                        id,
                        body_v
                    );
                    // And text parity alongside it.
                    let got_text = canon(&parsed, body_v)
                        .unwrap_or_else(|e| panic!("case {} form {}: {}", id, body_v, e));
                    assert_eq!(got_text, want_text);
                    outputs += 1;
                }
                "refuse" => {
                    let want_reason = vec_obj
                        .get("reason")
                        .and_then(Json::as_str)
                        .unwrap_or_else(|| {
                            panic!("case {} form {}: refuse vector missing reason", id, body_v)
                        });
                    match canon(&parsed, body_v) {
                        Ok(_) => panic!(
                            "case {} form {}: accepted but the oracle refuses ({})",
                            id, body_v, want_reason
                        ),
                        Err(err) => assert_eq!(
                            refusal_class(&err),
                            want_reason,
                            "case {} form {}: refusal class mismatch",
                            id,
                            body_v
                        ),
                    }
                    refusals += 1;
                }
                other => panic!("case {}: unknown expect {:?}", id, other),
            }
        }
    }

    // The full landed cut, or something was dropped en route.
    assert!(
        outputs >= 250 && refusals >= 100,
        "stroke count collapsed: outputs={}, refusals={}",
        outputs,
        refusals
    );
    println!(
        "A1-01 canon vectors: {} outputs + {} named refusals all meet the oracle bytes",
        outputs, refusals
    );
}
