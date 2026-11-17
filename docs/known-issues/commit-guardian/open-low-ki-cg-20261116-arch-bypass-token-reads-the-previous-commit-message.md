---
title: "KI-CG-20261116-arch-bypass-token-reads-the-previous-commit-message — five pre-commit hooks honour `[NO-ARCH-UPDATE]` from the previous commit's message, never from the commit being made"
description: "check_structural_change, check_mermaid_drift, check_diagram_naming and check_mermaid_complexity read .git/COMMIT_EDITMSG at the pre-commit stage, and check_mermaid_parent_link reads the last commit's subject, so the approved [NO-ARCH-UPDATE] bypass is off by one commit in both directions"
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md
---

# KI-CG-20261116-arch-bypass-token-reads-the-previous-commit-message — five pre-commit hooks honour `[NO-ARCH-UPDATE]` from the previous commit's message, never from the commit being made

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium (a guard is silently switched off for one commit; another commit's
  legitimate bypass is ignored)
- **Status:** open, no AC. Kept out of the feedback-id bypass removal by decision on
  2026-11-16, because `[NO-ARCH-UPDATE]` is approved behaviour (GE-113b-1, GE-113b-1-i,
  GE-113b-2), while `[NO-FEEDBACK-CHECK]` is not.
- **Occurrences:** 1 (found by reading the code; no observed wrong outcome recorded yet)
- **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where** (`templates/scripts/commit_guardian/`, origin/main 2026-11-16):
  - `check_structural_change.py:163-187` reads `COMMIT_EDITMSG` via `git rev-parse --git-path`
  - `check_mermaid_drift.py:69-82` reads `COMMIT_EDITMSG`
  - `check_diagram_naming.py:58-71` reads `COMMIT_EDITMSG`
  - `check_mermaid_complexity.py:216` reads the relative path `.git/COMMIT_EDITMSG`, so it
    also misses in a linked worktree, where `.git` is a file
  - `check_mermaid_parent_link.py:83` reads `git log -1 --format=%s`, the last commit's subject
  - All are registered `stages: [pre-commit]` in `commit_guardian.json` (for example
    `check-structural-change` at `:590-599`)

**Symptom.** At the pre-commit stage, git has not yet written the message of the commit
being made. `.git/COMMIT_EDITMSG` still holds the previous commit's message, and
`git log -1` is the previous commit. So:

1. A commit whose own message carries `[NO-ARCH-UPDATE]` is **not** excused. The token is
   invisible until the commit-msg stage, which these hooks do not run at.
2. The commit **after** one that carried the token **is** excused, although it never asked.
   The guard says nothing when it should object, and nothing records that it was bypassed.

`check_structural_change.py:163`'s docstring says it reads `COMMIT_EDITMSG` "so the escape
hatch can be" honoured. That premise is false at this stage. INF-1300a-1 (guard 3) already
works around the same reads in a test harness, by asserting that no message in its scratch
repo contains the token. That is the defect noticed from the test side.

**Same root cause as** [KI-CG-20260901](open-low-ki-cg-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message.md)
(`[NO-FEEDBACK-CHECK]`), which is being removed outright under a new GE-123 L1. Removal is
not the obvious answer here, because the GE-113b ACs approve this bypass. The decision is
between moving the token read to the commit-msg stage (needs `always_run`, no `files`
filter, the commit-msg shim, and a rule in `commit.md` about agents writing the token)
and retiring the bypass.

**Detection.** Commit c1 with `[NO-ARCH-UPDATE]` in its message. Stage a structural change
without the matching architecture doc, and commit with a message that has no token. The
change goes through. Reverse the order and the token is ignored.

**Fix direction.** Decide the bypass's future first, at the GE-113b owner. Then, either:
- re-register the five token reads at commit-msg stage, reading the message file passed as
  an argument (the precedent is `check-package-surface-declaration`), with behavioural tests
  that make real commits; or
- remove the token, and amend GE-113b-1, GE-113b-1-i and GE-113b-2 accordingly.

Do not hand-write `COMMIT_EDITMSG` in the tests. That is how `tests/test_check_feedback_id.py`
locked the KI-CG-20260901 defect in.

**Pattern:** a pre-commit hook reading the commit message, which does not exist yet at that stage.
