# SPEC_CHAINS — hash-chain format reference

*Frozen reference for A1. Sources of truth: `Neiro\lib\us_chain.py` (609 ln),
`Neiro\lib\prove_parity.py` (287 ln), observed live chains across the estate.*

## The current form (BODY_V3 stamped)

Entry shape (one JSON object per line):

```json
{"ts": "...", "kind": "...", "n": <int>, "payload": {...},
 "prev": "<64 hex>", "actor": "...", "body_v": 3, "hash": "<64 hex>"}
```

- `ts` RFC 3339 UTC. First entry's `prev` = GENESIS = `"0"*64`.
- Projection: `BODY_KEYS = ("ts","kind","n","payload","prev","actor","body_v")`.
- `hash = sha256( prev_hex + canon(project(entry), body_v) )`, full 64-hex.
- Append verifies before writing; a broken weld refuses the append.
- Wraps: every 40 links a wrap entry closes a Merkle root over the window
  (`WRAP_KIND="wrap"`, `MERKLE_V=2`, leaf prefix `\x00`, node prefix `\x01`,
  odd node carried never doubled). Consistency proofs are weld-based.

## Verify verdicts

`EMPTY | INTACT | FLIP | TAMPER` — FLIP (a byte changed inside an entry,
hash mismatch but weld continuity holds) is told apart from TAMPER (broken
weld). Verdict dict carries `flips[]`, `broke_at`, `appendable`.

## The legacy forms (recognition table, from prove_parity FORMS)

Hash candidates over 13 named shapes; width may be full 64-hex or truncated
16-hex heads:

| Form family | Hashed material | Canon | Width |
|---|---|---|---|
| board whole | whole entry + prev prefix | V1/V2 | 16 |
| links projected | LINKS_BODY_KEYS projection + prev | V1/V2 | 64 / 16 |
| harvest bare whole | whole entry, no prev prefix | V1/V2 | 16 |
| envelope `{prev,hash,body}` | `body` alone | V1/V2 | 64 |
| whole | whole entry + prev prefix | V1/V2 | 64 |
| JCS projected | BODY_KEYS projection + prev | V3 | 64 |
| JCS whole | whole entry + prev prefix | V3 | 64 |

`LINKS_BODY_KEYS = ("ts","kind","payload","prev","actor")`.

## Known live chains to import (A1 golden masters)

- `estate\Steward 1.0\state\ledger\ledger.jsonl` (~948 KB; mixed mark
  semantics: awaken/home carry covenant `65118a147dd49ed9`; fold/
  doctrine_read carry content digests — readers filter by kind)
- `estate\Steward 1.0\state\chain\chain.jsonl` (steward chain)
- `estate\Agents\Seat_log\ledger.jsonl` (BODY_V3)
- `Neiro\Archive\ledger\ledger.jsonl` (envelope form, covenant
  `d3c7372efe56ecda`)
- `Steward\Archive\state\board.jsonl` + `ledger.jsonl` (board/envelope)
- `Neiro\Archive\shelf\commons\board.jsonl` (+ snapshots), custody,
  kimi_harvest ledger (harvest-bare-16), ops ledgers
- `Jesster\shelf\library\gen1..4\chain\chain.jsonl`, `Jesster\Archive\chain.jsonl`
- forge: `links\links.py` chain + public manjuel.us ledger (b3/keyed hashing,
  domain-separated genesis), gateway blake2b-32 event hashes
- Agent Skills board ledgers (escaped-ASCII V1, deliberate divergence)

## API surface (Rust)

```
verify(path) -> verdict {EMPTY|INTACT|FLIP|TAMPER, flips[], broke_at, appendable}
read(path) -> entries; head(path); links(rows)
append(path, kind, payload, actor, body_v)   // verify-then-write
recognize(path) -> form name + matched construction   // forms.rs
merkle / merkle_path / climb / consistency(proof)
```

## Prove requirements

- Every live chain listed above: recognize() names its form; verify()
  reproduces the Python verdict on the same bytes.
- Tamper/flip injections on temp copies produce FLIP vs TAMPER correctly.
- Export regenerates byte-identical JSONL for each imported chain.
