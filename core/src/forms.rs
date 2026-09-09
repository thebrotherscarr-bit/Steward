//! Legacy form recognition-by-trial (THE_CATALOG R3 · SPEC_CHAINS §legacy).
//! Thirteen named shapes across board/links/harvest/envelope/whole/JCS
//! families, 64- and 16-hex widths. Byte-faithful mirror of the oracle walk
//! (`estate/Neiro/lib/prove_parity.py :: read_chain`): every plausible
//! construction is tried against every entry, the best match wins, first
//! full match stops the trial. None of the legacy forms records which one
//! wrote it — that is why BODY_V now rides inside new entries.

use crate::canon::{canon, CanonRefused};
use crate::chain::Row;
use crate::json::Json;
use crate::sha256;

/// links.py's projection, verbatim from its BODY_KEYS.
pub const LINKS_BODY_KEYS: [&str; 5] = ["ts", "kind", "payload", "prev", "actor"];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Construction {
    /// Whole entry minus hash, prev prefixed (board.py's shape).
    Whole,
    /// Fixed LINKS_BODY_KEYS projection, prev prefixed (links.py's shape).
    Projected,
    /// Whole entry minus hash, NO prev prefix (kimi_harvest's shape).
    WholeBare,
    /// The nested `body` alone, prev prefixed (the {prev,hash,body} envelope).
    Enveloped,
}

#[derive(Debug, Clone, Copy)]
pub struct FormDef {
    pub name: &'static str,
    pub construction: Construction,
    pub body_v: u8,
    /// 0 = full 64 hex; otherwise the head width (16 on the legacy boards).
    pub width: usize,
}

/// The oracle's FORMS table, same order, same names. Order matters: the
/// first full match wins, and a zero-match chain reports the FIRST form's
/// name with matched = 0 (faithful quirk, pinned by the golden cut).
pub const FORMS: [FormDef; 13] = [
    FormDef { name: "board V1 whole 16",   construction: Construction::Whole,      body_v: 1, width: 16 },
    FormDef { name: "board V2 whole 16",   construction: Construction::Whole,      body_v: 2, width: 16 },
    FormDef { name: "links V2 projected",  construction: Construction::Projected,  body_v: 2, width: 0 },
    FormDef { name: "links V1 projected",  construction: Construction::Projected,  body_v: 1, width: 0 },
    FormDef { name: "harvest V1 bare 16",  construction: Construction::WholeBare,  body_v: 1, width: 16 },
    FormDef { name: "harvest V2 bare 16",  construction: Construction::WholeBare,  body_v: 2, width: 16 },
    FormDef { name: "envelope V1 body 64", construction: Construction::Enveloped,  body_v: 1, width: 0 },
    FormDef { name: "envelope V2 body 64", construction: Construction::Enveloped,  body_v: 2, width: 0 },
    FormDef { name: "whole V2 64",         construction: Construction::Whole,      body_v: 2, width: 0 },
    FormDef { name: "whole V1 64",         construction: Construction::Whole,      body_v: 1, width: 0 },
    FormDef { name: "links V2 projected 16", construction: Construction::Projected, body_v: 2, width: 16 },
    FormDef { name: "JCS V3 projected",    construction: Construction::Projected,  body_v: 3, width: 0 },
    FormDef { name: "JCS V3 whole",        construction: Construction::Whole,      body_v: 3, width: 0 },
];

fn obj_without(entry: &Json, key: &str) -> Json {
    match entry {
        Json::Obj(pairs) => {
            Json::Obj(pairs.iter().filter(|(k, _)| k != key).cloned().collect())
        }
        other => other.clone(),
    }
}

fn projected(entry: &Json) -> Json {
    match entry {
        Json::Obj(pairs) => Json::Obj(
            pairs
                .iter()
                .filter(|(k, _)| LINKS_BODY_KEYS.contains(&k.as_str()))
                .cloned()
                .collect(),
        ),
        other => other.clone(),
    }
}

fn stored_hash(entry: &Json) -> Option<&str> {
    match entry.get("hash") {
        Some(Json::Str(s)) => Some(s),
        _ => None,
    }
}

/// The hash this construction would have written for (entry, prev), or None
/// when the entry cannot be canonicalised under the form at all.
pub fn construction_hash(def: &FormDef, entry: &Json, prev: &str) -> Option<String> {
    let body = match def.construction {
        Construction::Whole => obj_without(entry, "hash"),
        Construction::Projected => projected(entry),
        Construction::WholeBare => obj_without(entry, "hash"),
        Construction::Enveloped => entry.get("body")?.clone(),
    };
    let text = match canon(&body, def.body_v) {
        Ok(t) => t,
        Err(CanonRefused::UnknownBodyV(_)) => return None,
        Err(_) => return None,
    };
    let material = match def.construction {
        Construction::WholeBare => text,
        _ => format!("{}{}", prev, text),
    };
    let full = sha256::hex_digest(material.as_bytes());
    Some(if def.width > 0 && full.len() >= def.width {
        full[..def.width].to_string()
    } else {
        full
    })
}

#[derive(Debug, Clone)]
pub struct Recognition {
    pub entries: usize,
    pub hex_width: usize,
    pub form: Option<String>,
    pub matched: usize,
    pub whole: bool,
    pub weld_ok: bool,
    pub weld_broke: Option<usize>,
    pub head: String,
}

/// Which form wrote this chain, and does its weld hold end to end. Mirrors
/// prove_parity.read_chain over parsed rows only (unparsable lines are
/// skipped there — us_chain.verify is the prover that names them TAMPER).
pub fn recognize_rows(rows: &[Row]) -> Recognition {
    let parsed: Vec<&Json> = rows
        .iter()
        .filter_map(|r| match r {
            Row::Parsed(e) => Some(e),
            Row::Unparsable => None,
        })
        .collect();

    if parsed.is_empty() {
        return Recognition {
            entries: 0,
            hex_width: 0,
            form: None,
            matched: 0,
            whole: false,
            weld_ok: false,
            weld_broke: None,
            head: String::new(),
        };
    }

    let width = stored_hash(parsed[0]).map(|h| h.len()).unwrap_or(0);
    let genesis = if width > 0 {
        "0".repeat(width)
    } else {
        String::new()
    };

    let mut best: Option<(usize, usize)> = None;
    for (fi, def) in FORMS.iter().enumerate() {
        let mut prev = genesis.clone();
        let mut matched = 0usize;
        for e in &parsed {
            let got = construction_hash(def, e, &prev);
            let hit = match (got, stored_hash(e)) {
                (Some(g), Some(s)) => g == s,
                _ => false,
            };
            if hit {
                // prev advances ONLY through matched entries.
                prev = stored_hash(e).unwrap().to_string();
                matched += 1;
            } else {
                break;
            }
        }
        if best.is_none() || matched > best.unwrap().1 {
            best = Some((fi, matched));
        }
        if matched == parsed.len() {
            break;
        }
    }

    let (form_idx, matched) = best.unwrap();
    let form = FORMS[form_idx].name.to_string();

    let mut weld_prev: Option<String> = Some(genesis);
    let mut weld_ok = true;
    let mut weld_broke = None;
    for (i, e) in parsed.iter().enumerate() {
        let e_prev = match e.get("prev") {
            Some(Json::Str(s)) => Some(s.clone()),
            _ => None,
        };
        if e_prev != weld_prev {
            weld_ok = false;
            weld_broke = Some(i);
            break;
        }
        weld_prev = match e.get("hash") {
            Some(Json::Str(s)) => Some(s.clone()),
            _ => None,
        };
    }

    Recognition {
        entries: parsed.len(),
        hex_width: width,
        whole: matched == parsed.len(),
        form: Some(form),
        matched,
        weld_ok,
        weld_broke,
        head: stored_hash(parsed[parsed.len() - 1])
            .unwrap_or("")
            .to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chain::{read_rows, verify_rows, Verdict};

    #[test]
    fn table_is_thirteen_named_shapes_in_oracle_order() {
        let names: Vec<&str> = FORMS.iter().map(|f| f.name).collect();
        assert_eq!(names.first(), Some(&"board V1 whole 16"));
        assert_eq!(names.last(), Some(&"JCS V3 whole"));
        assert_eq!(names.len(), 13);
    }

    #[test]
    fn empty_ground_has_no_form_and_no_weld() {
        let r = recognize_rows(&read_rows(""));
        assert_eq!(r.entries, 0);
        assert_eq!(r.form, None);
    }

    #[test]
    fn zero_match_reports_the_first_form_name_with_matched_zero() {
        // A single entry matching nothing: oracle reports the first tried
        // construction as "best" with matched=0. Quirk pinned, not fixed.
        let r = recognize_rows(&read_rows("{\"x\": 1}"));
        assert_eq!(r.form.as_deref(), Some("board V1 whole 16"));
        assert_eq!(r.matched, 0);
        assert!(!r.whole);
    }

    #[test]
    fn links_projected_v2_recognizes_a_handmade_links_chain() {
        // Build two entries whose hash = sha256(prev + canon(projection, V2)).
        use crate::canon::BODY_V_LINKS;
        let mut out = String::new();
        let mut prev = "0".repeat(64);
        for i in 0..2 {
            let entry = Json::Obj(vec![
                ("ts".into(), Json::Str(format!("2026-08-17T00:00:0{}Z", i))),
                ("kind".into(), Json::Str("beat".into())),
                (
                    "payload".into(),
                    Json::Obj(vec![("i".into(), Json::Int(i))]),
                ),
                ("prev".into(), Json::Str(prev.clone())),
                ("actor".into(), Json::Str("kyler".into())),
                // extra field OUTSIDE the projection must not disturb history
                ("extra".into(), Json::Str(format!("e{}", i))),
            ]);
            let proj = projected(&entry);
            let text = canon(&proj, BODY_V_LINKS).unwrap();
            let hash = sha256::hex_digest(format!("{}{}", prev, text).as_bytes());
            let line = format!(
                "{{\"ts\": \"2026-08-17T00:00:0{}Z\", \"kind\": \"beat\", \"payload\": {{\"i\": {}}}, \"prev\": \"{}\", \"actor\": \"kyler\", \"extra\": \"e{}\", \"hash\": \"{}\"}}",
                i, i, prev, i, hash
            );
            out.push_str(&line);
            out.push('\n');
            prev = hash;
        }
        let rec = recognize_rows(&read_rows(&out));
        assert_eq!(rec.form.as_deref(), Some("links V2 projected"));
        assert!(rec.whole, "{:?}", rec);
        assert!(rec.weld_ok);

        let v = verify_rows(&read_rows(&out));
        // The V3-world prover reads unstamped projections as all-flip: the
        // recorded split between the two provers, both faithful.
        assert_eq!(v.verdict, Verdict::Flip);
        assert_eq!(v.flips, vec![0, 1]);
    }
}
