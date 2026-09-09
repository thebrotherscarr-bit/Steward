# E1 Kernels — Rollback Fold Note

**Stone:** E1 (C++ PPMI, digest, predict, foldall, bench)
**Date:** 2026-09-07
**Operator:** Kyler Carr

## What cutover means

The C++ kernels (`kernels/`) are CLI filters — libppmi (51.5× faster
than Python), libdigest, libpredictor, foldall. They are additive; the
Python predictors (`models.py`, `digest.py`, `predictor.py`) remain
authoritative during strangler.

## Port/command mapping (Gx-02)

| Old | New | Match |
|---|---|---|
| `python models.py` | `kernels/ppmi.exe` | Same math, 51.5× faster |
| `python digest.py` | `kernels/digest.exe` | Same pipeline |
| `python predictor.py` | `kernels/predict.exe` | Same expect/surprise |

**No port** — these are CLI filters, not servers.

## Rollback

1. No process to stop — CLI tools invoked on-demand
2. Python predictors remain available and authoritative
3. The Rust `atlas link lay/status` continues to work independently
4. No data loss — kernels are stateless filters

**Fold action:** None required. The C++ kernels are additive.

## Verification

`atl gm run --stone E1` → 3/3 strokes green (ppmi/digest/predict cutters)
