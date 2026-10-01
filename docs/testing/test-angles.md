---
title: "Test Angles — A Set-Cover Taxonomy for Proof of Done"
type: reference
status: active
created: 2026-08-14
last_updated: 2026-09-30
components:
- testing_quality
- build_orchestration
related_docs:
- docs/testing/README.md
- docs/testing/test-angles-failure-catalogue.md
- docs/architecture/components/phantom-done-prevention.md
- docs/reference/ac-schema.md
description: "The five core + two conditional test angles required per acceptance criterion, the observed repo incidents that justify each, the literature behind them, and the failure classes this taxonomy explicitly does not fix."
---
# Test Angles — A Set-Cover Taxonomy for Proof of Done

## The thesis: the red baseline IS the specification

Under this repo's TDD order (`test-writer` before any coder — CLAUDE.md "TDD Order"),
the coder's contract is literally *make the red baseline green*. The cheapest green is
therefore **exactly the shape of the test that was written**. If the red test opens with
`from fast_lane import claim_build_set`, the cheapest green is a function. The CLI
subcommand, the workflow invocation, and the deploy-manifest entry are not in the red
baseline, so they are not in the contract, so they never get written — and the suite
stays green over code that nothing calls.

That is not hypothetical. Commit `9c58f4550` (PR #422), verbatim:

> The BO-2400f-7..10 lifecycle functions (claim_build_set, release_claim,
> filter_already_claimed, mark_done_built_acs, check_no_stale_todo) shipped
> unit-tested but unreachable — no CLI subcommands, no workflow invocation
> (phantom-done).

Those functions landed green in `8f0c55c2b` (PR #411) and were only *reached* by
`9c58f4550`. The defect was in the test plan, not in the code.

The corollary matters: **you cannot fix this by exhorting the coder.** The only lever is
what the red baseline contains. A test-angle taxonomy is a set-cover checklist applied
*before* the tests are written.

At HEAD, the ticket generator's fallback path (`_derive_tests_from_criteria` in
`scripts/ac_store/generate_ticket_from_ac.py`, selected by
`_build_test_requirements_section` when the AC carries no `test_spec`) emits one test
descriptor per Gherkin `Then` clause and nothing else. That is the `criterion` angle
alone — one of seven.

That fallback is the common case, not the edge case: **1,509 of the 1,886 ACs assigned to
a coder agent (80%) carry no `test_spec`** and so take it. (Store-wide the share is
higher still — only 394 of 2,888 records author a `test_spec` at all — but the coder
population is the one that matters here.)

> **In flight (uncommitted, 2026-08-14):** that fallback now tags each descriptor
> `angle: criterion` and appends a mandatory `angle: reachability` descriptor — the
> reachability floor — via `TEST_ANGLE_CRITERION` / `TEST_ANGLE_REACHABILITY`
> (`generate_ticket_from_ac.py:67-68`). The floor implements the first two rows of the
> table below. The remaining five angles are still unrepresented in generated tickets.
>
> **Known weakness of the floor at that scale.** For the 80% with no `test_spec`, the
> appended reachability descriptor cannot name an entry point — it says so in its own
> text ("the entry point is not declared: resolve it before writing this test"), leaving
> *what IS the production entry point* to `test-writer`. As of BP-1100g-1 (2026-08-25),
> `test-writer` carries a machine-extractable taught set of all seven angle names and
> their distinguishing rules (`templates/agents/test-writer.md`
> `<!-- TAUGHT-TEST-ANGLES:START/END -->` anchor), kept in cross-source lockstep with
> `config/ac_store_schema.json`'s `test_spec[].angle` enum by
> `unit_tests/prompt_assembly/test_bp_1100g_1.py` — closing the *vocabulary* gap only.
> It does not close the *judgement* gap: knowing the seven names is not knowing which
> concrete function, script, or command is *this* AC's production entry point. Until
> that seam closes, a reachability mandate can still be satisfied by a renamed
> `criterion` test that picks the wrong one.

## The taxonomy

> **The one question that decides everything below:**
> **"If I deleted the single line that wires this in, would this test go red?"**
> If no, the test covers `criterion` and nothing else, whatever it is named.

| Angle | Charge it when | The question it answers |
|---|---|---|
| `criterion` | **always** | Does the unit do what the Gherkin `Then` clause says? |
| `reachability` | **always** | Does the production entry point actually reach it? |
| `seam` | the work crosses a producer→consumer boundary: a signature is extended, a written artifact is read back by another module, or two sources share a vocabulary | Does the real producer's real output work in the real consumer? |
| `real_artifact` | the code parses, loads, or matches something another tool serializes — or the claim is about import/module-load | Does it work on the bytes the real writer emits, in a cold process? |
| `deployed` | the file ships through `build.py`: a hook, a gate, an agent template, a workflow, or anything they import | Does it work in the deployed layout, not just the source tree? |
| `boundary` | the AC names a range, a limit, a count, or a shape that can be empty / one / many | empty / one / many / limit / malformed-but-parseable |
| `failure` | the AC names an error path, a fallback, or a fail-open/fail-closed contract | the error path — and does it fail *closed*? |

**How to select, given the cap of 4.** `criterion` + `reachability` are the **floor** —
always both, never negotiable; that pair is what the generator's reachability floor now
emits. The other three core angles are "core" in the sense that you must always *check
their trigger*, not that all five are always charged. Where a trigger in column 2 fires,
that angle is mandatory. Floor (2) + at most two more = the cap of 4. When three or more
triggers fire, **cover two with one test** rather than dropping one: a subprocess test
that runs the deployed copy against a real on-disk artifact charges `reachability`,
`real_artifact` and `deployed` at once. Count angles covered, not tests written. The two
conditional angles never consume a slot by default — see "the two conditional angles"
below for why.

**`criterion`** — the AC-literal happy path, asserted on the unit that implements it.

**`reachability`** — start at the **production entry point** (CLI via `subprocess`, hook
via its real runner, slash command, workflow dispatch, `main()` with real `argv`) and
assert both that the new behaviour occurs *and* that its result is consumed in control
flow. Not satisfied by: importing the module; asserting a symbol exists;
`assertIn("name", registry_json)`; asserting a value was *passed as an argument* (that is
dispatch topology, not execution).

> **Modifier — `must_block`.** For any gate / guard / validator AC: a second test feeds
> known-bad input through the *same* entry point and asserts it **blocks** (non-zero exit,
> or the blocker string in the payload) — a gate that cannot block is inert, and a
> positive-path test alone can't tell the difference. It normally rides `reachability`,
> since that is usually where a gate's entry point lives, but it attaches to whichever
> angle carries that entry point: `real_artifact` for a schema validator, `seam` for a
> routing branch. The modifier is about what is being guarded, not which slot it occupies.

**`seam`** — pipe the REAL producer's actual output into the REAL consumer and assert the
consumer's observable behaviour. Not satisfied by calling an extended function with the
new argument: that passes while every real caller still uses the old signature.

**`real_artifact`** — fixture bytes come from the real serializer (`yaml.safe_dump`, the
project's ticket writer) or a verbatim on-disk file, never a hand-typed literal. For any
module-load claim, verify in a **genuinely fresh subprocess**: `importlib.reload()`
re-executes in an already-populated namespace and masks cold-import errors.

**`deployed`** — run `build.py` into a temp target, then exercise the DEPLOYED copy.
Source-tree imports are structurally blind to deploy-manifest gaps.

**`failure`** — the can-fail proof. A check that only ever reports "clean" licenses the
assumption it exists to falsify, so the obligation is not "does the error path exist" but
"can this check observe and report the bad state" — proved by deliberately inducing that
state via a **named mutation** and asserting the check catches it **by name**, not just
that something failed (the same discipline as the zero-file incident under "Existing
machinery" below). [TQ-600a-3](../acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml)
is the worked example: it dirties the TQ-600a-1 shared layout inside one consuming test
and requires the comparison to name both the altered file and the offending test by node
id. This is what separates `failure` coverage from a `criterion` test that merely asserts
an error message exists.

## Failure catalogue — the evidence base

> See [test-angles-failure-catalogue.md](test-angles-failure-catalogue.md) for the full
> incident-by-incident evidence base — reachability, seam, authenticity, deployment, and
> negative-control gaps, plus the two conditional angles' concentrated evidence — that
> justifies every core angle in the taxonomy above.

## Literature grounding

- **Khorikov, *Unit Testing: Principles, Practices, and Patterns*, ch. 7-8.** The
  complexity × collaborators quadrant. Controllers/orchestrators — low complexity, many
  collaborators — **cannot** be usefully unit tested: mocking the collaborators leaves
  only the wiring, which is precisely the implementation detail you must not assert on.
  They get integration tests. Budget (ch. 8): one integration test per business-scenario
  happy path, real *managed* dependencies, doubles only for *unmanaged* out-of-process
  ones. **In this repo, hooks, workflow steps, agent dispatch, and registration are all
  orchestrator-quadrant code** — which is the theoretical statement of why `reachability`
  and `seam` must exist here.
- **Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests*.** Walking
  skeleton, outside-in, acceptance test written **first**. The load-bearing point is
  *sequencing*: a test written after the implementation gets written against whatever the
  implementation happens to be. Phantom-done is a sequencing failure as much as a coverage
  failure.
- ***Software Engineering at Google*, ch. 13-14.** Configuration is the #1 cause of major
  outages. The enumerated list of what narrow tests structurally cannot catch — unfaithful
  test doubles, configuration, load, unanticipated inputs, emergent behaviour — and the
  blunt formulation that isolated tests using test doubles may pass while the actual
  system fails. Direct warrant for `deployed`.
- **Fowler, *TestPyramid*.** A failing high-level test means **two** bugs: the defect and
  a missing low-level test. Also *IntegrationTest* (narrow vs broad) and *ContractTest*
  (double drift) — the latter is exactly what `seam` guards.
- **Meszaros, *xUnit Test Patterns*.** The *Production Bugs* smell and its named causes,
  especially **Neverfail Test** (our grep-only structural tests) and **Lost Test** (our
  `continue-on-error: true` CI job and our six hook-less drives).

### Prompt-design note: do NOT give an agent a ratio model

Pyramid / trophy / honeycomb are **ratio models**. A ratio is an emergent property of a
whole suite; an agent working a single AC cannot observe or act on it. Worse, "write few
high-level tests" combined with a cheapest-green optimiser collapses reliably to *zero*
high-level tests.

Give the agent a **set-cover checklist over machine-decidable predicates** instead —
which is what this document is. Crispin & Gregory's agile-testing quadrants are
explicitly non-sequential and are the right *shape*; Feathers' disqualifier list ("not a
unit test if it touches the DB / the network / the filesystem / needs environment setup")
is the right *mechanics*, because every clause is checkable without judgement.

## What this taxonomy does NOT fix

Two independent minings of the 28-file retrospective corpus (`docs/retrospectives/`) put
**process failures at the plurality**. The two passes extracted different-sized failure
sets — 36 failure records in one, 24 in the other, since neither pass read every file and
neither used the other's extraction rule — but both landed on the same share: 15-16 of 36,
and 11 of 24. Roughly four in ten. The agreement is on the *ratio*, not the counts; treat
the counts as two samples, not as one population measured twice. These are **not** fixable
by better test-writing. Do not file them here.

| Failure | Evidence | Correct owner |
|---|---|---|
| Orchestrator lies about completion: `/build-feature` returned "5 tickets completed / epic complete" while ticket 02's implementation sat uncommitted in the working tree | EPIC-BOPhantomDoneRemediation, 2026-07-15 | build-feature workflow + post-drive verification |
| Store lies about state: finalize step 3.5 (`pre_merge_ac_closure`) flipped **45** tickets/ACs to done across **4 unrelated epics**; separately, step 3.5's "closure already present" skip left 7 merged tickets at `status: todo` | EPIC-PhantomDoneFilesTouched 2026-07-07; EPIC-InFlightVisibility FP-4 2026-07-23 | `finalize-feature.js` scope query |
| Gates run *after* commit: `ac-validator`, `ac-fulfillment-gate` and `live-surface-tester` are absent from `phaseOrder` in `templates/workflows-js/build-ticket.js:118-140` and `build-feature.js:184-206`; `getPriority()` returns `phaseOrder.length` for unknown agents, sorting them **after** `commit` and `pull-request` | verified in source, 2026-08-14 | workflow phase ordering |
| Gates never ran at all — **six** drives committed with zero package pre-commit hooks: AcPipelineDeployGaps (2026-06-17, all nine hooks, 14 would-have-blocked findings, fix `25adec3`), **PrecommitSafetyNet (2026-06-17 — the epic that shipped the safety net, run with the safety net off)**, Oneagenthandles… (2026-06-18, 18 commits), FinalizeFeatureHardening (2026-06-24, enabling all four F4 post-merge regressions), QuickFixWorkflow (2026-07-10, "hooks active: 0"), BOPhantomDoneRemediation (2026-07-15) | six retrospectives; single root cause `TICKET-20260617-Worktree_Precommit_Bootstrap.md`, still open across the whole nine-week window | worktree bootstrap / pre-flight |
| Work lands outside the ticket system: EPIC-QuickFixWorkflow's 16 tickets were all doc-spec-only, so a 516-line `SKILL.md`, a 440-line `quick-fix.js` and a command template arrived in three ad-hoc commits with no AC traceability — two post-merge defects (`BP-600f`, `ACS-700`) followed | EPIC-QuickFixWorkflow KI-1, 2026-07-10 | epic planning / `/build-ac` |
| Tests backfilled against *pre-fix broken* code (PRs #282/#290) merged before the fix (#281) and survived a union merge alongside the correct tests | EPIC-BOPhantomDoneRemediation, 2026-07-15 | backfill sequencing policy |

**Stated plainly: an enforced pre-drive pre-flight — hooks active, sink reachable, deploy
current — is arguably higher leverage than this entire taxonomy.** Six drives with zero
enforcement is a larger hole than any test-shape improvement can close, and the failure is
silent by construction: pre-commit exits 0 under `PRE_COMMIT_ALLOW_NO_CONFIG=1`, so an
ungated drive is indistinguishable from a gated one in the commit log.

## Existing machinery — reuse, do not rebuild

All four claims verified against the working tree on 2026-08-14; a fifth was added and
verified on 2026-09-21 (TQ-600a-1), and extended on 2026-09-28 (TQ-600a-1-i).

- **`user-surface-smoker` already implements the reachability angle** for user-facing
  surfaces, at priority 11.5, with a built-in negative control (`placeholder_signature`
  — a regex the output must NOT match), routed off `declares_side_effect`
  (`_build_agents_map` in `generate_ticket_from_ac.py`, BP-1100f-5). **It fires on 0 of
  the 2,888 records in the AC store** (every `.yaml` under `docs/acceptance-criteria/`,
  all of which parse). `declares_side_effect` is absent from `config/ac_store_schema.json` at
  HEAD, whose root is `additionalProperties: false` (`:15`), so no AC can legally carry
  it — a sibling change adding the property sits uncommitted, and even once it lands,
  zero records carry the field, so authoring is the second half of the fix. This is
  EPIC-ComputedQualityGates FP-1 layer 2 repeating: the mechanism shipped, the store
  never carried the data.
- **`test_requirements.schema.json` v1.1.0 already defines the vocabulary**:
  `type: live_dispatch` plus the required-when-`live_dispatch` field `surface_invoked`
  (`config/test_requirements.schema.json:48-71`). Outside `docs/`, the string
  `live_dispatch` occurs in **exactly one file in the repository — that schema**; nothing
  reads it. (Scope the grep to exclude `docs/`, or this page and its verification flow
  count themselves as consumers.) Reuse this vocabulary rather than
  inventing a parallel one; recommend retiring the name `live_dispatch` in favour of
  `reachability`, keeping `surface_invoked` as the entry-point field.
- **`test-writer.md` Rule 3 (cross-layer seam) already exists** and was, until now, nested
  under a repair-only heading. It has just been rescoped: the current working-tree text
  reads "Cross-layer seam test required (ALL work — new and repair alike)" and adds the
  script → hook and workflow-step → workflow-step boundaries. Read the file before
  describing it — the change is uncommitted.
- **`done_proof.py` already has the scanner an angle gate needs**:
  `_scan_test_root_for_covers_tags()` collects `# covers: <AC-ID>` tags, and
  `_classify_outcomes()` treats `XFAIL`, `XPASS`, `SKIPPED`, `FAILED`, `ERROR` and
  "nodeid not found" as non-passing (fail-closed) — which is what defeats xfail-masking.
  An angle gate should extend this scanner with a second tag axis, not duplicate it.
- **`shared_reference_layout` (TQ-600a-1) gives the "deployed exactly once" criterion
  test a fixture to request instead of a harness to invent**: a session-scoped pytest
  fixture in `scripts/suite_performance/pytest_shared_reference_layout.py`, registered
  whole-suite via `pytest.ini`'s `-p scripts.suite_performance.pytest_shared_reference_layout`
  (mirroring `-p scripts.ac_store.pytest_ac_enforcement` above). The underlying
  `get_or_produce_shared_layout()` (`scripts/suite_performance/_shared_layout_producer.py`)
  is lazy and cross-process-lock-safe, handing every requester — including different
  xdist workers — the identical, fully-produced root path exactly once per run, so a
  criterion-angle test can request it directly instead of inventing its own
  deploy-counting harness.
  **Existence is a `reachability`-angle fact, not a `criterion`-angle one**: being real
  doesn't prove any given test is routed onto it — the same `user-surface-smoker` gap
  above. A test that never requests `shared_reference_layout` still deploys its own copy.
  The boundary is read-only: a test that mutates the package before building (e.g.
  `unit_tests/test_bp_900g_8*.py`) must keep building its own copy, or it corrupts the
  shared copy for every consumer. See CLAUDE.md "Tests must not spawn their own
  `build.py` — reuse a shared deployed layout" for the standing rule, and TQ-600a-1 for
  the full contract.
  **TQ-600a-1-i pins the cheapest boundary case, no production code changed** — merged
  under TQ-600a-1 (PR #941): a zero-consumer selection must never enter
  `get_or_produce_shared_layout()` (no deploy subprocess, laziness holds per xdist
  worker), while one consumer must trigger exactly one deploy. Three tests in
  `unit_tests/suite_performance/test_tq_600a_1_i.py` pin this, green on first run: no
  subprocess for zero consumers, an idle worker produces nothing, and the fixture is
  reached only through the real `pytest.ini` `-p` entry point, not an import-only path.
  The mutations these tests catch both live in `pytest_shared_reference_layout.py`:
  `autouse=True`, or producing the layout at plugin-import/worker-startup time instead of
  on first request. Non-entry is observed independently via `emit_execution_signal()` /
  `EXECUTION_LOG_ENV_VAR` (`scripts/suite_performance/_shared_layout_coordination.py`);
  the reported-deploy-count half is deferred to TQ-600a-6, which has no reporting
  surface yet.

## Relationship to BO-2900

`BO-2900-runtime-reachability-guard` is an existing L0 tree of **39 ACs, all
`work_status: todo`**
(`docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/`). Its
L0 criterion opens: *"Nothing counts as delivered until it is genuinely wired into how the
product runs."*

This document is **documentation FOR that tree** — its taxonomy, evidence base, and
vocabulary. It is **not** a reason to author new ACs. Adopt the terms here when
decomposing BO-2900a..f rather than minting a third vocabulary alongside `live_dispatch`
and `declares_side_effect`.

## Cross-links

- [docs/testing/test-angles-failure-catalogue.md](test-angles-failure-catalogue.md) — the
  per-mechanism incident evidence base extracted from this doc: reachability, seam,
  authenticity, deployment, and negative-control gaps, plus the two conditional angles.
- [docs/testing/test-angles.verification.flow.json](test-angles.verification.flow.json) —
  the machine-readable companion to this doc: 16 falsifiable checks, each with a runnable
  command, a negative control, and an observed state, that answer "is this taxonomy live
  or decorative?" As of 2026-08-14 it stands at 4 passing / 10 failing / 2 blocked. Read
  it before assuming any mechanism described here is enforced. Schema:
  `config/verification_flow.schema.json`.
- [docs/testing/README.md](README.md) — test layout, frameworks, ADR-028 Fixture Convention
- [docs/architecture/components/phantom-done-prevention.md](../architecture/components/phantom-done-prevention.md) — the five BP-1100f gates this feeds
- [docs/reference/ac-schema.md](../reference/ac-schema.md) — AC store field reference
- `config/test_requirements.schema.json` — the `live_dispatch` / `surface_invoked` vocabulary to reuse
- `templates/agents/test-writer.md` — Rule 3 (cross-layer seam) and the skip rule
- `scripts/ac_store/done_proof.py` — the fail-closed `# covers:` scanner to extend
- [TQ-600a-3.yaml](../acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml) — worked example of the `failure`-angle can-fail-proof pattern
