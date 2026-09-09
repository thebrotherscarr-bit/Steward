//! BODY_V 1/2/3 canonical JSON (THE_CATALOG R1 · SPEC_CANON).
//!
//! V1 BOARD — the exact `json.dumps(body, sort_keys=True)` shape that wrote
//! the board chains: code-point key order, `, ` / `: ` separators, non-ASCII
//! escaped (lowercase hex, surrogate pairs for astral).
//! V2 LINKS — same sort and separators, raw UTF-8 carried.
//! V3 JCS  — RFC 8785 hand-rolled: UTF-16-be key order, minimal escaping,
//! no insignificant whitespace, floats refused, integers bounded to
//! ±(2^53−1). Never guesses; a body that cannot be canonicalised is refused
//! with the reason named.
//!
//! Every assertion meets the cut oracle vectors (tests/fixtures/canon/
//! vectors.json, A1-01), never an opinion formed here.

use crate::json::Json;
use std::fmt;

pub const BODY_V_BOARD: u8 = 1;
pub const BODY_V_LINKS: u8 = 2;
pub const BODY_V_JCS: u8 = 3;
pub const BODY_V_CURRENT: u8 = BODY_V_JCS;

/// ECMAScript Number.MAX_SAFE_INTEGER bounds (SPEC_CANON / us_canon.py).
pub const SAFE_INT_MAX: i64 = 9_007_199_254_740_991;
pub const SAFE_INT_MIN: i64 = -9_007_199_254_740_991;

const BS: char = '\\';

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CanonRefused {
    /// V3 only: JCS defers number form to ECMA-262; ledgers carry none.
    Float,
    /// V3 only: integer outside ±(2^53−1), including arbitrary `Big`
    /// magnitudes. Carries the offending digit text.
    IntRange(String),
    UnknownBodyV(u8),
}

impl fmt::Display for CanonRefused {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CanonRefused::Float => write!(
                f,
                "float refused under BODY_V 3: JCS defers number form to \
                 ECMA-262; carry an integer or a string"
            ),
            CanonRefused::IntRange(n) => write!(
                f,
                "integer {} is outside the ECMAScript safe range, so JCS \
                 cannot pin its form; carry it as a string",
                n
            ),
            CanonRefused::UnknownBodyV(v) => {
                write!(f, "no such BODY_V: {} (known: 1, 2, 3)", v)
            }
        }
    }
}

impl std::error::Error for CanonRefused {}

/// Canonical TEXT for a body under the named form.
pub fn canon(body: &Json, body_v: u8) -> Result<String, CanonRefused> {
    match body_v {
        BODY_V_BOARD => {
            let mut out = String::new();
            py_write(body, true, &mut out);
            Ok(out)
        }
        BODY_V_LINKS => {
            let mut out = String::new();
            py_write(body, false, &mut out);
            Ok(out)
        }
        BODY_V_JCS => {
            let mut out = String::new();
            jcs_write(body, &mut out)?;
            Ok(out)
        }
        v => Err(CanonRefused::UnknownBodyV(v)),
    }
}

/// Canonical BYTES — what a hash is actually taken over. Always UTF-8.
pub fn canon_bytes(body: &Json, body_v: u8) -> Result<Vec<u8>, CanonRefused> {
    canon(body, body_v).map(|s| s.into_bytes())
}

// -- V1/V2: reproduction of json.dumps(sort_keys=True) -------------------------

fn py_write(v: &Json, ascii: bool, out: &mut String) {
    match v {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Int(n) => out.push_str(&n.to_string()),
        // Digit text verbatim: json.dumps prints arbitrary ints exactly so.
        Json::Big(d) => out.push_str(d),
        Json::Float(x) => out.push_str(&python_repr(*x)),
        Json::Str(s) => py_string(s, ascii, out),
        Json::Arr(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                py_write(item, ascii, out);
            }
            out.push(']');
        }
        Json::Obj(pairs) => {
            let mut sorted: Vec<(&str, &Json)> =
                pairs.iter().map(|(k, v)| (k.as_str(), v)).collect();
            sorted.sort_by(|a, b| a.0.cmp(b.0)); // UTF-8 byte == code point
            out.push('{');
            for (i, (k, val)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                py_string(k, ascii, out);
                out.push_str(": ");
                py_write(val, ascii, out);
            }
            out.push('}');
        }
    }
}

fn short_escape(ch: char) -> Option<char> {
    match ch {
        '\u{0008}' => Some('b'),
        '\u{000C}' => Some('f'),
        '\n' => Some('n'),
        '\r' => Some('r'),
        '\t' => Some('t'),
        _ => None,
    }
}

fn py_push_escaped(ch: char, ascii: bool, out: &mut String) {
    match ch {
        '"' => {
            out.push(BS);
            out.push('"');
        }
        '\\' => {
            out.push(BS);
            out.push(BS);
        }
        c if short_escape(c).is_some() => {
            out.push(BS);
            out.push(short_escape(c).unwrap());
        }
        c if (c as u32) < 0x20 => {
            out.push(BS);
            out.push('u');
            out.push_str(&format!("{:04x}", c as u32));
        }
        c if ascii && (c as u32) > 0x7E => {
            let mut units = [0u16; 2];
            for unit in c.encode_utf16(&mut units) {
                out.push_str(&format!("{}u{:04x}", BS, unit));
            }
        }
        c => out.push(c),
    }
}

fn py_string(s: &str, ascii: bool, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        py_push_escaped(ch, ascii, out);
    }
    out.push('"');
}

/// Python `repr(float)` layout (CPython float_repr): shortest round-trip
/// digits; fixed notation while -4 <= exp10 < 16, scientific otherwise,
/// exponent signed and at least two digits, integral floats keep ".0".
pub fn python_repr(x: f64) -> String {
    if x == 0.0 {
        return if x.is_sign_negative() {
            "-0.0".to_string()
        } else {
            "0.0".to_string()
        };
    }
    let neg = x < 0.0;
    let sci = format!("{:e}", x.abs()); // shortest digits that round-trip
    let (mant, exp_txt) = sci.split_once('e').expect("{:e} always has e");
    let exp10: i32 = exp_txt.parse().expect("{:e} exponent parses");
    let digits: String = mant.chars().filter(|c| *c != '.').collect();
    let nd = digits.len() as i32;
    let decpt = exp10 + 1; // value == 0.<digits> * 10^decpt

    let mut out = String::new();
    if neg {
        out.push('-');
    }
    if exp10 <= -5 || exp10 >= 16 {
        out.push_str(&digits[..1]);
        if nd > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push('e');
        out.push(if exp10 < 0 { '-' } else { '+' });
        out.push_str(&format!("{:02}", exp10.abs()));
    } else if decpt <= 0 {
        out.push_str("0.");
        for _ in 0..(-decpt) {
            out.push('0');
        }
        out.push_str(&digits);
    } else if decpt >= nd {
        out.push_str(&digits);
        for _ in 0..(decpt - nd) {
            out.push('0');
        }
        out.push_str(".0");
    } else {
        out.push_str(&digits[..decpt as usize]);
        out.push('.');
        out.push_str(&digits[decpt as usize..]);
    }
    out
}

// -- V3: RFC 8785 JCS, hand-rolled ---------------------------------------------

fn jcs_write(v: &Json, out: &mut String) -> Result<(), CanonRefused> {
    match v {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Int(n) => {
            if *n > SAFE_INT_MAX || *n < SAFE_INT_MIN {
                return Err(CanonRefused::IntRange(n.to_string()));
            }
            out.push_str(&n.to_string());
        }
        Json::Big(digits) => return Err(CanonRefused::IntRange(digits.clone())),
        Json::Float(_) => return Err(CanonRefused::Float),
        Json::Str(s) => jcs_string(s, out),
        Json::Arr(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                jcs_write(item, out)?;
            }
            out.push(']');
        }
        Json::Obj(pairs) => {
            let mut sorted: Vec<(&str, &Json)> =
                pairs.iter().map(|(k, v)| (k.as_str(), v)).collect();
            // RFC 8785 3.2.3: UTF-16 code-unit order, NOT code-point order.
            sorted.sort_by(|a, b| {
                a.0.encode_utf16().cmp(b.0.encode_utf16())
            });
            out.push('{');
            for (i, (k, val)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                jcs_string(k, out);
                out.push(':');
                jcs_write(val, out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

fn jcs_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => {
                out.push(BS);
                out.push('"');
            }
            '\\' => {
                out.push(BS);
                out.push(BS);
            }
            c if short_escape(c).is_some() => {
                out.push(BS);
                out.push(short_escape(c).unwrap());
            }
            c if (c as u32) < 0x20 => {
                out.push(BS);
                out.push('u');
                out.push_str(&format!("{:04x}", c as u32));
            }
            c => out.push(c), // U+007F and all non-ASCII stay literal
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json::parse;

    #[test]
    fn unknown_body_v_refused_both_doors() {
        let body = Json::Obj(Vec::new());
        assert_eq!(
            canon(&body, 4),
            Err(CanonRefused::UnknownBodyV(4))
        );
        assert_eq!(
            canon(&body, 0),
            Err(CanonRefused::UnknownBodyV(0))
        );
    }

    #[test]
    fn v3_refusals_carry_the_named_reason() {
        let f = parse("{\"x\": 1.5}").unwrap();
        assert_eq!(canon(&f, BODY_V_JCS), Err(CanonRefused::Float));
        let big = parse("{\"x\": [9007199254740992]}").unwrap();
        assert_matches_int_range(&big);
        let huge = Json::Obj(vec![(
            "sig".into(),
            Json::Arr(vec![Json::Big("45080089829490884363882812606602674006760259617678563422530483273414777721469".into())]),
        )]);
        assert!(matches!(
            canon(&huge, BODY_V_JCS),
            Err(CanonRefused::IntRange(_))
        ));
    }

    fn assert_matches_int_range(body: &Json) {
        assert!(matches!(
            canon(body, BODY_V_JCS),
            Err(CanonRefused::IntRange(_))
        ));
    }

    #[test]
    fn safe_range_ends_are_carried_under_v3() {
        let ends = parse("{\"x\": 9007199254740991, \"y\": -9007199254740991}")
            .unwrap();
        assert_eq!(
            canon(&ends, BODY_V_JCS).unwrap(),
            "{\"x\":9007199254740991,\"y\":-9007199254740991}"
        );
    }

    #[test]
    fn python_repr_layout_matches_cpython_on_known_values() {
        let cases: Vec<(f64, &str)> = vec![
            (0.0, "0.0"),
            (-0.0, "-0.0"),
            (1.0, "1.0"),
            (1.5, "1.5"),
            (0.1, "0.1"),
            (100.0, "100.0"),
            (123.456, "123.456"),
            (1e15, "1000000000000000.0"),
            (1e16, "1e+16"),
            (1e30, "1e+30"),
            (1e-4, "0.0001"),
            (1e-5, "1e-05"),
            (5e-324, "5e-324"),
            (1.7976931348623157e308, "1.7976931348623157e+308"),
            (-2.5e-9, "-2.5e-09"),
        ];
        for (x, want) in cases {
            assert_eq!(python_repr(x), want, "repr({:?})", x);
        }
    }

    #[test]
    fn bytes_are_utf8_of_the_text() {
        let body = Json::Obj(vec![("note".into(), Json::Str("€ café".into()))]);
        let t = canon(&body, BODY_V_LINKS).unwrap();
        assert_eq!(canon_bytes(&body, BODY_V_LINKS).unwrap(), t.into_bytes());
    }

    #[test]
    fn v1_escapes_what_v2_carries_raw() {
        let body = Json::Obj(vec![("note".into(), Json::Str("€ café".into()))]);
        let v1 = canon(&body, BODY_V_BOARD).unwrap();
        let v2 = canon(&body, BODY_V_LINKS).unwrap();
        assert!(v1.contains("\\u20ac"));
        assert!(v2.contains('€'));
        assert_ne!(v1, v2);
    }
}
