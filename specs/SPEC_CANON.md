# SPEC_CANON — canonical JSON reference

*Frozen reference for A1. Source of truth: `Neiro\lib\us_canon.py` (327 ln).*

## The three forms

| body_v | Name | Construction |
|---|---|---|
| 1 | BOARD | `json.dumps(body, sort_keys=True)` — escaped ASCII |
| 2 | LINKS | same + `ensure_ascii=False` |
| 3 | JCS | RFC 8785 JSON Canonicalization Scheme, hand-rolled |

`BODY_V_BOARD=1 · BODY_V_LINKS=2 · BODY_V_JCS=3 · BODY_V_CURRENT=3`.
New chains stamp body_v = 3; readers accept all three.

## JCS rules (as implemented)

- Object keys sorted by UTF-16 code units: sort key =
  `key.encode("utf-16-be")`.
- Strings: minimal JSON escaping per RFC 8785.
- Numbers: floats are REFUSED (`CanonRefused`). Integers bounded to
  ±(2^53−1) (`SAFE_INT_MIN/MAX = ∓9007199254740991`); outside → refuse.

## API surface (Rust `canon.rs`)

```
canon(body, body_v) -> String
canon_bytes(body, body_v) -> Vec<u8>
CanonRefused error carrying the reason (float / int out of range)
```

## Prove requirements

- Byte-parity with Python for every fixture: V1, V2, V3 vectors from
  `us_canon.prove()` plus live-chain samples cut in A1.
- Float refusal and int-bound refusal named identically.
- UTF-16 ordering case: keys whose UTF-8 and UTF-16 orderings differ.
