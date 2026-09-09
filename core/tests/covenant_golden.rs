//! A1-07a/b golden strokes, proven from the cut fixtures BEFORE any
//! covenant.rs implementation exists. If these fail, either the fixtures
//! were touched or the derivation law drifted — both are review-gate stops.

use std::fs;
use std::path::{Path, PathBuf};

use atlas_core::covenant::golden::{ELDER_COVENANT, HOUSE_COVENANT};
use atlas_core::sha256::hex_digest;

const HOUSE_DOCS: [&str; 5] = [
    "01_MYTHOS.md",
    "02_CONSTITUTION.md",
    "03_CREED.md",
    "04_NEURO_CORE.md",
    "05_THE_LAW.md",
];
const ELDER_DOCS: [&str; 4] = [
    "01_MYTHOS.md",
    "02_CONSTITUTION.md",
    "03_CREED.md",
    "04_NEURO_CORE.md",
];

fn identity_dir(epoch: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("identity")
        .join(epoch)
}

/// Construction A: sha256 of the utf8 concat of the docs' hex digests,
/// taken strictly in declared order (SPEC_COVENANT).
fn construction_a(dir: &Path, docs: &[&str]) -> String {
    let concat: String = docs
        .iter()
        .map(|d| hex_digest(&fs::read(dir.join(d)).expect("doc read")))
        .collect();
    hex_digest(concat.as_bytes())
}

#[test]
fn house_covenant_reproduces_over_five_docs() {
    assert_eq!(
        construction_a(&identity_dir("house"), &HOUSE_DOCS),
        HOUSE_COVENANT,
        "House derivation broke"
    );
}

#[test]
fn elder_covenant_reproduces_over_four_docs() {
    assert_eq!(
        construction_a(&identity_dir("elder"), &ELDER_DOCS),
        ELDER_COVENANT,
        "Elder derivation broke"
    );
}

#[test]
fn an_intruder_file_moves_nothing() {
    let ground = std::env::temp_dir().join(format!("atlas_intruder_{}", std::process::id()));
    fs::create_dir_all(&ground).unwrap();
    for name in HOUSE_DOCS {
        let bytes = fs::read(identity_dir("house").join(name)).unwrap();
        fs::write(ground.join(name), bytes).unwrap();
    }
    fs::write(ground.join("FOUNDATION.md"), b"INTRUDER").unwrap();
    fs::write(ground.join("04_extra.md"), b"DECOY").unwrap();
    assert_eq!(construction_a(&ground, &HOUSE_DOCS), HOUSE_COVENANT);
    let _ = fs::remove_dir_all(&ground);
}

#[test]
fn one_flipped_byte_changes_the_covenant_and_names_the_doc() {
    let ground = std::env::temp_dir().join(format!("atlas_flip_{}", std::process::id()));
    fs::create_dir_all(&ground).unwrap();
    for name in HOUSE_DOCS {
        let bytes = fs::read(identity_dir("house").join(name)).unwrap();
        fs::write(ground.join(name), bytes).unwrap();
    }
    let mut creed = fs::read(ground.join("03_CREED.md")).unwrap();
    creed[0] ^= 0x01;
    fs::write(ground.join("03_CREED.md"), &creed).unwrap();

    let broken = construction_a(&ground, &HOUSE_DOCS);
    assert_ne!(broken, HOUSE_COVENANT, "flip must move the covenant");

    let culprit = HOUSE_DOCS
        .iter()
        .copied()
        .find(|name| {
            let ground_sha = if *name == "03_CREED.md" {
                hex_digest(&creed)
            } else {
                hex_digest(&fs::read(ground.join(name)).unwrap())
            };
            let pristine = hex_digest(
                &fs::read(identity_dir("house").join(name)).unwrap(),
            );
            ground_sha != pristine
        })
        .expect("exactly one doc moved");
    assert_eq!(culprit, "03_CREED.md");
    let _ = fs::remove_dir_all(&ground);
}
