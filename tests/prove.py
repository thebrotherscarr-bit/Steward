#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prove.py -- THE BALL. One command that proves the whole of atlas.

atlas proves itself in eight places and they had never been gathered: the
Rust spine, the two Go modules, the two shipped batteries that live inside
the binaries, twenty-six golden verifiers, six workflow scripts and one
end-to-end suite. AGENTS.md named four of the verifiers; nobody ran the
other twenty-two. This rolls every leg into one run and one verdict.

    python tests/prove.py              the hermetic legs (no server, no model)
    python tests/prove.py --check      the fast legs only (no cargo)
    python tests/prove.py --live       add the legs that need :8090 and Ollama
    python tests/prove.py --quiet      one line per leg, nothing else

THREE VERDICTS, NOT TWO. A leg is PASS, FAIL, or ABSENT. ABSENT means the
leg named a dependency this ground does not hold -- the read-only source
grounds (estate\\, secondbrain\\) that fourteen of the cutters were cut
from, a binary not yet built, a door not answering. ABSENT is never counted
as a pass and never silently skipped: it prints with the exact path or
command that would answer it. Only a FAIL sets a red exit.

Law 5 (proves are hermetic) is honoured: nothing here writes to the record.
Every child gets stdin=DEVNULL -- a child that inherits a live engine's
stdin deadlocks it, which cost this estate nine sittings on 2026-09-10.

Zero external dependencies (law 6): stdlib only.
"""

import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(HERE, ".."))
GROUND = os.path.normpath(os.path.join(ATLAS, ".."))
TOOLS = os.path.join(ATLAS, "tools")

PASS, FAIL, ABSENT, SKIPPED = "PASS", "FAIL", "ABSENT", "SKIPPED"

# The atlas binary the door battery shells. Never built here: a prove that
# builds its own subject is not a prove.
ATLAS_BIN = os.path.join(ATLAS, "target", "debug",
                         "atlas.exe" if os.name == "nt" else "atlas")

MISSING_PATH = re.compile(r"No such file or directory: '([^']+)'")
NOT_FOUND = re.compile(r"panicked at [^\n]*\n *([^\n:]+): The system cannot find")


class Leg(object):
    """One provable thing: its name, its verdict, and what it would take."""

    def __init__(self, group, name, verdict, detail="", need="", secs=0.0):
        self.group = group
        self.name = name
        self.verdict = verdict
        self.detail = detail
        self.need = need
        self.secs = secs


def run(cmd, cwd=None, timeout=1800):
    """Run a child with its stdin closed. Returns (code, text)."""
    try:
        p = subprocess.run(cmd, cwd=cwd or ATLAS,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except FileNotFoundError as ex:
        return 127, "toolchain absent: %s" % ex
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ds" % timeout


def tail(text, n=6):
    lines = [l.rstrip() for l in text.strip().splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def absent_dependency(text):
    """Name the missing dependency if a refusal is an absence, not a break.

    A refusal counts as ABSENT only when it names a path that (a) does not
    exist and (b) lies outside the atlas tree -- one of the read-only source
    grounds this repo was folded from. A missing file INSIDE atlas is a real
    break and stays a FAIL.
    """
    for path in _candidates(text):
        if os.path.exists(path):
            continue
        if os.path.normpath(path).lower().startswith(
                os.path.normpath(ATLAS).lower()):
            continue
        return path
    return ""


def _candidates(text):
    """Paths a refusal named, absolute-ised against the ground."""
    out = []
    m = MISSING_PATH.search(text)
    if m:
        # A traceback prints the path as a Python literal, so every
        # separator arrives doubled. Put it back the way the disk spells it.
        out.append(m.group(1).replace("\\\\", "\\"))
    m = NOT_FOUND.search(text)
    if m:
        frag = m.group(1).strip()
        if frag:
            out.append(os.path.join(GROUND, frag.replace("/", os.sep)))
    return out


def leg_toolchains():
    """Nothing proves without these; name each one before leaning on it."""
    out = []
    for name, cmd in (("rust", ["cargo", "--version"]),
                      ("go", ["go", "version"]),
                      ("python", [sys.executable, "--version"])):
        code, text = run(cmd, timeout=60)
        first = text.strip().splitlines()[0] if text.strip() else ""
        if code == 0:
            out.append(Leg("TOOLCHAIN", name, PASS, first))
        else:
            out.append(Leg("TOOLCHAIN", name, ABSENT, first,
                           "install it, or prepend %USERPROFILE%\\.cargo\\bin"))
    if os.path.exists(ATLAS_BIN):
        out.append(Leg("TOOLCHAIN", "atlas binary", PASS,
                       os.path.relpath(ATLAS_BIN, ATLAS)))
    else:
        out.append(Leg("TOOLCHAIN", "atlas binary", ABSENT,
                       "the door battery shells this",
                       "cargo build -p atlas"))
    return out


def leg_spine():
    """The Rust spine: core, store, apps/atlas."""
    t = time.time()
    code, text = run(["cargo", "test", "--workspace"])
    secs = time.time() - t
    total = sum(int(n) for n in
                re.findall(r"^test result: \w+\. (\d+) passed", text, re.M))
    detail = "%d strokes" % total
    if code == 0:
        return [Leg("SPINE", "cargo test --workspace", PASS, detail, "", secs)]
    need = absent_dependency(text)
    if need:
        return [Leg("SPINE", "cargo test --workspace", ABSENT,
                    detail + " held; one leg wants the read-only oracle",
                    need, secs)]
    return [Leg("SPINE", "cargo test --workspace", FAIL, tail(text), "", secs)]


def leg_go(module, label):
    """One Go module: it must build before it is asked to prove."""
    out = []
    cwd = os.path.join(ATLAS, module)
    t = time.time()
    code, text = run(["go", "build", "./..."], cwd=cwd)
    if code != 0:
        return [Leg(label, "go build ./...", FAIL, tail(text), "",
                    time.time() - t)]
    out.append(Leg(label, "go build ./...", PASS, "", "", time.time() - t))
    t = time.time()
    code, text = run(["go", "test", "./...", "-count=1"], cwd=cwd)
    secs = time.time() - t
    oks = len(re.findall(r"^ok\s", text, re.M))
    bare = len(re.findall(r"\[no test files\]", text, re.M))
    detail = "%d packages proven, %d carry no prover" % (oks, bare)
    if code == 0:
        out.append(Leg(label, "go test ./...", PASS, detail, "", secs))
    elif "no working atlas binary" in text and not os.path.exists(ATLAS_BIN):
        out.append(Leg(label, "go test ./...", ABSENT,
                       "the door battery has no binary to shell",
                       "cargo build -p atlas", secs))
    else:
        out.append(Leg(label, "go test ./...", FAIL, tail(text), "", secs))
    return out


def leg_mcp():
    """THE LINE's shipped battery -- hermetic, temp grounds, loopback."""
    t = time.time()
    code, text = run(["go", "run", "./cmd/atlas-mcp", "--prove"],
                     cwd=os.path.join(ATLAS, "line"))
    secs = time.time() - t
    strokes = len(re.findall(r"\[PASS\]", text))
    broke = len(re.findall(r"\[FAIL\]", text))
    detail = "%d strokes" % strokes
    if code == 0 and not broke:
        return [Leg("BATTERY", "atlas-mcp --prove", PASS, detail, "", secs)]
    return [Leg("BATTERY", "atlas-mcp --prove", FAIL,
                "%s, %d broke\n%s" % (detail, broke, tail(text)), "", secs)]


def verifiers():
    """Every cutter that answers --verify, in name order."""
    out = []
    for fn in sorted(os.listdir(TOOLS)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(TOOLS, fn)
        with open(path, encoding="utf-8", errors="replace") as f:
            if "--verify" not in f.read():
                continue
        out.append((fn[:-3], path))
    return out


def leg_goldens():
    """Law 2: goldens before assertions. These re-cut and compare."""
    out = []
    for name, path in verifiers():
        t = time.time()
        code, text = run([sys.executable, path, "--verify"], timeout=600)
        secs = time.time() - t
        if code == 0:
            out.append(Leg("GOLDENS", name, PASS, "", "", secs))
            continue
        # A CUTTER THAT SHELLS THE SPINE IS ABSENT WITHOUT IT, NOT BROKEN.
        # absent_dependency only recognises an absence that NAMES A PATH. A
        # cutter whose subject is the unbuilt binary names a COMMAND instead,
        # so check_trade_parity fell through to FAIL and set a RED EXIT on any
        # machine that had not yet run cargo build -- which is every fresh
        # clone, and the first thing a second machine does. Found 2026-09-11 in
        # the packaging run by parking the binary and re-running: 20 held, 14
        # absent, 1 broke, exit 1, on a tree where nothing was wrong.
        #
        # This is the doctrine leg_go already applies two functions up, and the
        # one cmd/atlas-door/prove_test.go learned the same day: ABSENT names
        # what would answer it and is never a pass; only FAIL is red.
        #
        # Gated on the binary being GENUINELY ABSENT so this can never turn a
        # real break into an absence -- with the binary on disk the branch is
        # unreachable. The cutter says the same thing from the other side with
        # exit 2, and it is the only cutter in tools/ that uses 2 at all.
        if not os.path.exists(ATLAS_BIN) and "cargo build -p atlas" in text:
            out.append(Leg("GOLDENS", name, ABSENT,
                           "the spine this cutter shells is not built",
                           "cargo build -p atlas", secs))
            continue
        need = absent_dependency(text)
        if need:
            # NAME THE DIAL, not just the missing file. The goldens themselves
            # are committed and travel with the repo; only the RE-CUT needs the
            # oracle it was cut from, and that ground is private and does not
            # ship. Until 2026-09-11 this said "oracle not in this ground" and
            # pointed at a path that has never existed on any machine — the
            # cutters resolved it relative to atlas's parent, which stopped
            # being the oracle ground at the 2026-09-10 split. ABSENT was the
            # right verdict for the wrong reason, with no way to act on it.
            out.append(Leg("GOLDENS", name, ABSENT,
                           "oracle not in this ground "
                           "(set ATLAS_ORACLE_ROOT to the ground holding it)",
                           need, secs))
        else:
            out.append(Leg("GOLDENS", name, FAIL, tail(text), "", secs))
    return out


def mcp_online():
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=3)
        return True
    except Exception:
        return False


def leg_workflows(live):
    """The six seat workflows. They drive the live door; without it they are
    ABSENT, never passed."""
    wfdir = os.path.join(HERE, "workflows")
    scripts = sorted(f for f in os.listdir(wfdir)
                     if f.startswith("wf_") and f.endswith(".py"))
    if not live:
        return [Leg("WORKFLOWS", f[:-3], SKIPPED, "pass --live to run")
                for f in scripts]
    if not mcp_online():
        return [Leg("WORKFLOWS", f[:-3], ABSENT, "the door is not answering",
                    "start atlas-mcp on :8090") for f in scripts]
    out = []
    for f in scripts:
        t = time.time()
        code, text = run([sys.executable, os.path.join(wfdir, f)], timeout=900)
        secs = time.time() - t
        line = ""
        for ln in reversed(text.strip().splitlines()):
            if "PASS" in ln:
                line = ln.strip()
                break
        if code == 0:
            out.append(Leg("WORKFLOWS", f[:-3], PASS, line, "", secs))
        elif code == 3:
            out.append(Leg("WORKFLOWS", f[:-3], ABSENT,
                           "the door is not answering",
                           "start atlas-mcp on :8090", secs))
        else:
            out.append(Leg("WORKFLOWS", f[:-3], FAIL, line or tail(text),
                           "", secs))
    return out


def leg_e2e(live):
    """The end-to-end suite: the door AND a local model."""
    path = os.path.join(HERE, "e2e", "test_suite.py")
    if not live:
        return [Leg("E2E", "test_suite", SKIPPED, "pass --live to run")]
    if not mcp_online():
        return [Leg("E2E", "test_suite", ABSENT, "the door is not answering",
                    "start atlas-mcp on :8090")]
    t = time.time()
    code, text = run([sys.executable, path], timeout=3600)
    secs = time.time() - t
    if code == 0:
        return [Leg("E2E", "test_suite", PASS, "", "", secs)]
    return [Leg("E2E", "test_suite", FAIL, tail(text), "", secs)]


def report(legs, quiet):
    width = max(len(l.name) for l in legs)
    group = None
    for l in legs:
        if l.group != group:
            group = l.group
            print()
            print("  %s" % group)
        lines = l.detail.splitlines() if l.detail else [""]
        secs = "  %5.1fs" % l.secs if l.secs >= 0.05 else "        "
        print("    [%-7s]  %-*s%s  %s"
              % (l.verdict, width, l.name, secs, lines[0]))
        if not quiet:
            for ln in lines[1:]:
                print("                 %s" % ln)
        if l.need:
            print("                 needs: %s" % l.need)


def main():
    ap = argparse.ArgumentParser(description="prove the whole of atlas")
    ap.add_argument("--check", action="store_true",
                    help="fast legs only: go + goldens, no cargo")
    ap.add_argument("--live", action="store_true",
                    help="also run the legs that need :8090 and Ollama")
    ap.add_argument("--quiet", action="store_true", help="one line per leg")
    args = ap.parse_args()

    t0 = time.time()
    print()
    print("  ATLAS -- THE BALL (%s)"
          % ("fast" if args.check else "live" if args.live else "hermetic"))

    legs = leg_toolchains()
    if not args.check:
        legs += leg_spine()
    legs += leg_go("line", "LINE")
    legs += leg_go("webapp", "GLASS")
    if not args.check:
        legs += leg_mcp()
    legs += leg_goldens()
    legs += leg_workflows(args.live)
    legs += leg_e2e(args.live)

    report(legs, args.quiet)

    broke = [l for l in legs if l.verdict == FAIL]
    gone = [l for l in legs if l.verdict == ABSENT]
    held = [l for l in legs if l.verdict == PASS]
    print()
    print("  %d held - %d absent - %d broke - %.1fs"
          % (len(held), len(gone), len(broke), time.time() - t0))
    if gone and not args.quiet:
        print()
        print("  ABSENT is not a pass. These legs named something this ground")
        print("  does not hold; nothing was assumed in their place:")
        seen = set()
        for l in gone:
            if not l.need or l.need in seen:
                continue
            seen.add(l.need)
            print("    %s" % l.need)
    print()
    if broke:
        print("  A leg broke. atlas does not claim what it cannot show.")
        return 1
    print("  PROVEN, to the edge of this ground.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
