//! Python-compat JSON dumps for the trade books (D2).
//!
//! The estate's trade skills hash `json.dumps(obj, sort_keys=True)` with the
//! DEFAULT `ensure_ascii=True`: separators `", "` / `": "`, keys sorted by
//! code point, non-ASCII as `\uXXXX` (surrogate pairs past BMP), floats in
//! Python repr. Rust must emit these exact bytes or cross-verification of
//! the hash chains breaks. This is the third canon mode in core (canon.rs is
//! BODY_V/JCS; mesh canon is ascii-off): one more writer, same law —
//! goldens cut from the oracle first (see tests below, probe-cut).
//!
//! BOUNDARY, stated: Python float repr and Rust `{:?}` agree on ordinary
//! magnitudes (`300.0`, `45.5`) but differ in exponent spelling (`1e+16` vs
//! `1e16`). Trade books carry dollar costs — bounded, never exponent-form —
//! so the seam holds where it is used. Non-finite floats are refused.

use crate::json::Json;

/// Dump a value exactly as CPython `json.dumps(v, sort_keys=True)`.
pub fn dumps(v: &Json) -> Result<String, String> {
    let mut sb = String::new();
    write_value(&mut sb, v)?;
    Ok(sb)
}

fn write_value(sb: &mut String, v: &Json) -> Result<(), String> {
    match v {
        Json::Null => sb.push_str("null"),
        Json::Bool(true) => sb.push_str("true"),
        Json::Bool(false) => sb.push_str("false"),
        Json::Int(i) => sb.push_str(&i.to_string()),
        Json::Big(digits) => {
            if is_integer_syntax(digits) {
                sb.push_str(digits);
            } else {
                return Err(format!("pyjson refuses non-integer number {digits:?}"));
            }
        }
        Json::Float(f) => sb.push_str(&py_float(*f)?),
        Json::Str(s) => write_ascii_string(sb, s),
        Json::Arr(items) => {
            sb.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    sb.push_str(", ");
                }
                write_value(sb, item)?;
            }
            sb.push(']');
        }
        Json::Obj(pairs) => {
            let mut keys: Vec<&String> = pairs.iter().map(|(k, _)| k).collect();
            keys.sort();
            sb.push('{');
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    sb.push_str(", ");
                }
                write_ascii_string(sb, k);
                sb.push_str(": ");
                let v = pairs.iter().find(|(kk, _)| kk == *k).map(|(_, v)| v).unwrap();
                write_value(sb, v)?;
            }
            sb.push('}');
        }
    }
    Ok(())
}

fn is_integer_syntax(s: &str) -> bool {
    let t = s.strip_prefix('-').unwrap_or(s);
    !t.is_empty() && t.bytes().all(|c| c.is_ascii_digit())
}

fn py_float(f: f64) -> Result<String, String> {
    if !f.is_finite() {
        return Err("pyjson refuses non-finite float".into());
    }
    Ok(format!("{f:?}"))
}

/// Quote one string exactly as dumps() would (CPython ensure_ascii).
pub fn quote(s: &str) -> String {
    let mut sb = String::new();
    write_ascii_string(&mut sb, s);
    sb
}

/// Quote like CPython with ensure_ascii=True: short escapes, `\u00xx` for
/// C0 controls and DEL, `\uXXXX` past ASCII (surrogate pairs past BMP),
/// lowercase hex throughout.
fn write_ascii_string(sb: &mut String, s: &str) {
    sb.push('"');
    for c in s.chars() {
        match c {
            '"' => sb.push_str("\\\""),
            '\\' => sb.push_str("\\\\"),
            '\n' => sb.push_str("\\n"),
            '\r' => sb.push_str("\\r"),
            '\t' => sb.push_str("\\t"),
            '\u{08}' => sb.push_str("\\b"),
            '\u{0c}' => sb.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) == 0x7f => {
                sb.push_str(&format!("\\u{:04x}", c as u32));
            }
            c if (c as u32) < 0x80 => sb.push(c),
            c if (c as u32) < 0x10000 => {
                sb.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => {
                // Astral: UTF-16 surrogate pair, high first — CPython order.
                let v = c as u32 - 0x10000;
                sb.push_str(&format!(
                    "\\u{:04x}\\u{:04x}",
                    0xd800 + (v >> 10),
                    0xdc00 + (v & 0x3ff)
                ));
            }
        }
    }
    sb.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Probe-cut from CPython `json.dumps(c, sort_keys=True)` — the oracle's
    /// exact bytes (tools-adjacent probe, witnessed sitting 17).
    fn oracle_cases() -> Vec<(&'static str, Json, &'static str)> {
        vec![
            (
                "roster-entry",
                Json::Obj(vec![
                    ("ts".into(), Json::Str("2026-09-03T12:00:00".into())),
                    ("name".into(), Json::Str("Red Rock Loop".into())),
                    ("notes".into(), Json::Str("55 Red Rock Loop Rd, Sedona".into())),
                ]),
                r#"{"name": "Red Rock Loop", "notes": "55 Red Rock Loop Rd, Sedona", "ts": "2026-09-03T12:00:00"}"#,
            ),
            (
                "float-cost",
                Json::Obj(vec![
                    ("cost".into(), Json::Float(300.0)),
                    ("id".into(), Json::Int(1)),
                    ("op".into(), Json::Str("done".into())),
                ]),
                r#"{"cost": 300.0, "id": 1, "op": "done"}"#,
            ),
            (
                "float-cents",
                Json::Obj(vec![
                    ("cost".into(), Json::Float(45.5)),
                    ("id".into(), Json::Int(1)),
                    ("op".into(), Json::Str("done".into())),
                ]),
                r#"{"cost": 45.5, "id": 1, "op": "done"}"#,
            ),
            (
                "unicode-checks",
                Json::Obj(vec![
                    ("checks".into(), Json::Obj(vec![
                        ("drip zone 3".into(), Json::Str("fail".into())),
                        ("water heater".into(), Json::Str("pass".into())),
                    ])),
                    ("notes".into(), Json::Str("javelina \u{2014} bent \u{2713} \u{e9}".into())),
                    ("property".into(), Json::Str("X".into())),
                    ("ts".into(), Json::Str("2026-09-03T12:00:00".into())),
                ]),
                "{\"checks\": {\"drip zone 3\": \"fail\", \"water heater\": \"pass\"}, \"notes\": \"javelina \\u2014 bent \\u2713 \\u00e9\", \"property\": \"X\", \"ts\": \"2026-09-03T12:00:00\"}",
            ),
            (
                "escapes",
                Json::Obj(vec![(
                    "s".into(),
                    Json::Str("q\"b\\c\nd\te\rf\x0cg\x01h\x7fZ\u{e9}\u{1f600}".into()),
                )]),
                "{\"s\": \"q\\\"b\\\\c\\nd\\te\\rf\\fg\\u0001h\\u007fZ\\u00e9\\ud83d\\ude00\"}",
            ),
            (
                "big-and-neg",
                Json::Obj(vec![
                    ("big".into(), Json::Big("123456789012345678901234567890".into())),
                    ("n".into(), Json::Int(-2)),
                    ("z".into(), Json::Int(0)),
                ]),
                r#"{"big": 123456789012345678901234567890, "n": -2, "z": 0}"#,
            ),
            (
                "atoms",
                Json::Obj(vec![
                    ("e".into(), Json::Obj(vec![])),
                    ("f".into(), Json::Bool(false)),
                    ("l".into(), Json::Arr(vec![])),
                    ("nil".into(), Json::Null),
                    ("t".into(), Json::Bool(true)),
                ]),
                r#"{"e": {}, "f": false, "l": [], "nil": null, "t": true}"#,
            ),
        ]
    }

    #[test]
    fn dumps_matches_cpython_byte_for_byte() {
        for (name, value, want) in oracle_cases() {
            let got = dumps(&value).unwrap();
            assert_eq!(got, want, "case {name}");
        }
    }

    #[test]
    fn refuses_non_finite_and_fractional_big() {
        assert!(dumps(&Json::Float(f64::NAN)).is_err());
        assert!(dumps(&Json::Float(f64::INFINITY)).is_err());
        assert!(dumps(&Json::Big("1.5".into())).is_err());
    }
}
