#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_rack_plan_vectors.py -- N3 rack_plan goldens (spec-first).

The VRAM planner v1 contract (ported from chain DESIGN section 9 /
SPEC_CONTROL_CENTER section 4.3, arithmetic pinned here as the oracle):

  VRAM_BUDGET      = 15 * 10**9  (CHAINKIT_VRAM_GB=15, RX 6800 XT 16GB - headroom)
  GRAPH_OVERHEAD   = 1_500_000_000 per resident model
  KV_PER_TOKEN     = scout 200_000 / voice 500_000 / mind 1_000_000 bytes
  CTX_DEFAULT      = 4096 tokens
  footprint(size, tier) = size + GRAPH_OVERHEAD + CTX_DEFAULT * KV_PER_TOKEN[tier]
  plan(models) = sum(footprints) vs budget -> FITS | OVER (evict list = largest first)

Tiers reuse the rack v1 contract (scout <=3GB, voice <=8GB, else mind).
The Go rack package must reproduce every vector byte-exact in shape
(verdict + bytes + evictions). --verify never fetches; the fixture file
is the oracle. Sizes are synthetic and fixed -- no live Ollama needed.
"""

import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
PLAN = os.path.join(FIX, "rack_plan.json")

VRAM_BUDGET = 15 * 10**9
GRAPH_OVERHEAD = 1_500_000_000
KV_PER_TOKEN = {"scout": 200_000, "voice": 500_000, "mind": 1_000_000}
CTX_DEFAULT = 4096


def tier_of(size):
    if size <= 3_000_000_000:
        return "scout"
    if size <= 8_000_000_000:
        return "voice"
    return "mind"


def footprint(size):
    tier = tier_of(size)
    return size + GRAPH_OVERHEAD + CTX_DEFAULT * KV_PER_TOKEN[tier]


def plan(models):
    fps = [(m["name"], footprint(m["size"])) for m in models]
    total = sum(f for _, f in fps)
    if total <= VRAM_BUDGET:
        return {"verdict": "FITS", "total": total,
                "budget": VRAM_BUDGET, "evict": []}
    order = sorted(fps, key=lambda x: -x[1])
    freed = 0
    evict = []
    for name, f in order:
        freed += f
        evict.append(name)
        if total - freed <= VRAM_BUDGET:
            break
    return {"verdict": "OVER", "total": total,
            "budget": VRAM_BUDGET, "evict": evict}


def vectors():
    G = 10**9
    cases = [
        ("single-scout-fits", [{"name": "llama3.2:latest", "size": int(2.0 * G)}]),
        ("two-scout-fit", [{"name": "llama3.2:latest", "size": int(2.0 * G)},
                           {"name": "phi4-mini:latest", "size": int(2.5 * G)}]),
        ("voice-fits", [{"name": "qwen3.5:4b", "size": int(3.4 * G)}]),
        ("voice-pair-fits", [{"name": "qwen3.5:4b", "size": int(3.4 * G)},
                             {"name": "qwen3.5:9b", "size": int(6.6 * G)}]),
        ("mind-single-fits", [{"name": "gemma4:12b", "size": int(7.6 * G)}]),
        ("court-over", [{"name": "qwen3.5:9b", "size": int(6.6 * G)},
                        {"name": "gemma4:12b", "size": int(7.6 * G)},
                        {"name": "deepseek-r1:8b", "size": int(5.2 * G)}]),
        ("heavy-pair-over", [{"name": "gemma4:e4b", "size": int(9.6 * G)},
                             {"name": "qwen2.5-coder:14b", "size": int(9.0 * G)}]),
        ("empty-fits", []),
        ("coder-tier", [{"name": "qwen2.5-coder:7b", "size": int(4.7 * G)}]),
        ("embedder-scout", [{"name": "nomic-embed-text-v2-moe", "size": int(958_000_000)}]),
        ("vl-voice", [{"name": "qwen3-vl:8b", "size": int(6.1 * G)}]),
        ("four-scout-over", [{"name": "a", "size": int(2.0 * G)},
                             {"name": "b", "size": int(2.0 * G)},
                             {"name": "c", "size": int(2.0 * G)},
                             {"name": "d", "size": int(2.0 * G)}]),
    ]
    out = {"constants": {"vram_budget": VRAM_BUDGET,
                         "graph_overhead": GRAPH_OVERHEAD,
                         "kv_per_token": KV_PER_TOKEN,
                         "ctx_default": CTX_DEFAULT},
           "vectors": []}
    for name, models in cases:
        p = plan(models)
        out["vectors"].append({"name": name, "models": models,
                               "verdict": p["verdict"], "total": p["total"],
                               "budget": p["budget"], "evict": p["evict"]})
    return out


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    doc = vectors()
    write_bytes(PLAN, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("rack_plan -> %s (%d vectors)" % (PLAN, len(doc["vectors"])))


def verify():
    doc = json.loads(open(PLAN, encoding="utf-8").read())
    want = vectors()
    print("\n  RACK-PLAN -- vram goldens (N3, pinned oracle)")
    if doc == want:
        print("    [PASS]  %d/%d vectors reproduce" % (len(want["vectors"]), len(want["vectors"])))
        print()
        print("  PROVEN. The planner measures before it seats.")
        return 0
    print("    [FAIL]  planner drifted from the pinned fixture")
    for a, b in zip(doc.get("vectors", []), want["vectors"]):
        if a != b:
            print("    drift:", b["name"])
            print("      want:", b)
            print("      got :", a)
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
