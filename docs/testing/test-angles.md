---
title: "Test Angles — A Set-Cover Taxonomy for Proof of Done"
type: reference
status: active
created: 2026-08-14
last_updated: 2026-08-14
components:
- testing_quality
- build_orchestration
related_docs:
- docs/testing/README.md
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
> text ("the entry point is not declared: resolve it before writing this test"). It hands
> the hardest judgement, *what IS the production entry point*, to `test-writer` — which,
> as of BP-1100g-1 (2026-08-25), now carries a machine-extractable taught set of all
> seven angle names and their distinguishing rules (`templates/agents/test-writer.md`
> `<!-- TAUGHT-TEST-ANGLES:START/END -->` anchor), kept in cross-source lockstep with
> `config/ac_store_schema.json`'s `test_spec[].angle` enum by
> `unit_tests/prompt_assembly/test_bp_1100g_1.py`. That closes the *vocabulary* gap —
> `test-writer` can no longer be ignorant of the word "angle" or of what separates each
> kind from a proof of the behaviour alone. It does not by itself close the *judgement*
> gap this paragraph is about: knowing the seven names and their rules is not the same
> as knowing which concrete function, script, or command is *this* AC's production entry
> point. Until that seam is closed, a reachability mandate can still quietly be satisfied
> by a renamed `criterion` test if the writer picks the wrong entry point.

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
> or the blocker string in the payload). A gate that cannot block is inert, and a
> positive-path test alone cannot tell the difference. It normally rides the
> `reachability` entry, because that is where a gate's production entry point lives — but
> it attaches to whichever angle carries that entry point. When the gate *is* a schema
> validator the entry point is `real_artifact`; when it is a routing branch, `seam`. The
> modifier is about what is being guarded, not which slot it occupies.

**`seam`** — pipe the REAL producer's actual output into the REAL consumer and assert the
consumer's observable behaviour. Not satisfied by calling an extended function with the
new argument: that passes while every real caller still uses the old signature.

**`real_artifact`** — fixture bytes come from the real serializer (`yaml.safe_dump`, the
project's ticket writer) or a verbatim on-disk file, never a hand-typed literal. For any
module-load claim, verify in a **genuinely fresh subprocess**: `importlib.reload()`
re-executes in an already-populated namespace and masks cold-import errors.

**`deployed`** — run `build.py` into a temp target, then exercise the DEPLOYED copy.
Source-tree imports are structurally blind to deploy-manifest gaps.

## Failure catalogue — the evidence base

Grouped by mechanism. Every core angle below is justified by incidents observed *in this
repository*.

### Reachability gap — never invoked from a production entry point

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| BO-2400f-7..10 (`8f0c55c2b` #411 → `9c58f4550` #422) | lifecycle functions had no CLI subcommand and no workflow call | tests imported the functions directly |
| fast lane, 2026-07-22 (CLAUDE.md "Gate / Workflow ACs") | `fast-lane-build.js` never executed its red/green gates; `fast_lane.py` had no CLI, so the runner's `select_batch` call was a silent no-op | grep-only structural tests assert a string is *present* — they pass on dead code |
| BO-1700, EPIC-BOPhantomDoneRemediation T02 (2026-07-15, `50e28cc1`) | `check_hook_freshness()`'s return value silently discarded; `resolve_hooks_path(cwd)` re-resolved internally and ignored | tests called the helpers directly, never via `run_checks()` |
| BO-2300 Interactive Pause/Resume — phantom-built **twice** | dispatch happened; the instruction payload and the on-disk effect did not | tests keyed on dispatch topology — presence, labels, counts of dispatched helpers that a mock controls (`docs/architecture/components/phantom-done-prevention.md`) |
| `finalize-feature.js` (EPIC-FinalizeFeatureHardening F2, 2026-06-24; EPIC-PrecommitSafetyNet KI-3) | legacy `async function run({...})` wrapper with no top-level body — the Workflow tool **never invokes it**; the agent fallback was dead, all 6 finalize steps done by hand | nothing executed the script through the real Workflow tool; a never-called entry function looks fine statically |
| TQ-100 collection isolation, `2a377f91` (2026-07-08) | CI's `-x` aborted at the first failure; the guarantee was inert in real CI | per-ticket tests built their own subprocess calls *without* `-x` — never the production invocation |

### Seam gap — both sides tested, never wired together

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| EPIC-ComputedQualityGates FP-1 layer 1 (2026-07-08, PR #201) | all three real call sites invoked `_build_agents_map(assigned_agent)` with no axes, so the computed path was dead code | tests called the function with the new kwargs; no test ran the generator end-to-end |
| BO-400c-3-i, EPIC-BOPhantomDoneRemediation T04 (2026-07-15) | the sole production call site (in `check_ticket_signoff_parity.py`) still passed one argument | all unit tests called the extended function correctly |
| EPIC-ComputedQualityGates FP-1 layer 3 | hook's `ALLOWED_CHANGE_TARGETS` and `guardrail_gates.yaml` keys were **disjoint** vocabularies | each side was tested against its own copy; no cross-source set-equality contract test existed |
| EPIC-PrecommitSafetyNet FP-1 (2026-06-17, `656b6d6`, PR #89) | tier lookup read a field from a file the re-dispatch path never opened; 4 of 7 `blocking_hook_ids` had no manifest entry, so lookup returned `null` and judgment-tier failures never routed | producer and consumer each green in isolation; the cross-ticket `delivers_to`/`expects_from` contract was never traced, and the consumer mocked the dependency |
| EPIC-AcPipelineDeployGaps inbound gap 4 (2026-06-17) | finalize step 3's output schema did not match step 6a's reader — the whole failure-tracking loop was dead code | writer and reader covered in isolation; no test round-tripped a real artifact between them |

### Authenticity gap — the fixture was not the real artifact

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| EPIC-PhantomDoneFilesTouched KI-1 (2026-07-07, PR #209 / `17c538fe`) | `files_touched` parser was a **complete no-op on every real ticket** — PyYAML emits list items at column 0; the regex required indented dashes | every fixture was hand-typed with indentation, reproducing the exact bias that hid the bug. The *first* remediation spot-check reused indented fixtures and missed it again |
| EPIC-ComputedQualityGates FP-1 layer 2 (2026-07-08) | **no AC in the 1,802-record store carried `change_target`/`risk_surface`** — the computed path returned `None` for every real AC even after the call sites were wired | every test fed hand-built AC dicts that already contained the axes; no test loaded a real on-disk AC |
| GenReviewFixes H-2 (2026-07-21, PR #372 / `439b74007`) | forward-reference `NameError` in `_load_migration_map`'s cold-import fallback — fires only in a genuinely fresh process | tests used `importlib.reload()`, which re-executes in an already-populated namespace, so names that would raise on true first import were already bound |
| GenReviewFixes root `conftest.py` (2026-07-21) | a repo-root `conftest.py` silently hijacked `from conftest import load_fixture` in an unrelated test tree | per-file runs resolve conftest relative to that file and passed; only the full strict suite reproduced real collection order |
| EPIC-ComputedQualityGates FP-7 (2026-07-07) | the `[NO-FEEDBACK-CHECK]` bypass reads `GIT_COMMIT_MSG`, which git only writes *after* the pre-commit stage — the bypass never fires | the tests set the env var themselves, reproducing a state git never produces at pre-commit time |
| EPIC-InFlightVisibility FP-1 / FP-7, `BO-1000b-1-i` (2026-07-23, fix `17735a2ed`) | every skipped step double-recorded in `stepOutcomes[]` | the count-guard regex matched only quoted-string first args and was blind to the template-literal calls it was meant to catch |

### Deployment gap — source tree green, deployed copy broken

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| `done_proof.py`, 2026-07-22 (CLAUDE.md "New Hook / Gate Dependencies") | omitted from `build_ac_store`'s `deploy_map`; the deployed hook raised `ModuleNotFoundError` — would have blocked **every** merge once required | unit tests import from the source tree; caught only when the hook fired on its own commit |
| BP-811, EPIC-AcPipelineDeployGaps Finding #3 (2026-06-17) | the shim wrote workflows to `output_root/workflows/`, not `.claude/workflows/` — the deployed file was unreachable at the invocation path | **the AC asserted the copy tier ("file present in build output"), never the reachability tier ("the command resolves and executes")**. This is the cleanest statement in the corpus of why `deployed` and `reachability` are separate angles |
| EPIC-AcPipelineDeployGaps inbound gap 2 | `plan-feature.js` was absent from `templates/workflows-js/`, so `build.py` never deployed it to any consumer | all tests ran the workflow from the source tree; nothing asserted the build manifest contained it |
| EPIC-FinalizeFeatureHardening F4-2 (2026-06-24) | the committed deployed mirror `scripts/workflows/plan-feature.js` diverged from its template source | the mirror relationship is codified nowhere an agent can check; the only detecting test lives in main's CI |
| EPIC-DocumentationCoverageGuarantee FP-2 (2026-08-10) | missing `requires_verification: true` failed `install_shims`, blocking the pytest gate *before any test ran* | the failure is in the build step, which no unit test exercises |

### Negative-control gap — the guard could not actually block

| Incident | What was actually broken | Why the suite missed it |
|---|---|---|
| BO-1700, EPIC-BOPhantomDoneRemediation (2026-07-15) | the gate was **fail-open**; had to be flipped to fail-closed | no test fed known-bad input through the gate and asserted a block |
| FIN-100h, `a0bcb8a6c` (#437) | finalize Step 2's final `else` was the *success* path, so an observed `{"status":"refused"}` recorded a clean merge that never happened — directly upstream of merge-to-main | no test fed a refusal or unrecognised status through the branch |
| EPIC-InFlightVisibility FP-5 (2026-07-23) | merging origin/main silently deleted main's H-1/H-2 deploy-parity guards from `finalize-feature.js`; a malformed test run could then merge to main | the guards had no test feeding a failing/contradictory post-merge state, so deleting them broke nothing observable. All 353 tests stayed green |
| TQ-100 L-4 / BP-1200b (2026-07-08) | the CI pytest job is `continue-on-error: true` — the gate fires and merges proceed anyway | the plugin's own tests pass; nothing asserts the verdict is *consumed* by CI |

### The two conditional angles: real but concentrated evidence

Evidence for `boundary` and `failure` exists, but it comes from **two sources only** —
GenReviewFixes (PR #372) and EPIC-PhantomDoneFilesTouched rounds 1-2. Five other
retrospectives mined contribute none.

- `boundary` — TKT-500f-15: a scalar-string `components` value was iterated
  per-character instead of wrapped in a single-element list (the one-vs-many shape
  boundary). PhantomDone round-1 defects #3-#6: quoted paths, multi-ticket union, flow-list
  YAML (`[a, b]`) vs block list, `lstrip` path mangling. EPIC-BOPhantomDoneRemediation
  T03: `_check_change_target` had an empty-list guard, the identically structured
  `_check_risk_surface` did not, and all 22 tests passed because none exercised
  `risk_surface: []`.
- `failure` — PhantomDone round-1 #2: an `OSError` path did not honour the hook's
  fail-open contract. Round 2 then inverted it: a wrong-shape `commit_guardian.json`
  raised an uncaught exception and **blocked commits**. TKT-500f-18-i and ACD-1200a-14-i:
  malformed/unavailable mapping source and `git rev-parse` fallback both had to be made to
  degrade without raising.

**Two honest caveats.** Nearly every one of these was found by post-merge adversarial
review, not by a boundary test someone had identified in advance — the AC simply never
specified the edge case, so the fix is AC-authoring coverage at least as much as a test
angle. And both angles were caught by `pr-reviewer`, which already exists. That is why
they are **conditional and trigger-fired**: never mandatory, and never worth one of the
four angle slots by default.

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

All four claims verified against the working tree on 2026-08-14.

- **`user-surface-smoker` already implements the reachability angle** for user-facing
  surfaces, at priority 11.5, with a built-in negative control (`placeholder_signature` —
  a regex the output must NOT match). Routing is data-driven off `declares_side_effect`
  (`_build_agents_map` in `generate_ticket_from_ac.py`, BP-1100f-5). **It fires on 0 of the
  2,888 records in the AC store** (every `.yaml` under `docs/acceptance-criteria/`; all 2,888
  parse). `declares_side_effect` is absent from `config/ac_store_schema.json` at HEAD,
  whose root is `additionalProperties: false` (`:15`), so no AC can legally carry it. A
  sibling change adding the property is in the working tree, uncommitted — but even once it
  lands, zero AC records carry the field, so authoring is the second half of the fix. This
  is EPIC-ComputedQualityGates FP-1 layer 2 repeating exactly: the mechanism shipped, the
  store never carried the data.
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
