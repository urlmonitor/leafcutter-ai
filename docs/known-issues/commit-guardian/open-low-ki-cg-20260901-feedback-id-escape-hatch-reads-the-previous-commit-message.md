---
title: "KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message — `check-feedback-id`'s documented `[NO-FEEDBACK-CHECK]` bypass cannot work with `git commit -m`, and the message it does read is the last successful commit's"
description: "KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message — `check-feedback-id`'s documented `[NO-FEEDBACK-CHECK]` bypass cannot work with `git commit -m`, and the message it does read is the last successful commit's"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message — `check-feedback-id`'s documented `[NO-FEEDBACK-CHECK]` bypass cannot work with `git commit -m`, and the message it does read is the last successful commit's

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/scripts/commit_guardian/check_feedback_id.py` — the "Fourth source"
  `COMMIT_EDITMSG` read (~`:100-120`) and the `_ESCAPE_TOKEN` check at `:53` / `:276`

**Symptom.** The hook refuses a commit and prints its own remedy:

```
Add 'feedback-id: <id>' on the line immediately after each heading,
or include [NO-FEEDBACK-CHECK] in the commit message to bypass.
```

Including the token — in the body, then in the subject line — changes nothing. The hook
refuses identically both times and never prints its
`[check-feedback-id] skipped via [NO-FEEDBACK-CHECK] escape hatch.` line.

**Cause.** The hook's fourth source reads `$GIT_DIR/COMMIT_EDITMSG`, and its comment states
the assumption plainly:

> *"This is the only reliable path at the pre-commit stage when the user runs
> `git commit -m "msg [NO-FEEDBACK-CHECK]"` — git writes the message to COMMIT_EDITMSG
> before running pre-commit hooks."*

**That is false.** With `-m`, git does not write `COMMIT_EDITMSG` before the *pre-commit*
hook; it writes it before the *commit-msg* hook. Read during pre-commit, the file still
holds the **previous successful commit's** message. Confirmed directly — mid-refusal, with
a subject containing the token, `head -3` of the worktree's `COMMIT_EDITMSG` showed the
subject of the commit that landed before it.

**The second-order defect is worse than the unusable bypass.** Because the file holds the
*previous* message, a commit whose predecessor legitimately used `[NO-FEEDBACK-CHECK]` will
be silently bypassed even though its own message never asked for it. The escape hatch is
therefore both unreachable when you want it and reachable when you do not — off by exactly
one commit in both directions. The gate is a feedback-traceability control, so a spurious
skip is a silent hole rather than a visible annoyance.

**Fix direction.** At the pre-commit stage the message is genuinely not yet available by any
reliable route, so the honest options are (a) move this check to the `commit-msg` stage,
where the message file is written and complete, or (b) keep it at pre-commit and **remove
the `COMMIT_EDITMSG` source and the escape-hatch text**, since advertising a bypass that
cannot be triggered sends every reader down a dead end. If the source is kept, it must at
minimum compare against `HEAD`'s message and ignore the file when they match — a
`COMMIT_EDITMSG` identical to the last commit is stale by definition, not a message about
the commit being made. Cover it with a test that asserts a *subsequent* commit is NOT
skipped when only its predecessor carried the token; a test that merely checks "token in
message ⇒ skip" passes against this defect.

**Workaround.** None via the commit message. Either add real `feedback-id:` lines, or —
where the headings are not phase-agent sign-offs at all — write them outside the sign-off
heading grammar the parser matches, which is the honest fix when no agent ran and no
feedback was submitted.

**Related.** `KI-CG-018` (a hook's own "did I look?" diagnostic that cannot fire).
`KI-CG-20260831-hook-scripts-never-invoked` (the family's other reachability defects).

**Pattern:** a fallback input source that is reliably *present* and reliably *wrong* — so the
control reads a real file, finds real content, and answers a question about the wrong commit.

---
