//! `.us` declaration grammar (THE_CATALOG R4 · SPEC_US).
//!
//! Byte-faithful mirror of the oracle (`estate/Neiro/lib/us_read.py`):
//! prose carrying fenced JSON blocks, one module per document, and the
//! structural gate — `can_approve` must be stated explicitly false; absence
//! is a refusal, never a default. Render is deterministic (sorted keys,
//! indent 2) so folded declarations compare byte for byte.
//!
//! Every assertion meets the cut oracle vectors (tests/fixtures/canon/
//! us_vectors.json, A2-01/A2-02), never an opinion formed here.

use crate::canon::python_repr;
use crate::json::{self, Json};
use std::path::Path;

pub const US_VERSION: i64 = 1;
pub const KINDS: [&str; 4] = ["module", "agent", "tool", "skill"];
pub const MODES: [&str; 2] = ["primary", "subagent"];
pub const FENCE: &str = "```";
pub const FENCE_TAGS: [&str; 3] = ["json", "us", "json us"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UsRefused {
    NotAnObject,
    BadVersion,
    BadKind,
    BadId,
    StemMismatch,
    CanApproveAbsent,
    CanApproveNotFalse,
    ModuleMissingField(&'static str),
    RowsEmpty,
    VerbsEmpty,
    BadMode,
    AgentPermissionMissing,
    NoModuleBlock,
    MultipleModules(usize),
    DocumentErrors(String),
}

impl UsRefused {
    /// The named class vocabulary shared with the golden cut; never guess.
    pub fn class(&self) -> &'static str {
        match self {
            UsRefused::NotAnObject => "not_an_object",
            UsRefused::BadVersion => "bad_version",
            UsRefused::BadKind => "bad_kind",
            UsRefused::BadId => "bad_id",
            UsRefused::StemMismatch => "stem_mismatch",
            UsRefused::CanApproveAbsent => "can_approve_absent",
            UsRefused::CanApproveNotFalse => "can_approve_not_false",
            UsRefused::ModuleMissingField(_) => "module_missing_field",
            UsRefused::RowsEmpty => "rows_empty",
            UsRefused::VerbsEmpty => "verbs_empty",
            UsRefused::BadMode => "bad_mode",
            UsRefused::AgentPermissionMissing => "agent_permission_missing",
            UsRefused::NoModuleBlock => "no_module_block",
            UsRefused::MultipleModules(_) => "multiple_modules",
            UsRefused::DocumentErrors(_) => "document_errors",
        }
    }
}

impl std::fmt::Display for UsRefused {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            UsRefused::NotAnObject => write!(f, "a declaration must be a JSON object"),
            UsRefused::BadVersion => write!(f, "us must be {}", US_VERSION),
            UsRefused::BadKind => write!(f, "kind must be one of {}", KINDS.join(", ")),
            UsRefused::BadId => write!(f, "id is required, lowercase kebab or snake"),
            UsRefused::StemMismatch => write!(f, "a module's id must match its filename"),
            UsRefused::CanApproveAbsent => write!(
                f,
                "can_approve must be stated: invariant 6 is enforced by \
                 structure, not assumed"
            ),
            UsRefused::CanApproveNotFalse => write!(
                f,
                "can_approve must be false: no code path runs from \
                 autonomous work to approve"
            ),
            UsRefused::ModuleMissingField(field) => {
                write!(f, "a module must declare {:?}", field)
            }
            UsRefused::RowsEmpty => write!(f, "rows must be a non-empty list"),
            UsRefused::VerbsEmpty => write!(f, "verbs must be a non-empty list"),
            UsRefused::BadMode => write!(f, "an agent's mode must be one of {}", MODES.join(", ")),
            UsRefused::AgentPermissionMissing => write!(
                f,
                "an agent must declare permission - it is canonical, and a \
                 vendor tool list folds down from it"
            ),
            UsRefused::NoModuleBlock => write!(f, "the document declares no module block"),
            UsRefused::MultipleModules(n) => {
                write!(f, "a .us file declares exactly one module; found {}", n)
            }
            UsRefused::DocumentErrors(e) => write!(f, "{}", e),
        }
    }
}

impl std::error::Error for UsRefused {}

type Result<T> = std::result::Result<T, UsRefused>;

#[derive(Debug, Clone, Default)]
pub struct UsDoc {
    pub prose: String,
    pub blocks: Vec<Json>,
    pub errors: Vec<String>,
    pub path: Option<String>,
    pub stem: Option<String>,
}

/// Split a .us into prose and blocks. Line-scanned rather than matched by
/// pattern, so nothing depends on escape handling — the oracle's own rule.
pub fn parse(text: &str) -> UsDoc {
    let mut prose: Vec<&str> = Vec::new();
    let mut blocks = Vec::new();
    let mut errors = Vec::new();
    let mut inside = false;
    let mut buf = String::new();
    let mut tag: Option<(String, usize)> = None;

    for (lineno, raw) in text.lines().enumerate() {
        let lineno = lineno + 1;
        let stripped = raw.trim();
        if !inside && stripped.starts_with(FENCE) {
            let candidate = stripped[FENCE.len()..].trim().to_lowercase();
            if FENCE_TAGS.contains(&candidate.as_str()) {
                inside = true;
                buf.clear();
                tag = Some((candidate, lineno));
            } else {
                prose.push(raw); // a fence we do not read is prose
            }
            continue;
        }
        if inside && stripped == FENCE {
            match json::parse(buf.trim()) {
                Ok(v) => blocks.push(v),
                Err(e) => errors.push(format!(
                    "block opened at line {} is not JSON: {}",
                    tag.as_ref().map(|t| t.1).unwrap_or(0),
                    e.msg
                )),
            }
            inside = false;
            buf.clear();
            tag = None;
            continue;
        }
        if inside {
            buf.push_str(raw);
            buf.push('\n');
        } else {
            prose.push(raw);
        }
    }
    if let Some((t, l)) = tag {
        errors.push(format!("a {} block opened at line {} was never closed", t, l));
    }
    UsDoc {
        prose: prose.join("\n").trim().to_string(),
        blocks,
        errors,
        path: None,
        stem: None,
    }
}

/// Read a .us from disk, carrying its path and stem like `load` does.
pub fn load(path: &Path) -> std::io::Result<UsDoc> {
    let bytes = std::fs::read(path)?;
    let text = String::from_utf8_lossy(&bytes).into_owned(); // errors="replace"
    let mut doc = parse(&text);
    doc.path = Some(path.to_string_lossy().into_owned());
    doc.stem = path
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned());
    Ok(doc)
}

fn field<'a>(block: &'a Json, key: &str) -> Option<&'a Json> {
    block.get(key)
}

/// Refuse a declaration that cannot be trusted. Absence is never a default:
/// a field that decides authority must be stated.
pub fn validate(block: &Json, stem: Option<&str>) -> Result<()> {
    if !matches!(block, Json::Obj(_)) {
        return Err(UsRefused::NotAnObject);
    }
    // NOTE on the id character law: the oracle admits any Unicode lowercase
    // digit-letter mix (`c.islower() or c.isdigit()`); every lawful file on
    // the grounds is ASCII. Narrowed to ASCII here deliberately — a unicode
    // id refuses loudly rather than passing by accident.
    match block.get("us") {
        Some(Json::Int(1)) => {}
        _ => return Err(UsRefused::BadVersion),
    }
    let kind = match field(block, "kind") {
        Some(Json::Str(s)) if KINDS.contains(&s.as_str()) => s.clone(),
        _ => return Err(UsRefused::BadKind),
    };
    let ident = match field(block, "id") {
        Some(Json::Str(s)) if !s.is_empty() => s.clone(),
        _ => return Err(UsRefused::BadId),
    };
    if !ident
        .chars()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-' || c == '_')
    {
        return Err(UsRefused::BadId);
    }
    if let Some(stem) = stem {
        if kind == "module" && !ident.eq_ignore_ascii_case(stem) {
            return Err(UsRefused::StemMismatch);
        }
    }

    // THE STRUCTURAL GATE. Stated after identity, before module fields —
    // same order as the oracle, so refusal classes line up stroke by stroke.
    match field(block, "can_approve") {
        None => return Err(UsRefused::CanApproveAbsent),
        Some(Json::Bool(false)) => {}
        Some(_) => return Err(UsRefused::CanApproveNotFalse),
    }

    if kind == "module" {
        for f in ["office", "verbs", "ledger", "wall", "rows"] {
            if field(block, f).is_none() {
                return Err(UsRefused::ModuleMissingField(match f {
                    "office" => "office",
                    "verbs" => "verbs",
                    "ledger" => "ledger",
                    "wall" => "wall",
                    "rows" => "rows",
                    _ => unreachable!(),
                }));
            }
        }
        match field(block, "rows") {
            Some(Json::Arr(r)) if !r.is_empty() => {}
            _ => return Err(UsRefused::RowsEmpty),
        }
        match field(block, "verbs") {
            Some(Json::Arr(v)) if !v.is_empty() => {}
            _ => return Err(UsRefused::VerbsEmpty),
        }
    } else if kind == "agent" {
        match field(block, "mode") {
            Some(Json::Str(m)) if MODES.contains(&m.as_str()) => {}
            _ => return Err(UsRefused::BadMode),
        }
        match field(block, "permission") {
            Some(Json::Obj(p)) if !p.is_empty() => {}
            _ => return Err(UsRefused::AgentPermissionMissing),
        }
    }
    Ok(())
}

/// The module (or sole) declaration in a .us document.
pub fn declaration(doc: &UsDoc) -> Result<Json> {
    if !doc.errors.is_empty() {
        return Err(UsRefused::DocumentErrors(doc.errors.join("; ")));
    }
    let mods: Vec<&Json> = doc
        .blocks
        .iter()
        .filter(|b| matches!(b.get("kind"), Some(Json::Str(k)) if k == "module"))
        .collect();
    match mods.len() {
        0 => Err(UsRefused::NoModuleBlock),
        1 => {
            validate(mods[0], doc.stem.as_deref())?;
            Ok(mods[0].clone())
        }
        n => Err(UsRefused::MultipleModules(n)),
    }
}

/// Every agent, tool, and skill declared in the document (validated without
/// a stem, mirroring the oracle).
pub fn roster(doc: &UsDoc) -> Result<Vec<Json>> {
    let mut out = Vec::new();
    for b in &doc.blocks {
        if matches!(
            b.get("kind"),
            Some(Json::Str(k)) if k == "agent" || k == "tool" || k == "skill"
        ) {
            validate(b, None)?;
            out.push(b.clone());
        }
    }
    Ok(out)
}

// -- the fold down to a vendor's shape -----------------------------------------

/// Is a capability present at all? A glob map grants it if ANY path is not
/// denied — the scope is real but a flat list cannot carry it.
fn granted(rule: Option<&Json>) -> bool {
    match rule {
        None => false,
        Some(Json::Str(s)) => s != "deny",
        Some(Json::Obj(map)) => map
            .iter()
            .any(|(_, v)| !matches!(v, Json::Str(s) if s == "deny")),
        Some(_) => false,
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DeriveTools {
    pub tools: Vec<String>,
    pub lost: Vec<String>,
}

/// Fold canonical permission down to a flat vendor tool list, and say what
/// the flattening lost. The reverse fold is not offered: it cannot be done
/// without inventing scope that was never granted.
pub fn derive_tools(permission: &Json) -> DeriveTools {
    let get = |k: &str| permission.get(k);
    let mut tools: Vec<String> = Vec::new();
    if granted(get("read")) {
        tools.extend(["Read", "Grep", "Glob"].map(String::from));
    }
    if granted(get("edit")) {
        tools.extend(["Write", "Edit"].map(String::from));
    }
    if granted(get("bash")) {
        tools.push("Bash".into());
    }
    if granted(get("net")) {
        tools.extend(["WebFetch", "WebSearch"].map(String::from));
    }

    let mut caps: Vec<(String, &Json)> = match permission {
        Json::Obj(pairs) => pairs.iter().map(|(k, v)| (k.clone(), v)).collect(),
        _ => Vec::new(),
    };
    caps.sort_by(|a, b| a.0.cmp(&b.0));

    let mut lost = Vec::new();
    for (cap, rule) in caps {
        match rule {
            Json::Obj(map) => {
                if map.len() > 1 {
                    let mut paths: Vec<String> =
                        map.iter().map(|(k, _)| k.clone()).collect();
                    paths.sort();
                    lost.push(format!(
                        "{} was scoped by path ({}) and a flat list cannot say so",
                        cap,
                        paths.join(", ")
                    ));
                }
                if map.iter().any(|(_, v)| matches!(v, Json::Str(s) if s == "ask")) {
                    lost.push(format!(
                        "{} carried an 'ask' gate and a flat list cannot carry it",
                        cap
                    ));
                }
            }
            Json::Str(s) if s == "ask" => {
                lost.push(format!(
                    "{} was 'ask' and a flat list cannot carry the gate",
                    cap
                ));
            }
            _ => {}
        }
    }
    DeriveTools { tools, lost }
}

// -- rendering ------------------------------------------------------------------

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

/// json.dumps string form with ensure_ascii=False: only `"`, `\`, and C0
/// controls are escaped (short forms where they exist, else lowercase
/// \u00xx); DEL and every non-ASCII char stay literal.
fn py_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if short_escape(c).is_some() => {
                out.push('\\');
                out.push(short_escape(c).unwrap());
            }
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn push_indent(out: &mut String, level: usize) {
    for _ in 0..level * 2 {
        out.push(' ');
    }
}

/// json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).
pub fn py_dumps_indent(value: &Json) -> String {
    let mut out = String::new();
    py_write(value, 0, &mut out);
    out
}

fn py_write(v: &Json, level: usize, out: &mut String) {
    match v {
        Json::Null => out.push_str("null"),
        Json::Bool(true) => out.push_str("true"),
        Json::Bool(false) => out.push_str("false"),
        Json::Int(n) => out.push_str(&n.to_string()),
        Json::Big(d) => out.push_str(d), // unreachable via parse; digits verbatim
        Json::Float(x) => out.push_str(&python_repr(*x)),
        Json::Str(s) => py_string(s, out),
        Json::Arr(items) => {
            if items.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push_str("[\n");
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push_str(",\n");
                }
                push_indent(out, level + 1);
                py_write(item, level + 1, out);
            }
            out.push('\n');
            push_indent(out, level);
            out.push(']');
        }
        Json::Obj(pairs) => {
            if pairs.is_empty() {
                out.push_str("{}");
                return;
            }
            let mut sorted: Vec<(&str, &Json)> =
                pairs.iter().map(|(k, v)| (k.as_str(), v)).collect();
            sorted.sort_by(|a, b| a.0.cmp(b.0)); // code-point order
            out.push_str("{\n");
            for (i, (k, val)) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push_str(",\n");
                }
                push_indent(out, level + 1);
                py_string(k, out);
                out.push_str(": ");
                py_write(val, level + 1, out);
            }
            out.push('\n');
            push_indent(out, level);
            out.push('}');
        }
    }
}

/// A .us file: prose, then one fenced block per declaration. Deterministic,
/// so a folded .us re-renders byte-identical and the prover can compare.
pub fn render(prose: &str, blocks: &[Json]) -> String {
    let mut parts: Vec<String> = vec![prose.trim_end().to_string(), String::new()];
    for b in blocks {
        parts.push(format!("{}json", FENCE));
        parts.push(py_dumps_indent(b));
        parts.push(FENCE.to_string());
        parts.push(String::new());
    }
    let joined = parts.join("\n");
    format!("{}\n", joined.trim_end())
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_PROSE: &str = "# AGENTS - the estate's engineering record\n\nstate = fold(record). Nothing is deleted.";

    fn sample_module() -> Json {
        json::parse(
            r#"{"us": 1, "id": "agents", "kind": "module", "office": "NEIRO",
               "generation": 1, "reports_to": "neiro", "can_approve": false,
               "body_v": 3, "wall": ".", "ledger": "state/ledger/ledger.jsonl",
               "rows": ["soul", "body", "road"], "verbs": ["look", "muster"],
               "covenant": "65118a147dd49ed9"}"#,
        )
        .unwrap()
    }

    fn sample_agent() -> Json {
        json::parse(
            r#"{"us": 1, "id": "courier", "kind": "agent", "mode": "subagent",
               "office": "STEWARD", "reports_to": "archivist",
               "can_approve": false,
               "permission": {"read": {"*": "allow"},
                              "edit": {"*": "deny", "shelf/**": "allow"},
                              "bash": {"*": "ask"}, "net": "deny"}}"#,
        )
        .unwrap()
    }

    #[test]
    fn rendered_document_parses_back_clean_and_survives_round_trip() {
        let text = render(SAMPLE_PROSE, &[sample_module(), sample_agent()]);
        let doc = parse(&text);
        assert!(doc.errors.is_empty(), "{:?}", doc.errors);
        assert!(doc.prose.contains("state = fold(record)"));
        assert_eq!(doc.blocks.len(), 2);
        assert!(declaration(&doc).is_ok());
        assert_eq!(roster(&doc).unwrap().len(), 1);
        // Determinism: render(parse(render(x))) == render(x)
        let again = render(&doc.prose, &doc.blocks);
        assert_eq!(again, text);
    }

    #[test]
    fn can_approve_is_the_load_bearing_refusal() {
        let drop = |k: &str| match sample_module() {
            Json::Obj(mut p) => {
                p.retain(|(k2, _)| k2 != k);
                Json::Obj(p)
            }
            _ => unreachable!(),
        };
        assert_eq!(
            validate(&drop("can_approve"), Some("Agents")).unwrap_err().class(),
            "can_approve_absent"
        );
        let truthy = json::parse(
            r#"{"us":1,"id":"agents","kind":"module","office":"o","wall":"w","ledger":"l","rows":["r"],"verbs":["v"],"can_approve":true}"#,
        )
        .unwrap();
        assert_eq!(validate(&truthy, Some("Agents")).unwrap_err().class(), "can_approve_not_false");
        let stry = json::parse(
            r#"{"us":1,"id":"agents","kind":"module","office":"o","wall":"w","ledger":"l","rows":["r"],"verbs":["v"],"can_approve":"no"}"#,
        )
        .unwrap();
        assert_eq!(validate(&stry, Some("Agents")).unwrap_err().class(), "can_approve_not_false");
    }

    #[test]
    fn validation_refusals_match_the_oracle_classes() {
        let bad_ver = merge(&sample_module(), &[("us", Json::Int(2))]);
        assert_eq!(validate(&bad_ver, Some("Agents")).unwrap_err().class(), "bad_version");
        let bad_kind = merge(&sample_module(), &[("kind", Json::Str("daemon".into()))]);
        assert_eq!(validate(&bad_kind, Some("Agents")).unwrap_err().class(), "bad_kind");
        let no_id = merge(&sample_module(), &[("id", Json::Str(String::new()))]);
        assert_eq!(validate(&no_id, Some("Agents")).unwrap_err().class(), "bad_id");
        let shouty = merge(&sample_module(), &[("id", Json::Str("Agents".into()))]);
        assert_eq!(validate(&shouty, Some("Agents")).unwrap_err().class(), "bad_id");
        let empty_rows = merge(&sample_module(), &[("rows", Json::Arr(vec![]))]);
        assert_eq!(validate(&empty_rows, Some("Agents")).unwrap_err().class(), "rows_empty");
        let no_ledger = remove_key(&sample_module(), "ledger");
        assert_eq!(
            validate(&no_ledger, Some("Agents")).unwrap_err().class(),
            "module_missing_field"
        );
        let bad_mode = merge(&sample_agent(), &[("mode", Json::Str("primary-ish".into()))]);
        assert_eq!(validate(&bad_mode, None).unwrap_err().class(), "bad_mode");
        let no_perm = remove_key(&sample_agent(), "permission");
        assert_eq!(
            validate(&no_perm, None).unwrap_err().class(),
            "agent_permission_missing"
        );
        let wrong_stem = merge(&sample_module(), &[("id", Json::Str("steward".into()))]);
        assert_eq!(validate(&wrong_stem, Some("Agents")).unwrap_err().class(), "stem_mismatch");
        let no_mod_doc = parse("just prose");
        assert_eq!(
            declaration(&no_mod_doc).unwrap_err().class(),
            "no_module_block"
        );
    }

    fn merge(base: &Json, over: &[(&str, Json)]) -> Json {
        let mut obj = base.clone();
        for (k, v) in over {
            if let Json::Obj(pairs) = &mut obj {
                match pairs.iter_mut().find(|(k2, _)| k2 == k) {
                    Some(slot) => slot.1 = v.clone(),
                    None => pairs.push(((*k).into(), v.clone())),
                }
            }
        }
        obj
    }

    fn remove_key(base: &Json, key: &str) -> Json {
        match base {
            Json::Obj(pairs) => Json::Obj(
                pairs.iter().filter(|(k, _)| k != key).cloned().collect(),
            ),
            other => other.clone(),
        }
    }

    #[test]
    fn malformed_documents_are_named_not_swallowed() {
        let bad = parse("prose\n```json\n{not json}\n```");
        assert!(!bad.errors.is_empty());
        assert!(bad.errors[0].contains("line 2"), "{:?}", bad.errors[0]);
        assert!(bad.errors[0].contains("not JSON"));

        let unclosed = parse("prose\n```json\n{}\n");
        assert!(unclosed.errors.iter().any(|e| e.contains("never closed")));

        let stray = parse("```python\nprint(1)\n```");
        assert!(stray.prose.contains("print(1)"));
        assert!(stray.errors.is_empty());

        let two_mods = render(SAMPLE_PROSE, &[sample_module(), sample_module()]);
        let doc = parse(&two_mods);
        assert!(matches!(
            declaration(&doc).unwrap_err(),
            UsRefused::MultipleModules(2)
        ));
    }

    #[test]
    fn derive_tools_folds_and_reports_losses_like_the_oracle() {
        let perm = sample_agent().get("permission").unwrap().clone();
        let d = derive_tools(&perm);
        assert_eq!(
            d.tools,
            vec!["Read", "Grep", "Glob", "Write", "Edit", "Bash"]
        );
        assert!(d.lost.iter().any(|m| m.contains("scoped by path")));
        assert!(d.lost.iter().any(|m| m.contains("'ask'")));

        let deny_all = json::parse(r#"{"read": "deny", "edit": "deny"}"#).unwrap();
        assert!(derive_tools(&deny_all).tools.is_empty());

        let ask_flat = json::parse(r#"{"read": "ask"}"#).unwrap();
        let d = derive_tools(&ask_flat);
        // Oracle law: 'ask' still GRANTS the capability (present != free);
        // the fold carries the tool and reports the gate it cannot carry.
        assert_eq!(d.tools, vec!["Read", "Grep", "Glob"]);
        assert!(d.lost[0].contains("was 'ask'"));
    }
}
