#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_predict_vectors.py -- E1-03 predictor goldens (spec-first).

Fixes weights (seeded RNG: 64-dim unit places + 64x64 W + synthetic calib),
then pins the oracle's own consult answers: expect() neighbors (word +
round-4 score) per query and surprise() outputs per text. The C++ port must
answer identically; the bench must answer them ≥10x faster.

The oracle's expect() is a bound method needing a speaking library; the
cutter builds a bare instance (__new__), injects weights/calib/places, and
stubs _speakable to (True, "") — the MATH under test is untouched, only the
library standing (which E1 does not port) is bypassed. Deterministic: fixed
seeds, fixed queries. No network. `--verify` recomputes; run bare to (re)cut.
Hermetic by law.
"""

import importlib.util
import json
import math
import os
import random
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
# THE ORACLE ROOT IS NAMEABLE. ADR-006 item 6, 2026-09-11.
#
# This was `ATLAS.parent` outright. Before the 2026-09-10 split atlas sat
# beside its source grounds, so the parent WAS the ground holding the oracle.
# After the split the parent is the manjuel core, and this resolves to a path
# that has never existed on any machine — so `tests/prove.py` reported the
# re-cut legs ABSENT naming a phantom. ABSENT was the right verdict for the
# wrong reason.
#
# The goldens themselves ARE committed and DO travel; only the RE-CUT needs
# the oracle. Set ATLAS_ORACLE_ROOT to the ground that holds it. Unset, the
# old location is still tried, so nothing that worked stops working.
ARCHIVE = os.environ.get("ATLAS_ORACLE_ROOT") or os.path.normpath(os.path.join(ATLAS, ".."))
NEIRO = os.path.join(ARCHIVE, "estate", "Neiro", "Archive", "neiro")
GOLDEN = os.path.join(ATLAS, "tests", "fixtures", "predict_vectors.json")

ORDER = ["rain", "river", "delta", "sea", "seed", "stalk", "grain", "bread",
         "valve", "gate", "water", "morning", "dust", "hinge", "cooler",
         "filter", "pressure", "drain", "javelina", "marco", "dale", "sedona",
         "loop", "ridge", "casita", "rock", "red", "juniper", "night",
         "holds", "mends", "runs", "watches", "settles", "coats", "loosened",
         "bent", "ordered", "replaced", "logged"]
assert len(ORDER) == 40

QUERIES = [["rain", "river"],
           ["the", "valve", "leaks"],
           ["xyzzy", "unknown", "words"],
           ["seed"],
           ["morning", "water", "gate", "hinge", "extra", "words"]]
SURPRISE_TEXTS = ["the valve leaks at night",
                  "xyzzy qqq zzz river",
                  "seed stalk grain bread seed stalk"]
CALIB = {"bands": [{"n": 100, "mean": 0.4, "std": 0.1},
                   {"n": 100, "mean": 0.5, "std": 0.12},
                   {"n": 0, "mean": None, "std": 0.0},
                   {"n": 50, "mean": 0.45, "std": 0.09}],
         "z_floor": 0.01}


def load():
    spec = importlib.util.spec_from_file_location(
        "predict_oracle", os.path.join(NEIRO, "predictor.py"))
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


def unit(rng):
    v = [rng.uniform(-1.0, 1.0) for _ in range(64)]
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def build_weights():
    rng = random.Random(99)
    places = [unit(rng) for _ in ORDER]
    wrng = random.Random(100)
    W = [[wrng.uniform(-1.0, 1.0) for _ in range(64)] for _ in range(64)]
    return places, W


def consultor(P, places, W):
    pred = P.Predictor.__new__(P.Predictor)
    pred._weights = {"w": W}
    pred._calib = CALIB
    pred._places = (list(ORDER), places)
    pred._speakable = lambda: (True, "")
    return pred


def payload():
    P = load()
    places, W = build_weights()
    pred = consultor(P, places, W)
    expects = []
    for q in QUERIES:
        r = pred.expect(q, k=8)
        assert r["refused"] is None, r
        expects.append({"query": q,
                        "neighbors": [[w, s] for w, s in r["neighbors"]]})
    surprises = []
    for t in SURPRISE_TEXTS:
        o = pred.surprise(t)
        # Tuples do not survive JSON: pin lists (order preserved).
        o = {k: ([list(p) if isinstance(p, tuple) else p for p in v]
                 if isinstance(v, list) else v)
             for k, v in o.items()}
        surprises.append({"text": t, "out": o})
    return {
        "spec": "E1-03 predictor consult (expect + surprise)",
        "oracle": {"file": "neiro/predictor.py",
                   "sha256": sha_of(os.path.join(NEIRO, "predictor.py"))},
        "order": ORDER,
        "places_hex": [[x.hex() for x in v] for v in places],
        "W_hex": [[x.hex() for x in row] for row in W],
        "calib": CALIB,
        "expects": expects,
        "surprises": surprises,
    }


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    p = payload()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print("cut predict vectors -> %s" % GOLDEN)
    for e in p["expects"]:
        print("  expect %-28s -> %s" %
              (" ".join(e["query"]),
               ", ".join("%s:%.4f" % (w, s) for w, s in e["neighbors"][:3])))


def verify():
    p = payload()
    pinned = json.loads(open(GOLDEN, encoding="utf-8").read())
    print("\n  PREDICT -- golden vectors (E1-03, hermetic, local oracle)")
    ok = True
    if pinned["oracle"] != p["oracle"]:
        print("    [FAIL]  oracle drifted")
        ok = False
    else:
        print("    [PASS]  oracle pin holds (predictor.py)")
    same = (p["expects"] == pinned["expects"]
            and p["surprises"] == pinned["surprises"])
    print("    [%s]  %d expects + %d surprises identical"
          % ("PASS" if same else "FAIL",
             len(p["expects"]), len(p["surprises"])))
    ok = ok and same
    print()
    if ok:
        print("  PROVEN. The oracle answers what the kernels must answer.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
