# SPEC_US_MESH — THE MESH, the `.us` messaging protocol

*Spec for stone **B2**. Status: SPEC-FIRST — this document and the golden
vectors in `tools/cut_mesh_vectors.py` land before any protocol or server code.
atlas version pins `0.1.0+b2` only at implementation time.*

---

## 0. Purpose

atlas **is** the SSM — the sovereign session/mesh engine. THE MESH is its
messaging protocol: the operational half of `.us`. Where the foundation *speaks*
the law in documents, THE MESH *speaks* the estate — agent-to-agent,
agent-to-ledger, conversation-to-ledger, all chained, signed, and confidential.
It is the local mesh for agentic chatter the operator described — but sovereign,
estate-internal, and nosotros-only.

THE MESH reuses the estate's proven **links-chain** envelope shape (read
`estate/forge/links/links.py`). It does not invent a new crypto. It adds two
things the links chain did not scope: **confidentiality by default** (the
plaintext never leaves the estate) and **wall isolation** (per-project channels).

### 0.1 Three distinct systems — do not fuse them

1. **manjuel.us** — the operator's (Kyler's) personal **BLAKE3 sovereign ledger**,
   paper-cypher (private), chain public, served read-only. It is NOT the estate
   and NOT atlas. Reference model only (`Index/manjuel_us.py`,
   `estate/forge/ledger/manjuel_us.py`).
2. **The estate's `manjuel` core engine** — the capital. atlas must NOT boot or
   forward to it; B1's zero-write guard holds (atlas writes only on the estate,
   with its own cypher).
3. **`jesster`** — the estate's **key generator** (asymmetric secp256k1 Schnorr).
   `estate/forge/links/links.py:708` `jesster.identity(words, read_secret(),
   OFFICE)`; `cockpit.py:30` "the proven engine". **Signing in THE MESH is
   jesster's, never `keys.py`.**

> `estate/Manjuel/5.0/manjuel5/keys.py` is HMAC/symmetric; its asymmetric path is
> PARKED. It is never cited for mesh signing.

---

## 1. The envelope (a links-chain entry)

One message = one chain entry:

```jsonc
{
  "ts":     "<RFC3339 UTC>",
  "kind":   "mesh",            // or "wrap"
  "payload": {
    "n":     <int>,            // position in this conversation's chain
    "chan":  "<project/ground>",   // the wall this message lives inside
    "to":    "<actor | @channel | @everyone>",
    "ct":    "<ciphertext of the body>",   // CONFIDENTIAL: plaintext never at rest
    "mode":  "sealed|open",
    "cites": ["<hash>", ...],  // LINKS: hash refs to other conversations / ledgers / marks
    "mark":  "<16-hex key mark>"   // welded: name bound to key forever
  },
  "prev":   "<64 hex>",        // the weld — head of this conversation's chain
  "actor":  "<.us agent id>",  // WHO, inside the hash
  "hash":   "<64 hex>",        // sha256(prev || canon(body))
  "sig":    "<96 bytes hex>",  // Schnorr over the HASH (never the body)
  "pub":    "<64 bytes hex>"   // verifying key; mark = sha256(pub)[:16]
}
```

- `body` = the five keys `{ts, kind, payload, prev, actor}` — the sealed kernel's
  own tuple (`links.py:80`).
- `canon(body)` = `json.dumps(body, sort_keys=True, ensure_ascii=False)`
  (`links.py:90`).
- `hash = sha256(prev + canon(body))` (`links.py:94-96`). First `prev` =
  `"0"*64` (GENESIS).
- `sig` rides **outside** the five hashed keys, so its presence or absence can
  never break an old entry (`links.py:17-21`). It is a **deterministic Schnorr
  over secp256k1**, `JESSTER|OFFICE|vEPOCH` domain (`links.py:308-310`), taken
  over the **hash**, never the body.
- `mark` = `sha256(pub)[:16]`, welded **inside** `payload` (`links.py:276`).

### 1.1 Signing — hand-rolled secp256k1 Schnorr, differential acceptance

Go's standard library has `crypto/ecdsa`, `crypto/ed25519`, `crypto/ecdh` — **no
secp256k1 and no Schnorr**. So atlas signs with secp256k1 Schnorr **hand-rolled
in Go (zero external crates)**, byte-for-byte compatible with `jesster.py`
(`forge_secret@197`, `identity@254`, `session@266`, `certify@335`, `sign@298`,
`check_cert@348`). This is a *second* hand-rolled crypto implementation; the risk
is cross-language agreement, not a single honest path.

> `jesster.py`'s own honesty clause covers one implementation. Two that must
> match is a different risk. **Acceptance is a differential vector set** (see §11,
> golden `signing-model` + acceptance row **B2-05**): sign in Python → verify in
> Go, sign in Go → verify in Python, over the fixture chain, **including the
> malleability edge cases**. "The port passes its own tests" is not sufficient.

### 1.2 `cites` — the estate's message-graph

`cites` names the work a message stands on, **by hash** — another message in this
channel, a message in another channel (refused unless same project), an off-estate
anchor (a `manjuel.us` block, a git commit, a covenant/foundation mark). It sits
**inside** `payload`, inside the hash: the terrain a message claims is welded
forever (`links.py:34-38`).

---

## 2. Identity — the `.us` trust root

- Every message's `actor` + `pub` + `sig` verify against **enrollment** in the
  `.us` ground (`atlas agent enroll <db> --dir agents`). An **unenrolled actor is
  refused by name** — no anonymous posting.
- `can_approve` is `false` in every declaration, ever. Approval lives in the
  operator's hand alone.
- `mark` lets a human read *whose* key signed, without exposing the key.

---

## 3. Authorization / the wall

- A **channel = an atlas tenant** (the multi-tenant foundation already landed in
  B1). `"chan"` must equal the caller's project; a message addressed to another
  project's channel is **refused by name** (cross-project chatter is a packet,
  not a message — only the operator lands cross-ground work).
- Direct messages: `to` must name an **enrolled** agent; an unenrolled target is
  refused.
- Delegation (`reports_to`) is read from the enrolled seat's record; a delegate
  may post on a channel it is enrolled to, never beyond it.

---

## 4. The chains (integrity)

THE MESH keeps **per-actor chains** (one pen per actor) **plus a channel-head
chain** written by the SSM. The channel-head chain carries weld-pointers to the
latest entry of each participant and the operator's channel key; it is how the
mesh rewinds (via the head + `cites[]`) without re-sending history. No fork is
ever permitted — a chain with two heads is `TAMPER`.

`verify()` rewalks any chain:
- `prev` weld continuity + `hash` match per entry → `INTACT`;
- a byte changed **inside** an entry (hash mismatch, weld holds) → `FLIP`;
- a broken weld (a missing/reordered entry) → `TAMPER`.

This is the A1 verdict set `EMPTY | INTACT | FLIP | TAMPER`
(`estate/Neiro/lib/us_chain.py`). atlas reuses the same logic as the estate
walker so the two implementations agree (see §11, `cross-impl`).

Wraps: every `WRAP_SIZE=40` messages close a Merkle root (domain-separated,
`links.py:109-154`); the wrap **is** the token. Fixed, nobody chooses it.

---

## 5. Confidentiality + the deciphering ledger

The outside world — and the repo — sees **ciphertext only**. Plaintext exists
**only inside the ledger-holding estate**.

### 5.1 SEALED commitment — `H(salt ‖ plaintext)`, NOT `H(ct)`

`links.py`'s SEALED commits to `H(document)` — safe there because documents are
high-entropy. A message mesh is different: committing to `H("yes")` or
`H("meet at 3")` lets anyone holding the chain brute-force the plaintext in
milliseconds. A bare hash only hides when its input is unguessable.

Worse, committing to `H(ct)` (the ciphertext) does not give you what SEALED is
*for*: Hooke's anagram — you reveal the document later and a stranger checks it
against the commitment you made years earlier. Revealing plaintext does not verify
against `H(ct)` unless you also reveal the key, the nonce, and reproduce the exact
encryption.

**The fix (one line of spec):** commit to

```
commitment = H(salt || plaintext)
```

where `salt` = **32 random bytes**, stored beside the message in the estate and
**revealed with the plaintext**. This (a) hides low-entropy messages — a guesser
must find the 32-byte salt, not just the words; and (b) the reveal *verifies*:
recompute `H(salt || plaintext)` and compare to the stored commitment. The
ciphertext `ct` is the encrypted body at rest; the commitment is the verifiable
seal.

### 5.2 The deciphering ledger (operator-refined)

- The **sovereign paper cypher** is the ROOT of trust. It is used as **2FA to
  unlock / enter — once per day or per session**, never per message. A pincode may
  stand in for routine ops; the paper cypher is the 2FA on login.
- **Per-user / per-agent keys are keyed in a `.env`** (local, not in repo) — the
  backend is keyed per agent, so the operator never types 12 words 35× in a row.
- Post-unlock, an **ephemeral session key** (`jesster.py session()`) carries the
  run — no repeated cypher typing. The identity key **certifies** the session
  (`jesster.py certify()`), so a dead session's signatures still verify.
- The plain salt + the seal live **only inside the estate**; the public chain
  carries `ct` + `commitment`, never `plaintext` or `salt`.

> The gate is **structural, not policed** (see §8). Security is not "in
> orchestration" — it is in the absent verbs, the wall, and the cypher root.

---

## 6. Zero-egress

- THE MESH refuses any destination that is not loopback or an estate ground.
  Mirrors `manjuel_us.py`'s web mirror, which has **no write path**
  (`manjuel_us.py:582-586`): the chain is written only on the estate.
- A message addressed to a non-estate endpoint is refused outright — egress is a
  packet, not a message.

---

## 7. Transport (decided here)

THE MESH uses **live transport + the ledger, both**:

- **Live transport**: a websocket mesh, **estate-internal only**. Messages fly
  live within the estate; nothing leaves the wall.
- **Ledger**: the per-actor + channel-head chains are the **truth**. The live
  socket is a fast path; the ledger is what you verify and what you rewind against
  (via the channel head + `cites[]`).
- The protocol is transport-agnostic because the envelope is self-describing; the
  websocket is v1, not the only possible carrier.

### 7.1 Surfaces (who may read)

- **Aurora** — the console, the face of `manjuel.us`. **View / verify only** (a
  human reads and checks the chain). It does not write.
- **`api.manjuel.us`** — the operator's personal API. **READ-ONLY by structure**:
  `GET` (head / chain / entry / verify) only; a write verb (`POST/PUT/DELETE/
  PATCH`) is **refused with 405**, never reached over the network during a prove.
- **`manjuel.us`** — the operator's PaaS (5-yr prepaid, Cloudflare) that hosts the
  estate + Aurora.
- **atlas (the SSM)** — local on the estate; writes happen only on the estate with
  the paper cypher; the live websocket is estate-internal.

---

## 8. The structural gate

The gate is **structural, not policed** (`us_mcp.py:25` "THE GATE IS STRUCTURAL,
NOT POLICED … not disabled, ABSENT"):

- **Refused verbs are ABSENT** from the surface — `approve, ascend, merge, commit,
  push, delete, reject, promote` do not exist as mesh verbs. A request for one is
  not denied; it is unrecognized.
- **The wall = tenant isolation** — `chan` must equal caller project, by
  construction.
- **The cypher = the root** — unlock is once-per-session 2FA; without it, no write.
- **Breach is logged, not argued** — a refused op lands on-chain as a
  `breach_attempt` entry (§9), and reconciliation is a first-class `reconcile`
  kind (§9). The record proves the gate held.

---

## 9. On-chain governance kinds

Two first-class chain kinds ride THE MESH (observed in the folded `neiro`
ledger):

- **`reconcile`** — tallies `weighed / grounded / flagged / registry`; the estate
  reconciling its own state against the chain.
- **`breach_attempt`** — logs a refused operation (e.g. `detail: "network call
  refused"`); the structural gate's receipt.

Both are cut as goldens (`reconcile`, `breach`) so the mesh protocol treats them
as native, not bolt-ons.

---

## 10. Versioning

- `SPEC_SEAM` pins this envelope; any change orphans every existing chain.
- atlas version stays `0.1.0+b1` through B1; **`0.1.0+b2` lands with the B2
  implementation**, not the spec.

---

## 11. Goldens (cut first, assert after)

`tools/cut_mesh_vectors.py --verify` is the oracle. **The oracle is the LOCAL
folded fixture set under `tests/fixtures/chains/`** (`forge_links_chain.jsonl`,
`jesster_gen1_chain.jsonl`, `neiro_archive_ledger.jsonl`). The live chains
(`manjuel.us`, `api.manjuel.us`, `github.com/thebrotherscarr-bit`) were folded
into those fixtures **once** (cut 2026-08-25); each golden pins the fixture's
`sha256` so the oracle cannot drift silently. A live re-fetch is a SEPARATE,
OPTIONAL drift stroke and is **never** part of `--verify` (this tool touches no
network — hermetic by law).

Vectors (15):

1. **chain-intact** — fixture rewalks `INTACT` (hash over `prev||canon` matches).
2. **flip** — a byte changed inside an entry → hash mismatch, weld holds → `FLIP`.
3. **tamper** — a dropped entry → broken weld → `TAMPER`.
4. **mark-welded** — `sha256(pub)[:16]` recomputes to `payload.mark`.
5. **sealed** — commitment `= H(salt || plaintext)`; salt 32B hides low-entropy
   msgs; the reveal verifies; `commitment != H(plaintext)` (NOT `H(ct)`).
6. **auth-refuse** — unenrolled `actor` refused by name.
7. **wall-refuse** — `chan` ≠ caller's project refused by name.
8. **egress-refuse** — non-loopback/estate destination refused.
9. **signing-model** — `sig`/`pub` ride OUTSIDE the five hashed keys; `mark`
   welds to `pub`. (The differential Py↔Go sign/verify is acceptance **B2-05**.)
10. **cross-impl** — two independent walkers agree on verdict + head hash (estate
    `us_chain.py` ↔ atlas logic, both local).
11. **one-pen** — per-actor chains + channel-head: distinct chains, each `INTACT`,
    zero forks.
12. **marks-weld** — the jesster chain cites the covenant (`65118a147dd49ed9`) and
    foundation (`2cee607d21696d63`) marks.
13. **reconcile** — on-chain `reconcile` kind tallies weighed/grounded/flagged.
14. **breach** — on-chain `breach_attempt` logs the refused op (structural gate).
15. **mirror-readonly** — `api.manjuel.us` / `manjuel.us` are read-only by
    structure: a write verb is refused (405). Modeled, never reached over network.

---

## 12. Forbidden verbs

`approve, ascend, merge, commit, push, delete, reject, promote` are absent from
the mesh surface by construction, as in B1. Write verbs on the read-only mirror
are refused with 405.
