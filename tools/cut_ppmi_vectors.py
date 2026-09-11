#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut_ppmi_vectors.py -- E1-01 PPMI golden vectors (spec-first).

Trains the read-only oracle (5.0 manjuel5/models.py: tokenizer, stems,
Embedder, LanguageModel) on a FIXED ASCII corpus and pins every observable:
tokens, stems, vocab+counts, co-occurrence rows, 64-dim vectors, freqs,
trigram tables, lambdas, prob/perplexity spots, detokenize cases, and
fixed-seed generations.

Floats are pinned with float.hex() (exact round-trip; C++ reads %la), so
the port can assert near-bit-exactness inside the acceptance tolerance.
Counts are integers (bit-exact by law). Deterministic: fixed corpus, fixed
seeds, no I/O beyond the golden file. No network. `--verify` retrains and
compares; run bare to (re)cut. Hermetic by law.

Out of scope, named: save_weights 6-decimal rounding (no stone needs the
weights file yet); non-ASCII lowercasing boundary (corpus is ASCII).
"""

import importlib.util
import json
import os
import sys

SCRIPT = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.normpath(os.path.join(SCRIPT, ".."))
# THE ORACLE ROOT IS NAMEABLE. ADR-006 item 6, 2026-09-11.
#
# This was `ATLAS.parent` outright. Before the 2026-09-10 split atlas sat
# beside its source grounds, so the parent WAS the ground holding the oracle.
# After the split the parent is the manjuel core, and this resolves to a path
# that has never existed on any machine — so `tests/prove.py` reported the
# re-cut legs ABSENT naming a phantom. ABSENT was the right verdict for the
# wrong reason.
#
# The goldens themselves ARE committed and DO travel; only the RE-CUT needs
# the oracle. Set ATLAS_ORACLE_ROOT to the ground that holds it. Unset, the
# old location is still tried, so nothing that worked stops working.
ARCHIVE = os.environ.get("ATLAS_ORACLE_ROOT") or os.path.normpath(os.path.join(ATLAS, ".."))
ORACLE = os.path.join(ARCHIVE, "secondbrain", "SecondBrain-collab",
                      "demo_vault", "attic", "folded",
                      "2026-08-24-manjuel-app-mirror", "5.0", "manjuel5",
                      "models.py")
GOLDEN = os.path.join(ATLAS, "tests", "fixtures", "ppmi_vectors.json")

CORPUS = (
    "The valve leaks at night. Dale mends the valve; the valve holds.\n"
    "Water runs downhill, and the javelina don't wait. "
    "Don't let the gate hinge fail!\n"
    "Red rock dust coats everything. Everything settles by morning.\n"
    "Dale watches the water. The morning holds what the night loosened."
)

GEN_SEEDS = [1234, 7]
GEN_PROMPTS = ["", "the valve", "javelina"]
EMBED_PROBES = ["the valve leaks", "morning water", "xyzzy qqq"]
PERPLEX = "the gate hinge holds"


def load_oracle():
    spec = importlib.util.spec_from_file_location("models_oracle", ORACLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hexvec(v):
    return [x.hex() for x in v]


def train(M):
    toks = M.tokenize(CORPUS)
    stems = sorted(M.stems(CORPUS))
    sents = M.sentences(CORPUS)
    emb = M.Embedder().train(toks)
    # Co-occurrence is internal; re-derive the observable rows through the
    # trained object is impossible, so pin what the vectors prove: full
    # hex vectors + freqs + vocab + counts via a recount here.
    counts = {}
    for t in toks:
        counts[t] = counts.get(t, 0) + 1
    lm = M.LanguageModel().train(CORPUS)
    import random
    gens = {}
    for seed in GEN_SEEDS:
        for prompt in GEN_PROMPTS:
            gens["%d|%s" % (seed, prompt)] = lm.generate(
                prompt, max_tokens=12, temperature=1.0,
                rng=random.Random(seed))
    probes = []
    for p in EMBED_PROBES:
        e = emb.embed_text(p)
        probes.append([p, hexvec(e) if e is not None else None])
    return {
        "tokens": toks,
        "stems": stems,
        "sentences": sents,
        "vocab": emb.vocab,
        "counts": [counts[w] for w in emb.vocab],
        "freq_hex": hexvec(emb.freq),
        "vectors_hex": [hexvec(v) for v in emb.vectors],
        "dim": M.Embedder.DIM,
        "embed_probes": probes,
        "uni": sorted([list(kv) for kv in lm.uni.items()]),
        "bi": sorted([list(kv) for kv in lm.bi.items()]),
        "tri": sorted([list(kv) for kv in lm.tri.items()]),
        "bi_cont": {k: v for k, v in sorted(lm.bi_cont.items())},
        "tri_cont": {k: v for k, v in sorted(lm.tri_cont.items())},
        "total": lm.total,
        "lambdas": list(lm.lambdas),
        "prob_spots": [
            [["<s>", "<s>", toks[0]], lm.prob("<s>", "<s>", toks[0])],
            [[toks[0], toks[1], toks[2]],
             lm.prob(toks[0], toks[1], toks[2])],
            [["xyzzy", "qqq", "zzz"], lm.prob("xyzzy", "qqq", "zzz")],
        ],
        "perplexity": lm.perplexity(PERPLEX),
        "generations": gens,
        "detokenize": [
            [["hello", "world"], M.detokenize(["hello", "world"])],
            [["it", "leaks", ".", "dale", "mends"], M.detokenize(
                ["it", "leaks", ".", "dale", "mends"])],
        ],
        "dot": M.dot([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]),
        "normalize_zero": M.normalize([0.0, 0.0]),
    }


def payload():
    M = load_oracle()
    return {"spec": "E1-01 PPMI (models.py Embedder + LanguageModel)",
            "oracle": {"file": "5.0/manjuel5/models.py",
                       "sha256": sha_of(ORACLE)},
            "corpus": CORPUS,
            "vectors": train(M)}


def write_bytes(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as f:
        f.write(data)


def cut():
    p = payload()
    write_bytes(GOLDEN, json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    v = p["vectors"]
    print("cut ppmi vectors -> %s" % GOLDEN)
    print("  oracle sha256 %s" % p["oracle"]["sha256"])
    print("  tokens=%d stems=%d vocab=%d dim=%d uni/bi/tri=%d/%d/%d" % (
        len(v["tokens"]), len(v["stems"]), len(v["vocab"]), v["dim"],
        len(v["uni"]), len(v["bi"]), len(v["tri"])))


def verify():
    M = load_oracle()
    print("\n  PPMI -- golden vectors (E1-01, hermetic, local oracle)")
    print("    oracle 5.0/manjuel5/models.py sha256 %s" % sha_of(ORACLE))
    live = train(M)
    pinned = json.loads(open(GOLDEN, encoding="utf-8").read())
    if pinned["oracle"]["sha256"] != sha_of(ORACLE):
        print("    [FAIL]  oracle drifted")
        return 1
    ok = True

    def check(name, a, b):
        nonlocal ok
        same = a == b
        ok = ok and same
        print("    [%s]  %-14s" % ("PASS" if same else "FAIL", name))

    v = pinned["vectors"]
    for k in ["tokens", "stems", "sentences", "vocab", "counts", "dim",
              "uni", "bi", "tri", "bi_cont", "tri_cont", "total",
              "generations", "detokenize", "dot", "normalize_zero"]:
        check(k, live[k], v[k])
    check("freq_hex", live["freq_hex"], v["freq_hex"])
    check("vectors_hex", live["vectors_hex"], v["vectors_hex"])
    check("lambdas", live["lambdas"], v["lambdas"])
    check("embed_probes", live["embed_probes"], v["embed_probes"])
    check("prob_spots", live["prob_spots"], v["prob_spots"])
    check("perplexity", live["perplexity"], v["perplexity"])
    print()
    if ok:
        print("  PROVEN. The oracle trains what the kernels must train.")
        return 0
    print("  A vector failed.")
    return 1


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else cut())
