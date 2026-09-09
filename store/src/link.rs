//! The Rust pen (D2-02/E1-02): links-chain entries laid natively,
//! behavior-for-behavior with `estate/forge/links/links.py`.
//!
//! Entry shape: {ts, kind, payload, prev, actor, hash} + sig/pub outside the
//! hash when given. Hash = sha256(prev || canon(body)) where canon is
//! CPython `json.dumps(sort_keys)` (core::pyjson) and body is the five keys.
//! Payload for links: {n, says, mode, doc} + cites + mark. Wraps close every
//! 40 links (WRAP_SIZE, nobody chooses it) under Merkle v2 with the mv
//! marker; absent mv verifies as v1 forever (the oracle's own rule).
//!
//! Two honest divergences, both witnessed: timestamps are UTC with "+0000"
//! (the oracle stamps local %z); sig/pub hex is validated on deposit (the
//! oracle attaches opaquely — the walk treats both identically: weld first).

use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

use atlas_core::json::{self, Json};
use atlas_core::pyjson;
use atlas_core::sha256;

pub const GENESIS: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";
pub const WRAP_SIZE: i64 = 40;

pub struct LayArgs {
    pub chain: std::path::PathBuf,
    pub kind: String,
    pub says: String,
    pub actor: String,
    pub doc: String,
    pub mode: String,
    pub cites: Vec<String>,
    pub sig: String,
    pub pub_: String,
}

/// Lay one entry; close a wrap when a 40th link lands. Returns the entry hash.
pub fn lay(a: &LayArgs) -> Result<String, String> {
    if a.says.trim().is_empty() {
        return Err("refused: every link says what it is".into());
    }
    if a.actor.trim().is_empty() {
        return Err("refused: every link names its actor".into());
    }
    if a.mode != "open" && a.mode != "sealed" {
        return Err(format!(
            "refused: mode is \"open\" or \"sealed\", not {:?}",
            a.mode
        ));
    }
    if a.kind != "link" && a.kind != "wrap" && a.kind != "mesh" && a.kind != "cite"
        && a.kind != "head" && a.kind != "reconcile" && a.kind != "breach_attempt"
    {
        return Err(format!("refused: kind {:?} is not a chain kind", a.kind));
    }
    for c in &a.cites {
        if !is_hash_len(c) {
            return Err(format!(
                "refused: citation {c:?} is not a hash (16/40/64 hex)"
            ));
        }
    }
    if a.sig.is_empty() != a.pub_.is_empty() {
        return Err("refused: sig and pub ride together or not at all".into());
    }
    if !a.sig.is_empty() {
        if a.sig.len() != 192 || !is_hex(&a.sig) {
            return Err("refused: sig is 96 bytes hex (192 chars)".into());
        }
        if a.pub_.len() != 128 || !is_hex(&a.pub_) {
            return Err("refused: pub is 64 bytes hex (128 chars)".into());
        }
    }
    let entries = read_entries(&a.chain)?;
    let mut nlinks = 0i64;
    let mut prev = GENESIS.to_string();
    for e in &entries {
        prev = sval(e, "hash");
        if sval(e, "kind") == "link" {
            nlinks += 1;
        }
    }
    let doc = if a.mode == "sealed" {
        sha256::hex_digest(a.doc.as_bytes())
    } else {
        a.doc.clone()
    };
    let mut payload_parts: Vec<(String, String)> = Vec::new();
    if a.kind == "link" {
        payload_parts.push(("n".into(), format!("{}", nlinks + 1)));
    }
    payload_parts.push(("says".into(), q(&a.says)));
    payload_parts.push(("mode".into(), q(&a.mode)));
    payload_parts.push(("doc".into(), q(&doc)));
    if !a.cites.is_empty() {
        let cs: Vec<String> = a.cites.iter().map(|c| q(&c.to_lowercase())).collect();
        payload_parts.push(("cites".into(), format!("[{}]", cs.join(","))));
    }
    if !a.pub_.is_empty() {
        payload_parts.push(("mark".into(), q(&mark_of(&a.pub_)?)));
    }
    let payload_json = format!(
        "{{{}}}",
        payload_parts
            .iter()
            .map(|(k, v)| format!("{}:{}", pyjson::quote(k), v))
            .collect::<Vec<_>>()
            .join(",")
    );
    let ts = crate::trade::utc_ts_penned();
    let mut line = format!(
        "{{\"ts\":{},\"kind\":{},\"payload\":{},\"prev\":{},\"actor\":{}",
        pyjson::quote(&ts),
        pyjson::quote(&a.kind),
        payload_json,
        pyjson::quote(&prev),
        pyjson::quote(&a.actor)
    );
    // Hash covers the five-key body under the links canon (sorted).
    let body = Json::Obj(vec![
        ("ts".into(), Json::Str(ts.clone())),
        ("kind".into(), Json::Str(a.kind.clone())),
        ("payload".into(), parse_payload(&payload_json)?),
        ("prev".into(), Json::Str(prev.clone())),
        ("actor".into(), Json::Str(a.actor.clone())),
    ]);
    let hash = chain_hash(&prev, &body)?;
    line.push_str(&format!(",\"hash\":{}", pyjson::quote(&hash)));
    if !a.sig.is_empty() {
        line.push_str(&format!(
            ",\"sig\":{},\"pub\":{}",
            pyjson::quote(&a.sig.to_lowercase()),
            pyjson::quote(&a.pub_.to_lowercase())
        ));
    }
    line.push('}');
    append_line(&a.chain, &line)?;
    if a.kind == "link" && (nlinks + 1) % WRAP_SIZE == 0 {
        close_wrap(&a.chain)?;
    }
    Ok(hash)
}

fn parse_payload(json_text: &str) -> Result<Json, String> {
    json::parse(json_text).map_err(|e| format!("refused: payload unparsable: {e:?}"))
}

fn chain_hash(prev: &str, body: &Json) -> Result<String, String> {
    let canon = pyjson::dumps(body).map_err(|e| format!("refused: {e}"))?;
    Ok(sha256::hex_digest(format!("{prev}{canon}").as_bytes()))
}

fn mark_of(pub_hex: &str) -> Result<String, String> {
    let bytes = (0..pub_hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&pub_hex[i..i + 2], 16).map_err(|_| "refused: pub is not hex".to_string()))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(sha256::hex_digest(&bytes)[..16].to_string())
}

fn close_wrap(chain: &Path) -> Result<(), String> {
    let entries = read_entries(chain)?;
    let link_hashes: Vec<String> = entries
        .iter()
        .filter(|e| sval(e, "kind") == "link")
        .map(|e| sval(e, "hash"))
        .collect();
    let n = link_hashes.len() as i64;
    let w = n / WRAP_SIZE;
    let from = n - WRAP_SIZE + 1;
    let from_idx = link_hashes.len().saturating_sub(WRAP_SIZE as usize);
    let root = merkle_v2(&link_hashes[from_idx..]);
    let prev = entries.last().map(|e| sval(e, "hash")).unwrap_or(GENESIS.into());
    let ts = crate::trade::utc_ts_penned();
    let says = format!("wrap {w} seals links {from}-{n} and IS token {w}. Nobody closed it; forty links did.");
    let line = format!(
        "{{\"ts\":{},\"kind\":\"wrap\",\"payload\":{{\"w\":{w},\"from\":{from},\"to\":{n},\"root\":{},\"mv\":2,\"token\":{w},\"says\":{}}},\"prev\":{},\"actor\":\"arithmetic\",\"hash\":{}}}",
        pyjson::quote(&ts),
        pyjson::quote(&root),
        pyjson::quote(&says),
        pyjson::quote(&prev),
        "PENDING"
    );
    let body = Json::Obj(vec![
        ("ts".into(), Json::Str(ts.clone())),
        ("kind".into(), Json::Str("wrap".into())),
        (
            "payload".into(),
            Json::Obj(vec![
                ("w".into(), Json::Int(w)),
                ("from".into(), Json::Int(from)),
                ("to".into(), Json::Int(n)),
                ("root".into(), Json::Str(root.clone())),
                ("mv".into(), Json::Int(2)),
                ("token".into(), Json::Int(w)),
                ("says".into(), Json::Str(says)),
            ]),
        ),
        ("prev".into(), Json::Str(prev)),
        ("actor".into(), Json::Str("arithmetic".into())),
    ]);
    let hash = chain_hash(
        &entries.last().map(|e| sval(e, "hash")).unwrap_or(GENESIS.into()),
        &body,
    )?;
    let line = line.replacen("PENDING", &pyjson::quote(&hash), 1);
    append_line(chain, &line)?;
    Ok(())
}

// --- merkle ---------------------------------------------------------------

fn sha_hex(data: &[u8]) -> String {
    sha256::hex_digest(data)
}

fn hex_bytes(h: &str) -> Result<Vec<u8>, String> {
    if h.len() % 2 != 0 || !is_hex(h) {
        return Err(format!("refused: not hex: {h:?}"));
    }
    (0..h.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&h[i..i + 2], 16).map_err(|_| format!("refused: not hex: {h:?}")))
        .collect()
}

/// v1: hex-TEXT concatenation (the third tree A1 named), odd node carried.
pub fn merkle_v1(leaves: &[String]) -> String {
    if leaves.is_empty() {
        return GENESIS.into();
    }
    let mut row: Vec<String> = leaves.to_vec();
    while row.len() > 1 {
        let mut nxt = Vec::new();
        let mut i = 0;
        while i + 1 < row.len() {
            nxt.push(sha_hex(format!("{}{}", row[i], row[i + 1]).as_bytes()));
            i += 2;
        }
        if row.len() % 2 == 1 {
            nxt.push(row[row.len() - 1].clone());
        }
        row = nxt;
    }
    row[0].clone()
}

/// v2: domain-separated (0x00 leaf / 0x01 node), odd node carried.
pub fn merkle_v2(leaves: &[String]) -> String {
    if leaves.is_empty() {
        return GENESIS.into();
    }
    let leaf = |h: &str| -> String {
        let mut d = vec![0x00u8];
        d.extend(hex_bytes(h).unwrap_or_default());
        sha_hex(&d)
    };
    let node = |a: &str, b: &str| -> String {
        let mut d = vec![0x01u8];
        d.extend(hex_bytes(a).unwrap_or_default());
        d.extend(hex_bytes(b).unwrap_or_default());
        sha_hex(&d)
    };
    let mut row: Vec<String> = leaves.iter().map(|h| leaf(h)).collect();
    while row.len() > 1 {
        let mut nxt = Vec::new();
        let mut i = 0;
        while i + 1 < row.len() {
            nxt.push(node(&row[i], &row[i + 1]));
            i += 2;
        }
        if row.len() % 2 == 1 {
            nxt.push(row[row.len() - 1].clone());
        }
        row = nxt;
    }
    row[0].clone()
}

// --- status -----------------------------------------------------------------

pub struct ChainStatus {
    pub entries: usize,
    pub links: usize,
    pub wraps: usize,
    pub head: String,
    pub verdict: String,
    pub detail: String,
}

/// Rewalk a links chain: weld continuity, links-canon hash, wrap roots
/// (v1 when mv is absent, v2 when mv=2). Signatures ride opaquely — the
/// oracle's own rule (the mesh envelope is where sigs verify).
pub fn status(chain: &Path) -> Result<ChainStatus, String> {
    let raw = read_raw_lines(chain)?;
    let mut entries: Vec<Json> = Vec::with_capacity(raw.len());
    for (idx, line) in raw.iter().enumerate() {
        match json::parse(line) {
            Ok(v) => entries.push(v),
            Err(_) => {
                return Ok(ChainStatus {
                    entries: raw.len(),
                    links: 0,
                    wraps: 0,
                    head: GENESIS.into(),
                    verdict: "TAMPER".into(),
                    detail: format!("line {idx} is not JSON"),
                });
            }
        }
    }
    let mut st = ChainStatus {
        entries: entries.len(),
        links: 0,
        wraps: 0,
        head: GENESIS.into(),
        verdict: "EMPTY".into(),
        detail: "no entries yet".into(),
    };
    if entries.is_empty() {
        return Ok(st);
    }
    let mut prev = GENESIS.to_string();
    let mut link_hashes: Vec<String> = Vec::new();
    for (idx, e) in entries.iter().enumerate() {
        if sval(e, "prev") != prev {
            st.verdict = "TAMPER".into();
            st.detail = format!("weld breaks at entry {idx}");
            return Ok(st);
        }
        let body = Json::Obj(vec![
            ("ts".into(), get(e, "ts")),
            ("kind".into(), get(e, "kind")),
            ("payload".into(), get(e, "payload")),
            ("prev".into(), get(e, "prev")),
            ("actor".into(), get(e, "actor")),
        ]);
        let want = chain_hash(&prev, &body)?;
        if sval(e, "hash") != want {
            st.verdict = "FLIP".into();
            st.detail = format!("hash mismatch at entry {idx}, weld holds");
            return Ok(st);
        }
        let kind = sval(e, "kind");
        if kind == "link" {
            st.links += 1;
            link_hashes.push(sval(e, "hash"));
            if st.links as i64 % WRAP_SIZE == 0 {
                // A wrap must follow every 40th link.
                let w = entries.get(idx + 1);
                match w {
                    Some(w) if sval(w, "kind") == "wrap" => {
                        st.wraps += 1;
                        if let Err(d) = check_wrap(w, &link_hashes) {
                            st.verdict = "TAMPER".into();
                            st.detail = d;
                            return Ok(st);
                        }
                        link_hashes.clear();
                    }
                    _ => {
                        st.verdict = "TAMPER".into();
                        st.detail = format!("wrap missing after link {}", st.links);
                        return Ok(st);
                    }
                }
            }
        }
        prev = sval(e, "hash");
    }
    st.head = prev;
    st.verdict = "INTACT".into();
    st.detail = format!("{} links, {} wraps", st.links, st.wraps);
    Ok(st)
}

fn check_wrap(w: &Json, link_hashes: &[String]) -> Result<(), String> {
    let p = w.get("payload").cloned().unwrap_or(Json::Null);
    let root = sval(&p, "root");
    let from = num(&p, "from");
    let to = num(&p, "to");
    let mv = num(&p, "mv");
    let start = link_hashes.len().saturating_sub(WRAP_SIZE as usize);
    let slice = &link_hashes[start..];
    if slice.len() as i64 != to - from + 1 {
        return Err(format!("wrap spans {from}-{to} but holds {} links", slice.len()));
    }
    let want = if mv == 0 {
        merkle_v1(&slice.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    } else {
        merkle_v2(&slice.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    };
    if want != root {
        return Err(format!("wrap root mismatch (mv={mv})"));
    }
    Ok(())
}

// --- file + tiny helpers ----------------------------------------------------

fn read_raw_lines(chain: &Path) -> Result<Vec<String>, String> {
    if !chain.is_file() {
        return Ok(Vec::new());
    }
    let body = std::fs::read_to_string(chain).map_err(|e| format!("refused: {e}"))?;
    Ok(body
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.to_string())
        .collect())
}

fn read_entries(chain: &Path) -> Result<Vec<Json>, String> {
    if !chain.is_file() {
        return Ok(Vec::new());
    }
    let body = std::fs::read_to_string(chain).map_err(|e| format!("refused: {e}"))?;
    let mut out = Vec::new();
    for line in body.lines() {
        if line.trim().is_empty() {
            continue;
        }
        out.push(json::parse(line).map_err(|e| format!("refused: line is not JSON: {e:?}"))?);
    }
    Ok(out)
}

fn append_line(chain: &Path, line: &str) -> Result<(), String> {
    if let Some(parent) = chain.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|e| format!("refused: {e}"))?;
        }
    }
    let mut f = OpenOptions::new()
        .create(true)
        .append(true)
        .open(chain)
        .map_err(|e| format!("refused: {e}"))?;
    f.write_all(line.as_bytes()).map_err(|e| format!("refused: {e}"))?;
    f.write_all(b"\n").map_err(|e| format!("refused: {e}"))?;
    Ok(())
}

fn q(s: &str) -> String {
    pyjson::quote(s)
}

fn is_hex(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|c| c.is_ascii_hexdigit())
}

fn is_hash_len(s: &str) -> bool {
    (s.len() == 16 || s.len() == 40 || s.len() == 64)
        && s.bytes().all(|c| c.is_ascii_hexdigit())
}

fn get(v: &Json, key: &str) -> Json {
    v.get(key).cloned().unwrap_or(Json::Null)
}

fn sval(v: &Json, key: &str) -> String {
    match v.get(key) {
        Some(Json::Str(s)) => s.clone(),
        _ => String::new(),
    }
}

fn num(v: &Json, key: &str) -> i64 {
    match v.get(key) {
        Some(Json::Int(i)) => *i,
        Some(Json::Float(f)) => *f as i64,
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merkle_matches_oracle_both_versions() {
        // Probe-cut from links.py _merkle (sitting 19).
        let l3 = vec!["a".repeat(64), "b".repeat(64), "c".repeat(64)];
        assert_eq!(
            merkle_v1(&l3),
            "0993562e172c64ee4dc2ecb8525986a8fbd40bf0331d49f0a90d3467b19747e3"
        );
        assert_eq!(
            merkle_v2(&l3),
            "d73cea60f2ce124730a688b2456b84beb6fed822ab3e6d23c30c1ccdcbb5433b"
        );
        let l5 = vec!["0".repeat(64), "1".repeat(64), "2".repeat(64), "3".repeat(64), "4".repeat(64)];
        assert_eq!(
            merkle_v1(&l5),
            "c31bd8486d02f1f2f6c772f1be6786a9bdc62be163122d4fd849093d5f4aa401"
        );
        assert_eq!(
            merkle_v2(&l5),
            "e68425ce96c5fff3a5f4ee6d49a0c3c84088038a9f27a568ca501ce69507c345"
        );
        assert_eq!(
            merkle_v2(&["ab".repeat(32)]),
            "86754e71ab90f305c4faa7eee57b41b89e49ebcdf03a745c855ee611e4597237"
        );
    }

    #[test]
    fn lay_walk_wrap_close_on_temp_ground() {
        let dir = std::env::temp_dir().join(format!("atlas_link_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let chain = dir.join("chain.jsonl");
        for i in 1..=41 {
            let h = lay(&LayArgs {
                chain: chain.clone(),
                kind: "link".into(),
                says: format!("meal {i}"),
                actor: "neiro".into(),
                doc: format!("{{\"seq\":{i}}}"),
                mode: "open".into(),
                cites: vec!["65118a147dd49ed9".into()],
                sig: String::new(),
                pub_: String::new(),
            })
            .unwrap();
            assert_eq!(h.len(), 64);
        }
        let st = status(&chain).unwrap();
        assert_eq!(st.verdict, "INTACT");
        assert_eq!(st.links, 41);
        assert_eq!(st.wraps, 1);
        assert_eq!(st.entries, 42);
        // A flipped byte names FLIP; a dropped line names TAMPER.
        let body = std::fs::read_to_string(&chain).unwrap();
        let mut lines: Vec<&str> = body.lines().collect();
        lines[5] = &lines[5][..lines[5].len().min(200)];
        std::fs::write(&chain, lines.join("\n") + "\n").unwrap();
        let st = status(&chain).unwrap();
        assert!(st.verdict == "FLIP" || st.verdict == "TAMPER", "{}", st.verdict);
        std::fs::remove_dir_all(&dir).ok();
    }
}
