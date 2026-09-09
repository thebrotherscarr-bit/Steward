#!/usr/bin/env python3
"""SCOUT workflow — read-only survey. No writes, no Ollama."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _mcp_client import call, is_online

PROJECT = "atlas"

def main():
    print("=== SCOUT WORKFLOW ===\n")
    if not is_online():
        print("  MCP offline — skipping"); return 3
    steps = [
        ("get_in_line", {"project": PROJECT}, "fold(record)"),
        ("muster", {"project": PROJECT}, PROJECT),
        ("read_handoffs", {"project": PROJECT}, "sha256"),
        ("state_matrix", {"project": PROJECT}, None),
        ("tenant_list", {}, None),
    ]
    passed = 0
    for tool, args, expect in steps:
        try:
            r = call(tool, args)
            ok = expect in r if expect else len(r) > 10
            status = "PASS" if ok else "FAIL"
            if ok: passed += 1
            print(f"  {tool}: {status} — {r[:120]}")
        except Exception as e:
            print(f"  {tool}: ERROR — {e}")
    print(f"\nSCOUT: {passed}/{len(steps)} PASS")
    return 0 if passed == len(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
