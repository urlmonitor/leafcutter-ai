---
title: "KI-BO-20260901-1045 — Every handoff halts the drive: the driver routes on a `handoff_target` field that no agent template tells any agent to emit"
description: "KI-BO-20260901-1045 — Every handoff halts the drive: the driver routes on a `handoff_target` field that no agent template tells any agent to emit"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260901-1045 — Every handoff halts the drive: the driver routes on a `handoff_target` field that no agent template tells any agent to emit

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** **RESOLVED 2026-09-23** — see the dated closure note at the foot of this entry.
  Original line, preserved: open — no AC
- **Occurrences:** 2 observed (ACD-2100a-1 on 2026-08-26, ACD-2100a-4 on 2026-09-01),
  but the mechanism guarantees it for every handoff from every agent
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/build-feature.js:1595`
  (`const handoffTarget = phaseResult.handoff_target;`) and the refusal at `:1606`,
  against `templates/agents/python-coder.md` — and against every other agent template

**Symptom.** A phase returns `handoff` and the drive stops:

```
Phase 'python-coder' returned 'status: handoff' but named no recognizable
handoff_target ('undefined'). Refusing to guess a re-dispatch target and
refusing to advance to the next phase in phaseOrder.
```

**Cause, and it is not "the agent forgot".** The driver reads the target from a
`handoff_target` key on the phase's returned payload. Grep the entire agent template
directory:

```
grep -c handoff_target templates/agents/python-coder.md   -> 0
templates/agents/ files mentioning handoff_target         -> 0
```

**No agent template anywhere names that field.** What `python-coder.md` actually documents
is a *ticket-file* convention, in three places:

- `:142` — "Adds tasks to `### test-writer` section and uses `(status: handoff)` instead of
  `(status: ok)`"
- `:458` — "When signing off, use `(status: handoff)` instead of `(status: ok)` to signal
  that test-writer must run next."
- `:601` — "`(status: handoff)` to test-writer for the assertion-only fix."

So the protocol is specified as *write a section in the ticket and mark the comment*, and it
is read as *set a key in the return value*. An agent that follows its template **exactly**
produces a handoff the driver cannot route. This is not intermittent and not agent-dependent:
it is every handoff, always.

**Why blocker rather than high.** The handoff path is not an edge case — it is the mandated
route for the Test Delegation rule, where a coder that needs a test changed must hand off
rather than edit tests itself. So the one protocol the repo requires coders to use is the one
that halts the drive, and the halt is unrecoverable by re-running: the cached phase result is
byte-identical, so the same `undefined` comes back. Both observed instances required a human
to read the prose and act on it.

**The information is always present and always ignored.** In both observed cases the target
was unambiguous in the record:

- `ACD-2100a-1` — the coder's comment named test-writer and gave a full remediation manifest:
  file, function, and the exact one-line edit.
- `ACD-2100a-4` — the coder wrote an entire `## Implementation Tasks` → `### test-writer`
  section, which is *precisely* what `python-coder.md:142` instructs it to do.

The driver is right to refuse to guess. It is looking in the wrong place: the ticket says who
the target is, in the structured heading its own template mandates.

**Fix direction.** Resolve the target from the ticket rather than from the return payload —
the `### <agent>` heading under `## Implementation Tasks` is already structured, already
mandated, and already populated. If the return-payload contract is the one to keep instead,
then every agent template that can emit `handoff` must be told to set `handoff_target`, and a
`handoff` returned without it should be a template-conformance error named as such, not an
`('undefined')` the reader has to decode. Do not do both halves independently — the two-sided
contract with only one side documented is the defect.

**Trap for whoever fixes it.** The refusal message reads as a per-ticket problem, so the
natural response is to fix that ticket's comment by hand. That works, and it hides the
defect: the drive then runs until the next handoff, which is how this reached two occurrences
across two weeks before the pattern was visible. Check `grep -c handoff_target
templates/agents/` before concluding an instance is a one-off.

**Related.** `KI-BO-20260831-1930` (the driver defers a phase the generator marks needed) and
`KI-BO-20260831-1931` (completeness read from the newest comment while the driver halts before
dispatching) — the same family: a two-sided contract whose halves were specified separately
and never reconciled, failing closed in a way that reads as a ticket defect.

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse face: a gate that fails
closed correctly, on a field the other side of its own contract was never told to provide.

**Closed 2026-09-23.** Re-verified against the current code, not this entry's narrative:

- **The emitter side was fixed, not the driver side** — matching this entry's own second fix
  option ("every agent template that can emit `handoff` must be told to set
  `handoff_target`"). `grep -c handoff_target templates/agents/python-coder.md` now returns
  **3** and `test-writer.md` returns **2** (both were 0 at the time this entry was filed).
  `python-coder.md`'s "Test Delegation" behavior line (142) now reads: "...uses `(status:
  handoff)` instead of `(status: ok)`, and returns `handoff_target: \"test-writer\"` in the
  JSON result" — the exact two-part instruction (ticket prose AND the return-value field) this
  entry says was missing. `test-writer.md:530-534` carries the mirror instruction for handing
  back to `python-coder`/`sql-coder`.
- **No other template emits `(status: handoff)` for the driver to route on.**
  `grep -rl "status: handoff" templates/agents/*.md` returns exactly three files:
  `python-coder.md`, `test-writer.md`, and `retrospective-agent.md`. The third's only match is
  itself PARSING a historical `## Comments` status tag from ticket files during a retrospective
  — it does not itself emit a handoff for the driver to route on, so it is not a gap in this
  fix's coverage.
- **The driver side is unchanged, correctly** — `build-feature.js:2020` still reads
  `phaseResult.handoff_target` and still refuses diagnosably when absent (lines 2020-2058).
  That refusal is the fail-closed behavior this entry explicitly says to keep; only the
  emitter's silence needed fixing.
- **Verified by name and by test.** `BO-3000a.yaml` — "A handoff is routed by the target the
  handing-off agent named in its own result, and is refused diagnosably... never inferred from
  the ticket body" — is `work_status: done`, with its own amendment note recording that an
  earlier "infer from ticket body" design was rejected by code review in favor of the
  emitter-side fix, and that its coverage was rewritten and verified 1:1 against
  `unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py` by an AC-fulfillment gate.
- **Not verified end-to-end.** No live handoff dispatch was executed as part of this closure;
  the verdict rests on the current templates, the current driver code, and the AC store's own
  recorded test-mapping verification.

---
