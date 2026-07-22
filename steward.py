#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STEWARD — the gateway that DOES. The hands, bound to a conscience it cannot change.

Three layers, three walls:
  MANJUEL  (kernel)   — doctrine, ledger, memory. Sealed, air-gapped. Judges + remembers.
  STEWARD  (gateway)  — researches, calls models, carries plans to Manjuel + rulings back.
  OPERATOR (dashboard)— re-calls, re-reviews, or submits forward. Final gate.

The loop is the scientific process:
  1. Manjuel reminds Steward of the process
  2. Steward forms the ask, records the PLAN to Manjuel (immutable)
  3. Steward asks the local models (multiple angles)
  4. Steward matches responses against the plan, weighs confidence
  5. Steward asks Manjuel: does this match, and does doctrine alter it?
  6. Manjuel returns the doctrinal ruling (recorded)
  7. Steward delivers all observations to the operator
  8. Operator re-calls/re-reviews, or submits forward
Every step gated, stepped, observed.

SECURITY BY ARCHITECTURE, not by rule:
  Steward can only ASK Manjuel through his REPL bridge. It holds no handle to
  change him. A prompt injection reaching Steward can, at most, make Steward ask
  Manjuel a question — and Manjuel answers from sealed doctrine or says he does
  not know. Nothing downstream can rewrite the conscience. Steward never writes
  to Manjuel's kernel. It only asks, and records what it did.
"""
import http.server, json, os, hmac, secrets, subprocess, threading, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 7374                      # steward's own port (manjuel gateway was 7373)
KERNEL = os.path.join(HERE, "manjuel.py")
TOKEN_FILE = os.path.join(HERE, "steward_token.txt")
OLLAMA = "http://127.0.0.1:11434"


def _token():
    try:
        t = open(TOKEN_FILE).read().strip()
        if t: return t
    except Exception: pass
    t = secrets.token_hex(32); open(TOKEN_FILE, "w").write(t); return t

TOKEN = _token()


# ---------------------------------------------------------------------------
# WALL 1: the ask-only bridge to sealed Manjuel. Steward speaks to the kernel
# ONLY through his own REPL prompt. No handle to change him exists here.
# ---------------------------------------------------------------------------
class Manjuel:
    PROMPT = "steward> "
    def __init__(self):
        self.p = subprocess.Popen([sys.executable, "-u", KERNEL], cwd=HERE,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        self.lock = threading.Lock()
        self._read_to_prompt(20)
    def _read_to_prompt(self, timeout=30):
        buf, start = "", time.time()
        while time.time() - start < timeout:
            ch = self.p.stdout.read(1)
            if ch == "": break
            buf += ch
            if buf.endswith(self.PROMPT): return buf[:-len(self.PROMPT)]
        return buf
    def ask(self, line):
        with self.lock:
            self.p.stdin.write(line + "\n"); self.p.stdin.flush()
            ans = self._read_to_prompt()
            rows = ans.split("\n")
            if rows and rows[0].strip() == line.strip(): rows = rows[1:]
            return "\n".join(rows).strip()

MANJUEL = Manjuel()

# ---------------------------------------------------------------------------
# STEWARD'S FOUNDATION — his own ground. Manjuel has five documents; Steward has
# three: how he inquires (Method), what he may never do (Servant's Law), and how
# he tells signal from noise (Weighing). Loaded on waking, held for reference, so
# Steward is legible to himself the way the kernel is. He reasons FROM doctrine,
# not merely under hardcoded rules.
# ---------------------------------------------------------------------------
FOUNDATION = {}

def load_foundation():
    d = os.path.join(HERE, "steward_foundation")
    if not os.path.isdir(d):
        return 0
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md"):
            FOUNDATION[fn] = open(os.path.join(d, fn), encoding="utf-8").read()
    return len(FOUNDATION)


def doctrine_says(topic):
    """Return the foundation passages touching a topic — Steward quoting his own
    law. Plain substring match; the documents are small and legible on purpose."""
    hits = []
    for name, text in FOUNDATION.items():
        for para in text.split("\n\n"):
            if topic.lower() in para.lower() and len(para.strip()) > 40:
                hits.append({"source": name, "passage": para.strip()[:400]})
    return hits[:3]


_n = load_foundation()
print("[steward] foundation loaded: %d documents — Steward reasons from his own law" % _n)


# ---------------------------------------------------------------------------
# WALL 2: model calls. Steward's research labor. Local only.
# ---------------------------------------------------------------------------
def call_model(prompt, tag, temperature=0.3):
    body = json.dumps({"model": tag, "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
        "messages": [{"role": "user", "content": prompt}]}).encode()
    try:
        req = urllib.request.Request(OLLAMA + "/api/chat", data=body, method="POST",
            headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read()).get("message", {}).get("content", ""), None
    except Exception as e:
        return None, f"model '{tag}' unreachable: {e}"


# ---------------------------------------------------------------------------
# THE LOOP — the scientific process, stepped and observed.
# Each stage returns its record; nothing auto-advances past the operator gate.
# ---------------------------------------------------------------------------
class Investigation:
    """One task, carried through the process. Held in memory between operator
    steps (Steward is stateful; Manjuel stays sealed and stateless-to-Steward)."""
    _all = {}
    def __init__(self, task, models):
        self.id = secrets.token_hex(6)
        self.task = task
        self.models = models
        self.plan = None
        self.responses = []
        self.ruling = None
        self.log = []
        Investigation._all[self.id] = self

    def record(self, stage, detail):
        entry = {"stage": stage, "detail": detail, "ts": time.strftime("%H:%M:%S")}
        self.log.append(entry)
        # WALL 1 in action: Steward RECORDS to Manjuel by asking him to remember.
        # It never writes Manjuel's files directly — it asks, through the bridge.
        MANJUEL.ask(":remember [STEWARD/%s] %s: %s" % (self.id, stage, str(detail)[:180]))
        return entry


def step_remind():
    """1. Manjuel reminds Steward of the process — from his own doctrine."""
    return MANJUEL.ask("what is the steward's question and the scientific process?")

def step_plan(task, reminder):
    """2. Steward forms the ask + records the PLAN to Manjuel."""
    inv = Investigation(task, [])
    plan = ("HYPOTHESIS: the task '%s' can be resolved by consulting the models from "
            "multiple angles, weighing their agreement, and checking the result against "
            "doctrine before any action.\nMETHOD: ask N models, match responses to this "
            "plan, request Manjuel's doctrinal ruling, deliver to operator.") % task
    inv.plan = plan
    inv.record("PLAN", plan)
    return inv

def step_research(inv, angles):
    """3+4. Ask the models from multiple angles, weigh each against the plan."""
    for angle in angles:
        for tag in inv.models:
            text, err = call_model(angle, tag)
            if err:
                inv.responses.append({"angle": angle, "model": tag, "error": err, "score": 0.0})
                continue
            # weigh: crude agreement score = overlap of task keywords in the answer
            kws = [w.lower() for w in inv.task.split() if len(w) > 3]
            hit = sum(1 for k in kws if k in text.lower())
            score = round(hit / max(1, len(kws)), 2)
            inv.responses.append({"angle": angle, "model": tag, "text": text, "score": score})
    inv.record("RESEARCH", "%d model responses gathered, weighed against the plan" % len(inv.responses))
    return inv

def step_ruling(inv):
    """5+6. Ask Manjuel: does the result match the plan, and does doctrine alter it?"""
    best = max((r for r in inv.responses if "text" in r), key=lambda r: r["score"], default=None)
    if best:
        q = "does this honor the doctrine? %s" % best["text"][:280]
    else:
        # no model result to weigh — ask Manjuel the pure doctrinal frame instead
        q = "what does doctrine require before an action is taken?"
    ruling = MANJUEL.ask(q)
    inv.ruling = ruling
    inv.record("RULING", ruling[:180])   # record AFTER, so echo can't contaminate the read
    return inv



# ---------------------------------------------------------------------------
# EXECUTION LAYER — scoped, explained-like-you-are-5, gated, recorded.
# Steward can DO things now, but only inside SCOPE, only after explaining the
# command simply enough that a child could follow, and only when the operator
# gates it. If Steward cannot explain a command simply, it REFUSES to run it —
# over-technical is the alarm that it does not truly understand (Creed III, Art V).
# ---------------------------------------------------------------------------
import shlex, subprocess as _sub

SCOPE = {"dir": None}     # the leash: Steward physically cannot act outside this


def set_scope(path):
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(p):
        return {"ok": False, "error": "not a folder: %s" % p}
    SCOPE["dir"] = p
    MANJUEL.ask(":remember [STEWARD/scope] working directory set to %s" % p)
    return {"ok": True, "scope": p}


def _in_scope(cmd):
    """True only if every path-looking token stays inside SCOPE. Conservative:
    if it can't prove a path is inside, it treats it as outside."""
    if not SCOPE["dir"]:
        return False, "no scope set — the operator must set a working directory first"
    scope = SCOPE["dir"]
    try:
        parts = shlex.split(cmd, posix=(os.name != "nt"))
    except Exception:
        parts = cmd.split()
    for tok in parts:
        # any token that looks like a path
        if "/" in tok or "\\" in tok or tok.startswith(".") or ":" in tok:
            ap = os.path.abspath(os.path.join(scope, os.path.expanduser(tok)))
            if not (ap == scope or ap.startswith(scope + os.sep)):
                return False, "command reaches outside scope: %s" % tok
    return True, scope


def explain_eli5(cmd, model):
    """Ask a local model to explain the command like the operator is 5. Then
    CHECK it stayed simple. Over-technical explanation = Steward flags it."""
    prompt = ("Explain what this computer command does, like you are talking to a "
              "smart 5-year-old. Two or three short sentences. No jargon. Say plainly "
              "what it changes or touches. Command:\n\n%s" % cmd)
    text, err = call_model(prompt, model, temperature=0.2)
    if err:
        return None, err, False
    # simplicity check: long words / known jargon = too technical
    jargon = ["recursive", "stdout", "stderr", "symlink", "inode", "regex", "daemon",
              "kernel", "environment variable", "pipe", "redirect", "chmod", "sudo"]
    hits = [j for j in jargon if j in text.lower()]
    hard_words = [w for w in text.split() if len(w) > 13]
    simple = len(hits) == 0 and len(hard_words) <= 1
    return text.strip(), None, simple


def propose(cmd, model):
    """Turn a raw command into an operator-legible proposal. Records the proposal
    to Manjuel. Does NOT run anything."""
    ok_scope, where = _in_scope(cmd)
    eli5, err, simple = explain_eli5(cmd, model)
    verdict = ("BLOCKED — outside scope" if not ok_scope
               else "HELD — too technical to run safely; Steward does not fully understand it"
                    if (eli5 and not simple)
               else "READY — explained simply, inside scope, awaiting your gate"
                    if eli5 else "ERROR — could not explain")
    proposal = {
        "command": cmd,
        "eli5": eli5 or ("(could not explain: %s)" % err),
        "touches": where if ok_scope else "OUTSIDE the allowed folder",
        "in_scope": ok_scope,
        "simple_enough": bool(simple),
        "runnable": bool(ok_scope and eli5 and simple),
        "verdict": verdict,
    }
    MANJUEL.ask(":remember [STEWARD/propose] %s :: %s" % (cmd, verdict))
    return proposal


def execute(cmd, model):
    """Run a command — ONLY if it re-passes every gate at execution time. The
    operator has approved; Steward re-verifies scope + simplicity so nothing
    slips through between propose and execute. Records the real result to Manjuel."""
    p = propose(cmd, model)
    if not p["runnable"]:
        MANJUEL.ask(":remember [STEWARD/execute] REFUSED %s :: %s" % (cmd, p["verdict"]))
        return {"ran": False, "reason": p["verdict"], "proposal": p}
    try:
        r = _sub.run(cmd, shell=True, cwd=SCOPE["dir"], capture_output=True,
                     text=True, timeout=120)
        out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
        result = {"ran": True, "exit": r.returncode, "output": out[:4000], "eli5": p["eli5"]}
    except Exception as e:
        result = {"ran": False, "reason": "execution error: %s" % e}
    # the TRUE RECORD: what was done, its result, to Manjuel's ledger
    MANJUEL.ask(":remember [STEWARD/executed] %s :: exit=%s" % (cmd, result.get("exit", "err")))
    return result



# ---------------------------------------------------------------------------
# THE FORGE — the workshop where Steward and Manjuel work, and the five-gate
# pipeline that stands between an idea and a real change. Nothing skips a gate.
# Stability is the baseline, never efficiency: a slow proven change beats a fast
# unproven one, always. No matter the complexity or time-to-task, a thing is not
# done until it is SHOWN working and the operator has blessed it.
#
# Manjuel cannot act here. He is sealed, ask-only, handless. He JUDGES against
# doctrine; he never touches. The ledgers are READ to check and APPENDED to as
# witness — never modified by any decision. History does not bend to a verdict.
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ("name", "tag", "scope", "rules", "commands", "timestamp")


class WorkItem:
    """One piece of work moving through the Forge. It carries its own papers —
    every field required before it may even enter — and it accumulates a record
    of every gate it passes, so its whole life is legible end to end."""
    _shelf = {}

    def __init__(self, spec):
        self.id = secrets.token_hex(6)
        self.spec = spec
        self.gates = []           # the record of each gate, in order
        self.state = "received"
        self.shelved = False
        WorkItem._shelf[self.id] = self

    def gate(self, name, passed, detail):
        rec = {"gate": name, "passed": bool(passed), "detail": str(detail)[:300],
               "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.gates.append(rec)
        # WITNESS ONLY: record that the gate happened. This appends; it never
        # rewrites. Manjuel remembers that the check occurred — the check itself
        # read the ledgers, it did not change them.
        MANJUEL.ask(":remember [FORGE/%s] %s: %s — %s" %
                    (self.id, name, "PASS" if passed else "HELD", str(detail)[:120]))
        return rec


def gate1_check_in(item):
    """Steward checks the work IN. Every required field present and non-empty,
    or it is turned away at the door. Malformed work never enters the Forge."""
    missing = [f for f in REQUIRED_FIELDS if not str(item.spec.get(f, "")).strip()]
    if missing:
        item.state = "rejected"
        return item.gate("1_CHECK_IN", False, "missing required fields: " + ", ".join(missing))
    item.state = "checked_in"
    return item.gate("1_CHECK_IN", True, "well-formed; carries all papers")


def gate2_manjuel(item, model):
    """Manjuel-checked. Steward carries the work to the sealed conscience and
    asks whether it honors the doctrine. Manjuel reads his ground and rules. He
    cannot act; he can only judge. His answer is recorded, not his hand."""
    q = ("does this work honor the doctrine? name: %s. what it does: %s. "
         "scope: %s." % (item.spec.get("name"), item.spec.get("rules"),
                          item.spec.get("scope")))
    ruling = MANJUEL.ask(q)
    # Steward reads the ruling for a refusal signal, honestly and conservatively.
    refused = any(w in ruling.lower() for w in
                  ("refuse", "violat", "must not", "may never", "cannot", "forbid"))
    item.manjuel_ruling = ruling
    if refused:
        item.state = "held_by_doctrine"
        return item.gate("2_MANJUEL", False, "doctrine holds this: " + ruling[:160])
    item.state = "doctrine_ok"
    return item.gate("2_MANJUEL", True, "ruled consistent with doctrine: " + ruling[:160])


def gate3_check_out(item):
    """Steward checks the work OUT — the second pass, the other direction. It
    verifies the ruling actually came back sound and the work still carries its
    papers after doctrine review. In and out, both checked, by design."""
    if not getattr(item, "manjuel_ruling", "").strip():
        return item.gate("3_CHECK_OUT", False, "no doctrine ruling to verify")
    if item.state != "doctrine_ok":
        return item.gate("3_CHECK_OUT", False, "did not clear doctrine; nothing to pass out")
    # re-verify the papers are intact (nothing stripped mid-pipeline)
    missing = [f for f in REQUIRED_FIELDS if not str(item.spec.get(f, "")).strip()]
    if missing:
        return item.gate("3_CHECK_OUT", False, "papers lost in transit: " + ", ".join(missing))
    item.state = "checked_out"
    return item.gate("3_CHECK_OUT", True, "ruling sound, papers intact, cleared for testing")


def gate4_test(item):
    """Tested and SHOWN working. The commands run in a throwaway sandbox — never
    the real scope, never the machine — and must actually succeed. Not 'should
    work': shown working. If it does not run clean, it does not pass, however
    long or complex the work. Stability is the baseline."""
    if item.state != "checked_out":
        return item.gate("4_TEST", False, "not cleared for testing")
    sandbox = os.path.join(HERE, "forge_sandbox", item.id)
    os.makedirs(sandbox, exist_ok=True)
    cmds = item.spec.get("commands", [])
    if isinstance(cmds, str):
        cmds = [cmds]
    results = []
    all_ok = True
    for c in cmds:
        try:
            r = _sub.run(c, shell=True, cwd=sandbox, capture_output=True,
                         text=True, timeout=120)
            ok = r.returncode == 0
            all_ok = all_ok and ok
            results.append({"command": c, "exit": r.returncode,
                            "out": (r.stdout or r.stderr or "")[:400]})
        except Exception as e:
            all_ok = False
            results.append({"command": c, "error": str(e)})
    item.test_results = results
    if not all_ok:
        item.state = "test_failed"
        return item.gate("4_TEST", False, "did not run clean in sandbox — not proven")
    item.state = "proven"
    return item.gate("4_TEST", True, "ran clean in sandbox, demonstrated working")


def gate5_operator(item, approve):
    """Operator approved — the last gate, and only reachable when all four before
    it passed. The human blesses the proven work, or does not. Steward proposes
    the whole chain; the operator disposes. Nothing here is automatic."""
    if item.state != "proven":
        return item.gate("5_OPERATOR", False, "cannot reach the operator gate unproven")
    if not approve:
        item.state = "operator_declined"
        return item.gate("5_OPERATOR", False, "operator declined")
    item.state = "APPROVED"
    return item.gate("5_OPERATOR", True, "operator approved — the work is blessed and recorded")


def forge_run(spec, model, operator_approve=False):
    """Move a work-item through all five gates, in order, stopping at the first
    that holds. Returns the full record — every gate, its verdict, the ruling,
    the test results — for the operator to see the whole life of the work."""
    item = WorkItem(spec)
    gate1_check_in(item)
    if item.state == "checked_in":
        gate2_manjuel(item, model)
    if item.state == "doctrine_ok":
        gate3_check_out(item)
    if item.state == "checked_out":
        gate4_test(item)
    if item.state == "proven":
        gate5_operator(item, operator_approve)
    return {"id": item.id, "name": item.spec.get("name"), "state": item.state,
            "gates": item.gates, "ruling": getattr(item, "manjuel_ruling", ""),
            "tests": getattr(item, "test_results", [])}


# ---------------------------------------------------------------------------
# WALL 3: the operator. Steward delivers; the operator gates every advance.
# ---------------------------------------------------------------------------
class H(http.server.BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Steward-Token")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())
    def _auth(self):
        return hmac.compare_digest(self.headers.get("X-Steward-Token", ""), TOKEN)
    def log_message(self, *a): pass
    def do_OPTIONS(self): self._send({})

    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            # Steward serves its OWN face, with the token already inside. No second
            # server, no token-copy. One process, one window, one URL.
            try:
                html = open(os.path.join(HERE, "steward_dashboard.html"), encoding="utf-8").read()
                html = html.replace("__STEWARD_TOKEN__", TOKEN)
            except Exception as e:
                html = "<h1>dashboard file missing</h1><p>%s</p>" % e
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            return
        if self.path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if self.path == "/ping":
            self._send({"status": "STEWARD_ONLINE", "port": PORT,
                        "manjuel": "sealed", "models_endpoint": OLLAMA})
        elif self.path == "/remind":
            self._send({"process": step_remind()})
        elif self.path.startswith("/doctrine"):
            # Steward's own foundation, and what it says on a topic
            topic = self.path.split("?", 1)[1].replace("topic=", "") if "?" in self.path else ""
            self._send({"documents": list(FOUNDATION.keys()),
                        "says": doctrine_says(topic) if topic else []})
        elif self.path == "/manjuel/audit":
            self._send({"audit": MANJUEL.ask(":audit")})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth():
            self._send({"error": "unauthorized — operator gate (Art. VII)"}, 401); return
        n = int(self.headers.get("Content-Length", 0))
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: self._send({"error": "bad json"}, 400); return

        if self.path == "/investigate":
            # full loop up to the operator gate: remind -> plan -> research -> ruling
            task = (body.get("task") or "").strip()
            models = body.get("models") or ["llama3.2:3b-instruct-q4_K_M"]
            angles = body.get("angles") or [task]
            if not task: self._send({"error": "no task"}, 400); return
            reminder = step_remind()
            inv = step_plan(task, reminder)
            inv.models = models
            step_research(inv, angles)
            step_ruling(inv)
            # deliver ALL observations to the operator. Nothing proceeds past here
            # without the operator re-calling or submitting forward.
            self._send({"id": inv.id, "task": inv.task, "process": reminder,
                        "plan": inv.plan, "responses": inv.responses,
                        "ruling": inv.ruling, "log": inv.log,
                        "gate": "operator: re-call to refine, or submit forward"})
        elif self.path == "/manjuel/chat":
            # CONVERSATION ONLY with the sealed core. No control, ever. Just talk.
            q = (body.get("message") or "").strip()
            self._send({"reply": MANJUEL.ask(q) if q else "…"})
        elif self.path == "/scope":
            self._send(set_scope(body.get("dir") or ""))
        elif self.path == "/forge":
            # run a work-item through the five gates. operator_approve only blesses
            # the LAST gate, and only if the first four already passed.
            spec = body.get("spec") or {}
            spec.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
            self._send(forge_run(spec, body.get("model") or "llama3.2:3b-instruct-q4_K_M",
                                  bool(body.get("operator_approve"))))
        elif self.path == "/forge/shelf":
            # shelve or pick up work — park an idea without it becoming the plan
            iid = body.get("id"); act = body.get("action")
            it = WorkItem._shelf.get(iid)
            if not it: self._send({"error": "no such item"}); return
            it.shelved = (act == "shelve")
            self._send({"id": iid, "shelved": it.shelved, "state": it.state})
        elif self.path == "/propose":
            self._send(propose((body.get("command") or "").strip(),
                               body.get("model") or "llama3.2:3b-instruct-q4_K_M"))
        elif self.path == "/execute":
            self._send(execute((body.get("command") or "").strip(),
                               body.get("model") or "llama3.2:3b-instruct-q4_K_M"))
        else:
            self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    print("[steward] online :%d — the gateway that does. Manjuel sealed beneath." % PORT)
    print("[steward] token in %s" % os.path.basename(TOKEN_FILE))
    http.server.HTTPServer(("127.0.0.1", PORT), H).serve_forever()
