---
title: "Agent Reference: research-agent"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "CLAUDE.md"
  - "tickets/09_done/EPIC-CodingAgents/00_research_agent.md"
related_code:
  - ".claude/agents/research-agent.md"
---

# Agent Reference: `research-agent`

Implementing agent: `research-agent` (Sonnet, internal).
Family: `coding/` — central context-gathering hub.
Visibility: **Internal** — spawned only by other coding agents, never by the
user directly and never auto-triggered from prose.

This doc explains **when to call** the agent, the **three MCP search families**
it owns, the **dedicated-skill carve-outs**, **sample request/response payloads**,
and a **manual smoke-test** invocation example.

---

## 1. When to Call research-agent

Call `research-agent` whenever a spawned coding agent needs to answer a
cross-cutting codebase question and does not have `Grep`, `Glob`, or MCP search
tools in its own allowlist.

Per `docs/agents/conventions.md` §4.2 (strict research-delegation rule), the
following tools are **removed** from every non-research agent:

- `Grep`, `Glob`
- All `mcp__jcodemunch__*`
- All `mcp__plugin_serena_serena__*`
- All `mcp__plugin_context7_context7__*`

`research-agent` is the single agent that keeps these tools. It accepts a
structured question, searches with the full toolkit, and returns curated findings
— file paths with 1–3 line descriptions each and a synthesis paragraph. The
caller's context never sees raw `rg` output or raw MCP JSON.

### 1.1 Use research-agent when…

| Situation | Example question |
|---|---|
| You need to find where a function is called across the codebase | "Where is `populate_candle_context` wired into the worker loop?" |
| You need the blast radius of a planned rename | "What files import `CandleContextPopulator`?" |
| You need to understand a class hierarchy before extending it | "What does `BaseWorker` inherit from and who extends it?" |
| You need to find the canonical pattern for a new file type | "What does an existing SQL procedure file look like in `sql_functions/procedures/`?" |
| You need library or framework documentation | "Show me the TimescaleDB `time_bucket` function signature" |
| You need to verify a pattern exists before adding it | "Is there already a `candle_context` GIN index, and where?" |

### 1.2 Use a dedicated skill instead when…

Three existing skills own domain-specific query logic. Do **not** ask
`research-agent` to replicate them — invoke them via Bash:

| Situation | Dedicated skill |
|---|---|
| Which Python files import a specific symbol | `.claude/skills/import-scanner/SKILL.md` |
| Find the latest 1-minute candle near a price level | `.claude/skills/find-context-candle/SKILL.md` |
| Explain why a trade fired / what triggered the signal | `.claude/skills/trade-analysis/SKILL.md` |

These skills encapsulate domain-specific SQL and codebase knowledge.
`research-agent` calling them is fine; re-implementing them with raw Grep is not.

---

## 2. The Three MCP Search Families research-agent Owns

`research-agent`'s tools list explicitly grants the following MCP families. No
other coding agent carries these.

### 2.1 jcodemunch (`mcp__jcodemunch__*`)

Indexed symbol-level code retrieval and impact analysis. Use for:

- `get_blast_radius` — every file that would change if a function/class is
  renamed or deleted.
- `get_dependency_graph` — what a file imports and what imports it (up to 3 hops).
- `get_class_hierarchy` — inheritance chains across the codebase.
- `get_context_bundle` / `get_symbol` — retrieve one function from a large file
  without reading the whole file.
- `find_references` / `find_importers` — all usages of an identifier.
- `search_symbols` — symbol lookup by name across the codebase.

Prefer jcodemunch over raw Grep for cross-file impact analysis. See `CLAUDE.md`
§ "jCodeMunch MCP Server" for the full decision matrix that `research-agent`
mirrors in its tool decision table.

### 2.2 serena (`mcp__plugin_serena_serena__*`)

Language-server-backed symbol navigation. Use for:

- `find_declaration` — jump to the definition of a symbol.
- `find_implementations` — all concrete implementations of an interface or
  abstract method.
- `find_referencing_symbols` — who references this symbol.
- `search_for_pattern` — regex search with language-server context.
- `get_symbols_overview` — high-level symbol map of a file.

Use serena when jcodemunch's indexed results are stale (e.g., after a large
refactor not yet re-indexed) or when you need the precision of a live
language-server traversal.

### 2.3 context7 (`mcp__plugin_context7_context7__*`)

Current library and framework documentation. Use for:

- `resolve-library-id` — find the context7 identifier for a library.
- `query-docs` — fetch up-to-date API docs, configuration reference, or
  migration guides for any library.

Use context7 when the question involves third-party library behaviour (TimescaleDB
functions, SQLAlchemy ORM, pybit SDK, FastAPI routing, etc.). Training data may
be outdated; context7 fetches current docs.

---

## 3. Sample Request Payloads

### 3.1 Compact form

```
Q: where is the candle context populator wired into the worker?
```

### 3.2 Structured form

```json
{
  "question": "where is candle_context_populator wired into the worker loop?",
  "scope": "data_collector/",
  "depth": "shallow"
}
```

### 3.3 Deep blast-radius form

```json
{
  "question": "blast radius of renaming CandleContextPopulator to ContextPopulator",
  "scope": "codebase-wide",
  "depth": "deep"
}
```

---

## 4. Sample Response Payloads

### 4.1 Normal findings response

```
## Findings

### WorkerBase.register_populator
**Path**: `data_collector/workers/worker_base.py`
**Lines**: 42–61
`register_populator` accepts a populator instance and schedules it inside the
worker's per-candle callback chain. This is the wiring point for all context
populators including `CandleContextPopulator`.

### CandleContextPopulator.__init__
**Path**: `data_collector/populators/candle_context_populator.py`
**Lines**: 1–28
Initialises the populator with a DB session and the level-proximity threshold.
Registered into the worker in `app_launcher.py` during startup.

### app_launcher.py (startup block)
**Path**: `app_launcher.py`
**Lines**: 88–104
Constructs a `CandleContextPopulator` and calls
`worker.register_populator(populator)` before the event loop starts.

## Synthesis

The candle context populator is wired in at startup: `app_launcher.py` (lines
88–104) constructs a `CandleContextPopulator` and registers it with the worker
via `WorkerBase.register_populator`. The registration method appends the populator
to the per-candle callback chain in `worker_base.py` (lines 42–61), so the
populator runs on every completed 1-minute candle. No dynamic rewiring happens
at runtime.
```

### 4.2 Ambiguity response

```
## Clarification Needed

The phrase "trader code" could refer to several distinct parts of the codebase.

Candidate interpretations:
1. `live_trader/main.py` — the WebSocket-driven live trading engine entry point.
2. `trader_bot/` — the Docker service that runs the live trader container.
3. `trading_model/` — the ML model training and prediction pipeline.

Which do you mean? (reply with the number or restate the question)
```

### 4.3 No results response

```
## Findings

None found matching "GIN index on candle_context".

## Synthesis

No results. Possible reasons: the index may not yet exist, or it may be defined
inline in an Alembic migration rather than as a standalone SQL file. Suggested
next step: search `alembic/versions/` for `gin` or `candle_context` to check
migration history.
```

---

## 5. Manual Smoke-Test (no automated harness)

There is no automated test harness for `research-agent`. The following is a
manual invocation example you can use to verify the agent behaves correctly after
modifying it.

### 5.1 Setup

Open a Claude Code session in the project worktree. Ensure `research-agent` is
present at `.claude/agents/research-agent.md`.

### 5.2 Test: normal question

Invoke via the Agent tool (or from a parent agent) with:

```
Q: where is the candle context populator wired into the worker?
```

**Expected**: response contains `## Findings` with 2–5 file entries (each with
path + 1–3 line description) and a `## Synthesis` paragraph that names the wiring
location. Response does **not** contain raw `rg` or grep output lines.

### 5.3 Test: ambiguous question

Invoke with:

```
Q: find the trader code
```

**Expected**: response contains `## Clarification Needed` with a paragraph
explaining the ambiguity and 2–3 numbered candidate interpretations. Agent does
**not** start searching.

### 5.4 Test: skill delegation

Invoke with:

```
Q: which Python files import CandleContextPopulator?
```

**Expected**: agent recognises this as an import-scanner question and either:
(a) invokes `.claude/skills/import-scanner/SKILL.md` via Bash and summarises the
result, or (b) answers via jcodemunch `find_importers` and returns curated
findings (not raw output).

---

## 6. Interaction with Conventions

`research-agent` is the single carve-out from the strict research-delegation rule
in `docs/agents/conventions.md` §4.3. All other coding agents lose `Grep`, `Glob`,
jcodemunch, serena, and context7. `research-agent` keeps them because its whole
job is research — without the tools the rule would be self-defeating.

The user-facing Opus session is also exempt from the rule (§4.3 carve-out #1):
the user steers that session directly, so it keeps search tools. The rule applies
only to spawned agents under `.claude/agents/`.

For the full rationale (context isolation, payload size, cost), see
[ADR-006 §2.6](../../architecture/ADR-006-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation).

---

## 7. Cross-Links

- [`docs/agents/conventions.md`](../conventions.md) — §4.2 (strict
  research-delegation rule), §4.3 (carve-outs), §1 (frontmatter schema),
  §3.3 (internal visibility class).
- [`docs/architecture/adrs/ADR-006-agent-model-tiers.md`](../../architecture/ADR-006-agent-model-tiers.md) —
  §2.6 (tool allowlist + research-delegation rationale), §2.5 (visibility
  classes), §2.1 (three-tier model ladder).
- [`CLAUDE.md`](../../../CLAUDE.md) — § "jCodeMunch MCP Server": the canonical
  decision matrix that `research-agent`'s tool table mirrors.
- [`tickets/09_done/EPIC-CodingAgents/00_research_agent.md`](../../../tickets/09_done/EPIC-CodingAgents/00_research_agent.md) —
  the ticket that shipped this agent.

[EPIC-CodingAgents]: ../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
