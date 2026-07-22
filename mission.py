#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE MISSION LOOP — how the estate acts together, on the board.

Every mission is bracketed by honesty (B1). BEFORE: the plan is recorded — the
scope Steward set, the tools the Forge recommended, the time the board allotted,
the purpose. AFTER: the review spares nothing — what was planned, what happened,
what we learn, what to change, what we missed, where we get better AND where we
get worse. Both are recorded. The estate returns to the board wiser, or the
mission was not truly reviewed.

This loop lives on the board. It commands only the littles — mortal clay. It
touches neither sealed Manjuel nor finished Steward directly; it records their
roles and asks them as clients, the way everything in this estate reaches. The
board allots the time; when the clock runs out, the mission ends, reviewed.

Roles honored, each in plain english over simple python:
  Steward   directs — sets scope and purpose (the authority on the work)
  Forge     recommends — advises which tools serve
  Board     allots time, commands the littles, records; advises, never rules
  Manjuel   observes — witnesses success/failure; judges, never acts
  Operator  holds authority — permanent, over all of it
"""
import os, json, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
MISSIONS = os.path.join(HERE, "board", "missions.jsonl")
os.makedirs(os.path.dirname(MISSIONS), exist_ok=True)


def _last_hash():
    if not os.path.exists(MISSIONS):
        return "0" * 16
    last = None
    for line in open(MISSIONS, encoding="utf-8"):
        if line.strip():
            last = line
    return json.loads(last).get("hash", "0" * 16) if last else "0" * 16


def _record(entry):
    """Append-only, hash-chained — the same honest spirit as Manjuel's ledger.
    A mission's whole life is witnessed; nothing is edited after the fact."""
    prev = _last_hash()
    entry["prev"] = prev
    entry["hash"] = hashlib.sha256((prev + json.dumps(entry, sort_keys=True)).encode()).hexdigest()[:16]
    with open(MISSIONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


class Mission:
    """One mission, from before-plan to after-review, held on the board."""
    active = {}

    def __init__(self, purpose, scope, tools, minutes, directed_by="steward"):
        self.id = hashlib.sha256((purpose + str(time.time())).encode()).hexdigest()[:8]
        self.purpose = purpose
        self.scope = scope                 # what Steward set — the wall
        self.tools = tools                 # what the Forge recommended — the pack
        self.allotted = minutes * 60       # what the board allotted — the clock
        self.directed_by = directed_by
        self.born = time.time()
        self.plan = None
        self.events = []                   # what actually happened, witnessed
        self.review = None
        self.state = "planned"
        Mission.active[self.id] = self

    # ---- BEFORE: the plan is recorded ----
    def before(self):
        self.plan = {
            "purpose": self.purpose,
            "scope": self.scope,
            "tools_recommended": self.tools,
            "time_allotted_min": round(self.allotted / 60, 1),
            "directed_by": self.directed_by,
        }
        _record({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "mission": self.id,
                 "phase": "BEFORE", "plan": self.plan})
        self.state = "underway"
        return self.plan

    # ---- the mission runs; the board watches the clock ----
    def time_left(self):
        return round(self.allotted - (time.time() - self.born), 1)

    def observe(self, what, ok=True):
        """Manjuel observes — an event witnessed during the mission. The board
        records it. If the clock has run out, the mission cannot continue."""
        if self.time_left() <= 0:
            self.events.append({"at": "expired", "what": "clock ran out; mission ends", "ok": False})
            self.state = "expired"
            return {"ended": True, "why": "time allotted by the board is spent"}
        ev = {"at": round(time.time() - self.born, 1), "what": what, "ok": bool(ok)}
        self.events.append(ev)
        return ev

    # ---- AFTER: the review that spares nothing ----
    def after(self, learned, change, missed, better, worse):
        wins = sum(1 for e in self.events if e.get("ok"))
        total = len([e for e in self.events if "ok" in e])
        rate = round(wins / total, 2) if total else None
        self.review = {
            "what_was_planned": self.plan,
            "what_happened": self.events,
            "success_rate": rate,             # Manjuel's observation, tallied
            "what_we_learn": learned,
            "what_to_change": change,
            "what_we_missed": missed,
            "where_better": better,
            "where_worse": worse,             # the downside, named as plainly as the gain
        }
        _record({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "mission": self.id,
                 "phase": "AFTER", "review": self.review})
        self.state = "reviewed"
        Mission.active.pop(self.id, None)
        return self.review


def history(limit=20):
    if not os.path.exists(MISSIONS):
        return {"entries": []}
    rows = [json.loads(l) for l in open(MISSIONS, encoding="utf-8") if l.strip()]
    return {"entries": rows[-limit:], "total": len(rows)}


def audit():
    if not os.path.exists(MISSIONS):
        return {"intact": True, "entries": 0}
    rows = [json.loads(l) for l in open(MISSIONS, encoding="utf-8") if l.strip()]
    prev = "0" * 16
    for i, r in enumerate(rows):
        c = dict(r); h = c.pop("hash")
        if h != hashlib.sha256((prev + json.dumps(c, sort_keys=True)).encode()).hexdigest()[:16] or r.get("prev") != prev:
            return {"intact": False, "broke_at": i}
        prev = h
    return {"intact": True, "entries": len(rows)}


if __name__ == "__main__":
    print("THE MISSION LOOP — a full cycle, on the board\n")

    # PREPARE: Steward scopes, Forge recommends, board allots
    m = Mission(
        purpose="check the household is sound before the day's work",
        scope="read-only; the status tool only; no reach beyond the estate",
        tools=["status"],
        minutes=5,
        directed_by="steward",
    )

    print("--- BEFORE (the plan, recorded) ---")
    plan = m.before()
    for k, v in plan.items():
        print("  %-20s %s" % (k, v))

    print("\n--- MISSION (Manjuel observes; board watches the clock) ---")
    print("  time left:", m.time_left(), "sec")
    print(" ", m.observe("ran status: all cores present, ledger intact", ok=True))
    print(" ", m.observe("noted forge server was offline", ok=False))
    print("  time left:", m.time_left(), "sec")

    print("\n--- AFTER (the review that spares nothing) ---")
    review = m.after(
        learned="the estate reads its own health honestly, even flagging itself",
        change="launch the forge server as part of the mission next time",
        missed="did not check the littles' folder",
        better="one command gives the whole household at a glance",
        worse="if the tool's assumptions drift, it could misreport — watch for that",
    )
    print("  success rate:", review["success_rate"])
    for k in ("what_we_learn", "what_to_change", "what_we_missed", "where_better", "where_worse"):
        print("  %-16s %s" % (k, review[k]))

    print("\n--- the mission ledger ---")
    print("  audit:", audit())
