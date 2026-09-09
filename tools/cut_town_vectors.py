#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_town_vectors.py -- D1 Town golden vectors (spec-first).

Calls the read-only oracle's own decision function
(estate/Steward 1.0/trade_tasks.py candidates()) on a FIXED synthetic ops
ground and pins its exact decision strings: work-order keys/titles, patrol
month keys, slug shape, dedup-against-history, month recurrence. The Go port
(atlas-town) must reproduce these bytes from the equivalent JSONL ground.

Determinism notes, stated plainly:
  * `now` is passed explicitly (mid-month noon local: no TZ-boundary wobble).
  * Inspection timestamps are fixed strings; the oracle reads them with
    time.mktime/strptime (TZ-local), exactly as the port must. Cut and
    --verify run on the same box, like every other cutter here.
  * The oracle reads work orders from sqlite; the port reads JSONL (Go stdlib
    has no sqlite — ADAPT, witnessed). The cutter builds the sqlite with the
    skill's own schema and mirrors the same logical rows to JSONL, so both
    sides decide over identical facts.
  * No network, no wall clock at verify time (--verify rebuilds temp-only).

Goldens (tests/fixtures/town_vectors.json):
  draft      open WO + overdue/never properties decided (keys + titles verbatim)
  dedup      known_keys silences everything already handled
  recur      next month re-drafts patrols with the new month key (WO unchanged)
  closed     a ground with no open WOs and fresh inspections drafts nothing
"""

import json
import importlib.util
import os
import shutil
import sqlite3
import sys
import tempfile
import time

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
ARCHIVE = os.path.normpath(os.path.join(ATLAS, ".."))
TRADE = os.path.join(ARCHIVE, "estate", "Steward 1.0", "trade_tasks.py")
GOLDEN = os.path.join(ATLAS, "tests", "fixtures", "town_vectors.json")

# Mid-month noon local: the month key cannot wobble across timezones.
NOW = time.mktime(time.strptime("2026-09-15T12:00:00", "%Y-%m-%dT%H:%M:%S"))
NEXT_MONTH = time.mktime(time.strptime("2026-10-15T12:00:00", "%Y-%m-%dT%H:%M:%S"))

WO_ROWS = [
    (1, "Alpha House", "leaking valve", "Dale", "open"),
    (2, "Alpha House", "finished job", "Dale", "done"),
]
PROPS = ["Alpha House", "Beta House"]
# Alpha visited long ago (overdue at NOW); Beta never visited.
INSPECTIONS = [{"ts": "2026-01-15T10:00:00", "property": "Alpha House"}]


def load_oracle():
    spec = importlib.util.spec_from_file_location("trade_tasks_oracle", TRADE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def oracle_sha():
    h = hashlib_sha256()
    with open(TRADE, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hashlib_sha256():
    import hashlib
    return hashlib.sha256()


def build_sqlite_ops(ops):
    con = sqlite3.connect(os.path.join(ops, "workorders.db"))
    con.execute("CREATE TABLE IF NOT EXISTS wo (id INTEGER PRIMARY KEY, "
                "property TEXT, issue TEXT, vendor TEXT, "
                "status TEXT, cost REAL, opened TEXT, closed TEXT)")
    for wid, prop, issue, vendor, status in WO_ROWS:
        con.execute("INSERT INTO wo (id,property,issue,vendor,status) "
                    "VALUES (?,?,?,?,?)", (wid, prop, issue, vendor, status))
    con.commit()
    con.close()
    with open(os.path.join(ops, "properties.jsonl"), "w",
              encoding="utf-8") as f:
        for p in PROPS:
            f.write(json.dumps({"name": p}) + "\n")
    with open(os.path.join(ops, "inspections.jsonl"), "w",
              encoding="utf-8") as f:
        for e in INSPECTIONS:
            f.write(json.dumps(e) + "\n")


def jsonl_mirror():
    """The equivalent JSONL ground the Go port reads (same logical facts)."""
    return {
        "workorders": [
            {"id": wid, "property": prop, "issue": issue,
             "vendor": vendor, "status": status}
            for wid, prop, issue, vendor, status in WO_ROWS],
        "properties": [{"name": p} for p in PROPS],
        "inspections": list(INSPECTIONS),
    }


def build(T):
    tmp = tempfile.mkdtemp(prefix="town_vectors_")
    try:
        ops = os.path.join(tmp, "ops")
        os.makedirs(ops)
        build_sqlite_ops(ops)
        draft = T.candidates(ops, frozenset(), NOW)
        keys = [k for k, _ in draft]
        dedup = T.candidates(ops, frozenset(keys), NOW)
        recur = T.candidates(ops, frozenset(), NEXT_MONTH)
        # Closed ground: everything done, everything freshly visited.
        ops2 = os.path.join(tmp, "ops2")
        os.makedirs(ops2)
        con = sqlite3.connect(os.path.join(ops2, "workorders.db"))
        con.execute("CREATE TABLE wo (id INTEGER PRIMARY KEY, property TEXT,"
                    " issue TEXT, vendor TEXT, status TEXT, cost REAL,"
                    " opened TEXT, closed TEXT)")
        con.execute("INSERT INTO wo (id,property,issue,vendor,status) VALUES "
                    "(1,'Alpha House','old job','Dale','done')")
        con.commit()
        con.close()
        fresh_ts = time.strftime("%Y-%m-%dT%H:%M:%S",
                                 time.localtime(NOW - 86400))
        with open(os.path.join(ops2, "properties.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps({"name": "Alpha House"}) + "\n")
        with open(os.path.join(ops2, "inspections.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps({"ts": fresh_ts,
                                "property": "Alpha House"}) + "\n")
        quiet = T.candidates(ops2, frozenset(), NOW)
        vecs = [
            {"id": "draft", "expect": "open WO + overdue patrols decided",
             "ok": [k for k, _ in draft] == [
                 "trade:wo:1", "trade:patrol:alpha-house:2026-09",
                 "trade:patrol:beta-house:2026-09"],
             "detail": "; ".join(k for k, _ in draft),
             "decisions": [[k, t] for k, t in draft]},
            {"id": "dedup", "expect": "history silences re-draft",
             "ok": dedup == [], "detail": "%d re-drafted" % len(dedup)},
            {"id": "recur", "expect": "next month re-keys patrols only",
             "ok": [k for k, _ in recur] == [
                 "trade:wo:1", "trade:patrol:alpha-house:2026-10",
                 "trade:patrol:beta-house:2026-10"],
             "detail": "; ".join(k for k, _ in recur),
             "decisions": [[k, t] for k, t in recur]},
            {"id": "closed", "expect": "quiet ground drafts nothing",
             "ok": quiet == [], "detail": "%d drafted" % len(quiet)},
        ]
        return vecs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def payload():
    T = load_oracle()
    return {"spec": "D1 Town (trade_tasks candidates)",
            "oracle": {"file": "estate/Steward 1.0/trade_tasks.py",
                       "sha256": oracle_sha()},
            "now": "2026-09-15T12:00:00 local",
            "inputs": {"workorders": WO_ROWS, "properties": PROPS,
                       "inspections": INSPECTIONS,
                       "mirror": jsonl_mirror()},
            "vectors": build(T)}


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    p = payload()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print("cut %d town vectors -> %s" % (len(p["vectors"]), GOLDEN))
    print("  oracle sha256 %s" % p["oracle"]["sha256"])
    for v in p["vectors"]:
        print("  [%s] %-8s %s" % ("ok" if v["ok"] else "BAD", v["id"],
                                  v["detail"]))


def verify():
    p = payload()
    pinned = json.load(open(GOLDEN, encoding="utf-8"))
    width = max(len(v["id"]) for v in p["vectors"])
    print("\n  TOWN -- golden vectors (D1, hermetic, local oracle)")
    print("    oracle estate/Steward 1.0/trade_tasks.py sha256 %s"
          % p["oracle"]["sha256"])
    ok = True
    if pinned["oracle"]["sha256"] != p["oracle"]["sha256"]:
        print("    [FAIL]  oracle drifted: golden pins %s"
              % pinned["oracle"]["sha256"])
        ok = False
    for v, pv in zip(p["vectors"], pinned["vectors"]):
        match = bool(v["ok"]) and v.get("decisions") == pv.get("decisions")
        status = "PASS" if match else "FAIL"
        ok = ok and match
        print("    [%s]  %-*s  %s" % (status, width, v["id"], v["detail"]))
    print()
    if ok:
        print("  PROVEN. The oracle decides what the port must decide.")
        return 0
    print("  A vector failed. The town's draft is not what the oracle drafts.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
