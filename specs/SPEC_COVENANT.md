# SPEC_COVENANT — identity derivation reference

*Frozen reference for A1-07 and every identity-bearing operation. v2,
2026-08-24: TWO epochs after the operator's rulings — the House heart
(today's ground) is identity-of-record; the Elder epoch is read-only legacy.
Sources: today-heart `weights\covenant.json` + genesis laws; elder epoch
anchored by `estate\Manjuel\5.0\soul\amendments.jsonl` n=1.*

---

## EPOCH II — HOUSE (current, identity-of-record)

**Heart:** the house founded 2026-08-24 at
`secondbrain\SecondBrain-collab\demo_vault\Manjuel\` (engine 3.2.0-lineage +
app platform + court polity). Atlas wraps him ask-only; atlas never ports or
rewrites him.

| field | value |
|---|---|
| covenant | `1512741580b7239b80c53e2456b46aa9ec43586788d569da0895718dccf15bbb` |
| mark | `1512741580b7239b` |
| ancestor | null |
| epoch_sealed | 2026-08-24T09:29:18-0700 |
| declared set | **FIVE**: 01_MYTHOS · 02_CONSTITUTION · 03_CREED · **04_NEURO_CORE** · **05_THE_LAW.md** (`8e569a8be3435d1ec9e5bf3f2cb974dcdebcd1e69b63689da5433820e5fa4474`) |
| anchor file | `core\Archive\weights\covenant.json` |

Derivation (construction A over the five-doc declared order — VERIFIED
2026-08-24 against his covenant.json):

```
declared = [01_MYTHOS, 02_CONSTITUTION, 03_CREED, 04_NEURO_CORE, 05_THE_LAW]
doc_sha[i] = sha256(bytes(doc_i)).hexdigest()
covenant   = sha256(utf8(concat(doc_sha[0..4]))).hexdigest()
mark       = covenant[:16]
```

His law layer (05_THE_LAW + LAW_001/LAW_002): sealed four say what he IS;
THE LAW says how the house RUNS and is amendable through a link chain whose
genesis `prev:` is the covenant itself. Atlas verifies; atlas never sits as
court.

## EPOCH I — ELDER (read-only legacy)

| field | value |
|---|---|
| covenant | `65118a147dd49ed96068e8a3cf1a472db1f4d91253b23507c56926ba2d8d9dd9` |
| legacy_mark | `65118a147dd49ed9` (= covenant prefix) |
| declared set | FOUR: 01_MYTHOS · 02_CONSTITUTION · 03_CREED · 04_NEURO_CORE |
| anchors | `estate\Manjuel\5.0\soul\amendments.jsonl` (n=1, key_id `961e4e49…9221`, pbkdf2-hmac-sha256 200k, salt `"covenant"`) |

Same construction A over four docs. Carried by the SEALED hearts (estate
genesis copies; the 5.0 held heart — ruled an elder/record 2026-08-24).
Elder marks are accepted ONLY in explicitly-marked legacy comparisons;
nothing new stamps them.

## Refuted constructions (do not use)

Concat of raw doc bytes (sorted or declared) · raw digest bytes either order
· all-`.md`-in-directory sorted (the FOUNDATION.md trap — an intruder file
must move nothing).

## Rules for atlas code

1. **Genesis is a declared set**, named docs only; directory contents
   otherwise ignored.
2. **Epoch-aware:** default target = House (five docs, `151274…5bbb`);
   Elder verification requires an explicit `--epoch elder`.
3. **Anchors:** House checks read his `covenant.json`; Elder checks read the
   5.0 amendments genesis entry. Recompute everything; name any broken doc.
4. **Keys are silent.** key_id/kdf fields are recorded, never verified here;
   signature verification binds to the key-stone.

## Prove requirements (A1-07a/b)

- House derivation reproduces `151274…5bbb` over his live foundation copies.
- Elder derivation reproduces `65118a…9dd9` over the 5.0 genesis copies.
- Intruder file dropped into a temp declared-set dir moves nothing (both
  epochs).
- One flipped byte in a temp doc changes the covenant and names that doc.
