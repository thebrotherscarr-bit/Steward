#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_digest_vectors.py -- E1-02 digest golden vectors (spec-first).

Plants a sample catalog with the oracle's own planter, runs the oracle's
meal pipeline (meals -> marks -> counts -> vocab -> single-shard count ->
project), and lays the meal links + closing with the LIVE pen (links.py,
read-only load) on a temp chain. Pins: meal marks, vocab, vectors, prune
events (forced-capos variant), link records, chain INTACT + head.

Two param sets: SMALL (prune dormant) and CAPFORCED (pair_cap tiny so the
prune rule engages and is recorded — the C++ port must reproduce the
events exactly: the rule is integer-deterministic).

Deterministic: fixed planter, fixed params, no wall clock in decisions
(link ts differ run to run — records/hashes-of-content pinned, ts not).
No network. `--verify` rebuilds temp-only and compares; run bare to (re)cut.
Hermetic by law.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
ARCHIVE = os.path.normpath(os.path.join(ATLAS, ".."))
NEIRO = os.path.join(ARCHIVE, "estate", "Neiro", "Archive", "neiro")
PEN_GROUND = os.path.join(ARCHIVE, "estate", "forge", "links")
GOLDEN = os.path.join(ATLAS, "tests", "fixtures", "digest_vectors.json")
CATALOG_FIX = os.path.join(ATLAS, "tests", "fixtures", "digest_catalog.jsonl")

SMALL = {"meal_rows": 50, "vocab_size": 500, "min_count": 2, "dim": 64,
         "window": 4, "workers": 1, "shards": 1, "ctx_stop": 0,
         "pair_cap": 3000000, "prune_every": 20000}
CAPFORCED = dict(SMALL, pair_cap=20, prune_every=5)


def load(name):
    spec = importlib.util.spec_from_file_location(
        "digest_oracle_" + name, os.path.join(NEIRO, name + ".py"))
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


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def run_diet(D, P, catalog, chain_path, do_links=True):
    """The oracle's pipeline, single-shard, on temp ground. Returns the
    pinned diet dict."""
    meals = []
    counts = {}
    docs = tokens = 0
    chain = None
    pen = None
    if do_links:
        pen = D._pen(PEN_GROUND)
        assert pen is not None, "live pen missing"
        chain = pen.Chain(chain_path)
    for seq, meal in D._meals(catalog, P["meal_rows"]):
        note, stats, ntok, delta = D._meal_marks(meal)
        for w, c in delta.items():
            counts[w] = counts.get(w, 0) + c
        first = docs + 1
        docs += len(meal)
        tokens += ntok
        record = {"seq": seq, "rows": [first, docs], "meal_note": note,
                  "stats_mark": stats, "tokens": ntok}
        if do_links:
            chain.deposit(json.dumps(record, separators=(",", ":")),
                          pen.OPEN,
                          "meal %d - rows %d to %d eaten, %d tokens"
                          % (seq, first, docs, ntok),
                          "neiro", cites=[D.COVENANT])
        meals.append({"seq": seq, "rows": [first, docs], "meal_note": note,
                      "stats_mark": stats, "tokens": ntok,
                      "delta": [list(kv) for kv in sorted(delta.items())]})
    order = sorted(((w, c) for w, c in counts.items()
                    if c >= P["min_count"]),
                   key=lambda wc: (-wc[1], wc[0]))[:P["vocab_size"]]
    words = [w for w, _ in order]
    vcounts = {w: c for w, c in order}
    tot = float(sum(vcounts.values()))
    # Single shard, in-process (workers=1 path, no multiprocessing).
    vindex = {w: i for i, w in enumerate(words)}
    tmpd = tempfile.mkdtemp(prefix="digest_ids_")
    try:
        ids_path = os.path.join(tmpd, "ids.bin")
        D._write_ids(catalog, vindex, ids_path)
        pairs, total, events = D._count_shard(ids_path, len(words), 0, 1, P)
        vecs = D._project_shard(pairs, words, vcounts, tot, total, P["dim"])
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
    diet_head = chain.head() if chain else None
    return {"meals": meals, "docs": docs, "tokens": tokens,
            "vocab": words, "counts": vcounts, "total_pairs": total,
            "prunes": events, "vectors": vecs, "diet_head": diet_head}


def payload():
    D = load("digest")
    P = load("predictor")
    tmp = tempfile.mkdtemp(prefix="digest_vectors_")
    try:
        catalog = os.path.join(tmp, "catalog.jsonl")
        P._plant_catalog(catalog, rows=60, undated=6)
        small = run_diet(D, SMALL, catalog,
                         os.path.join(tmp, "chain_small.jsonl"))
        capped = run_diet(D, CAPFORCED, catalog,
                          os.path.join(tmp, "chain_capped.jsonl"),
                          do_links=False)
        # Chain verdict for the linked run (oracle's own walker).
        pen = D._pen(PEN_GROUND)
        chain = pen.Chain(os.path.join(tmp, "chain_small.jsonl"))
        # Re-open read path: Chain(path) loads existing head.
        ok, nlinks, detail = chain.verify()
        head = chain.head()
        entries = []
        for line in open(os.path.join(tmp, "chain_small.jsonl"),
                         encoding="utf-8"):
            if line.strip():
                entries.append(json.loads(line))
        return {
            "spec": "E1-02 digest (meals + single-shard fold + pen links)",
            "oracles": {"digest.py": sha_of(os.path.join(NEIRO, "digest.py")),
                        "links.py": sha_of(os.path.join(PEN_GROUND, "links.py")),
                        "predictor.py (_plant_catalog)":
                            sha_of(os.path.join(NEIRO, "predictor.py"))},
            "params_small": SMALL,
            "params_capped": CAPFORCED,
            "catalog": {"rows": 60, "undated": 6, "planter": "_plant_catalog"},
            "small": small,
            "capped": {k: capped[k] for k in
                       ["docs", "tokens", "vocab", "total_pairs", "prunes"]},
            "capped_vectors": capped["vectors"],
            "chain": {"verdict": ok, "links": nlinks, "detail": detail,
                      "head": head,
                      "records": [
                          {"kind": e["kind"], "actor": e["actor"],
                           "says": e["payload"].get("says"),
                           "doc": e["payload"].get("doc"),
                           "cites": e["payload"].get("cites", [])}
                          for e in entries]},
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cut():
    p = payload()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    # The planted sample catalog, committed: prove.cpp folds these same
    # bytes (LF, like the planter writes).
    tmp = tempfile.mkdtemp(prefix="digest_catalog_")
    try:
        P = load("predictor")
        cat = os.path.join(tmp, "catalog.jsonl")
        P._plant_catalog(cat, rows=60, undated=6)
        with open(cat, "rb") as f:
            write_bytes(CATALOG_FIX, f.read())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("cut digest vectors -> %s" % GOLDEN)
    print("  meals=%d docs=%d vocab=%d prunes=%d chain=%s(%d links)" % (
        len(p["small"]["meals"]), p["small"]["docs"],
        len(p["small"]["vocab"]), len(p["capped"]["prunes"]),
        p["chain"]["verdict"], p["chain"]["links"]))


def verify():
    p = payload()
    pinned = json.loads(open(GOLDEN, encoding="utf-8").read())
    print("\n  DIGEST -- golden vectors (E1-02, hermetic, local oracle)")
    ok = True
    if pinned["oracles"] != p["oracles"]:
        print("    [FAIL]  oracle drifted")
        ok = False
    else:
        print("    [PASS]  oracle pins hold (digest/links/planter)")
    for key in ["meals", "docs", "tokens", "vocab", "counts",
                "total_pairs", "prunes", "vectors"]:
        same = p["small"][key] == pinned["small"][key]
        ok = ok and same
        print("    [%s]  %-12s" % ("PASS" if same else "FAIL", key))
    for key in ["docs", "tokens", "vocab", "total_pairs", "prunes"]:
        same = p["capped"][key] == pinned["capped"][key]
        ok = ok and same
        print("    [%s]  capped-%-8s" % ("PASS" if same else "FAIL", key))
    same = p["capped_vectors"] == pinned["capped_vectors"]
    ok = ok and same
    print("    [%s]  capped-vectors" % ("PASS" if same else "FAIL",))
    same = (p["chain"]["verdict"] is True
            and p["chain"]["links"] == pinned["chain"]["links"]
            and p["chain"]["records"] == pinned["chain"]["records"])
    ok = ok and same
    print("    [%s]  chain INTACT, %d links, records match"
          % ("PASS" if same else "FAIL", p["chain"]["links"]))
    # The committed sample catalog must equal a fresh planting.
    tmp = tempfile.mkdtemp(prefix="digest_catcheck_")
    try:
        P = load("predictor")
        cat = os.path.join(tmp, "catalog.jsonl")
        P._plant_catalog(cat, rows=60, undated=6)
        with open(cat, "rb") as f:
            fresh = f.read()
        with open(CATALOG_FIX, "rb") as f:
            pinned_cat = f.read()
        same = fresh == pinned_cat
        ok = ok and same
        print("    [%s]  catalog fixture matches fresh planting"
              % ("PASS" if same else "FAIL",))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if ok:
        print("  PROVEN. The meals fold what the kernels must fold.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
