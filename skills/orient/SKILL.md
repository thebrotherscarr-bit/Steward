---
name: orient
description: "Assemble the orientation pack for a project: standing law, line, road, and log tail."
risk: safe
---

# Orient Skill

Assemble the orientation pack for a project. This is the first thing every seat does before working.

## When to Use This Skill

Use this skill when:
- Starting a new sitting or session
- A seat needs to understand the current state
- Orienting a new project or ground
- Checking what's on THE_ROAD

## Prerequisites

- `atlas` binary built and on PATH
- SEAT_LOG.md and THE_ROAD.md present in the project root

## Usage

### Orient to the atlas project

```bash
atlas orient --home .
```

### Orient to a different project

```bash
atlas orient --home /path/to/project
```

### Orient via MCP

```json
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_in_line", "arguments": {}}}
```

## Expected Output

The orientation pack contains:
1. **Standing law** — the five laws from CHARTER.md
2. **The line** — current state of the system
3. **THE_ROAD** — the next stone and what's parked
4. **Log tail** — the most recent SEAT_LOG entry

## What a Seat Does After Orienting

1. Read the newest handoff first. Never re-derive documented state.
2. Bank the operator's ruling in SEAT_LOG before touching anything.
3. Cut goldens from the read-only oracle BEFORE writing assertions.
4. Implement stdlib-only. Prove hermetic. Full suite green.
5. Witness in SEAT_LOG.md + STATE_OF_BUILD.md (dated, append-only).
6. Stop at review gates — they belong to the operator.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Orientation pack assembled |
| 1 | Error (missing files, invalid ground) |
