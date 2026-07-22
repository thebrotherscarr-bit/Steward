#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE DELEGATION WALL — the leash the one door never had.

The Forge shapes fire; the operator alone carries it out. That was always true —
but the door itself trusted a single word, operator_confirm, and would then write a
figure to ANY path on the machine. Every other real act in this estate is scoped:
Steward cannot leave his working directory, and the board commands only clay. This
is the same leash, for the last and most consequential door. It does not open the
door — it decides where the door is allowed to open ONTO.

Pure by design: it reaches nothing, asks no one, runs no code. It answers one
question honestly — is this destination inside the sanctioned root? — and the
board's gatehouse builds the rest of the gates around it. A wall you can hold whole
in your mind, and prove alone.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_FILE = os.path.join(HERE, "delegation_root.txt")
DEFAULT_ROOT = os.path.join(HERE, "delegated")   # contained, real, safe from first use


def get_root():
    """The folder fire is allowed to land in. Defaults to a contained folder inside
    the estate — never the whole machine. The operator may repoint it, but there is
    no way to widen it to 'nowhere', because an unset root would mean 'anywhere',
    which is the exact thing this wall exists to forbid."""
    try:
        r = open(ROOT_FILE).read().strip()
        if r:
            return os.path.abspath(os.path.expanduser(r))
    except Exception:
        pass
    return DEFAULT_ROOT


def set_root(path):
    """The operator moves the root. It is created if it does not exist, so the wall
    is never pointed at a folder that isn't there."""
    p = str(path or "").strip()
    if not p:
        return {"ok": False, "error": "no folder given"}
    p = os.path.abspath(os.path.expanduser(p))
    try:
        os.makedirs(p, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": "could not make that root: %s" % e}
    open(ROOT_FILE, "w", encoding="utf-8").write(p)
    return {"ok": True, "root": p}


def within_root(destination):
    """The one honest question. Returns (ok, safe_absolute_path, detail).

    A bare name lands inside the root; an absolute path must already be inside it.
    os.path.abspath resolves any '..' FIRST, so a traversal out of the root
    (root/../etc/passwd) is refused, not followed. Conservative on purpose: if it
    cannot prove the destination is inside, it says no."""
    root = os.path.abspath(get_root())
    d = str(destination or "").strip()
    if not d:
        return False, None, "no destination given"
    d = os.path.expanduser(d)
    cand = d if os.path.isabs(d) else os.path.join(root, d)
    ap = os.path.abspath(cand)
    if ap == root:
        return False, None, "that is the root folder itself, not a file inside it"
    if ap.startswith(root + os.sep):
        return True, ap, root
    return False, None, "outside the delegation root (%s)" % root
