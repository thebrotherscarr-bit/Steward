#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_teamchat_vectors.py -- N5 team-chat goldens (spec-first).

The team-chat v1 contract (the oracle; the Go team package must honor it):

  platforms   : discord | slack | whatsapp — closed set, named otherwise
  channels    : ^[a-z0-9][a-z0-9_-]{0,63}$ (same shape law as prompts)
  directions  : outbound (atlas -> platform) | inbound (platform -> atlas)
  receipt     : sha256(direction + "\\n" + platform + "\\n" + channel +
                       "\\n" + agent + "\\n" + content + "\\n" + ts)
  webhook HMAC: signature = "sha256=" + hex(hmac_sha256(secret, raw_body));
                compared constant-time; wrong secret refuses, never stores
  dedupe      : inbound with a seen (platform, external_id) stores once —
                the second delivery reports duplicate, never a second row
  secrecy     : tokens live in state/chat_secrets.json (0600, never served,
                never logged); status reports connected:true/false ONLY
  guard-first : outbound content runs the guard pipeline — injection
                refuses with no POST, PII sends redacted with the marker

No live platforms, no network. The fixture file is the oracle; --verify
recomputes every vector deterministically with a fixed secret.
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
TEAM = os.path.join(FIX, "teamchat_vectors.json")

PLATFORMS = ["discord", "slack", "whatsapp"]
CHANNEL_RE = r"^[a-z0-9][a-z0-9_-]{0,63}$"
SECRET = "prove-only-secret-0123456789abcdef"
BODY = b'{"event_id":"E1","text":"hello atlas"}'


def receipt(direction, platform, channel, agent, content, ts):
    h = hashlib.sha256()
    h.update((direction + "\n" + platform + "\n" + channel + "\n"
              + agent + "\n" + content + "\n" + ts).encode("utf-8"))
    return h.hexdigest()


def sign(secret, body):
    return "sha256=" + hmac.new(secret.encode("utf-8"), body,
                                hashlib.sha256).hexdigest()


def payload(platform, text):
    if platform == "discord":
        return {"content": text, "username": "atlas"}
    if platform == "slack":
        return {"text": text}
    if platform == "whatsapp":
        return {"messaging_product": "whatsapp", "text": {"body": text}}
    raise KeyError("unknown platform: " + platform)


def vectors():
    return {
        "platforms": PLATFORMS,
        "channel_re": CHANNEL_RE,
        "good_channels": ["general", "ops-alerts", "a", "x" * 64],
        "bad_channels": ["", "UPPER", "has space", "../escape", "a" * 65],
        "receipt_example": {
            "direction": "outbound",
            "platform": "discord",
            "channel": "general",
            "agent": "manjuel",
            "content": "the beat walks",
            "ts": "2026-09-09T12:00:00Z",
            "receipt": receipt("outbound", "discord", "general",
                               "manjuel", "the beat walks",
                               "2026-09-09T12:00:00Z"),
        },
        "hmac_example": {
            "secret_hint": "prove-only (never the live secret)",
            "body": BODY.decode("utf-8"),
            "signature": sign(SECRET, BODY),
        },
        "payload_shapes": [
            {"platform": p, "text": "hi",
             "payload": payload(p, "hi")} for p in PLATFORMS
        ],
        "dedupe": {
            "first": "stored",
            "second": "duplicate",
        },
    }


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    doc = vectors()
    write_bytes(TEAM, json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("teamchat -> %s" % TEAM)


def verify():
    doc = json.loads(open(TEAM, encoding="utf-8").read())
    want = vectors()
    print("\n  TEAMCHAT -- golden contract (N5, pinned oracle)")
    ok = True
    if doc != want:
        ok = False
        print("    [FAIL]  fixture drifted from the contract")
        for k in want:
            if doc.get(k) != want[k]:
                print("    drift:", k)
    else:
        print("    [PASS]  platforms + channels + receipt + hmac + payloads + dedupe")
    for c in want["good_channels"]:
        if not re.match(want["channel_re"], c):
            ok = False
            print("    [FAIL]  good channel refused: %r" % c)
    for c in want["bad_channels"]:
        if re.match(want["channel_re"], c):
            ok = False
            print("    [FAIL]  bad channel admitted: %r" % c)
    ex = want["receipt_example"]
    if receipt(ex["direction"], ex["platform"], ex["channel"],
               ex["agent"], ex["content"], ex["ts"]) != ex["receipt"]:
        ok = False
        print("    [FAIL]  receipt formula does not reproduce")
    hx = want["hmac_example"]
    if sign(SECRET, hx["body"].encode("utf-8")) != hx["signature"]:
        ok = False
        print("    [FAIL]  hmac does not reproduce")
    if not hmac.compare_digest(sign(SECRET, BODY), hx["signature"]):
        ok = False
        print("    [FAIL]  constant-time compare disagrees")
    if sign("wrong-secret", BODY) == hx["signature"]:
        ok = False
        print("    [FAIL]  wrong secret verifies (catastrophic)")
    if ok:
        print()
        print("  PROVEN. The bridge checks its papers.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
