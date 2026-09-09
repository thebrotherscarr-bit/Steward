//! Hash-chain verify (THE_CATALOG R2 · SPEC_CHAINS).
//! Entry shape {ts,kind,n,payload,prev,actor,body_v,hash}; verdicts
//! EMPTY | INTACT | FLIP | TAMPER with flips[]/broke_at/appendable.
//! This is a byte-faithful mirror of the oracle walk
//! (`estate/Neiro/lib/us_chain.py :: verify`): the weld follows each
//! entry's STORED hash, which is what lets a flipped body (hash mismatch,
//! weld intact) read apart from a rewrite (weld broken). Verdicts must
//! match the Python prover's on identical bytes (A1-02/A1-03).

use crate::canon::{canon, CanonRefused, BODY_V_JCS};
use crate::json::Json;
use crate::sha256;

pub const GENESIS: &str = "0000000000000000000000000000000000000000000000000000000000000000";

/// The hashed projection of the current form (us_chain.BODY_KEYS, verbatim).
pub const BODY_KEYS: [&str; 7] = ["ts", "kind", "n", "payload", "prev", "actor", "body_v"];

/// Wrap marker (us_chain.WRAP_KIND). Wraps ride the chain like any entry;
/// root recomputation lands with the Merkle stone, later this stone.
pub const WRAP_KIND: &str = "wrap";

/// One non-empty line of a chain file: parsed, or the raw failure.
#[derive(Debug, Clone)]
pub enum Row {
    Parsed(Json),
    Unparsable,
}

pub fn read_rows(text: &str) -> Vec<Row> {
    let mut rows = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        match crate::json::parse(line) {
            Ok(v) => rows.push(Row::Parsed(v)),
            Err(_) => rows.push(Row::Unparsable),
        }
    }
    rows
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Verdict {
    Empty,
    Intact,
    Flip,
    Tamper,
}

impl Verdict {
    pub fn as_str(&self) -> &'static str {
        match self {
            Verdict::Empty => "EMPTY",
            Verdict::Intact => "INTACT",
            Verdict::Flip => "FLIP",
            Verdict::Tamper => "TAMPER",
        }
    }
}

#[derive(Debug, Clone)]
pub struct VerifyReport {
    pub verdict: Verdict,
    pub entries: usize,
    /// Last walked stored hash (GENESIS when EMPTY; absent on TAMPER,
    /// mirroring the oracle's dict shapes).
    pub head: Option<String>,
    pub flips: Vec<usize>,
    pub broke_at: Option<usize>,
    pub appendable: bool,
}

fn stored_str(value: Option<&Json>) -> Option<String> {
    match value {
        Some(Json::Str(s)) => Some(s.clone()),
        _ => None,
    }
}

/// The hashed view: exactly BODY_KEYS, only where present.
pub fn project(entry: &Json) -> Json {
    match entry {
        Json::Obj(pairs) => Json::Obj(
            pairs
                .iter()
                .filter(|(k, _)| BODY_KEYS.contains(&k.as_str()))
                .cloned()
                .collect(),
        ),
        other => other.clone(),
    }
}

/// sha256(prev_hex + canon(projection)). The form comes from the entry
/// itself (defaulting to JCS when unstamped), so a reader never guesses.
fn entry_hash(prev: &str, entry: &Json) -> Result<String, CanonRefused> {
    let body_v = match entry.get("body_v") {
        None => BODY_V_JCS,
        Some(Json::Int(n)) if (0..=255).contains(n) => *n as u8,
        Some(_) => return Err(CanonRefused::UnknownBodyV(0)),
    };
    let text = canon(&project(entry), body_v)?;
    Ok(sha256::hex_digest(format!("{}{}", prev, text).as_bytes()))
}

/// The oracle walk over parsed rows. Every branch corresponds to one shape
/// the Python prover emits; the golden cut pins them stroke by stroke.
pub fn verify_rows(rows: &[Row]) -> VerifyReport {
    if rows.is_empty() {
        return VerifyReport {
            verdict: Verdict::Empty,
            entries: 0,
            head: Some(GENESIS.to_string()),
            flips: Vec::new(),
            broke_at: None,
            appendable: true,
        };
    }

    if let Some(i) = rows.iter().position(|r| matches!(r, Row::Unparsable)) {
        return VerifyReport {
            verdict: Verdict::Tamper,
            entries: rows.len(),
            head: None,
            flips: Vec::new(),
            broke_at: Some(i),
            appendable: false,
        };
    }

    let mut prev: Option<String> = Some(GENESIS.to_string());
    let mut flips = Vec::new();
    for (i, row) in rows.iter().enumerate() {
        let entry = match row {
            Row::Parsed(e) => e,
            Row::Unparsable => unreachable!("unparsable rows returned above"),
        };
        let e_prev = stored_str(entry.get("prev"));
        if e_prev != prev {
            return VerifyReport {
                verdict: Verdict::Tamper,
                entries: rows.len(),
                head: None,
                flips,
                broke_at: Some(i),
                appendable: false,
            };
        }
        // prev is Some here whenever the weld held (the unwraps below ride
        // that invariant; the fallback keeps a hypothetical hash-less-prev
        // corner from panicking instead of silently lying).
        let prev_text = prev.clone().unwrap_or_default();
        match entry_hash(&prev_text, entry) {
            Err(_) => {
                return VerifyReport {
                    verdict: Verdict::Tamper,
                    entries: rows.len(),
                    head: None,
                    flips,
                    broke_at: Some(i),
                    appendable: false,
                };
            }
            Ok(expect) => {
                let stored = stored_str(entry.get("hash"));
                if stored.as_deref() != Some(expect.as_str()) {
                    flips.push(i);
                }
            }
        }
        // The weld follows the STORED hash — flip detection never disturbs
        // continuity, which is the whole FLIP/TAMPER separation.
        prev = stored_str(entry.get("hash"));
    }

    if !flips.is_empty() {
        return VerifyReport {
            verdict: Verdict::Flip,
            entries: rows.len(),
            head: prev,
            flips,
            broke_at: None,
            appendable: true,
        };
    }

    VerifyReport {
        verdict: Verdict::Intact,
        entries: rows.len(),
        head: prev,
        flips: Vec::new(),
        broke_at: None,
        appendable: true,
    }
}

pub fn verify_text(text: &str) -> VerifyReport {
    verify_rows(&read_rows(text))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::canon::{canon_bytes, BODY_V_JCS};

    /// Build a lawful three-entry V3 chain the way us_chain.append would.
    fn build_chain() -> String {
        let mut out = String::new();
        let mut prev = GENESIS.to_string();
        for (i, (kind, actor)) in [
            ("awaken", "kyler"),
            ("remember", "steward"),
            ("remember", "kyler"),
        ]
        .iter()
        .enumerate()
        {
            let entry = Json::Obj(vec![
                ("ts".into(), Json::Str(format!("2026-08-17T00:00:0{}Z", i))),
                ("kind".into(), Json::Str(kind.to_string())),
                ("n".into(), Json::Int(i as i64 + 1)),
                (
                    "payload".into(),
                    Json::Obj(vec![("note".into(), Json::Str(format!("note {}", i)))]),
                ),
                ("prev".into(), Json::Str(prev.clone())),
                ("actor".into(), Json::Str(actor.to_string())),
                ("body_v".into(), Json::Int(BODY_V_JCS as i64)),
            ]);
            let text = canon(&project(&entry), BODY_V_JCS).unwrap();
            let hash = sha256::hex_digest(format!("{}{}", prev, text).as_bytes());
            let mut pairs = match entry {
                Json::Obj(pairs) => pairs,
                _ => unreachable!(),
            };
            pairs.push(("hash".into(), Json::Str(hash.clone())));
            let line = canon(&Json::Obj(pairs.clone()), BODY_V_LINKS_CANON).unwrap();
            out.push_str(&line);
            out.push('\n');
            prev = hash;
        }
        out
    }

    const BODY_V_LINKS_CANON: u8 = 2;

    #[test]
    fn empty_ground_reads_empty_and_appendable() {
        let r = verify_text("");
        assert_eq!(r.verdict, Verdict::Empty);
        assert!(r.appendable);
        assert_eq!(r.head.as_deref(), Some(GENESIS));
    }

    #[test]
    fn lawful_chain_reads_intact_end_to_end() {
        let r = verify_text(&build_chain());
        assert_eq!(r.verdict, Verdict::Intact, "report: {:?}", r);
        assert_eq!(r.entries, 3);
        assert!(r.appendable);
    }

    #[test]
    fn flipped_body_reads_flip_names_the_entry_stays_appendable() {
        let text = build_chain();
        let mut rows: Vec<Json> = text
            .lines()
            .map(|l| crate::json::parse(l).unwrap())
            .collect();
        if let Json::Obj(pairs) = &mut rows[1] {
            for (k, v) in pairs.iter_mut() {
                if k == "payload" {
                    *v = Json::Obj(vec![("note".into(), Json::Str("NOTE 1".into()))]);
                }
            }
        }
        // One byte of content changed; the stored hash line stays as it was.
        let full = format!(
            "{}\n{}\n",
            String::from_utf8(canon_bytes(&rows[0], BODY_V_LINKS_CANON).unwrap()).unwrap(),
            String::from_utf8(canon_bytes(&rows[1], BODY_V_LINKS_CANON).unwrap()).unwrap(),
        );
        let r = verify_text(&full);
        assert_eq!(r.verdict, Verdict::Flip, "report: {:?}", r);
        assert_eq!(r.flips, vec![1]);
        assert!(r.appendable);
        assert_eq!(r.broke_at, None);
    }

    #[test]
    fn removed_entry_breaks_the_weld_and_is_located() {
        let text = build_chain();
        let lines: Vec<&str> = text.lines().collect();
        // Remove the middle entry; its successor still points at it.
        let cut = format!("{}\n{}\n", lines[0], lines[2]);
        let r = verify_text(&cut);
        assert_eq!(r.verdict, Verdict::Tamper);
        assert_eq!(r.broke_at, Some(1));
        assert!(!r.appendable);
    }

    #[test]
    fn unparsable_line_is_tamper_at_first_bad_index() {
        let text = build_chain();
        let lines: Vec<&str> = text.lines().collect();
        let broken = format!("{}\n{{broken\n", lines[0]);
        let r = verify_text(&broken);
        assert_eq!(r.verdict, Verdict::Tamper);
        assert_eq!(r.broke_at, Some(1));
    }

    #[test]
    fn truncation_is_a_prefix_and_reads_intact() {
        let text = build_chain();
        let head = format!("{}\n", text.lines().next().unwrap());
        let r = verify_text(&head);
        assert_eq!(r.verdict, Verdict::Intact);
        assert_eq!(r.entries, 1);
    }

    #[test]
    fn uncanonicalisable_body_is_tamper_named_at_the_entry() {
        // A float under BODY_V3 is refused at the door (us_chain raises
        // CanonRefused mid-verify -> TAMPER at that index).
        let entry = Json::Obj(vec![
            ("ts".into(), Json::Str("2026-08-17T00:00:00Z".into())),
            ("kind".into(), Json::Str("bad".into())),
            ("prev".into(), Json::Str(GENESIS.into())),
            ("actor".into(), Json::Str("kyler".into())),
            ("body_v".into(), Json::Int(BODY_V_JCS as i64)),
            (
                "payload".into(),
                Json::Obj(vec![("x".into(), Json::Float(1.5))]),
            ),
            ("hash".into(), Json::Str(GENESIS.into())),
        ]);
        let text = format!(
            "{}\n",
            String::from_utf8(canon_bytes(&entry, BODY_V_LINKS_CANON).unwrap()).unwrap()
        );
        let r = verify_text(&text);
        assert_eq!(r.verdict, Verdict::Tamper);
        assert_eq!(r.broke_at, Some(0));
    }
}
