# BO-3100 / BO-3200 — agent delegation boundary (PO framing notes for BA + IT PO)

Authored 2026-08-25 by product-owner during L0/L1 authoring for the durable fix to
KI-SS-001. Read before decomposing either tree.

## The one constraint that governs both trees

**Mechanical enforcement only.** Any L2 whose enforcement reduces to "an agent is
told to..." must be rejected. This is not a style preference — the prompt-level fix
was already tried and rotted:

- `building-epics/SKILL.md` §2.1-R1 "Synchronous phase dispatch (MANDATORY)" was
  written from the 2026-07-06 retrospective of this exact failure.
- It was in force on 2026-08-18 and the failure recurred anyway, twice in one drive.
- It could not even reach the second stall: the skill is loaded by `ticket-supervisor`
  only, and the agent that stalled never loads it.

If a proposed criterion's verification is "the template contains the instruction",
it is a grep-only test on dead prose. Reject it.

## The durable invariant (do not restate it as a depth limit)

> A subagent must never depend on the result of anything it spawns. If it needs the
> result, it must not delegate — it must do the work itself, or not be the one
> orchestrating.

Why: a subagent has **no idle state**. Emitting text with no tool call ends the
*agent*, not the turn, and that text becomes its result. There is no wait primitive —
the harness strips `TaskOutput`, `ScheduleWakeup`, `Workflow` and `AskUserQuestion`
from every subagent.

**ADR-006 and ADR-019 are wrong about this.** They claim a hard depth-1 limit and
that deeper calls are silently blocked. Nesting works. Anyone who believes the
constraint is about depth will design the wrong fix. BO-3100d covers correcting them.

## Already shipped — do NOT re-specify (PR #565, merged 88c6395e, 2026-08-25)

- Workflow runtime fails closed: missing / unrecognised / `undetermined` agent
  results can no longer be counted as a completed phase, ticket or epic.
- The three `/plan-feature` gates no longer default to discarding work.
- An `undetermined` status now exists.

What remains is everything else. Two children are deliberately scoped to the
*remainder* and will look like duplicates if you skim them:
- **BO-3200c** — the fail-closed default shipped; what remains is the gate actually
  reaching a **person**, and "no answer available" staying distinguishable from
  "the user said no".
- **BO-3200e** — the `undetermined` status exists; what remains is **using** it at
  every check site that can fail to inspect.

## Evidence beats self-report (binding on BO-3100b)

The verdict on whether a step ran must come from observable repository state, never
from the agent's returned text. A parked agent returns confident, well-formed prose
("I'll act on the completion notification when it arrives") — reading that text is
precisely how the failure stayed invisible. On 2026-08-18 it was caught only by
checking `git status` / `git log` against the report.

Two edge cases that make BO-3100b hard, both must be covered:
- A legitimately-no-op step must stay distinguishable from a vanished one, or the
  guard blocks honest work and gets switched off (the fate BO-2900d exists to avoid).
- The retry must terminate — an agent that parks identically every time must end as
  a visible failure, not a loop.

## Boundaries — what these trees are NOT (checked during authoring)

| Adjacent tree | Its axis | Why BO-3100/3200 is distinct |
|---|---|---|
| BO-2500, BO-2900 | **Artifact** layer: is the code real, tested, reached | BO-3100 is the **orchestration** layer: did the step run at all. KI-SS-001 calls it the same phantom-done shape "relocated from the artifact layer to the orchestration layer" |
| BO-1900 dispatch-preflight | Fires **before** spawn: is this ticket fit to dispatch | BO-3100b fires at **exit** |
| BO-210 pre-commit safety net | Re-dispatch after a hook **failure**; assumes the coder ran | BO-3100b covers it never running |
| BO-1300 independent spot-check | **Quality** of work that was done | BO-3100b: that work was done at all |
| AR-200 capability-matches-obligation | Agent **can** record a verdict | BO-3100a: authority is **bounded**; BO-3200e: what a verdict may claim |
| INF-600 self-describing agents | Registry-card coherence | BO-3100a is spawn **authority**; also INF-600 already has **12 L1 children** — do not add a 13th |

## Placement rule confirmed

Per the build-orchestration PROJECT_CONTEXT component-choice rule, a concern about
what happens **during a drive** belongs in build-orchestration — even when it touches
the agent registry. BO-3100a therefore lives under BO with
`components: [agent_registry, build_orchestration]`, using the two-axis convention
(scalar `component` = index.yaml kebab namespace; `components` list = components.json
graph vocabulary).

## Blame framing (shapes the L2s)

In all four observed failures (KI-BO-018/019/020, KI-ACD-005) the specialist behaved
**well** — it said plainly what it had done, or correctly refused a role outside its
remit. What failed was asking it for something no agent can reliably provide.
Decompose these as **contract defects**, never as agent-obedience problems.

## Store hygiene note found while authoring

`docs/acceptance-criteria/build-orchestration/PROJECT_CONTEXT.md` § "ID numbering"
is **stale**: it says the next free L0 hundred is BO-2300, but BO-2300..BO-2900 all
exist and BO-3000 is taken (by an L2 sitting loose at the component root, authored by
`/quick-fix`). Next free is now **BO-3300**. This is the second time that line has
gone stale. Always `ls` the component directory before assigning an L0 number, and
remember loose `BO-NNNN.yaml` files at the root occupy slots just as folders do.
