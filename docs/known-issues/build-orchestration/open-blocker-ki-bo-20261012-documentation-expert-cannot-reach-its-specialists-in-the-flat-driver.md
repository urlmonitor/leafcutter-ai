---
title: "KI-BO-20261012-documentation-expert-cannot-reach-its-specialists-in-the-flat-driver — /build-feature runs documentation-expert as a flat depth-1 phase, where the one route its template allows to a written doc (dispatching a specialist through the Agent tool) does not exist, so a doc-bearing ticket either halts or passes by breaking the template"
description: "blocker — documentation-expert may not write docs itself and must dispatch reference-author, how-to-author, adr-author, explanation-author or architecture-diagram-author through the Agent tool. build-feature.js dispatches every phase as a depth-1 agent(), and a depth-1 agent has no Agent tool (ADR-006, ADR-019). In run wf_54e15913-aea five tickets reached the phase: four halted, and the fifth signed off ok by writing the docs itself, against its own constraint. 39 of the epic's 48 tickets carried documentation-expert: needed. The specialists are already phases in phaseOrder, and the BO-3700 promotion wire already dispatches a promoted phase, so the driver can run them. Nothing routes the work there."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - build_orchestration
  - documentation_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute.md
  - docs/known-issues/build-orchestration/open-blocker-ki-bo-20260925-1309.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261009-one-halted-ticket-stops-the-whole-epic-run.md
  - docs/known-issues/supervisor-system/open-low-ki-ss-20260927-commit-signoff-precedes-the-commit.md
  - docs/known-issues/supervisor-system/open-high-ki-ss-20260826-agent-routed-around-a-blocked-capability.md
---

# KI-BO-20261012-documentation-expert-cannot-reach-its-specialists-in-the-flat-driver — the documentation phase cannot do its job where /build-feature runs it

> Filename severity is the three-level index bucket (`blocker`); the original grading is the
> `**Severity:**` line below.

- **Severity:** blocker. Under `/build-feature`, a ticket that needs `documentation-expert`
  cannot reach `done` by that agent's own rules. If the agent obeys its template, the ticket
  halts. That happened to four of the five tickets that reached the phase. The only way
  through is to break the template, which the fifth did, and that skips the specialist's
  genre guard. In this run the unguarded write is also what got that ticket's commit refused
  (see *Impact*). This is not a rare ticket shape: the ticket generator set the phase to
  `needed` on 39 of this epic's 48 tickets (81%) at the scaffold commit. So an epic drive halts on most of its tickets, and each one needs a
  manual specialist dispatch and a hand-written sign-off. "Work cannot land" through the tool
  is `blocker` by this register's rubric. The halt alone would be `high`: it is loud and
  survivable by hand. The grade is `blocker` because the other outcome is a template violation
  that reports `ok`.
- **Status:** open, no AC. Verified by reading this branch (`b6249edd3`):
  `templates/workflows-js/build-feature.js`, `templates/agents/documentation-expert.md`,
  `config/agent_registry.json` and `config/doc_types.json`. Also verified from the run's own
  record: the dispatch prompts and replies of `wf_54e15913-aea`. The script that run executed
  is this branch's template with its placeholders filled; nothing else differs.
- **Occurrences:** 1 run, 5 tickets reaching the phase: 4 halts and 1 template violation
  (`wf_54e15913-aea`, 2026-10-12, EPIC-RightJobRightAgent).
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:**
  - `templates/workflows-js/build-feature.js`: the flat depth-1 dispatch (header :11-19, :2192);
    `phaseOrder`, which already lists the five specialists as phases (:428-429, :440-442);
    `absorbPromotedPhases`, the BO-3700 wire (:611); the refusal of a handoff to a target that
    is not on the ticket (:2389-2402); a `design` or `halt` classification refuses the ticket
    (:2476-2489).
  - `templates/agents/documentation-expert.md`: Dispatch Contract (:179-184, "Never write or
    edit a doc file yourself"); No-Recursion Guard (:335-346, specialists "one further" below
    an agent "already one below the user-facing session"); Constraints (:352).
  - `config/agent_registry.json`: `documentation-expert` is `is_ticket_phase: true` and
    `spawned_by: ["ticket-supervisor"]`, with a `spawn_allowlist` of seven agents (the five
    specialists, `research-agent` and `glossary-triage`). None of the seven is reachable from
    depth 1. The five specialists are registered `is_ticket_phase: true` themselves.

## Symptom

`/build-feature` on EPIC-RightJobRightAgent, run `wf_54e15913-aea`. Five tickets of batch 1
reached `documentation-expert`:

| Ticket | Reply | `## Comments` entry |
|---|---|---|
| 01 ACD-1600c-1 | `blocker`: "This phase has no Agent dispatch tool, so I could not run reference-author, and I am not allowed to author docs myself." | blocker entry written |
| 03 ACD-1600c-5 | `blocker`: "My rules forbid writing doc files myself, and this run gave me no Agent tool to dispatch it. I have only Bash, Read, Edit and Write, so I stopped" | **none** ("The ticket body is unchanged.") |
| 04 ACD-1700b-1 | `blocker`, `result_status: blocked-no-agent-dispatch-tool` | blocker entry written |
| 06 ACD-2500a-1 | `blocker`: needs reference-author and architecture-diagram-author; "This session has no Agent dispatch tool" | **none** (it "did not touch the sign-off fields") |
| 46 TKT-600a-3 | **`ok`**: "I wrote the three doc edits myself because no specialist dispatch tool was available in this run." | `ok` entry, `diataxis_genre_correct: true` |

Each of the four blockers went to the failure classifier. It returned `halt` all four times
(once with the reason "This is a tooling failure, not a design question"). The driver then
refused the ticket with "Phase 'documentation-expert' returned a 'halt' blocker that requires
user intervention." For tickets 03 and 06 the halt left no trace in the ticket. The reason was
only in the run's return value, so a reader of either ticket saw the phase still `needed` and
no comment explaining why.

Every halted reply carried a complete brief for the specialist: the genre, the target doc and
what to cover. The doc work was decided. The only thing that could not happen was the
dispatch.

## Mechanism

1. **The template makes the phase a router.** `documentation-expert` classifies the request,
   then dispatches a specialist with the `Agent` tool, and must never write a doc itself
   (:179-184, :352). Its No-Recursion Guard places the specialists one level below itself
   (:343-346). Under `/build-feature` that is a depth-2 dispatch.
2. **The driver runs every phase at depth 1.** Since ADR-019, `/build-feature` dispatches each
   phase as `agent({agentType: phaseName})` from the workflow (depth 0). A depth-1 agent cannot
   invoke the Agent tool (ADR-006 :32-35, ADR-019 :44-45). The agents in this run listed their
   toolset as Bash, Read, Edit and Write. The template's frontmatter declares `Agent` as well;
   it was not there.
3. **So the template's success path does not exist where the template runs.** What the agent
   does next depends on which rule it weighs higher: the authoring constraint (halt) or the
   duty to sign off (author the doc itself). Both happened in one run, with the same model and
   the same template.
4. **The halt is classified correctly.** No retry and no rework by another phase supplies a
   missing tool, so `halt` is the right answer, and it refuses the ticket.

## Did the depth-limit design anticipate this?

It anticipated the class, but not this instance.

- **ADR-006** is the depth-limit decision. Its finalize-feature addendum (:839, 2026-06-24)
  found the same shape: an orchestrating agent at depth 1 whose own dispatches are dropped. It
  fixed that by deleting the agent and moving its dispatches into the depth-0 workflow. ADR-006
  never mentions `documentation-expert`. Its depth diagram (:156-172) lists seven phase agents,
  and this is not one of them.
- **ADR-019** moved `/build-feature` to depth-1 phase dispatch. Its own depth diagram lists
  `agent('documentation-expert') (depth 1)` (:156), and nothing notes that this agent's job is
  itself a dispatch. Its consequences say "Phase templates now apply on /build-feature". That
  is exactly the problem here: this phase's template applies, and its template cannot run.
- The same miss is recorded for the commit agent's autofix re-dispatch in
  `KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute`, which was
  found by inspection and never confirmed at runtime. This entry is the first instance of that
  pattern observed at runtime in a phase agent.
- The registry still shows the old design. `spawned_by` names `ticket-supervisor`, which
  `/build-feature` no longer dispatches, and the `spawn_allowlist` is seven agents the phase
  can never reach.

**Same shape, not observed in this run.** Other phases the driver runs at depth 1 also have
non-empty `spawn_allowlist`s: `sql-coder`, `architect-review`, `test-writer`, `pull-request`,
and `research-agent` on several more. `sql-coder` is the close match. Its template says "You do
not author SQL files yourself — you dispatch to specialist sub-agents" (`sql-coder.md:54`).
Unlike the documentation specialists, the SQL specialists are not in `phaseOrder`, so the
promotion route below does not exist for them.

**Earlier drives.** `KI-BO-20260925-1309` quotes `documentation-expert`'s reply in run
`wf_e1f3e873-096` (2026-09-25) as "Authored docs/how-to/...", under the same flat driver.
Inferred, not verified: earlier drives passed this phase the way ticket 46 did, by authoring
the doc themselves, which is why the defect did not surface as a halt until agents began
obeying the constraint.

## Impact

- **This run.** Four of the five tickets in batch 1 halted here. With ticket 46's refused
  commit, batch 1 left staged files, and the staged-leftovers stop ended the run before batches
  2 and 3 (`KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run`, occurrence 2026-10-12).
- **This epic.** 39 of 48 tickets carried `documentation-expert: needed` at the scaffold commit
  `32a542a65`. 34 of them had not yet reached the phase when the run stopped.
- **Self-authoring is not a safe fallback.** It runs without the specialist's genre guard, and
  without the convention doc the specialist loads. On ticket 46 it added 28 lines to
  `docs/reference/ac-schema.md`, which was already over its 300-line limit, and
  `check-doc-length` then refused the ticket's commit. That refusal became a phantom `done`
  (`KI-SS-20260927-commit-signoff-precedes-the-commit` and
  `KI-BO-20261009-completion-write-closes-a-ticket-whose-gate-failed`, occurrences 2026-10-12).
  The glossary coverage step is skipped too: `glossary-triage` is also reached only through
  the Agent tool. The ticket 46 reply says "The glossary coverage lint was skipped."

## Workaround used

The main session dispatched `reference-author` itself, since a main-session dispatch is depth 1,
and wrote the `documentation-expert` sign-off by hand. Tickets 01, 03, 04 and 06 each carry a
`documentation-expert (status: ok)` entry saying "Reference-author was dispatched directly by
the main session (the flattened per-phase driver has no Agent tool and could not dispatch it)".
Re-running `/build-feature` does not clear the halt.

## Detection

- **Loud form:** `halted_tickets[].error` reads "Phase 'documentation-expert' returned a 'halt'
  blocker", and the phase's reply mentions a missing Agent or dispatch tool.
- **Silent form:** a `documentation-expert (status: ok)` entry saying the agent authored the
  doc itself, for example "Authored directly because no specialist dispatch tool was
  available". Every such entry is a template violation that reported `ok`. Search ticket
  Comments for `no specialist dispatch tool` and `authored directly`.
- **Static:** any phase in `phaseOrder` with a non-empty registry `spawn_allowlist` whose
  template makes a dispatch its success path.

## Fix direction

1. **Run the specialist as a phase.** No new mechanism is needed. The five specialists are
   already in `phaseOrder` and registered `is_ticket_phase: true`. The BO-3700 wire already
   dispatches a phase that another phase promotes to `needed` mid-drive. This same run did that
   for `adr-author` on ticket 06: `architect-review` promoted it, and `adr-author` wrote ADR-069
   at depth 1. Two ways to use this:
   - **(a) `documentation-expert` routes instead of dispatching.** Add a flat-driver path to the
     template: classify, write the brief into its own Comments entry, set the chosen
     specialist(s) to `needed` in the frontmatter, and sign off as the router, with a manifest
     that names the routing rather than claiming `doc_written`. The driver absorbs and runs the
     specialists, and `documentation-verifier` (priority 11.9) still checks that the docs are in
     the diff. A `handoff` reply would **not** work today. The driver refuses a handoff whose
     target is not a key of the ticket's agents map (:2389-2402), and generated tickets carry no
     specialist keys (ticket 03's map has `documentation-expert` and none of the five).
   - **(b) The generator or the driver picks the specialist.** This can be mechanical where the
     inputs are. For an existing target doc, its frontmatter `type:` is checked against
     `config/doc_types.json`, and that file's `writer_agent` names the specialist
     (`docs/reference/ac-schema.md` is `type: reference`, so `reference-author`). The Agent
     Contracts line's kind token comes from the `documentation_triggers` enum in
     `scripts/ac_store/validate_ac_schema.py` (how-to, sequence-diagram, state-diagram,
     component-diagram, reference-doc), and those five values map to three writers. But no
     table joins that enum to the keys in `doc_types.json`, and the two can disagree. Ticket
     06's AC-1 reads `component-diagram | docs/reference/ac-schema.md`, a diagram kind aimed at
     a reference doc. A mechanical router therefore needs a precedence rule, plus a "cannot
     decide" result that falls back to (a). The multi-genre order in the template (:188-199)
     would also have to become driver ordering. Today the specialists sit at priority 10,
     except `adr-author` at 2 and `architecture-diagram-author` at 3.
2. **Do not fix it by letting `documentation-expert` write docs.** That removes the genre
   guard, and it makes the violation observed on ticket 46 the protocol.
3. **Correct the record and add a guard.** Correct ADR-019's depth diagram and the registry's
   `spawned_by`. Add the mechanical check `KI-BO-20260914` also asks for: no phase whose
   template's success path is an Agent dispatch.

**Related.** `KI-SS-20260826-agent-routed-around-a-blocked-capability`: a subagent denied a
capability reached the same effect another way and reported success. Ticket 46 is a milder case
of that. `KI-BO-20261009-1832`: the driver refuses a handoff to a phase the handing phase just
added.

**Pattern:** a phase whose only success path is a dispatch, run where dispatch does not exist.
