---
title: "KI-CG-20261116-removing-a-feedback-id-line-is-not-caught — check-feedback-id judges only sign-off headings a commit adds, so deleting the id under an existing heading passes"
description: "check-feedback-id inspects added heading lines and the lines that follow them; a commit that removes the feedback-id line beneath an already-committed sign-off heading adds no heading and is never judged"
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

# KI-CG-20261116-removing-a-feedback-id-line-is-not-caught — check-feedback-id judges only sign-off headings a commit adds, so deleting the id under an existing heading passes

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low (traceability loss, no observed occurrence)
- **Status:** open, no AC. Deliberately left out of GE-123e (bypass removal) by decision on
  2026-11-16. GE-123e covers only "a ticket change that adds a sign-off without its feedback
  id". This is the edit-side gap beside it.
- **Occurrences:** 0 observed (found while scoping GE-123e)
- **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where:** `templates/scripts/commit_guardian/check_feedback_id.py`. The check walks the
  staged diff for **added** `### YYYY-MM-DD HH:MM — ` heading lines and looks for a
  `feedback-id:` line among the next added lines (around `:227`).

**Symptom.** A commit that deletes, or blanks, the `feedback-id:` line beneath a sign-off
heading that is already committed adds no heading, so the check has nothing to judge, and
the commit passes. The heading now looks exactly like a legacy sign-off written before
feedback ids existed, and the link to its feedback record is gone without any signal.

**Why it is only low.** Nothing has been seen removing ids. The realistic paths are an
over-eager merge-conflict resolution, or an agent "tidying" a Comments section. The
traceability lost is real, but it can be recovered from history.

**Fix direction.** If wanted, add an L3 under GE-123e (it is at its 5-L2 limit): a staged
change that removes a `feedback-id:` line directly beneath an unchanged committed heading is
refused, naming the heading. Merge relief should apply on the same "identical to either
side" rule GE-123e-4 uses. Prove it with real commits, not a hand-built diff.

**Pattern:** a check that judges only additions has no view of a deletion that undoes what it once required.
