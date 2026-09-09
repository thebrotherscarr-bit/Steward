# TUTORIAL — learn the Atlas workflow by doing

*Five exercises, in order, each teaching one discipline of this build.*

---

## Exercise 1 — Verify the Chain

**Goal:** Understand how hash chains provide tamper-evident provenance.

```bash
# 1. Verify a known-good chain
atlas chain verify tests/fixtures/chains/steward_chain.jsonl
```

Expected:
```
verdict=FLIP entries=1 flips=[0] broke_at=None appendable=true
```

The verdict is FLIP because the fixture is a known-TAMPER chain used for
testing. The system correctly detects the mismatch.

```bash
# 2. Verify the live chain walk
atlas chain verify --roots .
```

Expected:
```
verdict=SOUND
```

The entire estate chain tree is sound — no tampering detected.

```bash
# 3. Recognize a chain form
atlas chain recognize tests/fixtures/chains/forge_links_chain.jsonl
```

Expected:
```
form=forge_links
```

The system identifies which legacy format this chain uses.

**What you learned:** Atlas walks hash chains, detects tampering, and
identifies chain formats. The verdict is mathematical, not opinion.

---

## Exercise 2 — Enroll an Agent

**Goal:** Understand structural refusal (`can_approve:false`).

```bash
# 1. Create a .us declaration
cat > my-agent.us << 'EOF'
# My Reader Agent

A document reader.

```json us
{
  "us": 1,
  "id": "reader-1",
  "kind": "agent",
  "mode": "primary"
}
```
EOF

# 2. Try to enroll it
atlas agent enroll data/master.db --dir agents --dry
```

Expected: enrollment reads 40+ existing agents. Your `reader-1` would be
new. The dry run shows what would happen.

**What you learned:** Agents must be declared before they act. The `.us`
format enforces this structurally.

---

## Exercise 3 — Run the Full Prove

**Goal:** Understand the "prove or it didn't happen" discipline.

```bash
# 1. Rust core prove (10 strokes)
atlas --prove
```

```bash
# 2. Go MCP prove (34 strokes)
atlas-mcp --prove
```

```bash
# 3. Go town prove (11 strokes)
atlas-town --prove
```

```bash
# 4. Go door prove (13 strokes)
atlas-door --prove
```

```bash
# 5. TypeScript toolchain prove (11 strokes)
atl self-test
```

**What you learned:** Every binary proves its own correctness. A status
claim is not evidence — run the command.

---

## Exercise 4 — Cut and Verify Goldens

**Goal:** Understand golden-master parity.

```bash
# 1. Run all 17 cutters independently
python tools/cut_canon_vectors.py --verify
python tools/cut_chain_verdicts.py --verify
python tools/cut_us_vectors.py --verify
# ... (see tests/e2e/test_suite.py for the full list)
```

Each cutter produces golden vectors and verifies them against a fresh cut.
"PROVEN" means the goldens are byte-identical.

```bash
# 2. Run the gm harness for one stone
atl gm run --stone A1
```

Expected: 8/8 strokes green across cutters and consumer tests.

**What you learned:** Atlas proves parity between Python originals and
polyglot replacements at the byte level. This is what makes strangler
migration safe.

---

## Exercise 5 — Run the E2E Suite

**Goal:** Understand the full test coverage.

```bash
# Run all 65 tests across 9 layers
python tests/e2e/test_suite.py --verbose
```

Expected output:
```
Layer 1: Binary Smoke         12/12 PASS
Layer 2: Rust Spine           12/12 PASS
Layer 3: Go MCP                3/3  PASS
Layer 4: Go Town               3/3  PASS
Layer 5: Go Door               3/3  PASS
Layer 6: TS atl                8/8  PASS
Layer 7: C++ Kernels           4/4  PASS
Layer 8: Cross-Impl Parity    17/17 PASS
Layer 9: Integration           3/3  PASS

TOTAL: 65/65 PASS — ALL GREEN
```

**What you learned:** The entire system — every binary, every language,
every seam — is tested end-to-end. The E2E suite is the final arbiter.

---

## Answer Key

**Exercise 1:** Why is the steward chain verdict FLIP?  
Because the fixture contains a known-tampered entry. The system correctly
detects the hash mismatch at entry 0 while the weld (prev pointer) still
holds. This is expected behavior for test fixtures.

**Exercise 2:** Why must `can_approve` be explicit?  
Because absence = refusal. If an agent doesn't say "I am safe," the parser
treats it as unsafe. This prevents an agent from gaining authority by
omission — the strongest structural safety guarantee in the market.

**Exercise 3:** Why does every binary have `--prove`?  
Because "prove or it didn't happen." A status claim is not evidence. The
prove command runs hermetic tests on temp grounds and reports pass/fail.
If the prove fails, the binary is broken.

**Exercise 4:** Why Python cutters first?  
Because the Python cutter is the oracle. The atlas artifact must match it
byte-for-byte. This is not "the port passes its own tests" — that's
circular. The oracle is the original implementation.

**Exercise 5:** Why 65 tests?  
Because every layer must be tested: binary smoke, Rust spine, Go services,
TypeScript toolchain, C++ kernels, cross-impl parity, and integration.
Missing any layer means missing a potential failure mode.
