//! The trade books (D2-01): property / workorder / inspect / report,
//! ported grammar-for-grammar from `estate/Steward 1.0/skills/*.py`.
//!
//! Rust owns the sqlite book (workorders.db) through the A1 FFI seam — Go's
//! standard library has no sqlite, and the books stay byte-compatible either
//! way (sqlite files are portable; the JSONL chains hash identically via
//! core::pyjson, CPython `json.dumps(sort_keys)` byte mode).
//!
//! Two honest divergences, both witnessed in the sitting record:
//! 1. Clocks are UTC (`%Y-%m-%dT%H:%M:%S`), the oracle's are local. Output
//!    shapes match post-normalization (the golden cutter normalizes both),
//!    and stored timestamp STRINGS round-trip through both verifiers, so
//!    chains stay mutually verifiable.
//! 2. The oracle lets bad numbers raise (traceback, exit 1). The port
//!    refuses honestly (`refused: ...`, exit 1) — a refusal over a crash.
//!
//! Witness receipts ride in-band (`entry sealed at <hash[:12]>`), exactly as
//! the oracle's outputs carry them — no separate witness plumbing needed.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;

use atlas_core::json::{self, Json};
use atlas_core::pyjson;
use atlas_core::sha256;

pub const GENESIS: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";

/// Run one skill grammar against the ops ground. Unknown skills and bad
/// numbers are refused; unknown commands answer HELP, like the oracle.
pub fn run(skill: &str, arg: &str, base: &Path) -> Result<String, String> {
    match skill {
        "property" => Ok(property_run(arg, base)),
        "workorder" => workorder_run(arg, base),
        "inspect" => Ok(inspect_run(arg, base)),
        "report" => report_run(arg, base),
        _ => Err(format!("refused: no trade skill {skill:?} on the rack")),
    }
}

// --- shared ground --------------------------------------------------------

fn now_ts() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format_ymd_hms(secs, true)
}

/// UTC clock for fellow pens (links.py stamps local %z; atlas stamps UTC
/// with an explicit +0000 — same shape, honest zone).
pub(crate) fn utc_ts_penned() -> String {
    format!("{}+0000", now_ts())
}

fn today() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format_ymd_hms(secs, false)
}

fn format_ymd_hms(secs: u64, with_time: bool) -> String {
    // Civil-from-days (Howard Hinnant's algorithm), UTC.
    let days = (secs / 86400) as i64;
    let sod = secs % 86400;
    let z = days + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = (z - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let date = format!("{:04}-{:02}-{:02}", y + if m <= 2 { 1 } else { 0 }, m, d);
    if !with_time {
        return date;
    }
    format!(
        "{date}T{:02}:{:02}:{:02}",
        sod / 3600,
        (sod % 3600) / 60,
        sod % 60
    )
}

fn chain_hash(prev: &str, obj: &Json) -> Result<String, String> {
    let canon = pyjson::dumps(obj).map_err(|e| format!("refused: {e}"))?;
    Ok(sha256::hex_digest(format!("{prev}{canon}").as_bytes()))
}

fn read_lines(path: &Path) -> Vec<String> {
    let Ok(body) = fs::read_to_string(path) else {
        return Vec::new();
    };
    body.lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.to_string())
        .collect()
}

fn append_line(path: &Path, line: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("refused: {e}"))?;
    }
    let mut f = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| format!("refused: {e}"))?;
    // LF bytes, always: text-mode translation would smuggle CRLF on Windows
    // and every chain hash below would break (the faces lesson, kept).
    f.write_all(line.as_bytes())
        .map_err(|e| format!("refused: {e}"))?;
    f.write_all(b"\n").map_err(|e| format!("refused: {e}"))?;
    Ok(())
}

fn last_hash(path: &Path) -> String {
    let mut prev = GENESIS.to_string();
    for line in read_lines(path) {
        if let Ok(Json::Obj(_)) = json::parse(&line) {}
        if let Ok(v) = json::parse(&line) {
            if let Some(Json::Str(h)) = v.get("hash") {
                prev = h.clone();
            }
        }
    }
    prev
}

fn split_arg(arg: &str) -> (String, String, Vec<String>) {
    let parts: Vec<String> = arg.split('|').map(|p| p.trim().to_string()).collect();
    let head = parts.first().cloned().unwrap_or_default();
    let mut words = head.split_whitespace();
    let cmd = words.next().unwrap_or("").to_lowercase();
    let rest = head[cmd.len().min(head.len())..].trim().to_string();
    // NOTE: cmd is lowercase; rest slices the ORIGINAL head by the lowercase
    // cmd's byte length — identical to the oracle, whose cmds are ASCII.
    let _ = words;
    (cmd, rest, parts)
}

// --- property -------------------------------------------------------------

const PROPERTY_HELP: &str = "commands:  enroll <name> | <address / notes>   ·   list\n           show <name>   ·   verify";

fn property_run(arg: &str, base: &Path) -> String {
    let path = base.join("properties.jsonl");
    let (cmd, rest, parts) = split_arg(arg);
    match cmd.as_str() {
        "enroll" => {
            if rest.is_empty() {
                return "enroll needs:  enroll <name> | <address / notes>".into();
            }
            for line in read_lines(&path) {
                if let Ok(v) = json::parse(&line) {
                    if let Some(Json::Str(n)) = v.get("name") {
                        if n.to_lowercase() == rest.to_lowercase() {
                            return format!("{rest} is already enrolled — the roster folds, it does not repeat.");
                        }
                    }
                }
            }
            let prev = last_hash(&path);
            let body = Json::Obj(vec![
                ("ts".into(), Json::Str(now_ts())),
                ("name".into(), Json::Str(rest.clone())),
                ("notes".into(), Json::Str(parts.get(1).cloned().unwrap_or_default())),
            ]);
            let mut flat = obj_without(&body, &[]);
            flat.push(("prev".into(), Json::Str(prev.clone())));
            let hashable = Json::Obj(vec![
                ("ts".into(), get(&body, "ts")),
                ("name".into(), get(&body, "name")),
                ("notes".into(), Json::Str(parts.get(1).cloned().unwrap_or_default())),
            ]);
            let hash = match chain_hash(&prev, &hashable) {
                Ok(h) => h,
                Err(e) => return e,
            };
            flat.push(("hash".into(), Json::Str(hash.clone())));
            let line = match pyjson::dumps(&Json::Obj(flat)) {
                Ok(l) => l,
                Err(e) => return e,
            };
            if let Err(e) = append_line(&path, &line) {
                return e;
            }
            let ts: String = match get(&body, "ts") {
                Json::Str(s) => s[..10].to_string(),
                _ => String::new(),
            };
            format!("enrolled {rest} — in his care as of {ts}. entry sealed at {}", &hash[..12])
        }
        "list" => {
            let entries = read_lines(&path);
            if entries.is_empty() {
                return "the roster is empty — no properties in his care yet.".into();
            }
            let mut out = Vec::new();
            for line in entries {
                let Ok(v) = json::parse(&line) else { continue };
                let name = sval(&v, "name");
                let ts = sval(&v, "ts");
                let notes = sval(&v, "notes");
                let hash = sval(&v, "hash");
                out.push(format!(
                    "{} — since {}{}  [{}]",
                    name,
                    ts.get(..10).unwrap_or(&ts),
                    if notes.is_empty() { String::new() } else { format!(" · {notes}") },
                    hash.get(..12).unwrap_or(&hash),
                ));
            }
            out.join("\n")
        }
        "show" => {
            if rest.is_empty() {
                return "show needs a name:  show <property>".into();
            }
            for line in read_lines(&path) {
                let Ok(v) = json::parse(&line) else { continue };
                let name = sval(&v, "name");
                if name.to_lowercase().contains(&rest.to_lowercase()) {
                    let ts = sval(&v, "ts");
                    let notes = sval(&v, "notes");
                    let hash = sval(&v, "hash");
                    return format!(
                        "{} — enrolled {}{}  [{}]",
                        name,
                        ts.get(..10).unwrap_or(&ts),
                        if notes.is_empty() { String::new() } else { format!(" · {notes}") },
                        hash.get(..12).unwrap_or(&hash),
                    );
                }
            }
            format!("no record of that property: {rest}")
        }
        "verify" => {
            let mut prev = GENESIS.to_string();
            let mut n = 0;
            for line in read_lines(&path) {
                let Ok(v) = json::parse(&line) else { continue };
                let hashable = Json::Obj(vec![
                    ("ts".into(), get(&v, "ts")),
                    ("name".into(), get(&v, "name")),
                    ("notes".into(), get(&v, "notes")),
                ]);
                let want = match chain_hash(&prev, &hashable) {
                    Ok(h) => h,
                    Err(e) => return e,
                };
                if sval(&v, "prev") != prev || sval(&v, "hash") != want {
                    return format!("property roster BROKEN at entry {n} ({})", sval(&v, "name"));
                }
                prev = sval(&v, "hash");
                if prev.is_empty() {
                    prev = want;
                }
                n += 1;
            }
            format!("property roster intact ({n} entries)")
        }
        _ => PROPERTY_HELP.into(),
    }
}

fn obj_without(body: &Json, _skip: &[&str]) -> Vec<(String, Json)> {
    match body {
        Json::Obj(pairs) => pairs.clone(),
        _ => Vec::new(),
    }
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

// --- workorder ------------------------------------------------------------

const WORKORDER_HELP: &str = "commands:  add <property> | <issue> [| <vendor>]   ·   assign <id> | <vendor>\n           done <id> | <cost>   ·   list [open|done|all]   ·   verify";

fn wo_db(base: &Path) -> Result<crate::driver::Conn, String> {
    let conn = crate::driver::Conn::open(&base.join("workorders.db"))
        .map_err(|e| format!("refused: {}", e.msg))?;
    conn.exec(
        "CREATE TABLE IF NOT EXISTS wo (id INTEGER PRIMARY KEY, property TEXT, issue TEXT, vendor TEXT, status TEXT, cost REAL, opened TEXT, closed TEXT)",
    )
    .map_err(|e| format!("refused: {}", e.msg))?;
    Ok(conn)
}

fn wo_audit(base: &Path, event: Json) -> Result<String, String> {
    let path = base.join("workorders_audit.jsonl");
    let prev = last_hash(&path);
    let hash = chain_hash(&prev, &event)?;
    // The audit nests the event under "event" (the oracle's shape):
    // {ts, event, prev, hash}. The hash covers the event ALONE.
    let line = pyjson::dumps(&Json::Obj(vec![
        ("ts".into(), Json::Str(now_ts())),
        ("event".into(), event),
        ("prev".into(), Json::Str(prev)),
        ("hash".into(), Json::Str(hash.clone())),
    ]))
    .map_err(|e| format!("refused: {e}"))?;
    append_line(&path, &line)?;
    Ok(hash)
}

fn wo_verify(base: &Path) -> String {
    let path = base.join("workorders_audit.jsonl");
    if !path.is_file() {
        return "audit chain intact (0 entries)".into();
    }
    let mut prev = GENESIS.to_string();
    let mut n = 0;
    for line in read_lines(&path) {
        let Ok(v) = json::parse(&line) else { continue };
        // The hashed kernel is the nested event object alone.
        let event = get(&v, "event");
        let want = match chain_hash(&prev, &event) {
            Ok(h) => h,
            Err(e) => return e,
        };
        if sval(&v, "prev") != prev || sval(&v, "hash") != want {
            return format!("audit chain BROKEN at entry {n}");
        }
        prev = sval(&v, "hash");
        n += 1;
    }
    format!("audit chain intact ({n} entries)")
}

fn money(cost: f64) -> String {
    format!("${cost:.2}")
}

fn workorder_run(arg: &str, base: &Path) -> Result<String, String> {
    let (cmd, rest, parts) = split_arg(arg);
    match cmd.as_str() {
        "add" => {
            let issue = parts.get(1).cloned().unwrap_or_default();
            let vendor = parts.get(2).cloned().unwrap_or_default();
            if rest.is_empty() || issue.is_empty() {
                return Ok("add needs:  add <property> | <issue> [| <vendor>]".into());
            }
            let conn = wo_db(base)?;
            let ins = conn
                .prepare("INSERT INTO wo (property,issue,vendor,status,cost,opened,closed) VALUES (?,?,?,?,?,?,?)")
                .map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(1, &rest).map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(2, &issue).map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(3, &vendor).map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(4, "open").map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_double(5, 0.0).map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(6, &today()).map_err(|e| format!("refused: {}", e.msg))?;
            ins.bind_text(7, "").map_err(|e| format!("refused: {}", e.msg))?;
            match ins.step() {
                Ok(crate::driver::Step::Done) | Ok(crate::driver::Step::Row) => {}
                Err(e) => return Err(format!("refused: {}", e.msg)),
            }
            let id = conn.last_insert_rowid();
            wo_audit(
                base,
                Json::Obj(vec![
                    ("op".into(), Json::Str("add".into())),
                    ("id".into(), Json::Int(id)),
                    ("property".into(), Json::Str(rest.clone())),
                    ("issue".into(), Json::Str(issue.clone())),
                    ("vendor".into(), Json::Str(vendor.clone())),
                ]),
            )?;
            let v = if vendor.is_empty() { "unassigned" } else { &vendor };
            Ok(format!("opened work order #{id}: {rest} — {issue} (vendor: {v})"))
        }
        "assign" => {
            let wid: i64 = rest.parse().map_err(|_| format!("refused: assign needs a work-order id, not {rest:?}"))?;
            let vendor = parts.get(1).cloned().unwrap_or_default();
            let conn = wo_db(base)?;
            let up = conn
                .prepare("UPDATE wo SET vendor=? WHERE id=?")
                .map_err(|e| format!("refused: {}", e.msg))?;
            up.bind_text(1, &vendor).map_err(|e| format!("refused: {}", e.msg))?;
            up.bind_int64(2, wid).map_err(|e| format!("refused: {}", e.msg))?;
            match up.step() {
                Ok(_) => {}
                Err(e) => return Err(format!("refused: {}", e.msg)),
            }
            wo_audit(
                base,
                Json::Obj(vec![
                    ("op".into(), Json::Str("assign".into())),
                    ("id".into(), Json::Int(wid)),
                    ("vendor".into(), Json::Str(vendor.clone())),
                ]),
            )?;
            Ok(format!("work order #{wid} assigned to {vendor}"))
        }
        "done" => {
            let wid: i64 = rest.parse().map_err(|_| format!("refused: done needs a work-order id, not {rest:?}"))?;
            let cost: f64 = if parts.len() > 1 {
                parts[1].parse().map_err(|_| format!("refused: done needs a cost number, not {:?}", parts[1]))?
            } else {
                0.0
            };
            let conn = wo_db(base)?;
            let up = conn
                .prepare("UPDATE wo SET status='done', cost=?, closed=? WHERE id=?")
                .map_err(|e| format!("refused: {}", e.msg))?;
            up.bind_double(1, cost).map_err(|e| format!("refused: {}", e.msg))?;
            up.bind_text(2, &today()).map_err(|e| format!("refused: {}", e.msg))?;
            up.bind_int64(3, wid).map_err(|e| format!("refused: {}", e.msg))?;
            match up.step() {
                Ok(_) => {}
                Err(e) => return Err(format!("refused: {}", e.msg)),
            }
            wo_audit(
                base,
                Json::Obj(vec![
                    ("op".into(), Json::Str("done".into())),
                    ("id".into(), Json::Int(wid)),
                    ("cost".into(), Json::Float(cost)),
                ]),
            )?;
            Ok(format!("work order #{wid} closed at {}", money(cost)))
        }
        "list" => {
            let want = if rest.is_empty() { "open".to_string() } else { rest.to_lowercase() };
            let mut q = "SELECT id,property,issue,vendor,status,cost FROM wo".to_string();
            if want == "open" || want == "done" {
                q.push_str(&format!(" WHERE status='{want}'"));
            }
            q.push_str(" ORDER BY id");
            let conn = wo_db(base)?;
            let sel = conn.prepare(&q).map_err(|e| format!("refused: {}", e.msg))?;
            let mut rows = Vec::new();
            loop {
                match sel.step().map_err(|e| format!("refused: {}", e.msg))? {
                    crate::driver::Step::Row => {
                        rows.push((
                            sel.int64(0),
                            sel.text(1).unwrap_or_default(),
                            sel.text(2).unwrap_or_default(),
                            sel.text(3).unwrap_or_default(),
                            sel.text(4).unwrap_or_default(),
                            sel.real(5),
                        ));
                    }
                    crate::driver::Step::Done => break,
                }
            }
            if rows.is_empty() {
                return Ok(format!("no {want} work orders."));
            }
            Ok(rows
                .iter()
                .map(|(id, prop, issue, vendor, status, cost)| {
                    let v = if vendor.is_empty() { "unassigned" } else { vendor };
                    format!("#{id} [{status}] {prop} — {issue} (vendor: {v}, {})", money(*cost))
                })
                .collect::<Vec<_>>()
                .join("\n"))
        }
        "verify" => Ok(wo_verify(base)),
        _ => Ok(WORKORDER_HELP.into()),
    }
}

// --- inspect --------------------------------------------------------------

const INSPECT_HELP: &str = "commands:  log <property> | item=result ; item=result ... [| <notes>]\n           report <property>   ·   verify";

const FAIL_WORDS: &[&str] = &["fail", "failed", "no"];

fn is_fail(v: &str) -> bool {
    FAIL_WORDS.contains(&v.to_lowercase().as_str())
}

/// The checklist in file order. The core JSON parser sorts object keys
/// (canon law), but the oracle renders checks in INSERTION order — output
/// parity needs the file's own order. Hashes are unaffected (dumps sorts).
/// A 60-line scanner, quoted strings with escapes, flat string values.
fn ordered_checks(line: &str) -> Vec<(String, String)> {
    let b = line.as_bytes();
    let Some(mut i) = find_key(b, b"\"checks\"") else {
        return Vec::new();
    };
    i += 8;
    skip_ws(b, &mut i);
    if b.get(i) != Some(&b':') {
        return Vec::new();
    }
    i += 1;
    skip_ws(b, &mut i);
    if b.get(i) != Some(&b'{') {
        return Vec::new();
    }
    i += 1;
    let mut out = Vec::new();
    loop {
        skip_ws(b, &mut i);
        if b.get(i) == Some(&b'}') {
            break;
        }
        let Some((k, ni)) = scan_string(b, i) else { break };
        i = ni;
        skip_ws(b, &mut i);
        if b.get(i) != Some(&b':') {
            break;
        }
        i += 1;
        skip_ws(b, &mut i);
        let Some((v, ni)) = scan_string(b, i) else { break };
        i = ni;
        out.push((k, v));
        skip_ws(b, &mut i);
        if b.get(i) == Some(&b',') {
            i += 1;
        } else if b.get(i) != Some(&b'}') {
            break;
        }
    }
    out
}

fn find_key(hay: &[u8], needle: &[u8]) -> Option<usize> {
    hay.windows(needle.len()).position(|w| w == needle)
}

fn skip_ws(b: &[u8], i: &mut usize) {
    while *i < b.len() && matches!(b[*i], b' ' | b'\t' | b'\n' | b'\r') {
        *i += 1;
    }
}

fn scan_string(b: &[u8], mut i: usize) -> Option<(String, usize)> {
    if b.get(i) != Some(&b'"') {
        return None;
    }
    i += 1;
    let mut s = String::new();
    loop {
        let c = *b.get(i)?;
        match c {
            b'"' => return Some((s, i + 1)),
            b'\\' => {
                i += 1;
                match *b.get(i)? {
                    b'"' => s.push('"'),
                    b'\\' => s.push('\\'),
                    b'/' => s.push('/'),
                    b'b' => s.push('\u{08}'),
                    b'f' => s.push('\u{0c}'),
                    b'n' => s.push('\n'),
                    b'r' => s.push('\r'),
                    b't' => s.push('\t'),
                    b'u' => {
                        let hex = std::str::from_utf8(b.get(i + 1..i + 5)?).ok()?;
                        let mut cp = u32::from_str_radix(hex, 16).ok()?;
                        i += 4;
                        // Surrogate pair: high followed by \uDC00–DFFF.
                        if (0xd800..0xdc00).contains(&cp)
                            && b.get(i + 1) == Some(&b'\\')
                            && b.get(i + 2) == Some(&b'u')
                        {
                            let hex2 = std::str::from_utf8(b.get(i + 3..i + 7)?).ok()?;
                            let lo = u32::from_str_radix(hex2, 16).ok()?;
                            if (0xdc00..0xe000).contains(&lo) {
                                cp = 0x10000 + ((cp - 0xd800) << 10) + (lo - 0xdc00);
                                i += 6;
                            }
                        }
                        s.push(char::from_u32(cp).unwrap_or('\u{fffd}'));
                    }
                    _ => return None,
                }
                i += 1;
            }
            _ => {
                // Multibyte UTF-8 copies through whole.
                let w = if c < 0x80 {
                    1
                } else if c >> 5 == 0b110 {
                    2
                } else if c >> 4 == 0b1110 {
                    3
                } else {
                    4
                };
                s.push_str(std::str::from_utf8(b.get(i..i + w)?).ok()?);
                i += w;
            }
        }
    }
}

fn inspect_run(arg: &str, base: &Path) -> String {
    let path = base.join("inspections.jsonl");
    let (cmd, rest, parts) = split_arg(arg);
    match cmd.as_str() {
        "log" => {
            if rest.is_empty() || parts.len() < 2 {
                return "log needs:  log <property> | item=result ; item=result [| notes]".into();
            }
            let mut checks: Vec<(String, Json)> = Vec::new();
            for item in parts[1].split(';') {
                if let Some((k, v)) = item.split_once('=') {
                    checks.push((k.trim().to_string(), Json::Str(v.trim().to_string())));
                }
            }
            let notes = parts.get(2).cloned().unwrap_or_default();
            let prev = last_hash(&path);
            let ts = now_ts();
            let checks_obj = Json::Obj(checks.clone());
            let hashable = Json::Obj(vec![
                ("ts".into(), Json::Str(ts.clone())),
                ("property".into(), Json::Str(rest.clone())),
                ("checks".into(), checks_obj),
                ("notes".into(), Json::Str(notes.clone())),
            ]);
            let hash = match chain_hash(&prev, &hashable) {
                Ok(h) => h,
                Err(e) => return e,
            };
            // Stored line keeps the checks in TYPED order (the oracle's
            // insertion order): report output renders file order. The hash
            // above covers the SORTED form either way, so verification is
            // order-free on both sides.
            let checks_line = checks
                .iter()
                .map(|(k, v)| {
                    let s = match v {
                        Json::Str(s) => s.clone(),
                        _ => String::new(),
                    };
                    format!("{}: {}", pyjson::quote(k), pyjson::quote(&s))
                })
                .collect::<Vec<_>>()
                .join(", ");
            let line = format!(
                "{{\"ts\": {}, \"property\": {}, \"checks\": {{{}}}, \"notes\": {}, \"prev\": {}, \"hash\": {}}}",
                pyjson::quote(&ts),
                pyjson::quote(&rest),
                checks_line,
                pyjson::quote(&notes),
                pyjson::quote(&prev),
                pyjson::quote(&hash),
            );
            if let Err(e) = append_line(&path, &line) {
                return e;
            }
            let fails: Vec<String> = checks
                .iter()
                .filter(|(_, v)| matches!(v, Json::Str(s) if is_fail(s)))
                .map(|(k, _)| k.clone())
                .collect();
            let middle = if fails.is_empty() {
                "all pass".to_string()
            } else {
                format!("{} FAILED: {}", fails.len(), fails.join(", "))
            };
            format!(
                "inspection logged for {rest} — {} item(s), {middle}. entry sealed at {}",
                checks.len(),
                &hash[..12]
            )
        }
        "report" => {
            if !path.is_file() {
                return "no inspections on file.".into();
            }
            let mut out = Vec::new();
            for line in read_lines(&path) {
                let Ok(v) = json::parse(&line) else { continue };
                let prop = sval(&v, "property");
                if !rest.is_empty() && !prop.to_lowercase().contains(&rest.to_lowercase()) {
                    continue;
                }
                // File order, not key order (see ordered_checks).
                let marks = ordered_checks(&line)
                    .iter()
                    .map(|(k, s)| format!("{k}: {s}"))
                    .collect::<Vec<_>>()
                    .join(", ");
                let ts = sval(&v, "ts");
                let notes = sval(&v, "notes");
                let hash = sval(&v, "hash");
                out.push(format!(
                    "{ts}  {prop} — {}{}  [{}]",
                    marks,
                    if notes.is_empty() { String::new() } else { format!(" · {notes}") },
                    hash.get(..12).unwrap_or(&hash),
                ));
            }
            if out.is_empty() {
                return format!("nothing on file for '{rest}'.");
            }
            out.join("\n")
        }
        "verify" => {
            if !path.is_file() {
                return "inspection chain intact (0 entries)".into();
            }
            let mut prev = GENESIS.to_string();
            let mut n = 0;
            for line in read_lines(&path) {
                let Ok(v) = json::parse(&line) else { continue };
                let hashable = Json::Obj(vec![
                    ("ts".into(), get(&v, "ts")),
                    ("property".into(), get(&v, "property")),
                    ("checks".into(), get(&v, "checks")),
                    ("notes".into(), get(&v, "notes")),
                ]);
                let want = match chain_hash(&prev, &hashable) {
                    Ok(h) => h,
                    Err(e) => return e,
                };
                if sval(&v, "prev") != prev || sval(&v, "hash") != want {
                    return format!("inspection chain BROKEN at entry {n} ({})", sval(&v, "property"));
                }
                prev = sval(&v, "hash");
                n += 1;
            }
            format!("inspection chain intact ({n} entries)")
        }
        _ => INSPECT_HELP.into(),
    }
}

// --- report ---------------------------------------------------------------

fn report_slug(prop: &str) -> String {
    let mut s = String::new();
    let mut under = false;
    for c in prop.to_lowercase().chars() {
        if c.is_ascii_alphanumeric() {
            s.push(c);
            under = false;
        } else if !under {
            s.push('_');
            under = true;
        }
    }
    s.trim_matches('_').to_string()
}

fn report_run(arg: &str, base: &Path) -> Result<String, String> {
    let collapsed: String = arg.split_whitespace().collect::<Vec<_>>().join(" ");
    if collapsed.is_empty() {
        return Ok("usage:  <property> [since YYYY-MM-DD>".into());
    }
    let (prop, since) = match find_since(&collapsed) {
        Some((p, s)) => (p, s),
        None => (collapsed.trim().to_string(), String::new()),
    };
    if prop.is_empty() {
        return Ok("usage:  <property> [since YYYY-MM-DD>".into());
    }
    let enrolled = property_run(&format!("show {prop}"), base);
    if enrolled.starts_with("no record") {
        return Ok(format!(
            "no record of that property: {prop}. The report does not invent; enroll it first (:skill property enroll <name> | <notes>)."
        ));
    }
    // Work orders naming the property (substring, case-insensitive).
    // A missing book reads as empty — the report does not invent books.
    let mut wos: Vec<(i64, String, String, String, String, f64, String, String)> = Vec::new();
    if base.join("workorders.db").is_file() {
        let conn = wo_db(base)?;
        let sel = conn
            .prepare("SELECT id,property,issue,vendor,status,cost,opened,closed FROM wo ORDER BY id")
            .map_err(|e| format!("refused: {}", e.msg))?;
        loop {
            match sel.step().map_err(|e| format!("refused: {}", e.msg))? {
                crate::driver::Step::Row => {
                    wos.push((
                        sel.int64(0),
                        sel.text(1).unwrap_or_default(),
                        sel.text(2).unwrap_or_default(),
                        sel.text(3).unwrap_or_default(),
                        sel.text(4).unwrap_or_default(),
                        sel.real(5),
                        sel.text(6).unwrap_or_default(),
                        sel.text(7).unwrap_or_default(),
                    ));
                }
                crate::driver::Step::Done => break,
            }
        }
    }
    let wos: Vec<_> = wos
        .into_iter()
        .filter(|r| r.1.to_lowercase().contains(&prop.to_lowercase()))
        .filter(|r| {
            if since.is_empty() {
                return true;
            }
            let stamp = if r.7.is_empty() { r.6.clone() } else { r.7.clone() };
            stamp >= since
        })
        .collect();
    // Receipts: last audit hash per work-order id.
    let mut receipts = std::collections::HashMap::new();
    for line in read_lines(&base.join("workorders_audit.jsonl")) {
        let Ok(v) = json::parse(&line) else { continue };
        let hash = sval(&v, "hash");
        if let Some(ev) = v.get("event") {
            if let Some(Json::Int(wid)) = ev.get("id") {
                receipts.insert(*wid, hash);
            }
        }
    }
    // Visits naming the property (raw line kept beside the parse: the
    // checklist renders in file order — see ordered_checks).
    let mut visits: Vec<(String, Json)> = Vec::new();
    for line in read_lines(&base.join("inspections.jsonl")) {
        let Ok(v) = json::parse(&line) else { continue };
        let pname = sval(&v, "property");
        if !pname.to_lowercase().contains(&prop.to_lowercase()) {
            continue;
        }
        if !since.is_empty() && sval(&v, "ts").get(..10).unwrap_or("") < since.as_str() {
            continue;
        }
        visits.push((line, v));
    }
    let verdicts = vec![
        property_run("verify", base),
        wo_verify(base),
        inspect_run("verify", base),
    ];
    let whole = verdicts.iter().all(|v| v.contains("intact"));
    let today_s = today();
    let span = if since.is_empty() {
        "the whole record".to_string()
    } else {
        format!("{since} to {today_s}")
    };
    let head_name = enrolled.split(" — ").next().unwrap_or(&enrolled);
    let head_rest = enrolled.split("  [").next().unwrap_or(&enrolled);
    let mut lines = vec![
        format!("# OWNER REPORT — {head_name}"),
        format!("*Prepared {today_s} · covering {span} · {head_rest}*"),
        String::new(),
        format!("## THE VISITS — {} inspection(s)", visits.len()),
    ];
    if visits.is_empty() {
        lines.push("no inspections in this span.".into());
    }
    for (raw, e) in &visits {
        let ordered = ordered_checks(raw);
        let mut fails = Vec::new();
        let mut marks = Vec::new();
        for (k, s) in &ordered {
            marks.push(format!("{k}: {s}"));
            if is_fail(s) {
                fails.push(k.clone());
            }
        }
        // NOTE: operator-precedence trap lives here in the oracle too
        // (`a if fails else b` binds the whole concatenation): the middle is
        // "**N FAILED: ..**" when fails, else "all pass" — then notes append.
        let middle = if fails.is_empty() {
            "all pass".to_string()
        } else {
            format!("**{} FAILED: {}**", fails.len(), fails.join(", "))
        };
        let tail = format!("{}{}  · receipt {}", middle, {
            let n = sval(e, "notes");
            if n.is_empty() { String::new() } else { format!(" · {n}") }
        }, sval(e, "hash").get(..12).unwrap_or(""));
        lines.push(format!(
            "- {} — {} — {}",
            sval(e, "ts").get(..16).unwrap_or("").replace('T', " "),
            marks.join(", "),
            tail
        ));
    }
    lines.push(String::new());
    lines.push(format!("## THE WORK — {} work order(s)", wos.len()));
    if wos.is_empty() {
        lines.push("no work orders in this span.".into());
    }
    let mut total = 0.0;
    for (wid, _p, issue, vendor, status, cost, opened, closed) in &wos {
        total += cost;
        let v = if vendor.is_empty() { "unassigned" } else { vendor };
        let closed_part = if status == "done" {
            format!(" · closed {closed} at {}", money(*cost))
        } else {
            String::new()
        };
        let receipt = receipts
            .get(wid)
            .map(|h| h.get(..12).unwrap_or(h).to_string())
            .unwrap_or_else(|| "—".to_string());
        lines.push(format!(
            "- #{wid} [{status}] — {issue} (vendor: {v}) · opened {opened}{closed_part}  · receipt {receipt}"
        ));
    }
    if !wos.is_empty() {
        lines.push(format!("- work billed in this span: {}", money(total)));
    }
    lines.push(String::new());
    lines.push("## THE VERDICT".into());
    if whole {
        lines.push("**This record proves whole.** All three chains rewalk clean — the roster, the work-order audit, and the inspection log. Not one line above could have been altered without breaking the chain that seals it.".into());
    } else {
        lines.push("**This record does NOT prove whole.** The verdict is refused, and the break is named:".into());
    }
    for v in &verdicts {
        lines.push(format!("- {v}"));
    }
    let text = lines.join("\n");
    let reports = base.join("reports");
    fs::create_dir_all(&reports).map_err(|e| format!("refused: {e}"))?;
    let out_path = reports.join(format!("{}_{today_s}.md", report_slug(&prop)));
    fs::write(&out_path, format!("{text}\n")).map_err(|e| format!("refused: {e}"))?;
    Ok(format!("{text}\n\n(written to {})", out_path.display()))
}

fn find_since(arg: &str) -> Option<(String, String)> {
    // `\s+since\s+(\d{4}-\d{2}-\d{2})$` — hand-rolled, no regex crate.
    // The date must be a valid YYYY-MM-DD tail; "since" must stand alone
    // on whitespace.
    if arg.len() < 18 {
        return None;
    }
    let (head, tail) = arg.split_at(arg.len() - 10);
    let d: Vec<char> = tail.chars().collect();
    let is_date = d.len() == 10
        && d[0].is_ascii_digit() && d[1].is_ascii_digit()
        && d[2].is_ascii_digit() && d[3].is_ascii_digit()
        && d[4] == '-' && d[5].is_ascii_digit() && d[6].is_ascii_digit()
        && d[7] == '-' && d[8].is_ascii_digit() && d[9].is_ascii_digit();
    if !is_date {
        return None;
    }
    let words: Vec<&str> = head.split_whitespace().collect();
    if words.last().is_some_and(|w| w.to_lowercase() == "since") {
        let prop = head[..head.trim_end().len() - 5].trim().to_string();
        return Some((prop, tail.to_string()));
    }
    None
}
