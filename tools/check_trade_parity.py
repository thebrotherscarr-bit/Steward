#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_trade_parity.py -- the reverse cross-check (D2, dev-run + witnessed).

Builds trade books with the RUST binary (`atlas trade ...` on temp ground),
then verifies them with the ORACLE skills (property/workorder/inspect
`verify` + key reads). Hermetic: temp ground, local subprocess, no network.

This is not part of any --verify battery (it shells to a built binary);
run it by hand before landing trade changes and witness the result:

    cargo build -p atlas
    .venv\\Scripts\\python.exe tools\\check_trade_parity.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
ARCHIVE = os.path.normpath(os.path.join(ATLAS, ".."))
SKILLS = os.path.join(ARCHIVE, "estate", "Steward 1.0", "skills")
BIN = os.path.join(ATLAS, "target", "debug",
                   "atlas.exe" if os.name == "nt" else "atlas")

CMDS = [
    ("property", "enroll Red Rock Loop | 55 Red Rock Loop Rd, Sedona"),
    ("property", "enroll Juniper Ridge casita | key in the lockbox"),
    ("workorder", "add Juniper Ridge casita | swamp cooler pads worn | Dale"),
    ("workorder", "add Red Rock Loop | gate hinge javelina damage | Marco"),
    ("workorder", "assign 2 | Marco"),
    ("workorder", "done 1 | 300"),
    ("inspect", "log Red Rock Loop | water heater=pass ; drip zone 3=fail | javelina bent the gate"),
    ("inspect", "log Juniper Ridge casita | swamp cooler=pass"),
]


def load(name):
    spec = importlib.util.spec_from_file_location(
        "parity_" + name, os.path.join(SKILLS, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    if not os.path.isfile(BIN):
        print("REFUSED: build the binary first (cargo build -p atlas)")
        return 2
    d = tempfile.mkdtemp(prefix="trade_parity_")
    try:
        for skill, cmd in CMDS:
            r = subprocess.run([BIN, "trade", skill, cmd, "--ops", d],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print("RUST REFUSED: %s %s\n%s" % (skill, cmd, r.stderr))
                return 1
        prop = load("property")
        wo = load("workorder")
        insp = load("inspect")
        checks = [
            ("property verify", prop._run("verify", d), "intact (2 entries)"),
            ("workorder verify", wo._run("verify", d), "intact (4 entries)"),
            ("inspect verify", insp._run("verify", d), "intact (2 entries)"),
            ("property list", prop._run("list", d), "Red Rock Loop"),
            ("workorder list", wo._run("list open", d), "#2 [open]"),
            ("inspect report", insp._run("report red rock", d),
             "water heater: pass, drip zone 3: fail"),
        ]
        failed = False
        for name, got, want in checks:
            ok = want in got
            failed = failed or not ok
            print("  [%s]  %-16s  %s" % ("PASS" if ok else "FAIL", name,
                                         got[:70].replace("\n", " / ")))
        # And the Rust side reads its own books back whole.
        r = subprocess.run(
            [BIN, "trade", "report", "Red Rock Loop", "--ops", d],
            capture_output=True, text=True)
        ok = ("This record proves whole" in r.stdout
              and "$300.00" not in r.stdout  # Juniper's receipt, not Red Rock's
              and "gate hinge javelina damage" in r.stdout)
        failed = failed or not ok
        print("  [%s]  %-16s  %s" % ("PASS" if ok else "FAIL", "rust report",
                                     r.stdout[:70].replace("\n", " / ")))
        print()
        print("  PROVEN. Python reads Rust's books whole."
              if not failed else "  A check failed.")
        return 0 if not failed else 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
