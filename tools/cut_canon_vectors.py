#!/usr/bin/env python3
"""cut_canon_vectors.py -- cut A1-01 canon vectors from the Python oracle.

Oracle: the read-only source ground estate/Neiro/lib/us_canon.py (SPEC_CANON
names it). Every vector records exact input JSON TEXT plus, per form
(BODY_V 1/2/3 and the unknown-form stroke 4), either the expected canonical
text or a named refusal class. Rust must meet these bytes, never its own
opinion.

Case families:
  synthetic  hand-built inputs pinning the sharp edges: RFC 8785 3.2.3
             UTF-16 key order, the escape matrix, float spellings under
             V1/V2 (Python repr layout), big integers beyond i64 (digit
             passthrough V1/V2, refusal V3), safe-range ends, code-point
             vs UTF-16 ordering differentials.
  live       every sample entry cut in A1 step 1
             (tests/fixtures/samples/*/*.json), canonicalised under all
             three forms. Where the oracle refuses, the refusal IS the
             vector.

Output is deterministic on content (no wall clock): same oracle and same
sources give byte-identical vectors.json, so --verify can hold the gate.
Stdlib only; runs in atlas/.venv.

    python tools/cut_canon_vectors.py            cut / re-cut
    python tools/cut_canon_vectors.py --verify   re-cut in memory, compare

Note on construction: every backslash in this file is produced through
BS = chr(92) rather than typed literally, so no editor or transport layer
can silently turn an escape sequence into a real control byte.
"""
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
ARCHIVE = ATLAS.parent
ORACLE_PATH = ARCHIVE / "estate" / "Neiro" / "lib" / "us_canon.py"
SAMPLES = ATLAS / "tests" / "fixtures" / "samples"
OUT = ATLAS / "tests" / "fixtures" / "canon" / "vectors.json"

REASON_FLOAT = "float"
REASON_INT_RANGE = "int_range"
REASON_UNKNOWN_BODY_V = "unknown_body_v"
REASONS = [REASON_FLOAT, REASON_INT_RANGE, REASON_UNKNOWN_BODY_V]

FORMS = (1, 2, 3)
UNKNOWN_FORM_STROKE = 4

# byte-level shorthands so the source stays free of literal backslashes
BS = chr(92)   # backslash
DQ = chr(34)   # double quote


def jstr(inner):
    """A JSON string literal carrying inner escape TEXT verbatim."""
    return DQ + inner + DQ


def build_texts():
    """(name, exact JSON input text) pairs; sharp edges only."""
    texts = []

    # RFC 8785 3.2.3's own ordering example, keys scrambled on input. Astral
    # key carried as its literal character (the U-escape is Python syntax,
    # not JSON).
    rfc = (
        "{"
        + jstr("€") + ": " + jstr("Euro Sign") + ", "
        + jstr(BS + "r") + ": " + jstr("Carriage Return") + ", "
        + jstr("דּ") + ": " + jstr("Hebrew Letter Dalet With Dagesh") + ", "
        + jstr("1") + ": " + jstr("One") + ", "
        + jstr("😀") + ": " + jstr("Emoji: Grinning Face") + ", "
        + jstr(BS + "u0080") + ": " + jstr("Control") + ", "
        + jstr("ö") + ": " + jstr("Latin Small Letter O With Diaeresis")
        + "}"
    )
    texts.append(("rfc_8785_323_key_order", rfc))

    # Escape matrix: the two mandatory, five short forms, other C0 lowercase,
    # DEL escaped by V1 but literal under V2/V3, euro literal under V2/V3.
    esc = (
        "{" + jstr("k") + ": " + jstr(
            BS + DQ + BS + BS + BS + "b" + BS + "f" + BS + "n"
            + BS + "r" + BS + "t" + BS + "u0000" + BS + "u001f"
            + BS + "u007f€"
        ) + "}"
    )
    texts.append(("escape_matrix", esc))

    # Parser normalisation: solidus and u-escapes fold before canon rewrites.
    texts.append((
        "solidus_and_unicode_escapes",
        "{" + jstr("a") + ": " + jstr(BS + "/" + " " + BS + "u0041 "
                                      + BS + "u20ac") + "}",
    ))

    # Literals, nesting; V3 output must carry no insignificant whitespace.
    texts.append((
        "literals_nesting",
        "[null, true, false, {"
        + jstr("z") + ": [], " + jstr("a") + ": {}}]",
    ))

    # Whitespace between tokens never survives canon.
    ws_text = (
        "{" + chr(10) + chr(9) + jstr("a") + " :" + chr(9) + "1,"
        + chr(10) + " " + jstr("b") + chr(9) + ":" + chr(9)
        + "[1 , 2 ,{" + jstr("c") + ":  null } ]" + chr(10) + "}"
    )
    texts.append(("whitespace_between_tokens", ws_text))

    # Bool must never fall through to the integer writer.
    texts.append((
        "bool_not_int",
        "{" + jstr("t") + ": true, " + jstr("n") + ": 1}",
    ))

    # The safe range itself is carried, both ends, under every form.
    texts.append((
        "safe_int_ends",
        "{" + jstr("x") + ": 9007199254740991, "
        + jstr("y") + ": -9007199254740991}",
    ))

    # One past each end: V3 refuses int_range; V1/V2 carry.
    texts.append((
        "int_outside_safe",
        "{" + jstr("x") + ": 9007199254740992, "
        + jstr("y") + ": -9007199254740992}",
    ))

    # Real custody-shaped signature components (~77 digits, beyond i64):
    # V1/V2 pass the digits through exactly; V3 refuses int_range.
    sig0 = ("45080089829490884363882812606602674006760259617678563422530483"
            "273414777721469")
    sig1 = ("13617885940436894867965405303999551862086640376533908768222063"
            "82297032545532")
    texts.append((
        "bigint_signature_components",
        "{" + jstr("sig") + ": [" + sig0 + ", " + sig1 + "]}",
    ))

    # Integer spellings normalise exactly as json.loads does (-0 becomes 0).
    texts.append((
        "int_spellings",
        "{" + jstr("z") + ": 0, " + jstr("m") + ": -0}",
    ))

    # Non-ASCII: V1 escapes, V2 carries raw UTF-8 -- the recorded split.
    texts.append((
        "unicode_v1_v2",
        "{" + jstr("note") + ": " + jstr("€ café") + "}",
    ))

    # ASCII ledger shape: where the orders cannot disagree, all three agree
    # with the obvious form (guard against hand-rolled writer drift).
    texts.append((
        "plain_ascii_body",
        "{"
        + jstr("ts") + ": " + jstr("2026-08-17T00:00:00Z") + ", "
        + jstr("kind") + ": " + jstr("awaken") + ", "
        + jstr("payload") + ": {" + jstr("mark") + ": "
        + jstr("65118a147dd49ed9") + ", " + jstr("n") + ": 3}, "
        + jstr("prev") + ": " + jstr("0" * 64) + ", "
        + jstr("actor") + ": " + jstr("kyler")
        + "}",
    ))

    # Empty containers.
    texts.append((
        "empty_containers",
        "{" + jstr("e") + ": {}, " + jstr("l") + ": []}",
    ))

    # Astral KEY against U+E000..U+FFFF keys: UTF-16 order differs from
    # code-point order -- V3 sorts the emoji first, V1/V2 sort it middle.
    texts.append((
        "astral_key_ordering",
        "{"
        + jstr("😀x") + ": " + jstr("emoji-first") + ", "
        + jstr("דּ") + ": " + jstr("dalet") + ", "
        + jstr("é") + ": " + jstr("accent")
        + "}",
    ))
    return texts


FLOAT_TOKENS = [
    "0.0", "-0.0", "1.0", "1.5", "0.1", "10.25", "1e-4", "1e-5", "1e15",
    "1e16", "1e30", "5e-324", "1.7976931348623157e308", "-2.5e-9", "123.456",
]


def build_synthetic_cases(oracle):
    """Every sharp-edge input above, plus the float spellings wall and a
    depth probe."""
    cases = []
    for name, text in build_texts():
        obj = json.loads(text)
        cases.append(_case(f"synthetic__{name}", "synthetic", None, text, obj))

    pairs = ", ".join(
        jstr(f"f{i}") + ": " + tok for i, tok in enumerate(FLOAT_TOKENS)
    )
    text = "{" + pairs + "}"
    obj = json.loads(text)
    cases.append(_case("synthetic__float_spellings", "synthetic", None,
                       text, obj))

    depth = 64
    text = "[" * depth + "1" + "]" * depth
    obj = json.loads(text)
    cases.append(_case("synthetic__deep_nesting", "synthetic", None,
                       text, obj))
    return cases


def build_live_cases(oracle):
    if not SAMPLES.is_dir():
        raise SystemExit(f"cut_canon_vectors: samples dir missing: {SAMPLES}")
    files = sorted(SAMPLES.glob("*/*.json"))
    if not files:
        raise SystemExit("cut_canon_vectors: no sample fixtures found")
    cases = []
    for path in files:
        rel_posix = path.relative_to(ATLAS).as_posix()
        stem = path.relative_to(SAMPLES).as_posix()[: -len(".json")]
        text = path.read_bytes().decode("utf-8")
        obj = json.loads(text)
        cases.append(_case("live__" + stem, "live", rel_posix, text, obj))
    return cases


def classify(exc):
    """Map an oracle CanonRefused to its named class; never guess."""
    msg = str(exc)
    if "float refused" in msg:
        return REASON_FLOAT
    if "outside the ECMAScript safe range" in msg:
        return REASON_INT_RANGE
    if "no such BODY_V" in msg:
        return REASON_UNKNOWN_BODY_V
    raise SystemExit(
        f"cut_canon_vectors: unclassifiable oracle refusal: {msg!r}")


def _case(cid, origin, source, text, obj):
    forms = {}
    for v in FORMS + (UNKNOWN_FORM_STROKE,):
        try:
            forms[str(v)] = {"expect": "output",
                             "text": ORACLE.canon(obj, v)}
        except CanonRefused as exc:
            forms[str(v)] = {"expect": "refuse", "reason": classify(exc)}
    case = {"id": cid, "origin": origin, "input_text": text, "forms": forms}
    if source is not None:
        case["source"] = source
    return case


def load_oracle():
    spec = importlib.util.spec_from_file_location("us_canon_oracle",
                                                  ORACLE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ORACLE = None
CanonRefused = None


def build_document():
    cases = build_synthetic_cases(ORACLE) + build_live_cases(ORACLE)
    tally = Counter()
    for case in cases:
        for vec in case["forms"].values():
            tally[(vec["expect"], vec.get("reason"))] += 1
    return {
        "tool": "tools/cut_canon_vectors.py",
        # NO atlas_version here. A golden master's job is to detect DATA drift;
        # stamping a mutable value into an immutable artifact made --verify a
        # version check, so every VERSION bump reddened every fixture and a
        # real drift arriving in the same sitting would have been laundered by
        # the re-cut. Diagnosed 2026-08-27: the three cutters had been red
        # since the +a1 -> +b2 bump, one line out of 279,000 bytes, no data
        # moved. The version rides the WITNESS (the cut line below, the seat
        # log, STATE_OF_BUILD), never the artifact.
        "ordering_note": "A1-01: canon vectors cut from the Python oracle "
                         "(SPEC_CANON source of truth) BEFORE canon.rs exists",
        "determinism_note": "no wall clock anywhere in this file; provenance "
                            "carried by the oracle sha256",
        "oracle": {
            "path": ORACLE_PATH.relative_to(ARCHIVE).as_posix(),
            "sha256": hashlib.sha256(ORACLE_PATH.read_bytes()).hexdigest(),
        },
        "reason_vocabulary": REASONS,
        "tally": {
            "cases": len(cases),
            "vectors": sum(tally.values()),
            "by_outcome": {
                "_".join(str(k) for k in key): n
                for key, n in sorted(tally.items(), key=lambda kv: str(kv[0]))
            },
        },
        "cases": cases,
    }


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)


def main():
    args = sys.argv[1:]
    global ORACLE, CanonRefused
    ORACLE = load_oracle()
    CanonRefused = ORACLE.CanonRefused
    blob = render(build_document()).encode("utf-8")

    if "--verify" in args:
        if not OUT.exists():
            print(f"VERIFY FAIL -- {OUT.name} absent; run the cutter first")
            return 1
        if OUT.read_bytes() == blob:
            print(f"CANON VECTORS VERIFY OK -- {OUT.name} byte-identical to "
                  f"a fresh cut ({len(blob)} bytes)")
            return 0
        print("VERIFY FAIL -- landed vectors drifted from a fresh cut; "
              "re-cut and witness, never patch silently")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    t = json.loads(blob.decode("utf-8"))["tally"]
    refusals = {k: v for k, v in t["by_outcome"].items()
                if k.startswith("refuse")}
    version = (ATLAS / "VERSION").read_text(encoding="utf-8").strip()
    print(f"CANON VECTORS CUT -- {t['cases']} cases, {t['vectors']} "
          f"form-vectors -> tests/fixtures/canon/vectors.json")
    print(f"  cut at atlas {version} -- witness this line, not the artifact")
    print(f"  outcomes: outputs={t['vectors'] - sum(refusals.values())}, "
          f"refusals={sum(refusals.values())}"
          + (f" {refusals}" if refusals else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
