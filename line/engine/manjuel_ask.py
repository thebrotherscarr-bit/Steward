#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot ask adapter for the manjuel engine (atlas line/engine).

atlas-mcp's ask_steward invokes this as:
    python manjuel_ask.py <manjuel_core_path> "<question>"

It mirrors manjuel's own seat_mcp _RUNNER: wake the engine, wake the heart,
weigh, rest, print the ruling. This file lives in atlas and only RUNS the
manjuel build -- it never edits it (the secondbrain/estate grounds are
read-only to atlas).

The engine API it relies on (manjuel, 2026-08-25+):
    from manjuel import Steward
    m = Steward().awaken()
    m.conscience.wake()                       # heart runs in its own process
    out = m.skills.invoke("weigh", question, m)
    m.conscience.rest()
"""
import os
import sys

sys.dont_write_bytecode = True


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("manjuel_ask.py needs <manjuel_core> <question>\n")
        return 2
    home, question = sys.argv[1], sys.argv[2]
    os.chdir(home)
    sys.path.insert(0, home)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    from manjuel import Steward
    m = Steward().awaken()
    try:
        m.conscience.wake()
        out = m.skills.invoke("weigh", question, m)
    finally:
        try:
            m.conscience.rest()
        except Exception:
            pass
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
