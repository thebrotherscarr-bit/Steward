//! D2-01 trade parity: the port's outputs match the oracle's normalized
//! golden shapes, and both sides verify each other's chains.
//!
//! Wall clocks differ run to run, so parity is proven two ways (witnessed
//! sitting 17): normalized-output equality against trade_vectors.json, and
//! cross-verification — Rust walks the oracle's committed books intact
//! (hash-compat on real oracle bytes), Python walks Rust-written books
//! (tools/check_trade_parity.py, dev-run + witnessed).

use std::path::{Path, PathBuf};

use atlas_store::trade;

fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../tests/fixtures")
}

fn is_word_byte(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'_'
}

fn is_hex_byte(c: u8) -> bool {
    c.is_ascii_digit() || (b'a'..=b'f').contains(&c)
}

/// Mirror the cutter's normalize(): TS-><TS>, DATE-><DATE>,
/// CLOCK-><CLOCK>, tmpdir-><TMP>, 12..64hex-><HASH>. Same passes, same order.
/// Non-ASCII copies through intact (the cutter's ensure_ascii=False keeps it).
fn normalize(s: &str, tmp: &str) -> String {
    let b = s.as_bytes();
    let mut out = String::new();
    let mut i = 0;
    let digit_at = |j: usize| b.get(j).is_some_and(|c| c.is_ascii_digit());
    let date_at = |j: usize| {
        b.len() >= j + 10
            && digit_at(j) && digit_at(j + 1) && digit_at(j + 2) && digit_at(j + 3)
            && b.get(j + 4) == Some(&b'-')
            && digit_at(j + 5) && digit_at(j + 6)
            && b.get(j + 7) == Some(&b'-')
            && digit_at(j + 8) && digit_at(j + 9)
    };
    let time_at = |j: usize| {
        b.len() >= j + 5 && digit_at(j) && digit_at(j + 1) && b.get(j + 2) == Some(&b':')
            && digit_at(j + 3) && digit_at(j + 4)
    };
    // Width of the UTF-8 sequence starting at i (patterns are ASCII-only,
    // so a multibyte lead can never start one — copy it whole).
    let char_width = |j: usize| {
        let c = b[j];
        if c < 0x80 {
            1
        } else if c >> 5 == 0b110 {
            2
        } else if c >> 4 == 0b1110 {
            3
        } else {
            4
        }
    };
    while i < b.len() {
        if b[i] >= 0x80 {
            let w = char_width(i).min(b.len() - i);
            out.push_str(&s[i..i + w]);
            i += w;
            continue;
        }
        if date_at(i) {
            let mut j = i + 10;
            if b.get(j) == Some(&b'T') && time_at(j + 1) {
                j += 6;
                if b.get(j) == Some(&b':') && digit_at(j + 1) && digit_at(j + 2) {
                    j += 3;
                }
                out.push_str("<TS>");
            } else {
                out.push_str("<DATE>");
            }
            i = j;
            continue;
        }
        if time_at(i)
            && (i == 0 || !is_word_byte(b[i - 1]) && b[i - 1] != b':')
            && b.get(i + 5).is_none_or(|c| !c.is_ascii_digit() && *c != b':')
        {
            let mut j = i + 5;
            if b.get(j) == Some(&b':') && digit_at(j + 1) && digit_at(j + 2) {
                j += 3;
            }
            out.push_str("<CLOCK>");
            i = j;
            continue;
        }
        if is_hex_byte(b[i])
            && (i == 0 || !is_word_byte(b[i - 1]))
        {
            let mut j = i;
            while j < b.len() && is_hex_byte(b[j]) {
                j += 1;
            }
            if (12..=64).contains(&(j - i)) && (j == b.len() || !is_word_byte(b[j])) {
                out.push_str("<HASH>");
                i = j;
                continue;
            }
        }
        out.push(b[i] as char);
        i += 1;
    }
    out.replace(tmp, "<TMP>")
}

fn scenario() -> Vec<(&'static str, String)> {
    vec![
        ("property", "enroll Red Rock Loop | 55 Red Rock Loop Rd, Sedona".into()),
        ("property", "enroll Juniper Ridge casita | key in the lockbox".into()),
        ("property", "list".into()),
        ("workorder", "add Juniper Ridge casita | swamp cooler pads worn | Dale".into()),
        ("workorder", "add Red Rock Loop | gate hinge javelina damage | Marco".into()),
        ("workorder", "assign 2 | Marco".into()),
        ("workorder", "done 1 | 300".into()),
        ("workorder", "list open".into()),
        ("workorder", "list done".into()),
        ("workorder", "list all".into()),
        ("inspect", "log Red Rock Loop | water heater=pass ; drip zone 3=fail | javelina bent the gate".into()),
        ("inspect", "log Juniper Ridge casita | swamp cooler=pass".into()),
        ("inspect", "report red rock".into()),
        ("report", "Red Rock Loop".into()),
        ("report", "Oak Creek".into()),
    ]
}

#[test]
fn outputs_match_golden_shapes() {
    let raw = std::fs::read_to_string(fixtures().join("trade_vectors.json")).unwrap();
    let golden = atlas_core::json::parse(&raw).unwrap();
    let want_vec = match golden.get("outputs") {
        Some(atlas_core::json::Json::Arr(items)) => items.clone(),
        _ => panic!("golden outputs missing"),
    };
    let dir = std::env::temp_dir().join(format!("atlas_trade_parity_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let tmp = dir.to_string_lossy().to_string();
    let cmds = scenario();
    assert_eq!(cmds.len(), want_vec.len(), "scenario/golden length drift");
    for ((skill, cmd), w) in cmds.iter().zip(want_vec.iter()) {
        let out = trade::run(skill, cmd, &dir).unwrap();
        let norm = normalize(&out, &tmp);
        let wnorm = match w.get("norm") {
            Some(atlas_core::json::Json::Str(s)) => s.clone(),
            _ => panic!("golden norm missing"),
        };
        assert_eq!(norm, wnorm, "shape drift: {skill} {cmd}\n  port: {norm}\n  gold: {wnorm}");
    }
    std::fs::remove_dir_all(&dir).ok();
}

/// Rust walks the oracle's committed books: hash-compat on real oracle
/// bytes (workorders.db opens read-only; the JSONL chains re-hash).
#[test]
fn cross_verify_oracle_books() {
    // Copy first: report writes reports/*.md beside the books, and fixtures
    // stay pristine (the fold law applies to test grounds too).
    let books = fixtures().join("trade_books");
    let dir = std::env::temp_dir().join(format!("atlas_trade_xverify_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    for f in ["properties.jsonl", "workorders.db", "workorders_audit.jsonl", "inspections.jsonl"] {
        std::fs::copy(books.join(f), dir.join(f)).unwrap();
    }
    let base = dir.as_path();
    assert_eq!(
        trade::run("property", "verify", base).unwrap(),
        "property roster intact (2 entries)"
    );
    assert_eq!(
        trade::run("workorder", "verify", base).unwrap(),
        "audit chain intact (4 entries)"
    );
    assert_eq!(
        trade::run("inspect", "verify", base).unwrap(),
        "inspection chain intact (2 entries)"
    );
    // And the content reads through: open WO + the page carries the work,
    // the fail, the receipts, and the whole verdict (per the golden outputs).
    let open = trade::run("workorder", "list open", base).unwrap();
    assert!(open.contains("#2 [open]"), "open WO reads: {open}");
    let page = trade::run("report", "Red Rock Loop", base).unwrap();
    assert!(
        page.contains("gate hinge javelina damage")
            && page.contains("1 FAILED: drip zone 3")
            && page.contains("This record proves whole"),
        "report reads"
    );
    std::fs::remove_dir_all(&dir).ok();
}

/// A flipped byte in a copy names its break — every chain, both writers.
#[test]
fn tamper_names_the_break() {
    let books = fixtures().join("trade_books");
    let dir = std::env::temp_dir().join(format!("atlas_trade_tamper_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    for f in ["properties.jsonl", "workorders.db", "workorders_audit.jsonl", "inspections.jsonl"] {
        std::fs::copy(books.join(f), dir.join(f)).unwrap();
    }
    flip(&dir.join("properties.jsonl"), "Sedona", "Phoenix");
    assert!(trade::run("property", "verify", &dir).unwrap().contains("BROKEN at entry 0"));
    restore(&books, &dir, "properties.jsonl");
    flip(&dir.join("workorders_audit.jsonl"), "javelina", "coyote");
    assert!(trade::run("workorder", "verify", &dir).unwrap().contains("BROKEN"));
    restore(&books, &dir, "workorders_audit.jsonl");
    flip(&dir.join("inspections.jsonl"), "fail", "pass");
    assert!(trade::run("inspect", "verify", &dir).unwrap().contains("BROKEN at entry 0"));
    restore(&books, &dir, "inspections.jsonl");
    // Untouched copies still prove whole (report verdict path).
    let page = trade::run("report", "Red Rock Loop", &dir).unwrap();
    assert!(page.contains("This record proves whole"), "healed ground proves whole");
    std::fs::remove_dir_all(&dir).ok();
}

fn flip(path: &Path, from: &str, to: &str) {
    let body = std::fs::read_to_string(path).unwrap();
    std::fs::write(path, body.replacen(from, to, 1)).unwrap();
}

fn restore(books: &Path, dir: &Path, name: &str) {
    std::fs::copy(books.join(name), dir.join(name)).unwrap();
}
