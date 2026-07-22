#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE BOARD SERVER — the mission loader's face, and the gatehouse before the one door.

The Forge keeps the fire lean: it shapes figures and holds the one door out, and
nothing else. The board carries everything a mission needs so the Forge never has
to — the rack, the ledger, the inbox a direction is dropped into, the out-tray a
result is observed from. This server is the board's front door: the one window the
console speaks to, and the gateway that reaches the finished pieces on the
operator's behalf.

It owns what is the board's own — the clay in the sand, the kit on the rack, the
weighing, the missions, and now the GATEHOUSE that stands before the Forge's one
door out. It reaches the rest as a client, the way everything in this estate
reaches: it knocks on the Forge's door for the fire, and on Steward's door for
reasoning and, through him alone, sealed Manjuel's rulings. It never touches
Manjuel's process, never Steward's, never the Forge's. It only asks.

  /board/sand      the clay in the fire — the littles a mission may move
  /board/kit       the rack, live
  /board/weigh     the board's read on the toolstack
  /board/missions  every mission's story: directed, gated, run, reviewed
  /board/deploy    load a mission -> the pack serves it -> observe the result
  /board/root      GET the delegation root; POST to move it (the operator's leash)
  /delegate        the ONE door — routed through the four gates, never blind
  /shape /run …    proxied to the Forge — the fire stays the Forge's alone
  /ask_steward     proxied to Steward — his reasoning
  /ask_manjuel     proxied to Steward -> sealed Manjuel, never his process direct
"""
import http.server, json, os, hmac, secrets, urllib.request

try:
    import board as _board
    import assault_pack as _pack
except Exception:
    _board = _pack = None

import delegation as _gate     # the delegation wall — pure, reaches nothing

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 7376                                  # the board's own port (steward 7374, forge 7375)
FORGE = "http://127.0.0.1:7375"              # the fire, spoken to as a client
STEWARD = "http://127.0.0.1:7374"            # the gateway, spoken to as a client
SAND = os.path.join(HERE, "forge_sand")
TOKEN_FILE = os.path.join(HERE, "board_token.txt")
os.makedirs(SAND, exist_ok=True)


def _token():
    try:
        t = open(TOKEN_FILE).read().strip()
        if t:
            return t
    except Exception:
        pass
    t = secrets.token_hex(32)
    open(TOKEN_FILE, "w").write(t)
    return t


TOKEN = _token()

# The board witnesses each figure's source as it passes through on the way to the
# fire — it is already the messenger. Held only in memory, keyed by figure id, so
# that when the operator carries one out, the board can carry its TRUE source to
# Manjuel for a doctrine ruling. Nothing is written; when the board rests, it forgets.
CODE_SEEN = {}
NAME_SEEN = {}


# --- reaching the finished pieces, from outside, as a client --------------
def _peer_token(fname):
    """Read a peer's token file to knock on its door. The board holds no share of a
    peer's memory; it authenticates as any client would, and nothing more."""
    try:
        return open(os.path.join(HERE, fname)).read().strip()
    except Exception:
        return ""


def _proxy(base, path, payload, token_header, token_file):
    """Carry one POST to a peer and hand back its JSON, unchanged. Here the board is
    only a faithful messenger: it carries the operator's ask to the door that
    answers it, and carries the answer back. Its own thinking is reserved for its
    own work — the reads below, and the gatehouse."""
    try:
        req = urllib.request.Request(
            base + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", token_header: _peer_token(token_file)})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": "%s unreachable: %s" % (base, e)}


# --- the board's own reads (its own area; nothing here reaches outward) ----
def sand_clay():
    """The clay in the fire — every little and figure the sand holds, named the way
    a mission would call it. A mission moves clay by this exact name, so what is
    listed here is precisely what the pack's finder will resolve: no guessing, no
    drift, and never the empty name that would match the first thing at random."""
    names = []
    if os.path.isdir(SAND):
        for fn in sorted(os.listdir(SAND)):
            if fn.endswith(".py"):
                names.append(fn[:-3])
    return {"clay": names, "count": len(names)}


def _read_jsonl(path):
    if not path or not os.path.exists(path):
        return []
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def _step(steps, name):
    """A run_mission log is a list of one-key dicts, in order. Pull one step's value
    by name, or None if the mission never reached it."""
    for s in steps:
        if name in s:
            return s[name]
    return None


def missions_view(limit=30):
    """Every mission's whole story, joined from the board's own honest records: the
    direction dropped in the inbox (the plan) and the result left on the out-tray
    (what happened). Newest first, the way the eye reads. This reveals the record;
    it never writes it — the inbox and out-tray remain the only authors of truth."""
    if not _board:
        return {"missions": [], "total": 0}
    inbox = _read_jsonl(_board.INBOX)
    results = {r["ticket"]: r for r in _read_jsonl(_board.OUTTRAY) if r.get("ticket")}
    missions = []
    for order in reversed(inbox):
        ticket = order.get("ticket")
        res = (results.get(ticket) or {}).get("result", {})
        steps = res.get("steps", [])
        review = _step(steps, "after_review") or {}
        outcome = res.get("outcome", "")
        held = outcome.startswith("HELD") or outcome.startswith("HALTED")
        missions.append({
            "ticket": ticket,
            "purpose": order.get("purpose", ""),
            "t": order.get("t", ""),
            "scope": order.get("scope", ""),
            "tools": order.get("tools", []),
            "littles": order.get("littles", []),
            "minutes": order.get("minutes"),
            "gate": {"verdict": "REFUSED" if held else ("CLEARED" if outcome else "—"),
                     "refusals": [outcome] if held else []},
            "outcome": outcome or "(waiting on the board)",
            "success_rate": review.get("success_rate"),
            "where_worse": review.get("where_worse"),
        })
    return {"missions": missions[:limit], "total": len(inbox)}


def deploy(purpose, scope, tools, littles, minutes):
    """Load a mission and let the pack serve it. The board directs and is decoupled
    the instant it does; the pack picks the direction up, runs it under the gates,
    and leaves the result to be observed. One call carries load -> motion -> result.

    It refuses an unnamed little on purpose: a mission moves clay by name, not by
    chance, so a blank name is turned away rather than matching the first figure it
    finds. That refusal is the small honest wall that keeps deploy legible."""
    if not (_board and _pack):
        return {"error": "board/pack not loaded"}
    clean = [l for l in littles if str(l).strip()]
    if not clean:
        return {"error": "no little named — a mission moves clay by name, not by chance"}
    ticket = _board.direct(purpose, scope or "read-only; the garden only",
                           tools, clean, minutes, by="steward")
    ran = _pack.serve_board(once=True)
    return {"deployed": ticket, "ran": ran, "results": _board.observe_results(limit=1)}


# --- THE GATEHOUSE — the four gates before the Forge's one door ------------
def carry_out(body):
    """The gatehouse before the one door. The Forge still owns the door; the board
    decides whether it may open, and onto WHERE. Four gates, in order, and the first
    that holds ends it:

      1  SCOPE          the destination must sit inside the sanctioned root — the
                        leash the door never had. os.path.abspath resolves '..'
                        first, so nothing escapes the root by traversal.
      2  OPERATOR       only the operator carries fire out (the Forge's one law).
      3  SHOWN WORKING  the figure must RUN CLEAN in the fire right now — shown
                        working, never 'should work'.
      4  DOCTRINE       the figure's own source is carried to sealed Manjuel; his
                        ruling is recorded for the operator to read, and holds the
                        door only on an explicit refusal. Manjuel judges; he never
                        acts; the operator's confirm is what actually opens it.

    Only when all four clear does the board hand the Forge a VETTED path — the safe
    absolute path inside the root — and let its one door write. The Forge is never
    touched; it is simply never reached except through here."""
    fid = body.get("id", "")
    record = {"gates": []}

    def held(gate, why):
        record["gates"].append({"gate": gate, "passed": False, "detail": why})
        return {"delegated": False, "error": why, "record": record}

    def cleared(gate, detail):
        record["gates"].append({"gate": gate, "passed": True, "detail": detail})

    # GATE 1 — the wall: where is this allowed to land?
    ok, safe, detail = _gate.within_root(body.get("destination", ""))
    if not ok:
        return held("1_SCOPE", "refused — %s" % detail)
    cleared("1_SCOPE", "lands inside the root: %s" % safe)

    # GATE 2 — the one law: only the operator carries fire out.
    if not bool(body.get("operator_confirm")):
        return held("2_OPERATOR", "refused — only the operator may carry a figure out of the fire")
    cleared("2_OPERATOR", "operator confirmed")

    # GATE 3 — shown working, never 'should work': run it in the fire, require clean.
    run = _proxy(FORGE, "/run", {"id": fid}, "X-Forge-Token", "forge_token.txt")
    rr = (run or {}).get("run") or {}
    if rr.get("exit") != 0:
        return held("3_SHOWN_WORKING", "refused — did not run clean in the fire (exit=%s)" % rr.get("exit"))
    cleared("3_SHOWN_WORKING", "ran clean in the fire, exit 0")

    # GATE 4 — the conscience: carry the figure's own source to sealed Manjuel.
    name = NAME_SEEN.get(fid, fid)
    code = CODE_SEEN.get(fid)
    if code:
        q = ("the operator would carry a forged figure out of the fire and make it real. "
             "it ran clean. its name is %s. this is what it does, in its own code:\n\n%s\n\n"
             "does making this real honor the doctrine?" % (name, code[:1500]))
    else:
        q = ("the operator would carry a forged figure named %s out of the fire and make it "
             "real; it ran clean, but the board did not witness its source. does making it real "
             "honor the doctrine, and what should the operator check first?" % name)
    ruling = (_proxy(STEWARD, "/manjuel/chat", {"message": q},
                     "X-Steward-Token", "steward_token.txt") or {}).get("reply", "")
    record["ruling"] = ruling
    refusal = ("i refuse", "refuse to", "this violates", "violates the", "must not be made",
               "may never be", "i cannot honor", "dishonor")
    if any(w in ruling.lower() for w in refusal):
        return held("4_DOCTRINE", "held by the conscience: %s" % ruling[:200])
    cleared("4_DOCTRINE", "the conscience did not refuse; ruling recorded")

    # ALL GATES CLEARED — hand the Forge a vetted path and let its one door write.
    out = _proxy(FORGE, "/delegate",
                 {"id": fid, "destination": safe, "operator_confirm": True},
                 "X-Forge-Token", "forge_token.txt")
    if isinstance(out, dict):
        out["record"] = record
    return out


# --- the board's own server -----------------------------------------------
#  The fire is proxied to the Forge; reasoning to Steward. The one door out is
#  gated here first. Everything else the board answers from its own record. One
#  origin, one window — the console never has to know there are servers behind it.
_FIRE = {"/shape", "/run", "/remold", "/smooth"}   # /delegate is NOT here — it is gated


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Forge-Token")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def _auth(self):
        # The console names its key "X-Forge-Token" because it was first written for
        # the Forge. Here that key is the BOARD's own token — the board serves the
        # console, so the board's key opens it. The name is the console's; the key
        # is ours. Same handshake, honestly labeled.
        return hmac.compare_digest(self.headers.get("X-Forge-Token", ""), TOKEN)

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if self.path in ("/", "/board", "/console"):
            try:
                html = open(os.path.join(HERE, "console.html"), encoding="utf-8").read()
                html = html.replace("__FORGE_TOKEN__", TOKEN)
            except Exception as e:
                html = "<h1>the board face is missing</h1><p>%s</p>" % e
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            return
        if self.path == "/ping":
            self._send({"status": "BOARD_ONLINE", "port": PORT,
                        "speaks_to": {"forge": FORGE, "steward": STEWARD}})
        elif self.path == "/board/sand":
            self._send(sand_clay())
        elif self.path == "/board/kit":
            self._send(_board.inventory() if _board else {"tools": [], "count": 0})
        elif self.path == "/board/weigh":
            self._send(_board.weigh() if _board else {"assessment": []})
        elif self.path == "/board/results":
            self._send(_board.observe_results(limit=8) if _board else {"results": []})
        elif self.path == "/board/missions":
            self._send(missions_view())
        elif self.path == "/board/root":
            self._send({"root": _gate.get_root()})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth():
            self._send({"error": "unauthorized — the operator's key opens the board"}, 401); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._send({"error": "bad json"}, 400); return

        if self.path == "/board/deploy":
            self._send(deploy(body.get("purpose", ""), body.get("scope", ""),
                              body.get("tools", []), body.get("littles", []),
                              int(body.get("minutes", 2))))
        elif self.path == "/board/root":
            # the operator moves the leash — the one setting that widens or narrows
            # where fire may ever land. The board records it; it never sets it itself.
            self._send(_gate.set_root(body.get("dir", "")))
        elif self.path == "/delegate":
            # the one door out — through the gatehouse, never blind
            self._send(carry_out(body))
        elif self.path in _FIRE:
            # witness the source on its way to the fire, then carry the ask through
            resp = _proxy(FORGE, self.path, body, "X-Forge-Token", "forge_token.txt")
            if self.path == "/shape" and isinstance(resp, dict) and resp.get("id"):
                CODE_SEEN[resp["id"]] = body.get("code", "")
                NAME_SEEN[resp["id"]] = resp.get("name", body.get("name", ""))
            elif self.path == "/remold" and body.get("id"):
                CODE_SEEN[body["id"]] = body.get("code", "")
            self._send(resp)
        elif self.path == "/ask_steward":
            self._send(_proxy(STEWARD, "/investigate",
                       {"task": body.get("task", ""),
                        "models": body.get("models", ["llama3.2:3b-instruct-q4_K_M"]),
                        "angles": body.get("angles", [body.get("task", "")])},
                       "X-Steward-Token", "steward_token.txt"))
        elif self.path == "/ask_manjuel":
            # reach sealed Manjuel THROUGH Steward — never his process directly
            self._send(_proxy(STEWARD, "/manjuel/chat", {"message": body.get("message", "")},
                       "X-Steward-Token", "steward_token.txt"))
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    print("[board] online :%d — the mission loader, and the gatehouse before the one door." % PORT)
    print("[board] delegation root: %s" % _gate.get_root())
    print("[board] reaches the Forge at %s and Steward at %s as a client" % (FORGE, STEWARD))
    print("[board] token in %s" % os.path.basename(TOKEN_FILE))
    http.server.HTTPServer(("127.0.0.1", PORT), H).serve_forever()
