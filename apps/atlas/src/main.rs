mod prove;

use std::process::ExitCode;

use atlas_core::chain::{read_rows, verify_rows};
use atlas_core::forms::recognize_rows;
use atlas_store::driver::Conn;
use atlas_store::import_export::{export_chain, export_matches, import_chain};
use atlas_store::migrations::{apply_migrations, ledger_migrations};

const VERSION_FILE: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../VERSION"));

/// The SPEC_CHAINS known-live-chains table (slug -> path relative to a
/// root ground), mirroring tools/cut_fixtures.py. Deferred stones (gateway
/// sqlite shards, remote manjuel.us) are absent on purpose.
const ROOTS: [(&str, &str); 21] = [
    ("steward_ledger", r"Steward 1.0\state\ledger\ledger.jsonl"),
    ("steward_chain", r"Steward 1.0\state\chain\chain.jsonl"),
    ("agents_seatlog", r"Agents\Seat_log\ledger.jsonl"),
    ("neiro_archive_ledger", r"Neiro\Archive\ledger\ledger.jsonl"),
    ("steward_board", r"Steward\Archive\state\board.jsonl"),
    ("steward_archive_ledger", r"Steward\Archive\state\ledger.jsonl"),
    ("commons_board", r"Neiro\Archive\shelf\commons\board.jsonl"),
    ("commons_snapshots", r"Neiro\Archive\shelf\commons\snapshots.jsonl"),
    ("custody", r"Neiro\Archive\shelf\custody\custody.jsonl"),
    ("kimi_harvest_ledger", r"Neiro\Archive\shelf\kimi_harvest\ledger.jsonl"),
    ("ops_gate", r"Neiro\Archive\shelf\ops\gate.jsonl"),
    ("trade_properties", r"Steward 1.0\state\ops\properties.jsonl"),
    ("trade_inspections", r"Steward 1.0\state\ops\inspections.jsonl"),
    ("trade_workorders_audit", r"Steward 1.0\state\ops\workorders_audit.jsonl"),
    ("jesster_gen1_chain", r"Jesster\shelf\library\gen1\chain\chain.jsonl"),
    ("jesster_gen2_chain", r"Jesster\shelf\library\gen2\chain\chain.jsonl"),
    ("jesster_gen3_chain", r"Jesster\shelf\library\gen3\chain\chain.jsonl"),
    ("jesster_gen4_chain", r"Jesster\shelf\library\gen4\chain\chain.jsonl"),
    ("jesster_archive_chain", r"Jesster\Archive\chain.jsonl"),
    ("forge_links_chain", r"forge\links\chain.jsonl"),
    ("skills_board_ledger", r"Agent Skills\board\ledger.jsonl"),
];

fn usage() {
    println!("usage: atlas [--version] [--describe] [--prove] <command> [args]");
    println!("landed commands:");
    println!("  chain verify    (<path> | --roots <dir>)   verdicts EMPTY|INTACT|FLIP|TAMPER");
    println!("  chain recognize (<path> | --roots <dir>)   form recognition-by-trial");
    println!("  db init         <db>                       create + migrate + connection law");
    println!("  db import       <db> <slug> <chain.jsonl>  verify-first mirror");
    println!("  db export       <db> <slug> [--check file] byte-identical JSONL out");
    println!("  db status       <db>                       pragmas, migrations, pointers");
    println!("  agent enroll    <db> --dir <agents> [--dry]");
    println!("  orient          --home <dir>               line + road + log-tail");
    println!("  trade <skill> <arg> --ops <dir>            property|workorder|inspect|report grammars");
    println!("  link lay --chain <f> --says <s> --actor <a> --doc <json>|--doc-file <f> [--mode open|sealed] [--cites h,h] [--sig H --pub H]");
    println!("  link status --chain <f>                    entries/links/wraps/head/verdict");
    println!("commands land stone by stone: covenant check · link · ark · deposit ·");
    println!("matrix (SPEC_COMMANDS)");
}

fn load_text(path: &std::path::Path) -> Result<String, String> {
    let bytes = std::fs::read(path)
        .map_err(|e| format!("cannot read {}: {}", path.display(), e))?;
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}

fn one_path_report(
    path: &std::path::Path,
    label: &str,
    mode: &str,
) -> Result<(bool, String), String> {
    let text = load_text(path)?;
    let rows = read_rows(&text);
    let rec = recognize_rows(&rows);
    let ver = verify_rows(&rows);

    let line = match mode {
        "recognize" => format!(
            "{label}: form={} matched={}/{} hex={} weld={}",
            rec.form.as_deref().unwrap_or("-"),
            rec.matched,
            rec.entries,
            rec.hex_width,
            match rec.weld_ok {
                true => "intact".to_string(),
                false => format!("BROKEN@{}", rec.weld_broke.unwrap_or(0)),
            }
        ),
        _ => format!(
            "{label}: verdict={} entries={} flips={:?} broke_at={:?} appendable={}",
            ver.verdict.as_str(),
            ver.entries,
            ver.flips,
            ver.broke_at,
            ver.appendable
        ),
    };

    // Soundness for exit codes: recognition mode passes when every entry
    // was read by one form and the weld holds; verify mode passes while the
    // chain stays appendable (EMPTY/INTACT/FLIP; TAMPER refuses).
    let ok = match mode {
        "recognize" => rec.whole && rec.weld_ok,
        _ => ver.appendable,
    };
    Ok((ok, line))
}

fn roots_walk(mode: &str, root: &str) -> ExitCode {
    let base = std::path::PathBuf::from(root);
    let mut all_ok = true;
    let mut present = 0usize;
    for (slug, rel) in ROOTS {
        let path = base.join(rel);
        if !path.is_file() {
            println!("{slug}: ABSENT ({})", path.display());
            continue;
        }
        present += 1;
        match one_path_report(&path, slug, mode) {
            Ok((ok, line)) => {
                if !ok {
                    all_ok = false;
                }
                println!("{line}");
            }
            Err(e) => {
                all_ok = false;
                println!("{slug}: REFUSED {e}");
            }
        }
    }
    println!(
        "-- {} of {} named chains walked under {}; result: {}",
        present,
        ROOTS.len(),
        root,
        if all_ok { "SOUND" } else { "UNSOUND" }
    );
    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

fn chain_command(args: &[String]) -> ExitCode {
    let mode;
    let mut rest: &[String] = args;
    match rest.first().map(String::as_str) {
        Some("verify") => {
            mode = "verify";
            rest = &rest[1..];
        }
        Some("recognize") => {
            mode = "recognize";
            rest = &rest[1..];
        }
        _ => {
            eprintln!("refused: chain needs 'verify' or 'recognize'");
            return ExitCode::from(2);
        }
    }
    if rest.first().map(String::as_str) == Some("--roots") {
        match rest.get(1) {
            Some(dir) => return roots_walk(mode, dir),
            None => {
                eprintln!("refused: --roots needs a directory");
                return ExitCode::from(2);
            }
        }
    }
    match rest.first() {
        Some(path) => match one_path_report(
            std::path::Path::new(path),
            path,
            mode,
        ) {
            Ok((ok, line)) => {
                println!("{line}");
                if ok {
                    ExitCode::SUCCESS
                } else {
                    ExitCode::from(1)
                }
            }
            Err(e) => {
                eprintln!("refused: {e}");
                ExitCode::from(2)
            }
        },
        None => {
            eprintln!("refused: chain {} needs a path or --roots <dir>", mode);
            ExitCode::from(2)
        }
    }
}

use std::path::{Path, PathBuf};

/// A2-04 — the orientation pack: standing law + line + road + log-tail,
/// assembled from a home directory under SPEC_MCP's 60k cap. The full MCP
/// server is B1; this is the assembly it will serve.
const ORIENT_CAP: usize = 60_000;

fn read_capped(path: &Path, max_chars: usize) -> Result<String, String> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| format!("cannot read {}: {}", path.display(), e))?;
    Ok(text.chars().take(max_chars).collect())
}

fn tail_lines(text: &str, n: usize) -> String {
    let lines: Vec<&str> = text.lines().collect();
    let start = lines.len().saturating_sub(n);
    lines[start..].join("\n")
}

fn orient_home(home: &Path) -> Result<String, String> {
    if !home.is_dir() {
        return Err(format!("home {} is not a directory", home.display()));
    }
    let mut out = String::from(
        "== ATLAS ORIENTATION ==\n\
         state = fold(record): nothing is deleted; append and supersede.\n\
         Propose, never dispose: can_approve is false in every declaration,\n\
         and approval lives in the operator's hand alone.\n\
         Prove hermetic on temp ground; leave your toll in SEAT_LOG.md.\n\n",
    );

    // THE LINE: who sits here (AGENTS.md preferred, else any .us stem list).
    let agents_md = home.join("AGENTS.md");
    if agents_md.is_file() {
        out.push_str("-- LINE --\n");
        out.push_str(&read_capped(&agents_md, 4_000)?);
        out.push_str("\n\n");
    } else {
        let us_files: Vec<PathBuf> = std::fs::read_dir(home)
            .map_err(|e| format!("home unreadable: {}", e))?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("us"))
            .collect();
        if us_files.is_empty() {
            return Err("orientation refused: no AGENTS.md and no .us in home".into());
        }
        out.push_str("-- LINE --\n");
        for f in us_files {
            out.push_str(&format!(
                "declared: {}\n",
                f.file_stem().unwrap_or_default().to_string_lossy()
            ));
        }
        out.push('\n');
    }

    // THE ROAD: what is next.
    let road = ["THE_ROAD.md", "STATE_OF_BUILD.md"]
        .iter()
        .map(|f| home.join(f))
        .find(|p| p.is_file());
    match road {
        Some(p) => {
            out.push_str("-- ROAD --\n");
            out.push_str(&read_capped(&p, 4_000)?);
            out.push_str("\n\n");
        }
        None => return Err("orientation refused: no THE_ROAD.md / STATE_OF_BUILD.md".into()),
    }

    // THE LOG TAIL: what the last seats landed.
    let log = home.join("SEAT_LOG.md");
    if !log.is_file() {
        return Err("orientation refused: no SEAT_LOG.md in home".into());
    }
    let log_text = std::fs::read_to_string(&log)
        .map_err(|e| format!("cannot read {}: {}", log.display(), e))?;
    out.push_str("-- LOG TAIL --\n");
    out.push_str(&tail_lines(&log_text, 40));
    out.push('\n');

    if out.chars().count() > ORIENT_CAP {
        out = out.chars().take(ORIENT_CAP).collect();
        out.push_str("\n\n[truncated at the 60000-character law]\n");
    }
    Ok(out)
}

fn db_command(args: &[String]) -> ExitCode {
    let sub = match args.first().map(String::as_str) {
        Some(s @ ("init" | "import" | "export" | "status")) => s,
        _ => {
            eprintln!("refused: db needs 'init', 'import', 'export' or 'status'");
            return ExitCode::from(2);
        }
    };
    let rest = &args[1..];
    match sub {
        "init" => match rest.first() {
            Some(db) => {
                let conn = match Conn::open(std::path::Path::new(db)) {
                    Ok(c) => c,
                    Err(e) => return db_fail(e),
                };
                match conn.apply_connection_law().and_then(|law| {
                    apply_migrations(&conn, &ledger_migrations()).map(|m| (law, m))
                }) {
                    Ok((law, applied)) => {
                        println!(
                            "{db}: journal_mode={} synchronous={} foreign_keys={} busy_timeout={}",
                            law.journal_mode, law.synchronous, law.foreign_keys, law.busy_timeout_ms
                        );
                        for (v, name) in applied {
                            println!("{db}: migration {v} {name} applied");
                        }
                        ExitCode::SUCCESS
                    }
                    Err(e) => db_fail(e),
                }
            }
            None => {
                eprintln!("refused: db init needs a path");
                ExitCode::from(2)
            }
        },
        "import" => match (rest.get(0), rest.get(1), rest.get(2)) {
            (Some(db), Some(slug), Some(jsonl)) => {
                match import_chain(std::path::Path::new(db), slug, std::path::Path::new(jsonl)) {
                    Ok(rep) => {
                        println!(
                            "{db}: imported {slug} — {} lines ({}/{} newly mirrored), wraps walked: {}, head {}",
                            rep.lines,
                            rep.inserted_now,
                            rep.lines,
                            rep.wraps_walked,
                            rep.head.as_deref().unwrap_or("-")
                        );
                        ExitCode::SUCCESS
                    }
                    Err(e) => {
                        eprintln!("refused: {}", e);
                        ExitCode::from(1)
                    }
                }
            }
            _ => {
                eprintln!("refused: db import needs <db> <slug> <chain.jsonl>");
                ExitCode::from(2)
            }
        },
        "export" => {
            let db = match rest.first() {
                Some(d) => d.clone(),
                None => {
                    eprintln!("refused: db export needs <db> <slug>");
                    return ExitCode::from(2);
                }
            };
            let slug = match rest.get(1) {
                Some(s) => s.clone(),
                None => {
                    eprintln!("refused: db export needs a slug");
                    return ExitCode::from(2);
                }
            };
            if rest.get(2).map(String::as_str) == Some("--check") {
                match rest.get(3) {
                    Some(file) => {
                        match export_matches(std::path::Path::new(&db), &slug, std::path::Path::new(file))
                        {
                            Ok(true) => {
                                println!("{db}: export {slug} byte-identical to {file}");
                                ExitCode::SUCCESS
                            }
                            Ok(false) => {
                                println!("{db}: export {slug} DIVERGES from {file}");
                                ExitCode::from(1)
                            }
                            Err(e) => db_fail(e),
                        }
                    }
                    None => {
                        eprintln!("refused: --check needs a reference file");
                        ExitCode::from(2)
                    }
                }
            } else {
                use std::io::Write;
                match export_chain(std::path::Path::new(&db), &slug) {
                    Ok(bytes) => {
                        std::io::stdout().write_all(&bytes).ok();
                        ExitCode::SUCCESS
                    }
                    Err(e) => db_fail(e),
                }
            }
        }
        "status" => match rest.first() {
            Some(db) => match Conn::open_readonly(std::path::Path::new(db)) {
                Ok(conn) => {
                    let jm = text_q(&conn, "PRAGMA journal_mode;");
                    let sync = text_q(&conn, "PRAGMA synchronous;");
                    println!("{db}: journal_mode={jm} synchronous={sync}");
                    let n = int_q(
                        &conn,
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='schema_migrations';",
                    );
                    if n > 0 {
                        list_rows(
                            &conn,
                            "SELECT CAST(version AS TEXT), name, '' FROM schema_migrations ORDER BY version;",
                            |r| format!("migration {} {}", r.0, r.1),
                        );
                    }
                    list_rows(&conn, "SELECT slug, CAST(entries AS TEXT), head FROM chains ORDER BY slug;", |r| {
                        format!("chain {} entries={} head={}", r.0, r.1, r.2)
                    });
                    list_rows(
                        &conn,
                        "SELECT chain_path, CAST(last_applied_n AS TEXT), applied_hash FROM journal_sync ORDER BY chain_path;",
                        |r| format!("pointer {} at n={} hash={}", r.0, r.1, r.2),
                    );
                    ExitCode::SUCCESS
                }
                Err(e) => db_fail(e),
            },
            None => {
                eprintln!("refused: db status needs a path");
                ExitCode::from(2)
            }
        },
        _ => unreachable!("sub validated above"),
    }
}

fn agent_command(args: &[String]) -> ExitCode {
    // atlas agent enroll <db> (--dir <agents-dir> | --file <x.us>) [--dry]
    if args.first().map(String::as_str) != Some("enroll") {
        eprintln!("refused: agent needs 'enroll' (landed verbs grow stone by stone)");
        return ExitCode::from(2);
    }
    let mut db: Option<String> = None;
    let mut target: Option<PathBuf> = None;
    let mut dry = false;
    let mut it = args[1..].iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--dry" => dry = true,
            "--dir" => target = it.next().map(PathBuf::from),
            "--file" => target = it.next().map(PathBuf::from),
            other if db.is_none() && !other.starts_with('-') => db = Some(other.to_string()),
            other => {
                eprintln!("refused: unexpected argument {other:?}");
                return ExitCode::from(2);
            }
        }
    }
    let (db, target) = match (db, target) {
        (Some(d), Some(t)) => (d, t),
        _ => {
            eprintln!("usage: atlas agent enroll <db> --dir <agents-dir> [--dry]");
            return ExitCode::from(2);
        }
    };
    match atlas_store::enroll::enroll_dir(Path::new(&db), &target, dry) {
        Ok(rep) => {
            println!(
                "{}: {} files read ({} modules); enrolled {} agents{} ({} already present){}",
                db,
                rep.files_read,
                rep.modules,
                rep.enrolled.len(),
                if dry { " [DRY RUN - rolled back]" } else { "" },
                rep.skipped_existing,
                if rep.refused.is_empty() {
                    String::new()
                } else {
                    format!("\nrefused:\n  {}", rep.refused.join("\n  "))
                }
            );
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("refused: {}", e);
            ExitCode::from(1)
        }
    }
}

fn db_fail(e: atlas_store::driver::StoreError) -> ExitCode {
    eprintln!("refused: {}", e);
    ExitCode::from(1)
}

/// atlas trade <skill> <arg...> --ops <dir>: the trade grammars
/// (property|workorder|inspect|report) against an ops ground. The arg words
/// rejoin with spaces, so pipes survive one shell quoting.
fn trade_command(args: &[String]) -> ExitCode {    let mut skill: Option<String> = None;
    let mut ops = std::path::PathBuf::from("state/ops");
    let mut words: Vec<String> = Vec::new();
    let mut it = args.iter().peekable();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--ops" => match it.next() {
                Some(d) => ops = std::path::PathBuf::from(d),
                None => {
                    eprintln!("refused: --ops needs a directory");
                    return ExitCode::from(2);
                }
            },
            other if skill.is_none() && !other.starts_with('-') => {
                skill = Some(other.to_string())
            }
            other => words.push(other.to_string()),
        }
    }
    let Some(skill) = skill else {
        eprintln!("usage: atlas trade <property|workorder|inspect|report> <arg> --ops <dir>");
        return ExitCode::from(2);
    };
    match atlas_store::trade::run(&skill, &words.join(" "), &ops) {
        Ok(out) => {
            println!("{out}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("refused: {e}");
            ExitCode::from(1)
        }
    }
}

/// atlas link lay|status: the Rust pen (SPEC_COMMANDS). lay appends one
/// links-chain entry (closing a wrap every 40th link); status rewalks.
fn link_command(args: &[String]) -> ExitCode {
    let mut verb: Option<String> = None;
    let mut chain = std::path::PathBuf::new();
    let mut says = String::new();
    let mut actor = String::new();
    let mut doc = String::new();
    let mut doc_file: Option<String> = None;
    let mut mode = "open".to_string();
    let mut cites: Vec<String> = Vec::new();
    let mut sig = String::new();
    let mut pub_ = String::new();
    let mut it = args.iter().peekable();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--chain" | "--doc" | "--doc-file" | "--says" | "--actor" | "--mode" | "--cites"
            | "--sig" | "--pub" => {
                let v = it.next().cloned().unwrap_or_default();
                match a.as_str() {
                    "--chain" => chain = std::path::PathBuf::from(v),
                    "--doc" => doc = v,
                    "--doc-file" => doc_file = Some(v),
                    "--says" => says = v,
                    "--actor" => actor = v,
                    "--mode" => mode = v,
                    "--cites" => {
                        cites = v.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect()
                    }
                    "--sig" => sig = v,
                    "--pub" => pub_ = v,
                    _ => {}
                }
            }
            other if verb.is_none() && !other.starts_with('-') => {
                verb = Some(other.to_string())
            }
            other => {
                eprintln!("refused: unexpected argument {other:?}");
                return ExitCode::from(2);
            }
        }
    }
    match verb.as_deref() {
        Some("status") => {
            if chain.as_os_str().is_empty() {
                eprintln!("usage: atlas link status --chain <file>");
                return ExitCode::from(2);
            }
            match atlas_store::link::status(&chain) {
                Ok(st) => {
                    println!(
                        "{}: entries={} links={} wraps={} head={} verdict={} {}",
                        chain.display(),
                        st.entries,
                        st.links,
                        st.wraps,
                        st.head,
                        st.verdict,
                        st.detail
                    );
                    if st.verdict == "INTACT" || st.verdict == "EMPTY" {
                        ExitCode::SUCCESS
                    } else {
                        ExitCode::from(1)
                    }
                }
                Err(e) => {
                    eprintln!("refused: {e}");
                    ExitCode::from(1)
                }
            }
        }
        Some("lay") => {
            if chain.as_os_str().is_empty() || says.is_empty() || actor.is_empty() {
                eprintln!("usage: atlas link lay --chain <f> --says <s> --actor <a> --doc <json>|--doc-file <f> [--mode open|sealed] [--cites h,h] [--sig H --pub H]");
                return ExitCode::from(2);
            }
            if let Some(f) = doc_file {
                match std::fs::read_to_string(&f) {
                    Ok(t) => doc = t,
                    Err(e) => {
                        eprintln!("refused: --doc-file unreadable: {e}");
                        return ExitCode::from(1);
                    }
                }
            }
            if doc.is_empty() {
                eprintln!("usage: atlas link lay needs --doc <json> or --doc-file <f>");
                return ExitCode::from(2);
            }
            let lay_args = atlas_store::link::LayArgs {
                chain,
                kind: "link".into(),
                says,
                actor,
                doc,
                mode,
                cites,
                sig,
                pub_,
            };
            match atlas_store::link::lay(&lay_args) {
                Ok(hash) => {
                    println!("{hash}");
                    ExitCode::SUCCESS
                }
                Err(e) => {
                    eprintln!("refused: {e}");
                    ExitCode::from(1)
                }
            }
        }
        _ => {
            eprintln!("usage: atlas link <lay|status> --chain <file> ...");
            ExitCode::from(2)
        }
    }
}

fn text_q(conn: &Conn, sql: &str) -> String {
    conn.prepare(sql)
        .and_then(|s| s.step().map(|_| s.text(0).unwrap_or_default()))
        .unwrap_or_else(|_| "-".into())
}

fn int_q(conn: &Conn, sql: &str) -> i64 {
    conn.prepare(sql)
        .and_then(|s| s.step().map(|_| s.int64(0)))
        .unwrap_or(0)
}

fn list_rows<F>(conn: &Conn, sql: &str, fmt: F)
where
    F: Fn((String, String, String)) -> String,
{
    if let Ok(stmt) = conn.prepare(sql) {
        loop {
            match stmt.step() {
                Ok(atlas_store::driver::Step::Row) => {
                    let a = stmt.text(0).unwrap_or_default();
                    let b = stmt.text(1).unwrap_or_default();
                    let c = stmt.text(2).unwrap_or_default();
                    println!("{}", fmt((a, b, c)));
                }
                _ => break,
            }
        }
    }
}

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some("--version") => {
            println!("{}", VERSION_FILE.trim());
            ExitCode::SUCCESS
        }
        Some("--help") | Some("-h") => {
            usage();
            ExitCode::SUCCESS
        }
        Some("--prove") => {
            let code = prove::run_prove();
            ExitCode::from(code as u8)
        }
        Some("--describe") => {
            println!(
                "atlas {} - polyglot reconciliation spine; all provenance math lives here",
                VERSION_FILE.trim()
            );
            ExitCode::SUCCESS
        }
        Some("chain") => chain_command(&args.collect::<Vec<String>>()),
        Some("db") => db_command(&args.collect::<Vec<String>>()),
        Some("orient") => {
            let rest: Vec<String> = args.collect();
            match (rest.first().map(String::as_str), rest.get(1)) {
                (Some("--home"), Some(dir)) => match orient_home(Path::new(dir)) {
                    Ok(pack) => {
                        print!("{pack}");
                        ExitCode::SUCCESS
                    }
                    Err(e) => {
                        eprintln!("refused: {e}");
                        ExitCode::from(1)
                    }
                },
                _ => {
                    eprintln!("refused: orient needs --home <dir>");
                    ExitCode::from(2)
                }
            }
        }
        Some("agent") => agent_command(&args.collect::<Vec<String>>()),
        Some("trade") => trade_command(&args.collect::<Vec<String>>()),
        Some("link") => link_command(&args.collect::<Vec<String>>()),
        Some(other) => {
            eprintln!("refused: '{other}' is not a landed command");
            usage();
            ExitCode::from(2)
        }
        None => {
            usage();
            ExitCode::from(2)
        }
    }
}
