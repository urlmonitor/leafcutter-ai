---
title: "The done-proof entry-point gate refuses the proof it asks for and accepts the one it forbids"
description: "A full-store sweep of BO-2900a-1's entry-point reachability gate, which backs the required Proof-of-done CI check. 185 of 188 in-scope done ACs (98.4%) are refused, an upper bound. The predicate reads entered_entry_point alone, so a ritual invocation that enters main and then calls the code directly passes while an ordinary direct-import test is refused — the exact trap the sibling AC's decision history says the check must never reduce to. It also judges 29 of 54 ACs against a module other than their declared implementation file, and its whole scope depends on --test-root being spelled '.' rather than absolutely."
type: explanation
status: active
created: 2026-09-29
last_updated: 2026-09-29
components:
  - ac_store
  - build_orchestration
  - testing_quality
related_docs:
  - docs/known-issues/ac-store/open-low-ki-acs-20260928-entry-point-gate-demands-cli-traversal-from-every-proof.md
  - docs/architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md
  - docs/analysis/2026-09-25-jev-test-triage-leafcutter-replication.md
---

# The done-proof entry-point gate refuses the proof it asks for and accepts the one it forbids

`_apply_entry_point_reachability_gate`, in
`scripts/ac_store/_done_proof_entry_point_gate.py`, landed on main on 2026-09-25 in commit
`11b92057` as part of BO-2900a-1. It is the third condition on done-eligibility, composed
into `verify_done_eligible` at `scripts/ac_store/done_proof.py:2429-2434`, and so it backs
the **required** "Proof-of-done coverage check" CI gate. Its rule: for each Python
covers-tagged test of an otherwise-eligible done AC, detect whether the test's unit defines
a module-level `main`; if one exists and the test's own execution never entered it, refuse
with `refusal_cause: "proof_not_through_entry_point"`.

The target failure is real and documented in this repository's own history, so this page is
not an argument that the gate should not exist. It is an account of the distance between
what the gate's acceptance criterion asks for and what its predicate decides, and of the
measured blast radius of that distance.

## Verdict

| Finding | Status | Figure |
|---|---|---|
| Nearly every in-scope done AC is refused | MEASURED (sweep), count is an UPPER BOUND | 185 of 188 (98.4%) |
| The predicate reads `entered_entry_point` alone, never `reached_through` | VERIFIED by execution | ritual probe: eligible **True** |
| An ordinary direct-import test of the same unit is refused | VERIFIED by execution | `proof_not_through_entry_point` |
| The judged unit is not the AC's declared implementation file | MEASURED (sweep) | 29 of 54 (54%) |
| The judged unit is the build-output copy, not the source copy | MEASURED (sweep) | 627 of 811 detections (77%) |
| Scope depends on how `--test-root` is spelled | VERIFIED by execution | `.` → 188; same dir, absolute → 0 |
| Tests the observation runner cannot execute at all | MEASURED (sweep); causes SAMPLED | 49 ACs, 274 of 803 observations |

Rows marked "VERIFIED by execution" were re-derived for this page against the checked-out
tree; rows marked MEASURED come from a full-store sweep of 2026-09-28 using the gate's own
functions, with no sampling and scope computed by `_detect_module_entry_point` itself.

## 1. Scale

| Population (all MEASURED) | Count |
|---|---|
| AC records scanned | 4,455 |
| `work_status: done` (13 of them waived) | 1,024 |
| done, with at least one Python covers-tagged test | 799 |
| **in the gate's scope** (a test whose unit defines module-level `main`) | **188** |
| refused `proof_not_through_entry_point` | 136 |
| refused `observation_unavailable` | 49 |
| pass | 3 |

At the level of individual observations rather than ACs, the 188 produced 803 observations:
491 direct-import refusals, 274 "isolated re-run did not pass", 9 unparseable, and **29**
that entered the detected way in. MEASURED.

**185 of 188 is an UPPER BOUND.** The gate runs only after the two incumbent conditions have
passed — a covers-tagged test exists, and every such test passes (`done_proof.py:2429`;
BO-2900a-1 requires that "reachability is evaluated only after both pass"). The sweep
applied the gate's functions without first establishing that precondition per AC; three ACs
were spot-checked end-to-end, the other 182 were not. An AC whose linked tests already fail
for unrelated reasons would never reach this gate in a real evaluation, yet is counted here.

By component the 185 refusals are: build-orchestration 79, knowledge-management 28,
build-pipeline 28 (21 + 7 under two spellings of the name), ux-prototyping 25, ac-driven-dev
13, infrastructure 9, guardrail-engine 2, testing-quality 1. Largest families: KM-KGS (25),
BO-2400f (19), BO-2400a (13), BO-2500e (10), BO-2400c (8), INF-500e (8). All MEASURED. The
[known issue](../known-issues/ac-store/open-low-ki-acs-20260928-entry-point-gate-demands-cli-traversal-from-every-proof.md)
filed on 2026-09-28 closes by saying "the store has not been swept for how many ACs are in
this state; that count is the first thing the owner will want and is not yet measured." The
table above is that count.

## 2. The central defect: the gate accepts the ritual it exists to refuse

Line 176 of `_done_proof_entry_point_gate.py` calls the observation runner with an **empty**
target specification — `_observe_reachability(test_file, test["function"], "", entry_point)`
— and line 196 branches on a single fact from the result:
`if not observation["entered_entry_point"]:`. The runner (`done_proof.py:476-490`) sets
`reached_through` only when a frame whose qualified name equals `_TARGET_SPEC` is entered
while the entry point is a live ancestor on the same stack. With `_TARGET_SPEC` the empty
string no frame can ever match — a qualified name is always `"<module>:<name>"` — so on this
path `reached_through` is structurally, unconditionally `False` and the gate cannot consult
it. The only fact available to line 196 is *did the test enter `main` at any point*.

That is decidable by ritual. A probe was constructed for this page: a unit exposing
`the_behaviour_under_proof()` and a `main(argv)` that deliberately never calls it, plus a
test invoking `main(["noop"])` and then calling the function directly. Against the real gate:

| Probe | `entered_entry_point` | `reached_through` | gate verdict |
|---|---|---|---|
| ritual: `main(["noop"])`, then direct call | True | False | **eligible: True** |
| ordinary: direct call only | False | False | refused, `proof_not_through_entry_point` |

Both VERIFIED by execution. Same unit, same function under proof, same assertion about its
behaviour; the only difference is one line entering a `main` that does nothing relevant, and
it decides the verdict.

**The gate's own family says this must not happen.** BO-2900a-1's criteria require the
criterion to become eligible once a proof "drives the same behaviour by invoking the way in
with the action and arguments an operator would use" — which the ritual probe does not do,
and it passes. More pointedly, `done_proof.py`'s DECISION HISTORY entry for the sibling
BO-2900a-1-i, dated 2026-09-07, describes this probe exactly:

> The check is deliberately never a conjunction of two independently recorded booleans
> (entered_entry_point AND target_was_called), since that conjunction is satisfiable by one
> unrelated entry-point invocation plus a separate direct call to the target — the exact
> ritual-invocation trap this AC isolates.

The a-1 gate is weaker than the conjunction that entry rejects — it is not a conjunction at
all, reading `entered_entry_point` and nothing else. The machinery to avoid the trap exists
in the same runner, reached by the same function: the a-1-i path at `done_proof.py:686-689`
passes a real `target_spec` and tests `reached_through`. The a-1 path passes `""`.

The errors compound in opposite directions: a ritual invocation is accepted, and an honest
test that executes the behaviour but reaches it by import is refused, 136 times over. The
predicate is not a strict or a loose version of the intent. It is a different predicate.

## 3. It judges the wrong unit

`_detect_module_entry_point` first checks whether the test file itself defines `main`; if
not, it iterates `sorted(_local_import_module_names(test_file))` and takes the first bare
import resolving to a file that defines one (gate module, lines 118-124). Ordering is
over module names, not relevance to the AC. Of the 188 in-scope ACs, 54 declare a `.py`
`it_requirements.reference_file_path`, and **29 of those 54 (54%) are judged against a
module other than their own declared implementation file.** MEASURED.

| AC (all MEASURED) | Declares | Judged against |
|---|---|---|
| BO-2500e-2, BO-2500e-3 | `scripts/ac_store/done_proof.py` | `mark_ac_done:main` |
| BO-2400a-2 | `scan_ac_store.py` | `fast_lane:main` |
| BO-2400d-1 | `submit_feedback.py` | `generate_health_report:main` |
| ACD-1200b-4 | `epic_readiness_gate.py` | `goal_to_epic:main` |
| BP-900c-1 | `build_propagation_audit.py` | `build:main` |

The BO-2500e-2 row was re-derived here: its covering test imports both `done_proof` and
`mark_ac_done`; `done_proof.py` defines no module-level `main` and `mark_ac_done.py` does
(`mark_ac_done.py:321`), so the alphabetically-first qualifying import is `mark_ac_done`.
VERIFIED by execution. The AC is about `done_proof.py`, and the gate demands it be proven
through the CLI of a different script the test happens to import.

A second distortion rides along. `_resolve_candidate_unit` falls back to
`sorted(project_root.rglob(f"{module_name}.py"))` (`done_proof.py:1960`), and `.leafcutter`
sorts before `scripts`. **627 of 811 detections (77%) resolve into `.leafcutter/`, the
build-output tree, rather than `scripts/`** — MEASURED, with the ordering re-derived here
for three real test files, all three landing in `.leafcutter/` (VERIFIED by execution). CI
sees the same: it runs `build.py --target-dir .` at `ci.yml:266` immediately before invoking
the gate at line 275. The entry point a proof is measured against is therefore a build
output, which can be stale against the source the AC names.

## 4. The scope is an accident of argument spelling

`_resolve_candidate_unit` excludes candidates inside the test tree — "a module physically
living inside the test tree is test-support code, not implementing code" — via
`_is_within(candidate, test_root)` (`done_proof.py:1966`). `_is_within` is
`path.relative_to(root)` wrapped in a `ValueError` guard (`done_proof.py:1884-1890`), and
`Path('/abs/x.py').relative_to(Path('.'))` raises `ValueError`, so with a relative
`test_root` the exclusion returns `False` for every absolute candidate and never fires.
Both deployed invocations pass `--test-root .`:
`scripts/commit_guardian/commit_guardian.json:1209` and `.github/workflows/ci.yml:275`. That
argument means "the whole repository is the test tree", and with it the exclusion is
silently disabled and the project-wide fallback is unblocked. Spell the *same directory*
absolutely and the exclusion fires for every candidate instead of none:

| `--test-root` | Detection on three real test files | Scope over 799 done ACs |
|---|---|---|
| `.` (both deployed call sites) | entry point found in 3 of 3 | 188 (MEASURED) |
| absolute path to the same directory | `None` in 3 of 3 | 0 (MEASURED) |

The three-file column is VERIFIED by execution; the scope column is from the sweep. This is
a fail-open, and the gate's entire operating scope rests on it: the same guard, pointed at
the same tree, judges either every done AC or none of them, according to how its caller
typed the path.

## 5. Forty-nine ACs whose proofs cannot be observed at all

49 of the 188 are refused `observation_unavailable`, accounting for 274 of the 803
observations — "isolated re-run did not pass". MEASURED. The runner
(`_REACHABILITY_RUNNER_SCRIPT`, `done_proof.py:433-557`) executes one named test function in
a bare subprocess, outside pytest. From a uniform random sample of 25 of the 274, seed 7
(SAMPLED), the causes are: pytest fixtures (`tmp_path`, `capsys`, custom ones),
pytest-style test classes, and package-relative imports failing with `ModuleNotFoundError:
No module named 'unit_tests'` — the runner adds only the test file's own parent directory
to `sys.path` (`done_proof.py:464`).

**This is distinct from the `unittest.TestCase` defect fixed in PR #862 (`41ae84ea`), and
conflating the two would be a mistake.** That defect was narrower: the runner resolved the
test with `getattr(module, name)` and called it, which raises `AttributeError` for a method
and was reported as "did not pass", indistinguishable from a real failure. It is fixed —
`_find_case_class` (`done_proof.py:493-508`) now locates the defining `TestCase` subclass and
runs it through the case's own `run()`. The 49 above are what remains *after* that fix, with
different causes; a reader who assumes PR #862 handled this will be hunting a closed defect.
The gate does fail closed here, which is the right posture for an unobservable proof — the
observation is only that "the runner cannot execute this test" is a common condition rather
than a rare one, and is reported with the same finality as a genuine refusal.

## 6. The gate is aimed at a real failure

Nothing above argues the intent is wrong, and the evidence that it is right stands on its
own terms. The failure shape is catalogued: [the Jev
replication](2026-09-25-jev-test-triage-leafcutter-replication.md) names "Reachability: code
never reached from a production entry point" as a distinct shape in leafcutter's own corpus,
with 5 vacuous and 5 fixed tests spanning BO-2400f-7..10, BO-1700 T02 and TQ-100. It is also
the shape that document reports its pre-registered wiring questions handled *worst*
(`reaches_entry_point` AUC 0.58) — an argument for a mechanical check over a judgement.

The calibrating incident is recorded in BO-2900a-1's own notes:

> When the five fast-lane AC-lifecycle functions were marked done, every statement the
> incumbent gate checks was TRUE: a covers-tagged test existed, it executed real code, and it
> passed. What was false is that no test in the repository entered the module's way in — every
> test direct-imported an inner function.

`CLAUDE.md`'s own worked example under "Gate / Workflow ACs" is the same incident:
`fast_lane.py` had no CLI, so the runner's `select_batch` call was a silent no-op and the
structural tests could not see it. And the demand is satisfiable in a way that would
genuinely have caught it.
`unit_tests/build_orchestration/test_bo2400f_7_cli_proof.py` — one of the 3 passing ACs —
drives `fast_lane:main(["claim", ...])` as an operator would, and says so in its docstring:
the fine-grained direct-import unit tests of `claim_build_set` stay in the sibling file
*without* the covers tag, "a different and still-useful thing to assert, just not the
reachability proof." That test would have failed on the stranded lifecycle functions. It is
the shape BO-2900a-1 asks for, it exists, and it passes. The intent is implementable.

## 7. The counter-position, at its strongest

`unit_tests/ac_store/test_done_proof_composite.py` carries a module-docstring section
titled "Why `verify_done_eligible` is exercised directly for AC-6 (tests 1 & 2)". Its
argument is not laziness:

> The Implementation Notes name scripts/ac_store/done_proof.py as the file of record and
> require the composite/leaf distinction to "live in this module's done-eligibility logic"
> — i.e. in verify_done_eligible itself. Calling it directly is the most direct behavioral
> exercise of that logic and needs no git fixture repo: … a real on-disk fixture store +
> real on-disk pytest files fully exercise the real classification and subprocess-pytest
> code paths with zero mocking.

The unit of record was named by the ticket, and the test addresses it directly over real
on-disk artifacts. The gate refuses it because the module beside it also exposes a CLI.
`CLAUDE.md`'s standing rule, "Gate / Workflow ACs — Verify Behaviorally, Not by Grep",
licenses less than it appears to on either side. Its stated target is the presence-only
assertion: "a test that only greps the source for a string's presence or ordering… passes on
dead code." A direct-import test that executes the behaviour is not that, and already meets
the rule's letter. But its worked example is the fast-lane incident, and it says the fix
"required behavioral (CLI) and semantic-consumption… tests" — so it does not license
direct-import proofs for *command-surface* ACs either. It settles neither side. What it does
not support is the gate's actual reach: every unit that defines `main`, whether or not the
criterion is about the command surface.

The sharpest tension is internal to the family. BO-2900a-3, this gate's own sibling, carries
an anti-ritual clause as a structural constraint:

> THE ANTI-RITUAL CLAUSE IS STRUCTURAL: no term in the condition set may reference test
> count, test presence, test outcome, or coverage. Adding another passing test must be
> incapable of changing the verdict, because the predicate never reads those facts.

PR #862 (`41ae84ea`) flipped BO-2500a-6 from refused to eligible by appending a CLI
assertion to ten covers-tagged tests across two files. The composite/leaf logic in
`verify_done_eligible` that BO-2500a-6 is *about* was not touched; that commit's only
`done_proof.py` change was the unrelated `TestCase` runner fix, which widens observation and
weakens no refusal. Adding assertions to tests changed the verdict — the behaviour a-3's
clause forbids, occurring in a-1. This was the same session's own work, and its commit
message says so: "the gate still demands CLI traversal from every proof, which conflicts
with that test file's documented rationale."

## 8. Open questions, not answered here

1. Whose position governs when a deliberately-reasoned direct-import test meets a gate that
   refuses it — the test's author, or the gate? The known issue filed this for BO-2900a-1's
   owner and declined to author an AC, since authoring one would presume the answer.
2. Does ADR-050's refuse-never-warn posture extend to this gate? ADR-050's own subject is
   the BO-2900b/c change-refusal hook over the built argparse surface, not the a-1 done-proof
   gate. The known issue invokes it for posture — reasonable, but not the ADR's stated scope.
3. What is the true refused count once the "all linked tests already pass" precondition is
   established per AC? 185 is an upper bound; nobody knows the lower one.
4. Which unit should a criterion be judged against — the one its `reference_file_path`
   declares, or the one its test imports first alphabetically? They disagree for 54% of the
   ACs that declare one.

---

*Claims marked VERIFIED by execution were re-derived on 2026-09-29 in
`/home/henzeh/projects/leafcutter/worktrees/ki-guardrail-findings`, branch
`analysis/entry-point-gate` at `origin/main`, by importing and running the gate's own
functions: the §2 probes, the §3 import ordering and `.leafcutter` resolution, the §4
`_is_within` and `--test-root` behaviour. Quoted text was read at source; probe fixtures
were written under `/tmp` and no repository file but this one was touched. MEASURED counts
come from the 2026-09-28 full-store sweep, reported as given; the §5 cause breakdown is
SAMPLED (25 of 274, uniform, seed 7). No remedy is proposed here, by design.*
