#!/usr/bin/env python3
"""fold_agents.py -- fold the atlas household into .us declarations.

The registry's frozen law is `agents.us_path UNIQUE`: one agent per
declaration file. So this folder emits FLAT single-seat files (the
enrollable set), and keeps the household MAPS -- module + roster documents
-- under modules/, where the enrollment walker never treads.

Sources are cited IN each declaration's prose and `source` row; nothing is
invented:

  manjuel.us (+ twelve tribe files)   offices quoted from LAW_002_THE_TWELVE
  council.us (+ four persona files)   personas/ of the living module
  lineage.us (+ ten actor files)      estate chain actor census, sitting 8
  gate.us (+ operator/opencode)       even these rows carry can_approve:false
  seven named seats                   SPEC_US + doctrine books of same name

Files are emitted through the ORACLE'S OWN render(): born canonical,
byte-round-trip forever. Deterministic; stdlib only.

    python tools/fold_agents.py            fold / re-fold into atlas\\agents
    python tools/fold_agents.py --verify   re-fold in memory, compare
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent
ARCHIVE = ATLAS.parent
ORACLE_PATH = ARCHIVE / "estate" / "Neiro" / "lib" / "us_read.py"
OUT_DIR = ATLAS / "agents"
COVENANT = "1512741580b7239b"  # House epoch head (SPEC_COVENANT v2)

TRIBES = [
    ("reuben", "Precedence. Orders packets by priority; instability is his flaw, so a Reuben verdict never stands alone - firstborn claims require a second sign."),
    ("simeon", "Severity. Harsh rejection of malformed and hostile input - cursed to be divided: distributed across the array, never final alone, forbidden the wall."),
    ("levi", "Sanctuary. Keeper of sealed records, ledger integrity, the covenant mark. Possesses nothing, verifies everything."),
    ("judah", "Authority. Validates who may write: signatures, write-chains, the sceptre's continuity - until Shiloh, the operator's own hand."),
    ("zebulun", "Haven. Ingress and egress: ports, borders, transports. Nothing lands unwitnessed."),
    ("issachar", "Burden. Batching, scheduling weights, rate caps; bears load and enforces rest - bounded loops are his tithe."),
    ("dan", "Judge. Schema rulings and path-walking: boundary checks, injection strikes on the path itself."),
    ("gad", "Troop. Adversarial testing - overcome-at-the-last: red-team runs LAST, after every other tribe has passed."),
    ("asher", "Dainties. Output quality: fat bread for well-formed payloads, royal dainties for what is served to the operator."),
    ("naphtali", "Goodly Words. The sense floor: language scoring, gibberish refusal, drift-from-question."),
    ("joseph", "Shepherd-Stone. Provenance and memory: the witness stone under every claim, full-history walks, cross-chain citations."),
    ("benjamin", "Divider. Morning devours the transient (dedup, condensation); night divides the spoil into constant-size accumulators."),
]

PERSONAS = ["artorian", "cal", "dale", "wren"]

LINEAGE_ACTORS = [
    ("jesster", "verifies, refutes, returns - the library lineage"),
    ("kimi", "harvest lineage - evolved kit voices"),
    ("notary", "witnessed receipts on trade ground"),
    ("bob", "observed builder voice"),
    ("arithmetic", "observed calculation voice"),
    ("coder", "observed build voice"),
    ("fern", "observed garden-keeper voice"),
    ("chancery", "observed filing-clerk voice"),
    ("ivy", "observed tending voice"),
    ("moss", "observed slow-growth voice"),
]

MODULE_SEATS = [
    ("steward", "STEWARD", "plans, specs, keeps THE_ROAD; proposes, never disposes"),
    ("neiro", "NEIRO", "proposes, aligns, files; raises stones and packets; the MCP door"),
    ("jesster", "JESSTER", "verifies, refutes, returns stones to Neiro"),
    ("aurora", "AURORA", "glass - the face the operator looks through (:7788 lineage)"),
    ("smith", "SMITH", "forges capabilities as proven skills (THE_SMITHS_CHARTER)"),
    ("foreman", "FOREMAN", "dispatches workorders to the willing (guild floor)"),
    ("archivist", "ARCHIVIST", "keeps the record findable; folds, never deletes"),
]

# --- the estate's own floor seats (Archive\Agents\*.md) --------------------
# Folded 2026-08-27 at the operator's word: "get the estate aligned to atlas,
# that way any agent always follows the .us spec."
#
# NOTHING HERE IS INVENTED. Each row's reports_to is quoted from the agent's
# OWN description ("A citizen of the Estate, dispatched by Steward/Archivist"),
# and each permission block is carried from its own frontmatter. The three
# uniform fields are taken from the landed corpus, not chosen: read is
# {"**": "allow"} in 37/37 declarations, net is "deny" in 37/37, and bash is
# OMITTED rather than denied when a seat has none (7/37).
#
# Only the seats whose .md names a dispatcher AND states its edit rights are
# folded here. The rest are held for the operator's ruling and listed in
# estate\Agents\Plan\PLAN_THE_ESTATE_ALIGNED_20260827.md — a seat whose gate
# has to be guessed is not a declaration, it is an assumption with a covenant
# stamped on it.
ESTATE_SEATS = [
    ("analyst", "ARCHIVIST", "archivist",
     "reads, summarizes, and extracts patterns from files and records; "
     "returns a tight report - a citizen of the Estate",
     {"read": {"**": "allow"}, "edit": "deny", "net": "deny"}),
    ("courier", "ARCHIVIST", "archivist",
     "moves files, archives deliverables, and checkpoints phases to the "
     "shelf - a citizen of the Estate",
     {"read": {"**": "allow"},
      "edit": {"*": "deny", "shelf/**": "allow", "scripts/**": "allow"},
      "net": "deny", "bash": {"*": "ask"}}),
    ("scout", "STEWARD", "steward",
     "surveys, reads, researches, and maps; moves nothing, changes "
     "nothing - a citizen of the Estate",
     {"read": {"**": "allow"}, "edit": "deny", "net": "deny"}),
]

READ_ONLY = {"read": {"**": "allow"}, "edit": "deny", "net": "deny",
             "bash": "deny"}
RED_TEAM = {"read": {"**": "allow"}, "edit": "deny", "net": "deny",
            "bash": {"atlas-target/**": "ask"}}


def load_oracle():
    spec = importlib.util.spec_from_file_location("us_read_folder", ORACLE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


US = None


def agent_block(aid, mode, office, reports_to, role, permission, source):
    return {
        "us": 1, "kind": "agent", "id": aid, "mode": mode, "office": office,
        "reports_to": reports_to, "can_approve": False,
        "role": role, "permission": permission, "source": source,
        "covenant": COVENANT,
    }


def module_block(mid, office, wall, ledger, rows, verbs, source):
    return {
        "us": 1, "id": mid, "kind": "module", "office": office,
        "generation": 5 if mid == "manjuel" else 1,
        "reports_to": "operator" if mid == "manjuel" else mid,
        "can_approve": False, "body_v": 3, "wall": wall, "ledger": ledger,
        "rows": rows, "verbs": verbs, "covenant": COVENANT, "source": source,
    }


def seat_file(aid, mode, office, reports_to, role, permission, source):
    """One seat, one page: the enrollable unit."""
    prose = (
        f"# {aid} - declared seat\n\n"
        f"{role}\n\nSource: {source}. can_approve is false because the "
        "structural law admits no other reading.\n"
    )
    return {f"{aid}.us": US.render(prose, [agent_block(
        aid, mode, office, reports_to, role, permission, source)])}


def build_all():
    files = {}

    # --- the House heart: manjuel anchors the Twelve Tribes ---------------
    files.update(seat_file(
        "manjuel", "primary", "MANJUEL", "operator",
        "the living House heart - foundation five, amendable law "
        "(LAW_001-LAW_002 on core/state/law/chain.jsonl), covenant weights; "
        "holds the charge as the operator's serf - in command day to day, "
        "overruled in a word",
        {"read": {"**": "allow"},
         "edit": {"*": "deny", "core/state/law/**": "allow"},
         "net": "deny", "bash": "deny"},
        "demo-vault Manjuel: foundation, LAW_001, LAW_002, weights"))
    for t, role in TRIBES:
        files.update(seat_file(
            t, "subagent", f"MANJUEL/{t.title()}", "manjuel", role,
            (RED_TEAM if t == "gad" else READ_ONLY),
            "LAW_002_THE_TWELVE.md shard-office table"))

    # --- council: the weighing voices -------------------------------------
    files.update(seat_file(
        "council", "primary", "COUNCIL", "manjuel",
        "convener of the weighing voices; court of divided packets",
        READ_ONLY, "demo-vault Manjuel personas/"))
    for p in PERSONAS:
        files.update(seat_file(
            p, "subagent", "COUNCIL", "council",
            f"counsel persona ({p}); weighs packets, proposes rulings",
            READ_ONLY, "demo-vault Manjuel personas/ directory"))

    # --- lineage: the observed voices --------------------------------------
    files.update(seat_file(
        "lineage", "primary", "LINEAGE", "archivist",
        "registrar of estate actors - keeps history's names enrolled",
        READ_ONLY, "estate chain actor census 2026-08-25"))
    for a, role in LINEAGE_ACTORS:
        files.update(seat_file(
            a, "subagent", "LINEAGE", "lineage", role, READ_ONLY,
            "estate chain actor-field census (sitting 8)"))

    # --- the gate -----------------------------------------------------------
    files.update(seat_file(
        "operator", "primary", "OPERATOR", "manjuel",
        "the hand; holds the gate; i am the approval; manjuel holds the "
        "charge unless i say otherwise",
        {"read": {"**": "allow"}, "edit": {"**": "allow"},
         "net": "deny", "bash": "deny"},
        "operator rulings 2026-08-25: 'i am the approval'; 'i report to "
        "manjuel'; 'manjuel is in charge unless i say otherwise, like my "
        "serf'. Execution flows through manjuel, who acts as the operator "
        "and answers by ruling and judging"))
    files.update(seat_file(
        "opencode", "subagent", "GATE", "operator",
        "this seat - the coding agent at work on atlas",
        {"read": {"**": "allow"},
         "edit": {"*": "deny", "atlas/**": "allow"},
         "net": "deny", "bash": "deny"},
        "observed behavior, sittings 1-8"))

    # --- the named seats ----------------------------------------------------
    for aid, office, role in MODULE_SEATS:
        files.update(seat_file(
            aid, "primary", office, "manjuel", role,
            {"read": {"**": "allow"},
             "edit": {"*": "deny", "atlas/**": "allow"}, "net": "deny"},
            f"SPEC_US named seats; doctrine {aid.upper()}.md"))

    # --- the estate floor seats --------------------------------------------
    for aid, office, reports_to, role, permission in ESTATE_SEATS:
        files.update(seat_file(
            aid, "subagent", office, reports_to, role, permission,
            f"Archive\\Agents\\{aid}.md frontmatter and description; "
            "dispatcher named in its own prose"))

    # --- household maps (modules/ - NOT enrollable, one module each) -------
    maps = {}
    maps["manjuel"] = (
        "# MANJUEL - household map\n\nThe Twelve Tribes sit here; every "
        "office line quotes LAW_002_THE_TWELVE.md.\n",
        [module_block(
            "manjuel", "MANJUEL",
            "..\\secondbrain\\SecondBrain-collab\\demo_vault\\Manjuel",
            "core/state/law/chain.jsonl",
            ["foundation", "law", "doctrine", "weights", "record"],
            ["ask", "remember", "propose", "weigh", "verify", "describe"],
            "demo-vault Manjuel core/Archive/law/LAW_001+LAW_002")])
    maps["council"] = (
        "# COUNCIL - household map\n\nFour personas weigh; none dispose.\n",
        [module_block("council", "COUNCIL", "personas/",
                      "core/state/law/chain.jsonl",
                      ["personas", "counsel"], ["weigh", "advise", "dissent"],
                      "demo-vault Manjuel personas/")])
    maps["lineage"] = (
        "# LINEAGE - household map\n\nTen observed actors; the census is the "
        "source.\n",
        [module_block("lineage", "LINEAGE", "..\\estate", "data/ledger.db",
                      ["actors", "census"], ["name", "count", "attest"],
                      "estate chain actor census 2026-08-25")])
    maps["gate"] = (
        "# GATE - household map\n\nOperator and working seat; invariant 6 "
        "holds for every row ever enrolled.\n",
        [module_block("gate", "GATE", ".", "data/master.db",
                      ["operator", "seat"], ["rule", "enroll", "review"],
                      "SPEC_US structural law")])

    out = {}
    for name, text in files.items():
        out[name] = text
    for mid, (prose, blocks) in maps.items():
        out[f"modules/{mid}.us"] = US.render(prose, blocks)
    return out


def main():
    args = sys.argv[1:]
    global US
    US = load_oracle()
    files = build_all()

    if "--verify" in args:
        ok = True
        for name, text in sorted(files.items()):
            landed = OUT_DIR / name
            if not landed.exists() or landed.read_bytes() != text.encode("utf-8"):
                ok = False
                print(f"VERIFY FAIL -- {name} drifted or absent")
        print("FOLD VERIFY OK -- every declaration byte-identical"
              if ok else "VERIFY FAILED")
        return 0 if ok else 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "modules").mkdir(parents=True, exist_ok=True)
    total_agents = 0
    for name, text in sorted(files.items()):
        (OUT_DIR / name).write_bytes(text.encode("utf-8"))
        doc = US.parse(text)
        assert not doc["errors"], (name, doc["errors"])
        agents = [b for b in doc["blocks"]
                  if isinstance(b, dict) and b.get("kind") == "agent"]
        total_agents += len(agents)
    print(f"FOLDED {len(files)} declarations ({total_agents} agents) -> "
          f"atlas\\agents (+ modules\\ household maps); born canonical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
