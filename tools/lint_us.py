#!/usr/bin/env python3
"""lint_us.py -- measure every .us declaration against the five gaps.

Written 2026-08-27 at the operator's word, after the Fabrice fold showed that a
seat can follow SPEC_US exactly and still land a declaration that reads wrong.
The finding was never the seat; it was the protocol's silences. This tool
measures those silences across the whole ground so they can be ruled on numbers
rather than on one example.

IT REFUSES NOTHING. Every check here is a LINT -- reported, never enforced.
SPEC_US is a frozen contract and changes only by new spec version at the
operator's gate (CHARTER: "never by edit"). This tool adds no rule; it counts
where the existing rules do not reach.

  G1  a permission not stated -- SPEC_US rules absence a refusal for
      can_approve and for no other field
  G2  a role naming a verb its grant does not carry
  G4  a covenant cited but never checked for fit against its ground
  G5  one id claimed by more than one ground (ON CONFLICT DO NOTHING skips
      silently, so a collision costs a citizen without a word)

  python tools/lint_us.py            report
  python tools/lint_us.py --quiet    counts only
"""
import importlib.util
import json
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
ARCHIVE = ATLAS.parent
ORACLE_PATH = ARCHIVE / "estate" / "Neiro" / "lib" / "us_read.py"
SKIP = {"node_modules", ".venv", "venv", "target", "__pycache__", ".git",
        # THE ATTIC IS NOT A GROUND. Folded copies are history kept by law
        # (fold, never delete), not live declarations. The first cut of this
        # lint walked it and reported 37 id collisions -- every one of them a
        # backup taken that same morning. A tool that counts the fold measures
        # its own process, not the estate.
        "attic", "folded"}

# Verbs a role may claim, and the grant each one needs. Deliberately small and
# literal: a lint that guesses is worse than no lint. Only unambiguous words.
VERB_NEEDS = {
    "commit": "bash", "push": "bash", "merge": "bash", "clone": "bash",
    "run": "bash", "runs": "bash", "execute": "bash", "tests": "bash",
    "compile": "bash", "spawn": "bash",
    "write": "edit", "writes": "edit", "edit": "edit", "edits": "edit",
    "modify": "edit", "modifies": "edit", "refactor": "edit",
    "record": "edit", "records": "edit", "scaffold": "edit",
}


def load_oracle():
    spec = importlib.util.spec_from_file_location("us_read_lint", ORACLE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The declared grounds. A lint measures grounds, not strays -- and walking the
# whole Archive means descending vendored trees that are neither. Override with
# arguments: python tools/lint_us.py <ground> [<ground> ...]
GROUNDS = ["atlas", "estate", "Fabrice", "Index", "Agents"]


def walk_us(roots=None):
    """Walk for .us files, pruning the skip set as we descend and surviving a
    directory we cannot read. rglob descends into vendored trees before
    filtering and dies outright on one I/O error; on this ground both happen."""
    import os
    unreadable = []
    for ground in (roots or GROUNDS):
        base = ARCHIVE / ground
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base, onerror=unreadable.append):
            dirs[:] = sorted(d for d in dirs if d not in SKIP)
            for f in sorted(files):
                if f.endswith(".us"):
                    yield Path(root) / f
    for err in unreadable:
        print(f"  [unreadable, skipped] {getattr(err, 'filename', err)}")


def granted(permission, key):
    """Does this permission block grant `key` at all? A missing key and an
    explicit 'deny' read the same: not granted. A dict of paths counts as
    granted if any entry allows or asks."""
    if not isinstance(permission, dict) or key not in permission:
        return False
    v = permission[key]
    if isinstance(v, str):
        return v not in ("deny", "none", "false")
    if isinstance(v, dict):
        return any(str(x) not in ("deny", "none", "false") for x in v.values())
    return bool(v)


def ground_of(path):
    """The ground a declaration sits in: the first path part under Archive."""
    rel = path.relative_to(ARCHIVE)
    return rel.parts[0] if len(rel.parts) > 1 else "."


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv[1:]
    US = load_oracle()
    seats, modules, others, broken = [], [], [], []

    for p in walk_us(args or None):
        raw = p.read_bytes()
        try:
            doc = US.parse(raw.decode("utf-8"))
        except Exception as exc:
            broken.append((p, f"{type(exc).__name__}: {exc}"))
            continue
        if doc["errors"]:
            broken.append((p, f"{len(doc['errors'])} parse error(s)"))
            continue
        rt = US.render(doc["prose"], doc["blocks"]).encode("utf-8") == raw
        for b in doc["blocks"]:
            rec = {"path": p, "ground": ground_of(p), "block": b,
                   "round_trip": rt}
            # SPEC_US names four kinds: module, agent, tool, skill. The ground
            # carries a fifth -- `snapshot` (estate\Neiro\Shelf\estate.us and
            # its snapshots\). Only an AGENT is granted capabilities, so only
            # an agent can be missing them; the first cut of this lint demanded
            # read/edit/net/bash from a snapshot. Anything not an agent is
            # counted and left alone, and an unknown kind is reported.
            kind = b.get("kind")
            if kind == "module":
                modules.append(rec)
            elif kind == "agent":
                seats.append(rec)
            else:
                rec["kind"] = kind
                others.append(rec)

    # --- ground -> epoch, taken from each ground's own module declaration ---
    ground_epoch = {}
    for m in modules:
        ground_epoch.setdefault(m["ground"], set()).add(m["block"].get("covenant"))

    g1 = g2 = g4 = 0
    g1_rows, g2_rows, g4_rows = [], [], []
    ids = {}

    for rec in seats:
        b, path, ground = rec["block"], rec["path"], rec["ground"]
        name = b.get("id", "?")
        perm = b.get("permission") or {}
        ids.setdefault(name, []).append(ground)

        missing = [k for k in ("read", "edit", "net", "bash") if k not in perm]
        if missing:
            g1 += 1
            g1_rows.append((ground, name, ",".join(missing)))

        role = str(b.get("role", "")).lower()
        words = [w.strip(".:()-\"'") for w in
                 role.replace(",", " ").replace(";", " ").split()]
        for i, w in enumerate(words):
            need = VERB_NEEDS.get(w)
            if not need or granted(perm, need):
                continue
            # "never writes feature code" is a REFUSAL, not a claim. The first
            # cut of this lint flagged two declarations for promising the exact
            # thing they promise not to do. A check that inverts its subject is
            # worse than no check.
            if any(n in words[max(0, i - 3):i] for n in
                   ("never", "not", "no", "without", "cannot", "neither")):
                continue
            # A noun reads like a verb: "keeper of sealed records", "validates
            # who may write". Skip when the word follows an article or a
            # preposition -- there it is the object, not the act.
            if i and words[i - 1] in ("the", "a", "an", "of", "and", "sealed",
                                      "may", "who", "all", "its", "their"):
                continue
            # A lint that cries wolf is worse than none. These words are nouns
            # as often as verbs -- "keeper of sealed records", "validates who
            # may write". Carry the phrase so a human judges, and never claim
            # more than "look at this".
            phrase = " ".join(words[max(0, i - 3):i + 3])
            g2 += 1
            g2_rows.append((ground, name, w, need, phrase))
            break

        # G4 has two shapes. A seat may cite a mark its ground does not declare
        # -- and a GROUND may declare more than one epoch, in which case no seat
        # can ever mismatch and the check is vacuous. The second is the defect
        # that hides the first.
        epochs = {e for e in (ground_epoch.get(ground) or set()) if e}
        cov = b.get("covenant")
        if epochs and cov and cov not in epochs:
            g4 += 1
            g4_rows.append((ground, name, cov, "/".join(sorted(epochs))))

    collisions = {k: v for k, v in ids.items() if len(set(v)) > 1}

    if not quiet:
        kinds = {}
        for r in others:
            kinds.setdefault(r["kind"], 0)
            kinds[r["kind"]] += 1
        print(f"  scanned {len(seats)} agents + {len(modules)} modules"
              + (f" + {len(others)} other blocks {kinds}" if others else "")
              + f" across {len(set(r['ground'] for r in seats+modules+others))} grounds")
        unknown = {k: v for k, v in kinds.items()
                   if k not in ("agent", "module", "tool", "skill")}
        if unknown:
            print(f"  KINDS NOT IN SPEC_US ({sum(unknown.values())}): {unknown}"
                  "  -- SPEC_US names module/agent/tool/skill")
        if broken:
            print(f"\n  UNPARSEABLE ({len(broken)})")
            for p, why in broken:
                print(f"    {p.relative_to(ARCHIVE)}: {why}")
        # per FILE, not per block -- a five-block document is one file, and the
        # first cut listed it five times
        files = {}
        for r in seats + modules + others:
            files.setdefault(r["path"], r["round_trip"])
        nort = sorted(p for p, ok in files.items() if not ok)
        print(f"\n  round-trip: {len(files)-len(nort)}/{len(files)} files canonical, "
              f"{len(nort)} NOT byte-identical under the oracle")
        for p in nort:
            print(f"    {p.relative_to(ARCHIVE)}")

        print(f"\n  G1  permission keys not stated ({g1})"
              "  -- SPEC_US rules absence a refusal for can_approve only")
        for ground, name, miss in g1_rows:
            print(f"    {ground:10} {name:16} missing: {miss}")

        print(f"\n  G2  role claims a verb its grant does not carry ({g2})"
              "  -- ADVISORY: these words are nouns as often as verbs; read the phrase")
        for ground, name, verb, need, phrase in g2_rows:
            print(f"    {ground:10} {name:16} '{verb}' needs {need}: \"...{phrase}...\"")

        multi = {g: e for g, e in ground_epoch.items() if len({x for x in e if x}) > 1}
        print(f"\n  G4a a ground declaring more than one epoch ({len(multi)})"
              "  -- while this holds, no seat in that ground can ever mismatch")
        for g, e in sorted(multi.items()):
            print(f"    {g:10} declares {', '.join(sorted(x for x in e if x))}")
        print(f"  G4b covenant not among its ground's declared epochs ({g4})")
        for ground, name, cov, epochs in g4_rows:
            print(f"    {ground:10} {name:16} cites {cov} | ground declares {epochs}")

        print(f"\n  G5  one id claimed by more than one ground ({len(collisions)})"
              "  -- ON CONFLICT DO NOTHING skips these silently")
        for name, grounds in sorted(collisions.items()):
            print(f"    {name:16} {', '.join(sorted(set(grounds)))}")

        print("\n  epochs declared, by ground")
        for ground, marks in sorted(ground_epoch.items()):
            print(f"    {ground:10} {', '.join(sorted(m or '-' for m in marks))}")

    print(f"\n  LINT -- G1 {g1} · G2 {g2} · G4 {g4} · G5 {len(collisions)} "
          f"· unparseable {len(broken)}")
    print("  Reported, never enforced. SPEC_US changes by new spec version at "
          "the operator's gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
