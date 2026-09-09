# SPEC_COMMANDS — old ↔ new command reconciliation map

*Frozen reference for every cutover stone. During strangler, the left column
keeps working untouched; the right column runs against copied/temp ground
until its G-stone flips it live.*

## Prove convention (universal)

Every binary ships `--prove` (exit 0 = all strokes green) and `--describe`.
Proves are hermetic: temp books, stub engines, never the live record.

## REPL / doors

| Old (Python) | New (atlas) | Cutover |
|---|---|---|
| `python run.py` / `run.py --proof` (Steward 1.0) | KEEP (heart door) — no atlas twin; engines call through the heart's door | never |
| `python town.py beat\|flow [a b]\|story [h]\|look\|prove` | `atlas-town beat\|flow\|story\|look\|prove` | D1 acceptance → G-stone |
| `python door.py [--port N]\|--prove` (:8080) | `atlas-door [--port N]\|--prove` | D2 phone acceptance |
| `python aurora\server.py` (:7788) | `atlas-glass` (identical routes + her untouched console) | G8 only |
| `forge_server.py` (:7375) | `atlas-forge` | F-stone |
| `gateway.py` / `gateway.js` (:7374) | `atlas-gateway` | F-stone |
| `manjuel_us.py serve` | `atlas-mirror` (read-only) | G-stone |
| `python -m manjuel [--selftest]` (:8899) | `atlas-platform --selftest` | G-stone |
| CARR `boot.py` / `frontends.web` (:8760) | `atlas-townweb` + pkg/carr harness | E-stone |

## MCP surfaces

| Old | New |
|---|---|
| `.mcp.json` → `seat_mcp.py` (steward-line) | `.mcp.json` → `atlas-mcp --home "Steward 1.0"` |
| `us_mcp.py --home .` (Agents/Neiro) | `atlas-mcp --home <module>` |
| `wall.py` (HTTP+bearer) | `atlas-wall` |

## Records / provenance CLI

| Old | New |
|---|---|
| `matrix.py` | `atlas matrix build --home <dir>` (Rust) |
| `link.py status\|lay` | `atlas link status\|lay` |
| `prove_parity.py` walk | `atlas chain verify --roots estate\|secondbrain\|atlas` |
| `fold_us.py` | `atlas fold us --out Shelf\estate.us` |
| `ark.py` | `atlas ark pack\|check` |
| `checkpoint.py` | `atlas deposit checkpoint\|status` |

## Faces & tooling

| Old | New |
|---|---|
| builder engine CLI | `atl agent new\|enroll\|orient <decl.us>` |
| skills catalog / validate-skills.mjs | `atl skill lint\|list\|install` |
| opencode.json + 3× .mcp.json hand edits | `atl wire check\|apply --dry` (apply = operator hand) |
| golden-master ad-hoc diffs | `atl gm run --stone <S>` |

## Rules

1. Names keep their verbs: beat stays beat, prove stays prove.
2. Ports do not move at cutover.
3. A new command lands only with its acceptance rows green and its
   STATE_OF_BUILD entry witnessed.
4. Retiring an old process is a fold note written by the operator's hand.
