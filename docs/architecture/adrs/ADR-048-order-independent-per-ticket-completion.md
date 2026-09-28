---
title: "ADR-048: One Run Gives One Answer Per Condition — Completion Is Order-Independent"
description: "A run that carries several tickets MUST decide each ticket's close solely from that ticket's own read-back record, with no state carried between tickets, so two tickets in the identical state in one run can never receive different answers and no answer varies with the order the run reached it."
type: "adr"
status: "active"
created: "2026-09-22"
last_updated: "2026-09-22"
deciders:
  - BrainCandy
components:
  - build_orchestration
  - supervisor_system
related_docs:
  - docs/architecture/adrs/ADR-047-single-writer-ticket-close-path.md
  - docs/architecture/adrs/ADR-046-completion-demanded-set-is-record-only.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/agent_delivery_workflows.md
  - docs/known-issues/build-orchestration.md
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-4.yaml
  - docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-iii.yaml
related_code:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/agents/status-checker.md
  - scripts/set_ticket_status.py
  - unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
---

# ADR-048: One Run Gives One Answer Per Condition — Completion Is Order-Independent

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-22 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded during the `BO-400e-4` one-answer-per-condition pass of 2026-09-22 |
| Supersedes | None |

## Context

On 2026-08-31 a single drive met three tickets that were in the same state as each
other. Each named the same phases as needed; each carried a passing sign-off for every
one of them except `pull-request`, for which none of the three carried any entry at all.
The drive refused one of the three and wrote the other two finished.
[`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md)
records that as `KI-BO-20260831-1932`, and it reads there as agent caprice — the split
survived a day of inspection precisely because nobody could see the three decisions side
by side. The tell, once the records were laid out, is that the split correlated with
**position in the run**: ticket 01 was refused; tickets 03 and 20, reached later, were
written.

Two sibling records in this family have already fixed the pieces on either side of this
one. [ADR-046](ADR-046-completion-demanded-set-is-record-only.md) fixed *which phases are
checked* — the demanded set is derived solely from the ticket's own record, with no
caller channel through which a driver can narrow it.
[ADR-047](ADR-047-single-writer-ticket-close-path.md) fixed *which mechanism may write* —
`scripts/set_ticket_status.py`, unforced, as the single door. Neither says anything about
what must be true when the mechanism is run **several times in one drive**. One writer and
one input rule still permit a run that answers the same question two ways, because neither
forbids the run from carrying something between tickets.

Direct inspection of `templates/workflows-js/build-feature.js` at the time of writing finds
the arithmetic already clean. `concludeTicket` (line ~1481), `completionVerdictFromRecord`
(~933), `demandedPhasesFromRecord` (~1072) and `requiredPhasesForCompletion` (~1123) are
pure functions of `spec.record` / `spec.demandedRecord`, both of which are read-backs of
the ticket's own file; `concludeTicket`'s own header records that `spec` was deliberately
stripped of a caller-supplied phase list for exactly this reason. The one module-level
mutable in the file, `unknownPhaseAgentsReported` (line 434), only deduplicates a
diagnostic `console.error` and does not feed any return value. So the leak is not visible
in the decision arithmetic — which is the whole difficulty. What the run *does* carry
across tickets is everything around that arithmetic: the batch loop's chunked parallel
dispatch (`templates/workflows-js/build-feature.js`, the `for (const batch of batches)`
loop at ~3218), the accumulating `completedBatches` / `batchResults` structures, and —
most plausibly — the `status-checker` sub-agent dispatches that `writeTicketCompletion`
(~1301) performs once per closing ticket. A sub-agent whose context is not fresh per
ticket has seen the previous ticket's close before it is asked about this one, and that is
an order-dependent input that no JS-level review can see.

The cost of leaving this undecided is that the two decisions already recorded become
unfalsifiable in the only setting that matters. A single-ticket run cannot exhibit the
defect: with one ticket, the broken driver and the fixed driver produce the same output,
because either branch is defensible in isolation. The defect *is* the disagreement between
tickets inside one run. So a suite of per-ticket assertions gathered from four independent
single-ticket runs passes, unchanged, on the driver that produced `KI-BO-20260831-1932` —
and that suite is the natural one to write. The property has to be stated as a property of
a **run**, or it cannot be tested at all.

One further trap must be foreclosed here rather than discovered later. "All the tickets in
the run agreed" is a property a completely broken writer holds trivially: a run that
refuses everything is perfectly consistent and perfectly repeatable. Agreement is therefore
only evidence when the run also contains a ticket that *should* close and does. That is why
[`BO-400e-4`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-4.yaml)
puts a fourth, fully-signed-off ticket in the same run as the three, and why this record
treats that control as part of the contract rather than as a testing nicety.
[`BO-400a-2-iii`](../../acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400a-2-iii.yaml)
already established the three-tickets-in-one-drive-plus-control shape and is the closest
precedent. [ADR-006](ADR-006-flatten-supervisor-chain.md) explains why the driver's own
per-ticket loop — not an intermediate `ticket-supervisor` — is the surface that carries
several tickets in one run, and therefore the only place this disagreement can occur.

## Decision

1. **The completion decision is a pure function of the ticket's own read-back record.**
   For every ticket a run closes, the verdict MUST be computed from that ticket's own
   record and from nothing else. The same record MUST yield the same verdict on every
   evaluation, in every run, on every machine. `concludeTicket`,
   `completionVerdictFromRecord`, `demandedPhasesFromRecord` and
   `requiredPhasesForCompletion` in `templates/workflows-js/build-feature.js`, and their
   twins in `templates/workflows-js/build-ticket.js`, MUST remain pure in this sense.

2. **No state MUST be carried between tickets into the decision.** No memo, cache, running
   tally, set of already-seen phases, batch index, chunk position, accumulated results
   array, or any other value that a run mutates as it proceeds MUST be an input to any
   ticket's completion verdict or to the close dispatch performed for it. A diagnostic-only
   accumulator (such as `unknownPhaseAgentsReported`, which dedupes a warning and feeds no
   return value) is permitted and MUST remain diagnostic-only; if such a value ever comes
   to influence a returned verdict, it becomes a violation of this clause.

3. **Each ticket's close MUST be dispatched in its own fresh sub-agent context.** The
   `status-checker` dispatch that `writeTicketCompletion` performs MUST be independent per
   ticket: one ticket's close MUST NOT be conducted in a conversation, session, or context
   that has already handled another ticket's close in the same run, and several tickets'
   closes MUST NOT be batched into one dispatch. Independence of the JS-level inputs is not
   sufficient — the dispatch layer is itself an input, and an implementation that leaves it
   stateful has relocated the defect rather than removed it.

4. **Two tickets in the identical state, in one run, MUST receive the identical answer.**
   Where two tickets' records name the same phases as needed and carry sign-offs for the
   same subset of them, the run MUST produce the same verdict for both — the same
   closed/not-closed outcome, the same recorded state, and the same named outstanding
   phases. It MUST NOT be possible for one run to both refuse and write a close for the
   same condition.

5. **No answer MUST vary with the order in which the run reached the ticket.** Permuting
   the tickets of a run — including moving a ticket from first to last position, and
   including changing which ticket is closed first — MUST leave every ticket's answer
   unchanged. Order-independence is a property of the decision, not of the fixture: it MUST
   NOT be obtained by canonically sorting the input, by serialising the batch loop, or by
   any other arrangement that fixes the order rather than removing the dependence on it.

6. **A second run over the same records MUST produce the same answers.** Restoring the same
   tickets to the same state and driving the run again MUST yield, ticket for ticket, the
   verdicts the first run produced.

7. **Determinism MUST NOT be obtained by refusing everything.** A run that contains a ticket
   whose record carries a passing sign-off for every phase it names MUST write that ticket
   finished, through the single door
   [ADR-047](ADR-047-single-writer-ticket-close-path.md) §1 establishes. Uniform refusal
   satisfies §4, §5 and §6 vacuously and MUST NOT be accepted as conformance; the contrast
   with a closing ticket in the same run is what makes the refusals attributable to the
   missing sign-off.

8. **A refusal MUST leave the record untouched and MUST name its outstanding phase.** Each
   refused ticket MUST have its recorded state left exactly as found, and the refusal MUST
   name the phase that is outstanding. Two tickets refused for the same reason MUST name
   the same phase.

9. **The per-ticket decision MUST be individually observable in the run's own output.** The
   run MUST expose, separately for each ticket it carried, the verdict it reached and the
   record write it performed or withheld. An aggregate-only report MUST NOT be the run's
   only account of its closes: agreement between tickets cannot be checked against a total,
   and the absence of that per-ticket surface is exactly the observability gap that let
   `KI-BO-20260831-1932` read as caprice for a day.

10. **Both twins MUST change in the same commit.** `templates/workflows-js/build-feature.js`
    and `templates/workflows-js/build-ticket.js` MUST land this decision together, per
    `BO-400a-2-ii`'s standing constraint and this ticket's `n_location_rule: 2`.
    `build-ticket.js` carries one ticket per run and therefore cannot exhibit the
    disagreement — which is precisely why it MUST NOT be left behind: a one-sided landing
    recreates two drivers with two behaviours, the same shape as the two doors
    [ADR-047](ADR-047-single-writer-ticket-close-path.md) §2 closed.

11. **Conformance MUST be verified by executing a four-ticket run, never by grep.** Nothing
    about this decision is visible in the source: the broken driver and the fixed one both
    contain completion code, a phase list and a parity check. Conformance MUST be
    demonstrated by loading and running the real workflow through
    `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` with **four tickets carried
    in one run** — three in the identical state plus the §7 control — and asserting the four
    record writes the run actually performed. Four independent single-ticket runs MUST NOT
    be accepted as a substitute, and neither MUST importing the completion helper and
    calling it four times: both are the single-ticket shape this record exists to rule out,
    and both pass on the broken driver.

## Consequences

### Positive

- The answer becomes attributable to the ticket. Any refusal or close a drive produces can
  be explained by that ticket's own record, so an operator comparing two tickets no longer
  has to reason about where in the run each one sat.
- `KI-BO-20260831-1932` acquires a falsifiable closing condition. The register entry's
  "one refused, two written from an identical condition" is now a statement the harness can
  check, rather than an anecdote two readers drew opposite conclusions from.
- The contrast case makes the refusals mean something. Because §7 forbids conformance by
  uniform refusal, a green suite proves the guard discriminates, not merely that it is
  consistent.
- Per-ticket observability (§9) pays off beyond this decision: any future disagreement
  between tickets in one run surfaces in the run's own payload on the first occurrence,
  instead of after a day of inspection.
- The three decisions of this family now cover the whole close: ADR-046 the input, ADR-047
  the writer, this record the behaviour across a batch.

### Negative

- The cheap test is forbidden. The natural per-ticket unit test is explicitly not
  acceptable evidence (§11), so every change to the close path now costs a multi-ticket
  harness run — slower to write and slower to execute than the assertion it replaces.
- §3 constrains the dispatch layer, not just the JS. Guaranteeing a fresh sub-agent context
  per ticket may cost context re-establishment on every close, which is real token and
  latency spend proportional to the number of tickets in a drive.
- Legitimate optimisations are closed off. A run-scoped cache of, say, a repeatedly re-read
  record would be a sensible performance move and is now forbidden outright, because the
  rule cannot distinguish a safe cache from an unsafe one by inspection.
- The property is partly enforced through an LLM sub-agent's behaviour. Structure can make
  the JS inputs independent and the dispatch fresh, but the final write is still performed
  by an agent following a prompt, so the harness — not the code's shape — remains the only
  thing that keeps §4 true.
- §5 forbids the tempting mitigation. Canonically sorting tickets would make a real drive's
  output stable and would look like a fix; it is rejected here, so an order-dependence bug
  must actually be found rather than pinned.

### Operational

- `templates/workflows-js/*.js` are build sources, not the running artefacts. Keep the
  deployed copies in step (`check-build-drift` is the gate) and confirm the four-ticket
  behaviour through the **deployed** layout before sign-off — a change confirmed only
  against the source tree is not confirmed against what runs.
- Land §10's two files in one commit. A `build-feature.js`-only landing passes every test
  in the harness, because `build-ticket.js` cannot exhibit the defect the harness looks
  for.
- The architect review on `BO-400e-4` hypothesised the `status-checker` dispatch sequencing
  as the residual leak after ruling out module-level mutable state in the decision core.
  That is a hypothesis to confirm by execution, not a finding: implementers MUST NOT treat
  the pure-core inspection as proof the run is already conformant.
- Sequencing inherited from [ADR-047](ADR-047-single-writer-ticket-close-path.md) still
  applies: this record assumes the close already goes through
  `scripts/set_ticket_status.py` unforced. Attempting §4 while a second write route remains
  open measures agreement between two mechanisms rather than one.
- The batching and dispatch topology that determines reach-order is described in
  [`docs/architecture/agent_delivery_workflows.md`](../agent_delivery_workflows.md); that
  document and this record MUST be kept in agreement when either changes.

## Alternatives

- **Sort the tickets canonically before the run so the order is always the same.** Rejected.
  It makes the output stable without making the decision independent: the dependence on
  position survives untouched and simply stops being observable, so the next change to the
  batch planner — which legitimately reorders tickets by dependency and file-conflict edges
  — reintroduces the split with no test able to see it. §5 names this explicitly for that
  reason.
- **Serialise the batch loop so only one ticket is ever in flight.** Rejected. It attacks
  concurrency, which is not the mechanism: the observed split was between tickets closed at
  different points of a run, and a fully serial run still reaches ticket 20 after ticket 01.
  It would also discard the parallel-safe batching that build orchestration exists to
  compute, at a large throughput cost, in exchange for a property it does not deliver.
- **Cache the phase-name resolution or the read-back record across tickets in a run.**
  Rejected. Any run-scoped store is by construction a value that differs depending on how
  many tickets preceded this one, so it is the exact shape §2 forbids; and because a cache
  is correct almost always, its failures appear as isolated anomalies indistinguishable from
  the agent caprice this defect was first mistaken for.
- **Close all of a batch's tickets in one `status-checker` dispatch.** Rejected. It makes
  every ticket's close conditioned on the records of its batch-mates by construction, which
  is §3's prohibition stated as a design; it also collapses the per-ticket record write into
  an aggregate reply, defeating §9's observability requirement in the same change.
- **Assert only the aggregate outcome of the run (e.g. `tickets_completed`).** Rejected. An
  aggregate cannot distinguish "three refused, one written" from "one refused, three
  written" plus a compensating miscount, so it cannot detect disagreement between tickets —
  which is the entire content of this record.
- **Test with four independent single-ticket runs and compare the four answers.** Rejected.
  At one ticket per run, the broken driver and the fixed driver are indistinguishable,
  because nothing is carried between tickets when there is no second ticket. Such a suite
  passes on the driver that produced `KI-BO-20260831-1932` and would have signed that defect
  off as fixed.
- **Import the completion helper and call it four times in one process.** Rejected. It
  exercises the pure core, which direct inspection already shows to be order-independent,
  while skipping the batch loop and the dispatch layer where the residual state actually
  lives. It is the single-ticket shape again, wearing a four-call costume.
- **Prove determinism by having the run refuse every ticket whose state is not
  unambiguous.** Rejected. It satisfies §4, §5 and §6 vacuously while making the drive
  useless, and it converts a phantom-done into a phantom-blocked: work that is genuinely
  finished never closes, and the operator has no way to tell a real outstanding phase from
  the guard's own timidity. §7 exists to make this inadmissible.
- **Fix only `build-feature.js`, since `build-ticket.js` carries one ticket and cannot
  exhibit the defect.** Rejected. It leaves two drivers with two close behaviours, which is
  the two-doors shape [ADR-047](ADR-047-single-writer-ticket-close-path.md) §2 closed one
  level up; the single-ticket driver then becomes the surface a future change to the shared
  close path is tested against, and the untested twin is the one that batches.
- **Detect the disagreement after the fact with a store-wide parity sweep.** Rejected. A
  post-hoc sweep finds a wrongly-written `done` only after it is committed and only where
  the checker happens to look — `KI-BO-20260831-1932` is itself a case that had to be caught
  that way — and it can say nothing at all about the two tickets the run refused correctly,
  because a correct refusal leaves no artefact for a sweep to inspect.

## References

- Originating ticket:
  `tickets/00_inbox/epics/EPIC-WorkIsOnlyEverMarkedFinishedThroughThe/04_TICKET-20260914-BO-400e-4.md`
  (AC `BO-400e-4`).
- [ADR-047 — The Finished State Is Written Only by the Mechanism That Checks It](ADR-047-single-writer-ticket-close-path.md)
  — which mechanism may write. This record governs how that mechanism must behave when a run
  invokes it for several tickets.
- [ADR-046 — The Completion Decision's Demanded-Step Set Is Derived Solely From the Ticket's
  Own Record](ADR-046-completion-demanded-set-is-record-only.md) — which phases are checked.
- [ADR-006 — Flatten Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — why the
  drivers' own per-ticket loop, not a supervisor agent, is the surface that carries several
  tickets in one run.
- [`docs/known-issues/build-orchestration.md`](../../known-issues/build-orchestration.md) —
  `KI-BO-20260831-1932`, the split outcome this record closes.
- [`docs/architecture/components/build-orchestration.md`](../components/build-orchestration.md)
  — the component boundary this change stays inside.
- [`docs/architecture/agent_delivery_workflows.md`](../agent_delivery_workflows.md) — the
  batching and dispatch topology that determines reach-order.
- `unit_tests/prompt_assembly/harness_build_ticket_guard.mjs` — the behavioural harness
  §11 requires, driven with four tickets in one run.
