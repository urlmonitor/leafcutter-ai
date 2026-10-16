---
title: 'Agent Reference: conflict-resolver'
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
- tickets/09_done/EPIC-CodingAgents/11_conflict_resolver_agent.md
related_code:
- .claude/agents/conflict-resolver.md
description: 'Overview of Agent Reference: conflict-resolver.'
---
# Agent Reference: `conflict-resolver`

Internal identifier: `conflict-resolver` (Sonnet gatekeeper).
Spawned by: `pull-request`.
Family: `coding/`.

This document explains **when `pull-request` routes here**, **what inputs the
agent expects**, **what it produces**, the **line-by-line vs structural rubric**
with three examples each, and how a **structural** file is resolved in place.

---

## 1. When `pull-request` Routes Here

`pull-request` spawns `conflict-resolver` whenever `gh pr create` or a
preceding `git merge` / `git rebase` reports one or more unresolved conflict
markers in the working tree. The caller confirms the conflict state with
`git diff --name-only --diff-filter=U` before spawning.

**Do not invoke `conflict-resolver` directly.** It is an internal gatekeeper;
only `pull-request` spawns it. The agent produces a structured resolution
payload that `pull-request` uses to decide whether to proceed with the PR or
wait for a human decision.

---

## 2. Inputs

| Field | Type | Notes |
|---|---|---|
| `conflicted_files` | `string[]` | Paths with unresolved markers. The agent re-validates against `git diff --name-only --diff-filter=U`. |
| `base_branch` | string | The branch being merged into. |
| `head_branch` | string | The branch containing the incoming changes. |

The agent accepts a missing or partial input and falls back to running
`git diff --name-only --diff-filter=U` itself.

---

## 3. What the Agent Produces

A structured **Conflict Resolution Report** followed by an `## Escalation`
section (required on every run):

```
## Conflict Resolution Report

### resolved_files
- <path>: line-by-line — <one-line description of resolution applied>
- <path>: structural — <one-line description of the rubric trigger and the resolution>

### escalation
none (the field is kept so the report shape is unchanged; no escalation tier exists)

### escalation_reason
none | <one sentence naming the rubric trigger(s) that made file(s) structural>

### unresolved_files
none | <list>

## Escalation
line-by-line: all conflicts matched line-by-line triggers
```

---

## 4. Line-by-line vs Structural Rubric

The rubric is the agent's core classification gate. The agent reads every
conflict hunk (`git diff --diff-filter=U -- <file>`) and checks it against
this table before routing.

**Conservative default: classify as structural if in doubt.** A false-positive
costs a slower, more careful resolution. A false-negative silent wrong resolution
can corrupt source files or data.

### 4.1 Line-by-line triggers (Sonnet resolves inline)

All of the following must be true: EVERY hunk in the file matches at least
one line-by-line trigger.

| # | Trigger | Concrete example |
|---|---|---|
| L1 | **Import-list reordering** | `main` added `from collector import X` at line 3; `feature/foo` moved it to line 5. Both branches are additive; resolution is the union. |
| L2 | **Same line added in different positions** | Both branches appended `- 03_architect_review_agent.md` to the `depends_on:` list in a ticket frontmatter, but at different list positions. Resolution: include both entries, deduplicate if identical. |
| L3 | **Whitespace or formatting only** | One branch normalised trailing spaces; the other added a blank line between methods. Neither change is semantic. |
| L4 | **Frontmatter scalar update** | `last_updated: 2026-05-06` vs `last_updated: 2026-05-07` — take the later date. |
| L5 | **Comment change** | One branch updated a `# TODO` comment; the other did not touch the surrounding code block. |
| L6 | **Ticket frontmatter field addition** | `main` added `priority: high`; the feature branch added `components: [infrastructure]`. Both fields belong in the merged result. |
| L7 | **Dependency list divergence** | `main` added `requests>=2.31` to `pyproject.toml`; the feature branch added `httpx>=0.27`. Resolution: include both. |

### 4.2 Structural triggers (resolved in place, with fuller context)

ANY single hunk matching a structural trigger makes the entire file structural.

| # | Trigger | Concrete example |
|---|---|---|
| S1 | **Function signature differs across branches** | `main` changed `update_candle_context(candle_id: int)` to add `force: bool = False`; the feature branch changed it to `update_candle_context(candle_id: int, dry_run: bool)`. Incompatible parameter sets — Sonnet cannot choose safely. |
| S2 | **Both branches modified the same logic block** | `collector/services/candle_context/candle_context_worker.py`: `main` rewrote the retry loop to use exponential backoff; the feature branch extracted the same loop into a helper function `_retry_with_backoff()`. Both sides changed the same call site in incompatible ways. |
| S3 | **File moved or renamed on one branch** | `main` renamed `strategies/v1/pattern_matcher.py` to `strategies/pattern_matcher.py`; the feature branch modified the original path. Git reports the conflict on the old path — the agent escalates because applying ours/theirs on a moved file can silently discard the rename. |
| S4 | **Both branches introduced a new abstraction at the same call site** | `main` inlined a helper; the feature branch extracted a different helper at the same site. The merged result would contain two incompatible refactors. |
| S5 | **Both branches changed the same class/method in ways that cannot be merged by union** | Both branches added a new method `validate()` to `LiveTrader` but with different signatures and different bodies — it is not an additive union. |
| S6 | **Cross-cutting rename** | `main` renamed config key `MAX_POSITIONS` to `MAX_OPEN_POSITIONS`; the feature branch renamed the same key to `POSITION_LIMIT`. The two names must be adjudicated — one must win or the config key is ambiguous. |

---

## 5. Git Tools Used

The agent uses the following git and file-system operations directly (no MCP
search tools):

| Operation | Command |
|---|---|
| List conflicted files | `git diff --name-only --diff-filter=U` |
| Read raw conflict hunks | `git diff --diff-filter=U -- <file>` |
| Stage resolved file | `git add <file>` |
| Verify no markers remain | `grep -c "<<<<<<" <file>` — must return 0 |
| Read both sides and the ancestor | `git show :1:<file>`, `git show :2:<file>`, `git show :3:<file>` |

The conflict-resolver carries no `Grep`, `Glob`, or `jcodemunch` tools and is
permitted no sub-agents: it gathers context with `Read` and read-only git
commands only.

---

## 6. Resolving a Structural File

There is no deeper resolver to hand a structural file to. The agent gathers
both sides and the common ancestor, reads the history of the conflicting lines
on each branch, decides what each side was trying to do, and writes a merged
result that preserves both intents. When the two intents cannot both be kept it
does not guess: the file goes to `unresolved_files` with a one-line reason. A
real Opus escalation tier is tracked as the follow-up in KI-AR-004.

---

## 7. Post-Resolution Hook Compliance

Before declaring a file resolved, the agent enforces:

- **Ticket files** (`tickets/**/*.md`): frontmatter must contain `title`,
  `status`, `components`, `created`, `priority` — all present and non-empty.
  A file that fails this check is moved to `unresolved_files`, not `resolved_files`.
- **Python files**: no conflict marker (`<<<<<<`, `=======`, `>>>>>>>`) may
  remain. The agent runs `grep -c "<<<<<<" <file>` and aborts the resolution
  (moves to `unresolved_files`) if the count is non-zero.

---

## 8. What This Agent Does NOT Do

- Does not commit or push — resolution stops at `git add`. The calling
  `pull-request` agent controls commit and push.
- Does not perform codebase search with search tools — it reads files and
  read-only git output only.
- Does not spawn sub-agents: it is permitted none.
- Does not modify files outside the conflicted working tree (no ticket moves,
  no README updates, no doc writes during a conflict resolution run).

---

## 9. Cross-Links

- [`.claude/agents/conflict-resolver.md`](../../../.claude/agents/conflict-resolver.md) —
  the Sonnet gatekeeper agent file.
- [`docs/agents/conventions.md`](../conventions.md) — Gatekeeper Escalation
  pattern (§5.3); tool allowlists (§4).
- [`docs/architecture/adrs/ADR-033-agent-model-tiers.md`](../../architecture/adrs/ADR-033-agent-model-tiers.md) —
  Gatekeeper Escalation pattern (§2.3); strict-research-delegation (§2.6).
- [Ticket 11](../../../tickets/09_done/EPIC-CodingAgents/11_conflict_resolver_agent.md) —
  the ticket that shipped this agent.
- [Ticket 12](../../../tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md) —
  `pull-request` agent, the only legitimate caller.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
