---
title: "How to Use the Known-Failing Tests Baseline"
type: how_to
status: active
created: 2026-05-22
last_updated: 2026-05-22
components:
  - build_system
related_docs:
  - docs/explanation/why-feedback-system.md
related_code:
  - scripts/commit_guardian/known_failing_tests.py
  - scripts/commit_guardian/known_failing_tests.json
---

# How to Use the Known-Failing Tests Baseline

The known-failing tests baseline lets commits proceed even when pre-existing
test failures are present. The pre-commit hook blocks only on **new**
regressions — tests that were passing before your change and now fail.

This eliminates the `--no-verify` escape path: you no longer need to bypass
all hooks just because a test that predates your change is still failing.

---

## How It Works

1. The pre-commit hook `run-tests-with-baseline` runs pytest on every commit.
2. It loads `scripts/commit_guardian/known_failing_tests.json` (the baseline).
3. It computes `new_failures = current_failures - baseline`.
4. If `new_failures` is empty: the commit proceeds (exit 0).
5. If `new_failures` is non-empty: the commit is blocked (exit 1) with an
   actionable error listing the new failures.

---

## When to Update the Baseline

Update the baseline when:

- You are not responsible for a pre-existing failure and want to commit
  unrelated work without fixing it first.
- The failing test was already failing on `main` before your branch.
- You or your team have decided the failing test is deferred work (create a
  ticket for it and update the baseline).

Do **not** update the baseline to hide regressions you introduced. The
baseline diff is a reviewable `git diff` — reviewers will see it in your PR.

**Policy:** Baseline entries should not accumulate indefinitely. If an entry
is older than 30 days, create a ticket to fix the underlying test.

---

## How to Update the Baseline

Run the update command from the project root:

```bash
python scripts/commit_guardian/known_failing_tests.py --update
```

This runs pytest, collects all currently-failing tests, and writes them to
`scripts/commit_guardian/known_failing_tests.json`.

Then stage and commit the updated baseline alongside your other changes:

```bash
git add scripts/commit_guardian/known_failing_tests.json
git commit -m "chore(tests): update known-failing baseline — <reason>"
```

The commit message should explain **why** the baseline was updated (e.g.
"pre-existing DB migration failures not related to this PR").

---

## What NOT to Do

- Do not use `git commit --no-verify`. This bypasses ALL hooks, not just
  the test hook. Use the baseline instead.
- Do not delete `known_failing_tests.json` to reset the baseline silently.
  Use `--update` so the change is tracked in git history.

---

## For Commit Agents

Commit agents should not reach for `--no-verify` when tests fail.
Instead:

1. Check whether the failing tests are in the baseline:
   ```bash
   python scripts/commit_guardian/known_failing_tests.py
   ```
2. If no new failures are detected, the commit will proceed normally.
3. If new failures are detected, investigate whether they are caused by the
   current change or pre-existed. If pre-existing, update the baseline.

See also: `templates/agents/commit.md` — the commit agent instructions
include a reminder not to use `--no-verify` for test failures.
