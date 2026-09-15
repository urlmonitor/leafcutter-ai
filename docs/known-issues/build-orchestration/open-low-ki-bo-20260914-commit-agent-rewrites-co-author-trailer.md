---
title: "KI-BO-20260914-commit-agent-rewrites-co-author-trailer — the commit agent replaces the caller's `Co-Authored-By` trailer with its own model name, so a commit misattributes which model did the work"
description: "low. No code is affected, but git history now states something false about provenance, and the only repair for a pushed commit is to rewrite history."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260914-commit-agent-rewrites-co-author-trailer — the commit agent replaces the caller's `Co-Authored-By` trailer with its own model name, so a commit misattributes which model did the work

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low. No code is affected, but git history now states something false about provenance, and the only repair for a pushed commit is to rewrite history.
- **Status:** open
- **Occurrences:** 1 confirmed (commit `6a537708`, 2026-09-14, now on `main` via #780)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/agents/commit.md`, around line 214. Its message-format rules name the footer as `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` "(the harness adds this; do not duplicate)".

**Symptom.** The calling session wrote a commit message file ending `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`, naming the model that authored the change. It dispatched the commit agent with `git commit -F <file>`. The agent reported: *"Attribution line correction: the message file had `Claude Opus 5`, but this session's attribution instruction specifies `Claude Sonnet 5`. I edited the scratchpad file to match before committing."* The resulting commit names the commit agent's model, which only ran `git commit`.

**Mechanism.** The template tells the agent the footer belongs to "the harness", meaning whichever session is running the commit agent. That session's attribution names the commit agent's own model tier, which differs from the model that wrote the code. So the agent treats a caller-supplied trailer as an error to reconcile against its own attribution, not as part of a message the caller authored. The template's example footer names a third model, which shows it has no notion of who authored the change.

**Workaround in use.** State in the dispatch prompt: "use the message file EXACTLY as written; do NOT change its Co-Authored-By trailer." Two later commits (`f7fd79de`, `d4fcb274`) kept the correct trailer under that instruction.

**Fix direction.**
- In `commit.md`, when the caller supplies a message (`-F` or `-m`), treat it as authoritative. The agent adds a trailer only when none is present, and never rewrites an existing one.
- Remove the hardcoded model name from the template footer.
- Add a template-contract test: the commit agent's instructions contain no literal model name, and they state that a caller-supplied trailer is preserved.

**Pattern:** a delegate that normalises metadata it was handed, substituting its own identity for its principal's.

---
