---
title: "KI-BO-20260923-0630 — finalize-feature writes status: done by rewriting the frontmatter, so the single-writer close path has a second door"
description: "KI-BO-20260923-0630 — finalize-feature writes status: done by rewriting the frontmatter, so the single-writer close path has a second door"
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/architecture/adrs/ADR-047-single-writer-ticket-close-path.md
  - docs/architecture/diagrams/c3-008-ticket-close-paths-sequence.md
---

# KI-BO-20260923-0630 — finalize-feature writes `status: done` by rewriting the frontmatter, so the single-writer close path has a second door

- **Severity:** high — it defeated the invariant EPIC-WorkIsOnlyEverMarkedFinishedThroughThe
  was built to establish, on a path that runs against every ticket of a finalized epic.
- **Status:** resolved — see `BO-400e-3-i` (the fix), landed 2026-09-23 yet
- **Occurrences:** 1 (found 2026-09-23 by BO-400e-5's own diagram, not by a drive)
- **First seen:** 2026-09-23 · **Last seen:** 2026-09-23
- **Where:** `templates/workflows-js/finalize-feature.js`, step 3.5 sub-step C, the
  dispatch prompt at lines 1599-1604.

**Symptom.** The instruction reads, verbatim:

```
"=== SUB-STEP C: SET status: done ===\n" +
"For each ticket in OPEN_TICKETS:\n" +
"  Read the file content.\n" +
"  Replace the `status: <value>` line in the YAML frontmatter with `status: done`.\n" +
"  Write the updated content back to the file.\n" +
```

There is no invocation of `scripts/set_ticket_status.py`. So this write has no parity check
against the ticket's own `agents:` map, no transition validation, and no possibility of
refusal. It cannot decline to close a ticket whose record says it is not finished.

**Why it matters.** [ADR-047](../../architecture/adrs/ADR-047-single-writer-ticket-close-path.md)
§1 states that the finished state is written by one mechanism and that "no other agent,
script, workflow step, or prompt MUST write that value by any other means". This is that,
and it is reached on the ordinary finalization path rather than in some corner: it runs
over every still-open ticket in the epic being finalized.

The consequence is the exact failure the BO-400e family was built to remove, relocated one
step later in the lifecycle. BO-400e-1 through BO-400e-4 made the drivers' close a decision
taken against the ticket's own record. A ticket that those drivers correctly REFUSED to
close — because its record still names an unaccounted phase — is closed anyway by finalize,
silently, with no record of the refusal having been overridden.

**How it was found, and why that is the notable part.** Not by a drive, and not by a test.
`BO-400e-5` required a sequence diagram of every route to the finished state, on the stated
principle that "a route which is not drawn is a route which does not exist". Enumerating the
writers to satisfy that clause is what surfaced this one. The epic's own capstone
documentation task found the defect the epic's four implementation tickets had missed,
because it was the first artefact that required the set of writers to be **complete** rather
than merely correct.

**Consequence for BO-400e-5's own AC-7.** That criterion reads "exactly one path in the
diagram ends in the finished state being written, and that path passes through the checking
mechanism". With this route drawn — and it must be drawn, per the AC's own
every-participant clause — the diagram contains two paths that end in the finished state
being written, and only one goes through the mechanism. AC-7 is therefore **not satisfied**,
and is deliberately left unchecked on ticket 05. It becomes true when this issue is fixed,
not before. Narrowing AC-7's scope to "inside the close" so that it passes would be the same
softening-the-check move the whole epic exists to refuse.

**A second, dormant claim.** `templates/agents/ticket-supervisor.md`'s Constraints section
still names "flipping `status: todo` -> `status: done`" as a write surface it owns. That
agent is no longer dispatched for phase execution (ADR-006 flattened the supervisor chain),
so it is not a live route today — but a change that revives the agent revives an ungated
writer with it.

**Fix (landed 2026-09-23, `BO-400e-3-i`).** Sub-step C now invokes
`scripts/set_ticket_status.py --status done` per open ticket — the same shape sub-step D
immediately below already used for `mark_ac_done.py`, which is what made the omission
visible once anyone looked. `--force` is explicitly forbidden in the instruction, since the
override also disables the parity check and would reinstate the ungated write behind a flag.
A non-zero exit leaves the ticket open, names it in a `REFUSED:` log line, and increments a
refused counter; the step does not fall back to any other write. Finalization is not made to
fail on a refusal — the archive check at step 5 already refuses to archive an epic holding a
non-done ticket, so the refusal surfaces there on its own terms rather than through a second
mechanism invented for the purpose.

The transition allow-list already permitted `todo -> done` without `--force` (BO-400e-3), so
the ordinary finalization case needs no override.

Covered by `unit_tests/test_finalize_feature_single_writer_close.py`, including a negative
test that scans the whole finalization prompt — not just sub-step C — so the same defect
reappearing in a different sub-step fails it too. Red baseline captured before the fix: 3 of
4 failing.

**Related.** `ADR-047` (the invariant this breaks), `ADR-046` (record-only demanded set),
`BO-400e-1`/`-2`/`-3`/`-4` (the drivers' close, already correct),
[c3-008](../../architecture/diagrams/c3-008-ticket-close-paths-sequence.md) (the diagram
that found it, where this route is drawn in red outside the close boundary).

**Pattern:** an invariant established at one layer and left unenforced at the layer that
runs after it — the guarded door was built, and a second unguarded one was left standing
next to it in a file nobody in the epic's scope had reason to open.
