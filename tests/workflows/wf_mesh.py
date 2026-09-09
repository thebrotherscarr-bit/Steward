#!/usr/bin/env python3
"""MESH workflow — enroll, post, chain walk, read."""

import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(__file__))
from _mcp_client import call, is_online

PROJECT = "atlas"

def main():
    print("=== MESH WORKFLOW ===\n")
    if not is_online():
        print("  MCP offline — skipping"); return 3
    alice = "alice_wf_" + uuid.uuid4().hex[:4]
    bob = "bob_wf_" + uuid.uuid4().hex[:4]
    uid = uuid.uuid4().hex[:4]

    steps = [
        ("mesh_enroll", {"project": PROJECT, "actor": alice},
         lambda r: len(r) > 0),
        ("mesh_enroll", {"project": PROJECT, "actor": bob},
         lambda r: len(r) > 0),
        ("mesh_post", {"project": PROJECT, "actor": alice,
                        "channel": "general", "text": f"hello {uid}"},
         lambda r: len(r) > 0),
        ("mesh_post", {"project": PROJECT, "actor": bob,
                        "channel": "general", "text": f"sealed {uid}", "seal": True},
         lambda r: len(r) > 0),
        ("mesh_chain", {"project": PROJECT},
         lambda r: "INTACT" in r.upper() or len(r) > 10),
        ("mesh_read", {"project": PROJECT, "actor": alice, "channel": "general"},
         lambda r: len(r) > 0),
        ("mesh_read", {"project": PROJECT, "actor": bob,
                        "channel": "general", "reveal": True},
         lambda r: len(r) > 0),
    ]
    passed = 0
    for tool, args, check in steps:
        try:
            r = call(tool, args)
            ok = check(r)
            status = "PASS" if ok else "FAIL"
            if ok: passed += 1
            print(f"  {tool}: {status} — {r[:120]}")
        except Exception as e:
            print(f"  {tool}: ERROR — {e}")
    print(f"\nMESH: {passed}/{len(steps)} PASS")
    return 0 if passed == len(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
