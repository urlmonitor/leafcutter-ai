---
title: "How to understand the done-proof reachability axes (BO-2900a-1 and BO-2900a-3)"
description: "The two mechanical reachability axes verify_done_eligible evaluates after the incumbent BO-2500a-3 pass/fail rule already returned eligible: True — the third eligibility axis (BO-2900a-1) that refuses a proof reaching the code by direct import when the unit has a real way in, and the sibling no-entry-point-anywhere axis (BO-2900a-3) that refuses a unit no way of running the product can reach at all, however many tests pass."
type: how-to
category: how-to
status: active
created: 2026-09-27
last_updated: 2026-09-27
components:
  - build_orchestration
  - commit_guardian
  - ac_store
related_docs:
  - docs/how-to/done-proof-enforcement.md
  - docs/architecture/diagrams/c3-done-proof-reachability-gates-sequence.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml
  - docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md
---

# How to understand the done-proof reachability axes (BO-2900a-1 and BO-2900a-3)

> **Parent document:** [done-proof-enforcement.md](done-proof-enforcement.md)

This guide continues from
[done-proof-enforcement.md, section 2](done-proof-enforcement.md#2-the-ci-gate),
which covers the incumbent `BO-2500a-3` pass/fail rule: a covers-tagged test
exists, and it passes. The two sections below cover the two mechanical
conditions `verify_done_eligible` (`scripts/ac_store/done_proof.py`) evaluates
**after** that pass/fail rule already returned `eligible: True` — they never
change the "no linked test" or "linked test failed" verdicts documented in the
parent guide.

---

## 3. The third eligibility axis: did the proof go in through the real way in? (BO-2900a-1)

The incumbent rule ([BO-2500a-3](../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-3.yaml))
asks nothing about *what the test actually reached* while it ran. A test that
imports the implementing function directly and calls it satisfies BO-2500a-3
just as well as a test that drives the same behaviour through the product's
real command surface — even though only the second kind of test proves an
operator can actually reach the fix.

`verify_done_eligible` (`scripts/ac_store/done_proof.py`) closes that gap with a
**third, mechanical condition**, evaluated only after both of the BO-2500a-3
conditions already passed — it never changes the existing "no linked test" or
"linked test failed" messages:

1. **Does the unit expose a runtime way in?** For each of the AC's linked Python
   tests, `_detect_module_entry_point(test_file, project_root, test_root)`
   (`scripts/ac_store/_done_proof_entry_point_gate.py`) looks by AST alone for a
   module-level `def main` (or `async def main`) — the same surface
   `python <module> <action> ...` would reach — checked in two places, in order:
   (1) the covers-tagged test's *own* module (this AC family's single-file fixture
   convention), then (2) each bare module that test's file imports, resolved the
   SAME way the sibling no-entry-point-anywhere rule resolves candidate units
   (`_local_import_module_names` / `_resolve_candidate_unit`, both in
   `scripts/ac_store/done_proof.py`) — the codebase's normal separate
   test/implementation layout (e.g. `fast_lane.main`,
   `scripts/build_orchestration/fast_lane.py:925`), which a same-file-only check
   would never catch. This is a structural check only: a filename that looks like a
   CLI, a docstring that mentions one, or an `if __name__ == "__main__":` block with
   no real `main` function are all ignored. No `main` found in the test's own module
   or in any module it imports means this rule does not apply at all — see the scope
   fence below.

2. **Did the test's own run enter it?** When a `main` is found (in the test's own
   module, or in the first of its imports that has one — the *resolved module*),
   `_observe_reachability` re-executes the covers-tagged test in a fresh subprocess
   under a call-stack profiler and records whether `main` was ever entered during
   that run, and whether that isolated re-run itself passed. This is an
   **execution-derived observation, never a read of the test's source text** —
   a test can `import module; module.main` in its own body without ever calling
   it, and a text-based check would miss that.

3. **Verdict.**
   - `main` entered during the test's own run → the existing `eligible: True`
     verdict is returned unchanged.
   - `main` exists but was never entered (and the isolated re-run did pass) →
     `eligible: False`, `refusal_cause: "proof_not_through_entry_point"`, and the
     verdict names the `unit` (the *resolved module* — the implementing module's
     own name when the cross-file branch fired, not always the test file), the
     `entry_point` (`"<resolved module>:main"`) that was never entered, and the
     `offending_test` (`"<file>::<function>"`) that reached the code by direct
     import instead.
   - The observation subprocess itself could not be run, produced no parseable
     result, **or its isolated re-run did not pass** → `eligible: False`,
     `refusal_cause: "observation_unavailable"`. The `passed` check exists because
     the bare re-execution bypasses the pytest fixtures/conftest/parametrize
     machinery the original, already-passing pytest run used — an isolated-run
     failure for an unrelated reason (e.g. a fixture-arg `TypeError`) must not be
     misreported as "direct import". This fails closed rather than being read as
     "did not enter" — an infrastructure failure must never look identical to a
     genuine refusal, and must never silently grant eligibility either.

### The scope fence is mechanical, not a judgment call

A unit that exposes **no** runtime way in at all — no linked test's own module, nor
any module it imports, defines `main` — is **not** judged by this rule.
`refusal_cause: "proof_not_through_entry_point"` never fires in that case; the
criterion falls through to the sibling no-entry-point-anywhere rule
(`refusal_cause: "no_entry_point_reaches_code"`, `_apply_reachability_gate`, part of
the BO-2900 runtime-reachability-guard family). `verify_done_eligible` composes the
two gates unconditionally — `_apply_reachability_gate(_apply_entry_point_reachability_gate(...), ...)`
— so the no-entry-point-anywhere gate always runs immediately after this one, on
this one's *output*. It opens with `if not verdict.get("eligible"): return verdict`,
so an already-refused verdict from this rule is returned unchanged rather than
silently overwritten with the sibling gate's own, independently-computed
`no_entry_point_reaches_code` verdict for the same unit — that guard, not the two
gates never running together, is what keeps the two `refusal_cause` values disjoint
in practice. Each still names a different fact and clears a different way: rewrite
the proof to call the entry point it skipped, versus give the unit an entry point
(or a recorded exemption) in the first place.

### Fixing a refusal

With no change to the implementing code and no additional assertion, a refused
criterion becomes eligible again once its proof is rewritten to invoke the
detected entry point with the action and arguments an operator would actually
use — for example, calling `main(["<action>", ...])` instead of importing and
calling the implementing function directly. See the
[Done-Proof Evaluation sequence diagram](../architecture/diagrams/c3-done-proof-reachability-gates-sequence.md#3-the-mechanical-entry-point-reachability-gate-bo-2900a-1)
for the full message-level flow, and
[ADR-003](../architecture/adrs/ADR-003-test-source-of-truth-discipline.md) for the
standing discipline this axis extends: the test is the source of truth for done,
and this rule adds a condition on *what that test reached*, not on what it asserts.

> **Where this fits relative to BP-1100b-5.** This axis is adjacent to, but does not
> overlap with, `BP-1100b-5` (which rejects a newly *added* assertion whose shape is
> presence-only over a fixed workflow/commit-guardian glob set). This rule instead
> rejects a genuinely-executing proof by what it **reached**, at done time, for any
> unit with a way in — it is not restating BP-1100b-5 and is not restated by it.

---

## 4. The sibling axis: no way of running the product reaches the code at all (BO-2900a-3)

Section 3 covers the case where a linked test's own module — or a module it
imports — defines a `main`, but the proof never entered it. That rule has a
**scope fence**: it does not fire at all when no `main` exists anywhere in
that test's own module or its imports. `_apply_reachability_gate`
(`scripts/ac_store/done_proof.py`) is the sibling gate that covers exactly
that remainder — the case Section 3 deliberately does not judge — and it runs
unconditionally immediately after Section 3's gate, on that gate's own
output. Composition is `_apply_reachability_gate(_apply_entry_point_reachability_gate(success_verdict, ...), ...)`,
and `_apply_reachability_gate` opens with `if not verdict.get("eligible"): return
verdict`, so an already-refused Section 3 verdict is returned unchanged — the
two `refusal_cause` values are disjoint by construction, never by the two
gates happening not to run together. See the
[Done-Proof Evaluation sequence diagram — Section 4](../architecture/diagrams/c3-done-proof-reachability-gates-sequence.md#4-the-no-entry-point-anywhere-gate-bo-2900a-3)
for the full message-level flow.

### The three conditions, evaluated mechanically

For each of the AC's linked Python tests, `_find_no_entry_point_unit` inspects
every bare module the test imports directly and, for each resolved candidate
unit, refuses only when **all three** of these hold:

1. **The unit defines no entry point of its own.** `_has_entry_point_of_its_own`
   checks for an `if __name__ == "__main__":` guard in the candidate's own
   source — a structural check, not a filename or docstring match.
2. **No other project file reaches it.** `_is_imported_elsewhere` walks every
   other `*.py` file under the project root (excluding the test tree) and
   checks whether the candidate's module name appears in that file's own
   **AST-derived** import graph (`_local_import_module_names` — the same seam
   Section 3's own cross-file resolution uses), never a regex text scan over
   raw file content. This distinction is load-bearing: a regex for the words
   `import <name>` matches a docstring, comment, or log string that merely
   *mentions* the import spelling without containing a real
   `ast.Import`/`ast.ImportFrom` node, which would let a fixture (or,
   originally, real code) game the gate by writing prose that looks like an
   import rather than writing one. This was fixed as part of BO-2900a-3
   itself — see the note below.
3. **No automation runs it as a program.** `_done_proof_automation_gate.unit_is_invoked_by_automation`
   (`scripts/ac_store/_done_proof_automation_gate.py`) answers this against the
   now-merged BO-2900b-1/BO-2900b-3 seam, `collected_invocations(script_paths)`
   (`scripts/commit_guardian/_reachability_invocation_collector.py`, re-exported
   by `_reachability_inventory.py` — the SAME import `_apply_reachability_gate`
   already reaches for BO-2900d-1's `is_exempt`; this module never opens a
   second import path to the `commit_guardian` package). It scans a
   project-scoped set of `.py` files — every file under the inferred project
   root except those under an excluded scan directory or under `test_root`,
   mirroring `_is_imported_elsewhere`'s own `project_root.rglob("*.py")`
   convention — and matches an `Invocation.surface` from the collected,
   AST-derived invocations against the candidate unit's own resolved path by
   **exact string equality**, never a glob, prefix, or basename match. A unit
   that IS run as a program by a real automation script fails condition 3, so
   the refusal does not fire at all for it and the verdict passes through
   unchanged — exactly like the "no no-way-in unit found" and "unit is
   exempted" outcomes below. This check runs **before** the exemption check
   (step 14 in the [sequence diagram](../architecture/diagrams/c3-done-proof-reachability-gates-sequence.md#4-the-no-entry-point-anywhere-gate-bo-2900a-3)):
   a unit that is invoked by automation is spared regardless of whether an
   exemption is also recorded for it, since automation invocation already
   answers "is this reachable" on its own.

A test importing the unit does not count as a way in for condition 2 — that
is exactly the case this gate exists to catch (see the regression note
below).

### The anti-ritual clause

No term in the condition set above reads test count, test presence, test
outcome, or coverage. Adding a second, third, or Nth passing test over the
same unreachable unit cannot flip the verdict, because the predicate never
looks at the test tree beyond resolving which units the linked test imports,
and condition 3's automation check reads only `collected_invocations`'
AST-derived invocation surfaces, never anything test-derived either. The only
two things that flip the verdict are:

- **The unit gains a real entry point** — condition 1 or 2 above becomes
  false (an `if __name__ == "__main__":` guard is added, or some other
  project file starts genuinely importing it).
- **A recorded exemption is registered for that exact unit** — see below.

### The refusal and how to clear it

When all three conditions hold and no exemption is recorded, `verify_done_eligible`
returns (`build_no_entry_point_refusal`, `scripts/ac_store/_done_proof_automation_gate.py`):

```
{
  "eligible": False,
  "reason": "no way of running the product reaches <unit> (refusal_cause: no_entry_point_reaches_code) for <ac_id>",
  "refusal_cause": "no_entry_point_reaches_code",
  "unit": "<repo-relative path to the unreachable module>",
  "clearing_actions": ["give the unit an entry point", "record an exemption"],
  "passing_tests": [...],
  "failing_tests": [],
  "dangling_tags": [...],
}
```

The `unit` field always names the specific module the gate refused — never
a vague "some code is unreachable" message. The `clearing_actions` field is
not prose commentary — it is a literal, machine-readable list built from the
single `CLEARING_ACTIONS` constant in `_done_proof_automation_gate.py`, so
`check_done_proof.py` and BO-2900e-1's future refusal message can read the
two ways to clear this exact cause directly off the verdict rather than
hard-coding their own copy of the wording.

Two, and only two, actions clear this refusal — the same two named in
`clearing_actions` above:

1. **Give the unit a real way in** — add a module-level `main`/`if __name__
   == "__main__":` entry point, have some other real project file genuinely
   import it (not merely mention it in prose), or have a real automation
   script run it as a program (condition 3 above).
2. **Record a reasoned exemption** for that exact unit in
   `config/reachability_exemptions.yaml`, per
   [BO-2900d](../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml).
   `_apply_reachability_gate` checks the shared exemption seam
   (`scripts/commit_guardian/_reachability_inventory.py`'s `load_exemptions`
   / `is_exempt`) before refusing — but only after the automation check
   above has already passed a unit through unrefused; a matching,
   non-blank-reason entry releases the refusal and the returned verdict
   carries an `exemption: {item, reason}` field naming the recorded reason
   rather than silently absorbing the exception. This is deliberately the
   *only* other release valve — this AC does not decide the helper-module
   case itself, it hands off to BO-2900d's exemption registry.

### The regression this AC is calibrated against

This is the clause that catches the actual PR-411 regression state: a unit
with no registered capability, no caller, and passing tests anyway. The
BO-2900a-1 direct-import check (Section 3) passes vacuously on a unit with no
`main` at all — it is not designed to catch this shape, and was not widened
to compensate. Before this AC's fix, `_is_imported_elsewhere`'s regex-based
text scan could itself be fooled by a decoy: a second, unrelated source file
whose **docstring** (never a real `import` statement) mentioned the target
module's import spelling was enough to make the gate believe the module was
imported elsewhere and grant `eligible: True`. The fix — routing condition 2
through the AST-derived import graph instead of a text scan — closes that
gap; see the [sequence diagram's Section 4](../architecture/diagrams/c3-done-proof-reachability-gates-sequence.md#4-the-no-entry-point-anywhere-gate-bo-2900a-3)
for the exact before/after.

---

Both axes above run only after
[done-proof-enforcement.md, section 2](done-proof-enforcement.md#2-the-ci-gate)'s
pass/fail rule already returned `eligible: True` — see that guide for the
two-layer (pre-commit / CI) enforcement strategy these axes extend.
