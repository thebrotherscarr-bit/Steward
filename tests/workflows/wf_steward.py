#!/usr/bin/env python3
"""STEWARD workflow — ask Ollama, record testimony, verify chain."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from _mcp_client import call, is_online

PROJECT = "atlas"

def main():
    print("=== STEWARD WORKFLOW ===\n")
    if not is_online():
        print("  MCP offline — skipping"); return 3
    steps = [
        ("rack_list", {"project": PROJECT}, lambda r: "voice" in r.lower() or len(r) > 10),
        ("rack_ask", {"project": PROJECT, "voice": "qwen3.5:4b",
                       "question": "What is ATLAS? One sentence."},
         lambda r: len(r) > 5),
        ("memory", {"project": PROJECT, "voice": "qwen3.5:4b",
                     "question": "What is ATLAS?"},
         lambda r: len(r) > 0),
        ("remember", {"project": PROJECT, "actor": "steward",
                       "body": "Steward workflow complete."},
         lambda r: len(r) > 0),
        ("verify_chain", {"project": PROJECT, "path": "tests/fixtures/chains/agents_seatlog.jsonl"}, lambda r: "INTACT" in r),
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
    print(f"\nSTEWARD: {passed}/{len(steps)} PASS")
    return 0 if passed == len(steps) else 1

if __name__ == "__main__":
    sys.exit(main())
