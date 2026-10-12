---
title: "The entry-point gate: the scoping question is premature, because the instrument cannot see the repository's own mandated proof shape"
description: "Two rounds of architectural, procedural and deterministic analysis. Round 1 converged on scoping by criterion kind. Round 2 dissolved that conclusion: both candidate declaration fields were abandoned by the lenses that proposed them, the 185-AC migration was withdrawn as ~15, and 164 ticket files were found mandating a subprocess proof shape that an in-process profiler structurally cannot observe. The recommendation is to demote the gate to report-only now, fix the observer, and defer the scoping choice — which may turn out to be unnecessary."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - ac_store
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/analysis/2026-09-29-the-entry-point-gate-refuses-the-proof-it-wants-and-accepts-the-one-it-does-not.md
  - docs/analysis/2026-09-29-the-entry-point-gate-refuses-the-proof-it-wants-and-accepts-the-one-it-does-not-2-remedies.md
  - docs/known-issues/ac-store/open-low-ki-acs-20260928-entry-point-gate-demands-cli-traversal-from-every-proof.md
---

# The entry-point gate: the scoping question is premature

Three lenses — architectural, procedural, deterministic — were run independently on one
question: should `BO-2900a-1`'s gate be scoped by **code shape** ("your code sits in a unit
with a `main`") or by **criterion kind** ("your criterion is about the command surface")?

Round 1 converged on criterion kind. A second, adversarial round — each lens handed only the
counter-evidence bearing on its own position — **dissolved that conclusion rather than
confirming it**. This document records the resulting recommendation and, as carefully as it
can, what each lens gave up.

## Recommendation

**Demote the gate to report-only now. Fix the observer. Defer the scoping choice, which may
prove unnecessary.**

Choosing a scope today means choosing it on numbers that are artifacts of a blind instrument.

## Why the question is premature

`scripts/ac_store/_gtfa_constants.py:68` stamps this instruction onto every derived
reachability descriptor:

> REQUIRED — invoke the production entry point (CLI, hook, slash command, workflow dispatch,
> or `main()`) **as a subprocess/dispatch** and assert the new behaviour actually occurs.
> **Do NOT satisfy this by importing the function directly.**

**164 ticket files in this repository currently carry that instruction** (MEASURED). The
gate's observer installs `sys.setprofile` in its own process (`done_proof.py:516`), and a
profiler cannot see frames in a child process.

So the repo mandates a proof shape its required gate cannot observe, and forbids the only
shape it can. That is not a scoping problem. Any rule quantifying over "which frames did the
proof enter" is quantifying over a set that systematically excludes the repo's own standard.

Three `readiness: approved` records in the same family (`BO-2900g-1`, `-g-2`, `-g-4`) mandate
the subprocess shape in their own `test_spec` while sitting `work_status: todo` — approved,
queued work specified in a shape its sibling's required gate cannot see.

## What both candidate fields turned out to be

Both were abandoned by the lens that proposed them.

**`test_spec[].angle: reachability`** (architectural's proposal) — conceded. 3,348 of 4,891
covers-tagged functions (68.5%) carry no `# angle:` tag, and
`templates/scripts/commit_guardian/check_test_ac_tags.py` contains no `angle` handling at
all. The decisive objection was not sparsity but **self-selection**: an unenforced
declaration makes the gate opt-in, so it bites conscientious authors and exempts everyone
else. Sparse-but-random would have been tolerable; opt-in is an incentive inversion.

One correction to the record: the "dirty vocabulary" finding applies to the **in-test
comment**, not the store field. `test_spec[].angle` is a JSON Schema `enum`
(`config/ac_store_schema.json:422`) rejected at authoring time. The scanner that reported
`'{angle}\n"'` was loose; the store is not dirty. The right move is to *enforce* the tag on
the test side, not to clean the store.

**`it_requirements.reference_file_path`** (deterministic's proposal) — conceded, on a reading
of the schema it had not made. `ac_store_schema.json:357` defines it as:

> Path (relative to repo root) to **the file that must be modified for registration**.

A registration edit-surface, not the unit under proof. It carries a `.py` value on **11.9% of
done ACs**, and 112 of the 234 done ACs using the object form name a non-`.py` file — a JSON
manifest has no runtime way in for an ancestry predicate to judge. The residual population is
therefore **mis-declaration, not aspiration**: the ACs are built and proven, the field points
elsewhere. That matters because the clearing action becomes "correct the record", which
`BO-2900e-1:81` names and forbids — *"never as something they do to the guard or to the AC
record."*

Deterministic also applied architectural's own principle — *never gate on a field whose only
reader is the gate* — back at it correctly. Checked: `surface_invoked` has **zero code
readers** across `scripts/` and `templates/`; `reference_file_path` has two, one of them the
ticket generator rather than a gate. The principle disqualifies the wrong field from the one
it was raised against. And `BP-1100g-2`, cited as the consumer establishing multi-reader
standing, is `work_status: todo` and states in its own text that the key it reads has "ZERO
code readers today… no forcing function."

## The correction that matters most

An earlier draft of this analysis, and my own relay of it, said today's gate **refuses** the
subprocess population. That is wrong, and the error mattered because it merged two
populations with opposite failure modes.

Verified by executing `_detect_module_entry_point` against real proof files:

| proof file | outcome |
|---|---|
| `unit_tests/ac_store/test_bo_2900g_3.py` (pure subprocess CLI proof) | **NO VERDICT — scope-fenced, passes silently** |
| `unit_tests/commit_guardian/test_bp_100n_1.py` (pure subprocess CLI proof) | **NO VERDICT — passes silently** |
| `unit_tests/ac_store/test_components_enforcement.py` | judged against `backfill_components:main` — **not its unit** |

A pure spawn-only proof imports nothing local, so no entry point resolves and the gate passes
it. Only the **hybrid** shape — imports the module *and* spawns it — is refused.

So the subprocess population splits in two, and the halves need opposite fixes:

- **Silent passes** (pure spawn) — a phantom-done vector: the gate's own scope fence hands
  them to `BO-2900a-3`, which fires for **0 of 802** done ACs under either `--test-root`
  spelling. Nothing judges them.
- **False refusals** (hybrid) — told they "reached the code by direct import" when they ran
  the real CLI.

## What the numbers actually are

Round 1's headline was withdrawn by the lens that produced it.

| claim | round 1 | round 2 (measured) |
|---|---|---|
| ACs needing test rewrites | 185 | **~15 in actual scope**, of 160 candidates with a `.py` impl and a `.py` proof |
| the migration's completability | "decisive — not completable" | **argument withdrawn**; this is instrument engineering, not migration |
| cost allocation | "falls on uninvolved authors" | **largely conceded** — the CI job is diff-scoped (`ci.yml:275`) |

145 of the 160 candidates are scope-fenced out because no linked unit defines a module-level
`main`. The gate's scope is set by the accident of a proof's import list.

What survives of the procedural case is narrower and better evidenced than what it replaced:
the gate trains the wrong clearing action, and it is **wrong about which module is under
proof**. Live against the real store, `KM-KGS-100e-1` (`work_status: done`,
`implemented_by: scripts/ac_store/_ac_components.py`) is refused with:

> the proof … reached the code by direct import instead of through `backfill_components:main`

The clearing action that message trains is *make your test call an unrelated module's
`main`*.

## One dispute remains open

The **quantifier**. Deterministic holds the universal law `R ≠ ∅ ∧ R ⊆ Rt` — eligible only if
some proof reached the declared unit through its entry point and **no** covers-tagged proof
reached it any other way. Architectural rebuts it structurally, and the rebuttal has not yet
been answered:

- The ritual is *already* unrepresentable without the universal. `done_proof.py:485` sets
  `_reached_through` only when the entry point is a **live ancestor** on the same call stack,
  never as two independent booleans. The universal buys nothing on the ritual.
- `ac_store_schema.json:423` documents that the criteria-derived fallback "tags its own
  descriptors 'criterion' and appends one mandatory 'reachability' descriptor". So a generated
  AC carries criterion-angle tests **plus** one reachability test: `R ⊄ Rt` **by
  construction**. The universal would refuse every AC this repo's own ticket generator emits.

That objection was not put to the deterministic lens in round 2 — an omission in how the
round was designed, not a concession by either side. **The quantifier should be treated as
unresolved**, and resolving it needs one more exchange, not a decision taken here.

## What the observer fix looks like

Deterministic built and measured it rather than arguing for it: a `PYTHONPATH`-injected
`sitecustomize` shim carrying the *same* ancestry profiler, plus a `subprocess.Popen` audit
hook to count spawns, plus an env-merge patch for tests that replace the environment wholesale.

Measured discrimination over seven proof shapes — the load-bearing row is the third:

| shape | verdict |
|---|---|
| `subprocess.run([sys.executable, hook, args])` — gold standard | PASS |
| direct import in-process | REFUSE |
| **child that spawns but bypasses `main`, exit 0** | **REFUSE** |
| child launched with `-S`, or a non-Python child | observation unavailable |
| child with wholly replaced `env`; grandchild two levels deep | PASS |

That third row is why the cheap alternative — parse argv, accept a zero exit — fails: it
passes a real defect. Five consecutive runs produced byte-identical output.

Named ship blockers: **profiler eviction** (a child that installs its own tracer silently
evicts the shim, and the record then reads as a refusal rather than as unavailable — must be
detected in `atexit` and downgraded), and `sitecustomize` chaining (a naive chain recursed 245
times in the prototype). Genuine coverage ceiling: non-Python children and `-S`/`-E`/`-I`,
both of which degrade to *unavailable* rather than to a false refusal.

Note that `BO-2900a-2` — `work_status: todo`, the observation contract this gate declares it
consumes — already specifies the correct architecture at line 64: *"call it from
done_proof.py's existing pytest-invocation path … do not add a second pytest run per AC."*
`11b92057` shipped a second bespoke non-pytest runner instead. The 47% fixture-argument
failure rate is the foreseeable consequence.

## Sequencing

From the lens that owns it, and the other two deferred to it:

1. **Demote to report-only, today, in its own commit.** One line. It stops a verified false
   refusal on the real store and costs no migration. Do not sequence this behind an
   investigation.
2. **The required-gate approval rule second, not last** — because the observer rebuild is
   precisely the commit it should govern. Shipping the fix last would land it under the same
   absent discipline that produced the defect.
3. **Observer fix third**, re-hosted per `BO-2900a-2`'s own constraint and taught the process
   tree.
4. **Scoping last, and possibly not at all.** If the observer is honest, criterion-kind
   scoping may be unnecessary.

Two cheap rules worth adopting alongside:

- **A refusal must name a unit drawn from the AC's own `implemented_by`.** Costs nothing;
  kills the `backfill_components` misattribution outright.
- **A required check may not ship a refusal path until it demonstrates, over a corpus sampled
  from proof files already in `covered_by`, that it can execute each shape and return a
  correct verdict** — shipping report-only until that corpus is green, and mapping any shape
  it cannot observe to *no verdict*, never to a refusal. The corpus is already enumerable: 862
  covers-tagged functions in four shapes (unittest method no-args 698, module func with
  fixture args 91, unittest method with fixture args 38, module func no-args 35), plus the
  subprocess-CLI shape.

## Provenance

Verified independently for this document: `_gtfa_constants.py:68` and the 164 ticket files
carrying it; `_detect_module_entry_point` returning `None` for two pure-subprocess proofs and
`backfill_components:main` for the misattribution case; `reference_file_path`'s schema
definition; zero code readers for `surface_invoked`; `_ANGLE_TAG_RE` at `done_proof.py:260`;
`BO-2900a-1` at `readiness: reviewed` against `BO-2900g-3` at `approved`; `BO-2900a-1`'s
`expects_from` naming `reached_through` from the `todo` `BO-2900a-2`.

Carried from the lens reports and not re-derived: the full-store sweeps, the seven-shape
prototype matrix, the `a-3` zero-fire measurement, the 47% and 15% fixture-argument samples
(different denominators, both unresolved), and the 862-function shape census.

Two figures remain unreconciled between lenses and should not be quoted without a denominator:
the declared-`.py` population (122 by one sweep, 334 by another using a wider definition) and
the fixture-argument share (47% of an in-scope sample versus 15% of all covers-tagged
functions). The 17 spawn-only count was reproduced exactly by two independent sweeps.

One round-1 claim did not reproduce: that the observation verdict changes with the invoking
directory. Re-run against `test_done_proof_composite` from three directories, the verdict was
identical each time. It is therefore test-dependent rather than a universal property, which
narrows it without refuting the original measurement.
