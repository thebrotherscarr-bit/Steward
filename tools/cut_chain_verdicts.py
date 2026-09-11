#!/usr/bin/env python3
"""cut_chain_verdicts.py -- cut A1-02/A1-03 golden verdicts from the oracles.

Two read-only oracle modules are named by SPEC_CHAINS:

  estate/Neiro/lib/us_chain.py       verify() -> EMPTY | INTACT | FLIP |
                                     TAMPER with flips[]/broke_at/appendable
  estate/Neiro/lib/prove_parity.py   read_chain() -> form recognition-by-trial
                                     over 13 named constructions + weld walk

Every fixture chain under tests/fixtures/chains gets BOTH provers run over
it and the results frozen here. Then, on TEMP GROUND ONLY, four injection
recipes run against two representative chains (the BODY_V3 ledger and a
legacy board-V1 16-hex board) and their verdicts freeze too -- A1-03's FLIP-
vs-TAMPER material, cut before a line of Rust exists.

Deterministic on content (no wall clock); oracle sha256s carry provenance.
Stdlib only; runs in atlas/.venv.

    python tools/cut_chain_verdicts.py            cut / re-cut
    python tools/cut_chain_verdicts.py --verify   re-cut in memory, compare
"""
import hashlib
import io
import importlib.util
import json
import shutil
import sys
import tempfile
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
LIB = ARCHIVE / "estate" / "Neiro" / "lib"
CHAINS_DIR = ATLAS / "tests" / "fixtures" / "chains"
OUT = ATLAS / "tests" / "fixtures" / "canon" / "chain_verdicts.json"

sys.path.insert(0, str(LIB))


def load(name):
    spec = importlib.util.spec_from_file_location(name, LIB / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


US_CHAIN = None
PROVE_PARITY = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_guarded(path):
    """us_chain.verify was written for the stamped-V3 world: an entry with
    no hash field makes its weld-walk crash on prev[:12]. Three estate
    chains carry such rows. That IS oracle behavior -- recorded as a skip
    with the reason, never papered over."""
    rows = PROVE_PARITY._rows(str(path))
    if any(not e.get("hash") for e in rows):
        return {"verify_skipped": "rows without hash fields "
                                  "(us_chain.verify requires one per entry)"}
    return norm_verify(US_CHAIN.verify(str(path)))


def norm_verify(state):
    """The us_chain.verify dict, normalised to a stable key set."""
    out = {
        "verdict": state["verdict"],
        "entries": state["entries"],
        "flips": state.get("flips", []),
        "appendable": state.get("appendable"),
    }
    for key in ("broke_at", "head"):
        if key in state:
            out[key] = state[key]
    out["why"] = state.get("why")
    return out


def norm_parity(r):
    return {
        "entries": r["entries"],
        "hex_width": r["hex"],
        "form": r["form"],
        "matched": r["matched"],
        "whole": r["whole"],
        "weld_ok": r["weld"],
        "weld_broke": r["weld_broke"],
        "head": r["head"],
    }


# -- injection recipes ----------------------------------------------------------
# Each op rewrites WHOLE LINES of a temp copy, leaving sibling lines verbatim;
# the flipped line is re-serialised the way the estate writes lines.

INJECT_SOURCES = [
    "agents_seatlog.jsonl",   # BODY_V3 stamped, 64-hex, the current form
    "steward_board.jsonl",    # legacy board family, 16-hex heads
]


def mutate_hashed_material(entry):
    """Change one byte of hashed content, leaving the stored hash alone."""
    if isinstance(entry.get("payload"), dict):
        entry["payload"]["__golden_flip__"] = "oracle was here"
    elif isinstance(entry.get("body"), dict):
        entry["body"]["__golden_flip__"] = "oracle was here"
    else:
        entry["kind"] = (entry.get("kind") or "") + "X"


def apply_op(lines, op):
    """Apply one recipe to raw lines; returns the rewritten lines."""
    op_name = op["op"]
    idx = op.get("index")
    if op_name == "mutate_hashed_material":
        entry = json.loads(lines[idx])
        mutate_hashed_material(entry)
        lines[idx] = json.dumps(entry, ensure_ascii=False)
        return lines
    if op_name == "drop_entry":
        del lines[idx]
        return lines
    if op_name == "truncate_to":
        return lines[: op["keep"]]
    if op_name == "corrupt_json_line":
        lines[idx] = "{broken"
        return lines
    raise SystemExit(f"cut_chain_verdicts: unknown op {op_name!r}")


RECIPES = [
    {"op": "mutate_hashed_material", "index": 1},
    {"op": "drop_entry", "index": 1},
    {"op": "truncate_to", "keep": 2},
    {"op": "corrupt_json_line", "index": 1},
]


def build_injections():
    out = []
    tmp = tempfile.mkdtemp(prefix="cut_chain_verdicts_")
    try:
        for src in INJECT_SOURCES:
            origin = CHAINS_DIR / src
            raw = origin.read_bytes().decode("utf-8")
            for recipe in RECIPES:
                work = Path(tmp) / f"{src}.{recipe['op']}.jsonl"
                lines = [ln for ln in raw.split(chr(10)) if ln.strip()]
                work.write_text(
                    chr(10).join(apply_op(list(lines), dict(recipe)))
                    + chr(10),
                    encoding="utf-8", newline="")
                parity = PROVE_PARITY.read_chain(str(work))
                state = verify_guarded(work)
                out.append({
                    "source": "chains/" + src,
                    "recipe": recipe,
                    "parity": norm_parity(parity),
                    "verify": norm_verify(state),
                })
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def build_document():
    chains = []
    for path in sorted(CHAINS_DIR.glob("*.jsonl")):
        rel = "chains/" + path.name
        parity = PROVE_PARITY.read_chain(str(path))
        state = verify_guarded(path)
        chains.append({
            "file": rel,
            "sha256": sha(path),
            "parity": norm_parity(parity),
            "verify": state,
        })
    return {
        "tool": "tools/cut_chain_verdicts.py",
        # NO atlas_version here -- see cut_canon_vectors.py for the diagnosis.
        # The version rides the witness, never the artifact.
        "ordering_note": "A1-02/A1-03: chain verdicts cut from the Python "
                         "provers BEFORE forms.rs/chain.rs exist",
        "determinism_note": "no wall clock anywhere in this file; provenance "
                            "carried by oracle sha256s",
        "oracles": {
            "us_chain": {
                "path": "estate/Neiro/lib/us_chain.py",
                "sha256": sha(LIB / "us_chain.py"),
            },
            "prove_parity": {
                "path": "estate/Neiro/lib/prove_parity.py",
                "sha256": sha(LIB / "prove_parity.py"),
            },
            "us_canon": {
                "path": "estate/Neiro/lib/us_canon.py",
                "sha256": sha(LIB / "us_canon.py"),
            },
        },
        "tally": {
            "chains": len(chains),
            "injections": len(INJECT_SOURCES) * len(RECIPES),
        },
        "chains": chains,
        "injections": build_injections(),
    }


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)


def main():
    args = sys.argv[1:]
    global US_CHAIN, PROVE_PARITY
    US_CHAIN = load("us_chain")
    PROVE_PARITY = load("prove_parity")
    blob = render(build_document()).encode("utf-8")

    if "--verify" in args:
        if not OUT.exists():
            print(f"VERIFY FAIL -- {OUT.name} absent; run the cutter first")
            return 1
        if OUT.read_bytes() == blob:
            print(f"CHAIN VERDICTS VERIFY OK -- {OUT.name} byte-identical to "
                  f"a fresh cut ({len(blob)} bytes)")
            return 0
        print("VERIFY FAIL -- landed verdicts drifted from a fresh cut; "
              "re-cut and witness, never patch silently")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    doc = json.loads(blob.decode("utf-8"))
    forms = sorted({c["parity"]["form"] for c in doc["chains"]
                    if c["parity"]["whole"]})
    print(f"CHAIN VERDICTS CUT -- {doc['tally']['chains']} chains x 2 provers, "
          f"{doc['tally']['injections']} injections "
          f"-> tests/fixtures/canon/chain_verdicts.json")
    print(f"  fully-recognized forms across the estate fixtures: "
          f"{', '.join(forms)}")
    inj = doc["injections"]
    by_src = {}
    for i in inj:
        by_src.setdefault(i["source"].split("/")[-1], []).append(
            i["verify"]["verdict"])
    for src, verdicts in sorted(by_src.items()):
        print(f"  injections {src}: {' / '.join(v['verdict'] for v in inj[:0])}"
              f"{', '.join(verdicts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
