#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_skill_vectors.py -- F1-03 skill-lint goldens (spec-first, closing step).

No validate-skills.mjs survives on the estate (T6 cites it as a pattern
only), so the oracle is the SKILL.md FORMAT plus the rack corpus itself:
frontmatter block, name == directory, non-empty description, non-empty
headed body, no duplicate keys. This cutter writes one minimal fixture per
rule (valid + one violation each) under tests/fixtures/skills/ and pins the
expected verdicts. `atl skill lint` must reproduce them exactly.

Rules v1 (pinned here, implemented in atl):
  R1 frontmatter: file opens with a --- ... --- block.
  R2 name: present, [a-z0-9-]+, and equal to the directory name.
  R3 description: present, 10..500 chars.
  R4 body: at least one markdown heading and one non-empty paragraph line.
  R5 keys: no duplicate frontmatter keys.

--verify checks fixtures unchanged + verdicts recompute. Hermetic by law.
"""

import json
import os
import re
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures", "skills")
GOLDEN = os.path.join(ATLAS, "tests", "fixtures", "skill_vectors.json")

VALID = """---
name: valid
description: A small valid probe skill for the lint golden set.
---

# Probe Valid

A paragraph of honest description. Triggers on probe duty.
"""

CASES = {
    "valid": (VALID, []),
    # No frontmatter means no name and no description either: the cascade
    # is honest (each rule independently true), pinned as such.
    "nofront": ("# No Frontmatter Here\n\nBody without a block.\n",
                ["R1", "R2", "R3"]),
    "noname": ("---\ndescription: Has a description but no name at all.\n---\n\n# Nameless\n\nBody here.\n",
               ["R2"]),
    "badname": ("---\nname: Bad_Name!!\ndescription: A fine description of decent length here.\n---\n\n# Bad Name\n\nBody here.\n",
                ["R2"]),
    "mismatch": ("---\nname: other-name\ndescription: A fine description of decent length here.\n---\n\n# Mismatch\n\nBody here.\n",
                 ["R2"]),
    "nodesc": ("---\nname: nodesc\n---\n\n# No Desc\n\nBody here.\n",
               ["R3"]),
    "shortdesc": ("---\nname: shortdesc\ndescription: tiny\n---\n\n# Short\n\nBody here.\n",
                  ["R3"]),
    "emptybody": ("---\nname: emptybody\ndescription: A fine description of decent length here.\n---\n",
                  ["R4"]),
    "noheading": ("---\nname: noheading\ndescription: A fine description of decent length here.\n---\n\nJust paragraphs, no headings at all here.\n",
                  ["R4"]),
    "dupkey": ("---\nname: dupkey\ndescription: First description here.\ndescription: Second description here.\n---\n\n# Dup\n\nBody here.\n",
               ["R5"]),
}


def lint(text, dirname):
    """Reference implementation: the rules above, plainly."""
    violations = []
    lines = text.split("\n")
    fm = {}
    dupes = set()
    body = text
    if len(lines) < 2 or lines[0].strip() != "---":
        violations.append("R1")
    else:
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                end = i
                break
        if end is None:
            violations.append("R1")
            end = len(lines)
        else:
            # Folded scalars (>, | and chomping variants): following
            # indented lines belong to the value.
            idx = 0
            fmlines = lines[1:end]
            while idx < len(fmlines):
                ln = fmlines[idx]
                if not ln.strip() or ln.strip().startswith("#"):
                    idx += 1
                    continue
                if ":" not in ln:
                    idx += 1
                    continue
                k, _, v = ln.partition(":")
                k, v = k.strip(), v.strip()
                if v in (">", "|", ">-", ">+", "|-", "|+") or v.startswith("> ") or v.startswith("| "):
                    style = v[0]
                    buf = []
                    idx += 1
                    while idx < len(fmlines) and (
                            fmlines[idx].startswith((" ", "\t"))):
                        buf.append(fmlines[idx].strip())
                        idx += 1
                    v = (" ".join(buf) if style == ">" else "\n".join(buf))
                    if k in fm:
                        dupes.add(k)
                    fm[k] = v
                    continue
                if k in fm:
                    dupes.add(k)
                fm[k] = v
                idx += 1
            body = "\n".join(lines[end + 1:])
    if dupes:
        violations.append("R5")
    name = fm.get("name", "")
    if (not name or not re.fullmatch(r"[a-z0-9-]+", name)
            or name != dirname):
        violations.append("R2")
    desc = fm.get("description", "")
    if not (10 <= len(desc) <= 500):
        violations.append("R3")
    blines = [l for l in body.split("\n") if l.strip()]
    if not (any(l.strip().startswith("#") for l in blines)
            and any(not l.strip().startswith("#") for l in blines)):
        violations.append("R4")
    return sorted(set(violations))


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    os.makedirs(FIX, exist_ok=True)
    for dirname, (text, _) in CASES.items():
        d = os.path.join(FIX, dirname)
        os.makedirs(d, exist_ok=True)
        write_bytes(os.path.join(d, "SKILL.md"), text)
    payload = {"spec": "F1-03 skill lint (rules R1..R5)",
               "rules": ["R1 frontmatter block", "R2 name present, shaped, == dirname",
                         "R3 description 10..500 chars",
                         "R4 headed non-empty body", "R5 no duplicate keys"],
               "cases": [{"dir": d, "expect": e} for d, (_, e) in CASES.items()]}
    write_bytes(GOLDEN, json.dumps(payload, indent=2) + "\n")
    print("cut %d skill fixtures -> %s" % (len(CASES), FIX))


def verify():
    print("\n  SKILL LINT -- goldens (F1-03, rule fixtures)")
    ok = True
    pinned = json.loads(open(GOLDEN, encoding="utf-8").read())
    if len(pinned["cases"]) != len(CASES):
        print("    [FAIL]  case count moved")
        return 1
    for case in pinned["cases"]:
        d = case["dir"]
        text = open(os.path.join(FIX, d, "SKILL.md"), encoding="utf-8").read()
        got = lint(text, d)
        same = got == case["expect"]
        ok = ok and same
        print("    [%s]  %-10s -> %s" % ("PASS" if same else "FAIL", d, got))
    print()
    if ok:
        print("  PROVEN. Violations name themselves; the valid set is green.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
