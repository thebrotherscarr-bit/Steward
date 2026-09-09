//! Estate wrap-root pins — the Merkle goldens the ground itself wrote.
//!
//! Every wrap entry in the fixture chains that carries a window and a root
//! must reproduce under one of the estate's NAMED trees, and a sampled leaf
//! must climb to the same root by path alone. The kimi harvest ledger's
//! `wrap` kind carries no root/window at all — a different animal wearing
//! the same name; it is counted as a named skip, never force-fitted.
//!
//! Witnessed by probe 2026-08-25: all eight Jesster library wraps (gen2 ×3,
//! gen3 ×4, gen4-head46 ×1) reproduce under the forge/links TEXT tree.

use std::fs;
use std::path::PathBuf;

use atlas_core::chain::{read_rows, Row};
use atlas_core::json::Json;
use atlas_core::merkle::{
    climb, climb_links_v1, merkle_path, merkle_path_links_v1, verify_wrap_root,
};

fn chains_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("chains")
}

#[test]
fn every_estate_wrap_root_reproduces_under_a_named_tree() {
    let mut pinned = 0usize;
    let mut skipped_no_root = 0usize;
    let mut trees_seen = std::collections::BTreeSet::new();

    for entry in fs::read_dir(chains_dir()).expect("fixture chains present") {
        let path = entry.unwrap().path();
        if path.extension().and_then(|e| e.to_str()) != Some("jsonl") {
            continue;
        }
        let text = String::from_utf8_lossy(&fs::read(&path).unwrap()).into_owned();
        let rows = read_rows(&text);

        // Links in order; windows index into them positionally.
        let parsed: Vec<&Json> = rows
            .iter()
            .filter_map(|r| match r {
                Row::Parsed(e) => Some(e),
                Row::Unparsable => None,
            })
            .collect();
        let links: Vec<&Json> = parsed
            .iter()
            .filter(|e| e.get("kind").and_then(Json::as_str) != Some("wrap"))
            .copied()
            .collect();

        for e in &parsed {
            if e.get("kind").and_then(Json::as_str) != Some("wrap") {
                continue;
            }
            let payload = match e.get("payload") {
                Some(p) => p,
                None => continue,
            };
            let (from, to, root) = match (
                payload.get("from"),
                payload.get("to"),
                payload.get("root"),
            ) {
                (
                    Some(Json::Int(f)),
                    Some(Json::Int(t)),
                    Some(Json::Str(r)),
                ) => (*f as usize, *t as usize, r.clone()),
                _ => {
                    skipped_no_root += 1;
                    continue;
                }
            };
            let stamped_mv = match payload.get("mv") {
                Some(Json::Int(v)) => Some(*v as u8),
                _ => None,
            };

            let start = from.saturating_sub(1);
            let end = to.min(links.len());
            assert!(
                start < end && end <= links.len(),
                "{}: window {}..{} out of range ({} links)",
                path.display(),
                from,
                to,
                links.len()
            );
            let leaves: Vec<String> = links[start..end]
                .iter()
                .filter_map(|e| e.get("hash").and_then(Json::as_str).map(str::to_string))
                .collect();
            assert_eq!(leaves.len(), end - start, "{}: missing link hashes", path.display());

            let label = format!(
                "{} wrap window {}..{}",
                path.file_name().unwrap().to_string_lossy(),
                from,
                to
            );

            let (tree, got) =
                verify_wrap_root(&leaves, &root, stamped_mv)
                    .unwrap_or_else(|why| panic!("{}: {}", label, why));
            assert_eq!(got, root);

            // The consistency half: leaf 0 climbs to the same root alone.
            let climbed = match tree {
                atlas_core::merkle::Tree::LinksV1Text => {
                    let p = merkle_path_links_v1(&leaves, 0);
                    climb_links_v1(&leaves[0], &p)
                }
                _ => {
                    let p = merkle_path(&leaves, 0, 2);
                    climb(&leaves[0], &p, 2)
                }
            };
            assert_eq!(climbed, root, "{}: path climb diverges", label);

            trees_seen.insert(tree.name().to_string());
            pinned += 1;
        }
    }

    assert!(
        pinned >= 8,
        "expected at least the eight witnessed estate wraps, pinned {}",
        pinned
    );
    assert!(
        trees_seen.contains("links-v1 text"),
        "the Jesster lineage must be recognized as its own named tree"
    );
    println!(
        "wrap pins: {} roots reproduced + climbed under {:?}; {} non-Merkle 'wrap' kinds skipped",
        pinned,
        trees_seen,
        skipped_no_root
    );
}
