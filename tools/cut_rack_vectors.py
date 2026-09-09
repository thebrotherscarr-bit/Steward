#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_rack_vectors.py -- F1 rack_list goldens (spec-first, step 1 small).

Folds the LIVE loopback Ollama model list (/api/tags) ONCE into
tests/fixtures/rack_tags.json, then pins the expected ladder rendering in
tests/fixtures/rack_ladder.txt. The Go rack package must render these bytes
exactly from the folded tags.

Oracle discipline (THE_ROAD law): the folded file is the oracle. --verify
never fetches; it renders the file and compares. Live models come and go —
re-folding is a separate operator drift stroke (`cut`, bare), never part of
--verify. Loopback only: any host but 127.0.0.1/localhost is refused here
and in Go (zero-egress kin).

Tier rule (v1, the contract both sides implement):
  size <= 3GiB  -> scout      (small, fast, near)
  size <= 8GiB  -> voice      (working voices)
  else          -> mind       (heavy thinkers)
Size prints as decimal GB with one decimal (bytes/1e9). Family prints from
details.family (or "-" when absent). Sort: tier scout/voice/mind, name
ascending within. No role inference in v1 (honest: no guessing).
"""

import json
import os
import sys
import urllib.request

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
TAGS = os.path.join(FIX, "rack_tags.json")
LADDER = os.path.join(FIX, "rack_ladder.txt")
HOST = "http://127.0.0.1:11434"

TIERS = [("scout", 3 * 10**9), ("voice", 8 * 10**9), ("mind", None)]


def fetch_live():
    req = urllib.request.Request(HOST + "/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def tier_of(size):
    for name, cap in TIERS:
        if cap is None or size <= cap:
            return name
    return "mind"


def render(tags):
    models = tags.get("models", [])
    rows = []
    for m in models:
        details = m.get("details") or {}
        rows.append({"name": m.get("name", "?"),
                     "size": m.get("size", 0),
                     "family": details.get("family") or "-"})
    groups = {}
    for r in rows:
        groups.setdefault(tier_of(r["size"]), []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["name"])
    lines = ["THE RACK — lawful local voices (%d), loopback only"
             % len(rows)]
    for tier, _ in TIERS:
        if tier not in groups:
            continue
        cap = {k: v for k, v in
               [("scout", "≤3GB"), ("voice", "≤8GB"), ("mind", ">8GB")]}[tier]
        lines.append("  %s (%s):" % (tier, cap))
        for r in groups[tier]:
            lines.append("    - %s · %.1fGB · %s"
                         % (r["name"], r["size"] / 1e9, r["family"]))
    return "\n".join(lines) + "\n"


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    tags = fetch_live()
    write_bytes(TAGS, json.dumps(tags, indent=2, sort_keys=True) + "\n")
    ladder = render(tags)
    write_bytes(LADDER, ladder)
    print("folded %d live voices -> %s" % (len(tags.get("models", [])), TAGS))
    print("ladder -> %s (%d bytes)" % (LADDER, len(ladder.encode("utf-8"))))


def verify():
    tags = json.loads(open(TAGS, encoding="utf-8").read())
    want = open(LADDER, encoding="utf-8").read()
    got = render(tags)
    print("\n  RACK -- golden ladder (F1 step 1, folded oracle)")
    if got == want:
        print("    [PASS]  ladder renders folded tags byte-exact")
        print()
        print("  PROVEN. The ladder shows what the rack holds.")
        return 0
    print("    [FAIL]  ladder drifted from the folded tags")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
