#!/usr/bin/env python3
"""cut_us_vectors.py -- cut A2-01/A2-02 `.us` goldens from the Python oracle.

Oracle: the read-only source ground `estate/Neiro/lib/us_read.py` (SPEC_US
names it; byte-identical copies live across every ground). Every vector is
computed BEFORE any Rust exists:

  files      the four tool-born declarations: exact prose, parsed blocks,
             and the oracle's own render() output -- byte-round-trip holds
             for all four (the fifth, manjuel5.us, was stricken by operator
             ruling 2026-08-25 and is excluded permanently).
  refusals   every prove()-style validation failure as an input block plus a
             named refusal CLASS (never raw Python error text -- parser
             internals are not .us law).
  docs       document-level failures keyed structurally (line numbers, not
             exception strings).
  derive     derive_tools fixtures incl. what the fold LOSES.

Deterministic on content (no wall clock); oracle sha256 carries provenance.
Stdlib only; runs in atlas/.venv.

    python tools/cut_us_vectors.py            cut / re-cut
    python tools/cut_us_vectors.py --verify   re-cut in memory, compare
"""
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
# THE ORACLE ROOT IS NAMEABLE. ADR-006 item 6, 2026-09-11.
#
# This was `ATLAS.parent` outright. Before the 2026-09-10 split atlas sat
# beside its source grounds, so the parent WAS the ground holding the oracle.
# After the split the parent is the manjuel core, and this resolves to a path
# that has never existed on any machine — so `tests/prove.py` reported the
# re-cut legs ABSENT naming a phantom. ABSENT was the right verdict for the
# wrong reason.
#
# The goldens themselves ARE committed and DO travel; only the RE-CUT needs
# the oracle. Set ATLAS_ORACLE_ROOT to the ground that holds it. Unset, the
# old location is still tried, so nothing that worked stops working.
import os
ARCHIVE = Path(os.environ.get("ATLAS_ORACLE_ROOT") or ATLAS.parent)
ORACLE_PATH = ARCHIVE / "estate" / "Neiro" / "lib" / "us_read.py"
OUT = ATLAS / "tests" / "fixtures" / "canon" / "us_vectors.json"

FILES = [
    r"estate\Agents\.us\Agents.us",
    r"estate\Neiro\.us\Neiro.us",
    r"estate\Neiro\Shelf\estate.us",
    r"estate\Neiro\Shelf\snapshots\estate_48a37de19f1974ca.us",
]

REFUSAL_CLASSES = [
    ("can_approve must be stated", "can_approve_absent"),
    ("can_approve must be false", "can_approve_not_false"),
    ("us must be ", "bad_version"),
    ("kind must be one of", "bad_kind"),
    ("id is required", "bad_id"),
    ("id must be lowercase kebab or snake", "bad_id"),
    ("must match its filename", "stem_mismatch"),
    ("a module must declare", "module_missing_field"),
    ("rows must be a non-empty list", "rows_empty"),
    ("verbs must be a non-empty list", "verbs_empty"),
    ("an agent's mode must be one of", "bad_mode"),
    ("must declare permission", "agent_permission_missing"),
    ("declares no module block", "no_module_block"),
]


def classify(msg):
    """Map an oracle UsRefused to its named class; never guess."""
    for needle, cls in REFUSAL_CLASSES:
        if needle in msg:
            return cls
    raise SystemExit(f"cut_us_vectors: unclassifiable refusal: {msg!r}")


def load_oracle():
    spec = importlib.util.spec_from_file_location("us_read_oracle", ORACLE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


US = None
UsRefused = None

SAMPLE_PROSE = """# AGENTS - the estate's engineering record

state = fold(record). Nothing is deleted; the past is appended and current
state is derived fresh from it."""

MODULE = {"us": 1, "id": "agents", "kind": "module", "office": "NEIRO",
          "generation": 1, "reports_to": "neiro", "can_approve": False,
          "body_v": 3, "wall": ".", "ledger": "state/ledger/ledger.jsonl",
          "rows": ["soul", "body", "road"],
          "verbs": ["look", "muster", "witness"],
          "covenant": "65118a147dd49ed9"}
AGENT = {"us": 1, "id": "courier", "kind": "agent", "mode": "subagent",
         "office": "STEWARD", "reports_to": "archivist", "can_approve": False,
         "permission": {"read": {"*": "allow"},
                        "edit": {"*": "deny", "shelf/**": "allow"},
                        "bash": {"*": "ask"}, "net": "deny"}}


def build_files():
    out = []
    for rel in FILES:
        path = ARCHIVE / rel
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        doc = US.parse(text)
        if doc["errors"]:
            raise SystemExit(f"cut_us_vectors: {rel} carries parse errors")
        original = doc["prose"], doc["blocks"]
        rendered = US.render(*original)
        if rendered.encode("utf-8") != raw_bytes:
            raise SystemExit(
                f"cut_us_vectors: {rel} does not byte-round-trip under the "
                "oracle -- the lawful set changed; investigate, never coerce")
        out.append({
            "file": rel.replace("\\", "/"),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "prose": doc["prose"],
            "blocks": doc["blocks"],
            "render_text": rendered,
            "byte_round_trip": True,
        })
    return out


def try_refuse(fn):
    try:
        fn()
        return None
    except UsRefused as exc:
        return classify(str(exc))


def build_refusals():
    """Each case stores its INPUT BLOCK so Rust drives byte-identical
    mutations, plus the expected refusal class."""
    def drop_key(block, key):
        return {k: v for k, v in block.items() if k != key}

    variants = [
        ("can_approve missing", drop_key(MODULE, "can_approve"), "Agents"),
        ("can_approve true", dict(MODULE, can_approve=True), "Agents"),
        ("can_approve truthy string", dict(MODULE, can_approve="no"), "Agents"),
        ("bad us version", dict(MODULE, us=2), "Agents"),
        ("unknown kind", dict(MODULE, kind="daemon"), "Agents"),
        ("missing id", dict(MODULE, id=""), "Agents"),
        ("shouty id", dict(MODULE, id="Agents"), "Agents"),
        ("empty rows", dict(MODULE, rows=[]), "Agents"),
        ("module missing ledger", drop_key(MODULE, "ledger"), "Agents"),
        ("module missing wall", drop_key(MODULE, "wall"), "Agents"),
        ("module id vs filename", dict(MODULE, id="steward"), "Agents"),
        ("agent bad mode", dict(AGENT, mode="primary-ish"), None),
        ("agent no permission", drop_key(AGENT, "permission"), None),
    ]
    cases = []
    for name, block, stem in variants:
        cls = try_refuse(lambda b=block, s=stem: US.validate(b, s))
        if cls is None:
            raise SystemExit(f"cut_us_vectors: refusal {name!r} was ACCEPTED")
        cases.append({"name": name, "target": "validate",
                      "stem": stem, "block": block, "expect_class": cls})
    # document-level: declaration() requires exactly one module block
    cls = try_refuse(lambda: US.declaration(US.parse("just prose")))
    if cls is None:
        raise SystemExit("cut_us_vectors: 'no module block' was ACCEPTED")
    cases.append({"name": "no module block", "target": "declaration_doc",
                  "input_text": "just prose", "expect_class": cls})
    return cases


def build_docs():
    """Document-level failures, pinned structurally (no exception text)."""
    out = []
    bad = US.parse("prose\n```json\n{not json}\n```")
    out.append({"name": "block_not_json",
                "input_text": "prose\n```json\n{not json}\n```",
                "expect_errors_nonempty": True,
                "first_error_mentions_line": 2})
    unclosed = US.parse("prose\n```json\n{}\n")
    out.append({"name": "unclosed_fence",
                "input_text": "prose\n```json\n{}\n",
                "expect_errors_nonempty": True,
                "first_error_says_never_closed": True})
    stray = US.parse("```python\nprint(1)\n```")
    out.append({"name": "unknown_fence_stays_prose",
                "input_text": "```python\nprint(1)\n```",
                "prose_contains": "print(1)",
                "expect_errors_nonempty": False})
    return out


def build_derive():
    cases = []
    d = US.derive_tools(AGENT["permission"])
    cases.append({"name": "courier", "permission": AGENT["permission"],
                  "tools": d["tools"], "lost": d["lost"]})
    variants = [
        ("flat_allow", {"read": "allow", "bash": "allow"}),
        ("all_deny", {"read": "deny", "edit": "deny"}),
        ("ask_flat", {"read": "ask"}),
        ("single_scoped", {"read": {"shelf/**": "allow"}}),
        ("multi_scoped_ask", {"edit": {"*": "deny", "out/**": "allow"},
                              "net": {"site": "ask"}, "read": "allow"}),
        ("empty_map", {}),
    ]
    for name, perm in variants:
        d = US.derive_tools(perm)
        cases.append({"name": name, "permission": perm,
                      "tools": d["tools"], "lost": d["lost"]})
    return cases


def build_document():
    return {
        "tool": "tools/cut_us_vectors.py",
        # NO atlas_version here -- see cut_canon_vectors.py for the diagnosis.
        # The version rides the witness, never the artifact.
        "ordering_note": "A2-01/A2-02: .us vectors cut from the Python "
                         "oracle BEFORE core/src/us.rs exists",
        "determinism_note": "no wall clock anywhere in this file; provenance "
                            "carried by the oracle sha256",
        "strike_note": "manjuel5.us excluded permanently by operator ruling "
                       "2026-08-25 (stricken to attic); the lawful set is "
                       "four tool-born declarations",
        "oracle": {
            "path": ORACLE_PATH.relative_to(ARCHIVE).as_posix(),
            "sha256": hashlib.sha256(ORACLE_PATH.read_bytes()).hexdigest(),
        },
        "tally": {
            "files": len(FILES),
            "refusals": 0,
            "docs": 0,
            "derive": 0,
        },
        "files": [],
        "refusals": [],
        "docs": [],
        "derive": [],
    }


def main():
    args = sys.argv[1:]
    global US, UsRefused
    US = load_oracle()
    UsRefused = US.UsRefused
    doc = build_document()
    doc["files"] = build_files()
    doc["refusals"] = build_refusals()
    doc["docs"] = build_docs()
    doc["derive"] = build_derive()
    doc["tally"] = {"files": len(doc["files"]), "refusals": len(doc["refusals"]),
                    "docs": len(doc["docs"]), "derive": len(doc["derive"])}
    blob = (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
            + chr(10)).encode("utf-8")

    if "--verify" in args:
        if OUT.exists() and OUT.read_bytes() == blob:
            print(f"US VECTORS VERIFY OK -- {OUT.name} byte-identical to a "
                  f"fresh cut ({len(blob)} bytes)")
            return 0
        print("VERIFY FAIL -- run the cutter to (re)land the vectors")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    t = doc["tally"]
    print(f"US VECTORS CUT -- files={t['files']} refusals={t['refusals']} "
          f"docs={t['docs']} derive={t['derive']} -> "
          f"tests/fixtures/canon/us_vectors.json")
    print(f"  oracle sha256 {doc['oracle']['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
