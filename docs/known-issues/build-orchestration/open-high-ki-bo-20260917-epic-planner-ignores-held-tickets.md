---
title: "KI-BO-20260917-epic-planner-ignores-held-tickets — `/build-feature`'s epic planner omits only `status: done` tickets, so a ticket held as `blocked` or `deferred` is still batched and driven"
description: "KI-BO-20260917-epic-planner-ignores-held-tickets — `/build-feature`'s epic planner omits only `status: done` tickets, so a ticket held as `blocked` or `deferred` is still batched and driven"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260917-epic-planner-ignores-held-tickets — `/build-feature`'s epic planner omits only `status: done` tickets, so a ticket held as `blocked` or `deferred` is still batched and driven

> Index: [build-orchestration.md](../build-orchestration.md). Filename severity is the
> three-level index bucket (`high`); the original grading is the `**Severity:**` line below.

- **Severity:** high. A recorded hold is silently not honoured: the drive builds work the
  operator deliberately withheld, and the only stop is an operator noticing mid-drive.
- **Status:** open — **no AC**. No acceptance criterion in the store requires the epic drive to
  exclude held tickets. The closest is `BO-400a-5`, which is about `ticket-prioritizer` (not
  this planner) and names only `in_progress`/`done` as excluded.
- **Occurrences:** 1 (2026-09-16, `EPIC-StartingNewWorkTheProperWayAlways`: the hold comments
  record that "the build drive does not read `status` to exclude tickets, so a held ticket
  dispatched by the planner is stopped by the operator")
- **First seen:** 2026-09-16 · **Last seen:** 2026-09-16
- **Where:** `templates/workflows-js/build-feature.js` — the `epic-planner` agent prompt
  (`:2690-2706`), `PLANNER_SCHEMA` (`:60-117`, ticket `status` enum `["todo", "blocked"]` at
  `:80`), and the batch loops that consume the plan (`:2809-2863`, `:2878-2890`,
  `:2969-2990`)

**Symptom.** A sub-ticket whose frontmatter reads `status: blocked` (or `deferred`) is offered
in a batch and driven like any `todo` ticket.

**Mechanism.** The planner prompt names exactly one exclusion:

> (4) Tickets with status 'done', or already recorded complete above, are OMITTED from all
> batches (resume).

It never mentions `blocked` or `deferred`. Readiness at step (2) depends only on `depends_on`.
`PLANNER_SCHEMA` goes further and explicitly **permits** a batched ticket to carry
`status: "blocked"`. The code after the planner filters batch entries only on
`completedTicketOutcomes`, run-set membership and de-duplication. None of the loops cited
above reads the ticket's own `status`. The one lifecycle comparison nearby (`:3084`) checks
for `"done"`. So whether a held ticket is skipped depends on the status-checker agent's
judgement, not on any instruction or check.

**Why high.** This is the enforcement half of a hold, and it is missing silently. It
compounds `KI-BO-20260917-no-status-transition-into-blocked`: today a hold cannot be written
to frontmatter anyway. Fixing that alone would give operators a `blocked` status that looks
authoritative and that the drive still ignores. The two need to land together.

**Evidence.** Prompt text at `build-feature.js:2691-2699` (quoted above);
`PLANNER_SCHEMA.properties.batches.items.properties.tickets.items.properties.status.enum`
is `["todo", "blocked"]`. `grep -n "blocked\|deferred"` over the planner region
(`:2600-3000`) finds no status-based exclusion. The 2026-09-16 hold comments in 7 epic
tickets describe the operator-stop workaround.

**Fix direction.**

- Add `blocked` and `deferred` to the planner's step (4) omission, and report them in a
  separate `held` field (the way `already_done` is reported) so the run summary can say
  "withheld: N held" rather than dropping them silently.
- Do not trust the agent alone. After the planner returns, have the workflow drop any batched
  ticket whose frontmatter status is `blocked`/`deferred` (the per-ticket reader at
  `:1083-1088` already returns `lifecycle_status`), and remove `"blocked"` from the batch
  ticket `status` enum.
- Decide whether a held ticket counts as satisfying a dependent's `depends_on`. It should
  not, so its dependents must be withheld too and reported.
- Author an AC together with the transition fix in
  `KI-BO-20260917-no-status-transition-into-blocked`.

**Pattern:** a filter specified as an allow-list of one state (`done`), so every newer "do
not build" state falls through as buildable.

---
