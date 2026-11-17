---
title: "KI-CG-20261116-authored-change-treats-a-failed-git-diff-as-an-empty-change — the shared change-set source reports a clean, empty change when git diff exits non-zero"
description: "_authored_change._build_authored_change checks only that git could be started, not its exit status, so a git diff --cached that fails returns could_not_check=False with an empty diff; every check that consumes it then passes having examined nothing"
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
---

# KI-CG-20261116-authored-change-treats-a-failed-git-diff-as-an-empty-change — the shared change-set source reports a clean, empty change when git diff exits non-zero

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium (silent pass: a check that examined nothing reports a clean change)
- **Status:** open. The fix is scheduled under **GE-123e-4-i**. The person decided on
  2026-11-16 to fix the shared source there, because that AC's fault-injection test depends on
  an honest could-not-check result. Filed separately so the change to a shared module stays
  visible to every check that consumes it.
- **Occurrences:** 0 observed (found by code reading during GE-123e enrichment)
- **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where:** `templates/scripts/commit_guardian/_authored_change.py:298-306`
  (`_build_authored_change`)

**Symptom.** `_build_authored_change` runs `git diff --cached [<incoming>]` and
`git diff --cached --name-status [<incoming>]` through `_run_git`, then treats only a `None`
result (git could not be started or timed out) as could-not-check. A command that starts but
exits non-zero is used as if it had succeeded. For example, an unreadable incoming blob, a bad
ref, or a corrupt index all produce an `AuthoredChange` with `could_not_check=False`,
`error=None` and empty `diff_text` / `name_status`. Every consumer then sees "nothing was
authored" and passes.

The same file already gets this right elsewhere: line 233 tests
`result is None or result.returncode != 0`. The defect is that one call site skips the exit
status.

**Why it matters.** It contradicts ADR-038 §6, which says a derivation failure is reported in
band as could-not-check, never as an empty change set. A check that found nothing and a check
that could not look become indistinguishable. That is the exact failure mode GE-120 ("green
means checked") exists to prevent. Consumers today include `check-contract-shrinking` and
`check-doc-frontmatter`, and `check-feedback-id` once GE-123e-4 lands.

**Detection.** In a scratch repo mid-merge, make the incoming side's copy of a staged file
unreadable while `MERGE_HEAD` stays valid, then call `get_authored_change()`. It returns
`could_not_check=False` with an empty diff. Expected: `could_not_check=True` with an `error`
naming the failed command.

**Fix direction.** In `_build_authored_change`, treat
`result is None or result.returncode != 0` as could-not-check for both invocations, with
git's stderr in `error`. Then re-run the consumers' tests. A consumer that relied on the silent
empty result was itself passing vacuously.

**Pattern:** "could the command run?" answered in place of "did the command succeed?".
