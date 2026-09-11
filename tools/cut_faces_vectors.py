#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_faces_vectors.py -- C1 Faces golden vectors (spec-first).

Pins the read-only oracle facts C1 must match AND builds a deterministic
golden mesh ground + its expected bridge snapshot:

  faces_vectors.json  oracle pins: console.html + sprites.js (sha256/size),
                      face singularity (one entry point, STOP law).
  faces_ground/       fixed-key, fixed-ts mesh ground (members/chains/head/
                      ledger) built with the oracle's own jesster.sign --
                      the Go mesh walker must verify it (cross-impl).
  faces_snapshot.json the exact bridge snapshot bytes for faces_ground/
                      (sorted keys, indent 2) -- bridge.ts must reproduce
                      them byte-for-byte.

Deterministic: fixed privs/msgs/ts, no wall clock, no network. `--verify`
rebuilds in memory and compares; run bare to (re)cut. Hermetic by law.
"""

import hashlib
import importlib.util
import json
import os
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
CONSOLE = os.path.join(ARCHIVE, "estate", "Aurora", "aurora", "console.html")
SPRITES = os.path.join(ARCHIVE, "estate", "Aurora", "game", "sprites.js")
JESSTER = os.path.join(ARCHIVE, "estate", "forge", "links", "jesster.py")
FIX = os.path.join(ATLAS, "tests", "fixtures")
GROUND = os.path.join(FIX, "faces_ground")
VECTORS = os.path.join(FIX, "faces_vectors.json")
SNAPSHOT = os.path.join(FIX, "faces_snapshot.json")

GENESIS = "0" * 64
BODY_KEYS = ("ts", "kind", "payload", "prev", "actor")


def load_jesster():
    spec = importlib.util.spec_from_file_location("jesster_faces", JESSTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(body):
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def entry_hash(prev, entry):
    body = {k: entry[k] for k in BODY_KEYS if k in entry}
    return hashlib.sha256((prev + canon(body)).encode("utf-8")).hexdigest()


def build_ground(J):
    """Fixed voices, fixed words, fixed clock. Nothing random, nothing live."""
    def keyed(priv):
        pub = J._ser(J._mul(priv, J._G))
        return {"priv": priv, "pub": pub.hex(), "mark": J.mark(pub)}

    members = {"alice": keyed(101), "bob": keyed(102)}
    chains = {"alice": [], "bob": []}
    heads = []

    def post(actor, to, text, cites, n_ts):
        prev = chains[actor][-1]["hash"] if chains[actor] else GENESIS
        e = {"ts": "2026-09-03T00:00:%02dZ" % n_ts, "kind": "mesh",
             "payload": {"n": len(chains[actor]) + 1, "chan": "golden",
                         "to": to, "ct": text, "mode": "open",
                         "cites": list(cites),
                         "mark": members[actor]["mark"]},
             "prev": prev, "actor": actor}
        e["hash"] = entry_hash(prev, e)
        e["sig"] = J.sign(members[actor]["priv"], e["hash"]).hex()
        e["pub"] = members[actor]["pub"]
        chains[actor].append(e)
        hp = heads[-1]["hash"] if heads else GENESIS
        h = {"ts": "2026-09-03T00:01:%02dZ" % len(heads), "kind": "head",
             "payload": {"n": len(heads) + 1, "chan": "golden",
                         "to": "@channel",
                         "ct": "head %d: %s n=%d %s"
                               % (len(heads) + 1, actor,
                                  e["payload"]["n"], e["hash"][:16]),
                         "mode": "open", "cites": [e["hash"]],
                         "mark": members[actor]["mark"]},
             "prev": hp, "actor": actor}
        h["hash"] = entry_hash(hp, h)
        h["sig"] = J.sign(members[actor]["priv"], h["hash"]).hex()
        h["pub"] = members[actor]["pub"]
        heads.append(h)
        return e

    first = post("alice", "bob", "the face shows the record", [], 0)
    post("alice", "@channel", "the second stands on the first",
         [first["hash"]], 1)
    post("bob", "alice", "seen", [], 2)
    return members, chains, heads


def snapshot_of(members, chains, heads):
    mem = [{"actor": a, "mark": members[a]["mark"],
            "entries": len(chains[a])} for a in sorted(members)]
    ch = {a: {"entries": len(chains[a]),
              "head": chains[a][-1]["hash"] if chains[a] else GENESIS}
          for a in sorted(chains)}
    return {"ground": "faces-golden", "members": mem, "chains": ch,
            "head": {"entries": len(heads),
                     "head": heads[-1]["hash"] if heads else GENESIS}}


def snap_json(snapshot):
    return json.dumps(snapshot, sort_keys=True, indent=2,
                      ensure_ascii=False) + "\n"


def oracle_vectors():
    console = {"file": "estate/Aurora/aurora/console.html",
               "sha256": sha_of(CONSOLE),
               "bytes": os.path.getsize(CONSOLE)}
    sprites = {"file": "estate/Aurora/game/sprites.js",
               "sha256": sha_of(SPRITES),
               "bytes": os.path.getsize(SPRITES)}
    aurora_dir = os.path.dirname(CONSOLE)
    html_entry_points = sorted(
        f for f in os.listdir(aurora_dir) if f.endswith(".html"))
    return [
        {"id": "face-bytes", "expect": "vendored console.html byte-identical",
         "ok": console["bytes"] > 0, "detail": console},
        {"id": "sprites-bytes", "expect": "vendored sprites.js byte-identical",
         "ok": sprites["bytes"] > 0, "detail": sprites},
        {"id": "face-singularity",
         "expect": "one entry point (STOP law: no second face)",
         "ok": html_entry_points == ["console.html"],
         "detail": {"entry_points": html_entry_points}},
    ]


def write_bytes(path, data):
    """Golden files are bytes: LF always, on every OS (text mode would
    smuggle CRLF on Windows and poison byte-parity)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    J = load_jesster()
    members, chains, heads = build_ground(J)
    os.makedirs(os.path.join(GROUND, "chains"), exist_ok=True)
    write_bytes(os.path.join(GROUND, "members.json"),
                json.dumps({a: {"pub": members[a]["pub"],
                                "mark": members[a]["mark"]}
                            for a in sorted(members)}, indent=2) + "\n")
    for a, entries in chains.items():
        write_bytes(os.path.join(GROUND, "chains", a + ".jsonl"),
                    "".join(json.dumps(e, ensure_ascii=False) + "\n"
                            for e in entries))
    write_bytes(os.path.join(GROUND, "head.jsonl"),
                "".join(json.dumps(h, ensure_ascii=False) + "\n"
                        for h in heads))
    write_bytes(os.path.join(GROUND, "ledger.jsonl"), "")
    snap = snapshot_of(members, chains, heads)
    write_bytes(SNAPSHOT, snap_json(snap))
    vecs = oracle_vectors()
    write_bytes(VECTORS, json.dumps({"spec": "C1 Faces", "vectors": vecs,
                                     "snapshot": "faces_snapshot.json",
                                     "ground": "faces_ground/"}, indent=2))
    print("cut faces ground: %d members, %d+%d entries, %d head" %
          (len(members), len(chains["alice"]), len(chains["bob"]),
           len(heads)))
    print("cut %s + %s" % (SNAPSHOT, VECTORS))
    for v in vecs:
        print("  [%s] %-16s %s" % ("ok" if v["ok"] else "BAD", v["id"],
                                   v["expect"]))


def verify():
    J = load_jesster()
    ok = True
    print("\n  FACES -- golden vectors (C1, hermetic, local oracle)")
    for v in oracle_vectors():
        print("    [%s]  %-16s  %s" % ("PASS" if v["ok"] else "FAIL",
                                       v["id"], v["expect"]))
        ok = ok and v["ok"]
        if v["id"] == "face-bytes":
            print("           console.html sha256 %s (%d bytes)"
                  % (v["detail"]["sha256"], v["detail"]["bytes"]))
        if v["id"] == "sprites-bytes":
            print("           sprites.js sha256 %s (%d bytes)"
                  % (v["detail"]["sha256"], v["detail"]["bytes"]))
    members, chains, heads = build_ground(J)
    want = snap_json(snapshot_of(members, chains, heads))
    have = open(SNAPSHOT, encoding="utf-8").read()
    match = want == have
    print("    [%s]  %-16s  golden snapshot byte-identical"
          % ("PASS" if match else "FAIL", "snapshot-bytes"))
    ok = ok and match
    # The cut ground on disk must equal a fresh deterministic build.
    for a, entries in chains.items():
        disk = [json.loads(l) for l in
                open(os.path.join(GROUND, "chains", a + ".jsonl"),
                     encoding="utf-8") if l.strip()]
        same = disk == entries
        print("    [%s]  %-16s  %s chain matches fresh build (%d entries)"
              % ("PASS" if same else "FAIL", "ground-" + a, a, len(entries)))
        ok = ok and same
    print()
    if ok:
        print("  PROVEN. The face and the fold have their oracle bytes.")
        return 0
    print("  A vector failed. C1 is not yet what it claims.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
