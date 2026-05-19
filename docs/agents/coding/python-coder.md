---
title: "Agent Reference: python-coder"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "tickets/09_done/EPIC-CodingAgents/Master_Plan.md"
  - "tickets/09_done/EPIC-CodingAgents/06_python_coder_agent.md"
related_code:
  - ".claude/agents/python-coder.md"
  - ".agents/workflows/python-coder.md"
---

# Agent Reference: `python-coder`

Visibility class: **User-facing** — auto-triggers on Python implementation requests.
Implementing agent: `python-coder` (Sonnet).
Family: `coding/`.

This doc explains **when to use** the agent, **the required-skills checklist**,
**the research-delegation table**, and a **walked example**.

---

## 1. When to Use

Fire `python-coder` whenever a task produces new or edited Python files.

| Trigger | What happens |
|---|---|
| "Implement ticket X in Python" | Agent loads ticket, pre-flight docs, then codes |
| "Write the code for Y" | Agent auto-fires via description |
| "Refactor module Z" | Agent auto-fires; runs complexity-reduction automatically |
| Ticket touches `collector/` paths | Agent auto-picks `collector-enforcer` before writing |

Do **not** invoke `python-coder` for:

- Raw `.sql` files — use `sql-coder`.
- Alembic migration files — use `sql-coder` (it delegates to `database-agent`).
- Architectural design questions — use `architect-review`.
- Cross-codebase search only — use `research-agent` directly.

---

## 2. Required-Skills Checklist

Every `python-coder` run is required to demonstrate the following skills were
invoked. The **Completion Report** at the end of each run documents the result.
The orchestrator (or the user) may refuse to mark a ticket "done" if any row is
missing.

| Skill | When invoked | Required? |
|---|---|---|
| `doc-enforcer` | After every edit pass, before declaring done | Always |
| `complexity-reduction` | For any function flagged over the complexity threshold | Always (when flagged); skip only when zero functions are flagged |
| `collector-enforcer` | When any edited path falls under `collector/` | Conditional — auto-picked by agent |
| `code-analysis` | When an AST-driven refactor is requested | On demand |
| `research-agent` | When a cross-file or symbol-level question arises | On demand |

---

## 3. Delegation Table

| Question type | Delegate to | Via |
|---|---|---|
| "Every caller of function X" | `research-agent` | `Agent` tool (`get_blast_radius`) |
| "Current signature of class Y" | `research-agent` | `Agent` tool (`get_symbol`) |
| "Which files import module Z" | `research-agent` | `Agent` tool (`find_importers`) |
| "Does this SQL procedure exist?" | `research-agent` | `Agent` tool (then stop-and-ask if SQL edit needed) |
| "AST structure of function W" | `code-analysis` skill | `Skill` tool |
| "Collector structural rules" | `collector-enforcer` skill | `Skill` tool |

Do **not** attempt to answer cross-file questions via guessing. The tools `Grep`,
`Glob`, and all MCP search tools are removed from `python-coder`'s allowlist.
Delegation is mandatory.

---

## 4. Walked Example

**Task**: "Implement ticket 42 — add `p_min_volume` filter to `CandleScoreWorker`"

**Step 1 — Pre-flight reads**

Agent reads:
- `tickets/00_inbox/TICKET-42-CandleScoreWorker.md`
- `docs/conventions/` (scans; reads relevant files)

No ADR is cited in the ticket, so no ADR reads.

**Step 2 — Research delegation**

Agent needs to know every caller of `CandleScoreWorker.run()` before changing its
signature. It spawns `research-agent`:

```
Agent tool call:
  subagent_type: agent
  agent: research-agent
  prompt: "Find every caller of CandleScoreWorker.run() in the codebase.
           Use get_blast_radius. Return the file paths and call sites."
```

`research-agent` returns: `app_launcher.py:87`, `unit_tests/…/test_worker.py:34`.
Agent notes these in its working context; it does NOT include raw search output in
the final response — only the summary: "2 callers found; both pass `**kwargs`; no
signature change required."

**Step 3 — collector-enforcer**

`CandleScoreWorker` lives under `collector/workers/`. Agent invokes
`collector-enforcer` via the `Skill` tool before writing a line.

**Step 4 — Implementation**

Agent edits `collector/workers/candle_score_worker.py`. The change is a new
`p_min_volume` keyword argument with a default; it adds a guard clause inside
`run()`.

**Step 5 — Tests**

```bash
python unit_tests/live_trader/test_candle_score_worker.py
# Result: 4 tests, 0 failures, 0 errors (1.2s)
```

**Step 6 — Pre-completion checks**

Agent invokes `doc-enforcer` on `collector/workers/candle_score_worker.py`.
`doc-enforcer` flags: missing `ARCHITECTURE:` field in module docstring. Agent
fixes it. Second run: pass.

Agent invokes `complexity-reduction` — `run()` is at cyclomatic complexity 6,
within threshold. No refactor needed.

**Step 7 — Response payload**

```
## Completion Report

### Files changed
- collector/workers/candle_score_worker.py: added p_min_volume filter with default None

### Skills run
- doc-enforcer: 1 violation fixed (ARCHITECTURE: field missing in module docstring)
- complexity-reduction: pass (run() at CC=6, threshold=10)
- collector-enforcer: invoked — no violations
- research-agent: 1 query (blast radius of CandleScoreWorker.run()); 2 callers found, no signature impact

### Tests
- Command: python unit_tests/live_trader/test_candle_score_worker.py
- Result: pass (4 tests, 1.2s)

### Notes
None.
```

---

## 5. Stop-and-Ask Scenarios

`python-coder` will stop and ask (not self-resolve) in these cases:

| Scenario | What the agent says |
|---|---|
| Task requires editing a `.sql` file | "SQL files are owned by `sql-coder`. Invoke `sql-coder` for the SQL portion." |
| `doc-enforcer` violations cannot be fixed without understanding intent | "doc-enforcer flagged X. I need clarification on Y before fixing." |
| `research-agent` returns ambiguous findings | "research-agent returned N candidates for X. Which should I edit?" |

---

## 6. Cross-Links

- [docs/agents/conventions.md](../conventions.md) — frontmatter schema (§1),
  file layout (§2), visibility classes (§3), tool allowlists (§4),
  strict-research-delegation (§4.2), nesting depth soft cap (§5.4).
- [docs/architecture/adrs/ADR-006-agent-model-tiers.md](../../architecture/ADR-006-agent-model-tiers.md) —
  model tier policy; Sonnet rationale; tool allowlist rule (§2.6).
- [tickets/09_done/EPIC-CodingAgents/Master_Plan.md](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md) —
  Phase 2 implementation plan; python-coder is ticket 06.
- [.claude/agents/python-coder.md](../../../.claude/agents/python-coder.md) —
  the agent file itself (frontmatter + system prompt).
- [tickets/09_done/EPIC-CodingAgents/06_python_coder_agent.md](../../../tickets/09_done/EPIC-CodingAgents/06_python_coder_agent.md) —
  the ticket that shipped this agent.
- [tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md](../../../tickets/09_done/EPIC-CodingAgents/07_sql_coder_agent.md) —
  `sql-coder`, the sibling agent that owns all SQL file changes.
- [tickets/09_done/EPIC-CodingAgents/00_research_agent.md](../../../tickets/09_done/EPIC-CodingAgents/00_research_agent.md) —
  `research-agent`, the delegation target for all cross-file searches.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
