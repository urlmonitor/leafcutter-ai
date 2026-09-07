---
title: "How to understand proof-of-done enforcement (pre-commit and CI)"
description: "Explains the two-layer proof-of-done enforcement system: the fast local pre-commit check and the authoritative CI gate that blocks merge on unproven work."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/how-to/prove-ac-done.md
  - docs/how-to/fast-lane-build.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/pre-commit-hooks.md
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
