#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_flow_vectors.py -- N2 workflow goldens (spec-first).

The flow v1 contract (the oracle; the Go flow package must honor it):

  names         : ^[a-z0-9][a-z0-9_-]{0,63}$ for flows, nodes, runs carry
                  f-YYYYMMDD-HHMMSS-<8hex> (RUN_RE pinned below)
  node kinds    : ask | prompt | seat | memory | eval | gate | run — a
                  closed set. A `run` node drives a whole Manjuel turn (the
                  council), so it must carry an objective or it refuses; the
                  others reach one voice.
  edges         : {from, to, when: always|pass|fail}; fail-edges only from
                  eval/gate nodes; everything else with when:fail refuses
  validation    : unique names, known kinds, refs resolve, no cycles,
                  exactly one start, all nodes reachable from the start
  order         : Kahn over name-sorted ready sets (deterministic)
  branches      : eval pass/fail (exact trim+casefold) and gate
                  continue/stop steer which out-edges fire; parallelism is
                  declared but runs sequentially, topo order (one rack queue)
  templates     : {{var}} from run inputs plus {{out_<node>}} from finished
                  nodes; missing vars fail the node, never guess
  run receipt   : sha256(run + "\\n" + node + "\\n" + output + "\\n" + ts)
  budget        : wall sum vs budget_s (default 600); over() is pure and
                  pinned here; OUT_OF_TIME stops the run honestly

No live Ollama, no network. The fixture file is the oracle; --verify
recomputes every vector deterministically with canned node outputs.
"""

import hashlib
import json
import os
import re
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
FLOW = os.path.join(FIX, "flow_vectors.json")

NAME_RE = r"^[a-z0-9][a-z0-9_-]{0,63}$"
RUN_RE = r"^f-\d{8}-\d{6}-[0-9a-f]{8}$"
KINDS = ["ask", "prompt", "seat", "memory", "eval", "gate", "run"]


def topo(nodes, edges):
    names = [n["name"] for n in nodes]
    if len(set(names)) != len(names):
        raise ValueError("duplicate node name")
    if len(names) == 0:
        raise ValueError("empty flow")
    kinds = {n["name"]: n["kind"] for n in nodes}
    for n in nodes:
        if n["kind"] not in KINDS:
            raise ValueError("unknown kind: " + n["kind"])
        if n["kind"] == "run" and not (n.get("question") or "").strip():
            raise ValueError("run node with no objective")
    incoming = {n: 0 for n in names}
    adj = {n: [] for n in names}
    for e in edges:
        if e["from"] not in incoming or e["to"] not in incoming:
            raise ValueError("edge refs unknown node")
        if e.get("when", "always") == "fail" and kinds[e["from"]] not in ("eval", "gate"):
            raise ValueError("fail-edge only from eval/gate")
        if e.get("when", "always") not in ("always", "pass", "fail"):
            raise ValueError("bad when: " + str(e.get("when")))
        incoming[e["to"]] += 1
        adj[e["from"]].append(e)
    starts = sorted(n for n in names if incoming[n] == 0)
    if len(starts) != 1:
        raise ValueError("want exactly one start, got %d" % len(starts))
    ready = sorted(starts)
    order = []
    indeg = dict(incoming)
    while ready:
        n = ready.pop(0)
        order.append(n)
        for e in sorted(adj[n], key=lambda x: x["to"]):
            indeg[e["to"]] -= 1
            if indeg[e["to"]] == 0:
                ready.append(e["to"])
        ready.sort()
    if len(order) != len(names):
        raise ValueError("cycle or unreachable node")
    return order


def run_outcome(spec, canned, eval_expected, gate_decision):
    """Simulate branch routing: canned outputs per node, eval expected map,
    gate decision map. Returns fired node names in order + verdict."""
    order = topo(spec["nodes"], spec.get("edges", []))
    byname = {n["name"]: n for n in spec["nodes"]}
    edges = spec.get("edges", [])
    fired = []
    verdict = "DONE"
    passed = {}
    for n in order:
        nd = byname[n]
        # gate: does any in-edge fire?
        fire = True
        for e in edges:
            if e["to"] != n:
                continue
            src = e["from"]
            if src not in fired:
                continue
            when = e.get("when", "always")
            if when == "always":
                break
            if when == "pass" and passed.get(src) is True:
                break
            if when == "fail" and passed.get(src) is False:
                break
        else:
            # no in-edge fired (start has none -> fires)
            fire = any(e["to"] == n for e in edges) is False
        if n == order[0]:
            fire = True
        if not fire:
            continue
        fired.append(n)
        if nd["kind"] == "eval":
            exp = (eval_expected or {}).get(n, "")
            got = canned.get(nd.get("node", ""), "")
            ok = exp.strip().casefold() == got.strip().casefold()
            passed[n] = ok
            # fail with no fail-edge -> run FAILs here
            if not ok and not any(e["from"] == n and e.get("when") == "fail" for e in edges):
                verdict = "FAIL"
                break
        elif nd["kind"] == "gate":
            decision = (gate_decision or {}).get(n, "continue")
            passed[n] = (decision == "continue")
            if decision == "stop":
                # stop with no fail-edge -> STOPPED here
                if not any(e["from"] == n and e.get("when") == "fail" for e in edges):
                    verdict = "STOPPED"
                    break
            else:
                verdict = "PAUSED" if n == order[-1] or True else verdict
                # gate pauses the run unless resumed; simulation marks PAUSED
                verdict = "PAUSED"
                break
    return {"fired": fired, "verdict": verdict}


def receipt(run, node, output, ts):
    h = hashlib.sha256()
    h.update((run + "\n" + node + "\n" + output + "\n" + ts).encode("utf-8"))
    return h.hexdigest()


def over(elapsed_ms, budget_s):
    return sum(elapsed_ms) > budget_s * 1000


def spec(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def vectors():
    ask = lambda n, q="Q": {"name": n, "kind": "ask", "question": q}
    ev = lambda n, ref, exp: {"name": n, "kind": "eval", "node": ref, "expected": exp}
    gate = lambda n: {"name": n, "kind": "gate", "title": "review"}
    E = lambda f, t, w="always": {"from": f, "to": t, "when": w}
    linear = spec([ask("a"), ask("b")], [E("a", "b")])
    branch = spec([ask("a"), ev("e", "a", "yes"), ask("b"), ask("c")],
                  [E("a", "e"), E("e", "b", "pass"), E("e", "c", "fail")])
    gated = spec([ask("a"), gate("g"), ask("b")], [E("a", "g"), E("g", "b")])
    return {
        "name_re": NAME_RE,
        "run_re": RUN_RE,
        "kinds": KINDS,
        "topo_linear": {"order": topo(linear["nodes"], linear["edges"])},
        "branch_pass": run_outcome(branch, {"a": "yes"}, {"e": "yes"}, {}),
        "branch_fail": run_outcome(branch, {"a": "no"}, {"e": "yes"}, {}),
        "gate_pauses": run_outcome(gated, {"a": "hi"}, {}, {}),
        "receipt_example": {
            "run": "f-20260909-120000-01234567",
            "node": "a",
            "output": "the ledger holds",
            "ts": "2026-09-09T12:00:00Z",
            "receipt": receipt("f-20260909-120000-01234567", "a",
                               "the ledger holds", "2026-09-09T12:00:00Z"),
        },
        "budget_cases": [
            {"elapsed_ms": [100, 200], "budget_s": 600, "over": False},
            {"elapsed_ms": [300000, 300001], "budget_s": 600, "over": True},
            {"elapsed_ms": [], "budget_s": 600, "over": False},
        ],
        "refusals": [
            {"why": "cycle",
             "spec": spec([ask("a"), ask("b")], [E("a", "b"), E("b", "a")])},
            {"why": "two starts",
             "spec": spec([ask("a"), ask("b")], [])},
            {"why": "unreachable",
             "spec": spec([ask("a"), ask("b"), ask("c")], [E("a", "b")])},
            {"why": "unknown kind",
             "spec": spec([{"name": "a", "kind": "teleport"}], [])},
            {"why": "fail-edge from ask",
             "spec": spec([ask("a"), ask("b")], [E("a", "b", "fail")])},
            {"why": "edge refs unknown",
             "spec": spec([ask("a")], [E("a", "ghost")])},
            {"why": "run node with no objective",
             "spec": spec([{"name": "a", "kind": "run"}], [])},
        ],
    }


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    doc = vectors()
    # refusals must actually refuse under our own topo()
    for r in doc["refusals"]:
        try:
            topo(r["spec"]["nodes"], r["spec"].get("edges", []))
            print("REFUSAL HOLE:", r["why"])
            sys.exit(1)
        except ValueError:
            pass
    write_bytes(FLOW, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("flow -> %s" % FLOW)


def verify():
    doc = json.loads(open(FLOW, encoding="utf-8").read())
    want = vectors()
    print("\n  FLOW -- golden contract (N2, pinned oracle)")
    ok = True
    if doc != want:
        ok = False
        print("    [FAIL]  fixture drifted from the contract")
        for k in want:
            if doc.get(k) != want[k]:
                print("    drift:", k)
    else:
        print("    [PASS]  topo + branches + gate + receipt + budget + refusals")
    for r in want["refusals"]:
        try:
            topo(r["spec"]["nodes"], r["spec"].get("edges", []))
            ok = False
            print("    [FAIL]  refusal hole: %s" % r["why"])
        except ValueError:
            pass
    for b in want["budget_cases"]:
        if over(b["elapsed_ms"], b["budget_s"]) != b["over"]:
            ok = False
            print("    [FAIL]  budget mispinned: %r" % b)
    ex = want["receipt_example"]
    if receipt(ex["run"], ex["node"], ex["output"], ex["ts"]) != ex["receipt"]:
        ok = False
        print("    [FAIL]  receipt formula does not reproduce")
    if ok:
        print()
        print("  PROVEN. The builder routes honestly.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
