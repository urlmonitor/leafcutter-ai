---
title: "KI-AR-003 — `skills_invoked` still declares `signoff` for two agents whose sign-off obligation was removed, and the resulting mismatch is advisory only"
description: "KI-AR-003 — `skills_invoked` still declares `signoff` for two agents whose sign-off obligation was removed, and the resulting mismatch is advisory only"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - agent_registry
related_docs:
  - docs/known-issues/agent-registry.md
  - docs/known-issues/README.md
---

# KI-AR-003 — `skills_invoked` still declares `signoff` for two agents whose sign-off obligation was removed, and the resulting mismatch is advisory only

> One known issue, split out of `docs/known-issues/agent-registry.md` on
> 2026-09-14. Index: [agent-registry.md](../agent-registry.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `config/agent_registry.json` — `research-agent.skills_invoked`, `worktree-agent.skills_invoked`; detected by `check_skills_invoked_xref` in `scripts/build_phases.py`

**Symptom.** `AR-200a-1` (PR #557) removed the sign-off obligation from `research-agent` and
`worktree-agent`: both are `tier: utility`, `is_ticket_phase: false`, appear in no `phaseOrder`,
and each declared a mandatory sign-off it had no write-capable tool to perform. Their
frontmatter `signoff: true`, their `## Sign-off` body sections, and their false
`outputs`/`mutates` entries were all corrected. The **registry** was not: both still carry
`{"skill_id": "signoff", "mode": "always"}` in `skills_invoked`.

`build.py` notices and says so:

```text
[WARNING] research-agent: skills_invoked declares 'signoff' but no reference found in template body
[WARNING] worktree-agent: skills_invoked declares 'signoff' but no reference found in template body
```

It is a `[WARNING]`, the build exits 0, and nothing downstream reads it.

**Why this is worth a register entry rather than a silent follow-up.** It is the same shape as
the defect it was created by: two halves of one declaration disagreeing, with nothing that
fails. `AR-200a-1` exists because a template's `tools:` line and its sign-off obligation
contradicted each other and no gate compared them; this is the registry and the template
contradicting each other, one layer out, with a gate that compares them and only whispers.

**Blast radius today: none, and that is worth stating precisely.** `skills_invoked` is not
injected into the deployed agent body — verified against `.claude/agents/research-agent.md`,
which contains no sign-off instruction at all. So no agent is currently told to sign off. The
cost is that the registry is wrong about two agents, and any future consumer of
`skills_invoked` — a router, an audit, a card generator — inherits that error.

**It was left deliberately.** The change was driven by `/quick-fix`, whose constraints forbid
editing `config/agent_registry.json`. That was the correct call at the time; this entry is the
handoff rather than an omission.

**Approximately 14 pre-existing warnings of the same class already exist** for other agents, so
the fix is not two lines but a decision about whether this cross-reference should be advisory at
all. If it stays advisory, nothing stops the count growing; if it becomes blocking, the existing
14 must be resolved first. Recommend resolving the backlog and then promoting it — an advisory
that has accumulated 14 unresolved instances is already being ignored.

**Fix direction.** Drop the `signoff` object from `research-agent.skills_invoked` (leaving `[]`)
and from `worktree-agent.skills_invoked` (leaving its `feature`/`conditional` entry), then decide
the advisory-vs-blocking question for the class. Owner is `workflow-architect`, which owns the
registry.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 — a check that measures the right
thing and reports it at a severity nobody acts on.
