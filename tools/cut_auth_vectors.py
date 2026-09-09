#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_auth_vectors.py -- N6 auth goldens (spec-first).

The auth v1 contract (the oracle; the Go auth package must honor it):

  key format  : "atl_" + 32 lowercase hex (128-bit secrets, crypto/rand)
  key id      : "k-" + 8 lowercase hex (public handle, safe to log)
  KDF         : HMAC-SHA256(password=key, salt) iterated 210000 times,
                result hex. No bcrypt (zero-deps law): the iteration count
                and domain string are pinned here. Verification recomputes
                and compares constant-time; only hash+salt persist.
  scope       : a key belongs to the tenant whose store holds it, plus an
                optional tenants[] allowlist. "*" = every carried tenant
                (operator). Requested project must be carried by the key.
  session     : webapp-side random 32B hex, HttpOnly SameSite=Lax cookie,
                12h expiry, mapped to (tenant, key_id) server-side.
  audit       : every create/revoke appends
                {ts, action, key_id, tenant, by} to state/auth_audit.jsonl.
  bootstrap   : an empty store creates freely (the first key is the
                operator's hand); afterwards creation names an existing key.

No live servers. The fixture file is the oracle; --verify recomputes
every vector deterministically with fixed salt/key inputs.
"""

import hashlib
import hmac
import json
import os
import re
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
FIX = os.path.join(ATLAS, "tests", "fixtures")
AUTH = os.path.join(FIX, "auth_vectors.json")

KEY_RE = r"^atl_[0-9a-f]{32}$"
KID_RE = r"^k-[0-9a-f]{8}$"
ITERS = 210000
DOMAIN = "atlas-auth-v1"


def kdf(key_hex, salt_hex):
    mac = hmac.new(bytes.fromhex(salt_hex), (DOMAIN + key_hex).encode(),
                   hashlib.sha256).digest()
    for _ in range(ITERS - 1):
        mac = hmac.new(bytes.fromhex(salt_hex), mac, hashlib.sha256).digest()
    return mac.hex()


def scope_ok(key_tenants, request):
    if "*" in key_tenants:
        return True
    return request in key_tenants


def vectors():
    salt = "00" * 16
    key = "atl_" + "ab" * 16
    return {
        "key_re": KEY_RE,
        "kid_re": KID_RE,
        "iters": ITERS,
        "domain": DOMAIN,
        "kdf_example": {
            "key": key,
            "salt": salt,
            "hash": kdf(key, salt),
        },
        "scope_matrix": [
            {"tenants": ["atlas"], "request": "atlas", "allow": True},
            {"tenants": ["atlas"], "request": "manjuel", "allow": False},
            {"tenants": ["atlas", "manjuel"], "request": "manjuel", "allow": True},
            {"tenants": ["*"], "request": "stranger-tenant", "allow": True},
            {"tenants": [], "request": "atlas", "allow": False},
        ],
        "audit_shape": {
            "fields": ["ts", "action", "key_id", "tenant", "by"],
            "actions": ["create", "revoke"],
        },
        "session_hours": 12,
    }


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    doc = vectors()
    write_bytes(AUTH, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("auth -> %s" % AUTH)


def verify():
    doc = json.loads(open(AUTH, encoding="utf-8").read())
    want = vectors()
    print("\n  AUTH -- golden contract (N6, pinned oracle)")
    ok = True
    if doc != want:
        ok = False
        print("    [FAIL]  fixture drifted from the contract")
        for k in want:
            if doc.get(k) != want[k]:
                print("    drift:", k)
    else:
        print("    [PASS]  format + kdf + scope + audit + session")
    if not re.match(want["key_re"], want["kdf_example"]["key"]):
        ok = False
        print("    [FAIL]  example key breaks its own shape")
    ex = want["kdf_example"]
    if kdf(ex["key"], ex["salt"]) != ex["hash"]:
        ok = False
        print("    [FAIL]  kdf does not reproduce")
    if kdf("atl_" + "cd" * 16, ex["salt"]) == ex["hash"]:
        ok = False
        print("    [FAIL]  wrong key verifies (catastrophic)")
    for row in want["scope_matrix"]:
        if scope_ok(row["tenants"], row["request"]) != row["allow"]:
            ok = False
            print("    [FAIL]  scope misscored: %r" % row)
    if ok:
        print()
        print("  PROVEN. The gate knows its own.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
