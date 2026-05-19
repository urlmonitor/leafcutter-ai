---
title: "Agent Reference: refinement"
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
  - "tickets/09_done/EPIC-CodingAgents/02_refinement_agent.md"
  - "docs/agents/coding/create-ticket.md"
related_code:
  - ".claude/agents/refinement.md"
---

# Agent Reference: `refinement`

Implementing agent: `refinement` (Sonnet, internal).
Invoked by: `create-ticket` (after the `business-analyst` pass, small path).
Family: `coding/`.

This doc explains **when to use** the agent, **the five-lens questioning
template**, **the delegation rule**, **the output contract**, and a fully
walked-through example showing vague input → concrete output.

---

## 1. When to Use

`refinement` is an **internal** agent. You never invoke it directly.
`create-ticket` spawns it (in parallel with `architect-review`) whenever the
business-analyst returns `deliverables_count <= 3`.

Do not invoke `refinement` directly. It has no slash command.

---

## 2. What It Does

Given a freshly framed ticket body whose Implementation Tasks are vague,
`refinement` works through five technical lenses for each task:

| Lens | Question answered |
|---|---|
| **Files touched** | Which source file(s) change? Full project-relative paths. |
| **Functions / call sites** | Which function changes? Which new function is written? Named with module/class prefix. |
| **Tests needed** | Which test file covers this? Is a SQL test needed (`_MANUAL`)? ≤5 s rule. |
| **Configs / migrations** | Alembic migration? SQL file reload? New `.env` variable? |
| **Doc updates** | Which doc needs a new section? Which convention file applies? |

Anything that cannot be resolved becomes an `open_questions` item. `refinement`
does NOT invent answers — it surfaces the question for the user.

---

## 3. Strict Delegation Rule

`refinement` does **not** carry `Grep`, `Glob`, or any MCP search tool.
All codebase lookups go through `research-agent` via the Agent tool.

```
Agent tool call:
  agent: research-agent
  prompt: "<narrow factual question>. Return file path, function name,
           and a one-paragraph summary. Do not return raw grep output."
```

This keeps the parent context clean (no raw tool dumps) and forces
`refinement` to pose narrow, answerable questions.

---

## 4. Project Conventions It Enforces

`refinement` appends a Conventions Checklist to every rewritten ticket so
the implementing coder sees the project rules immediately:

- **`doc-enforcer` skill** — audits Python and SQL docstrings before commit
  (`.claude/skills/doc-enforcer/SKILL.md`).
- **Pre-commit complexity rules** — cyclomatic complexity ≤ 10; the
  `precommit-autofix` skill dispatches a Sonnet code-review pass on
  non-trivial changes (`.claude/precommit-autofix.json`).
- **No file output to project directories in tests** — use `tmp_path`,
  `tempfile`, or `test_output_dir` fixture (`unit_tests/README.md`).
- **SQL changes require local-DB apply before SQL tests** — via
  `db.create_procedures()` or Alembic (`docs/database-domain.md`).

---

## 5. Output Contract

`refinement` returns a JSON block with two keys:

```json
{
  "rewritten_ticket_body": "<full markdown body — frontmatter unchanged, tasks concrete>",
  "open_questions": ["<unanswered technical decision>", "..."]
}
```

`create-ticket` merges this with `architect-review`'s output and, when either
agent returns open questions, consolidates them into a single user prompt
before finalising the ticket.

---

## 6. Walked-Through Example

### 6.1 Input

A stub ticket with one vague task:

```markdown
## Implementation Tasks
- [ ] Add CVD divergence to the worker
```

Business-analyst output (abridged):

```json
{
  "summary": "Enrich candle_context with CVD divergence signals",
  "deliverables_count": 1,
  "open_questions": [],
  "success_criteria": ["candle_context rows carry cvd_p5_15 and cvd_p95_15 keys after enrichment"]
}
```

### 6.2 What refinement does

**Step 1 — Files touched:** `refinement` does not know which file computes
CVD. It calls `research-agent`:

> "Where is CVD computed and where is the candle context worker that
> enriches candle_context records? Return file paths and key function names."

`research-agent` returns (summary):

> `CVD is computed in collector/services/indicators/cvd_calculator.py,
> function compute_cvd_delta(). The candle context worker is
> collector/services/candle_context/candle_context_worker.py;
> enrichment entry point: CandleContextWorker._enrich_batch().`

**Step 2 — Lenses applied:**

| Lens | Finding |
|---|---|
| Files touched | `collector/services/candle_context/candle_context_worker.py`, `collector/services/indicators/cvd_calculator.py` |
| Functions | Modify `CandleContextWorker._enrich_batch()`; call `compute_cvd_delta()` |
| Tests | Extend `unit_tests/live_trader/test_candle_context_worker.py` — ≤5 s, no TimescaleDB compression |
| Configs | None (no new schema column; key stored in JSONB `context` dict) |
| Docs | Check `docs/database-domain.md` Observability Surface section if any monitored column list changes |

**Step 3 — Open question:** the ticket says "HTF" but does not list which
intervals. `refinement` cannot resolve this from code alone.

### 6.3 Output

```json
{
  "rewritten_ticket_body": "---\n...(frontmatter unchanged)...\n---\n\n## Implementation Tasks\n- [ ] In `collector/services/candle_context/candle_context_worker.py`:\n      add a call to `compute_cvd_delta()` (from\n      `collector/services/indicators/cvd_calculator.py`) inside\n      `CandleContextWorker._enrich_batch()`. Store the result under\n      the divergence key `cvd_p5_15` / `cvd_p95_15` following the\n      directional-key convention in MEMORY.md (Divergence Keys section).\n- [ ] Extend `unit_tests/live_trader/test_candle_context_worker.py`\n      with a test for the new divergence key — must complete in ≤5 s;\n      no TimescaleDB compression.\n- [ ] Check `docs/database-domain.md` (Observability Surface section)\n      and update if any monitored column list changes.\n- [ ] Reload any changed `sql_functions/` procedure:\n      `db.create_procedures()` — see docs/database-domain.md.\n\n### Conventions Checklist (refinement-injected)\n- [ ] Run `doc-enforcer` skill before committing ...\n...",
  "open_questions": [
    "Should the CVD divergence key be computed for all HTF intervals or only 15 m and 1 D? The ticket says 'HTF' but does not name which intervals."
  ]
}
```

`create-ticket` surfaces the open question to the user, collects the answer,
then finalises the ticket with the concrete tasks already in place.

---

## 7. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — frontmatter schema (§1),
  tool allowlists + strict-research-delegation rule (§4.2), visibility classes (§3).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  upstream policy: tool allowlist (§2.6), visibility classes (§2.5).
- [`docs/agents/coding/create-ticket.md`](create-ticket.md) —
  the orchestrator that spawns `refinement`.
- [`.claude/agents/refinement.md`](../../../.claude/agents/refinement.md) —
  the agent file itself (frontmatter + system prompt).
- [`tickets/09_done/EPIC-CodingAgents/02_refinement_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/02_refinement_agent.md) —
  the ticket that shipped this agent.
- [`tickets/09_done/EPIC-CodingAgents/Master_Plan.md`](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md) —
  locked design decisions; strict-research-delegation rule.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
