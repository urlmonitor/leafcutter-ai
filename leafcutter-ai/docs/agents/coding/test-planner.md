---
title: "Agent Reference: test-planner"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-05-13
components:
  - infrastructure
related_docs:
  - "docs/agents/conventions.md"
  - "docs/agents/ticket-creation/business-analyst.md"
  - "docs/testing/README.md"
  - "leafcutter/config/skills_config.default.json"
related_code:
  - "leafcutter/templates/agents/test-planner.md"
---

# Agent Reference: `test-planner`

Visibility class: **internal** — spawned by `business-analyst` only.
Implementing agent: `test-planner` (Sonnet).
Family: `coding/`.

This doc explains **what the agent does**, **the structured payload it returns**,
and **how downstream agents consume it**.

---

## 1. Role and Boundaries

`test-planner` is the planning-phase test specialist. It runs inside the
ticket-creation pipeline, spawned by `business-analyst` after deliverables are
scoped.

Its sole job: produce a `test_requirements` JSON block that specifies which
tests should be written, what they cover, and where they live.

It does **not**:
- Write any test files (that is `test-writer`'s job).
- Run any tests (that is `test-runner`'s job).
- Write code or config files.
- Make implementation decisions.

It **may** spawn `research-agent` (via the Agent tool) for one narrowly scoped
purpose: finding the current signature of a function or determining whether an
existing test already covers a behavior.

---

## 2. Position in the Pipeline

```
create-ticket
  └─ business-analyst
       ├─ (optional) research-agent  ← scoping research
       ├─ spawns test-planner        ← you are here
       │     └─ returns test_requirements
       └─ returns unified BA payload (includes test_requirements)
```

The `test-planner` result flows into the BA payload, which flows into
`refinement` (for validation) and ultimately into the ticket body as the
`## Test Requirements` section.

---

## 3. Output Contract

`test-planner` returns **only** this JSON block:

```json
{
  "test_requirements": {
    "rationale": "<why these tests are needed or why none are>",
    "tests": [
      {
        "name": "test_<descriptive_name>",
        "description": "<one sentence: what observable behavior this test verifies>",
        "type": "unit|integration|manual",
        "target_dir": "unit_tests/<module>/",
        "covers": "<function, class, or behavior under test>"
      }
    ]
  }
}
```

| Field | Rule |
|---|---|
| `rationale` | Always present. One sentence explaining the testing strategy or why no tests are needed. |
| `tests` | Always an array. Empty for docs-only/config-only tickets. |
| `name` | Starts with `test_`. Matches `testing_context.naming_pattern`. |
| `description` | One sentence. Describes observable behavior, not implementation. |
| `type` | Exactly `"unit"`, `"integration"`, or `"manual"`. |
| `target_dir` | Must match `unit_tests/<key>/` from `testing_context.directories`, OR note `"new directory needed"`. |
| `covers` | Specific function, class, or behavior. Not a file path. |

---

## 4. Config Fallback Chain

The agent reads `testing_context` in priority order:

1. `.claude/skills_config.json` → `testing_context` key (project-specific).
2. `leafcutter/config/skills_config.default.json` (portable defaults).
3. Built-in fallback defaults (hardcoded in the template).

If `testing_context` is absent from `.claude/skills_config.json`, the agent
falls back gracefully — it never hard-fails on a missing config key.

---

## 5. When `tests` is Empty

For docs-only or config-only requests, `test-planner` returns:

```json
{
  "test_requirements": {
    "rationale": "All deliverables are documentation files; no executable logic changes.",
    "tests": []
  }
}
```

`business-analyst` propagates this empty array, and `ticket-wiring` renders
the `## Test Requirements` section with an empty table body (signalling
`test-writer` to skip).

---

## 6. Refinement Validation

`refinement` receives `test_requirements` in the BA payload and validates:

- Each `target_dir` resolves to an existing `unit_tests/` subdirectory (or
  is explicitly flagged `"new directory needed"`).
- Each `type` is consistent with the directory's `db_required` flag.
- Code-touching tickets with an empty `tests` array trigger an `open_questions`
  flag unless the `rationale` clearly explains the omission.

---

## 7. Example Output

**Request**: "Add a `p_min_volume` filter to `CandleScoreWorker`"

**Deliverables**: `collector/workers/candle_score_worker.py` (modified)

**test-planner output**:

```json
{
  "test_requirements": {
    "rationale": "CandleScoreWorker.run() has new conditional logic for p_min_volume; needs a unit test for the filter path and an edge-case test for None input.",
    "tests": [
      {
        "name": "test_candle_score_worker_volume_filter",
        "description": "CandleScoreWorker.run() filters out candles below p_min_volume when the parameter is set.",
        "type": "unit",
        "target_dir": "unit_tests/live_trader/",
        "covers": "CandleScoreWorker.run() — p_min_volume branch"
      },
      {
        "name": "test_candle_score_worker_volume_filter_none",
        "description": "CandleScoreWorker.run() applies no volume filter when p_min_volume is None.",
        "type": "unit",
        "target_dir": "unit_tests/live_trader/",
        "covers": "CandleScoreWorker.run() — p_min_volume=None default path"
      }
    ]
  }
}
```

---

## 8. Cross-Links

- [docs/agents/ticket-creation/business-analyst.md](../ticket-creation/business-analyst.md) — the parent that spawns test-planner.
- [docs/agents/coding/test-writer.md](test-writer.md) — consumes test_requirements to write test files.
- [docs/agents/coding/test-runner.md](test-runner.md) — runs the tests written by test-writer.
- [docs/testing/README.md](../../testing/README.md) — portable testing conventions.
- [leafcutter/templates/agents/test-planner.md](../../../templates/agents/test-planner.md) — the agent template itself.
- [leafcutter/config/skills_config.default.json](../../../config/skills_config.default.json) — default `testing_context` values.
