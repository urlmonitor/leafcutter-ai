---
title: "Known issues — ac-driven-dev"
description: "Open, observed defects in the ac-driven-dev component: AC selection and prioritisation, ticket generation from AC records, and the traceability block the downstream gates read. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-14
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/components/phantom-done-prevention.md
---


# Known issues — ac-driven-dev

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACD-YYYYMMDD-HHMM` section, using the UTC time you
filed it (`date -u "+%Y%m%d-%H%M"`). Nothing here is generated — edit it by hand. Fill in what
you actually know; an issue recorded with a thin `Evidence` line is far better than one not
recorded.

**Why datetime ids and not the next free number.** Sequential ids collide whenever two
sessions file at once. On 2026-08-26 alone, two different defects both landed as `KI-CG-012`,
a branch's `KI-BP-010`/`KI-BO-016`/`KI-BO-017` all had to be renumbered at merge because main
had independently minted the same numbers, and a changelog ended up describing `KI-CG-012`
using what became `KI-CG-013`'s text. Renumbering is worse than it sounds — inbound references
do not disambiguate, so a rename can silently repoint a citation at the wrong defect. Existing
`KI-ACD-NNN` entries keep their ids; **do not renumber them.**

This instruction was itself stale until 2026-09-07: the convention changed on 2026-08-26 and
this file kept prescribing next-free-number for twelve days, while the entries being appended
to it had already moved to datetime ids. See `docs/known-issues/build-orchestration.md` for the
canonical wording.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`ac-driven-dev/`](ac-driven-dev/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/ac-driven-dev/open-blocker-*   # anything critical open?
ls docs/known-issues/ac-driven-dev/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`ac-driven-dev/resolved/`](ac-driven-dev/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 27** (3 blocker, 20 high, 4 low) · **Resolved: 1**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace | [open-blocker-ki-acd-004.md](ac-driven-dev/open-blocker-ki-acd-004.md) |
| `blocker` | KI-ACD-005 — User approval gates are dispatched to a `status-checker` agent, whose out-of-scope refusal is parsed as "the user chose cancel" | [open-blocker-ki-acd-005.md](ac-driven-dev/open-blocker-ki-acd-005.md) |
| `blocker` | KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct | [open-blocker-ki-acd-009.md](ac-driven-dev/open-blocker-ki-acd-009.md) |
| `high` | KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces | [open-high-ki-acd-001.md](ac-driven-dev/open-high-ki-acd-001.md) |
| `high` | KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket | [open-high-ki-acd-002.md](ac-driven-dev/open-high-ki-acd-002.md) |
| `high` | KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []` | [open-high-ki-acd-003.md](ac-driven-dev/open-high-ki-acd-003.md) |
| `high` | KI-ACD-006 — A run that authors zero ACs reports `status: "ok"` | [open-high-ki-acd-006.md](ac-driven-dev/open-high-ki-acd-006.md) |
| `high` | KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree | [open-high-ki-acd-007.md](ac-driven-dev/open-high-ki-acd-007.md) |
| `high` | KI-ACD-008 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main | [open-high-ki-acd-008.md](ac-driven-dev/open-high-ki-acd-008.md) |
| `high` | KI-ACD-010 — An ASCII comma in an AC title survives every normalisation step and lands in the epic folder name, the AC store, and Master_Plan | [open-high-ki-acd-010.md](ac-driven-dev/open-high-ki-acd-010.md) |
| `high` | KI-ACD-012 — The generated `Master_Plan.md` is missing six fields the repo's own ticket guard requires | [open-high-ki-acd-012.md](ac-driven-dev/open-high-ki-acd-012.md) |
| `high` | KI-ACD-017 — Epic generation re-scans the whole AC store per ticket, so its cost is tickets × store size and the store only grows | [open-high-ki-acd-017.md](ac-driven-dev/open-high-ki-acd-017.md) |
| `high` | KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle | [open-high-ki-acd-018.md](ac-driven-dev/open-high-ki-acd-018.md) |
| `high` | KI-ACD-019 — `goal_to_epic.py` cites two governing acceptance criteria that do not exist, and five `done` ACs in this register's scope are falsified | [open-high-ki-acd-019.md](ac-driven-dev/open-high-ki-acd-019.md) |
| `high` | KI-ACD-020 — Non-interactive epic generation drops every unapproved leaf AC without naming one of them | [open-high-ki-acd-020.md](ac-driven-dev/open-high-ki-acd-020.md) |
| `high` | KI-ACD-021 — Every `depends_on` edge pointing at an AC's own parent is dropped from the generated ticket, while the Master_Plan still draws it | [open-high-ki-acd-021.md](ac-driven-dev/open-high-ki-acd-021.md) |
| `high` | KI-ACD-022 — Conditional phase agents are written into the agents map without the frontmatter fields they are conditional on, and one of the two fields is written under a different name | [open-high-ki-acd-022.md](ac-driven-dev/open-high-ki-acd-022.md) |
| `high` | KI-ACD-023 — The generated `files_touched` surface admits bare directories and incidental prose while excluding the deliverable the record creates | [open-high-ki-acd-023.md](ac-driven-dev/open-high-ki-acd-023.md) |
| `high` | KI-ACD-20260831-1934 — A ticket's `depends_on` models lifecycle status where the real requirement is an artifact, and on an L2 with a Roman child that closes a cycle no run can exit | [open-high-ki-acd-20260831-1934.md](ac-driven-dev/open-high-ki-acd-20260831-1934.md) |
| `high` | KI-ACD-20260831-agent-contracts-block-not-pipe-delimited — the generator writes the documentation-expert contract as prose, and `documentation-verifier` fail-closes on every generated ticket that has one, before it looks at a single doc | [open-high-ki-acd-20260831-agent-contracts-block-not-pipe-delimited.md](ac-driven-dev/open-high-ki-acd-20260831-agent-contracts-block-not-pipe-delimited.md) |
| `high` | KI-ACD-20260907-1555 — Nothing in the pipeline binds a module or symbol name, so whichever agent needs one first invents it and the next agent cannot see the choice | [open-high-ki-acd-20260907-1555.md](ac-driven-dev/open-high-ki-acd-20260907-1555.md) |
| `high` | KI-ACD-20260909-2130 — Two approved ACs in one epic demand opposite verdicts for the same store state, and nothing in the AC store can detect it | [open-high-ki-acd-20260909-2130.md](ac-driven-dev/open-high-ki-acd-20260909-2130.md) |
| `high` | KI-ACD-20260914-0657 — Every `Master_Plan.md` the generator writes is rejected by the ticket frontmatter gates, so no generated epic can be committed without a hand patch | [open-high-ki-acd-20260914-0657.md](ac-driven-dev/open-high-ki-acd-20260914-0657.md) |
| `high` | KI-ACD-20260921-1600 — An AC with no `risk_surface` generates a ticket with no `ac-validator` and no `ac-fulfillment-gate`, and the store validator passes it | [open-high-ki-acd-20260921-1600.md](ac-driven-dev/open-high-ki-acd-20260921-1600.md) |
| `high` | KI-ACD-20260921-1615 — `expects_from` is never a source for a generated ticket's `depends_on`, so a contract edge survives only if its author also duplicated it into `depends_on` by hand | [open-high-ki-acd-20260921-1615.md](ac-driven-dev/open-high-ki-acd-20260921-1615.md) |
| `low` | KI-ACD-011 — Epic-name truncation has no phrase awareness, so names end on a dangling preposition or article | [open-low-ki-acd-011.md](ac-driven-dev/open-low-ki-acd-011.md) |
| `low` | KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by` | [open-low-ki-acd-014.md](ac-driven-dev/open-low-ki-acd-014.md) |
| `low` | KI-ACD-015 — Epic ordering reads `depends_on` only, so `expects_from` contract edges are invisible to the build sequencer | [open-low-ki-acd-015.md](ac-driven-dev/open-low-ki-acd-015.md) |
| `low` | KI-ACD-016 — Generated tickets carry AC checklist items truncated mid-clause | [open-low-ki-acd-016.md](ac-driven-dev/open-low-ki-acd-016.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `high` | KI-ACD-013 — `goal_to_epic.py` writes a `target_epic` field the AC schema rejects, so every epic it generates fails the required store gate | [resolved-high-ki-acd-013.md](ac-driven-dev/resolved/resolved-high-ki-acd-013.md) |
