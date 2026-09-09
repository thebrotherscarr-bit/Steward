#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_memory_vectors.py -- F1-01 envelope goldens (spec-first, small step).

Renders expected memory envelopes over the FIXED bundle ground ledger
(tests/fixtures/rack_open_ground/state/rack_ledger.jsonl — the same three
witness lines rack_open proves). The Go memory tool must render these bytes
exactly.

Envelope contract (v1, both sides implement):
  header: ENVELOPE — "<query>" (<n> cited), or ENVELOPE — latest (<n> cited)
          when both filters are empty (latest single).
  block per answer:
    "  text: <full answer — envelopes never truncate>"
    "  citations:"
    "    - [<ts>] <voice> :: <question>"
  blocks joined by one blank line; file ends with exactly one newline.
  At most the latest 5 match, with "  (+N earlier, narrow the query)"
  when more match. Filters AND (voice exact, question case-insensitive
  substring). No match, or empty ledger, is a REFUSAL (pinned strings):
    'refused: no cited memory for "<query>" — never invented, never uncited.'
    'refused: the ledger is empty — no cited memory.'

--verify compares files only. Hermetic by law.
"""

import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
GROUND = os.path.join(FIX, "rack_open_ground", "state", "rack_ledger.jsonl")

CASES = [
    ("memory_q_word.txt", {"query": "say the word"}),
    ("memory_voice_llama.txt", {"voice": "llama3.2:latest"}),
    ("memory_latest.txt", {}),
]


def load_ledger():
    out = []
    for ln in open(GROUND, encoding="utf-8"):
        if ln.strip():
            out.append(json.loads(ln))
    return out


def match(lines, voice="", query=""):
    out = []
    for e in lines:
        if voice and e["voice"] != voice:
            continue
        if query and query.lower() not in e["question"].lower():
            continue
        out.append(e)
    return out


def envelope(query, entries):
    head = 'ENVELOPE — "%s" (%d cited)' % (query, len(entries))
    blocks = []
    for e in entries:
        blocks.append("  text: %s\n  citations:\n    - [%s] %s :: %s" % (
            e["answer"], e["ts"], e["voice"], e["question"]))
    return head + "\n" + "\n\n".join(blocks) + "\n"


def render(voice="", query=""):
    lines = load_ledger()
    if not lines:
        return None, "refused: the ledger is empty — no cited memory."
    if not voice and not query:
        picked = lines[-1:]
        return envelope("latest", picked), None
    found = match(lines, voice, query)
    if not found:
        q = query or voice
        return None, ('refused: no cited memory for "%s" — never invented, '
                      "never uncited." % q)
    extra = ""
    if len(found) > 5:
        extra = "\n  (+%d earlier, narrow the query)" % (len(found) - 5)
        found = found[-5:]
    text, _ = envelope(query or voice, found), None
    return text + extra + "\n" if extra else text, None


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    for name, kw in CASES:
        text, refusal = render(**kw)
        assert refusal is None, kw
        write_bytes(os.path.join(FIX, name), text)
        print("envelope -> %s" % name)
    text, refusal = render(query="no such thing")
    print("refusal pins: %r" % refusal)


def verify():
    print("\n  MEMORY -- envelope goldens (F1-01, fixture ledger)")
    ok = True
    for name, kw in CASES:
        want = open(os.path.join(FIX, name), encoding="utf-8").read()
        got, refusal = render(**kw)
        same = refusal is None and got == want
        ok = ok and same
        print("    [%s]  %s" % ("PASS" if same else "FAIL", name))
    _, refusal = render(query="no such thing")
    same = (refusal == 'refused: no cited memory for "no such thing" — '
            "never invented, never uncited.")
    ok = ok and same
    print("    [%s]  refusal pinned" % ("PASS" if same else "FAIL",))
    print()
    if ok:
        print("  PROVEN. Every answer carries citations or is refused.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
