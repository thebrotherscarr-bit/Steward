---
name: enroll
description: "Enroll agent declarations from .us files into the master database."
risk: safe
---

# Enroll Skill

Enroll agent declarations from .us files into the master database. This validates each declaration against the schema and registers it.

## When to Use This Skill

Use this skill when:
- Adding new agents to the household
- Validating existing .us declarations
- After modifying any .us file
- Before a prove run to ensure all agents are valid

## Prerequisites

- `atlas` binary built and on PATH
- `data/master.db` present (or create with `atlas db init`)
- `.us` declaration files in `agents/` directory

## Usage

### Dry run (validate only, no writes)

```bash
atlas agent enroll data/master.db --dir agents --dry
```

Expected output:
```
data/master.db: 40 files read (0 modules); enrolled 0 agents [DRY RUN - rolled back] (40 already present)
```

### Actual enrollment

```bash
atlas agent enroll data/master.db --dir agents
```

### Validate a single .us file

```bash
atlas agent enroll data/master.db --dir agents --dry 2>&1 | findstr "filename.us"
```

## What Enrollment Checks

For each `.us` file:
1. **Parse clean** — the document must parse without errors
2. **Validate pass** — required fields per kind (agent, module, tool, skill)
3. **can_approve: false** — must be explicitly stated, absence is a refusal
4. **Covenant cited** — must contain the covenant hash `1512741580b7239b`
5. **reports_to resolvable** — the chain must resolve to a known seat

## Schema

The .us schema is defined at `specs/SPEC_US_SCHEMA.json`. All 40 agent declarations must validate against it.

## Expected Output

```
40 files read (0 modules); enrolled 0 agents [DRY RUN] (40 already present)
```

- `40 files read` — all .us files found and parsed
- `0 modules` — module blocks are handled separately
- `enrolled 0 agents` — no new agents (already present)
- `[DRY RUN]` — no database writes

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All files validated |
| 1 | One or more files failed validation |
