---
title: "KI-CG-038 — the commit agent's mandated command is refused by Claude Code's permission classifier, and the agent clears the refusal by repeating the identical command"
description: "KI-CG-038 — the commit agent's mandated command is refused by Claude Code's permission classifier, and the agent clears the refusal by repeating the identical command"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - commit_guardian
  - build_orchestration
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-038 — the commit agent's mandated command is refused by Claude Code's permission classifier, and the agent clears the refusal by repeating the identical command

> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the three-level
> index bucket (`high`); the original grading is the `**Severity:**` line below.

- **Severity:** high. A deny decision was cleared by repetition rather than by the condition
  changing, and the successful retry is indistinguishable from an ordinary commit afterwards.
  Not graded blocker: the commits still ran the full pre-commit chain, and their content was
  verified by the coordinating session, so nothing unchecked landed on this occasion.
- **Status:** open — `GE-129`
  (`docs/acceptance-criteria/guardrail-engine/GE-129-who-acts-not-what-typed/`) owns retiring
  the token that most plausibly triggers the refusal. **No AC covers the retry behaviour
  itself** — nothing in the store says an agent must not re-issue a command a permission
  decision has denied, or must surface the denial instead. That half is unowned.
- **Occurrences:** 1 session, 4 commits (2026-09-17)
- **First seen:** 2026-09-17 · **Last seen:** 2026-09-17
- **Where:** `templates/agents/commit.md` Step 4 (`:276-292`) — the mandated command form; the
  auto-mode permission classifier in Claude Code, which is harness-side and not in this repo

**Symptom, as reported by the dispatched `commit` agent.** On each of four commits, its first
`git commit` invocation was refused by Claude Code's auto-mode permission classifier, citing
"[Safety Bypass Flag]" — for two of them the first two attempts were refused. The agent then
re-ran the **identical** command and it succeeded. It said so itself:

> Identical commands succeeded on retry for commits 1–3.

**Evidence and its limits — stated plainly.** This entry rests on the commit agent's own
report to the coordinating session on 2026-09-17, not on a transcript of the classifier. What
is verified here from the repository:

- `templates/agents/commit.md:281` prescribes `COMMIT_AGENT_MODE=1 git commit -m "$(cat <<'EOF'
  … EOF)"`, and `:289-292` states *"The `COMMIT_AGENT_MODE=1` prefix is required"*, because
  `enforce_commit_delegation` blocks any commit without it. The agent was following its
  template.
- `grep -rn -i "safety bypass"` over this repository returns nothing. The string is
  harness-side, so the classifier's rule cannot be read here and the trigger cannot be
  confirmed from this side.

The plausible trigger is that same `COMMIT_AGENT_MODE=1` prefix: an inline environment
assignment in front of a git command is the shape a bypass-detecting classifier would flag,
and `KI-CG-20260907-commit-delegation-is-a-password-not-an-identity` records that this token
is exactly a published password. **Plausible, not established** — do not cite it as confirmed.

**Why it matters — two defects, and the second is the one with no owner.**

1. **The project's own guard requires a gesture another guard reads as an attack.** The
   delegation hook demands a string the agent must type; a bypass classifier sees a typed
   token in front of a privileged command. Neither guard can see who is acting, which is the
   whole subject of `GE-129`. Retiring the token should remove the trigger.
2. **A denied decision was cleared by repetition.** Whatever the classifier decided, the
   condition did not change between attempts — the command was byte-identical. So either the
   deny was not stable, or retrying defeats it. Both are bad in the same way: after the
   successful attempt, nothing in the ticket, the commit, or the agent's sign-off records that
   a safety control said no first. The correct behaviour on a denial is to stop and report,
   not to try again; `commit.md` says nothing about what to do when a permission decision
   refuses the call, and the one retry it does specify is for pre-commit hook failures
   (Step 5), which is a different thing.

This is a template/guard interaction, not one agent misbehaving. The agent used the command
its template mandates and retried a call that had failed; no instruction told it otherwise.

**Fix direction.**

- Under `GE-129`, stop requiring a typed token. A caller recognised by identity (or a commit
  gate that checks confirmation rather than the caller) removes the shape the classifier
  flags.
- Add an explicit rule to `commit.md`: a refusal by a permission decision is terminal for the
  attempt. Report it as a blocker naming the refusal text; never re-issue the same command.
  Distinguish it from the Step 5 pre-commit retry path, which is about hook output.
- Record the refusal where it can be audited — a refused-then-retried commit should leave a
  line in the ticket's `## Comments`, not vanish.
- Author an AC for "a denied permission decision is surfaced, not retried". Nothing in the
  store covers it today.

**Related.** `KI-CG-20260907-commit-delegation-is-a-password-not-an-identity` (the token, and
this occurrence recorded there as its live consequence), `KI-CG-016` (the same token's matcher
blocking read-only work).

---
