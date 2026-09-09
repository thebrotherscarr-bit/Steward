#!/usr/bin/env python3
"""cut_jesster_vectors.py -- pin the keymaker's DOMAIN STRINGS, byte for byte.

HANDOFF 2026-08-27 (B2, in flight) carried this as an inference, not a fact:

    "Inferred (confirm at impl): the hand-rolled Go Schnorr reuses the same
     JESSTER|OFFICE|vEPOCH domain tag as jesster.py -- the differential
     vectors must pin the domain string, not just the curve."

This cutter confirms it and pins it. SPEC_US_MESH names the live risk plainly:
"this is a *second* hand-rolled crypto implementation; the risk is cross-language
agreement, not a single honest path... 'the port passes its own tests' is not
sufficient." A Go port that agrees on secp256k1 and disagrees on one separator
byte produces signatures nothing in the estate can verify -- and it will pass
every test it writes for itself.

FOUR domain-separated preimages, not one. Measured 2026-08-27 against
estate\\forge\\links\\jesster.py (byte-identical to the copies at
estate\\Jesster\\Archive\\chain\\, Index\\links\\, Skills\\projects\\links\\):

  D1  scrypt salt      b"JESSTER|<OFFICE-UPPER>|v<EPOCH>"
      scrypt input     covenant_utf8 + b"|" + secret     <- NOT domain-prefixed
  D2  nonce preimage   b"JESSTER|nonce|" + priv32 + b"|" + msg
                       ^ separator before msg ONLY -- none after the prefix
  D3  challenge        b"JESSTER|chal|" + R64 + P64 + msg
                       ^ NO separators anywhere
  D4  certify body     b"JESSTER|session|v<EPOCH>|" + ipub64 + b"|" + spub64
                       ^ %s on bytes inserts RAW BYTES (PEP 461), not a repr.
                         Measured, because a reading of this line suspected it
                         embedded b'\\x..' text. It does not. 148 bytes == raw
                         concat length. A warning here would have sent the port
                         hunting a bug that does not exist.

THE TRAPS A PORT WILL HIT, all measured below and none of them the curve:
  * the covenant is a HEX STRING encoded UTF-8 -- 16 ASCII bytes for a 16-char
    mark, never 8 decoded bytes
  * pub is UNCOMPRESSED 64 bytes x||y -- no 0x04 SEC1 prefix, not 33 compressed
  * the signature is R(64) || s(32) = 96 bytes -- NOT BIP-340's 64
  * `k = int(...) % N or 1` -- a nonce that hashes to zero becomes one
  * mark = sha256(pub)[:16] over the 64-byte uncompressed pub

NO atlas_version is stamped into the artifact. That fault reddened three
cutters for two days (diagnosed 2026-08-27); the version rides the witness.

    python tools/cut_jesster_vectors.py            cut
    python tools/cut_jesster_vectors.py --verify   re-cut in memory, compare
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
ARCHIVE = ATLAS.parent
KEYMAKER = ARCHIVE / "estate" / "forge" / "links" / "jesster.py"
OUT = ATLAS / "tests" / "fixtures" / "canon" / "jesster_vectors.json"

# Fixed inputs. THE OPERATOR'S REAL machine.secret IS NEVER READ BY THIS TOOL --
# a golden that depends on a private key is not a golden, it is a leak.
SECRET = bytes(range(32))
SESSION_PRIV = int.from_bytes(bytes(range(32, 64)), "big")
COVENANTS = ["1512741580b7239b", "65118a147dd49ed9"]   # HOUSE, ELDER
OFFICES = ["MANJUEL", "NEIRO", "JESSTER"]
MESSAGES = [b"", b"the estate remembers", bytes(range(256)),
            "café — non-ascii".encode("utf-8")]


def load_keymaker():
    spec = importlib.util.spec_from_file_location("jesster_vec", KEYMAKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_document():
    J = load_keymaker()
    epoch = J.EPOCH
    doc = {
        "tool": "tools/cut_jesster_vectors.py",
        "ordering_note": "B2: the keymaker's domain strings pinned from the "
                         "Python original BEFORE any Go Schnorr exists",
        "keymaker": {
            "path": KEYMAKER.relative_to(ARCHIVE).as_posix(),
            "sha256": hashlib.sha256(KEYMAKER.read_bytes()).hexdigest(),
        },
        "params": {
            "epoch": epoch, "curve": "secp256k1",
            "scrypt": {"n": J._SCRYPT_N, "r": J._SCRYPT_R, "p": J._SCRYPT_P,
                       "dklen": 32, "maxmem": J._MAXMEM},
            "pub_encoding": "uncompressed x||y, 64 bytes, no SEC1 prefix",
            "sig_encoding": "R(64) || s(32), 96 bytes",
            "mark": "sha256(pub)[:16] hex over the 64-byte uncompressed pub",
            "nonce_zero_rule": "k = int(H) % N or 1",
        },
        "domains": {},
        "identities": [],
        "signatures": [],
        "certify": [],
    }

    # D1 -- the scrypt salt, per office
    doc["domains"]["D1_scrypt_salt"] = {
        "form": "JESSTER|<OFFICE-UPPER>|v<EPOCH>",
        "scrypt_input": "covenant_utf8 + b'|' + secret",
        "samples": {o: J.domain(o, epoch).hex() for o in OFFICES},
    }
    doc["domains"]["D2_nonce"] = {
        "form": "b'JESSTER|nonce|' + priv32 + b'|' + msg",
        "prefix_hex": b"JESSTER|nonce|".hex(),
        "note": "separator before msg only; none after the prefix",
    }
    doc["domains"]["D3_challenge"] = {
        "form": "b'JESSTER|chal|' + R64 + P64 + msg",
        "prefix_hex": b"JESSTER|chal|".hex(),
        "note": "no separators anywhere",
    }

    for cov in COVENANTS:
        for office in OFFICES:
            ident = J.identity(cov, SECRET, office, epoch)
            doc["identities"].append({
                "covenant": cov, "office": office, "epoch": epoch,
                "secret_hex": SECRET.hex(),
                "priv_hex": ident["priv"].to_bytes(32, "big").hex(),
                "pub_hex": ident["pub"].hex(),
                "mark": ident["mark"],
            })

    base = J.identity(COVENANTS[0], SECRET, OFFICES[0], epoch)
    for msg in MESSAGES:
        sig = J.sign(base["priv"], msg)
        doc["signatures"].append({
            "priv_hex": base["priv"].to_bytes(32, "big").hex(),
            "msg_hex": msg.hex(), "msg_len": len(msg),
            "sig_hex": sig.hex(), "R_hex": sig[:64].hex(),
            "s_hex": sig[64:].hex(),
            "verifies": bool(J.verify(base["pub"], msg, sig)),
        })

    # D4 -- measured with a FIXED session key so the vector is reproducible
    spub = J._ser(J._mul(SESSION_PRIV, J._G))
    body = b"JESSTER|session|v%d|%s|%s" % (epoch, base["pub"], spub)
    doc["domains"]["D4_certify_body"] = {
        "form": "b'JESSTER|session|v<EPOCH>|' + ipub64 + b'|' + spub64",
        "percent_s_inserts": "raw bytes (PEP 461), NOT a repr -- measured",
        "expected_len": len(b"JESSTER|session|v%d|" % epoch) + 64 + 1 + 64,
        "actual_len": len(body),
    }
    doc["certify"].append({
        "identity_pub_hex": base["pub"].hex(),
        "session_priv_hex": SESSION_PRIV.to_bytes(32, "big").hex(),
        "session_pub_hex": spub.hex(),
        "body_hex": body.hex(),
    })

    doc["tally"] = {"identities": len(doc["identities"]),
                    "signatures": len(doc["signatures"]),
                    "domains": len(doc["domains"])}
    return doc


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + chr(10)


def main():
    blob = render(build_document()).encode("utf-8")
    if "--verify" in sys.argv[1:]:
        if OUT.exists() and OUT.read_bytes() == blob:
            print(f"JESSTER VECTORS VERIFY OK -- {OUT.name} byte-identical to "
                  f"a fresh cut ({len(blob)} bytes)")
            return 0
        print("VERIFY FAIL -- re-cut and witness, never patch silently")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(blob)
    doc = json.loads(blob.decode("utf-8"))
    t = doc["tally"]
    print(f"JESSTER VECTORS CUT -- {t['domains']} domain strings, "
          f"{t['identities']} identities, {t['signatures']} signatures "
          f"-> tests/fixtures/canon/jesster_vectors.json")
    print(f"  keymaker sha256 {doc['keymaker']['sha256'][:16]}...")
    print(f"  cut at atlas {(ATLAS / 'VERSION').read_text(encoding='utf-8').strip()}"
          " -- witness this line, not the artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
