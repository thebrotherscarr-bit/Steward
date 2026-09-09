//! Hand-rolled JSON reader for atlas-core (supports THE_CATALOG R1 ·
//! SPEC_CANON; feeds chain reading at A1-02). Stdlib-only by standing
//! ruling (sitting 4 precedent extended by operator ruling 2026-08-25):
//! no crates.io, no network.
//!
//! Laws this module keeps:
//!   * Duplicate object keys resolve last-one-wins, exactly like
//!     `json.loads`, so canon parity holds even on drifted bodies.
//!   * Integers that fit i64 parse exact; larger magnitudes land in
//!     `Json::Big` carrying the digit text verbatim (estate custody chains
//!     carry ~77-digit BIP-340 signature components — refusing them here
//!     would refuse real history). Canon decides per-form what Big means.
//!   * Lone surrogates, raw control characters in strings, trailing
//!     garbage, leading zeros and non-finite floats are refused loudly,
//!     never coerced.

use std::fmt;

/// A parsed JSON value. Numbers keep their source shape: exact small
/// integers (`Int`), arbitrary-magnitude integers (`Big`, digit text
/// verbatim), and everything with a fraction or exponent (`Float`).
#[derive(Debug, Clone, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Big(String),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

impl Json {
    /// Last-value lookup, matching the last-one-wins parse law.
    pub fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(pairs) => pairs
                .iter()
                .rev()
                .find(|(k, _)| k == key)
                .map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_arr(&self) -> Option<&[Json]> {
        match self {
            Json::Arr(items) => Some(items),
            _ => None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ParseError {
    pub pos: usize,
    pub msg: String,
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "JSON parse error at byte {}: {}", self.pos, self.msg)
    }
}

impl std::error::Error for ParseError {}

const MAX_DEPTH: usize = 256;

/// Parse one complete JSON document; trailing non-whitespace is refused.
pub fn parse(src: &str) -> Result<Json, ParseError> {
    let mut p = Parser {
        s: src,
        b: src.as_bytes(),
        i: 0,
        depth: 0,
    };
    p.ws();
    let v = p.value()?;
    p.ws();
    if p.i != p.b.len() {
        return Err(p.err("trailing characters"));
    }
    Ok(v)
}

struct Parser<'a> {
    s: &'a str,
    b: &'a [u8],
    i: usize,
    depth: usize,
}

impl<'a> Parser<'a> {
    fn err(&self, msg: &str) -> ParseError {
        ParseError {
            pos: self.i,
            msg: msg.to_string(),
        }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn ws(&mut self) {
        while matches!(
            self.peek(),
            Some(b' ') | Some(b'\t') | Some(b'\n') | Some(b'\r')
        ) {
            self.i += 1;
        }
    }

    fn eat(&mut self, byte: u8) -> Result<(), ParseError> {
        if self.peek() == Some(byte) {
            self.i += 1;
            Ok(())
        } else {
            Err(self.err(&format!("expected {:?}", byte as char)))
        }
    }

    fn value(&mut self) -> Result<Json, ParseError> {
        self.depth += 1;
        if self.depth > MAX_DEPTH {
            return Err(self.err("nesting too deep"));
        }
        let out = match self.peek() {
            Some(b'{') => self.object(),
            Some(b'[') => self.array(),
            Some(b'"') => self.string().map(Json::Str),
            Some(b't') => self.literal("true", Json::Bool(true)),
            Some(b'f') => self.literal("false", Json::Bool(false)),
            Some(b'n') => self.literal("null", Json::Null),
            Some(b'-') | Some(b'0'..=b'9') => self.number(),
            _ => Err(self.err("expected a JSON value")),
        };
        self.depth -= 1;
        out
    }

    fn literal(&mut self, word: &str, val: Json) -> Result<Json, ParseError> {
        if self.b[self.i..].starts_with(word.as_bytes()) {
            self.i += word.len();
            Ok(val)
        } else {
            Err(self.err("bad literal"))
        }
    }

    fn object(&mut self) -> Result<Json, ParseError> {
        self.eat(b'{')?;
        let mut pairs: Vec<(String, Json)> = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Json::Obj(pairs));
        }
        loop {
            self.ws();
            let key = self.string()?;
            self.ws();
            self.eat(b':')?;
            self.ws();
            let val = self.value()?;
            match pairs.iter_mut().find(|(k, _)| *k == key) {
                Some(slot) => slot.1 = val,
                None => pairs.push((key, val)),
            }
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(Json::Obj(pairs));
                }
                _ => return Err(self.err("expected ',' or '}'")),
            }
        }
    }

    fn array(&mut self) -> Result<Json, ParseError> {
        self.eat(b'[')?;
        let mut items = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(Json::Arr(items));
        }
        loop {
            self.ws();
            items.push(self.value()?);
            self.ws();
            match self.peek() {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(Json::Arr(items));
                }
                _ => return Err(self.err("expected ',' or ']'")),
            }
        }
    }

    fn string(&mut self) -> Result<String, ParseError> {
        self.eat(b'"')?;
        let mut out = String::new();
        loop {
            match self.peek() {
                None => return Err(self.err("unterminated string")),
                Some(b'"') => {
                    self.i += 1;
                    return Ok(out);
                }
                Some(b'\\') => {
                    self.i += 1;
                    self.escape(&mut out)?;
                }
                Some(c) if c < 0x20 => {
                    return Err(self.err("raw control character in string"))
                }
                Some(_) => {
                    let ch = self.s[self.i..]
                        .chars()
                        .next()
                        .ok_or_else(|| self.err("invalid UTF-8"))?;
                    out.push(ch);
                    self.i += ch.len_utf8();
                }
            }
        }
    }

    fn escape(&mut self, out: &mut String) -> Result<(), ParseError> {
        let c = self
            .peek()
            .ok_or_else(|| self.err("unterminated escape"))?;
        self.i += 1;
        match c {
            b'"' => out.push('"'),
            b'\\' => out.push('\\'),
            b'/' => out.push('/'),
            b'b' => out.push('\u{0008}'),
            b'f' => out.push('\u{000C}'),
            b'n' => out.push('\n'),
            b'r' => out.push('\r'),
            b't' => out.push('\t'),
            b'u' => {
                let hi = self.hex4()?;
                let cp = match hi {
                    0xD800..=0xDBFF => {
                        if self.peek() != Some(b'\\') {
                            return Err(self.err("lone high surrogate"));
                        }
                        self.i += 1;
                        if self.peek() != Some(b'u') {
                            return Err(self.err("lone high surrogate"));
                        }
                        self.i += 1;
                        let lo = self.hex4()?;
                        if !(0xDC00..=0xDFFF).contains(&lo) {
                            return Err(self.err("invalid low surrogate"));
                        }
                        0x10000 + ((hi as u32 - 0xD800) << 10)
                            + (lo as u32 - 0xDC00)
                    }
                    0xDC00..=0xDFFF => {
                        return Err(self.err("lone low surrogate"))
                    }
                    _ => hi as u32,
                };
                out.push(
                    char::from_u32(cp)
                        .ok_or_else(|| self.err("invalid code point"))?,
                );
            }
            _ => return Err(self.err("invalid escape")),
        }
        Ok(())
    }

    fn hex4(&mut self) -> Result<u16, ParseError> {
        let mut v: u16 = 0;
        for _ in 0..4 {
            let c = self
                .peek()
                .ok_or_else(|| self.err("short unicode escape"))?;
            let d = match c {
                b'0'..=b'9' => c - b'0',
                b'a'..=b'f' => c - b'a' + 10,
                b'A'..=b'F' => c - b'A' + 10,
                _ => return Err(self.err("bad hex digit in unicode escape")),
            };
            self.i += 1;
            v = v * 16 + d as u16;
        }
        Ok(v)
    }

    fn number(&mut self) -> Result<Json, ParseError> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        match self.peek() {
            Some(b'0') => {
                self.i += 1;
                if matches!(self.peek(), Some(b'0'..=b'9')) {
                    return Err(self.err("leading zero"));
                }
            }
            Some(b'1'..=b'9') => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.i += 1;
                }
            }
            _ => return Err(self.err("bad number")),
        }
        let mut float = false;
        if self.peek() == Some(b'.') {
            float = true;
            self.i += 1;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.err("digit required after '.'"));
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            float = true;
            self.i += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.i += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.err("digit required in exponent"));
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.i += 1;
            }
        }
        let text = &self.s[start..self.i];
        if float {
            let x: f64 = text.parse().map_err(|_| self.err("bad float"))?;
            if !x.is_finite() {
                return Err(self.err("float out of range"));
            }
            Ok(Json::Float(x))
        } else {
            match text.parse::<i64>() {
                Ok(v) => Ok(Json::Int(v)),
                Err(_) => Ok(Json::Big(text.to_string())),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_basics_and_normalisation() {
        assert!(matches!(parse("-0").unwrap(), Json::Int(0)));
        assert!(matches!(parse("1.0").unwrap(), Json::Float(_)));
        assert!(matches!(parse("2e0").unwrap(), Json::Float(_)));
        assert_eq!(parse("\"\\/\"").unwrap(), Json::Str("/".into()));
        assert_eq!(
            parse("\"\\u0041\\u20ac\"").unwrap(),
            Json::Str("A€".into())
        );
        assert_eq!(
            parse("\"😀\"").unwrap(),
            Json::Str("\u{1F600}".into())
        );
    }

    #[test]
    fn duplicate_keys_last_wins_like_json_loads() {
        let v = parse(r#"{"a": 1, "a": 2}"#).unwrap();
        assert_eq!(v.get("a"), Some(&Json::Int(2)));
        assert_eq!(v, Json::Obj(vec![("a".into(), Json::Int(2))]));
    }

    #[test]
    fn big_integers_carry_digit_text_verbatim() {
        let v = parse("{\"sig\": [45080089829490884363882812606602674006760259617678563422530483273414777721469]}").unwrap();
        match v.get("sig") {
            Some(Json::Arr(a)) => match &a[0] {
                Json::Big(d) => assert!(d.starts_with("45080089829490884")),
                other => panic!("expected Big, got {:?}", other),
            },
            other => panic!("expected array, got {:?}", other),
        }
    }

    #[test]
    fn refusals_are_loud_and_named() {
        for bad in [
            "{\"a\": 01}",
            "{\"a\": 1}}",
            "[1,]",
            "\"\\ud800\"",
            "\"\\udc00\"",
            "\"raw\u{0001}ctl\"",
            "1e999",
            "tru",
            "+1",
            "",
        ] {
            assert!(parse(bad).is_err(), "should refuse: {:?}", bad);
        }
    }

    #[test]
    fn depth_cap_holds() {
        let deep = format!("{}1{}", "[".repeat(300), "]".repeat(300));
        let ok = format!("{}1{}", "[".repeat(200), "]".repeat(200));
        assert!(parse(&deep).is_err());
        assert!(parse(&ok).is_ok());
    }
}
