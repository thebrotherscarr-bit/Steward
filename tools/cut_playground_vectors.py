#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_playground_vectors.py -- N4 playground goldens (spec-first).

The playground v1 contract (the oracle; the Go play package must honor it):

  prompt name   : ^[a-z0-9][a-z0-9_-]{0,63}$ (files under prompts/)
  file shape    : --- fence, name:/version:/description: lines, --- fence,
                  body with {{var}} slots. versions fold: prompts/<n>.md is
                  latest; history is prompts/<n>.v<k>.md, never rewritten.
  render        : {{var}} substituted verbatim; a missing var REFUSES
                  (never an empty guess, never invented).
  run receipt   : sha256(kind + "\\n" + prompt + "\\n" + version +
                         "\\n" + input + "\\n" + output + "\\n" + ts)
  seat address  : "@seat rest..." -> seat + question; no @ -> refused;
                  unknown seats refused by name (the enrollment law).
  override      : a named model is stamped measurement, not configuration.
  eval score    : exact match after trim+casefold -> pass/fail; anything
                  else is a fail with the diff shown, never a pass.

No live Ollama, no network. The fixture file is the oracle; --verify
recomputes every vector deterministically.
"""

import hashlib
import json
import os
import re
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
PLAY = os.path.join(FIX, "playground_vectors.json")

NAME_RE = r"^[a-z0-9][a-z0-9_-]{0,63}$"
SEAT_RE = r"^@([A-Za-z0-9_-]+)\s+([\s\S]+)$"


def render(body, vars):
    missing = []

    def sub(m):
        key = m.group(1).strip()
        if key not in vars:
            missing.append(key)
            return m.group(0)
        return str(vars[key])

    out = re.sub(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", sub, body)
    if missing:
        raise KeyError("missing var: " + ", ".join(sorted(set(missing))))
    return out


def receipt(kind, prompt, version, input, output, ts):
    h = hashlib.sha256()
    h.update((kind + "\n" + prompt + "\n" + str(version) + "\n"
              + input + "\n" + output + "\n" + ts).encode("utf-8"))
    return h.hexdigest()


def score(expected, got):
    return expected.strip().casefold() == got.strip().casefold()


def vectors():
    bad_names = ["", "UPPER", "has space", "semi;colon", "a" * 65,
                 "../escape", ".hidden"]
    good_names = ["hello", "sum", "a", "x" * 64, "with-dash_under0"]
    return {
        "name_re": NAME_RE,
        "bad_names": bad_names,
        "good_names": good_names,
        "render": {
            "body": "Hello {{name}}, you are {{role}}.",
            "vars": {"name": " Ada ", "role": "the sentry"},
            "want": "Hello  Ada , you are the sentry.",
        },
        "render_missing_refuses": ["role"],
        "receipt_example": {
            "kind": "prompt_run",
            "prompt": "hello",
            "version": 3,
            "input": "name=Ada",
            "output": "Hello Ada",
            "ts": "2026-09-09T12:00:00Z",
            "receipt": receipt("prompt_run", "hello", 3,
                               "name=Ada", "Hello Ada",
                               "2026-09-09T12:00:00Z"),
        },
        "seat_shape": {
            "re": SEAT_RE,
            "cases": [
                {"raw": "@manjuel what holds",
                 "seat": "manjuel", "question": "what holds"},
                {"raw": "@scout   survey the ground floor",
                 "seat": "scout", "question": "survey the ground floor"},
            ],
            "refused": ["no seat here", "@", "@  ", ""],
        },
        "eval_pairs": [
            {"expected": "witnessed", "got": "witnessed", "pass": True},
            {"expected": "Witnessed ", "got": " witnessed", "pass": True},
            {"expected": "something else", "got": "witnessed", "pass": False},
            {"expected": "", "got": "witnessed", "pass": False},
        ],
    }


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    doc = vectors()
    write_bytes(PLAY, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("playground -> %s" % PLAY)


def verify():
    doc = json.loads(open(PLAY, encoding="utf-8").read())
    want = vectors()
    print("\n  PLAYGROUND -- golden contract (N4, pinned oracle)")
    ok = True
    if doc != want:
        ok = False
        print("    [FAIL]  fixture drifted from the contract")
        for k in want:
            if doc.get(k) != want[k]:
                print("    drift:", k)
    else:
        print("    [PASS]  names + render + receipt + seat + eval")
    # Self-honesty: every pinned behavior recomputes.
    for n in want["good_names"]:
        if not re.match(want["name_re"], n):
            ok = False
            print("    [FAIL]  good name refused: %r" % n)
    for n in want["bad_names"]:
        if re.match(want["name_re"], n):
            ok = False
            print("    [FAIL]  bad name admitted: %r" % n)
    r = want["render"]
    if render(r["body"], r["vars"]) != r["want"]:
        ok = False
        print("    [FAIL]  render does not reproduce")
    try:
        render("Hello {{role}}.", {})
        ok = False
        print("    [FAIL]  missing var did not refuse")
    except KeyError:
        pass
    ex = want["receipt_example"]
    if receipt(ex["kind"], ex["prompt"], ex["version"],
               ex["input"], ex["output"], ex["ts"]) != ex["receipt"]:
        ok = False
        print("    [FAIL]  receipt formula does not reproduce")
    for c in want["seat_shape"]["cases"]:
        m = re.match(want["seat_shape"]["re"], c["raw"])
        if not m or m.group(1) != c["seat"] or m.group(2) != c["question"]:
            ok = False
            print("    [FAIL]  seat misparsed: %r" % c["raw"])
    for raw in want["seat_shape"]["refused"]:
        if re.match(want["seat_shape"]["re"], raw):
            ok = False
            print("    [FAIL]  seat shape admitted: %r" % raw)
    for p in want["eval_pairs"]:
        if score(p["expected"], p["got"]) != p["pass"]:
            ok = False
            print("    [FAIL]  eval misscored: %r" % p)
    if ok:
        print()
        print("  PROVEN. The playground measures, never guesses.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
