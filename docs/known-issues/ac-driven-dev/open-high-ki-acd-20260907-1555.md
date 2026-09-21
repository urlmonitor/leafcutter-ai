---
title: "KI-ACD-20260907-1555 — Nothing in the pipeline binds a module or symbol name, so whichever agent needs one first invents it and the next agent cannot see the choice"
description: "KI-ACD-20260907-1555 — Nothing in the pipeline binds a module or symbol name, so whichever agent needs one first invents it and the next agent cannot see the choice"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-20260907-1555 — Nothing in the pipeline binds a module or symbol name, so whichever agent needs one first invents it and the next agent cannot see the choice

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3, all within one epic (EPIC-TrustThatAGreenCheckActuallyChecked)
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-07
- **Where:** the AC schema (`test_spec` pins the test side; no field pins the implementation
  side), ticket frontmatter `files_touched`, the `## Agent Contracts` block emitted by
  `generate_ticket_from_ac.py`, and `templates/agents/test-writer.md:682`

**The pipeline specifies the test side exhaustively and the implementation side not at all.**
An AC's `test_spec` pins each test's `name`, `target_dir`, `framework` and `type`. For the code
under test there is **no field anywhere** — not in the AC schema, not in ticket frontmatter —
that names the module to create or the symbols it must expose.

`test-writer` runs at priority 5, before any coder, so it must import something that does not
exist yet. Its template tells it to *"Import the module or function that the ticket says should
exist"* (`test-writer.md:682`). **The ticket routinely says no such thing.** Across this epic
`files_touched` is a bare package directory on most tickets (`templates/scripts/commit_guardian`)
and on ticket 36 it is literally `files_touched: []`. So the agent invents a name. The coder,
reading the same silent ticket, invents a different one.

**Three instances, same epic:**

| test-side name | implementation-side name | caught by |
|---|---|---|
| `_authored_change.py` / `get_authored_change` / `AuthoredChange` | `_resolve_change_set.py` / `get_change_set` / `ChangeSet` | `pr-reviewer`, after the coder shipped |
| `unit_tests.portability.harness` | `unit_tests/portability/_deployed_check_harness.py` | manual, during a later ticket |
| `build_second_working_copy()` / `stage_carried_in_deletion()` / `run_check()` | `create_second_copy()` / `stage_files()` / `invoke_check()` / `run_sweep()` | manual, during a later ticket |

Note the direction is **not** consistent: in the first row the *test* was authoritative and the
coder diverged, and reconciling it cost a dedicated commit (`ecd31238d`, whose own message
records "the first implementation shipped as `_resolve_change_set.py` … and `pr-reviewer`
blocked it for the divergence"). In the other two the *implementation* was authoritative. There
is no rule about who wins because there is no binding — only whichever artifact a human happens
to read first. `test_ge_120e_2_i.py`'s own decision-history block calls its guess
"a SPECULATIVE harness contract".

**Why the red baseline cannot catch this.** `test-writer.md:684` names `ImportError` as a valid
red state — correctly, since the code genuinely does not exist yet. But that makes
*"not implemented"* and *"named something the coder will never create"* produce **the identical
signal**. The red baseline is this pipeline's evidence that tests constrain the implementation;
against a misnamed import it is evidence of nothing. GE-120 exists to stop a green check that
never checked; this is its mirror — a red check that proves nothing — and it cost real time in
GE-120's own drive, where a fixture bug and a naming divergence both presented as
"AC not implemented yet".

**The phase that should decide already runs first, and declines the job.** `architect-review`
is dispatched before `test-writer`. On ticket 35 it produced a genuinely good blast-radius
analysis — it identified `_authored_change.py`, its `get_authored_change() -> AuthoredChange`
signature and every attribute both consumers read. It named **no module for the new code**,
because naming is outside its charter: its own `completion_manifest` records
`seam_note: not_applicable`, reasoned as *"architect-review performs classification and
notation only; it makes no code change and introduces no producer/consumer seam of its own."*
Its template describes it as classifying impact and writing an inline note. So the slot in the
phase order exists, the right agent is already in it, and it is explicitly defined as not
deciding this.

**The contract mechanism also already exists, and covers only documentation.** The
`## Agent Contracts` block on a generated ticket carries a `### documentation-expert`
subsection listing exact file paths, and a `### Expects From` subsection whose contract is
**prose** (ticket 35: *"The shared authored-change source, which this AC requires to consult
the operation record…"* — no symbol in it). There is no `### python-coder` and no
`### test-writer` subsection. And documentation has an enforcement phase —
`documentation-verifier` at priority 11.9 blocks the commit when a named doc file is absent
from the diff. **There is no equivalent asking whether the module the tests import was ever
created under that name.**

**How it should work.**

1. **`architect-review` binds the names, and that becomes its deliverable.** Widen its charter
   from classify-and-note to classify-and-bind: for any ticket that creates a module or a new
   public symbol, it must emit the exact path and the exact public surface (function names,
   class names, and for a returned object its attribute names — the shape all three failures
   above turned on). Its existing `seam_note: not_applicable` escape must stop being available
   when `change_target: code` and the ticket creates a file. It already does the analysis; today
   it just throws the naming half away.
2. **The binding lands in a structured field, not prose.** Add a `### code-contract`
   subsection to `## Agent Contracts` — machine-readable, same pipe-delimited grammar as the
   documentation rows so one parser serves both. It must be parseable, which is the standing
   objection in `KI-ACD-20260831-agent-contracts-block-not-pipe-delimited`: fix that first or
   the new subsection inherits the same defect.
3. **Both downstream agents read it, and neither may deviate.** `test-writer.md:682` changes
   from *"the module the ticket says should exist"* to *"the module named in
   `### code-contract`"*, plus an explicit refusal: **if the ticket creates a module and names
   no path, emit `(status: blocker)` rather than choosing a name.** The same binding is injected
   into the coder prompt. An implementation agent inventing a public name is then a defect, not
   a judgement call — which is the rule this entry is really asking for.
4. **Verify it the way documentation is verified.** A `code-contract-verifier`, modelled on
   `documentation-verifier`, asserts every path and symbol in the block exists in the diff.
   That closes the loop: the red baseline stops being the only thing standing between a guessed
   name and a merge.
5. **Cheap partial, worth doing regardless of the above:** make `files_touched` name **files**,
   never bare directories, and reject an empty `files_touched` on a `change_target: code`
   ticket. Ticket 36 shipped with `files_touched: []` and is the worst of the three cases. This
   alone would not have prevented any of them — a path is not a symbol — but it removes the
   condition under which an agent has nothing at all to go on.

**Related.** `KI-ACD-20260831-agent-contracts-block-not-pipe-delimited` (the same block, already
unparseable — a prerequisite for fix 2). `KI-BP-20260831-generator-emits-unparseable-doc-contract`
(the generator side of it). `KI-BO-20260907-1555` shares ticket 36 as its worked example, from
the dispatcher side.

**Pattern:** a contract between two agents that exists only inside the artifact one of them
happens to write first — so the second agent is asked to honour a decision it was never told
about, and the mechanism meant to detect the mismatch reports the same signal as
not-yet-implemented.
