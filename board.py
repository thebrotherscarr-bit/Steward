#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE BOARD — the taskmaster beside the Forge.

The Forge must not be bloated. It does the hot work — shaping, running, the fire.
The board carries everything else, so the Forge stays lean: it is the RACK that
holds the tools, and it is the LEDGER that records their use. The Forge calls the
board to pick up a tool and to mark what it did; the board keeps the Forge on task.

The board is to the Forge what Steward is to Manjuel — the one that tracks and
organizes, so the core stays pure. Two surfaces, one relationship.

The ledger is append-only and witnessed, in the same honest spirit as Manjuel's:
what tool, when, by whom. The count is EVIDENCE, never verdict — Steward judges
what is truly working, from many angles. Disuse does not bely value.
"""
import os, json, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD_DIR = os.path.join(HERE, "board")
RACK = os.path.join(BOARD_DIR, "rack.json")       # the tools the board holds
LEDGER = os.path.join(BOARD_DIR, "ledger.jsonl")  # append-only record of use
os.makedirs(BOARD_DIR, exist_ok=True)


# ---- the ledger: append-only, hash-chained, witnessed ----
def _last_hash():
    if not os.path.exists(LEDGER):
        return "0" * 16
    last = None
    for line in open(LEDGER, encoding="utf-8"):
        if line.strip():
            last = line
    if not last:
        return "0" * 16
    return json.loads(last).get("hash", "0" * 16)


def _mark(kind, detail):
    """Mark the board — one append-only entry, chained to the last. Nothing is
    ever edited or removed; the record only grows."""
    prev = _last_hash()
    entry = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "detail": detail, "prev": prev}
    entry["hash"] = hashlib.sha256((prev + json.dumps(entry, sort_keys=True)).encode()).hexdigest()[:16]
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


# ---- the rack: the tools the board holds ----
def _load_rack():
    if os.path.exists(RACK):
        try:
            return json.load(open(RACK, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_rack(rack):
    json.dump(rack, open(RACK, "w", encoding="utf-8"), indent=2)


def rack_tool(name, path, note=""):
    """Place a tool on the rack. The board now holds it and knows it exists.
    Records the racking as witness. Re-racking updates without losing history."""
    rack = _load_rack()
    first = name not in rack
    rack[name] = {"path": path, "note": note,
                  "racked_at": rack.get(name, {}).get("racked_at", time.strftime("%Y-%m-%dT%H:%M:%S")),
                  "uses": rack.get(name, {}).get("uses", 0)}
    _save_rack(rack)
    _mark("racked" if first else "re-racked", {"tool": name, "path": path})
    return {"racked": name, "first_time": first}


def use_tool(name, who):
    """Mark that a tool was used, by whom. Raises its count (evidence, not verdict)
    and witnesses it in the ledger. This is what the annealing will later read."""
    rack = _load_rack()
    if name not in rack:
        return {"error": "no such tool on the board: %s" % name}
    rack[name]["uses"] += 1
    rack[name]["last_used"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_rack(rack)
    _mark("used", {"tool": name, "by": who})
    return {"tool": name, "uses": rack[name]["uses"], "by": who}


def inventory():
    """What the board holds, and how each has been used. Plain facts — the raw
    evidence, laid out. Not a judgment of worth."""
    rack = _load_rack()
    return {"tools": [{"name": n, "uses": d["uses"], "path": d["path"],
                       "last_used": d.get("last_used"), "note": d.get("note", "")}
                      for n, d in sorted(rack.items())],
            "count": len(rack)}


def history(name=None, limit=50):
    """Read the ledger — the whole witnessed record, or one tool's story."""
    if not os.path.exists(LEDGER):
        return {"entries": []}
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    if name:
        rows = [r for r in rows if r.get("detail", {}).get("tool") == name]
    return {"entries": rows[-limit:], "total": len(rows)}


def audit():
    """Verify the ledger's chain — proof nothing was edited. Same honesty as the
    core: tampering anywhere breaks the chain visibly."""
    if not os.path.exists(LEDGER):
        return {"intact": True, "entries": 0}
    rows = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    prev = "0" * 16
    for i, r in enumerate(rows):
        check = dict(r); h = check.pop("hash")
        expect = hashlib.sha256((prev + json.dumps(check, sort_keys=True)).encode()).hexdigest()[:16]
        if h != expect or r.get("prev") != prev:
            return {"intact": False, "broke_at": i, "entries": len(rows)}
        prev = h
    return {"intact": True, "entries": len(rows)}


if __name__ == "__main__":
    print("THE BOARD — taskmaster beside the Forge\n")
    print("rack:", RACK)
    print("ledger:", LEDGER)
    inv = inventory()
    print("\nholds %d tools:" % inv["count"])
    for t in inv["tools"]:
        print("  %-20s uses:%-4d %s" % (t["name"], t["uses"], t["note"]))
    a = audit()
    print("\nledger:", a["entries"], "entries, intact:", a["intact"])


# ---------------------------------------------------------------------------
# THE BOARD'S SMARTS — the deliberating mind (B1). The board weighs the toolstack
# and the process OVER TIME, from its own honest ledger. This is measurement, not
# judgment: cold arithmetic on facts it already holds. It ADVISES and it never
# rules. Steward remains the authority on what is truly working; the count is
# evidence, never verdict; and disuse does not bely value — the board says so
# plainly, so its own numbers are never mistaken for the last word.
# ---------------------------------------------------------------------------

def _mission_rates():
    """If the mission ledger exists, read each tool's success from it. Missions
    record what happened; the board weighs it. Pure reading, no change."""
    path = os.path.join(BOARD_DIR, "missions.jsonl")
    rates = {}
    if not os.path.exists(path):
        return rates
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("phase") == "AFTER":
            plan = (e.get("review", {}) or {}).get("what_was_planned", {}) or {}
            for tool in plan.get("tools_recommended", []):
                r = e["review"].get("success_rate")
                if r is not None:
                    rates.setdefault(tool, []).append(r)
    return {t: round(sum(v) / len(v), 2) for t, v in rates.items()}


def weigh():
    """The board's assessment of the whole toolstack, from its own record. Reports
    what it MEASURES — reliable, cracking, seldom-used — each as evidence with a
    plain caveat. It recommends; it does not decide. Steward judges worth."""
    rack = _load_rack()
    hist = history(limit=100000)["entries"]
    rates = _mission_rates()

    findings = []
    for name, d in rack.items():
        uses = d.get("uses", 0)
        rate = rates.get(name)
        note = []
        if uses >= 3 and (rate is None or rate >= 0.75):
            note.append("reliable (annealing through use)")
        if rate is not None and rate < 0.5:
            note.append("cracking — low success; watch before trusting")
        if uses == 0:
            note.append("seldom used — evidence only; disuse does not bely value")
        findings.append({"tool": name, "uses": uses, "mission_success": rate,
                         "board_reads": note or ["in service; nothing notable yet"]})

    return {
        "assessment": findings,
        "measured_from": {"tools": len(rack), "ledger_entries": len(hist),
                          "missions_reviewed": len(rates)},
        "caveat": "The board measures; it does not rule. Steward is the authority "
                  "on what is truly working. The count is evidence, never verdict.",
    }


def advise(tool=None):
    """A focused read on one tool, or the board's top recommendation. Still only
    advice — the board's voice at the table, never its hand."""
    w = weigh()
    if tool:
        for f in w["assessment"]:
            if f["tool"] == tool:
                return {"tool": tool, "board_reads": f["board_reads"], "uses": f["uses"],
                        "mission_success": f["mission_success"], "caveat": w["caveat"]}
        return {"error": "no such tool on the board: %s" % tool}
    flags = [f for f in w["assessment"] if any("cracking" in r for r in f["board_reads"])]
    return {"the_board_would_note": flags or "nothing is cracking; the stack reads sound",
            "caveat": w["caveat"]}


# ---------------------------------------------------------------------------
# MISSION CONTROL — the board's inbox and out-tray. Steward DROPS a direction in;
# the board owns everything after. The pack listens to the board, never to
# Steward. Results are left out for Steward to OBSERVE. One-way in, one-way out —
# exactly like Manjuel's bridge. Nothing the mission does can flow back to harm
# the one who directed it.
# ---------------------------------------------------------------------------
INBOX = os.path.join(BOARD_DIR, "inbox.jsonl")     # directions Steward drops
OUTTRAY = os.path.join(BOARD_DIR, "outtray.jsonl")  # results left for observing


def direct(purpose, scope, tools, littles, minutes=5, by="steward"):
    """Steward drops a mission direction onto the board. He is decoupled the
    instant he does — the board owns it now. Returns a ticket id; Steward walks
    away and later observes the result. He never touches the pack."""
    ticket = hashlib.sha256((purpose + str(time.time())).encode()).hexdigest()[:8]
    order = {"ticket": ticket, "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": by,
             "purpose": purpose, "scope": scope, "tools": tools,
             "littles": littles, "minutes": minutes, "state": "waiting"}
    with open(INBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(order) + "\n")
    _mark("directed", {"ticket": ticket, "by": by, "purpose": purpose})
    return {"ticket": ticket, "dropped": True, "note": "the board has it now; Steward is decoupled"}


def pending():
    """Directions waiting in the inbox for mission control to pick up."""
    if not os.path.exists(INBOX):
        return []
    return [json.loads(l) for l in open(INBOX, encoding="utf-8") if l.strip()
            and json.loads(l).get("state") == "waiting"]


def leave_result(ticket, result):
    """Mission control leaves the result on the out-tray for Steward to observe.
    Also marks the inbox order done. Steward reads; he does not reach in."""
    with open(OUTTRAY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ticket": ticket, "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "result": result}) + "\n")
    _mark("mission_result", {"ticket": ticket, "outcome": result.get("outcome", "?")})
    return True


def observe_results(limit=10):
    """What Steward sees when he comes back to observe — results only. A one-way
    window onto finished work, never a handle to reach into it."""
    if not os.path.exists(OUTTRAY):
        return {"results": []}
    rows = [json.loads(l) for l in open(OUTTRAY, encoding="utf-8") if l.strip()]
    return {"results": rows[-limit:], "total": len(rows)}
