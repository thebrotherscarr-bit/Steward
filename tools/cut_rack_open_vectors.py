#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_rack_open_vectors.py -- F1 rack_open goldens (spec-first, small step).

Builds a FIXED bundle ground (tests/fixtures/rack_open_ground/ with three
witness lines, fixed timestamps, one long answer) and pins the expected
depth-1 and depth-2 bundles for llama3.2:latest. Depth 3 embeds the live
get_in_line pack, so it is asserted STRUCTURALLY (headers), never by bytes.

Bundle contract (v1, both sides implement):
  header:  "CONTEXT BUNDLE — <voice> at depth <N> (<project>)"
  d1:      header + blank + VOICE card:
             "VOICE <name>"
             "  tier: <t> · size: <X.Y>GB · family: <f>"
             "  capabilities: <sorted, comma-joined>"
  d2:      d1 + blank + "LADDER" + blank + <full ladder> +
           "MEMORY (last 5)" + up to 5 lines, or "  (no ledger yet)":
             "  [<ts>] <voice> :: <question> => <answer>"
  d3:      d2 + blank + "GROUND" + blank + <get_in_line pack>
  answers longer than 200 runes truncate to 200 + "… (+N more)".
  File ends with exactly one trailing newline.
Unknown voices refused by name; depths outside 1-3 refused; absent ledger
named ("  (no ledger yet)"), never an error.

--verify never fetches (folded tags/shows are the oracle). Hermetic by law.
"""

import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
TAGS = os.path.join(FIX, "rack_tags.json")
ASK = os.path.join(FIX, "rack_ask.json")
GROUND = os.path.join(FIX, "rack_open_ground")
BUNDLE1 = os.path.join(FIX, "rack_bundle_d1.txt")
BUNDLE2 = os.path.join(FIX, "rack_bundle_d2.txt")

LEDGER_LINES = [
    {"ts": "2026-01-01T00:00:00Z", "kind": "rack_ask",
     "voice": "llama3.2:latest", "question": "say the word",
     "answer": "witnessed"},
    {"ts": "2026-01-02T00:00:00Z", "kind": "rack_ask",
     "voice": "phi4-mini:latest", "question": "name the gate",
     "answer": "the gate is the operator's, always and only, held by no seat and no registry"},
    {"ts": "2026-01-03T00:00:00Z", "kind": "rack_ask",
     "voice": "llama3.2:latest", "question": "tell me everything",
     "answer": "L" * 300},
]

VOICE = "llama3.2:latest"
PROJECT = "atlas"


def tier_of(size):
    return ("scout" if size <= 3 * 10**9 else
            "voice" if size <= 8 * 10**9 else "mind")


def ladder(tags):
    rows = [{"name": m.get("name", "?"), "size": m.get("size", 0),
             "family": (m.get("details") or {}).get("family") or "-"}
            for m in tags.get("models", [])]
    groups = {}
    for r in rows:
        groups.setdefault(tier_of(r["size"]), []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["name"])
    lines = ["THE RACK — lawful local voices (%d), loopback only"
             % len(rows)]
    for tier, cap in [("scout", "≤3GB"), ("voice", "≤8GB"), ("mind", ">8GB")]:
        if tier not in groups:
            continue
        lines.append("  %s (%s):" % (tier, cap))
        for r in groups[tier]:
            lines.append("    - %s · %.1fGB · %s"
                         % (r["name"], r["size"] / 1e9, r["family"]))
    by_name = {r["name"]: r for r in rows}
    return "\n".join(lines) + "\n", by_name


def card(name, by_name, shows):
    r = by_name[name]
    caps = sorted((shows.get(name) or {}).get("capabilities", []))
    return ("VOICE %s\n"
            "  tier: %s · size: %.1fGB · family: %s\n"
            "  capabilities: %s" % (
                name, tier_of(r["size"]), r["size"] / 1e9, r["family"],
                ", ".join(caps)))


def short(answer):
    runes = list(answer)
    if len(runes) <= 200:
        return answer
    return "".join(runes[:200]) + "… (+%d more)" % (len(runes) - 200)


def memory(lines):
    if not lines:
        return "  (no ledger yet)"
    out = []
    for ln in lines[-5:]:
        e = json.loads(ln)
        out.append("  [%s] %s :: %s => %s"
                   % (e["ts"], e["voice"], e["question"],
                      short(e["answer"])))
    return "\n".join(out)


def bundle(voice, depth, project, by_name, shows, ladder_text, ledger):
    head = "CONTEXT BUNDLE — %s at depth %d (%s)\n\n%s" % (
        voice, depth, project, card(voice, by_name, shows))
    if depth >= 2:
        head += "\nLADDER\n\n" + ladder_text.rstrip("\n")
        head += "\nMEMORY (last 5)\n" + memory(ledger)
    return head + "\n"


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    tags = json.loads(open(TAGS, encoding="utf-8").read())
    ask = json.loads(open(ASK, encoding="utf-8").read())
    ladder_text, by_name = ladder(tags)
    os.makedirs(os.path.join(GROUND, "state"), exist_ok=True)
    ledger = [json.dumps(e, ensure_ascii=False) for e in LEDGER_LINES]
    write_bytes(os.path.join(GROUND, "state", "rack_ledger.jsonl"),
                "\n".join(ledger) + "\n")
    write_bytes(BUNDLE1, bundle(VOICE, 1, PROJECT, by_name,
                                ask["shows"], ladder_text, ledger))
    write_bytes(BUNDLE2, bundle(VOICE, 2, PROJECT, by_name,
                                ask["shows"], ladder_text, ledger))
    print("bundle ground (3 witness lines) -> %s" % GROUND)
    print("d1 -> %s, d2 -> %s" % (BUNDLE1, BUNDLE2))


def verify():
    tags = json.loads(open(TAGS, encoding="utf-8").read())
    ask = json.loads(open(ASK, encoding="utf-8").read())
    ladder_text, by_name = ladder(tags)
    ledger = [l for l in
              open(os.path.join(GROUND, "state", "rack_ledger.jsonl"),
                   encoding="utf-8").read().split("\n") if l.strip()]
    print("\n  RACK OPEN -- goldens (F1 step 3, fixture ground)")
    ok = True
    for path, depth in [(BUNDLE1, 1), (BUNDLE2, 2)]:
        want = open(path, encoding="utf-8").read()
        got = bundle(VOICE, depth, PROJECT, by_name, ask["shows"],
                     ladder_text, ledger)
        same = got == want
        ok = ok and same
        print("    [%s]  depth-%d bundle byte-exact"
              % ("PASS" if same else "FAIL", depth))
    print()
    if ok:
        print("  PROVEN. The bundle shows what the voice needs.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
