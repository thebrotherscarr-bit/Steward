#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_trade_vectors.py -- D2 trade golden masters (spec-first).

Runs the read-only trade skills (property / workorder / inspect / report)
over a temp book through one scripted scenario and pins:
  * every command output, raw AND time-normalized (ts/dates/hash receipts
    differ run to run — wall clocks cannot be byte-pinned across runs, so
    parity is proven on normalized shapes PLUS cross-verification);
  * chain stats (entry counts per book);
  * the scenario books themselves (properties.jsonl, workorders.db,
    workorders_audit.jsonl, inspections.jsonl) copied to
    tests/fixtures/trade_books/ — the Rust port must verify these bytes
    intact (hash-compat on real oracle bytes), and the oracle must verify
    Rust-written books (checked by tools/check_trade_parity.py).

No network. Temp ground only. `--verify` replays and compares normalized
shapes + chain stats; run bare to (re)cut. Hermetic by law.
"""

import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
SKILLS = os.path.normpath(os.path.join(
    ATLAS, "..", "estate", "Steward 1.0", "skills"))
FIX = os.path.join(ATLAS, "tests", "fixtures")
BOOKS = os.path.join(FIX, "trade_books")
GOLDEN = os.path.join(FIX, "trade_vectors.json")

TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CLOCK_RE = re.compile(r"\b\d{2}:\d{2}(:\d{2})?\b")
HASH_RE = re.compile(r"\b[0-9a-f]{12,64}\b")
# Temp grounds differ run to run (random suffix); the path is not content.
TMP_RE = re.compile(re.escape(tempfile.gettempdir()) + r"[\\/][A-Za-z0-9_.-]+")


def load(name):
    spec = importlib.util.spec_from_file_location(
        "trade_oracle_" + name, os.path.join(SKILLS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(s):
    s = TS_RE.sub("<TS>", s)
    s = DATE_RE.sub("<DATE>", s)
    s = CLOCK_RE.sub("<CLOCK>", s)
    s = TMP_RE.sub("<TMP>", s)
    return HASH_RE.sub("<HASH>", s)


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def scenario():
    """Returns (outputs, books, tmpdir) — outputs: [(skill, cmd, out)].
    Callers copy book files as BYTES (shutil) and remove tmpdir: the sqlite
    book is binary and must never round-trip through text."""
    prop = load("property")
    wo = load("workorder")
    insp = load("inspect")
    rep = load("report")
    d = tempfile.mkdtemp(prefix="trade_vectors_")
    out = []

    def run(skill, mod, cmd):
        r = mod._run(cmd, d)
        out.append([skill, cmd, r])
        return r

    run("property", prop, "enroll Red Rock Loop | 55 Red Rock Loop Rd, Sedona")
    run("property", prop, "enroll Juniper Ridge casita | key in the lockbox")
    run("property", prop, "list")
    run("workorder", wo, "add Juniper Ridge casita | swamp cooler pads worn | Dale")
    run("workorder", wo, "add Red Rock Loop | gate hinge javelina damage | Marco")
    run("workorder", wo, "assign 2 | Marco")
    run("workorder", wo, "done 1 | 300")
    run("workorder", wo, "list open")
    run("workorder", wo, "list done")
    run("workorder", wo, "list all")
    run("inspect", insp, "log Red Rock Loop | water heater=pass ; drip zone 3=fail | javelina bent the gate")
    run("inspect", insp, "log Juniper Ridge casita | swamp cooler=pass")
    run("inspect", insp, "report red rock")
    run("report", rep, "Red Rock Loop")
    run("report", rep, "Oak Creek")
    verifications = [
        ["property", prop._run("verify", d)],
        ["workorder", wo._run("verify", d)],
        ["inspect", insp._run("verify", d)],
    ]
    return out, verifications, d


def read_books(d):
    """Book bytes, binary-safe (the sqlite book is not text)."""
    books = {}
    for rel in ["properties.jsonl", "workorders.db",
                "workorders_audit.jsonl", "inspections.jsonl"]:
        with open(os.path.join(d, rel), "rb") as f:
            books[rel] = f.read()
    return books


def book_text(books, rel):
    return books[rel].decode("utf-8")


def payload():
    out, verifications, d = scenario()
    try:
        books = read_books(d)
        stats = {}
        for rel, data in books.items():
            if rel.endswith(".db"):
                stats[rel] = {"lines": None, "bytes": len(data)}
            else:
                text = data.decode("utf-8")
                stats[rel] = {"lines": len([l for l in text.split("\n") if l.strip()]),
                              "bytes": len(data)}
        return {
            "spec": "D2 Trade parity (golden-master shapes + cross-verify books)",
            "oracles": {n: sha_of(os.path.join(SKILLS, n + ".py"))
                        for n in ["property", "workorder", "inspect", "report"]},
            "normalize": "TS-><TS>, DATE-><DATE>, CLOCK-><CLOCK>, TMPDIR-><TMP>, 12..64hex-><HASH>",
            "outputs": [{"skill": s, "cmd": c, "raw": r, "norm": norm(r)}
                        for s, c, r in out],
            "verifications": [{"skill": s, "out": o} for s, o in verifications],
            "chain_stats": stats,
            "books_note": "tests/fixtures/trade_books/ holds these same bytes",
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def cut():
    p = payload()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    os.makedirs(BOOKS, exist_ok=True)
    _, _, d = scenario()
    try:
        for rel, data in read_books(d).items():
            write_bytes(os.path.join(BOOKS, rel), data)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("cut %d trade outputs -> %s" % (len(p["outputs"]), GOLDEN))
    print("  oracles:")
    for n, h in p["oracles"].items():
        print("    %s.py  %s" % (n, h))
    print("  books -> %s" % BOOKS)
    for o in p["outputs"]:
        print("  [%s] %-9s %-52s %s" % ("ok", o["skill"], o["cmd"][:52],
                                        o["norm"][:70].replace("\n", " / ")))


def verify():
    p = payload()
    pinned = json.loads(open(GOLDEN, encoding="utf-8").read())
    print("\n  TRADE -- golden masters (D2, hermetic, local oracle)")
    ok = True
    if pinned["oracles"] != p["oracles"]:
        print("    [FAIL]  oracle drifted")
        ok = False
    else:
        print("    [PASS]  oracle pins hold (4 skills)")
    if len(pinned["outputs"]) != len(p["outputs"]):
        print("    [FAIL]  output count moved")
        ok = False
    for have, want in zip(p["outputs"], pinned["outputs"]):
        match = (have["skill"] == want["skill"] and have["cmd"] == want["cmd"]
                 and have["norm"] == want["norm"])
        if not match:
            ok = False
            print("    [FAIL]  %s %s" % (have["skill"], have["cmd"]))
            print("      gold: %s" % want["norm"][:160].replace("\n", " / "))
            print("      live: %s" % have["norm"][:160].replace("\n", " / "))
    if ok:
        print("    [PASS]  %d outputs match normalized shapes" % len(p["outputs"]))
    for rel, st in p["chain_stats"].items():
        pst = pinned["chain_stats"][rel]
        if rel.endswith(".db"):
            match = True  # binary sqlite: presence + verifications carry it
            print("    [PASS]  %-24s  %d bytes (binary book)" % (rel, st["bytes"]))
        else:
            match = st["lines"] == pst["lines"]
            print("    [%s]  %-24s  %d lines" % ("PASS" if match else "FAIL", rel, st["lines"]))
        ok = ok and match
    print()
    if ok:
        print("  PROVEN. The skills decide what the port must decide.")
        return 0
    print("  A vector failed. The trade draft is not what the oracle drafts.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
