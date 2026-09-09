#!/usr/bin/env python3
"""TOWN workflow — task scheduling."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _mcp_client import call, is_online

PROJECT = "atlas"

def main():
    print("=== TOWN WORKFLOW ===\n")
    if not is_online():
        print("  MCP offline — skipping"); return 3
    steps = [
        ("get_in_line", {"project": PROJECT}, lambda r: "fold(record)" in r or len(r) > 20),
        ("remember", {"project": PROJECT, "actor": "town",
                       "body": "Work order WO-001: E2E test"},
         lambda r: len(r) > 0),
        ("verify_chain", {"project": PROJECT, "path": "tests/fixtures/chains/agents_seatlog.jsonl"}, lambda r: "INTACT" in r),
        ("state_matrix", {"project": PROJECT},
         lambda r: "fold" in r.lower() or len(r) > 10),
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
    print(f"\nTOWN: {passed}/{len(steps)} PASS")
    return 0 if passed == len(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
