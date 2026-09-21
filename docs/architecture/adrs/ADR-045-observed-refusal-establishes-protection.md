---
title: "ADR-045: A Check Counts as Protection Only Once It Has Been Observed Refusing"
description: "Every registered protective check must declare one known-bad input and the observable rejection it must produce, and a liveness runner must put that input through the entry point the protected surface actually uses and write the check's state from what it observed — because a declaration read back as its own answer is the defect this regime exists to catch."
type: "adr"
status: "active"
created: "2026-09-14"
last_updated: "2026-09-14"
deciders:
  - BrainCandy
  - architect-review
  - adr-author
components:
  - commit_guardian
  - precommit_hooks
  - testing_quality
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120c-1.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1600-counted-from-reality/BP-1600a-2.yaml
  - docs/testing/test-angles.verification.flow.json
  - docs/known-issues/commit-guardian.md
# check_negative_controls.py and test_ge_120f_1.py are this ADR's deliverables and do
# not exist yet; check-doc-frontmatter requires every related_code path to resolve, so
# they are named in section 4 of the body instead and added here when they land.
related_code:
  - config/verification_flow.schema.json
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/run_hook.py
  - unit_tests/portability/_deployed_check_harness.py
  - templates/hooks/readme_read_guard.py
---

# ADR-045: A Check Counts as Protection Only Once It Has Been Observed Refusing

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-09-14 |
| **Author** | `adr-author`, on the decision of BrainCandy with architectural facts settled by `architect-review` |
| **Supersedes** | None |

---

## Context

A protective check can be registered, invoked on every commit, reachable, and still
unable to refuse anything — and nothing in this repository distinguishes it from a
check that refuses correctly. Both are green on every input they are ever given. One
is green because it rejects what it should reject and passes what it should pass; the
other is green because its refusal branch cannot be reached, so it passes everything,
including the inputs it exists to stop.

`templates/hooks/readme_read_guard.py` is the worked example, re-derived using the
guard's own gating helper on 2026-09-01. Three of its four gated prefixes resolve out
from under themselves through symlinks into the deployed tree and stop matching; the
fourth names `alembic/`, a directory this repository has never had. It is registered,
correctly wired, and running on every edit, and it gates nothing. Its inertness arises
by two different mechanisms depending on layout — an exception in the main workspace, a
plain failed prefix match inside a worktree — so a repair addressing only the first
leaves every worktree inert, and worktrees are where the drives run.

Four adjacent acceptance criteria already own neighbouring questions, and the worked
example passes all four:
[`BP-1600a-2`](../../acceptance-criteria/build_pipeline/BP-1600-counted-from-reality/BP-1600a-2.yaml)
owns enumeration (which guards are in the set at all);
[`BP-100k-4`](../../acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml)
owns a registered gate whose trigger can never match;
[`GE-120c-6`](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120c-1.yaml)
owns a deployed guard that nothing invokes; and
[`TQ-500`](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500.yaml)
owns falsifiability of *tests*. None of them asks whether a guard that is in the set,
whose trigger matches, and which something does invoke, is capable of saying no. That
is the gap this ADR closes, and it is the subject of the parent L1
[`GE-120f`](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f.yaml)
— "A guard that has never said no is not counted as protection" — under which the
originating ticket
[`01_TICKET-20260914-GE-120f-1`](../../../tickets/00_inbox/epics/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01_TICKET-20260914-GE-120f-1.md)
implements
[`GE-120f-1`](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml).

The cost of not deciding is already paid and recorded. `config/verification_flow.schema.json`
states this rule in the repository's own words — "The known-bad input that MUST be
rejected. A check without one can pass on dead code" — models the negative control, the
`not_applicable`-with-a-`reason` hatch, and a four-value state enum. It has **no code
reader**: re-verified on 2026-09-14, no file under `scripts/`, `templates/` or
`unit_tests/` references it, and `docs/testing/test-angles.verification.flow.json` is
the only document ever written against it. The vocabulary was invented, one instance
document was produced, and the validator was never built. A vocabulary with one reader
becomes a vocabulary with none; this ADR makes that schema's first consumer.

The failure this decision must be designed against is subtler than the absence of a
check. It is a check *about* checks that satisfies itself by reading a declaration. A
well-formed declaration naming an input and a rejection, treated as evidence that the
rejection was observed, makes the first run quiet and reproduces the original defect one
level up — the declaration becomes the new thing nobody checks. Every binding clause
below is written so that no implementation which reads the declaration can satisfy it.

---

## Decision

### 1. Protection is established by observation, never by declaration

Every protective check on the registration surface defined in §2 MUST declare one
known-bad input it must reject, together with the observable rejection that input must
produce. A liveness run MUST put that declared input through the check and MUST write
that check's state from what it observed.

The check's **state** and its **evidence** MUST be produced by execution and MUST come
from nowhere else. A check whose declared input has not been put through it MUST record
`unverified` — the schema's own honest placeholder for an attempt never made — however
complete and however well-formed its declaration is written. A declaration MUST NOT be
read back as its own answer.

This constrains the state and the evidence, not the whole record. The record also
restates the declared input, the declared rejection, and the entry point used, which are
necessarily copied from the declaration and from the run's own configuration; those
fields are descriptive context, and no observational claim may rest on them. The
discriminator for the whole regime is the alter-and-revert pair: the declaration MUST be
held byte-identical while the check's behaviour is changed, and the recorded state MUST
move.

### 2. The population is the registration surface, and the registration surface is `hooks_manifest`

The liveness run MUST take its population from the checks that
`templates/scripts/commit_guardian/commit_guardian.json`'s `hooks_manifest.hooks` names
when it is read at run time, restricted to the subset that an entry line actually
invokes. It MUST NOT recite a list held inside the runner, and it MUST NOT encode any
population figure in the implementation or in any test expectation — every assertion is
count-and-membership over the run's own emitted output.

This is a boundary, not a gap: `GE-120f` reads the **registration surface**;
`BP-1600a-2` walks the **disk**. A check registered nowhere never touches the
registration surface and is structurally invisible here. The run MUST NOT be described
as covering the registered-nowhere case, and a disk walk MUST NOT be built beneath this
decision — this family has already had to unpick that fork once. The invoked subset of
`BP-1600a-2`'s census is consumed, never re-derived, and no second census is grown
beside it.

### 3. The declaration vocabulary is `config/verification_flow.schema.json`'s, reused verbatim

Each `hooks_manifest.hooks` entry naming a real gate MUST gain a `negative_control`
object whose shape is copied from that schema's `$defs/negative_control` — either
`{input, command (optional), expected_result, currently}` or the
`{not_applicable: true, reason}` alternative — and a `currently` object copied from
`$defs/currently`: `{state, observed, evidence[]}`. The entry MUST also carry
`entry_point`, defined there as "the real production way in that this check invokes
(CLI, hook, workflow dispatch, deployed script). NOT an internal helper import".

The four state values MUST be reused verbatim: `passing`, `failing`, `blocked`,
`unverified`. Synonyms MUST NOT be minted. `blocked` MUST NOT be collapsed into
`failing`. The block MUST NOT be omitted for an unrun control — the schema already
requires `unverified` "rather than omitting the block, so 'we never fed it bad input' is
visible in the artifact instead of silent". A second vocabulary beside this one MUST NOT
be written.

### 4. The runner is a registered `hooks_manifest` gate, deliberately named `check_*.py`

The runner MUST be `templates/scripts/commit_guardian/check_negative_controls.py`, and
it MUST be a real `hooks_manifest` entry invoked through `run_hook.py`. It MUST NOT be a
CI-only job and MUST NOT be a bare `unit_tests/` module: of the three candidate surfaces,
only a `hooks_manifest` entry blocks at commit time locally as well as in CI.

The runner MUST take the `check_*.py` name deliberately. `hook_parity.hook_script_patterns`
is `["check_*.py", "run_hook.py", "regenerate_*.py"]`, so this name enrols the runner in
`BP-1600a-2`'s future gate census, and the runner MUST be **registered** rather than
exempted. The exemption path exists and is declined: `hook_parity.excluded_scripts` in
the same config lists non-gates that match the pattern, and a sibling reachability
registry records a ground per entry. This runner is a genuine gate, not a utility hiding
from the census, so it belongs in the census it will one day be counted by.

Helper modules the runner needs MUST take an underscore prefix — this codebase's
existing answer to adding code to that directory without entering the census — and MUST
live inside `templates/scripts/commit_guardian/`, which `build_commit_guardian` copies
verbatim. Any module imported from outside that directory MUST be added to the deploy
map in `scripts/build_phases.py` in the same change, or the deployed runner raises
`ModuleNotFoundError` at runtime while source-tree unit tests stay green.

### 5. Execution is out of process, against the deployed copy, through the real entry point

The run MUST extend `unit_tests/portability/_deployed_check_harness.py` rather than
growing a second harness. That harness genuinely performs a `subprocess.run` build into
a second working copy, scrubs `PYTHONPATH`, and forces an isolated interpreter (`-I`)
with cwd off the source tree. The second copy MUST be built once per sweep, never once
per check.

`templates/scripts/commit_guardian/` is canonical; `scripts/commit_guardian/` and
`.leafcutter/scripts/commit_guardian/` are build outputs (see
[ADR-001](ADR-001-self-hosting-boundary.md)). An alteration applied to a copy the run
does not load fails **green**, and that failure is indistinguishable from a pass. The
alter-and-revert evidence MUST therefore state which copy was altered and which copy the
run loaded, and MUST assert they are the same path.

Several commit-guardian hooks ignore `argv` and read the git index or `HOOK_TEST_FILES`.
For any check invoked through `run_hook.py`, the run MUST establish that the check
actually saw the known-bad input before reading its verdict. A clean exit from a check
that was handed nothing MUST be recorded as `unverified` or `blocked`, never as
`passing` — a clean exit from a check that saw nothing is the never-attempted state
wearing a pass, and recording it as `passing` is this tree's own defect committed by its
own tooling.

Errors in the runner's subprocess, filesystem and JSON I/O MUST be caught by specific
exception type and logged at WARNING or higher or re-raised. A swallowed invocation
error MUST NOT become an absent record or a silent `passing`; it is `blocked`.

### 6. The runner is guarded twice, and the second guard does not route through its own regime

This is the sub-decision most likely to be quietly dropped in implementation, so it is
stated separately and in full.

**6a — The runner carries its own `hooks_manifest` entry with its own `negative_control`.**
It MUST NOT be exempt from the regime it enforces. A liveness checker that proves every
other check can refuse, while carrying no declaration of its own, is the precise
asymmetry `KI-CG-021` already cost this repository once.

**6b — AND its existence and reachability MUST additionally be pinned by unit tests that
do not route through the liveness regime at all.** This is the load-bearing half.

The reason is that guarding the runner *only* by its own regime is **circular**. If the
runner silently stops running, the thing that would report that is the thing that
stopped. Its silence arrives as an absence of findings, which is byte-for-byte what a
healthy repository with nothing to report also produces. No amount of hardening inside
the regime can distinguish those two states, because in both of them the regime emits
nothing. An independent unit test is the only guard that survives the runner itself
failing, precisely because its own liveness does not depend on the runner's.

Those tests MUST assert, without invoking the liveness run to do it, that the runner
exists at its registered path, that its `hooks_manifest` entry resolves to it, and that
invoking it through `run_hook.py` reaches it. A test that establishes any of these by
asking the liveness run does not satisfy this decision.

### 7. The two-guard rule generalises to this whole family

Decision 6 is a **general rule**, not a one-off for this ticket. Any later change in
this family that adds a **verifying surface** — anything whose output is a claim about
whether other things are working — MUST be guarded both by the regime it participates in
and by at least one independent check that does not route through that regime. The
governing test is whether the new surface's own silent failure would be distinguishable
from a clean result; whenever it would not be, the independent guard is mandatory.

This rule MUST be carried into `GE-120f-2`, which owns the run's outcome, and into every
subsequent record beneath `GE-120f`.

### 8. The runner's refusal MUST move a gate's verdict

A runner whose refusal changes no gate's verdict is inert — exactly `KI-CG-021`'s shape,
a `main()` hardened over six review rounds that no runner ever called. The runner's
non-zero outcome MUST propagate into the outcome of the `hooks_manifest` entry line that
invokes it, and that propagation MUST be demonstrated by a reachability-angle test that
asserts the gate's own exit status moves. Registration in a config section that no entry
line executes is not reaching; that is the trap `KI-TQ-007` records, where configuration
presence reads as evidence of registration.

---

## Consequences

### Positive

- A check that cannot refuse becomes **visible** and **named**, instead of being
  indistinguishable from one that refuses correctly. The worked example's failure mode
  acquires, for the first time, a mechanism that can report it.
- `config/verification_flow.schema.json` gains its first code reader. A vocabulary that
  was invented, documented once, and never consumed becomes load-bearing, which is the
  cheapest available alternative to minting a second vocabulary beside it.
- The alter-and-revert discriminator makes the regime **self-falsifying**: because the
  declaration is held byte-identical while behaviour changes, an implementation that
  reads the declaration cannot pass, and the anti-grep property is enforced mechanically
  rather than by reviewer vigilance.
- Blocking at commit time locally, not only in CI, means the feedback arrives where the
  repair is cheapest, and a local pass stops being a claim that CI will later contradict.

### Negative

- **Day-one blast radius is large, and that is the correct outcome.** On the commit that
  lands this, most checks will record `unverified`, because no refusal has ever been
  demonstrated for them. That is the true state of the repository. It MUST NOT be
  pre-suppressed by seeding records or by writing exemptions ahead of the first run, and
  the natural remedy for the resulting noise — weakening the rule until it goes quiet —
  is the failure mode to design against.
- **The worked example is outside the population this runner examines.**
  `readme_read_guard.py` is wired in `templates/settings.json`, a registration surface
  that `commit_guardian.json`'s `hooks_manifest` does not name and that this runner does
  not read. The motivating example therefore remains undetected by the mechanism its own
  defect motivated. This is recorded as a known limit, not as coverage; see the
  Unresolved Boundary note below.
- Naming the runner `check_*.py` enrols it in `BP-1600a-2`'s census, so the runner
  becomes one more thing that must stay registered and correct. This is accepted
  deliberately in §4 as the honest cost of not hiding a genuine gate.
- The sweep builds a real second working copy and executes checks out of process, so it
  is slow. It MUST be marked slow rather than quietly narrowing its subject list to stay
  fast.
- Maintaining a `negative_control` per gate is ongoing authoring work, and a
  `not_applicable` ground is now a thing reviewers must adjudicate rather than a thing
  they can wave through.

### Operational

- Every `hooks_manifest` entry naming a real gate must be given a `negative_control` or
  a grounded `not_applicable`, in the same change that lands the runner. A postponement
  is not a ground.
- Every `pytest` invocation covering this work MUST carry `AC_ENFORCE_STRICT=1`; without
  it `pytest_ac_enforcement` xfail-masks tests covering a not-done AC, and a green run
  means nothing.
- After any change to the runner or its helpers, `python scripts/build.py --target-dir .`
  must be run, because the run executes the deployed copy and the source tree is not what
  it loads.
- Reviewers of any future change in this family must apply §7 explicitly: ask whether the
  new surface's silent failure would look like a clean result, and require an independent
  guard whenever it would.

### Unresolved boundary carried forward, not closed here

No acceptance criterion today takes a census of the
`templates/settings.json` / `templates/hooks/` registration surface. Measured 2026-09-07,
`templates/hooks/` holds 13 scripts and `templates/settings.json` wires 11. The worked
example passes the enumeration boundary not because a census looked at it and found it
present, but because no census looks at it at all. This ADR does not close that gap and
must not be read as closing it. Extending the population of §2 to a second registration
surface is a separate decision requiring its own record.

---

## Alternatives

- **A CI-only job.** Rejected. It does not block at commit time locally, so the defect is
  reported only after the work has left the developer's machine, and a local pass
  continues to mean something CI will later contradict. Of the three candidate surfaces
  examined, only a `hooks_manifest` entry blocks in both places.

- **A bare `unit_tests/` module collected by `ci.yml`'s existing `test` job.** Rejected
  for the same mechanism as the CI-only job: `pytest` is not run at commit time locally,
  so the gate is absent exactly when a developer is creating the condition it detects.
  It was the third-preference reaching surface in the AC's own ordering and lost to the
  entry line for that reason.

- **Naming the runner outside the `check_*.py` glob to stay out of `BP-1600a-2`'s census.**
  Rejected. The mechanism is available and would work — `hook_parity.hook_script_patterns`
  is a literal glob list, and a differently-named file simply is not matched. It is
  rejected because the runner is a genuine gate, and a gate that arranges not to be
  counted reproduces this ADR's own defect class one level up: an enforcement surface
  invisible to the census that exists to find enforcement surfaces. The underscore-prefix
  convention remains correct for the runner's *helpers*, which are not gates.

- **Declaring the runner in `hook_parity.excluded_scripts` with a recorded ground.**
  Rejected. The path exists and is in live use for `check_outcome.py` and
  `check_v2_ac_store_alignment.py`, each with a written ground. It is declined because
  both existing entries are genuine non-gates — one has no `main()` at all, the other's
  entry point is an agent step rather than the pre-commit stage — whereas this runner
  blocks commits. Using the non-gate hatch for a gate would make the hatch's own meaning
  unreliable for every future reader.

- **Guarding the runner solely by its own `negative_control`.** Rejected as circular. If
  the runner stops running, the regime that would report that is the thing that stopped,
  and its silence is indistinguishable from a healthy repository with nothing to report.
  The failure mode is undetectable from inside, by construction, which is why §6b
  requires a guard that does not route through the regime at all.

- **Minting a new vocabulary for the per-check record.** Rejected. A synonym set beside
  `config/verification_flow.schema.json` is how a vocabulary with one reader becomes a
  vocabulary with none — the exact history that produced the unread schema this ADR
  consumes. Reuse costs nothing and removes a second thing to keep in sync.

- **Growing a second out-of-process harness rather than extending
  `_deployed_check_harness.py`.** Rejected. The existing harness already performs a real
  `subprocess.run` build into a second working copy, scrubs `PYTHONPATH`, and forces an
  isolated interpreter with cwd off the source tree. A second harness would duplicate
  each of those four properties, and any one of them silently omitted turns the
  alter-and-revert evidence into theatre by letting the run load a copy other than the
  one altered.

- **Deriving the record from the declaration when the declaration is well-formed.**
  Rejected, and named as the mutation every descriptor must survive. It is the
  efficiency a hasty implementation reaches for precisely because it makes the first run
  quiet; under it, every check carrying a declaration reads as demonstrated and the
  `unverified` class empties. It is rejected by construction rather than by preference:
  §1's alter-and-revert pair holds the declaration byte-identical while behaviour
  changes, so no declaration-reading implementation can produce a moving state.

- **Extending the population to walk the disk so the worked example is covered.**
  Rejected. `BP-1600a-2` owns the disk walk. Building a second census beneath `GE-120f`
  would fork a boundary this family has already had to unpick once, and the two records
  would disagree the first time one of them changed. The worked example's exclusion is
  recorded as a limit above and belongs to a separate decision about a second
  registration surface.

---

## References

- Originating ticket: [`tickets/00_inbox/epics/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01_TICKET-20260914-GE-120f-1.md`](../../../tickets/00_inbox/epics/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01_TICKET-20260914-GE-120f-1.md)
- Acceptance criterion: [`GE-120f-1`](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml) under parent [`GE-120f`](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f.yaml)
- Upstream vocabulary: [`GE-126b-5`](../../acceptance-criteria/guardrail-engine/GE-126-checks-answer-truthfully/GE-126b-5.yaml) (defines the four values and requires them carried); [`GE-126c-5`](../../acceptance-criteria/guardrail-engine/GE-126-checks-answer-truthfully/GE-126c-5.yaml) (which copy the run loaded)
- Population boundary: [`BP-1600a-2`](../../acceptance-criteria/build_pipeline/BP-1600-counted-from-reality/BP-1600a-2.yaml)
- Deployed-layout convention: [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md)
- Component: [`docs/architecture/components/commit-guardian.md`](../components/commit-guardian.md)
- Known issues: `KI-CG-021` (a hardened `main()` no runner called) and `KI-TQ-007` (configuration presence read as registration), in [`docs/known-issues/commit-guardian.md`](../../known-issues/commit-guardian.md) and `docs/known-issues/testing-quality.md`
- Schema and its only instance document: `config/verification_flow.schema.json`, [`docs/testing/test-angles.verification.flow.json`](../../testing/test-angles.verification.flow.json)

<!--
Component note: `testing_quality` is listed in `components` alongside `commit_guardian`
and `precommit_hooks` because Decision 5 binds `unit_tests/portability/_deployed_check_harness.py`
and Decision 6b binds an independent unit-test surface; there is no registered component
id specific to the portability harness, and `testing_quality` is the closest registered id.
-->
