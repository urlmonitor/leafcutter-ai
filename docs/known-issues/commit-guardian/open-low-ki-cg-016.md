---
title: "KI-CG-016 — `enforce_commit_delegation` matches the phrase anywhere in the command string, so read-only commands that merely mention committing are blocked"
description: "KI-CG-016 — `enforce_commit_delegation` matches the phrase anywhere in the command string, so read-only commands that merely mention committing are blocked"
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

# KI-CG-016 — `enforce_commit_delegation` matches the phrase anywhere in the command string, so read-only commands that merely mention committing are blocked

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the `enforce_commit_delegation` PreToolUse hook, matching against the whole Bash command string rather than the resolved program and its subcommand

**Symptom.** Any Bash command whose text contains the phrase is refused with the full
delegation error, regardless of what the command actually does. Searching for the phrase,
printing it, or reading a file about it are all blocked.

**Evidence.** Two pure reads, both refused on 2026-08-25 with
*"direct git commit is not allowed … COMMIT_AGENT_MODE is not set to '1'"*:

```
grep -c "git commit" CLAUDE.md
grep -n "git add\|add -A\|stageAll\|git commit" templates/workflows-js/fast-lane-ship.js
```

Neither invokes git. The first counts lines in a Markdown file. The second was an audit of the
fast lane's staging behaviour — the work that produced `KI-BO-029` — and the block is what
forced that audit to be re-run with the phrase removed from the pattern.

**Why it is low.** It is loud, immediate and trivially worked around by rephrasing the search.
Nothing is silently wrong; the cost is a wasted call and a detour.

**Why it is worth filing anyway.** The affected commands are disproportionately the ones that
*audit commit behaviour* — greps over hook code, workflow staging steps, and this register's own
prose. A guardrail that obstructs inspection of itself raises the cost of the reviews most
likely to find its own defects. `CLAUDE.md` and several agent templates contain the phrase in
prose, so any grep across them is affected.

**The converse is the open question, and is NOT claimed here.** A matcher keyed on a substring
of the raw command is in principle both over-inclusive (this entry) and potentially
under-inclusive against spellings that do not contain the literal phrase. Only the
over-inclusive half was observed. Deliberately not probed — attempting to slip a real commit
past a safety hook is not an appropriate way to characterise it. Flagged for the owner to
settle by reading the matcher, not by experiment.

**Fix direction.** Match on the parsed invocation — program resolves to `git` and the
subcommand is `commit` — rather than on a substring of the command text. Failing that, exclude
commands whose program is a known read-only tool (`grep`, `rg`, `cat`, `less`, `echo`).

**Numbering.** A concurrent session minted `KI-CG-016` for a different defect on the same
day and renumbered its own entry to `KI-CG-017` before merge, leaving `016` to this one — see
that entry's own note. This is `KI-BO-024`'s id-collision shape again, resolved cooperatively
rather than by any check.

---
