# BUILD PLAN — TUI Test, Agent Docs, Skills

*One sitting. Operator holds gate. Append-only witnesses.*

---

## Status snapshot (2026-09-08, sitting 79)

All stones P0–G COMPLETE. VERSION 0.1.0+f1. 85 Rust tests, 92 Go tests,
4 Python verifiers, MCP 58 strokes — all green. The extractField bug fixed
this sitting.

## Gap audit

| Gap | Severity | Source |
|---|---|---|
| No agent.md for any of the 40 citizens | HIGH | agents/ has only .us files |
| No skills directory in atlas | MEDIUM | estate has skills, atlas does not |
| TUI not tested end-to-end against live MCP | HIGH | extractField fixed, need full run |
| Agent .us validation not batch-tested | HIGH | enrollment was tested, not batch |
| docs/README.md has 49 files but no agent index | LOW | stale count |
| No agents/README.md | LOW | no index of the household |

## Phased build

### Phase 1: Test TUI end-to-end (acceptance: all resource commands return valid output)

1. Start `atlas-mcp --http :8090` in background
2. Run every TUI resource command:
   - `atlas-tui . status`
   - `atlas-tui . tools list`
   - `atlas-tui . tools get chain_list`
   - `atlas-tui . chain list`
   - `atlas-tui . agents list`
   - `atlas-tui . agents list --transform name -r`
   - `atlas-tui . agents get manjuel`
   - `atlas-tui . tenants`
   - `atlas-tui . rbac list`
   - `atlas-tui . mesh status`
   - `atlas-tui . rack list`
   - `atlas-tui . prove`
3. Test transform paths: `name`, `*.name`, `tools.*.name`
4. Test output formats: json, yaml, pretty, raw
5. Kill background MCP

### Phase 2: Test agent declarations (acceptance: 40/40 validate)

1. Run `atlas agent enroll data/master.db --dir agents --dry`
2. Verify all 40 files parse clean
3. Verify all reports_to chains resolve
4. Verify can_approve:false in every file
5. Verify covenant hash matches in every file

### Phase 3: Write agent.md for each citizen (acceptance: 40 files, one per agent)

Format per agent.md:
```
# <id> — <office>

<role> (one line from .us)

## Household
- **Reports to:** <reports_to>
- **Mode:** <primary|subagent>
- **Office:** <OFFICE>

## Permissions
- **read:** <glob or deny>
- **edit:** <glob or deny>
- **bash:** <allow, ask, or deny>
- **net:** <allow or deny>

## Source
<cite the source field from .us>

## Description
<2-3 sentence prose describing what this seat does in the household>
```

Files to create (40 total):
- agents/docs/analyst.md through agents/docs/zebulun.md
- agents/docs/README.md (index of all agents)

### Phase 4: Add basic skills (acceptance: skills dir exists, lints clean)

Create `skills/` directory with:
- `skills/prove/SKILL.md` — how to run the full prove battery
- `skills/orient/SKILL.md` — how to orient a new project
- `skills/enroll/SKILL.md` — how to enroll agents from .us declarations

Each SKILL.md follows the estate format:
```yaml
---
name: <skill-name>
description: "<10-500 char description>"
risk: safe
---
```

### Phase 5: Documentation updates (acceptance: all links resolve, counts correct)

1. Update `docs/README.md` — add agents/ section, update file count
2. Create `agents/docs/README.md` — index of all 40 agent.md files
3. Update `docs/CLI_REFERENCE.md` — verify TUI section matches actual commands
4. Update `docs/ARCHITECTURE.md` — verify §4d RBAC section is current

### Phase 6: Final prove (acceptance: all green)

1. `cargo test --workspace` — 85+ Rust tests
2. `cd line && go test ./...` — all Go tests
3. `atlas-mcp --prove` — 58 strokes
4. `atlas-tui prove` — full battery
5. Python verifiers — 4/4 byte-identical
6. `go vet ./line/...` — clean

## Acceptance checklist

| # | Criterion | How to verify |
|---|---|---|
| 1 | TUI all resource commands return valid output | Run each, check exit 0 |
| 2 | TUI transform paths work | `--transform name -r` returns names |
| 3 | 40/40 .us files validate | `atlas agent enroll --dry` |
| 4 | 40 agent.md files written | `ls agents/docs/*.md \| wc -l` = 40 |
| 5 | Skills directory exists and lints | `ls skills/*/SKILL.md` |
| 6 | docs/README.md updated | File count matches actual |
| 7 | All tests green | Full prove battery |
| 8 | go vet clean | No warnings |
| 9 | SEAT_LOG.md appended | Dated entry for this sitting |
| 10 | STATE_OF_BUILD.md appended | Dated entry for this sitting |
