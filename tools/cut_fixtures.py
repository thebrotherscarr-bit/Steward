#!/usr/bin/env python3
"""cut_fixtures.py -- cut A1 golden-master fixtures from the live chains.

A1-05 ordering: vectors are cut from the live chains BEFORE any Rust
canon/forms assertions exist, or the golden masters will lie. Read-only
over the source grounds; outputs land as byte-faithful copies/windows
under atlas\\tests\\fixtures\\ plus MANIFEST.json carrying sha256 per
source, structural stats, form hints, wrap positions, and construction-A
covenant reproductions for both epochs. Idempotent on content: same
sources -> same fixture bytes. Stdlib only; runs in atlas\\.venv.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
ARCHIVE = ATLAS.parent
ESTATE = ARCHIVE / "estate"
SECONDBRAIN = ARCHIVE / "secondbrain"
OUT = ATLAS / "tests" / "fixtures"

FULL_COPY_MAX_BYTES = 262144   # larger chains get head windows instead
HEAD_WINDOW_ENTRIES = 46       # >= one wrap boundary at 40 where present

HOUSE_ROOT = (SECONDBRAIN / "SecondBrain-collab" / "demo_vault" / "Manjuel"
              / "core" / "Archive")
ELDER_ROOT = ESTATE / "Steward 1.0" / "Archive"

HOUSE_DOCS = ["01_MYTHOS.md", "02_CONSTITUTION.md", "03_CREED.md",
               "04_NEURO_CORE.md", "05_THE_LAW.md"]
ELDER_DOCS = ["01_MYTHOS.md", "02_CONSTITUTION.md", "03_CREED.md",
              "04_NEURO_CORE.md"]
EXPECTED_COVENANT = {
    "house": "1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb",
    "elder": "65118a147dd49ed96068e8a3cf1a472db1f4d91253b23507c56926ba2d8d9dd9",
}

# slug -> path relative to the estate root (SPEC_CHAINS "Known live chains")
CHAINS = {
    "steward_ledger":         r"Steward 1.0\state\ledger\ledger.jsonl",
    "steward_chain":          r"Steward 1.0\state\chain\chain.jsonl",
    "agents_seatlog":         r"Agents\Seat_log\ledger.jsonl",
    "neiro_archive_ledger":   r"Neiro\Archive\ledger\ledger.jsonl",
    "steward_board":          r"Steward\Archive\state\board.jsonl",
    "steward_archive_ledger": r"Steward\Archive\state\ledger.jsonl",
    "commons_board":          r"Neiro\Archive\shelf\commons\board.jsonl",
    "commons_snapshots":      r"Neiro\Archive\shelf\commons\snapshots.jsonl",
    "custody":                r"Neiro\Archive\shelf\custody\custody.jsonl",
    "kimi_harvest_ledger":    r"Neiro\Archive\shelf\kimi_harvest\ledger.jsonl",
    "ops_gate":               r"Neiro\Archive\shelf\ops\gate.jsonl",
    "trade_properties":       r"Steward 1.0\state\ops\properties.jsonl",
    "trade_inspections":      r"Steward 1.0\state\ops\inspections.jsonl",
    "trade_workorders_audit": r"Steward 1.0\state\ops\workorders_audit.jsonl",
    "jesster_gen1_chain":     r"Jesster\shelf\library\gen1\chain\chain.jsonl",
    "jesster_gen2_chain":     r"Jesster\shelf\library\gen2\chain\chain.jsonl",
    "jesster_gen3_chain":     r"Jesster\shelf\library\gen3\chain\chain.jsonl",
    "jesster_gen4_chain":     r"Jesster\shelf\library\gen4\chain\chain.jsonl",
    "jesster_archive_chain":  r"Jesster\Archive\chain.jsonl",
    "forge_links_chain":      r"forge\links\chain.jsonl",
    "skills_board_ledger":    r"Agent Skills\board\ledger.jsonl",
}

DEFERRED = [
    "gateway blake2b-32 event store: sharded users\\<id>\\ledger.sqlite "
    "(SQLite, not JSONL; R12/S7 import stones)",
    "public manjuel.us ledger (remote; no seat egress)",
    "attic/folded duplicate mirrors and reading catalogs (corpus, not chains)",
]


def form_hint(entries):
    """Coarse family guess for the manifest; recognition-by-trial stays the
    prover's job (SPEC_CHAINS). Honest label, never trusted by tests."""
    if not entries:
        return "empty"
    bv = Counter(e.get("body_v") for e in entries if "body_v" in e)
    if bv:
        v = bv.most_common(1)[0][0]
        return {1: "board-v1", 2: "links-v2", 3: "jcs-v3"}.get(v, f"body_v{v}")
    env = sum(1 for e in entries if {"prev", "hash", "body"} <= set(e))
    if env * 2 >= len(entries):
        return "envelope"
    hw = Counter(len(e.get("hash", "")) for e in entries if "hash" in e)
    if hw:
        w = hw.most_common(1)[0][0]
        return "bare16" if w == 16 else f"hashwidth{w}"
    return "unknown"


def cut_identity(manifest_out):
    """Copy foundation docs + anchors; reproduce construction-A covenants."""
    ident = {}
    ident_dir = OUT / "identity"
    for epoch, root, docs in (("house", HOUSE_ROOT, HOUSE_DOCS),
                              ("elder", ELDER_ROOT, ELDER_DOCS)):
        found_root = root if (root / "foundation").is_dir() else None
        # the House heart may carry his foundation directly under core\Archive
        candidates = [root / "foundation", root]
        base = next((c for c in candidates if (c / docs[0]).is_file()), None)
        digests, doc_shas, missing, fixes = [], {}, [], []
        for name in docs:
            if base is None:
                missing.append(name)
                continue
            p = base / name
            if not p.is_file():
                missing.append(name)
                continue
            b = p.read_bytes()
            d = hashlib.sha256(b).hexdigest()
            digests.append(d)
            doc_shas[name] = d
            dest = ident_dir / epoch / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
            fixes.append(f"identity/{epoch}/{name}")
        reproduced = None
        if len(digests) == len(docs):
            reproduced = hashlib.sha256(
                "".join(digests).encode("utf-8")).hexdigest()
        ok = reproduced == EXPECTED_COVENANT[epoch]
        ident[epoch] = {
            "declared_order": docs,
            "foundation_dir": str(base) if base else None,
            "missing_docs": missing,
            "doc_sha256": doc_shas,
            "expected_covenant": EXPECTED_COVENANT[epoch],
            "reproduced_covenant": reproduced,
            "match": ok,
            "fixtures": fixes,
        }
        print(f"[{'PASS' if ok else 'FAIL'}] {epoch} construction-A "
              f"reproduction: {reproduced}")
    # anchors beside their epochs
    anchors = {}
    for tag, src in (("house/covenant.json", HOUSE_ROOT / "weights" / "covenant.json"),
                     ("elder/amendments.jsonl",
                      ESTATE / "Manjuel" / "5.0" / "soul" / "amendments.jsonl")):
        if not src.is_file():
            anchors[tag] = {"exists": False}
            continue
        b = src.read_bytes()
        dest = ident_dir / tag
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b)
        parsed = None
        try:
            parsed = json.loads(b.decode("utf-8"))
        except Exception:
            pass
        anchors[tag] = {
            "source": str(src), "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest(),
            "parsed_keys": sorted(parsed) if isinstance(parsed, dict) else None,
        }
    ident["anchors"] = anchors
    return ident


def cut_chain(slug, rel):
    src = ESTATE / rel
    row = {"slug": slug, "source": "estate\\" + rel}
    if not src.is_file():
        row["exists"] = False
        print(f"[MISS] {slug}: {rel}")
        return row
    raw = src.read_bytes()
    lines = raw.splitlines(keepends=True)
    parsed = []           # (line_index, obj)
    body_v = Counter()
    wraps = []
    blanks = unparsed = 0
    first_prev = last_hash = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            blanks += 1
            continue
        try:
            obj = json.loads(s.decode("utf-8"))
        except Exception:
            unparsed += 1
            continue
        if not isinstance(obj, dict):
            unparsed += 1
            continue
        parsed.append((i, obj))
        v = obj.get("body_v")
        if v in (1, 2, 3):
            body_v[str(v)] += 1
        if obj.get("kind") == "wrap":
            wraps.append(i)
        if first_prev is None and "prev" in obj:
            first_prev = obj["prev"]
        if "hash" in obj:
            last_hash = obj["hash"]

    fixtures = []
    chains_dir = OUT / "chains"
    chains_dir.mkdir(parents=True, exist_ok=True)
    if len(raw) <= FULL_COPY_MAX_BYTES:
        name = f"{slug}.jsonl"
        (chains_dir / name).write_bytes(raw)
        mode = "full"
    else:
        name = f"{slug}.head{HEAD_WINDOW_ENTRIES}.jsonl"
        (chains_dir / name).write_bytes(b"".join(lines[:HEAD_WINDOW_ENTRIES]))
        mode = f"window:{HEAD_WINDOW_ENTRIES}"
    fixtures.append(f"chains/{name}")

    samples_dir = OUT / "samples" / slug
    if parsed:
        picks = {}
        idxs = [i for i, _ in parsed]
        picks[idxs[0]] = "first"
        picks[idxs[-1]] = "last"
        picks[idxs[len(parsed) // 2]] = "mid"
        for i in wraps[:5]:
            picks.setdefault(i, "wrap")
        samples_dir.mkdir(parents=True, exist_ok=True)
        for i, tag in sorted(picks.items()):
            fn = f"{i:06d}-{tag}.json"
            (samples_dir / fn).write_bytes(lines[i])
            fixtures.append(f"samples/{slug}/{fn}")

    row.update({
        "exists": True,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "lines_total": len(lines),
        "blank_lines": blanks,
        "unparsed_lines": unparsed,
        "entries": len(parsed),
        "body_v_counts": dict(sorted(body_v.items())),
        "wrap_positions_lineidx": wraps,
        "first_prev": first_prev,
        "last_hash": last_hash,
        "form_hint": form_hint([o for _, o in parsed]),
        "fixture_mode": mode,
        "fixtures": fixtures,
    })
    print(f"[ OK ] {slug}: {len(raw)} B, {len(parsed)} entries, "
          f"hint={row['form_hint']}, {mode}")
    return row


def main():
    print(f"fixture root: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    version = (ATLAS / "VERSION").read_text(encoding="utf-8").strip()
    manifest = {
        "tool": "tools/cut_fixtures.py",
        "atlas_version": version,
        "cut_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ordering_note": "A1-05: fixtures cut BEFORE any Rust canon/forms "
                         "assertions exist",
        "roots": {"estate": str(ESTATE), "secondbrain": str(SECONDBRAIN)},
        "rules": {"full_copy_max_bytes": FULL_COPY_MAX_BYTES,
                  "head_window_entries": HEAD_WINDOW_ENTRIES},
    }
    manifest["identity"] = cut_identity(manifest)
    rows, tbytes, tentries = [], 0, 0
    for slug, rel in CHAINS.items():
        r = cut_chain(slug, rel)
        rows.append(r)
        tbytes += r.get("bytes", 0)
        tentries += r.get("entries", 0)
    manifest["chains"] = rows
    manifest["deferred"] = DEFERRED
    manifest["totals"] = {
        "chains_listed": len(CHAINS),
        "chains_found": sum(1 for r in rows if r.get("exists")),
        "source_bytes": tbytes,
        "source_entries": tentries,
        "covenant_house_match": manifest["identity"]["house"]["match"],
        "covenant_elder_match": manifest["identity"]["elder"]["match"],
    }
    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    t = manifest["totals"]
    print(f"\nfixtures: {t['chains_found']}/{t['chains_listed']} chains, "
          f"{t['source_entries']} entries, {t['source_bytes']} B | "
          f"covenant house={'PASS' if t['covenant_house_match'] else 'FAIL'} "
          f"elder={'PASS' if t['covenant_elder_match'] else 'FAIL'}")
    print("MANIFEST.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
