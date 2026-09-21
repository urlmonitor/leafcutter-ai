---
title: "KI-CG-20260907-commit-delegation-is-a-password-not-an-identity — the hook that enforces \"only the commit agent may commit\" is satisfied by typing a string"
description: "KI-CG-20260907-commit-delegation-is-a-password-not-an-identity — the hook that enforces \"only the commit agent may commit\" is satisfied by typing a string"
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

# KI-CG-20260907-commit-delegation-is-a-password-not-an-identity — the hook that enforces "only the commit agent may commit" is satisfied by typing a string

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 (found by an `architect-review` blast-radius pass; the author had been
  bypassing it unknowingly all session)
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `templates/hooks/enforce_commit_delegation.py:84-94`

**Symptom.** `CLAUDE.md` states the rule in strong terms: *"`git commit` must never be called
directly. Dispatch the `commit` agent via the Agent tool instead… The
`enforce_commit_delegation` PreToolUse hook will block any direct `git commit` call that does
not originate from within the `commit` agent."*

The hook cannot do that, and does not try. Its entire authorisation check:

```python
if os.environ.get("COMMIT_AGENT_MODE", "") == "1":
    return True
if payload is not None:
    ...
    tokens = command.lstrip().split()
    if "COMMIT_AGENT_MODE=1" in tokens:
        return True
return False
```

It is a **token match on the command string**. There is no caller binding, no agent identity,
no provenance of any kind. Anything that prefixes its command with `COMMIT_AGENT_MODE=1`
passes — the commit agent, another agent, a human, a script.

**The gap is between the documented guarantee and the implemented one, and only one of them
is load-bearing.** "Originates from within the commit agent" is an identity claim. What is
enforced is a shared secret with a published value, written in `CLAUDE.md`, in the commit
agent's own template, and in this entry. Calling it a bypass overstates it: there is nothing
to bypass, because possession of the string *is* the authorisation.

**Found the way these things are usually found.** An `architect-review` was asked for the
blast radius of a change to the commit path and reported the hook as identity-blind in
passing. The session that received that report had used
`COMMIT_AGENT_MODE=1 git commit -F …` on **every commit it made that day** — six merged PRs
— under the documented understanding that the batch-drive form was a sanctioned exception
routed through the same guarantee. It was not routed through anything.

**What is actually still enforced, and worth keeping in view.** The value of the delegation
rule was never only the identity check. `COMMIT_AGENT_MODE=1` bypasses the commit agent's
*interactive confirmation gate* and nothing else — the pre-commit hook chain, the
autofix-and-retry path and the message-matches-diff discipline all still run, because they
are hooks on the commit itself rather than on the caller. So the practical exposure is
narrower than "anyone can commit anything": it is that an unattended caller can commit
**without a human gate**, which is exactly the property `finalize-feature`'s step 3.5 already
exercises and which `KI-BO-*` has recorded going wrong at store-wide scale.

**Fix direction.** Decide which guarantee is wanted and make the two agree, in that order —
the current state is bad mainly because the documentation promises the stronger one.

- If identity is genuinely wanted, the hook needs something the caller cannot mint. A
  PreToolUse hook receives the payload; whether it can see agent provenance is the question
  to answer first, and if it cannot, the honest conclusion is that this rule is not
  mechanically enforceable at this layer and `CLAUDE.md` should stop saying it is.
- If a human gate is the real requirement, enforce *that* — the check becomes "was this
  commit confirmed", which is observable, rather than "who is calling", which is not.
- Either way, **correct `CLAUDE.md`.** A documented guarantee nobody can rely on is worse
  than a documented convention everybody follows, because the first stops people looking.

**The same hook fails in the opposite direction too, and it demonstrated this on the commit
that filed this entry.** `_is_git_commit_call` (line 40) returns True when the command field
*contains the literal string* `git commit` — anywhere, in any context. So the hook is
simultaneously:

| | |
|---|---|
| **False negative** | any caller that types `COMMIT_AGENT_MODE=1` is authorised |
| **False positive** | any command whose text merely *mentions* `git commit` is blocked |

The second is not hypothetical. Opening the pull request for this entry —
`gh pr create … --body "…"` , where the body quotes `CLAUDE.md`'s sentence about
`git commit` — was blocked by this hook. Nothing was being committed; the phrase appeared
inside prose being passed to GitHub. **The hook blocked the attempt to document the hook.**

The workaround is `--body-file`, which keeps the phrase out of the command string — but note
what that means: the guard is evaded by moving text into a file, and enforced against
commands that were never commits. Both halves are the same root cause, which is that a
command string is being used as a proxy for two things it cannot express — *who is calling*
and *what is being done*.

**Trap.** The hook is not broken and will not appear in any failing test — it does precisely
what its code says. Reading the code answers "does the env-var check work" (yes) rather than
"does this enforce delegation" (no). The mismatch is only visible by reading the hook against
the sentence in `CLAUDE.md` that claims what it does.

**Related.** `KI-BO-*` on `finalize-feature` step 3.5's unattended closure commit — the
concrete case where an unattended, unconfirmed commit did real damage, and the reason the
human-gate reading of this rule is the one with evidence behind it.
`docs/reference/false-green-mechanisms.md` — a guard that reports enforcement it does not
perform.

---
