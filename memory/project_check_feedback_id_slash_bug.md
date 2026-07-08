# check_feedback_id — [NO-FEEDBACK-CHECK] bypass defects

Captured 2026-07-07 during EPIC-ComputedQualityGates finalize.

## Bug 1 — GIT_COMMIT_MSG is never set during the pre-commit stage

`check_feedback_id.py`'s `[NO-FEEDBACK-CHECK]` bypass mechanism reads the
environment variable `GIT_COMMIT_MSG` to detect the bypass token. However,
git writes `COMMIT_EDITMSG` only AFTER the pre-commit hook stage completes.
During the pre-commit stage, `GIT_COMMIT_MSG` is always unset, so the bypass
condition never fires — the hook always runs regardless of whether
`[NO-FEEDBACK-CHECK]` appears in the commit message.

## Bug 2 — Commit message containing "/" causes OSError

When a commit message contains a "/" character, `check_feedback_id.py`
mis-parses it: the hook treats the commit message text as a file path and
calls `open()` on it. This raises an `OSError` (no such file or directory).
The escape hatch silently drops and the hook behaves non-deterministically on
commit messages that contain paths, branch names, or issue numbers with "/".
PR-merge commit messages routinely include "/" and are therefore affected.

## Workarounds (confirmed working)

- **Pre-write into `.git/COMMIT_EDITMSG` before committing:** Write the token
  `[NO-FEEDBACK-CHECK]` directly into `.git/COMMIT_EDITMSG` before issuing the
  commit command. The hook reads `COMMIT_EDITMSG` from the filesystem when
  `GIT_COMMIT_MSG` is absent, so a pre-written value is picked up correctly.

- **`SKIP=check-feedback-id`:** Skip the hook entirely for commits that
  genuinely need the bypass. Set `SKIP=check-feedback-id` in the environment
  before calling `git commit`. This is the cleanest workaround when the bypass
  is authorised.

## Fix status

Tracked as a standalone pre-commit-hooks ticket (not yet landed as of
2026-07-07). Discovered during EPIC-ComputedQualityGates ticket 10 finalize
(noted in that ticket's Out of Scope section). See FP-7 in
`docs/retrospectives/EPIC-ComputedQualityGates.md`.
