# GUIDED DEMO — a scripted live tour of atlas

*Every command below was executed for real on 2026-08-24; outputs shown are
actual. Run top to bottom in PowerShell. Nothing touches estate\ or
secondbrain\ — reads only, and today not even those.*

---

## Act 1 — Prove the ground

```powershell
cd C:\Users\novad\Desktop\Archive\atlas
Get-Content VERSION
```

```
0.1.0+p0
```

The build's identity: semver + stone tag. Every future binary will answer
`--version` with this exact string.

## Act 2 — The venv law

```powershell
powershell -ExecutionPolicy Bypass -File tools\make_venv.ps1
```

```
Python 3.14.7
venv ready: C:\Users\novad\Desktop\Archive\atlas\.venv\Scripts\python.exe
pip 26.2.1 from ...\.venv\Lib\site-packages\pip (python 3.14)
```

Idempotent: safe to re-run any time. All Python rides `.venv` (CHARTER §6).

## Act 3 — Seed and prove the catalog

```powershell
$py = ".venv\Scripts\python.exe"
& $py tools\seed_catalog.py
& $py tools\seed_catalog.py --verify
```

```
master.db: rulings=5 catalog=73 agents=0 (empty until A2)
VERIFY OK: dispositions valid, no dupes, schema complete, WAL on
```

Run it twice — identical output. That is the idempotency proof (row P0-03).
`agents=0` is honest: enrollment opens at A2.

## Act 4 — Ask the catalog questions

```powershell
& $py -c "import sqlite3; c=sqlite3.connect('data/master.db'); q=lambda s:[print(*r) for r in c.execute(s)]; print('-- by disposition'); q('SELECT disposition, COUNT(*) AS n FROM catalog GROUP BY disposition ORDER BY n DESC')"
```

Actual output:

```
-- by disposition
PORT 34
ADAPT 19
NEW 7
HARVEST 6
KEEP 4
FOLD 3
```

By language:

```
go 25 | rust 15 | json 8 | ts 7 | sqlite 7 | cpp 6 | python 2 | mixed 2 | md 1
```

By stone:

```
A1 15 | A2 3 | B1 4 | C1 4 | D1 5 | D2 2 | D3 5 | E1 7 | F1 14 | G-stone 9 | P0 1
```

Reading: A1 carries the heaviest load (the spine everything stands on);
F1+G-stones carry the long tail.

## Act 5 — Watch the sync law where it lives

```powershell
& $py -c "import sqlite3; c=sqlite3.connect('data/master.db'); [print(*r) for r in c.execute('SELECT name FROM sqlite_master WHERE type=''table''')]"
```

```
rulings | catalog | agents | journal_sync
```

`journal_sync` is empty today because no chain has been imported yet — but
its presence is the promise: when ledger.db lands at A1, every write order
is *record first, state second*, replay-on-open, refuse-on-break
(SPEC_SQLITE "Journaled-ledger sync").

## Act 6 — Read the road

```powershell
Get-Content STATE_OF_BUILD.md -Tail 12
```

The tail always answers "how far along are we?" — currently P0 complete,
stopped at your review gate.

## Act 7 — What you would see after A1 (preview, honest)

These commands do NOT work yet:

```powershell
atlas chain verify --roots estate   # A1-02
atlas covenant check                # A1-07
atl gm run --stone A1               # Gx golden masters
```

They appear with their acceptance rows the moment A1 opens. Their expected
outputs are already frozen in ACCEPTANCE.md — that is the point.

---

**End of demo.** Where to go: `docs\TUTORIAL.md` (learn by doing) ·
`docs\WALKTHROUGH.md` (understand the whole) · `specs\` (build against
them). To open A1: give the word.
