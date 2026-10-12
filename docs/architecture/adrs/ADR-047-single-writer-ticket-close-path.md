---
title: "ADR-047: The Finished State Is Written Only by the Mechanism That Checks It"
description: "A ticket's done lifecycle state MUST be written exclusively by scripts/set_ticket_status.py, invoked without the blanket --force override; the drivers' direct-frontmatter-edit instruction is removed rather than discouraged, because a second write route that skips the check makes the check optional."
type: "adr"
status: "active"
created: "2026-09-21"
last_updated: "2026-09-21"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - supervisor_system
related_docs:
  - docs/architecture/adrs/ADR-046-completion-demanded-set-is-record-only.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/agent_delivery_workflows.md
  - docs/known-issues/build-orchestration.md
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400b.yaml
related_code:
  - scripts/set_ticket_status.py
  - templates/agents/status-checker.md
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
---

# ADR-047: The Finished State Is Written Only by the Mechanism That Checks It

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-21 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded during the `BO-400e-3` single-door pass of 2026-09-21 |
| Supersedes | None |

## Context

A ticket reaches its finished state — `status: done` in its own frontmatter — by two
different routes today, and only the weaker of the two is ever actually taken by a real
drive.

The intended route is `scripts/set_ticket_status.py`. It is a guarded door: before it
writes `done` it reads the ticket's `agents:` map through `_get_needed_agents`, refuses
with a non-zero exit while any demanded phase is unaccounted for, validates the requested
transition against `ALLOWED_TRANSITIONS`, and stages the file. It has no exclusion
parameter, and [ADR-046](ADR-046-completion-demanded-set-is-record-only.md) §2 exists
specifically to keep it that way.
[`BO-400b`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400b.yaml)
already states the intent at L1 — when any agent or supervisor needs to change a ticket's
status it invokes a single script — but none of its three L2 children ever made that
script the *only* writer, so the intent has no enforcement behind it.

The route actually taken is a direct edit. `writeTicketCompletion` in
`templates/workflows-js/build-feature.js` (line ~1305) and its twin in
`templates/workflows-js/build-ticket.js` (line ~1145) dispatch `status-checker` with the
literal instruction *"Edit the ticket's frontmatter so that `status:` reads done. Change
nothing else"*. That string is the only completion-write instruction either driver
contains; neither file mentions `set_ticket_status.py` anywhere. A raw frontmatter
replacement performs no parity check, no transition validation, and no staging. The
drivers are the only surfaces that reach the completion write —
[ADR-006](ADR-006-flatten-supervisor-chain.md) flattened the supervisor chain so that they,
not an intermediate `ticket-supervisor`, own dispatch and closure — so in practice the
guarded door has never been the door a drive goes through.

The party performing the write already knows better. `templates/agents/status-checker.md`
carries the correct rule in two places: its `## Closing protocol` and its auto-close
trigger both invoke `python scripts/set_ticket_status.py --ticket <path> --status done`
and both warn against reaching for `--force` without explicit authorization. So the
system contains the right instruction and the wrong instruction simultaneously, and which
one wins depends on which surface dispatched the agent on a given run. That is the same
shape as `KI-BO-20260831-1932` in
[`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md),
where one drive produced a refusal on one ticket and a `done` write on two others from an
identical condition — and where two readers drew opposite conclusions from the register
entry on the same day. An outcome that a system can produce two ways is not evidence of
anything.

The cost of leaving this undecided is specific and already observable: every phantom-done
this family exists to remove can be reintroduced by a single prompt edit, because the
enforcement lives in wording rather than in structure. The ticket's own constraints make
the point — *"a fix that is only prompt wording is reopened by the next prompt edit"*.
[`BO-400e-3`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-3.yaml),
the AC this record serves, fixes the discriminating observation accordingly: make the
checking mechanism **refuse**, drive the close, and assert that no finished state appears
by any route. That single case is what distinguishes *the second door is closed* from
*the second door exists and was not taken this time*.

One mechanical obstacle sits directly in the path of the fix and must be decided here
rather than discovered under deadline. The unforced `ALLOWED_TRANSITIONS` set in
`scripts/set_ticket_status.py` is `{(todo, in_progress), (in_progress, done),
(in_progress, todo)}`; `(todo, done)` is reachable only through
`FORCE_ALLOWED_TRANSITIONS`. Neither driver ever moves a ticket to `in_progress`, and the
direct-edit route validated no transition at all, so the gap has been invisible. The
moment the close is routed through the script, an ordinary ticket sitting at
`status: todo` is rejected — not by the parity check the AC is about, but by the
lifecycle allow-list. That failure is indistinguishable from a genuine refusal when viewed
from outside, and it creates exactly the pressure this record must foreclose: an
implementer who sees every ordinary close fail will reach for `--force`, which switches
off the parity check *and* the allow-list together, recreating the lenient branch with a
flag on it.

## Decision

1. **There is exactly one writer of the finished state.** `scripts/set_ticket_status.py`
   MUST be the only mechanism that writes `status: done` into a ticket's record. Every
   close — epic drive, single-ticket drive, user-gated close, auto-close — MUST go through
   it. No other agent, script, workflow step, or prompt MUST write that value by any other
   means.

2. **The direct-edit instruction is removed, not softened.** The completion-write step in
   `templates/workflows-js/build-feature.js` (`writeTicketCompletion`) and its twin in
   `templates/workflows-js/build-ticket.js` MUST NOT instruct any agent to edit the
   ticket's frontmatter, replace its `status:` line, or otherwise author the lifecycle
   value itself. The dispatched instruction MUST name
   `python scripts/set_ticket_status.py --ticket <path> --status done` as the route, and
   MUST contain no fallback describing what to do if that command is unavailable.

3. **The ordinary close path MUST NOT pass `--force`.** `--force` also disables the
   transition allow-list, so it is not a surgical exception; a close that succeeds only
   because `--force` was passed is not a close through this door and MUST be treated as a
   failure of this decision. A narrower override MUST NOT be introduced in its place —
   that is the caller channel [ADR-046](ADR-046-completion-demanded-set-is-record-only.md)
   §2 forbids, wearing a different name. `--force` remains available exclusively for
   explicitly user-authorized manual repair, never for a driver.

4. **The unforced transition allow-list MUST admit `("todo", "done")`.** `ALLOWED_TRANSITIONS`
   in `scripts/set_ticket_status.py` MUST include the `todo -> done` pair so that the
   ordinary close of a ticket that never visited `in_progress` succeeds without `--force`.
   This is a data-table widening of the already-governed file; it MUST NOT be accompanied
   by any change to the parity check, and the drivers MUST NOT gain an intermediate
   `in_progress` transition step to work around the gap instead.

5. **A refusal MUST leave the record untouched and MUST surface as not-closed.** When
   `set_ticket_status.py` exits non-zero — for a parity reason or for a transition-allow-list
   reason alike — the ticket's recorded state MUST be left exactly as found, and the
   driver's result-interpretation branch MUST report that ticket as **not closed** in the
   structured payload it returns to its own caller. The run MUST NOT report success, MUST
   NOT retry through another route, MUST NOT retry with `--force`, and MUST NOT continue
   silently.

6. **`templates/agents/status-checker.md` holds the single canonical closing procedure.**
   The drivers MUST route to that procedure rather than restating a write recipe of their
   own, and the agent template MUST NOT describe editing the recorded state directly on
   any path. Where the drivers and the template both describe the close, they MUST name
   the same mechanism and the same prohibition on `--force`.

7. **Both twins MUST change in the same commit.** `build-feature.js` and `build-ticket.js`
   MUST close the same way and produce the same recorded state for the same ticket. A
   one-sided landing is forbidden: it yields a system in which the single-ticket driver
   goes through the door and the epic driver does not, which is this same defect one level
   up.

8. **Conformance MUST be verified by execution, never by grep.** The completion code, the
   prompt text, and the parity check are all present in the source today, so a
   source-reading test passes unchanged on the broken driver. Conformance MUST be
   demonstrated by loading and running the real workflow through
   `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` and asserting on the records
   the run actually wrote — including the refusing-mechanism case of Decision §5, without
   which the suite proves nothing.

## Consequences

### Positive

- The finished state acquires a single provenance. Any `done` in the store can be
  attributed to a run of `set_ticket_status.py`, and therefore to a parity check that
  passed, rather than to whichever surface happened to dispatch the write.
- The fix survives prompt editing. Removing the direct-edit route means a future reword of
  the completion prompt can no longer reopen the second door, because there is no longer a
  second door for wording to point at.
- The drivers and `status-checker.md` stop disagreeing. The agent is given one instruction
  by every caller, so its behaviour no longer depends on which caller reached it.
- A refused close becomes visible where it matters: in the run's own report. Report and
  store can no longer disagree, which is the phantom-done shape this family exists to
  remove.
- Staging comes along for free. The script `git add`s the ticket it writes, so a close no
  longer leaves an unstaged lifecycle change behind.

### Negative

- Closes that previously always succeeded can now fail. A ticket whose record still names
  a phase it will never receive will halt at the close rather than slip through, and the
  remedy is to fix the record — more work than editing one line of frontmatter.
- The close is now a subprocess with an exit code the driver must interpret, which is a
  strictly more complex control flow in both drivers than the previous fire-and-forget
  edit, and it adds a second sub-location (the result branch) to each of the two files.
- Widening `ALLOWED_TRANSITIONS` (Decision §4) weakens the lifecycle-visitation invariant:
  a ticket can go from `todo` to `done` without ever being recorded as `in_progress`. This
  is accepted deliberately — the direct-edit route was already ignoring that invariant
  entirely — but it does mean the allow-list no longer proves a ticket was ever picked up.
- The enforcement is partly a natural-language instruction executed by an LLM sub-agent.
  Structure closes the route in the drivers and in the script, but the final write is still
  performed by an agent following a prompt, so the harness — not the prompt text — is the
  only thing that keeps the property true.

### Operational

- `templates/workflows-js/*.js` and `templates/agents/*.md` are build sources, not the
  running artefacts. A change confirmed only against the source tree is not confirmed
  against what runs. Keep the deployed copies in step (`check-build-drift` is the gate) and
  confirm the single-door behaviour through the deployed layout before sign-off.
- Land Decision §4 (the transition widening) in the same change as §2. Routing the close
  through the script while `todo -> done` is still force-only makes every ordinary close
  fail and manufactures precisely the pressure toward `--force` that §3 forbids.
- Sequencing inherited from [ADR-046](ADR-046-completion-demanded-set-is-record-only.md)'s
  Operational section still applies: records that wrongly name a phase as `needed` must be
  repaired before a drive meets them, or the newly-enforced door halts on the first of
  them.
- The close-path sequence this record establishes is depicted in
  [`docs/architecture/agent_delivery_workflows.md`](../agent_delivery_workflows.md) under
  `BO-400e-5`; that diagram and this ADR MUST be kept in agreement.

## Alternatives

- **Reword the completion prompt without removing the direct-edit route.** Rejected. The
  instruction clause is the weaker half of the criterion and is also the only clause a
  source-reading test can see, so a wording-only fix produces a green suite over an
  unchanged capability: the next prompt edit reopens it, and no test in the repository can
  tell that it did.
- **Pass `--force` on the ordinary close path.** Rejected. `--force` disables the parity
  check and the transition allow-list together, so a driver that always passes it has
  reconstructed the lenient direct-edit branch behind a flag. The property under test —
  that a refusal blocks the write — would be false on every ordinary run.
- **Add a narrower override (e.g. `--allow-todo-done` or `--skip-transition-check`) to
  `set_ticket_status.py`.** Rejected. It reopens the caller channel that
  [ADR-046](ADR-046-completion-demanded-set-is-record-only.md) §2 closed: any parameter
  the driver can supply is a parameter that decides how strictly the driver is checked,
  and the guard is worth something only while the driven party cannot adjust it.
- **Insert an explicit `todo -> in_progress` transition step into both drivers instead of
  widening the allow-list.** Rejected. It adds a fifth edit location beyond the ticket's
  `n_location_rule: 4`, puts a second lifecycle write into the drive (a new opportunity to
  write state outside the close), and makes every close depend on an earlier step having
  run — a dependency that fails open the first time a drive resumes mid-ticket.
- **Have the driver shell out to `set_ticket_status.py` itself rather than dispatching
  `status-checker`.** Rejected. It splits the closing procedure across two surfaces again —
  the driver's own invocation and the agent template's `## Closing protocol` — recreating
  the divergence this record removes, and it bypasses the agent whose sign-off-completeness
  rule is the one that must always win.
- **Leave both routes in place and catch bad writes downstream with
  `check-ticket-ac-status-parity`.** Rejected. A post-hoc parity check finds a phantom
  `done` only after it has been committed and only where the checker happens to look; it
  cannot prevent the write, and the known-issues register already records a case
  (`KI-BO-20260831-1932`) where such a write had to be caught that way. Preventing the
  write is cheaper than detecting it.
- **Delete `--force` from `set_ticket_status.py` entirely.** Rejected. Manual repair of a
  mis-recorded ticket is a genuine, user-authorized need (`done -> todo`, `inbox -> todo`),
  and removing the escape hatch would push that repair back into hand-edited frontmatter —
  reopening the direct-edit route for the exact population of tickets whose records are
  already known to be wrong.

## References

- Originating ticket:
  `tickets/00_inbox/epics/EPIC-WorkIsOnlyEverMarkedFinishedThroughThe/03_TICKET-20260914-BO-400e-3.md`
  (AC `BO-400e-3`).
- Sibling decision: [ADR-046 — The Completion Decision's Demanded-Step Set Is Derived
  Solely From the Ticket's Own Record](ADR-046-completion-demanded-set-is-record-only.md).
  ADR-046 governs *which phases are checked* (the input to the decision); this record
  governs *which mechanism is allowed to write* (the output).
- [ADR-006 — Flatten Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — why the two
  workflow drivers, and not `ticket-supervisor`, own the completion write.
- [`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md) —
  `KI-BO-20260831-1932`, the split outcome this record closes.
- [`docs/architecture/components/build-orchestration.md`](../components/build-orchestration.md) —
  the component boundary this change stays inside.
