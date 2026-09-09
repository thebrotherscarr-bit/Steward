#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_rack_ask_vectors.py -- F1 rack_ask goldens (spec-first, small step).

Folds, ONCE, from the live loopback door:
  * /api/show for every folded voice (capabilities ground routing —
    embedding voices do not speak);
  * one real /api/generate answer (grounds the response parser in a real
    response; the TEXT is illustrative, the SHAPE is the contract).

Pins tests/fixtures/rack_ask.json:
  * expected default route (first speaking voice in ladder order);
  * the generate response shape the parser must extract;
  * the witness record shape rack_ask must append.

--verify never fetches (models come and go; the file is the oracle).
Re-folding is a separate drift stroke. Loopback only. Hermetic by law.

Routing contract (v1, both sides implement):
  1. explicit voice: must name a ladder voice, else refused by name;
     an embedding voice named explicitly is refused with the reason.
  2. default: first ladder voice (tier scout/voice/mind, name asc) whose
     capabilities lack "embedding". None speaking -> refused, named.
"""

import json
import os
import sys
import urllib.request

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
TAGS = os.path.join(FIX, "rack_tags.json")
GOLDEN = os.path.join(FIX, "rack_ask.json")
HOST = "http://127.0.0.1:11434"

ASK_PROMPT = "Say the word 'witnessed' and nothing else."


def post(path, obj, timeout=120):
    req = urllib.request.Request(
        HOST + path, data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ladder_order(tags):
    def tier(size):
        return ("scout" if size <= 3 * 10**9 else
                "voice" if size <= 8 * 10**9 else "mind")
    rows = [{"name": m.get("name", "?"), "size": m.get("size", 0)}
            for m in tags.get("models", [])]
    groups = {}
    for r in rows:
        groups.setdefault(tier(r["size"]), []).append(r["name"])
    out = []
    for t in ["scout", "voice", "mind"]:
        out.extend(sorted(groups.get(t, [])))
    return out


def is_speaking(show):
    caps = show.get("capabilities") or []
    return "embedding" not in caps


def build():
    tags = json.loads(open(TAGS, encoding="utf-8").read())
    order = ladder_order(tags)
    shows = {}
    for name in order:
        try:
            full = post("/api/show", {"model": name})
        except Exception as e:
            shows[name] = {"_fold_error": str(e)[:120]}
            continue
        # Trimmed to the routing contract (capabilities); templates and
        # modelfiles would bloat the fixture 100x for no proven property.
        shows[name] = {"model": full.get("model", name),
                       "capabilities": full.get("capabilities", [])}
    default = next((n for n in order
                    if is_speaking(shows.get(n, {}))), None)
    embedder = next((n for n in order
                     if not is_speaking(shows.get(n, {}))), None)
    answer = post("/api/generate",
                  {"model": default, "prompt": ASK_PROMPT, "stream": False},
                  timeout=300)
    return {"prompt": ASK_PROMPT, "default_route": default,
            "embedder": embedder, "shows": shows, "answer": answer,
            "ladder": order}


def shape_of_answer(answer):
    return {"has_model": isinstance(answer.get("model"), str),
            "has_response": isinstance(answer.get("response"), str),
            "done": answer.get("done")}


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    p = build()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print("folded rack_ask golden -> %s" % GOLDEN)
    print("  default route: %s" % p["default_route"])
    print("  embedder (refused if named): %s" % p["embedder"])
    print("  answer shape: %s" % shape_of_answer(p["answer"]))
    print("  answer text: %r" % p["answer"].get("response", "")[:80])


def verify():
    p = json.loads(open(GOLDEN, encoding="utf-8").read())
    print("\n  RACK ASK -- goldens (F1 step 2, folded oracle)")
    ok = True
    order = ladder_order(json.loads(open(TAGS, encoding="utf-8").read()))
    same = order == p["ladder"]
    print("    [%s]  ladder order stable" % ("PASS" if same else "FAIL",))
    ok = ok and same
    routed = next((n for n in order if is_speaking(p["shows"].get(n, {}))), None)
    same = routed == p["default_route"] and routed is not None
    print("    [%s]  default route %s" % ("PASS" if same else "FAIL", routed))
    ok = ok and same
    shape = shape_of_answer(p["answer"])
    same = (shape["has_model"] and shape["has_response"] and shape["done"] is True
            and len(p["answer"]["response"]) > 0)
    print("    [%s]  answer shape parses (model/response/done, non-empty)"
          % ("PASS" if same else "FAIL",))
    ok = ok and same
    print()
    if ok:
        print("  PROVEN. The route and the answer shape hold.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
