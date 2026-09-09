#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_schnorr_vectors.py -- B2-07 differential signing goldens (spec-first).

Reads the estate's `jesster.py` as a READ-ONLY oracle (never the machine
secret, never the network) and cuts deterministic sign/verify vectors for the
hand-rolled Go secp256k1 Schnorr port. The Go side must byte-match these:
sign in Python -> verify in Go, sign in Go -> verify in Python.

Deterministic: fixed private keys + fixed messages, no wall clock, no random.
`--verify` recomputes from the oracle and asserts; run bare to (re)cut the
golden JSON under tests/fixtures/. Hermetic by law: temp ground only for any
scratch, oracle file sha256 pinned so drift is loud, not silent.

Covers (acceptance B2-07, malleability edges included):
  determinism, verify-accept xN, wrong-message refuse, flipped-byte refuse,
  s>=N refuse, bad-length refuse, infinity-pub refuse, off-curve-pub refuse,
  certify round-trip + tampered-cert refuse.
"""

import hashlib
import importlib.util
import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ORACLE = os.path.normpath(os.path.join(
    SCRIPT, "..", "..", "estate", "forge", "links", "jesster.py"))
GOLDEN = os.path.normpath(os.path.join(
    SCRIPT, "..", "tests", "fixtures", "schnorr_vectors.json"))

# Fixed private keys (raw ints — never the machine secret, never scrypt).
PRIVS = [1, 2, 123456789, 0xDEADBEEFCAFE]
MSGS = [b"", b"hello mesh",
        bytes.fromhex("184708e3e11ea897bd505e29a1daeac3f229a3ab26604770ac35bce5bd21c97f"),
        b"JESSTER|session|v1|X|Y"]


def load_oracle():
    spec = importlib.util.spec_from_file_location("jesster_oracle", ORACLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def flip_byte(b, idx=0):
    out = bytearray(b)
    out[idx] ^= 0x01
    return bytes(out)


def build(J):
    vecs = []

    # 1. determinism: same priv + msg signs identically twice.
    sig_a = J.sign(1, MSGS[1]).hex()
    sig_b = J.sign(1, MSGS[1]).hex()
    vecs.append({"id": "determinism", "expect": "sign deterministic",
                 "ok": sig_a == sig_b,
                 "detail": "sign(1, 'hello mesh') twice -> identical",
                 "priv": 1, "msg": MSGS[1].hex(), "sig": sig_a})

    # 2. verify-accept across keys x messages.
    accepts = []
    for priv in PRIVS:
        pub = J._ser(J._mul(priv, J._G)).hex()
        for m in MSGS:
            sig = J.sign(priv, m).hex()
            ok = J.verify(bytes.fromhex(pub), m, bytes.fromhex(sig))
            accepts.append({"priv": priv, "pub": pub,
                            "msg": m.hex(), "sig": sig, "verified": bool(ok)})
    vecs.append({"id": "verify-accept", "expect": "all verify true",
                 "ok": all(a["verified"] for a in accepts),
                 "detail": "%d/%d key x message pairs verify"
                           % (sum(1 for a in accepts if a["verified"]), len(accepts)),
                 "cases": accepts})

    base = accepts[1]  # priv=1, MSGS[1]: the working trio for refusal edges.
    pub_b = bytes.fromhex(base["pub"])
    msg_b = bytes.fromhex(base["msg"])
    sig_b = bytes.fromhex(base["sig"])

    # 3. wrong message refuses.
    vecs.append({"id": "wrong-message", "expect": "REFUSED",
                 "ok": J.verify(pub_b, b"a different message", sig_b) is False,
                 "detail": "valid sig over another message does not verify"})

    # 4. flipped signature byte refuses.
    vecs.append({"id": "flipped-sig", "expect": "REFUSED",
                 "ok": J.verify(pub_b, msg_b, flip_byte(sig_b, 10)) is False,
                 "detail": "one flipped sig byte breaks the equation"})

    # 5. s >= N refuses (malleability edge: replace s with N).
    bad_s = sig_b[:64] + J._N.to_bytes(32, "big")
    vecs.append({"id": "s-gte-n", "expect": "REFUSED",
                 "ok": J.verify(pub_b, msg_b, bad_s) is False,
                 "detail": "s == N refused by the range check"})

    # 6. bad length refuses.
    vecs.append({"id": "bad-length", "expect": "REFUSED",
                 "ok": J.verify(pub_b, msg_b, sig_b[:95]) is False,
                 "detail": "95-byte sig is not 96 bytes"})

    # 7. infinity pub refuses.
    vecs.append({"id": "infinity-pub", "expect": "REFUSED",
                 "ok": J.verify(bytes(64), msg_b, sig_b) is False,
                 "detail": "zero pub (infinity) is not on the curve"})

    # 8. off-curve pub refuses: (1,1) fails y^2 == x^3+7.
    off = (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
    vecs.append({"id": "off-curve-pub", "expect": "REFUSED",
                 "ok": (not J.on_curve(J._deser(off)))
                 and J.verify(off, msg_b, sig_b) is False,
                 "detail": "(1,1) off curve and refused as a key"})

    # 9. certify round-trip + tamper refuse (session trust, SPEC_US_MESH 5.2).
    ident_priv, sess_priv = 7, 11
    ident = {"office": "TEST", "epoch": 1,
             "priv": ident_priv,
             "pub": J._ser(J._mul(ident_priv, J._G))}
    sess = {"priv": sess_priv,
            "pub": J._ser(J._mul(sess_priv, J._G))}
    cert = J.certify(ident, sess)
    tampered = dict(cert)
    tampered["session_pub"] = sess["pub"].hex()[:-1] + (
        "0" if sess["pub"].hex()[-1] != "0" else "1")
    vecs.append({"id": "certify", "expect": "round-trip true, tampered false",
                 "ok": J.check_cert(cert) is True
                 and J.check_cert(tampered) is False,
                 "detail": "identity vouches for the session; edited session_pub fails",
                 "cert": cert})

    return vecs


def payload():
    J = load_oracle()
    return {"spec": "SPEC_US_MESH B2-07",
            "oracle": {"file": "estate/forge/links/jesster.py",
                       "sha256": file_sha256(ORACLE)},
            "domain": "JESSTER|nonce| / JESSTER|chal| deterministic Schnorr, secp256k1",
            "vectors": build(J)}


def cut():
    p = payload()
    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)
    print("cut %d schnorr vectors -> %s" % (len(p["vectors"]), GOLDEN))
    print("  oracle sha256 %s" % p["oracle"]["sha256"])
    for v in p["vectors"]:
        print("  [%s] %-14s %s" % ("ok" if v["ok"] else "BAD", v["id"], v["detail"]))


def verify():
    J = load_oracle()
    pinned = None
    if os.path.exists(GOLDEN):
        with open(GOLDEN, "r", encoding="utf-8") as f:
            pinned = json.load(f)["oracle"]["sha256"]
    live = file_sha256(ORACLE)
    print("\n  SCHNORR -- differential goldens (SPEC_US_MESH B2-07, hermetic)")
    print("    oracle estate/forge/links/jesster.py sha256 %s" % live)
    if pinned is not None and pinned != live:
        print("    [FAIL]  oracle drifted: golden pins %s" % pinned)
        return 1
    vecs = build(J)
    width = max(len(v["id"]) for v in vecs)
    failed = False
    for v in vecs:
        print("    [%s]  %-*s  %s"
              % ("PASS" if v["ok"] else "FAIL", width, v["id"], v["detail"]))
        if not v["ok"]:
            failed = True
    print()
    if failed:
        print("  A vector failed. The signing model is not what the spec claims.")
        return 1
    print("  PROVEN. Python signs; Go must byte-match.")
    return 0


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
