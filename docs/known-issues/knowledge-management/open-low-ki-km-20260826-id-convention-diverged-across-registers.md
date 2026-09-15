---
title: "KI-KM-20260826-id-convention-diverged-across-registers — two registers adopted different replacement id forms, eleven still teach the one known not to work"
description: "KI-KM-20260826-id-convention-diverged-across-registers — two registers adopted different replacement id forms, eleven still teach the one known not to work"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-20260826-id-convention-diverged-across-registers — two registers adopted different replacement id forms, eleven still teach the one known not to work

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> **First entry in this file using the date-and-slug id form,** for the reason the entry
> itself describes. The sequential `KI-KM-NNN` entries above keep their ids.

- **Severity:** medium
- **Status:** open — no AC · **partially remediated 2026-09-07 (2 of 11 converted, 9 remain)**
- **Occurrences:** ongoing (introduced 2026-08-26)
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-07
- **Where:** the `## How to use this file` → **Adding an issue** block in all thirteen
  `docs/known-issues/*.md` registers

> **2026-09-07 — re-measured, and the count was exactly right.** A fresh grep for
> `section using the next free number` against `origin/main` returned **eleven** files,
> confirming this entry's measurement thirteen days on: nothing had been converted in the
> interval. Two were fixed in passing while filing unrelated defects —
> `ac-driven-dev.md` (adopted `KI-ACD-YYYYMMDD-HHMM`) and `commit-guardian.md` (adopted
> `KI-CG-YYYYMMDD-short-slug`, that register's own dominant form). **Nine still teach the
> retired scheme:** `agent-registry.md`, `ac-store.md`, `changelog.md`,
> `documentation-system.md`, `feedback-collector.md`, `knowledge-management.md` (this file),
> `security-scanner.md`, `supervisor-system.md`, `testing-quality.md`.
>
> Each converted register declares whichever form its own existing entries already use, per
> fix-direction 1's "the choice matters less than that it is the same everywhere" — applied
> per-file rather than globally, since a global pick would contradict one register or the
> other and no one has made that call. `commit-guardian.md` was 10 slug to 2 timestamp, so a
> timestamp declaration there was drafted and then corrected before commit; check the
> distribution before declaring a form in the remaining nine.
>
> The grep that finds them must be the **prescription**, not the phrase:
> `grep -ln "section using the next free number" docs/known-issues/*.md`. A loose search for
> "next free number" also matches the two registers that were already fixed, because their
> *rationale* section quotes the retired wording in order to argue against it — so the loose
> form reports 13 of 13 and makes a converted register look unconverted.

**Background.** `KI-BO-024` established that *"append the next free number"* cannot work
under concurrent authors: it requires every author to read the same file at the same moment
and act before anyone else does. On 2026-08-25 it produced ten collisions in one day, one
of which reached `main`. The prescribed remedy is a date-plus-slug id, which cannot collide.

**Symptom, measured 2026-08-26 against `origin/main`.** Of the thirteen registers, **two**
adopted a replacement id form and they do not agree with each other, and **eleven** still
instruct the author verbatim to do the thing that is known not to work:

```text
**Adding an issue.** Append a new `### KI-XX-NNN` section using the next free number.
```

| register | its "Adding an issue" says |
|---|---|
| `build-pipeline.md` | `KI-BP-YYYYMMDD-short-slug`, with a full "Why not the next free number" rationale |
| `build-orchestration.md` | `KI-BO-YYYYMMDD-HHMM`, using UTC `date -u "+%Y%m%d-%H%M"` |
| the other eleven | "append the next free number" — unchanged |

So a register's declared convention now depends on which register you open, and neither of
the two that changed mentions the other. An author landing in any of the eleven is told to
use the sequential form by a file that does not mention `KI-BO-024` at all.

**Three id forms are live, and none of them is wrong.** Filed within hours of each other:

| form | example | status |
|---|---|---|
| sequential | `KI-SS-004` | historical, all registers |
| date + time | `KI-BP-20260826-1421` | in four registers; the declared form in `build-orchestration.md` |
| date + slug | `KI-BP-20260826-worktree-hooks-only-on-one-path` | the declared form in `build-pipeline.md` |

Both replacements are collision-free, so this is a consistency problem, not a correctness
one. What makes it worth an entry is *how* it happened: the two forms were adopted
independently, hours apart, by sessions that could not see each other's work — which is the
same concurrency `KI-BO-024` exists to survive, reproduced on the fix for `KI-BO-024`.

**Do not renumber to unify them.** Measured, not assumed: the date-and-time ids already
carry **20 inbound references across four registers**. Renumbering breaks every one, and
`build-pipeline.md`'s own note says the sequential ids must not be renumbered for exactly
this reason. Both forms sort and grep identically on the `KI-XX-` prefix, so the cost of
leaving them is cosmetic and the cost of unifying them is broken cross-references. This
register already carries renumbering scar tissue (`KI-BP-020`, and the `KI-CG-012`
collision) from the last attempt.

**Fix direction.**

1. **Pick one of the two replacement forms and propagate it to all thirteen.** Either works;
   the choice matters less than that it is the same everywhere. Date-and-slug carries more
   information at the grep line, date-and-time is shorter and mechanically derivable from
   `date -u` with no naming judgement — that is the whole trade-off.
2. **Say explicitly that no existing id gets renumbered,** in whichever block is propagated.
   Both replacement forms are already load-bearing.
3. **Keep the block in one place.** `docs/known-issues/README.md` exists; hosting the
   convention there once, with the per-register sections pointing at it, removes the failure
   mode directly. Thirteen copies of one convention is how they came to disagree, and
   propagating a fourteenth copy of the *right* text still leaves the next author free to
   edit one of them.

**Related.** `KI-BO-024` (diagnosed the collision and named the remedy). `KI-BP-020` and the
`KI-CG-012` collision in `commit-guardian.md` (the scar tissue from renumbering).

**Pattern:** a convention fixed in the copy the author happened to be editing, in a system
with thirteen copies.
