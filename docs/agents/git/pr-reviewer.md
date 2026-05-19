---
title: "Agent Reference: pr-reviewer"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "tickets/09_done/EPIC-CodingAgents/28_pr_reviewer_agent.md"
  - "tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md"
related_code:
  - ".claude/agents/pr-reviewer.md"
  - ".agents/workflows/pr-review.md"
---

# Agent Reference: `pr-reviewer`

Implementing agent: `pr-reviewer` (Sonnet → Opus gatekeeper, user-facing).
Family: `coding/` — invoked directly by the user or by `pull-request` as a pre-open step.
Slash command: `/pr-review [auto|target <ref>|explain <N>]`

---

## 1. When to Use

`pr-reviewer` is the signal-filter layer on top of the existing `pr-review-toolkit:review-pr`
skill. Use it:

- Before opening a PR — get a clean, high-confidence-only view of the diff without wading through style nits.
- On a branch mid-flight — sanity-check the working diff before committing.
- Via `/pr-review explain <N>` — deep-dive a specific finding from the last review without re-running the full suite.

`pull-request` (ticket 12) invokes `pr-reviewer` automatically as part of its pre-open flow.

**Do not use `pr-reviewer` to:**

- Review PRs that are already open on GitHub (separate future ticket).
- Make code changes — use `python-coder` or `sql-coder` to act on findings.

---

## 2. Action Surface

| Action | Syntax | Behaviour |
|---|---|---|
| `auto` | `/pr-review` or `/pr-review auto` | Review working diff vs the current base branch |
| `target <ref>` | `/pr-review target main` | Review working diff vs a named branch or SHA |
| `explain <N>` | `/pr-review explain H-1` | Deep-explain finding H-1 or M-1 from the most recent review in this session; no full re-run |

Default when no argument is supplied: `auto`.

---

## 3. Classification Rubric

Every finding from the underlying review skill is assigned exactly one confidence class. When in doubt, the agent defaults to medium, not low — uncertain findings are kept, not dropped.

### High — surfaced to the user

| Example | Why high |
|---|---|
| `result = data["key"]` with no KeyError guard on a hot path | Crashes in production on any missing key |
| `except Exception: pass` in a DB write path | Silently swallows failures; data integrity risk |
| Hardcoded API key string literal | Security smell — will end up in git history |
| `if x == None:` on a value that can legitimately be `None` | Logic error — should be `is None` |
| Off-by-one in a loop bounds | Produces wrong results or index error |

### Medium — bundled for potential Opus escalation

| Example | Why medium |
|---|---|
| A naming convention that conflicts with existing patterns in the module | May be a real problem depending on what the symbol is used for elsewhere |
| A function that returns `None` implicitly and the caller doesn't check | Could be fine or could crash — depends on call paths |
| A type annotation that looks wrong for the domain | Suspicious but not definitively a bug without seeing callers |
| Any finding the agent cannot cleanly place in high or low | Default is medium, never low |

### Low — suppressed silently (tally only)

| Example | Why low |
|---|---|
| Missing blank line between functions | Pure style |
| `x` instead of `value` as a variable name in a short loop | No correctness implication |
| Comment says "returns string" but the doc is slightly off | Documentation polish |
| Import ordering not matching isort convention | Formatter territory |

---

## 4. Suppression-with-Tally Pattern

Low-confidence findings are never shown in the report — they are counted and the count is always shown in the **Suppression Tally** line at the bottom of the report, even when the count is zero:

```
Suppressed: 7 low-confidence nits, 0 medium findings dropped by Opus.
```

This makes suppression visible: a "clean" report that suppressed 50 low-confidence nits is not the same as a genuinely clean diff. The user can see the count and decide whether to investigate.

---

## 5. Medium-Cluster Escalation

**Threshold: more than 3 medium-confidence findings.**

When the threshold is crossed, the agent bundles all medium findings into a single context payload and spawns an Opus sub-agent inline via the `Agent` tool. Opus is asked to evaluate each finding and return either "promote to high" (with reason) or "drop" (with reason).

The agent merges Opus's decision:
- Promoted findings are added to the high-confidence list in the final report.
- Dropped findings are added to the suppressed tally.

**Rationale:** "Is this cluster of medium-confidence flags pointing at a real structural issue?" is a judgement call that requires synthesis across multiple findings. That is exactly the kind of work Opus should own.

The `## Escalation` section in every run's output records whether the gate fired:

```
## Escalation

Branch: none
Reason: not escalated: medium count was 2 (threshold > 3)
```

or:

```
## Escalation

Branch: opus
Reason: escalated: medium count was 5 (threshold > 3); Opus promoted 2, dropped 3
```

---

## 6. Integration with pull-request (ticket 12)

`pull-request` invokes `pr-reviewer` as a pre-open step before calling `gh pr create`. If `pr-reviewer` returns any high-confidence findings, `pull-request` surfaces them to the user and asks whether to proceed or address them first. The gate is advisory — the user decides.

---

## 7. Strict Research Delegation

`pr-reviewer` carries no search tools (`Grep`, `Glob`, MCP search tools). If a finding raises a cross-file question — "does this caller pattern appear elsewhere in the codebase?", "is this the only place this SQL procedure is called?" — the agent delegates to `research-agent` via the `Agent` tool and folds the answer into the finding's explanation.

This is especially relevant for the `explain <N>` action, where deeper context about a single finding may require tracing usages across files.

---

## 8. Read-Only Guarantee

`Write` is not in `pr-reviewer`'s tool list. The agent:

- Does not write or modify any source file.
- Does not stage files or create git commits.
- Does not push to any remote.
- Does not open or modify PRs.

The `Edit` tool is present for session-buffer annotation (the `explain` action appends a note to the conversation context). It is never used to modify project files.

---

## 9. Underlying Skill

`pr-reviewer` wraps `pr-review-toolkit:review-pr`. That skill dispatches to five
specialist sub-skills:

| Sub-skill | Focus |
|---|---|
| `code-reviewer` | General code quality and correctness |
| `comment-analyzer` | Comment quality and doc consistency |
| `silent-failure-hunter` | Swallowed exceptions and error-logged-and-ignored paths |
| `pr-test-analyzer` | Test coverage of changed code; missing edge cases |
| `type-design-analyzer` | Type annotation and signature smells |

`pr-reviewer` invokes the parent skill only — it does not call sub-skills directly. The fan-out is the skill's responsibility.

---

## 10. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1), file layout (§2), visibility classes (§3), tool allowlists (§4), gatekeeper escalation pattern (§5.3).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) — three-tier ladder (§2.1), gatekeeper escalation (§2.3), tool allowlist (§2.6).
- [`.agents/workflows/pr-review.md`](../../../.agents/workflows/pr-review.md) — slash-command workflow body.
- [`tickets/09_done/EPIC-CodingAgents/28_pr_reviewer_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/28_pr_reviewer_agent.md) — the ticket that shipped this agent.
- [`tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md) — pull-request agent that invokes pr-reviewer as a pre-open step.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
