---
title: "Reference: False-Green Mechanisms"
description: "Catalogue of the recurring mechanisms by which a green test, hook, or gate in this repo can pass while the work it certifies is not actually done."
type: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - ac_store
  - build_orchestration
  - build_pipeline
  - commit_guardian
  - injection_builder
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/ac-store.md
  - docs/known-issues/testing-quality.md
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/documentation-system.md
  - docs/how-to/prove-ac-done.md
  - docs/how-to/done-proof-enforcement.md
  - docs/how-to/real-artifact-fixtures.md
  - docs/reference/fixture-policy.md
  - docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900g-8.yaml
  - CLAUDE.md
---

# False-Green Mechanisms

Recurring, cross-component patterns by which a passing check in this repo carries no
information about whether the certified work actually happened. Each entry has a stable
id (`M1`..`M8`) for citing in commit messages, review comments, and other docs.

---

## Related surfaces

Three neighbouring surfaces exist. Route to the right one:

| Question | Surface |
|---|---|
| A specific thing is broken right now, in one component | `docs/known-issues/<component>.md` — deleted once the fix lands. |
| A rule to follow going forward, with its own war story | `CLAUDE.md` → "Implementation Conventions" — normative, authoritative. |
| How does a green check lie here, as a durable pattern | This document — cross-component, stays true after any one defect above is fixed. |
| How do I make a done AC provably done | `docs/how-to/prove-ac-done.md`, `docs/how-to/done-proof-enforcement.md`, `docs/how-to/real-artifact-fixtures.md` — the inverse: how to earn a green that means something. |

Specific-defect registers this catalogue draws examples from:
[`ac-store`](../known-issues/ac-store.md) (M5, M8), [`build-orchestration`](../known-issues/build-orchestration.md) (M7),
[`commit-guardian`](../known-issues/commit-guardian.md) (M3), [`testing-quality`](../known-issues/testing-quality.md) (M6),
[`documentation-system`](../known-issues/documentation-system.md) (adjacent, no mechanism here).

---

## Summary

| ID | Tell | What defeats it |
|---|---|---|
| [M1](#m1--structural-grep-only-tests-pass-on-dead-code) | A test asserts a string is present in source, not that it runs. | Execute the behavior, or assert the result is consumed in control flow. |
| [M2](#m2--a-hooks-dependency-missing-from-the-build-deploy-manifest) | Unit tests import from the source tree and pass; the deployed hook crashes. | Run the deployed hook, not just the unit tests. |
| [M3](#m3--ac-store-hooks-see-the-git-index-not-the-store) | A fact is true of the store but the hook only ever sees the staged files. | Stage the parent alongside the child; validate the store out of band (see M5). |
| [M4](#m4--synthetic-fixtures-reproduce-the-authors-bias) | A hand-typed fixture matches the author's mental model, not the real serializer's output. | Feed the real on-disk artifact, in a fresh process. |
| [M5](#m5--a-validator-that-silently-validates-nothing-on-the-wrong-argument-shape) | A bare directory (or a fixed-depth glob) yields a success-shaped, zero-content result. | Pass files via `find -exec`; confirm a non-zero file count before trusting the exit code. |
| [M6](#m6--a-scorer-that-treats-no-answer-as-an-answer) | An eval's score floor is not zero — an empty prediction still matches every all-negative gold row. | Compute the all-negative baseline and require the threshold above it; treat parse errors as unscored. |
| [M7](#m7--a-module-invoked-as-a-cli-that-has-no-cli) | The path resolves, the subprocess exits 0, nothing happens. | A test that executes the command and asserts an observable effect. |
| [M8](#m8--a-check-that-measures-a-proxy-and-reports-it-as-a-verdict) | The check's name describes a property; its assertion measures a count. | Compare against an independent source; a check that cannot assess correctness reports `INFO`, not `PASS`. |

---

## M1 — Structural (grep-only) tests pass on dead code

A test that asserts a string is present in a source file cannot distinguish "the gate
is wired and runs" from "the gate string is defined and ignored." Normative rule and
full incident: `CLAUDE.md` → "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" —
`fast-lane-build.js` passed its structural tests while never executing its red/green
gates, and `fast_lane.py` had no CLI so the runner's call was a silent no-op.

**Sub-variant — the structural test's own regex can be blind.** A regex matching only
`outcome\s*\(\s*['"]` does not see a backtick template-literal call, so it stays green
on the buggy double-recording code. Normative rule: `CLAUDE.md` → "Skip-Branch
Side-Effects — Conditionalize, Don't Add (+ tests must see all quote styles)". Verified
live in `unit_tests/workflows/test_bo_1000b_1_i.py:561-563`:

```python
step_label_pattern = re.compile(
    r"\boutcome\s*\(\s*['\"]([^'\"]+)['\"]"
)
```

The character class still today matches only single- and double-quoted first
arguments — no backtick alternative — so it remains blind to `outcome(\`...\`)`.

**Defeats it:** execute the behavior, or assert the result is consumed in control flow.

---

## M2 — A hook's dependency missing from the build deploy-manifest

Unit tests import from the source tree and pass; the deployed hook raises
`ModuleNotFoundError` at runtime because the module was never added to the manifest
that copies files into the deployed layout.

Manifest: `deploy_map` at `scripts/build_phases.py:851`, consumed at `:878`. The
`done_proof.py` entry (`:860`) carries its own warning: *"it MUST deploy or the
(required) CI done-proof check crashes with ModuleNotFoundError."* Confirmed present in
the manifest and on disk today.

Normative rule and incident narrative: `CLAUDE.md` → "New Hook / Gate Dependencies Must
Be in the Build Deploy-Manifest".

**Defeats it:** run the deployed hook, not just the unit tests that mask the gap.

**Update — BP-900g-8 (2026-08-25) closes the statically-resolvable half of this gap
mechanically.** The prior defeat ("run the deployed hook") depended on a human
remembering to do it — the `CLAUDE.md` rule was written down after the `done_proof.py`
incident and a fourth instance (`generate_ticket_from_ac.py` resolving its undeployed
sibling `_component_migration_map.py`) still shipped anyway. `build.py` now runs
`_check_intra_package_closure_guard()` before `_run_phases()` writes any output: for
every script the build will deploy it computes the DERIVED, TRANSITIVE closure of the
intra-package modules that script actually resolves —
`build_referential_integrity.compute_intra_package_closure()`, AST-based static analysis
of imports, relative imports, and `importlib.util.spec_from_file_location` dynamic
loads, never a hand-maintained list — and fails the build, naming the deployed script,
the missing dependency, and the deploy phase that would have to carry it, when the
deploy declaration (`build_phases.AC_STORE_DEPLOY_MAP`) does not contain it. A module a
deployed script starts importing tomorrow is caught on the next build without anyone
editing a list.

This does not retire the "run the deployed hook" defeat, it narrows what it is still
needed for: a dynamic loader that builds a module path from a runtime value is a
declared static-analysis blind spot (`compute_intra_package_closure` logs it as an
unresolvable reference for a human, rather than silently assuming it is external), so a
manual deployed-hook run remains the fallback for that residual case. Verified via a
deployed-tree subprocess harness (`unit_tests/test_bp_900g_8.py`): a positive/negative
control pair runs `python scripts/build.py --target-dir <tmp>` as a real subprocess,
withholding one intra-package dependency from the deploy declaration and asserting the
build blocks, then re-running unmodified and asserting it exits zero — the check
performed against the source tree alone cannot distinguish these, because the source
tree contains every module by construction.

---

## M3 — AC-store hooks see the git index, not the store

The commit-guardian AC hooks validate only the files present in that commit's index.
Anything true of the **store** but not of the **staged set** is structurally
unreachable — you edit children, never stage the parent, and the hook that exists to
check the parent never receives it.

Normative rule and incident narrative: `CLAUDE.md` → "AC-store commits — stage the
parent alongside the child". `ACD-400a` carried both failure shapes at once: `covered_by`
listed `[a-1, a-2]` while `a-3`/`a-4` had existed on disk since 2026-08-12, and it claimed
`work_status: done` while `a-1`/`a-2` were both still `todo`. Every commit in that window
passed every AC hook; both surfaced only once the parent was incidentally staged. A
store-wide sweep of 3,146 records found **20** composites marked `done` with at least
one unfinished child. Related trap: several of these hooks ignore `argv` entirely and
read the index or `HOOK_TEST_FILES`. Open defect:
[`docs/known-issues/commit-guardian.md`](../known-issues/commit-guardian.md) → KI-CG-001.

**Defeats it:** stage the parent alongside the child; run store-wide validation out of
band (see [M5](#m5--a-validator-that-silently-validates-nothing-on-the-wrong-argument-shape)
for the trap in doing that).

---

## M4 — Synthetic fixtures reproduce the author's bias

A hand-typed fixture encodes what the author thinks the artifact looks like, not what
the real serializer writes. Rule, rationale, and allowed/rejected fixture forms:
`docs/reference/fixture-policy.md`; task guide: `docs/how-to/real-artifact-fixtures.md`.
Normative rule: `CLAUDE.md` → "Real-artifact behavioral spot-check before declaring
done".

The `files_touched` parser (EPIC-PhantomDoneFilesTouched, 2026-07-07) required
list-item dashes at column 0 — standard `yaml.safe_dump` output — but every hand-typed
test fixture used two-space-indented dashes, matching the author's mental model of YAML.
Seven tickets signed off green while the hook was a complete no-op on every real ticket.
Even the first remediation spot-check reused indented fixtures and missed it.

**Defeats it:** feed the real on-disk artifact, in a fresh process.

---

## M5 — A validator that silently validates nothing on the wrong argument shape

`scripts/ac_store/validate_ac_schema.py` takes file paths and does no globbing of its
own. Given a bare directory it prints the message at `:333` and exits 0. Verified today:

```text
$ python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/testing-quality/
No YAML files to validate.
$ echo "exit: $?"
exit: 0
```

```text
$ find docs/acceptance-criteria/testing-quality -name "*.yaml" -exec \
    python scripts/ac_store/validate_ac_schema.py {} +
AC schema validation FAILED:
  .../TQ-300b-1.yaml: Field 'documentation_triggers' is permitted only on L1 ACs. AC TQ-300b-1 has level 'L2'.
  ...
$ echo "exit: $?"
exit: 1
```

(Annotation, not tool output: 109 files were checked, counted separately via
`find ... | wc -l`. The tool prints no file count of its own — part of the problem.)

The same bare-directory form is a success-shaped, zero-content result: it reports the
same exit code as a real pass while checking nothing. A fixed-depth shell glob
(`*/*.yaml`) is not a safe substitute either — AC YAML sits at more than one directory
depth, some files directly under `docs/acceptance-criteria/`, so a fixed-depth pattern
silently skips whole directories: the same failure in a smaller costume.

Normative rule: `CLAUDE.md` → "AC-store hygiene — bulk pre-flight before a
finalization drive". That section itself prescribed the bare-directory form from
2026-08-10 until it was corrected on 2026-08-18 — the repo's own documented defence
against store rot was a no-op for over a week. Open defect:
[`docs/known-issues/ac-store.md`](../known-issues/ac-store.md) → KI-ACS-001.

**Defeats it:** pass files via `find <dir> -name "*.yaml" -exec ... {} +`, never a bare
directory or a fixed-depth glob; confirm the tool reports a non-zero file count before
believing a pass.

---

## M6 — A scorer that treats "no answer" as an answer

`scripts/evals/run_agent_eval.py:1415-1422` catches `ModelInvocationError` (raised on
any subprocess or output-parse failure) and sets `predicted = {}` rather than marking
the row unscored:

```python
try:
    reply = _dispatch(backend, system_prompt, user_input, model, timeout)
    raw = extract_json_object(reply)
    predicted = _extract_labels(raw, response_label_field)
except ModelInvocationError as exc:
    logger.warning("Row %s: model invocation/parse failed: %s", row_id, exc)
    predicted = {}
    parse_error = str(exc)
```

An empty prediction scores as all-axes-`False`, which is a *correct* answer for any
gold row whose labels are all `False`. The eval's floor is therefore not zero — it is
the gold set's all-negative fraction. Verified directly: the `pt-classifier` eval set
(`docs/product-truth/classifier/eval.jsonl`, wired at
`scripts/evals/agent_eval_config.json:6`) has 18 rows, 4 of which are all-negative
across its three label axes (`needs_flow`, `needs_mock_data`, `needs_mockup`) —
4/18 = 22.22%. A completely dead agent (for example, a run with no
`ANTHROPIC_API_KEY`) does not score zero on this set; it scores 22.22%, a number that
reads as a quality result but is an infrastructure failure (KI-TQ-002, below).

The mechanism also fires inside a run that **passes**. A captured `pt-classifier` run
logged:

```text
WARNING run_agent_eval: Row clf-012: model invocation/parse failed: No JSON object found in model reply
WARNING run_agent_eval: Row clf-014: model invocation/parse failed: No JSON object found in model reply
...
  [PASS] clf-012  outcome[ok] exp=none got=none
  [PASS] clf-014  outcome[ok] exp=none got=none
...
  rows=18 passed=16 accuracy=88.89%
  GATE: PASS — score 88.89% >= threshold 70.00%
```

Rows `clf-012`/`clf-014` never received a model answer; the empty prediction matched a
`none` gold row on both. Two of the sixteen recorded "passes" had no answer behind them —
the honest figure is 14 correct out of 16 rows actually answered, inside a run whose gate
reported `PASS`.

**Defeats it:** compute the all-negative baseline for the gold set and require the pass
threshold to sit above it; treat any `parse_error` row as unscored rather than as a
prediction. Open defects:
[`docs/known-issues/testing-quality.md`](../known-issues/testing-quality.md) →
KI-TQ-001 (this mechanism) and KI-TQ-002 (the CI consequence: a credential-less run
reports as a 22.22% quality score rather than an infrastructure failure).

---

## M7 — A module invoked as a CLI that has no CLI

The path resolves, the subprocess exits 0, and nothing happens. Verified today:
`templates/workflows-js/fast-lane-build.js:121` calls

```
python3 <worktree>/scripts/injection_builders.py assemble_context_bundle
```

`scripts/injection_builders.py` has zero occurrences of `argparse` and no `__main__`
block. Recorded as an open defect:
[`docs/known-issues/build-orchestration.md`](../known-issues/build-orchestration.md) →
KI-BO-005 — noted there as *"verbatim the failure class `CLAUDE.md` already
documents"*: the original `fast_lane.py` incident (M1) was both a grep-only-test failure
and a no-CLI failure at once; this is the same no-CLI failure recurring on a different
module, because it had no catalogue entry to be looked up in — the reason this document
exists.

**Defeats it:** a test that actually executes the command and asserts an observable
effect.

---

## M8 — A check that measures a proxy and reports it as a verdict

Distinct from [M5](#m5--a-validator-that-silently-validates-nothing-on-the-wrong-argument-shape):
in M5 the tool validates **nothing**. In M8 the tool validates **something**, but a
countable proxy rather than the property its label names, and still reports `PASS`.

`scripts/ac_store/generate_ticket_from_ac.py --verify` includes a check labelled
`files_touched has N path(s) from doc_links`, whose assertion is `N > 0`. Verified today
against `BO-2400g-2` on `main`:

```text
$ python scripts/ac_store/generate_ticket_from_ac.py --ac BO-2400g-2 --verify
=== Ticket readiness report for BO-2400g-2: READY ===
  [PASS] files_touched has 4 path(s) from doc_links
```

The four derived paths omit the file this AC exists to change
(`templates/workflows-js/fast-lane-ship.js`), include a file the AC's own criteria
explicitly forbid touching (`change-scope-reviewer.md`), and mislabel provenance —
`scripts/build.py` came from the prose fallback, not a `doc_link`. None of that affects
the count, so the check reports `PASS` and the report concludes `READY`.

**Tell:** the check's name describes a property (surface correctness); its assertion
measures a count (surface non-emptiness). Open defect:
[`docs/known-issues/ac-store.md`](../known-issues/ac-store.md) → KI-ACS-002.

**Defeats it:** compare the derived surface against an independent source (the AC's own
`doc_links` and `out_of_scope`, not the check's own derivation of them); a check that
cannot assess correctness should report `INFO`, not `PASS`.

---

## See Also

- [Known issues — build-orchestration](../known-issues/build-orchestration.md) — KI-BO-005 (M7).
- [Known issues — ac-store](../known-issues/ac-store.md) — KI-ACS-001 (M5), KI-ACS-002 (M8).
- [Known issues — testing-quality](../known-issues/testing-quality.md) — KI-TQ-001, KI-TQ-002 (M6).
- [Known issues — commit-guardian](../known-issues/commit-guardian.md) — KI-CG-001 (M3).
- [Known issues — documentation-system](../known-issues/documentation-system.md) — adjacent, no mechanism here.
- [How to prove an AC is done with a passing covers-linked test](../how-to/prove-ac-done.md) —
  the inverse task guide: how to earn a green that means something.
- [How to understand proof-of-done enforcement](../how-to/done-proof-enforcement.md) —
  the two-layer pre-commit / CI enforcement this catalogue's mechanisms try to slip past.
- [How to author real-artifact fixtures and round-trip tests](../how-to/real-artifact-fixtures.md) /
  [Fixture Authenticity Policy](fixture-policy.md) — task guide and rule set for M4.
- `CLAUDE.md` → "Implementation Conventions" — normative rules and war stories for M1-M4.
- `scripts/ac_store/validate_ac_schema.py` (M5), `scripts/evals/run_agent_eval.py` (M6),
  `templates/workflows-js/fast-lane-build.js` + `scripts/injection_builders.py` (M7),
  `scripts/ac_store/generate_ticket_from_ac.py` (M8) — implementations referenced above.
- [`BP-900g-8`](../acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900g-8.yaml) —
  the AC that closed the statically-resolvable half of M2 mechanically;
  `scripts/build_referential_integrity.py` (`compute_intra_package_closure`,
  `find_uncovered_closure_dependencies`) and `scripts/build.py`
  (`_check_intra_package_closure_guard`) are the implementation.
