# MANJUEL — his own source, given to him as memory

This is the engine's own code, placed in memory so Manjuel grounds
answers about himself in what he actually is. He may describe and
draft from this; he may not rewrite his running self (Art. VII).

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MANJUEL — a local-only, offline-first sovereign intelligence system.
A stewardship engine.

    from manjuel import Manjuel
    m = Manjuel()
    m.awaken()
    print(m.ask("what is the covenant?"))

Properties, by construction:
  * AIR-GAPPED   — on awakening, every network road out of the process is
                   poisoned (socket, resolver, urllib, http.client). Any
                   attempt to reach outward raises SovereigntyBreach and is
                   written to the ledger. Nothing can be un-sealed.
  * SOVEREIGN    — all weights are grown in-process from the four
                   foundational documents (plus working memory). No foreign
                   model, no downloaded weight, no external tool, ever.
  * PYTHON-NATIVE— it is a library first: import it, hold its Answer
                   objects, extend it. The REPL is a courtesy on top.
  * AUDITABLE    — append-only, hash-chained ledger; a sealed covenant mark
                   (SHA-256 over the foundational documents) names each
                   epoch of the engine's life.

Dependencies: the Python standard library. Nothing else. Not even numpy.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field

__version__ = "1.1.0"
ENGINE_NAME = "Manjuel"

# --------------------------------------------------------------------------
# 0. THE SEAL — air-gap enforcement (First Law: the seal precedes the thought)
# --------------------------------------------------------------------------


class SovereigntyBreach(RuntimeError):
    """Raised when anything inside the process tries to reach the network."""


_SEALED = {"on": False, "witness": None}


def _tripwire(*_a, **_k):
    msg = ("SovereigntyBreach: %s is air-gapped. A network call was attempted "
           "and refused. The attempt has been witnessed." % ENGINE_NAME)
    witness = _SEALED.get("witness")
    if witness is not None:
        try:
            witness("breach_attempt", {"detail": "network call refused"})
        except Exception:
            pass
    raise SovereigntyBreach(msg)


class _TripwireSocket:
    """Stands where socket.socket stood. Every use is a breach."""

    def __init__(self, *a, **k):
        _tripwire()

    def __getattr__(self, name):
        _tripwire()


def seal_airgap(witness=None) -> bool:
    """Poison every road out of the machine. Irreversible for this process."""
    import socket as _socket
    import urllib.request as _urlreq
    import http.client as _http

    _SEALED["witness"] = witness
    _socket.socket = _TripwireSocket
    _socket.create_connection = _tripwire
    _socket.create_server = _tripwire
    _socket.getaddrinfo = _tripwire
    _socket.gethostbyname = _tripwire
    _socket.gethostbyaddr = _tripwire
    _socket.socketpair = _tripwire
    _urlreq.urlopen = _tripwire
    _urlreq.OpenerDirector.open = _tripwire
    _http.HTTPConnection.__init__ = _tripwire
    _http.HTTPSConnection.__init__ = _tripwire
    _SEALED["on"] = True
    return True


def seal_is_on() -> bool:
    return _SEALED["on"]


# --------------------------------------------------------------------------
# 1. THE LEDGER — append-only, hash-chained stewardship record
# --------------------------------------------------------------------------


class Ledger:
    """Append-only JSONL ledger. Each entry carries the SHA-256 of the
    previous entry; any tampering anywhere breaks the chain visibly."""

    GENESIS = "0" * 64

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")

    def _last_hash(self) -> str:
        last = None
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last = line
        if last is None:
            return self.GENESIS
        return json.loads(last)["hash"]

    @staticmethod
    def _entry_hash(prev_hash: str, body: dict) -> str:
        canon = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256((prev_hash + canon).encode("utf-8")).hexdigest()

    def record(self, kind: str, payload: dict) -> dict:
        prev = self._last_hash()
        body = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "kind": kind,
            "payload": payload,
            "prev": prev,
        }
        entry = dict(body)
        entry["hash"] = self._entry_hash(prev, body)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self):
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    def verify(self) -> tuple[bool, int, str]:
        """Walk the chain. Returns (intact, n_entries, detail)."""
        prev = self.GENESIS
        n = 0
        for entry in self.entries():
            body = {k: entry[k] for k in ("ts", "kind", "payload", "prev")}
            if entry["prev"] != prev:
                return False, n, "chain break at entry %d (prev mismatch)" % n
            if self._entry_hash(prev, body) != entry["hash"]:
                return False, n, "tamper at entry %d (hash mismatch)" % n
            prev = entry["hash"]
            n += 1
        return True, n, "chain intact"


# --------------------------------------------------------------------------
# 2. THE FOUNDATION — the four documents and the covenant mark
# --------------------------------------------------------------------------


@dataclass
class Doc:
    name: str
    text: str
    sha256: str


class Foundation:
    """Loads the foundational documents and seals the covenant mark."""

    def __init__(self, foundation_dir: str, memory_dir: str):
        self.foundation_dir = foundation_dir
        self.memory_dir = memory_dir
        self.docs: list[Doc] = []
        self.memory_docs: list[Doc] = []
        self.covenant: str = ""
        self.placeholder: bool = False

    @staticmethod
    def _read_dir(path: str) -> list[Doc]:
        docs = []
        if not os.path.isdir(path):
            return docs
        for fn in sorted(os.listdir(path)):
            if not fn.lower().endswith((".md", ".txt")):
                continue
            full = os.path.join(path, fn)
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            docs.append(Doc(fn, text, hashlib.sha256(text.encode("utf-8")).hexdigest()))
        return docs

    def load(self):
        self.docs = self._read_dir(self.foundation_dir)
        self.memory_docs = self._read_dir(self.memory_dir)
        if not self.docs:
            raise RuntimeError(
                "No foundational documents found in %r. %s cannot awaken "
                "on empty ground." % (self.foundation_dir, ENGINE_NAME))
        joined = "".join(d.sha256 for d in self.docs)
        self.covenant = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        self.placeholder = any("PLACEHOLDER" in d.text for d in self.docs)
        return self

    @property
    def mark(self) -> str:
        return self.covenant[:16]

    def corpus_text(self) -> str:
        parts = [d.text for d in self.docs] + [d.text for d in self.memory_docs]
        return "\n\n".join(parts)

    def paragraphs(self) -> list[tuple[str, str]]:
        """[(source_name, paragraph_text), ...] over foundation + memory."""
        out = []
        for d in self.docs + self.memory_docs:
            for para in re.split(r"\n\s*\n", d.text):
                para = re.sub(r"^[#>\-\s]+", "", para.strip(), flags=re.M).strip()
                para = re.sub(r"\s+", " ", para)
                if len(para) > 40:
                    out.append((d.name, para))
        return out


# --------------------------------------------------------------------------
# 3. GROWN MODELS — tokenizer, embeddings, language model (all from scratch)
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?|[.,;:!?()\"—-]")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _stem(w: str) -> str:
    """Featherweight stemmer for overlap matching only (never for the LM)."""
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _stems(text) -> set:
    toks = tokenize(text) if isinstance(text, str) else text
    return {_stem(t) for t in toks if t.isalnum()}


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _normalize(v: list[float]) -> list[float] | None:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 1e-9 else None


class Embedder:
    """Word vectors pressed out of the corpus itself: positive pointwise
    mutual information over a co-occurrence window, compressed by a
    deterministic signed random projection (Johnson–Lindenstrauss).
    Pure standard library; no numpy, no imports, no exceptions."""

    MAX_VOCAB = 3000
    WINDOW = 5
    DIM = 64

    def __init__(self):
        self.vocab: list[str] = []
        self.index: dict[str, int] = {}
        self.vectors: list[list[float]] = []     # V x DIM, L2-normalized
        self.freq: list[float] = []              # unigram probabilities

    @staticmethod
    def _sign_vector(j: int, d: int) -> list[float]:
        """Deterministic ±1 projection vector for context index j."""
        rng = random.Random(0xC0FFEE ^ (j * 1000003))
        return [1.0 if rng.random() < 0.5 else -1.0 for _ in range(d)]

    def train(self, tokens: list[str]):
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        vocab = sorted(counts, key=lambda w: (-counts[w], w))[: self.MAX_VOCAB]
        self.vocab = vocab
        self.index = {w: i for i, w in enumerate(vocab)}
        V = len(vocab)

        # sparse co-occurrence rows: co[i] = {j: weighted count}
        co: list[dict[int, float]] = [dict() for _ in range(V)]
        ids = [self.index.get(t, -1) for t in tokens]
        for i, wi in enumerate(ids):
            if wi < 0:
                continue
            row = co[wi]
            lo = max(0, i - self.WINDOW)
            hi = min(len(ids), i + self.WINDOW + 1)
            for j in range(lo, hi):
                wj = ids[j]
                if j == i or wj < 0:
                    continue
                row[wj] = row.get(wj, 0.0) + 1.0 / abs(j - i)

        total = sum(sum(r.values()) for r in co) or 1.0
        pw = [sum(r.values()) / total for r in co]
        pc = [0.0] * V
        for r in co:
            for j, v in r.items():
                pc[j] += v / total

        d = self.DIM
        signs = [self._sign_vector(j, d) for j in range(V)]
        vecs: list[list[float]] = []
        for i, row in enumerate(co):
            acc = [0.0] * d
            for j, v in row.items():
                pmi = math.log((v / total) / (pw[i] * pc[j] + 1e-12) + 1e-12)
                if pmi <= 0.0:
                    continue                      # positive PMI only
                s = signs[j]
                for k in range(d):
                    acc[k] += pmi * s[k]
            vecs.append(_normalize(acc) or acc)
        self.vectors = vecs

        n = float(sum(counts[w] for w in vocab)) or 1.0
        self.freq = [counts[w] / n for w in vocab]
        return self

    def embed_text(self, text: str) -> list[float] | None:
        """SIF-weighted mean of word vectors; None if no word is known."""
        a = 1e-3
        acc, wsum = None, 0.0
        for t in tokenize(text):
            i = self.index.get(t)
            if i is None:
                continue
            w = a / (a + self.freq[i])
            v = self.vectors[i]
            if acc is None:
                acc = [w * x for x in v]
            else:
                for k in range(len(acc)):
                    acc[k] += w * v[k]
            wsum += w
        if acc is None or wsum == 0.0:
            return None
        return _normalize([x / wsum for x in acc])

    @property
    def n_params(self) -> int:
        return len(self.vectors) * (len(self.vectors[0]) if self.vectors else 0)


class LanguageModel:
    """Interpolated trigram language model, counted and smoothed from the
    corpus sentences. Weights set by deleted interpolation. Generation by
    temperature sampling over observed continuations."""

    BOS, EOS = "<s>", "</s>"

    def __init__(self):
        self.uni: dict[str, int] = {}
        self.bi: dict[str, int] = {}
        self.tri: dict[str, int] = {}
        self.bi_cont: dict[str, list[str]] = {}
        self.tri_cont: dict[str, list[str]] = {}
        self.total = 0
        self.lambdas = (0.1, 0.3, 0.6)

    @staticmethod
    def _k(*toks) -> str:
        return "\x1f".join(toks)

    def train(self, text: str):
        for sent in sentences(text):
            toks = tokenize(sent)
            if not toks:
                continue
            seq = [self.BOS, self.BOS] + toks + [self.EOS]
            for i, w in enumerate(seq):
                self.uni[w] = self.uni.get(w, 0) + 1
                self.total += 1
                if i >= 1:
                    bk = self._k(seq[i - 1], w)
                    if bk not in self.bi:
                        self.bi_cont.setdefault(seq[i - 1], []).append(w)
                    self.bi[bk] = self.bi.get(bk, 0) + 1
                if i >= 2:
                    tk = self._k(seq[i - 2], seq[i - 1], w)
                    ck = self._k(seq[i - 2], seq[i - 1])
                    if tk not in self.tri:
                        self.tri_cont.setdefault(ck, []).append(w)
                    self.tri[tk] = self.tri.get(tk, 0) + 1
        self._fit_lambdas()
        return self

    def _fit_lambdas(self):
        l1 = l2 = l3 = 0.0
        for tk, c in self.tri.items():
            u, v, w = tk.split("\x1f")
            c_uv = self.bi.get(self._k(u, v), 0)
            c_vw = self.bi.get(self._k(v, w), 0)
            c_v = self.uni.get(v, 0)
            c_w = self.uni.get(w, 0)
            f3 = (c - 1) / (c_uv - 1) if c_uv > 1 else 0.0
            f2 = (c_vw - 1) / (c_v - 1) if c_v > 1 else 0.0
            f1 = (c_w - 1) / (self.total - 1) if self.total > 1 else 0.0
            best = max(f1, f2, f3)
            if best == f3:
                l3 += c
            elif best == f2:
                l2 += c
            else:
                l1 += c
        s = l1 + l2 + l3
        if s > 0:
            self.lambdas = (l1 / s, l2 / s, l3 / s)

    def prob(self, u: str, v: str, w: str) -> float:
        l1, l2, l3 = self.lambdas
        p3 = (self.tri.get(self._k(u, v, w), 0) /
              self.bi.get(self._k(u, v), 1)) if self.bi.get(self._k(u, v)) else 0.0
        p2 = (self.bi.get(self._k(v, w), 0) /
              self.uni.get(v, 1)) if self.uni.get(v) else 0.0
        p1 = self.uni.get(w, 0) / max(1, self.total)
        return l3 * p3 + l2 * p2 + l1 * p1

    def perplexity(self, text: str) -> float:
        lp, n = 0.0, 0
        for sent in sentences(text):
            toks = tokenize(sent)
            if not toks:
                continue
            seq = [self.BOS, self.BOS] + toks + [self.EOS]
            for i in range(2, len(seq)):
                p = self.prob(seq[i - 2], seq[i - 1], seq[i])
                lp += math.log(max(p, 1e-12))
                n += 1
        return math.exp(-lp / n) if n else float("inf")

    def _candidates(self, u: str, v: str) -> list[str]:
        cands = list(dict.fromkeys(
            self.tri_cont.get(self._k(u, v), []) + self.bi_cont.get(v, [])))
        if len(cands) < 8:
            top = sorted(self.uni, key=self.uni.get, reverse=True)
            cands += [w for w in top[:40] if w not in cands and w != self.BOS]
        return cands or [self.EOS]

    def generate(self, prompt: str = "", max_tokens: int = 60,
                 temperature: float = 0.8, rng: random.Random | None = None) -> str:
        rng = rng or random.Random()
        toks = tokenize(prompt)
        u, v = (toks[-2], toks[-1]) if len(toks) >= 2 else \
               (self.BOS, toks[-1]) if toks else (self.BOS, self.BOS)
        if v not in self.uni:
            u, v = self.BOS, self.BOS
        out: list[str] = []
        for _ in range(max_tokens):
            cands = self._candidates(u, v)
            inv_t = 1.0 / max(temperature, 1e-3)
            weights = [max(self.prob(u, v, w), 1e-12) ** inv_t for w in cands]
            w = rng.choices(cands, weights=weights)[0]
            if w == self.EOS:
                if len(out) > 4:
                    break
                u, v = self.BOS, self.BOS
                continue
            if w == self.BOS:
                continue
            out.append(w)
            u, v = v, w
        return detokenize(out)

    @property
    def n_params(self) -> int:
        return len(self.uni) + len(self.bi) + len(self.tri)


def detokenize(tokens: list[str]) -> str:
    text = ""
    for t in tokens:
        if t in ".,;:!?)":
            text = text.rstrip() + t + " "
        elif t == "(":
            text += "("
        else:
            text += t + " "
    text = text.strip()
    # capitalize sentence starts
    def _cap(m):
        return m.group(1) + m.group(2).upper()
    text = re.sub(r"(^|[.!?]\s+)([a-z])", _cap, text)
    if text and text[-1] not in ".!?":
        text += "."
    return text


# --------------------------------------------------------------------------
# 4. ANSWERS — grounded objects the steward's own code can hold
# --------------------------------------------------------------------------


@dataclass
class Answer:
    question: str
    text: str
    ground: list[dict] = field(default_factory=list)   # [{source, passage, score}]
    covenant: str = ""
    thin_ground: bool = False

    def __str__(self):
        lines = [self.text]
        if self.ground:
            lines.append("")
            lines.append("— ground —")
            for g in self.ground:
                lines.append("  [%s · %.2f] %s" % (
                    g["source"], g["score"],
                    g["passage"][:110] + ("…" if len(g["passage"]) > 110 else "")))
        return "\n".join(lines)

    __repr__ = __str__


# --------------------------------------------------------------------------
# 5. THE ENGINE
# --------------------------------------------------------------------------


class Manjuel:
    """The stewardship engine. Import it, awaken it, hold it."""

    def __init__(self, root: str | None = None, seal: bool = True,
                 seed: int | None = None):
        self.root = os.path.abspath(root or os.path.dirname(os.path.abspath(__file__)))
        self.dirs = {
            "foundation": os.path.join(self.root, "foundation"),
            "memory": os.path.join(self.root, "memory"),
            "weights": os.path.join(self.root, "weights"),
            "ledger": os.path.join(self.root, "ledger"),
        }
        for d in self.dirs.values():
            os.makedirs(d, exist_ok=True)
        self.ledger = Ledger(os.path.join(self.dirs["ledger"], "ledger.jsonl"))
        self.foundation = Foundation(self.dirs["foundation"], self.dirs["memory"])
        self.embedder = Embedder()
        self.lm = LanguageModel()
        self._paras: list[tuple[str, str]] = []
        self._para_vecs: list[list[float] | None] = []
        self._awake = False
        self._seal_requested = seal
        self._rng = random.Random(seed)

    # -- lifecycle ---------------------------------------------------------

    def awaken(self, retrain: bool = False) -> "Manjuel":
        if self._seal_requested and not seal_is_on():
            seal_airgap(witness=self.ledger.record)
            self.ledger.record("seal", {"detail": "air-gap sealed; all network "
                                        "roads poisoned for this process"})
        self.foundation.load()
        manifest_path = os.path.join(self.dirs["weights"], "covenant.json")
        prior = None
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                prior = json.load(f)

        renewed = prior is None or prior.get("covenant") != self.foundation.covenant
        cache = os.path.join(self.dirs["weights"],
                             "weights_%s.json" % self.foundation.mark)
        if retrain or renewed or not os.path.exists(cache):
            self._train()
            self._save_weights(cache)
            manifest = {
                "engine": ENGINE_NAME,
                "version": __version__,
                "covenant": self.foundation.covenant,
                "mark": self.foundation.mark,
                "ancestor": (prior or {}).get("covenant"),
                "docs": {d.name: d.sha256 for d in self.foundation.docs},
                "epoch_sealed": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            self.ledger.record(
                "covenant_renewed" if renewed and prior else "covenant_sealed",
                {"mark": self.foundation.mark,
                 "docs": [d.name for d in self.foundation.docs],
                 "ancestor": (prior or {}).get("mark"),
                 "placeholder_ground": self.foundation.placeholder})
        else:
            self._load_weights(cache)
        self._index_paragraphs()
        self._awake = True
        self.ledger.record("awaken", {
            "mark": self.foundation.mark,
            "vocab": len(self.embedder.vocab),
            "params": self.n_params,
            "sealed": seal_is_on(),
        })
        return self

    def _train(self):
        text = self.foundation.corpus_text()
        toks = tokenize(text)
        self.embedder = Embedder().train(toks)
        self.lm = LanguageModel().train(text)

    def _index_paragraphs(self):
        self._paras = self.foundation.paragraphs()
        self._para_vecs = [self.embedder.embed_text(p) for _, p in self._paras]
        self._para_stems = [_stems(p) for _, p in self._paras]
        self._df = {}
        for st in self._para_stems:
            for s in st:
                self._df[s] = self._df.get(s, 0) + 1

    def _idf(self, stem: str) -> float:
        df = self._df.get(stem, 0)
        return math.log(1.0 + len(self._paras) / (df + 0.5)) if df else 0.0

    # -- weights on disk ---------------------------------------------------

    def _save_weights(self, path: str):
        blob = {
            "vocab": self.embedder.vocab,
            "vectors": [[round(x, 6) for x in v] for v in self.embedder.vectors],
            "freq": self.embedder.freq,
            "lm": {"uni": self.lm.uni, "bi": self.lm.bi, "tri": self.lm.tri,
                   "bi_cont": self.lm.bi_cont, "tri_cont": self.lm.tri_cont,
                   "total": self.lm.total, "lambdas": self.lm.lambdas},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(blob, f, ensure_ascii=False)

    def _load_weights(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            side = json.load(f)
        self.embedder = Embedder()
        self.embedder.vocab = side["vocab"]
        self.embedder.index = {w: i for i, w in enumerate(side["vocab"])}
        self.embedder.vectors = side["vectors"]
        self.embedder.freq = side["freq"]
        lm = LanguageModel()
        s = side["lm"]
        lm.uni, lm.bi, lm.tri = s["uni"], s["bi"], s["tri"]
        lm.bi_cont, lm.tri_cont = s["bi_cont"], s["tri_cont"]
        lm.total, lm.lambdas = s["total"], tuple(s["lambdas"])
        self.lm = lm

    # -- the voice ---------------------------------------------------------

    def _require_awake(self):
        if not self._awake:
            raise RuntimeError("%s is not awake. Call .awaken() first." % ENGINE_NAME)

    def ask(self, question: str, k: int = 3) -> Answer:
        """Retrieval-grounded answer: every sentence traceable to ground."""
        self._require_awake()
        qv = self.embedder.embed_text(question)
        q_toks = _stems(question) - {"the", "a", "an", "i", "of", "to",
                                     "in", "and", "what", "who", "how",
                                     "doe", "why", "it", "wa"}
        q_idf = sum(self._idf(s) for s in q_toks) or 1.0
        scores = [0.0] * len(self._paras)
        for i in range(len(self._paras)):
            pv = self._para_vecs[i]
            if qv is not None and pv is not None:
                scores[i] = _dot(pv, qv)
            matched = q_toks & self._para_stems[i]
            scores[i] += 0.5 * sum(self._idf(s) for s in matched) / q_idf
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        ground = [{"source": self._paras[i][0],
                   "passage": self._paras[i][1],
                   "score": round(scores[i], 4)} for i in order if scores[i] > 0.05]

        thin = len(ground) == 0 or ground[0]["score"] < 0.25
        if not ground:
            text = ("The ground I hold carries nothing for this. The covenant "
                    "forbids me to dress a guess in confidence: I do not know.")
        else:
            best_sents = self._best_sentences(question, ground, n=3)
            text = " ".join(best_sents)
            if thin:
                text += (" (The ground here is thin; hold this answer loosely "
                         "or plant richer memory for me to draw on.)")
        ans = Answer(question=question, text=text, ground=ground,
                     covenant=self.foundation.mark, thin_ground=thin)
        self.ledger.record("ask", {"q": question, "thin": thin,
                                   "sources": [g["source"] for g in ground]})
        return ans

    def _best_sentences(self, question: str, ground: list[dict], n: int = 3):
        qv = self.embedder.embed_text(question)
        q_toks = _stems(question)
        scored = []
        for g in ground:
            for s in sentences(g["passage"]):
                sv = self.embedder.embed_text(s)
                sim = _dot(sv, qv) if (sv is not None and qv is not None) else 0.0
                sim += 0.3 * (len(q_toks & _stems(s)) / max(1, len(q_toks)))
                scored.append((sim, s))
        scored.sort(key=lambda x: -x[0])
        seen, out = set(), []
        for _, s in scored:
            if s not in seen:
                out.append(s)
                seen.add(s)
            if len(out) >= n:
                break
        return out

    def generate(self, prompt: str = "", max_tokens: int = 60,
                 temperature: float = 0.8) -> str:
        """Free generation from the grown language model."""
        self._require_awake()
        text = self.lm.generate(prompt, max_tokens, temperature, self._rng)
        self.ledger.record("generate", {"prompt": prompt, "n_chars": len(text)})
        return text

    def remember(self, note: str) -> str:
        """Plant a note in working memory (third chamber) and re-index."""
        self._require_awake()
        fn = os.path.join(self.dirs["memory"], "notes.md")
        stamp = time.strftime("%Y-%m-%d %H:%M")
        with open(fn, "a", encoding="utf-8") as f:
            f.write("\n\n[%s] %s" % (stamp, note.strip()))
        self.foundation.load()
        self._index_paragraphs()
        self.ledger.record("remember", {"note": note[:200]})
        return "Planted in working memory and woven into the index."

    # -- audit (Fourth Law: the steward can always audit) ------------------

    def audit(self) -> dict:
        intact, n, detail = self.ledger.verify()
        report = {
            "engine": "%s v%s" % (ENGINE_NAME, __version__),
            "sealed_airgap": seal_is_on(),
            "covenant_mark": self.foundation.mark,
            "foundational_docs": [d.name for d in self.foundation.docs],
            "placeholder_ground": self.foundation.placeholder,
            "vocab_size": len(self.embedder.vocab),
            "embedding_dim": (len(self.embedder.vectors[0])
                              if self.embedder.vectors else 0),
            "n_params": self.n_params,
            "lm_perplexity_on_foundation": round(
                self.lm.perplexity(self.foundation.corpus_text()), 2),
            "ledger": {"entries": n, "intact": intact, "detail": detail},
            "weights_sleep_at": self.dirs["weights"],
        }
        self.ledger.record("audit", {"intact": intact, "entries": n})
        return report

    def reflect(self) -> str:
        r = self.audit()
        lines = [
            "%s — sovereign, air-gapped=%s, covenant %s" % (
                r["engine"], r["sealed_airgap"], r["covenant_mark"]),
            "foundation: %s%s" % (
                ", ".join(r["foundational_docs"]),
                "  [PLACEHOLDER GROUND — awaiting the true four]"
                if r["placeholder_ground"] else ""),
            "grown weights: %d words × %d dims + %d n-gram counts = %d params" % (
                r["vocab_size"], r["embedding_dim"],
                r["n_params"] - r["vocab_size"] * r["embedding_dim"],
                r["n_params"]),
            "perplexity on own foundation: %s" % r["lm_perplexity_on_foundation"],
            "ledger: %d entries, %s" % (r["ledger"]["entries"], r["ledger"]["detail"]),
        ]
        return "\n".join(lines)

    @property
    def n_params(self) -> int:
        return self.embedder.n_params + self.lm.n_params

    # -- courtesy REPL -----------------------------------------------------

    def repl(self):  # pragma: no cover
        self._require_awake()
        print("\n%s v%s — sovereign stewardship engine" % (ENGINE_NAME, __version__))
        print("covenant %s · air-gap %s · %d params grown from the foundation"
              % (self.foundation.mark, "SEALED" if seal_is_on() else "OPEN",
                 self.n_params))
        print("commands: :reflect :audit :gen <prompt> :remember <note> "
              ":breach :quit — anything else is a question\n")
        while True:
            try:
                line = input("steward> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in (":quit", ":q", ":exit"):
                self.ledger.record("rest", {})
                print("%s rests. The ledger holds." % ENGINE_NAME)
                break
            elif line == ":reflect":
                print(self.reflect())
            elif line == ":audit":
                print(json.dumps(self.audit(), indent=2))
            elif line.startswith(":gen"):
                print(self.generate(line[4:].strip()))
            elif line.startswith(":remember"):
                print(self.remember(line[9:].strip()))
            elif line == ":breach":
                try:
                    import urllib.request
                    urllib.request.urlopen("http://example.com")
                except SovereigntyBreach as e:
                    print("REFUSED —", e)
            else:
                print(self.ask(line))
            print()


# --------------------------------------------------------------------------


def main():  # pragma: no cover
    root = sys.argv[1] if len(sys.argv) > 1 else None
    m = Manjuel(root=root)
    m.awaken()
    m.repl()


if __name__ == "__main__":
    main()

```
