#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
THE FORGE — its own place, its own process. Standalone.

Manjuel is finished. Steward is finished. The Forge does not live inside either
of them and never edits them. It stands on its own port and speaks to Steward's
finished API from the outside, exactly as any client would — to reach Steward's
reasoning and, through him, sealed Manjuel's rulings. It never reaches into
their processes; it only asks, over the wire they already expose.

The Forge is the returned tool-place, set aside long ago until the other two
were ready. It is where real tools are made — a test bench, an imagination, and
a forge in the old sense, where fire makes things with a true edge. Dangerous by
nature, and safe by one law only: nothing leaves the fire except by the
operator's own hand.

  shape / run / remold / smooth   disposable figures, pure code, no cost
  manual                          the Forge's own doctrine, read on demand
  ask_steward / ask_manjuel       reach the finished pieces from outside
  delegate                        the ONE door out — operator confirm required
"""
import http.server, json, os, hmac, secrets, subprocess, sys, shutil, time, urllib.request
try:
    import board as _board
    import assault_pack as _pack
except Exception:
    _board = _pack = None

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 7375                                  # the Forge's own port (steward is 7374)
STEWARD = "http://127.0.0.1:7374"            # the finished gateway, spoken to as a client
SAND = os.path.join(HERE, "forge_sand")
FOUNDATION_DIR = os.path.join(HERE, "forge_foundation")
TOKEN_FILE = os.path.join(HERE, "forge_token.txt")
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


# --- the Forge's own doctrine (F1_THE_FORGE.md) ---------------------------
FOUNDATION = {}


def load_foundation():
    if os.path.isdir(FOUNDATION_DIR):
        for fn in sorted(os.listdir(FOUNDATION_DIR)):
            if fn.endswith(".md"):
                FOUNDATION[fn] = open(os.path.join(FOUNDATION_DIR, fn), encoding="utf-8").read()
    return len(FOUNDATION)


def manual(topic=""):
    if not topic:
        return {"documents": list(FOUNDATION.keys()), "text": next(iter(FOUNDATION.values()), "")}
    hits = []
    for name, text in FOUNDATION.items():
        for para in text.split("\n\n"):
            if topic.lower() in para.lower() and len(para.strip()) > 30:
                hits.append({"source": name, "passage": para.strip()[:500]})
    return {"documents": list(FOUNDATION.keys()), "matches": hits[:3]}


# --- speaking to the finished pieces, from outside, as a client -----------
def _steward_token():
    """The Forge reads Steward's token file to authenticate as a client — it does
    not share Steward's memory, it just knocks on his door like anyone else."""
    try:
        return open(os.path.join(HERE, "steward_token.txt")).read().strip()
    except Exception:
        return ""


def ask_steward(path, payload):
    try:
        req = urllib.request.Request(STEWARD + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Steward-Token": _steward_token()})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": "steward unreachable: %s" % e}


# --- the sand: disposable figures -----------------------------------------
class Figure:
    garden = {}

    def __init__(self, name, code):
        self.id = secrets.token_hex(5)
        self.name = name or ("figure_" + self.id)
        self.code = code
        self.runs = []
        self.shaped_at = time.strftime("%H:%M:%S")
        Figure.garden[self.id] = self

    def path(self):
        return os.path.join(SAND, self.name + "_" + self.id + ".py")

    def shape(self):
        open(self.path(), "w", encoding="utf-8").write(self.code)
        return self.path()

    def run(self):
        self.shape()
        try:
            r = subprocess.run([sys.executable, self.path()], cwd=SAND,
                               capture_output=True, text=True, timeout=30)
            out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
            rec = {"at": time.strftime("%H:%M:%S"), "exit": r.returncode, "output": out.strip()[:2000]}
        except Exception as e:
            rec = {"at": time.strftime("%H:%M:%S"), "exit": None, "output": "error: %s" % e}
        self.runs.append(rec)
        return rec

    def smooth(self):
        try:
            os.remove(self.path())
        except OSError:
            pass
        Figure.garden.pop(self.id, None)


def delegate(fid, destination, operator_confirm=False):
    """The one door out of the fire. Only the operator opens it. Without explicit
    confirmation it refuses, every time — nothing becomes real by any judgment
    but the operator's own act."""
    f = Figure.garden.get(fid)
    if not f:
        return {"delegated": False, "error": "no such figure in the sand"}
    if not operator_confirm:
        return {"delegated": False, "error": "refused — only the operator may carry a figure out of the Forge"}
    dest = os.path.abspath(destination)
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        open(dest, "w", encoding="utf-8").write(f.code)
        return {"delegated": True, "from": f.name, "to": dest,
                "note": "the operator carried this out of the fire; it is real now"}
    except Exception as e:
        return {"delegated": False, "error": "could not delegate: %s" % e}


# --- the Forge's own server -----------------------------------------------
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
        return hmac.compare_digest(self.headers.get("X-Forge-Token", ""), TOKEN)

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if self.path == "/" or self.path == "/forge":
            try:
                html = open(os.path.join(HERE, "console.html"), encoding="utf-8").read()
                html = html.replace("__FORGE_TOKEN__", TOKEN)
            except Exception as e:
                html = "<h1>the forge face is missing</h1><p>%s</p>" % e
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            return
        if self.path == "/ping":
            self._send({"status": "FORGE_ONLINE", "port": PORT,
                        "speaks_to_steward": STEWARD, "doctrine": list(FOUNDATION.keys())})
        elif self.path.startswith("/manual"):
            topic = self.path.split("?", 1)[1].replace("topic=", "") if "?" in self.path else ""
            self._send(manual(topic))
        elif self.path == "/sand":
            self._send({"figures": [{"id": f.id, "name": f.name, "runs": len(f.runs)}
                                    for f in Figure.garden.values()]})
        elif self.path == "/board/kit":
            # the assault pack / inventory — the operator's loadout, live
            self._send(_board.inventory() if _board else {"tools": [], "count": 0})
        elif self.path == "/board/weigh":
            # the board's smarts — its read on the toolstack
            self._send(_board.weigh() if _board else {"assessment": []})
        elif self.path == "/board/results":
            # mission out-tray — what steward would observe
            self._send(_board.observe_results(limit=8) if _board else {"results": []})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth():
            self._send({"error": "unauthorized — the operator's key opens the Forge"}, 401); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self._send({"error": "bad json"}, 400); return

        if self.path == "/shape":
            f = Figure(body.get("name", ""), body.get("code", ""))
            f.shape()
            self._send({"id": f.id, "name": f.name})
        elif self.path == "/run":
            f = Figure.garden.get(body.get("id", ""))
            self._send({"error": "no such figure"} if not f else {"id": f.id, "run": f.run()})
        elif self.path == "/remold":
            f = Figure.garden.get(body.get("id", ""))
            if not f:
                self._send({"error": "no such figure"})
            else:
                f.code = body.get("code", ""); f.shape()
                self._send({"id": f.id, "remolded": True})
        elif self.path == "/smooth":
            f = Figure.garden.get(body.get("id", ""))
            if f: f.smooth()
            self._send({"smoothed": True})
        elif self.path == "/delegate":
            self._send(delegate(body.get("id", ""), body.get("destination", ""),
                                bool(body.get("operator_confirm"))))
        elif self.path == "/ask_steward":
            # reach the finished Steward from outside — his research/reasoning
            self._send(ask_steward("/investigate", {"task": body.get("task", ""),
                       "models": body.get("models", ["llama3.2:3b-instruct-q4_K_M"]),
                       "angles": body.get("angles", [body.get("task", "")])}))
        elif self.path == "/ask_manjuel":
            # reach sealed Manjuel THROUGH finished Steward — never his process directly
            self._send(ask_steward("/manjuel/chat", {"message": body.get("message", "")}))
        elif self.path == "/board/deploy":
            # STEWARD directs: drop a mission on the board, then the pack serves it.
            # The console is the operator watching this happen.
            if not (_board and _pack):
                self._send({"error": "board/pack not loaded"}); return
            t = _board.direct(body.get("purpose",""), body.get("scope",""),
                              body.get("tools",[]), body.get("littles",[]),
                              int(body.get("minutes",2)), by="steward")
            ran = _pack.serve_board(once=True)
            self._send({"deployed": t, "ran": ran,
                        "results": _board.observe_results(limit=1)})
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    load_foundation()
    print("[forge] online :%d — the place. Doctrine: %s" % (PORT, list(FOUNDATION.keys())))
    print("[forge] speaks to finished Steward at %s (never edits him)" % STEWARD)
    print("[forge] token in %s" % os.path.basename(TOKEN_FILE))
    http.server.HTTPServer(("127.0.0.1", PORT), H).serve_forever()
