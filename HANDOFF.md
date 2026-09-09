# HANDOFF — atlas build

> **FOSSIL** — This file is stale as of 2026-08-28. The active handoff chain
> is `SEAT_LOG.md` tail + `STATE_OF_BUILD.md` tail + `THE_ROAD.md`. This file
> is kept for historical reference only. Do not use it as the current state.

*Newest handoff for the atlas working folder. Read this + `STATE_OF_BUILD.md`
tail + `SEAT_LOG.md` tail before touching anything. The seat keeps no memory;
this file is the memory. Written 2026-08-27 at the operator's word.*

---

## Stone in flight: B2 — THE MESH (`.us` messaging protocol)

**State: SPEC-FIRST COMPLETE (corrected) + executed. Implementation not started.**

atlas **is** the SSM — the sovereign session/mesh engine. THE MESH is its
messaging protocol. The spec and the golden vectors landed before any protocol
code (per the fixtures-first law). VERSION is pinned `0.1.0+b2`; the B2 stone is
open.

### What landed this sitting (sitting 12)

- `specs/SPEC_US_MESH.md` — rewritten, corrected. Three-system split made
  explicit: **manjuel.us** (operator BLAKE3 ledger, private key / public chain) ≠
  **estate `manjuel` engine** (atlas must never boot/forward to it — B1 zero-write
  guard) ≠ **`jesster`** (estate keygen; signing is jesster's, never `keys.py`,
  whose asymmetric path is parked). Envelope = the proven links-chain entry
  (five-key body + `sha256(prev ‖ canon)` + `sig/pub` OUTSIDE the body + `cites`
  inside). SEALED commitment = `H(salt ‖ plaintext)`. Structural gate (refused
  verbs ABSENT, wall = tenant isolation, cypher = root, on-chain `breach_attempt`).
  Transport = live websocket (estate-internal) + ledger truth + channel-head
  chain. Surfaces: Aurora (view/verify), `api.manjuel.us` (read-only 405),
  `manjuel.us` (PaaS), atlas (SSM).
- `tools/cut_mesh_vectors.py` — **8 → 15 goldens**, all hermetic, all local
  (oracle = `tests/fixtures/chains/`, each fixture `sha256`-pinned, no network).
  New: signing-model · cross-impl · one-pen · marks-weld · reconcile · breach ·
  mirror-readonly. Confidentiality golden rewritten to the **salted** commitment.
- `ACCEPTANCE.md` B2 → 14 rows (B2-01..B2-14). **B2-07 = differential Py↔Go
  signing acceptance** (the hand-rolled Go Schnorr must byte-match `jesster.py`,
  both directions, incl. malleability edges). **B2-13 = hermetic-oracle discipline.**
- `VERSION` → `0.1.0+b2` (root + `line/VERSION` + `line/cmd/atlas-mcp/VERSION`
  + `core/src/version.rs` assert).
- Witnesses: `STATE_OF_BUILD.md` (sitting 12), `SEAT_LOG.md` (sitting 12),
  `THE_ROAD.md` (B2 row + NEXT).

### The three operator corrections that shaped it (all load-bearing)

1. **SEALED was committing to the wrong thing.** Draft used `H(ct)`. That is
   brute-forceable for low-entropy messages and does not verify on reveal. Fix:
   `H(salt ‖ plaintext)`, salt = 32 random bytes stored + revealed in the estate.
2. **"Go stdlib Schnorr port" is impossible.** Go has ecdsa/ed25519/ecdh, no
   secp256k1, no Schnorr. atlas signs with secp256k1 Schnorr **hand-rolled in Go
   (zero crates)**; acceptance is a differential Py↔Go vector set, not "the port
   passes its own tests."
3. **Live endpoints as oracles break hermetic law.** The cutter reads only the
   local folded fixtures (cut 2026-08-25); live `manjuel.us`/`api.manjuel.us`
   re-fetch is a separate optional drift stroke, never in `--verify`.

### Battery (all green, this sitting)

- `go build ./...` + `go vet ./...` + `go test ./...` clean (from `line/`).
- `go run ./cmd/atlas-mcp --prove` → **24 strokes exit 0**.
- `python tools/cut_mesh_vectors.py --verify` → **15/15 PASS** (hermetic).
- `cargo test --workspace` → **77/77** (version assert now `+b2`).
- No source-ground writes anywhere.

---

## NEXT — B2 implementation (opens at the operator's word)

1. **`mesh_*` tools over THE LINE** — `mesh_post` / `mesh_read` / `mesh_chain`
   (verify a channel) / `mesh_cite` / `mesh_enroll` (operator-only). All carry
   `project`. Forbidden verbs stay absent by construction.
2. **Deciphering ledger** — sovereign key root (paper cypher = 2FA unlock
   once/day) + per-agent `.env` keys; `salt` stored beside each message; reveal
   verifies `H(salt ‖ plaintext)`.
3. **Hand-rolled Go secp256k1 Schnorr** — byte-for-byte with `jesster.py`; the
   **differential Py↔Go prove** (B2-07) is the gate, not self-tests.
4. **Channel-head chain** — SSM-written weld-pointers + operator channel key;
   per-actor chains stay one-pen.
5. **On-chain governance** — `reconcile` + `breach_attempt` kinds are first-class
   (already goldens).

Gate: goldens stay green against real writes.

---

## Open / ruled

- **Ruled:** manjuel.us / api.manjuel.us are read-only by structure (write verbs
  405). atlas writes only on the estate with the cypher. Live transport is
  estate-internal only.
- **Ruled:** signing = jesster (secp256k1 Schnorr), never `keys.py`.
- **Inferred (confirm at impl):** the hand-rolled Go Schnorr reuses the same
  `JESSTER|OFFICE|vEPOCH` domain tag as `jesster.py` — the differential vectors
  must pin the domain string, not just the curve.
- **Not done on purpose:** no mesh protocol code yet — spec-first by law. No git
  history created (never commit without the operator's word).

## Standing law (carried)

Cut goldens from the read-only oracle BEFORE assertions. Prove hermetic. Fold,
never delete. Append-only witnesses. `can_approve` false everywhere — approval
lives in the operator's hand alone.
