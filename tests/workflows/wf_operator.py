#!/usr/bin/env python3
"""OPERATOR workflow — full lifecycle."""

import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(__file__))
from _mcp_client import call, is_online

PROJECT = "atlas"
VERSION = "0.1.3"

def main():
    print("=== OPERATOR WORKFLOW ===\n")
    if not is_online():
        print("  MCP offline — skipping"); return 3
    uid = uuid.uuid4().hex[:4]

    steps = [
        ("get_in_line", {"project": PROJECT}, lambda r: "fold(record)" in r or len(r) > 20),
        ("muster", {"project": PROJECT}, lambda r: len(r) > 10),
        ("tenant_list", {}, lambda r: len(r) > 0),
        ("rack_list", {"project": PROJECT}, lambda r: len(r) > 10),
        ("rack_ask", {"project": PROJECT, "voice": "qwen3.5:4b",
                       "question": "Status of ATLAS? One word."},
         lambda r: len(r) > 0),
        ("remember", {"project": PROJECT, "actor": "operator",
                       "body": f"Operator lifecycle complete {uid}"},
         lambda r: len(r) > 0),
        ("verify_chain", {"project": PROJECT, "path": "tests/fixtures/chains/agents_seatlog.jsonl"}, lambda r: "INTACT" in r),
        ("mesh_enroll", {"project": PROJECT, "actor": "operator"},
         lambda r: len(r) > 0),
        ("mesh_post", {"project": PROJECT, "actor": "operator",
                        "channel": "releases",
                        "text": f"release candidate {VERSION} {uid}"},
         lambda r: len(r) > 0),
        ("mesh_chain", {"project": PROJECT},
         lambda r: "INTACT" in r.upper() or len(r) > 10),
        ("read_handoffs", {"project": PROJECT}, lambda r: len(r) > 10),
        ("state_matrix", {"project": PROJECT}, lambda r: len(r) > 10),
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
    print(f"\nOPERATOR: {passed}/{len(steps)} PASS")
    return 0 if passed == len(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
