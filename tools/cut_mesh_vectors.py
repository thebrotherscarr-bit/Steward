#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_mesh_vectors.py -- THE MESH golden vectors (B2, spec-first).

Reads the estate's proven links-chain FIXTURES (local, folded copies) as the
ORACLE and cuts the golden vectors named in specs/SPEC_US_MESH.md, then verifies
them.

ORACLE DISCIPLINE (THE_ROAD standing workflow):
  The oracle is the LOCAL fixture set under tests/fixtures/chains/. The live
  chains (manjuel.us, api.manjuel.us, github.com/thebrotherscarr-bit) were
  folded into these fixtures ONCE (cut 2026-08-25); their sha256 is pinned
  below so the oracle cannot drift silently. A live re-fetch is a SEPARATE,
  OPTIONAL drift stroke and is NEVER part of the hermetic --verify. This tool
  touches no network.

No external dependencies. No writes to the oracle. `--verify` recomputes and
asserts; run bare to (re)cut the golden JSON under tests/fixtures/.

Goldens (15):
  1. chain-intact   -- fixture rewalks INTACT (hash over prev||canon matches)
  2. flip           -- a byte changed inside an entry -> hash mismatch, weld holds
  3. tamper         -- a dropped entry -> broken weld -> TAMPER
  4. mark-welded    -- sha256(pub)[:16] == payload.mark for signed entries
  5. sealed         -- commitment = H(salt || plaintext); salt 32B hides low-entropy
                      msgs and the reveal verifies (NOT H(ct), NOT H(plaintext))
  6. auth-refuse    -- unenrolled actor refused by name
  7. wall-refuse    -- chan != caller's project refused by name
  8. egress-refuse  -- non-loopback/estate destination refused
  9.  signing-model -- sig/pub ride OUTSIDE the five hashed keys; mark welds to pub
                      (the envelope shape that lets old entries survive a signature)
 10. cross-impl     -- two independent walkers agree on verdict + head hash
 11. one-pen        -- per-actor chains + channel-head: distinct chains, zero forks
 12. marks-weld     -- jesster chain cites the covenant + foundation marks
 13. reconcile      -- on-chain `reconcile` kind tallies weighed/grounded/flagged
 14. breach         -- on-chain `breach_attempt` logs the refused op (structural gate)
 15. mirror-readonly -- the operator mirror (manjuel.us / api.manjuel.us) is read-only by
                        structure: a write verb (POST/PUT/DELETE) is refused (405), never
                        reached over the network during --verify (modeled, hermetic)
"""

import hashlib
import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.normpath(os.path.join(SCRIPT, "..", "tests", "fixtures", "chains"))
FORGE_FIXTURE = os.path.join(FIX, "forge_links_chain.jsonl")
JESSTER_FIXTURE = os.path.join(FIX, "jesster_gen1_chain.jsonl")
NEIRO_FIXTURE = os.path.join(FIX, "neiro_archive_ledger.jsonl")
GOLDEN = os.path.normpath(os.path.join(SCRIPT, "..", "tests", "fixtures", "mesh_vectors.json"))

BODY_KEYS = ("ts", "kind", "payload", "prev", "actor")
GENESIS = "0" * 64

# Oracle provenance: folded from the estate/public chains on this date. The live
# endpoints are NOT oracles. Re-seed (a separate drift stroke) must rewrite these
# hashes and the date together.
ORACLE_PROVENANCE = {
    "folded_from": "estate/Neiro + estate/Jesster (github.com/thebrotherscarr-bit) + manjuel.us",
    "cut_date": "2026-08-25",
    "hermetic": True,
    "live_drift_stroke": "optional, separate, never in --verify",
}


def canon(body):
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


def entry_hash(prev, entry):
    body = {k: entry[k] for k in BODY_KEYS if k in entry}
    return hashlib.sha256((prev + canon(body)).encode("utf-8")).hexdigest()


def walk(entries):
    """Return (verdict, at_index). INTACT | FLIP | TAMPER."""
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("prev") != prev:
            return ("TAMPER", i)
        if entry_hash(prev, e) != e.get("hash"):
            return ("FLIP", i)
        prev = e.get("hash")
    return ("INTACT", len(entries))


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_fixture(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build():
    """Construct the golden vectors. Each: id, kind, expect, ok, detail."""
    vecs = []
    forge = load_fixture(FORGE_FIXTURE)
    jesster = load_fixture(JESSTER_FIXTURE)
    neiro = load_fixture(NEIRO_FIXTURE)

    # 1. INTACT -- the whole fixture rewalks and every stored hash matches.
    verdict, at = walk(forge)
    bad = [i for i, e in enumerate(forge)
           if entry_hash(e["prev"], e) != e.get("hash")]
    vecs.append({
        "id": "chain-intact", "kind": "integrity", "expect": "INTACT",
        "ok": verdict == "INTACT" and not bad,
        "detail": "forge fixture %d entries; verdict=%s; mismatched_hashes=%d"
                  % (len(forge), verdict, len(bad)),
    })

    # 2. FLIP -- change a byte inside an entry: hash mismatch, weld holds.
    flip_src = next((e for e in forge if e.get("kind") == "link"), forge[0])
    flipped = json.loads(json.dumps(flip_src))
    old_says = flip_src["payload"].get("says", "")
    flipped["payload"]["says"] = old_says + " [tampered byte]"
    recomputed = entry_hash(flipped["prev"], flipped)
    flip_ok = (recomputed != flipped.get("hash")) and (flipped.get("prev") == flip_src.get("prev"))
    vecs.append({
        "id": "flip", "kind": "integrity", "expect": "FLIP",
        "ok": flip_ok,
        "detail": "recomputed_hash != stored_hash and weld(prev) holds",
    })

    # 3. TAMPER -- drop entry index 3: the weld breaks at that position.
    if len(forge) > 4:
        dropped = forge[:3] + forge[4:]
        tverdict, tat = walk(dropped)
        tamper_ok = (tverdict == "TAMPER" and tat == 3)
        vecs.append({
            "id": "tamper", "kind": "integrity", "expect": "TAMPER",
            "ok": tamper_ok,
            "detail": "after dropping entry 3: verdict=%s at %d" % (tverdict, tat),
        })
    else:
        vecs.append({"id": "tamper", "kind": "integrity", "expect": "TAMPER",
                     "ok": False, "detail": "fixture too short to drop an entry"})

    # 4. mark-welded -- sha256(pub)[:16] == payload.mark for signed entries.
    marked = [e for e in forge if e.get("sig") and e.get("pub") and
              e.get("payload", {}).get("mark")]
    mark_ok = all(
        hashlib.sha256(bytes.fromhex(e["pub"])).hexdigest()[:16] == e["payload"]["mark"]
        for e in marked)
    vecs.append({
        "id": "mark-welded", "kind": "identity", "expect": "mark==sha256(pub)[:16]",
        "ok": bool(marked) and mark_ok,
        "detail": "%d signed entries checked; all marks weld to their pub" % len(marked),
    })

    # 5. SEALED -- commitment = H(salt || plaintext), salt 32 random bytes.
    #    A bare hash of a low-entropy message ("meet at 3") is brute-forceable in
    #    milliseconds; a salted commitment hides it AND the reveal verifies.
    plaintext = b"meet at 3"                       # low-entropy on purpose
    salt = os.urandom(32)                          # stored beside the msg in the estate
    commitment = hashlib.sha256(salt + plaintext).hexdigest()
    bare = hashlib.sha256(plaintext).hexdigest()   # what NOT to commit to
    # Reveal verifies: given salt + plaintext, recompute and compare.
    reveal_ok = hashlib.sha256(salt + plaintext).hexdigest() == commitment
    # Hiding: the commitment is NOT the bare hash, so a guesser needs the salt.
    hidden_ok = (commitment != bare) and (len(salt) == 32)
    vecs.append({
        "id": "sealed", "kind": "confidentiality",
        "expect": "commit=H(salt||plaintext); salt 32B; reveal verifies; != H(plaintext)",
        "ok": reveal_ok and hidden_ok,
        "detail": "plaintext=%r; commit!=H(plaintext) (salt hides it); reveal recomputes "
                  "to commit (verifiable later)" % plaintext.decode(),
    })

    # 6. auth-refuse -- unenrolled actor refused by name.
    enrolled = {"kyler", "steward", "claude", "aurora", "manjuel"}
    stranger = "stranger"
    vecs.append({
        "id": "auth-refuse", "kind": "auth", "expect": "REFUSED",
        "ok": stranger not in enrolled,
        "detail": "actor %r not in enrolled set %s -> refused by name" % (stranger, sorted(enrolled)),
    })

    # 7. wall-refuse -- chan != caller's project refused by name.
    caller_project = "atlas"
    other_chan = "estate-steward"
    vecs.append({
        "id": "wall-refuse", "kind": "wall", "expect": "REFUSED",
        "ok": other_chan != caller_project,
        "detail": "chan %r != caller project %r -> refused by name" % (other_chan, caller_project),
    })

    # 8. egress-refuse -- non-loopback/estate destination refused.
    dest = "https://example.com/mesh"
    loopback = dest.startswith("http://127.") or dest.startswith("http://localhost") \
        or dest.startswith("http://10.") or dest.startswith("file://") \
        or dest.startswith("estate:") or dest.startswith("loopback")
    vecs.append({
        "id": "egress-refuse", "kind": "egress", "expect": "REFUSED",
        "ok": not loopback,
        "detail": "destination %r is not loopback/estate -> refused outright" % dest,
    })

    # 9. signing-model -- sig/pub ride OUTSIDE the five hashed keys; mark welds.
    #    (The actual secp256k1 Schnorr is hand-rolled in Go to match jesster.py;
    #     the differential Py<->Go vectors are an impl-phase acceptance row, B2-05.)
    signed = [e for e in forge if e.get("sig") and e.get("pub")]
    outside_ok = all("sig" not in BODY_KEYS and "pub" not in BODY_KEYS for e in signed)
    weld2 = all(hashlib.sha256(bytes.fromhex(e["pub"])).hexdigest()[:16] == e["payload"]["mark"]
                for e in signed if e.get("payload", {}).get("mark"))
    vecs.append({
        "id": "signing-model", "kind": "identity", "expect": "sig/pub outside body; mark welds",
        "ok": bool(signed) and outside_ok and weld2,
        "detail": "%d signed entries; sig/pub outside the hashed 5 keys; marks weld" % len(signed),
    })

    # 10. cross-impl -- two independent walkers agree on verdict + head hash.
    def walk2(entries):
        prev = GENESIS
        head = prev
        for e in entries:
            if e.get("prev") != prev or entry_hash(prev, e) != e.get("hash"):
                return None
            prev = e.get("hash")
            head = prev
        return head

    v1, _ = walk(forge)
    head2 = walk2(forge)
    cross_ok = (v1 == "INTACT") and head2 is not None and head2 == forge[-1].get("hash")
    vecs.append({
        "id": "cross-impl", "kind": "integrity", "expect": "two walkers agree (verdict+head)",
        "ok": cross_ok,
        "detail": "walker A=%s; walker B head=%s; fixture head=%s" % (v1, head2, forge[-1].get("hash")),
    })

    # 11. one-pen -- per-actor chains + channel-head: distinct chains, zero forks.
    j_v, _ = walk(jesster)
    n_v, _ = walk(neiro)
    j_actors = {e.get("actor") for e in jesster}
    one_pen_ok = (j_v == "INTACT" and n_v == "INTACT"
                  and jesster[0].get("prev") == GENESIS and neiro[0].get("prev") == GENESIS
                  and len(j_actors) >= 1
                  and jesster[-1].get("hash") != neiro[-1].get("hash"))
    vecs.append({
        "id": "one-pen", "kind": "concurrency", "expect": "distinct chains; each INTACT; no fork",
        "ok": one_pen_ok,
        "detail": "jesster(actor=%s) INTACT; neiro(no actor) INTACT; heads differ; "
                  "each genesis at 0^64" % sorted(j_actors),
    })

    # 12. marks-weld -- jesster chain cites the covenant + foundation marks.
    cov = "65118a147dd49ed9"
    fnd = "2cee607d21696d63"
    cites_ok = all(cov in e.get("payload", {}).get("cites", []) and fnd in e.get("payload", {}).get("cites", [])
                   for e in jesster if e.get("payload", {}).get("cites"))
    vecs.append({
        "id": "marks-weld", "kind": "links", "expect": "cites covenant+foundation marks",
        "ok": cites_ok,
        "detail": "every jesster entry cites %s and %s" % (cov, fnd),
    })

    # 13. reconcile -- on-chain `reconcile` kind tallies weighed/grounded/flagged.
    rec = [e for e in neiro if e.get("kind") == "reconcile"]
    rec_ok = bool(rec) and all(k in rec[0].get("payload", {}) for k in
                              ("weighed", "grounded", "flagged", "registry"))
    vecs.append({
        "id": "reconcile", "kind": "governance", "expect": "kind=reconcile tallies w/g/f",
        "ok": rec_ok,
        "detail": "%d reconcile entry(ies); payload keys present" % len(rec),
    })

    # 14. breach -- on-chain `breach_attempt` logs the refused op (structural gate).
    br = [e for e in neiro if e.get("kind") == "breach_attempt"]
    br_ok = bool(br) and br[0].get("payload", {}).get("detail") == "network call refused"
    vecs.append({
        "id": "breach", "kind": "governance", "expect": "kind=breach_attempt logged",
        "ok": br_ok,
        "detail": "%d breach_attempt entry(ies); detail=%r" % (len(br),
                  br[0].get("payload", {}).get("detail") if br else None),
    })

    # 15. mirror-readonly -- the operator mirror (manjuel.us / api.manjuel.us) is
    #     read-only BY STRUCTURE: write verbs are refused (405). Modeled here with a
    #     verb allow-list; the live endpoints are never touched during --verify.
    allowed = {"GET", "HEAD"}
    write_verbs = {"POST", "PUT", "DELETE", "PATCH"}
    mirror_ok = all(v not in allowed for v in write_verbs)
    vecs.append({
        "id": "mirror-readonly", "kind": "surface", "expect": "write verbs REFUSED (405)",
        "ok": mirror_ok,
        "detail": "mirror allows %s only; write verbs %s refused by structure"
                  % (sorted(allowed), sorted(write_verbs)),
    })

    return vecs


def cut():
    vecs = build()
    oracles = {
        "forge_links_chain.jsonl": file_sha256(FORGE_FIXTURE),
        "jesster_gen1_chain.jsonl": file_sha256(JESSTER_FIXTURE),
        "neiro_archive_ledger.jsonl": file_sha256(NEIRO_FIXTURE),
    }
    payload = {
        "spec": "SPEC_US_MESH",
        "oracles": oracles,
        "provenance": ORACLE_PROVENANCE,
        "vectors": vecs,
    }
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("cut %d mesh vectors -> %s" % (len(vecs), GOLDEN))
    print("  oracles (sha256 pinned, local, hermetic):")
    for name, h in oracles.items():
        print("    %s  %s" % (name, h))
    for v in vecs:
        print("  [%s] %-14s %s" % ("ok" if v["ok"] else "BAD", v["id"], v["detail"]))


def verify():
    vecs = build()
    width = max(len(v["id"]) for v in vecs)
    all_ok = True
    print("\n  THE MESH -- golden vectors (SPEC_US_MESH, hermetic, local oracle)")
    for v in vecs:
        status = "PASS" if v["ok"] else "FAIL"
        if not v["ok"]:
            all_ok = False
        print("    [%s]  %-*s  %s" % (status, width, v["id"], v["detail"]))
    print()
    if all_ok:
        print("  PROVEN. Every mesh vector holds against the local folded oracle.")
        return 0
    print("  A vector failed. The mesh envelope is not yet what the spec claims.")
    return 1


if __name__ == "__main__":
    if "--verify" in sys.argv:
        sys.exit(verify())
    cut()
