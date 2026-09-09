# SPEC_US — `.us` declaration format reference

*Frozen reference for A1/A2. Source of truth: `Neiro\lib\us_read.py`.*

## Shape

A `.us` document is prose carrying fenced JSON blocks. Fences are tagged
`json`, `us`, or `json us`. US_VERSION = 1.

## Block kinds

- `module` — exactly one per document (the declaration): fields `us`, `id`,
  `kind:"module"`, `body_v`, `generation`, `office`, `reports_to`,
  `can_approve`, `ledger`, plus module rows (verbs the module offers) and its
  records locations.
- `agent` — roster entries with `mode` (`primary` | `subagent`) and
  `permission` rows.
- `tool` / `skill` — roster entries.

## Hard rule

`can_approve` must be stated explicitly as `false`. Absence is a refusal
(`UsRefused`), never a default. This is the structural gate.

## API surface (Rust `us.rs`)

```
parse(text) -> {prose, blocks, errors}
load(path)
validate(block)            // enforces required rows per kind
declaration(doc)           // the one module block, else refuse
roster(doc)                // agent/tool/skill blocks
derive_tools(permission) -> {tools, lost}   // glob flattening, losses reported
render(prose, blocks)      // deterministic round-trip
```

## Atlas additions (A2, additive)

- `atlas\agents\*.us` declarations folded from observed behavior for ~30
  agents (manjuel, steward, neiro, jesster, aurora, smith, foreman,
  archivist, + opencode defs).
- Registry enrollment requires: parse clean · validate pass · covenant cited
  · `can_approve:false` · resolvable `reports_to`.

## Prove requirements

- Round-trip render(parse(x)) == x for every existing .us on the grounds.
- Missing `can_approve` refused with named error.
- `derive_tools` loss report matches Python on shared fixtures.
