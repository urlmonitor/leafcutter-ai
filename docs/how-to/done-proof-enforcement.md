---
title: "How to understand proof-of-done enforcement (pre-commit and CI)"
description: "Explains the two-layer proof-of-done enforcement system: the fast local pre-commit check and the authoritative CI gate that blocks merge on unproven work, including the third eligibility axis (BO-2900a-1) that refuses a proof reaching the code by direct import when the unit has a real way in."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-09-25
components:
  - build_orchestration
  - commit_guardian
  - ac_store
related_docs:
  - docs/how-to/prove-ac-done.md
  - docs/how-to/fast-lane-build.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/pre-commit-hooks.md
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
  - docs/architecture/adrs/ADR-003-test-source-of-truth-discipline.md
---

# How to understand proof-of-done enforcement (pre-commit and CI)

No AC may reach `work_status: done` without a covers-tagged, passing test. This
guarantee is maintained by two enforcement layers that operate at different speeds
and with different authority:

| Layer | Speed | What it checks | Bypassable? |
|-------|-------|----------------|-------------|
| Pre-commit hook (`check-done-proof`) | Fast (static) | Tag presence only — no test run | Yes (with `SKIP=` or `--no-verify`) |
| CI gate (`done-proof` job) | Slower (runs pytest) | Full `verify_done_eligible` — all done ACs | No (runs on every push; catches all local bypasses) |

The rest of this guide explains exactly what each layer does, how to skip the
pre-commit hook when you have a legitimate reason, and why a local skip cannot
prevent unproven work from being caught before it reaches the protected branch.

**Sibling hook:** `check-proof-promise-claim` reads the same underlying
`done_proof.collect_test_tag_records` scanner but governs a different moment
— a staged *ticket's own plan* promising a kind of proof with no matching
claim yet, rather than an AC YAML claiming `work_status: done`. See its
entry in [`docs/pre-commit-hooks.md`](../pre-commit-hooks.md#proof-promise-vs-claim-check-check-proof-promise-claim).

---

## 1. The local pre-commit hook

### What the hook does

Hook id: `check-done-proof`

When you run `git commit`, this hook invokes:

```
python scripts/commit_guardian/check_done_proof.py
```

The default mode is `--mode precommit`. Its logic is:

1. Retrieve staged AC YAML files:
   ```
   git diff --cached --name-only --diff-filter=ACM
   ```
   Only files under `docs/acceptance-criteria/` with a `.yaml` extension are
   evaluated. Files that do not exist on disk are skipped.

2. For each staged YAML whose `work_status` field equals `"done"`:
   - Determine the AC's `id` from the YAML.
   - Search every `*.py` file under `unit_tests/` recursively for a line
     matching `# covers: <ac_id>`.
   - If no such tag is found anywhere in the test tree, record a violation.

3. If any violations were found, print each one and exit with code 1 (blocking
   the commit). If no violations were found, exit 0.

This is a **static filesystem scan only**. The hook does not invoke pytest; it
does not verify that the tagged test actually passes. It checks tag *presence*,
nothing more.

**Fail-open safety:** If the hook crashes unexpectedly (for example, due to an
import error in a fresh worktree), it exits 0 rather than 1. A crash never
blocks a commit — but it also means the local check was not performed. The CI
gate is still active regardless.

### What the hook does not catch

Because the pre-commit check is a tag-presence scan with no test execution:

- A test tagged with `# covers: MY-AC-001` that is currently failing, xfailed,
  or skipped **does not trigger a violation**. The tag exists; the hook exits 0.
- A commit made from a worktree that has no `.pre-commit-config.yaml` runs with
  `PRE_COMMIT_ALLOW_NO_CONFIG=1`, meaning the hook never fires at all.
- Any commit made with `--no-verify` or `SKIP=check-done-proof` bypasses this
  layer entirely.

All three of these bypass paths are caught by the CI gate (see section 2).

### How to skip the pre-commit hook

Skip this hook only when you have a concrete reason (for example, you are
committing a work-in-progress AC draft that is not yet marked done, and an
unrelated staged YAML is being flagged).

**Skip this hook only:**
```bash
SKIP=check-done-proof git commit -m "your message"
```

**Skip all pre-commit hooks:**
```bash
git commit --no-verify -m "your message"
```

Skipping the hook does not skip CI. If the commit includes any AC YAML with
`work_status: done` that lacks a passing covers-tagged test, the CI gate will
report the violation on your next push (see section 2).

---

## 2. The CI gate

### What the CI gate does

Job name: **Proof-of-done coverage check (BO-2500b)**

This job runs on `ubuntu-latest` (a fresh checkout) on every push to any branch.
Its steps are:

1. Checkout the repository.
2. Set up Python 3.13 and install `requirements-dev.txt`.
3. Run `python scripts/build.py --target-dir .` — this runs `install_shims` to
   create the `scripts/commit_guardian/` symlinks that the hook imports rely on
   (required on a fresh checkout where no local build has been run).
4. Run:
   ```
   python scripts/commit_guardian/check_done_proof.py --mode ci
   ```

In `--mode ci`, the script performs a **full, authoritative check**:

- Scans every YAML file under `docs/acceptance-criteria/` recursively.
- For each file whose `work_status` is `"done"`, calls `verify_done_eligible`
  from the `done_proof` engine.
- `verify_done_eligible` **runs pytest** against the test files linked by the AC's
  covers tags to confirm the tests actually pass.
- An AC is ineligible (a violation) if its linked test is FAILED, XFAIL, SKIPPED,
  ERROR, or missing entirely.
- Even when the linked test PASSES, `verify_done_eligible` also asks *what the
  test reached* while it ran — see [section 3](#3-the-third-eligibility-axis-did-the-proof-go-in-through-the-real-way-in-bo-2900a-1)
  below.

The CI mode evaluates the **entire AC store** — not just the files you staged in
your last commit. This means it finds done ACs that became ineligible due to
refactoring, even if you never changed their YAML.

### Current blocking status

The job is currently configured with `continue-on-error: true`. This means a
violation does not block the PR merge while the existing AC store is being brought
into full coverage (tracked by BO-2500b-3). Once that migration is complete, the
`continue-on-error` flag will be removed and the gate will become a hard merge
blocker.

Even in the current informational state, every violation the CI job reports is a
real gap: a done AC with no passing test. Do not let violations accumulate.

### Why CI catches what a local skip misses

Three common bypass paths all route through the same CI check:

| Bypass path | How it happens | CI outcome |
|-------------|---------------|------------|
| `SKIP=check-done-proof` | Developer skips the hook for one commit | CI still runs `--mode ci` on push and finds the violation |
| `git commit --no-verify` | Developer skips all hooks | Same as above |
| Hook-config-less worktree | No `.pre-commit-config.yaml` in the worktree; hooks never fire | Same as above |

In every case, the CI job runs on a fresh checkout where no local configuration
is assumed. It is structurally impossible to reach the protected branch with an
unproven done AC without the CI gate observing it.

---

## 3. The third eligibility axis: did the proof go in through the real way in? (BO-2900a-1)

Section 2 describes the incumbent rule ([BO-2500a-3](../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-3.yaml)):
a covers-tagged test exists, and it passes. That rule asks nothing about *what the
test actually reached* while it ran. A test that imports the implementing function
directly and calls it satisfies BO-2500a-3 just as well as a test that drives the
same behaviour through the product's real command surface — even though only the
second kind of test proves an operator can actually reach the fix.

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
[Done-Proof Evaluation sequence diagram](../architecture/diagrams/c3-done-proof-evaluation-sequence.md#3-the-mechanical-entry-point-reachability-gate-bo-2900a-1)
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

## Summary: two-layer strategy

The pre-commit hook and the CI gate are deliberately designed to have different
characteristics:

**Pre-commit (fast, local, bypassable):**
- Runs in milliseconds (static file scan, no subprocess).
- Gives you immediate feedback during your normal commit flow.
- Can be skipped when necessary — for example, when you are iterating on a draft
  or committing unrelated files alongside a staged AC.
- Checks only the ACs you are staging right now.

**CI gate (authoritative, remote, inescapable):**
- Runs pytest to verify test results, not just tag presence.
- Checks every done AC in the store on every push.
- Cannot be bypassed by any local action.
- Is the backstop that makes the local skip safe: you can defer feedback until
  push, but you cannot defer it past push.

Together, the two layers mean you get a developer-friendly fast loop locally and
a guarantee that no unproven work can reach the protected branch through any
bypass path.
