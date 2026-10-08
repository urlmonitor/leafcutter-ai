---
title: "Remedies for the done-proof entry-point gate: give it a declared scope, a predicate it cannot be tricked by, and a unit it was told"
description: "Companion to the 2026-09-29 entry-point-gate analysis. Five separable remedies against the four defects and their enabler, each named to real code in scripts/ac_store/. Recommends landing the scope separation and the unit-frame ancestry predicate together, then resolving the judged unit from the AC record, then hosting the observation in pytest. Includes a MEASURED prototype showing the replacement predicate refuses the ritual probe today's gate accepts, and the measurement that would change the plan."
type: explanation
status: active
created: 2026-09-29
last_updated: 2026-09-29
components:
  - ac_store
  - build_orchestration
  - testing_quality
related_docs:
  - docs/analysis/2026-09-29-the-entry-point-gate-refuses-the-proof-it-wants-and-accepts-the-one-it-does-not.md
  - docs/known-issues/ac-store/open-low-ki-acs-20260928-entry-point-gate-demands-cli-traversal-from-every-proof.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-3.yaml
---

# Remedies for the done-proof entry-point gate

The [sibling analysis](2026-09-29-the-entry-point-gate-refuses-the-proof-it-wants-and-accepts-the-one-it-does-not.md)
diagnoses `_apply_entry_point_reachability_gate` and deliberately proposes nothing. This page
proposes. It treats the diagnosis as given and does not restate its evidence; every new number
here is labelled MEASURED (re-derived on 2026-09-29 in this worktree) or carried.

## Recommendation

**Land C1 and C2 as one change; then C3; then C5. Keep the gate REQUIRED throughout, and narrow
what it judges rather than what it does about what it judges.**

| Step | Content | Why here |
|---|---|---|
| 1 (one PR) | **C1** separate the two jobs `test_root` is doing + **C2** replace the predicate with unit-frame ancestry | C1 alone silently disables *two* gates; C2 alone leaves scope accidental. Neither is safe to ship without the other. |
| 2 | **C3** resolve the judged unit from the AC record, refuse to guess | Needs C1's scope parameter to exist. Cuts the wrong-unit class; its inertness risk is contained by §5's population alarm. |
| 3 | **C5** host the observation in pytest | The `observation_unavailable` refusals have no operator action, which BO-2900e-1 forbids. Must precede any widening of policy. |
| Not now | **C4** narrow the policy to command-surface criteria | Re-litigates policy and needs a store field nobody has. Keep as a later ratchet on top of C3. |

The single sentence: the gate's problem is not that it is strict, it is that it is *guessing* — at
what to judge (scope), at which module (unit), and at what counts as proof (predicate). Remove the
three guesses and the strictness becomes defensible.

## 1. What each remedy must survive

The four problems and the enabler are separable, and no candidate below addresses more than two.

| # | Problem | Cleared by |
|---|---|---|
| 1 | POLICY: must every proof reach code through a module-level `main`? | C3 (by scope), C4 (by kind) |
| 2 | PREDICATE: `entered_entry_point` alone; `reached_through` structurally always False | C2 |
| 3 | UNIT: judged against the test's alphabetically-first import that defines `main` | C3, partly C2 |
| 4 | OBSERVABILITY: 49 ACs the runner cannot execute | C5 only |
| 5 | ENABLER: `_is_within(abs, Path("."))` is False, so the exclusion never fires | C1 |

Two facts bound the design, both MEASURED by reading the code today.

**`--test-root .` is not a mistake.** `commit_guardian.json:1217` states it deliberately: the
covers-tag scan must sweep the whole repository or JS-covered ACs are reported unproven
(BO-2500e-5), and consumer projects do not keep tests under `unit_tests/`. That same value is then
handed to `_resolve_candidate_unit` as "the directory to *exclude*" — one parameter, two opposite
requirements. The sibling calls the scope "an accident of argument spelling"; the argument is not
the accident, the overload is, which is why "spell it absolutely" is not an available fix.

**Fixing `_is_within` alone turns off two gates.** It is consulted by `_resolve_candidate_unit`
(`done_proof.py:1966`) and `_is_imported_elsewhere` (`:2015`), on which `_find_no_entry_point_unit`
(`:2060-2078`) is built — so a corrected `_is_within` under `--test-root .` resolves every
candidate to `None`, and BO-2900a-3's no-way-in gate stops firing alongside BO-2900a-1's. And
`_DEFAULT_TEST_ROOT = ""` (`check_done_proof.py:245`): a caller that *omits* `--test-root` already
gets the absolute spelling and the inert behaviour.

## 2. Five candidates

### C1 — Give the unit search its own root

`check_done_proof.py` gains `--unit-exclude-root` (default: the configured test directory, not the
covers-scan root), threaded through `verify_done_eligible`, `_apply_entry_point_reachability_gate`,
`_apply_reachability_gate`, `_resolve_candidate_unit` and `_is_imported_elsewhere` as a parameter
distinct from `test_root`; `_is_within` resolves both operands before comparing.

Fixes the enabler and makes scope a declared input; nothing else — the gate then judges a smaller,
honestly-chosen population by the same broken predicate against the same guessed unit. Migration
cost: **0 ACs**, two call sites, one signature. Proves wrong if a consumer project has no single
test directory: the default becomes "exclude nothing", reinstating today's behaviour under a better
name, and C3 becomes the only real scope control.

### C2 — Observe the unit's frames, not just its front door

Change `_REACHABILITY_RUNNER_SCRIPT` (`done_proof.py:433-557`) to take the **unit module name** in
place of `_TARGET_SPEC`. In `_profiler`, for every `call` event whose `frame.f_globals["__name__"]`
equals that module and whose callable is not the entry point, record the qualified name in
`touched`, and also in `touched_through` when the entry point is already a live ancestor on
`_call_stack`. `_observe_reachability` returns both sets; the gate
(`_done_proof_entry_point_gate.py:176,196`) refuses only when `touched` is non-empty and
`touched_through` empty, naming the functions reached only by import. MEASURED against one fixture
unit in four proof shapes, running the real `_observe_reachability` beside a prototype:

| Proof shape | Today's gate | Prototype (any-through) | Prototype (all-through) |
|---|---|---|---|
| ritual: `main(["noop"])`, then direct call | **eligible** | refused | refused |
| honest: `main(["run", "3"])` drives the behaviour | eligible | eligible | eligible |
| ordinary direct import | refused | refused | refused |
| mixed: one function through `main`, another direct | **eligible** | eligible | refused |
| resolved unit never entered by the test | refused | **no verdict** | no verdict |

Ship the any-through column. The last row is the quiet win: when the test never enters the resolved
unit, the resolution was wrong, and the gate now says so structurally instead of refusing.

C2 does not clear the 136 direct-import refusals — an honest direct-import test still has
`touched_through` empty, so it removes the false accept, not the contested refuses. It does not
help the 49 unobservable ACs, and a wrong unit the test *does* enter is still judged. Migration
cost: **0 ACs** to land, the same 136 still needing a decision. Proves wrong when a unit's `main`
is a thin dispatcher touching most of the module — then any-through is nearly vacuous and the
strict all-through column is the real predicate, at a far higher migration cost.

### C3 — Resolve the judged unit from the AC record

`_detect_module_entry_point` gains a `declared_unit: Path | None` parameter. When the AC record
declares its implementation file, only that file is inspected for a module-level `main`; the
`sorted(_local_import_module_names(...))` walk is deleted from the resolution path, not reordered.
When the record declares nothing, the function returns `None` — no verdict, handing off to the
BO-2900a-3 fence as it does today for a unit with no way in. The read seam is
`declared_files.get_declared_files` (`declared_files.py:110`), whose `NO_DECLARED_FILES` sentinel is
already the named "not declared" state; the transitional fallback is
`it_requirements.reference_file_path`. Adoption decides whether this is a remedy or a shutdown —
MEASURED over the whole store today:

| Field (of 4,456 records scanned, 1,025 done) | Records | of which done |
|---|---|---|
| top-level `declared_files` (non-empty list) | **2** (`TQ-600a-1-i`, `TQ-600a-1-ii`) | **0** |
| `it_requirements.reference_file_path` present | 361 | 235 |
| …of those, a `.py` path | 187 | **123** |

So `declared_files` alone makes the gate **exactly inert**: zero done records carry it, so zero can
be judged — and a required gate that judged nothing looks identical to one that found nothing, the
failure mode CLAUDE.md's merge-audit section already catalogues twice. With the
`reference_file_path` fallback it can judge at most 123 of 1,025 done records (the sibling's sweep
puts 54 of the in-scope 188 in that set). That is legitimate narrowing — judge what you were told,
decline to guess — but only when paired with the population alarm in §5. Migration cost: **123 done
records stay judgeable, ~900 leave scope until they declare a file**; new work costs one field.
Proves wrong if `reference_file_path` is aspirational rather than descriptive on a material
fraction of records: C3 would then swap one wrong unit for another. One nuance the sibling's §3
leaves open and C3 should not over-claim: the 77% `.leafcutter/` resolution does not corrupt the
observation, since the runner matches frames by module *name*, not by path. The build-output copy
decides only whether `main` is deemed to exist and which path the refusal names.

### C4 — Judge only criteria that are about the command surface

Fire the gate only when the criterion itself claims a command surface, decided from a record field
rather than the shape of the code: a new enumerated `proof_shape` on the AC schema, or the second
tag axis `collect_test_tag_records` (`done_proof.py:1138`) already collects and which its own
DECISION HISTORY calls "deliberately wired into nothing that computes eligibility".

The only candidate that answers POLICY head-on, and the honest home for the counter-position the
sibling records in its §7: a direct-import test of a module that merely also exposes a CLI is not
proving a command surface. It fixes nothing else, and its verdict depends on a declaration by the
author of the thing being judged. Migration cost: a field on every record that wants judging —
strictly worse than C3's for the same narrowing. Proves wrong the moment an author under-declares
to escape it; C3's declaration names which file the work touches and is checked against the tree.

### C5 — Host the observation in pytest

Replace the bare-subprocess execution in `_observe_reachability` (`done_proof.py:594-626`) with a
pytest invocation of the single node id under a profiling plugin carrying the C2 accounting —
`pytest <file>::<func> -p <plugin>`, in-process via `pytest.main()` or as a subprocess with the
`timeout=30` raised. Fixtures, `TestCase`-free pytest classes and package-relative imports then
resolve exactly as they do in the real suite, because they *are* the real suite.

The only candidate that touches the 49 ACs / 274 observations; no AC-side change substitutes. The
30-second timeout is the binding constraint: `done_proof.py:324-332` records collection alone at
~30-33s here, so a naive `pytest` subprocess per observation exhausts the budget before the test
body runs — `--rootdir`, `-p no:cacheprovider` and in-process invocation are the feasibility
condition, not optimisations. Migration cost: **0 ACs**; the cost is CI wall-clock. Proves wrong if
latency exceeds that budget at realistic AC counts — then observe per test *file*, not per function.

## 3. The gate stays required — and what that costs unrelated PRs

Keep it required. Narrowing what a gate judges is legitimate and is what C1 and C3 do; advisory is
not on the table, and the constraint needs no ADR-050 citation to hold — that ADR's `related_code`
names `check_reachability.py` and the reachability inventory, so it is scoped to the BO-2900b/c
hook, not this gate. The argument is simpler than a citation: this gate exists because a *passing
test* was accepted as proof of reachability, and a warning is a passing test in a nicer font.

The operational bite is narrower than the headline suggests — MEASURED by reading the call sites,
not carried. The pre-commit entry (`commit_guardian.json:1209`) runs `check_staged_done_proofs`,
which is static: it collects covers-tag ids (`_collect_all_covered_ids`) and never calls
`verify_done_eligible`. Only `--mode ci` and `--mode ci-changed` reach it
(`check_done_proof.py:755`, `:830`), and CI runs `ci-changed` against `origin/<base>`. The refusals
therefore bite **exactly on a PR that flips an AC YAML to done** — not on every PR, and not at
commit time. A docs PR, a refactor, a hotfix touching no AC record is unaffected today and stays
unaffected under every candidate above.

That bound is also the reason not to rush: the population that suffers is the AC-driven build loop,
every feature PR here, so a week of partial relief is worth less than a correct predicate. The
interim posture is therefore **no interim posture** — no blanket `SKIP=`, no waiver list. A blocked
PR files against the known issue and, if it must land, takes `SKIP=check-done-proof` per commit
with the AC id in the message, so the exceptions stay countable.

## 4. The prior recommendation, interrogated

The prior agent proposed: fix the fail-open; resolve the unit from `declared_files` with a
`reference_file_path` fallback; demand `reached_through`; keep refuse-not-warn; no store migration.
Three load-bearing claims do not survive contact with the code.

**Does `declared_files` at zero adoption leave a required gate inert?** Completely — MEASURED at 2
records store-wide and 0 done, so the pure form judges nothing. That is a new problem, not an
acceptable one, and is why C3 ships with the fallback *and* the population alarm. (The prior
agent's figures were 0 records and 378 with `reference_file_path`; the store today reads 2 and 361.)

**Is `reached_through` achievable, or does it relocate the refusals?** As specified it is not
achievable at all: it needs a `target_spec` of the form `<module>:<callable>`, and **no AC field
names a callable** — `declared_files` and `reference_file_path` both name files. That recommendation
would hand the runner a file path where it expects a qualified name, reproducing the empty-string
bug in a new spelling. C2 is the repair: derive the target set from the *run*, every frame in the
declared unit's module, rather than from a field that does not exist. On relocation: C2 moves none
of the 136, it removes the false accept. The only refusals it withdraws are those where the judged
unit was never entered — §2's last row.

**What happens to the 49?** C1-C4 all leave them refused `observation_unavailable`; their cause is
the runner's execution model, not the AC. C5 is the only answer. Until it lands those 49 hold a
refusal with no clearing action, exactly what BO-2900e-1 ("the one action that clears it") says a
refusal may not be — so C5 is the condition under which the family is self-consistent, not polish.

## 5. Durability: what stops each one recurring

The class to design against is not "this predicate was wrong". It is **a required gate whose real
behaviour is set by something nobody declared** — an argument spelling, an alphabetical sort, an
empty string. Four mechanisms, one per element.

**A required gate must report its own population, and zero must fail.** `check_done_proof.py` prints
the resolved unit-exclusion root and the count of ACs the reachability conditions actually judged;
CI fails when that count is zero. One mechanism, three defects: C1's fail-open, C3's inertness
risk, and the `_DEFAULT_TEST_ROOT = ""` divergence between callers all present identically today as
a green gate that examined nothing. It generalises past this gate; it is the most valuable line here.

**A permanent adversarial fixture pair, asserted in one run.** The ritual and honest probes of §2
belong in `unit_tests/ac_store/` as two assertions in one test, so any future predicate that
accepts the ritual fails CI. BO-2900a-1's own `test_spec` asked for that pairing ("asserted in the
same run so a reject-everything implementation cannot pass"); the shipped tests carry no ritual
case. Cheapest durable item on this list.

**The anti-ritual property, stated so it can be enforced.** BO-2900a-3's clause — "adding another
passing test must be incapable of changing the verdict" — is written about a-3's own condition set,
and a-1 cannot adopt it verbatim: a-1's criteria *require* test-sensitivity ("the same criterion
becomes eligible once a proof test drives the same behaviour"). What a-1 can hold is what its
`for test in py_linked` loop already gives it — it refuses if **any** linked test fails, so adding
a test can only create a refusal, never clear one. Write that quantifier into the AC as a
constraint; the remaining exposure, intra-test ritual, is what C2 closes.

**Scope grows by declaration, not by guess.** Once C3 lands, require `declared_files` on any record
flipped to `done` (`check_ac_schema` already calls `declared_files_commit_messages`). Scope then
ratchets with adoption and can never again be set by `sorted()` over a test's imports.

## 6. Measure these five things first

1. **The honest refused count.** Re-run the sibling's sweep with its stated precondition
   established per AC (all linked tests actually passing); 185 is an upper bound and nobody knows
   the lower one. *Under about thirty: drop C3's staging, take C1+C2 to full scope at once.*
2. **How many of the 136 flip under C2.** Run the §2 prototype over the in-scope 188. Prediction:
   near zero become eligible, and a meaningful number return *no verdict* because the resolved unit
   is never entered. *If a material fraction flips, C2 may suffice alone and C3 waits.*
3. **How much of the wrong-unit class C2 kills for free** — the count of the 188 whose tests never
   enter the resolved unit. *If it is most of the 29-of-54, C3 can ship without the fallback.*
4. **Per-observation latency under a pytest-hosted runner**, p50 and p95, against `timeout=30`.
   *If p50 exceeds the budget, C5 must be per-file rather than per-function.*
5. **Whether the 3 currently-passing ACs survive C2.** A remedy that refuses
   `test_bo2400f_7_cli_proof.py` — the one test in the corpus that is the shape BO-2900a-1 asks for
   — is disproved on the spot.

The PO/BA pass has four criteria to write, none authored here: an L2 on the gate reporting its
judged population with zero as a failure; an L2 on resolving the unit from the record and issuing
no verdict when none is declared; an L3 (`-i`) on the ritual/honest fixture pair asserted in one
run; an L2 on the observation running in the same host as the suite it re-executes. Note also that
BO-2900a-2 — the AC specifying the run observation this gate consumes — is still `work_status:
todo` while the gate that consumes it is done and required. Fix that inversion in the same pass.

---

*MEASURED claims were derived on 2026-09-29 in
`/home/henzeh/projects/leafcutter/worktrees/ki-guardrail-findings`, branch
`analysis/entry-point-gate`: field counts by parsing all 4,456 AC records; the predicate table by
running the real `_observe_reachability` and a prototype profiler against a four-shape fixture
under `/tmp`; the `_is_within` asymmetry and the call-site/mode facts by reading `done_proof.py`,
`_done_proof_entry_point_gate.py`, `check_done_proof.py` and `commit_guardian.json`. No repository
file but this one was touched; no acceptance criterion was authored or amended.*
