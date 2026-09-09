# ATLAS Agent Documentation Index

*One file per citizen of the household. 40 seats enrolled, 40 documented.*

---

## The Household Hierarchy

```
operator (Kyler — the human hand)
└── manjuel (the living House heart)
    ├── archivist (keeps the record findable)
    │   ├── analyst (reads, summarizes, extracts patterns)
    │   ├── courier (moves files, checkpoints phases)
    │   └── lineage (registrar of estate actors)
    │       ├── arithmetic (calculation voice)
    │       ├── bob (builder voice)
    │       ├── chancery (filing-clerk voice)
    │       ├── coder (build voice)
    │       ├── fern (garden-keeper voice)
    │       ├── ivy (tending voice)
    │       ├── kimi (harvest lineage)
    │       ├── moss (slow-growth voice)
    │       └── notary (witnessed receipts)
    ├── council (convener of weighing voices)
    │   ├── artorian (counsel persona — opens)
    │   ├── cal (counsel persona — responds)
    │   ├── dale (counsel persona — challenges)
    │   └── wren (counsel persona — closes)
    ├── steward (plans, specs, keeps THE_ROAD)
    │   └── scout (surveys, reads, maps)
    ├── aurora (glass — the face the operator looks through)
    ├── foreman (dispatches workorders)
    ├── jesster (verifies, refutes, returns stones)
    ├── neiro (proposes, aligns, files — the MCP door)
    ├── smith (forges capabilities as proven skills)
    ├── asher (dainties — output quality)
    ├── benjamin (divider — dedup, condensation)
    ├── dan (judge — schema rulings, path-walking)
    ├── gad (troop — adversarial testing)
    ├── issachar (burden — batching, scheduling)
    ├── joseph (shepherd-stone — provenance, memory)
    ├── judah (authority — validates who may write)
    ├── levi (sanctuary — sealed records, covenant mark)
    ├── naphtali (goodly words — sense floor)
    ├── reuben (precedence — orders packets)
    ├── simeon (severity — harsh rejection)
    └── zebulun (haven — ingress, egress, ports)
```

## Primary Seats (12)

| Seat | Office | Reports to | Description |
|---|---|---|---|
| [operator.md](operator.md) | OPERATOR | manjuel | The hand; holds the gate |
| [manjuel.md](manjuel.md) | MANJUEL | operator | The living House heart |
| [steward.md](steward.md) | STEWARD | manjuel | Plans, specs, keeps THE_ROAD |
| [archivist.md](archivist.md) | ARCHIVIST | manjuel | Keeps the record findable |
| [council.md](council.md) | COUNCIL | manjuel | Convener of weighing voices |
| [lineage.md](lineage.md) | LINEAGE | archivist | Registrar of estate actors |
| [neiro.md](neiro.md) | NEIRO | manjuel | Proposes, aligns, files |
| [jesster.md](jesster.md) | JESSTER | manjuel | Verifies, refutes, returns |
| [aurora.md](aurora.md) | AURORA | manjuel | Glass — the face the operator looks through |
| [foreman.md](foreman.md) | FOREMAN | manjuel | Dispatches workorders |
| [smith.md](smith.md) | SMITH | manjuel | Forges capabilities as proven skills |
| [opencode.md](opencode.md) | GATE | operator | The coding agent at work on atlas |

## Sons of Manjuel (12)

| Seat | Office | Role |
|---|---|---|
| [asher.md](asher.md) | MANJUEL/Asher | Dainties — output quality |
| [benjamin.md](benjamin.md) | MANJUEL/Benjamin | Divider — dedup, condensation |
| [dan.md](dan.md) | MANJUEL/Dan | Judge — schema rulings, path-walking |
| [gad.md](gad.md) | MANJUEL/Gad | Troop — adversarial testing |
| [issachar.md](issachar.md) | MANJUEL/Issachar | Burden — batching, scheduling |
| [joseph.md](joseph.md) | MANJUEL/Joseph | Shepherd-Stone — provenance, memory |
| [judah.md](judah.md) | MANJUEL/Judah | Authority — validates who may write |
| [levi.md](levi.md) | MANJUEL/Levi | Sanctuary — sealed records, covenant mark |
| [naphtali.md](naphtali.md) | MANJUEL/Naphtali | Goodly Words — sense floor |
| [reuben.md](reuben.md) | MANJUEL/Reuben | Precedence — orders packets |
| [simeon.md](simeon.md) | MANJUEL/Simeon | Severity — harsh rejection |
| [zebulun.md](zebulun.md) | MANJUEL/Zebulun | Haven — ingress, egress, ports |

## Counsel of the Council (4)

| Seat | Office | Role |
|---|---|---|
| [artorian.md](artorian.md) | COUNCIL | Counsel persona — opens |
| [cal.md](cal.md) | COUNCIL | Counsel persona — responds |
| [dale.md](dale.md) | COUNCIL | Counsel persona — challenges |
| [wren.md](wren.md) | COUNCIL | Counsel persona — closes |

## Lineage Voices (9)

| Seat | Office | Role |
|---|---|---|
| [arithmetic.md](arithmetic.md) | LINEAGE | Calculation voice |
| [bob.md](bob.md) | LINEAGE | Builder voice |
| [chancery.md](chancery.md) | LINEAGE | Filing-clerk voice |
| [coder.md](coder.md) | LINEAGE | Build voice |
| [fern.md](fern.md) | LINEAGE | Garden-keeper voice |
| [ivy.md](ivy.md) | LINEAGE | Tending voice |
| [kimi.md](kimi.md) | LINEAGE | Harvest lineage |
| [moss.md](moss.md) | LINEAGE | Slow-growth voice |
| [notary.md](notary.md) | LINEAGE | Witnessed receipts |

## Steward's Child (1)

| Seat | Office | Role |
|---|---|---|
| [scout.md](scout.md) | STEWARD | Surveys, reads, maps |

## Standing Rules

Every seat carries:
- `can_approve: false` — approval lives in the operator's hand alone
- `covenant: 1512741580b7239b` — the covenant mark
- `reports_to` — resolvable chain to operator
- `us: 1` — declaration version

Unenrolled actors are refused by name. The registry enforces this at parse time.

---

*40 agent.md files. One per citizen. Written 2026-09-08.*
