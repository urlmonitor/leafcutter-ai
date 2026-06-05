---
title: "Create feedback-analysis skill, feedback-analyst agent, and /feedback-report command templates"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: slash_command
actuation_contract: "Invokes the feedback-analyst agent which reads debugging/logs/feedback.jsonl and prints a human-readable prioritized report of actionable findings to stdout, grouped by category with trend annotations."
files_touched:
  - templates/skills/feedback-analysis/SKILL.md
  - templates/skills/feedback-analysis/scripts/trend_report.py
  - templates/agents/feedback-analyst.md
  - templates/workflows/feedback-report.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: needed
ac_traceability:
  L0: INF-500
  L1: INF-500b
  l2:
    - INF-500b-1
    - INF-500b-2
    - INF-500b-3
    - INF-500b-4
    - INF-500b-5
    - INF-500b-6
  l3:
    - INF-500b-2-i
    - INF-500b-2-ii
    - INF-500b-3-i
  ac_path: docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500b.yaml
  routing: direct_to_ba
---

# Create feedback-analysis skill, feedback-analyst agent, and /feedback-report command templates

## Actor / Goal

In order to act on accumulated agent feedback rather than letting it sit unread
in `feedback.jsonl`, we need a dedicated read-side analysis pipeline — a skill,
an agent, and a slash command — so that operators can invoke `/feedback-report`
and receive a prioritized, actionable summary of what the feedback data says to
tackle next.

## Context

The feedback write side is fully wired: agents submit observations via
`scripts/feedback/submit_feedback.py`, which appends validated JSONL entries to
`debugging/logs/feedback.jsonl`. Two read-side scripts already exist:

- `scripts/feedback/aggregate.py` — filters entries by ticket/category/phase/date
  range/source; returns JSON or table output. The authoritative query engine.
- `scripts/feedback/list_tags.py` — tag-frequency counter, optionally filtered by
  category. Used by the signoff skill to surface common tags.

What does not exist is any agent, skill, or slash command for *analyzing and
interpreting* that data. The retrospective-agent (`templates/agents/retrospective-agent.md`)
calls `aggregate.py` as one step inside an epic retrospective workflow, but it is
tightly coupled to the epic lifecycle (requires an EPIC-Name argument) and produces
a full retro document rather than a lightweight "what's broken / what's trending"
report.

This ticket introduces the missing read-side pipeline:

1. **`templates/skills/feedback-analysis/`** — a standalone skill that knows how
   to invoke `aggregate.py` and `list_tags.py`, group results by multiple axes,
   run trend detection, and produce a prioritized report structure.

2. **`templates/agents/feedback-analyst.md`** — a read-only analyst agent that
   loads the feedback-analysis skill, runs the analysis scripts, interprets
   findings across all nine feedback categories, and returns a structured report
   with prioritized recommendations.

3. **`templates/workflows/feedback-report.md`** — a `/feedback-report` slash
   command that dispatches the feedback-analyst agent and returns the human-readable
   summary to the user.

### Feedback categories in scope

From `config/feedback_categories.yaml`:

| Category | Actionable signal |
|---|---|
| `knowledge-gap` | Missing docs or context — creates doc tickets |
| `convention-ambiguity` | Unclear rules — creates rule-clarification items |
| `tooling-issue` | Broken hooks/scripts — creates fix tickets |
| `quality-concern` | Code quality regressions — flags for pr-reviewer follow-up |
| `blocker` | Recurring blockers — surfaces recurring external deps |
| `subagent-quality` | Weak phase agents — feeds agent trust ladder review |
| `success-pattern` | Patterns worth codifying — proposes new KIs |
| `complete` | Baseline volume metric — not actionable alone |
| `process-finding` | Hook-detected violations — flags process drift |

### Reuse contract

The skill MUST NOT re-implement data loading or filtering logic already present in
`aggregate.py` or `list_tags.py`. The canonical approach:

```bash
python scripts/feedback/aggregate.py --format json [filters...]
python scripts/feedback/list_tags.py [--category <id>] [--top N]
```

The `trend_report.py` script in the skill's `scripts/` directory acts as an
orchestrator that calls these scripts (via subprocess or direct import) and adds
cross-category aggregation, trend detection (week-over-week or by epoch), and
report generation. It does not duplicate the JSONL reading or filtering logic.

### Relationship to retrospective-agent

`feedback-analyst` is NOT a replacement for `retrospective-agent`. The
retrospective-agent requires a completed epic, produces a full retro document, and
is part of the epic lifecycle. `feedback-analyst` is invocable at any time against
the entire feedback corpus (or a time window), and produces an operational
"inbox triage" report — what needs attention today, regardless of which epic
generated the signal.

## Acceptance Criteria

```gherkin
Given the build system has deployed the leafcutter package
When the deploy target is inspected
Then .claude/skills/feedback-analysis/SKILL.md exists
And .claude/skills/feedback-analysis/scripts/trend_report.py exists
And .claude/agents/feedback-analyst.md exists
And .claude/commands/feedback-report.md exists

Given feedback.jsonl contains at least one entry per category
When trend_report.py is run with no filters
Then it exits 0
And it prints a prioritized report with at minimum one section per non-zero category
And each section contains at minimum one actionable recommendation

Given feedback.jsonl contains entries spanning at least 7 days
When trend_report.py is run with --trend week
Then the output includes a trend indicator (rising/stable/falling) for each category

Given feedback.jsonl is empty or absent
When trend_report.py is run
Then it exits 0 and prints "(no feedback data found)"

Given a user invokes /feedback-report
When the feedback-analyst agent is dispatched
Then it reads feedback.jsonl via the analysis scripts
And returns a structured report to the user without modifying any file

Given the /feedback-report command is invoked with --since 2026-05-01
When the feedback-analyst filters by date
Then only entries on or after 2026-05-01 appear in the report
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Smoke Fixture

```yaml
surface: feedback-report
fixture_input: |
  (invoke /feedback-report with no arguments; feedback.jsonl may be empty)
assertion: "(?i)(no feedback data found|prioritized report|knowledge.gap|tooling.issue)"
placeholder_signature: "(?i)(TODO|PLACEHOLDER|not implemented)"
```

## Comments

## Implementation Tasks

### python-coder — create trend_report.py

- [ ] Create `templates/skills/feedback-analysis/scripts/trend_report.py` with
  the following specification:

  **CLI interface:**
  ```
  python trend_report.py
    [--jsonl <path>]          # override feedback.jsonl path; default: auto-detect via aggregate.py default
    [--since <YYYY-MM-DD>]    # pass-through to aggregate.py
    [--until <YYYY-MM-DD>]    # pass-through to aggregate.py
    [--category <id>]         # limit report to one category
    [--trend week|month|none] # emit trend indicators; default: none
    [--format text|json]      # output format; default: text
    [--top-tags N]            # top-N tags per category in text report; default: 5
  ```

  **Behaviour:**
  1. For each feedback category in `config/feedback_categories.yaml`'s closed
     vocabulary (hardcoded list acceptable; categories are PR-gated), call
     `aggregate.py --category <id> --format json [--since ...] [--until ...]`.
     Import `aggregate.filter_entries` and `aggregate._build_summary` directly
     when running in-process; fall back to subprocess when the import path is
     unavailable (worktree vs deployed path difference).
  2. Build a per-category count table sorted descending by count.
  3. For actionable categories (`knowledge-gap`, `convention-ambiguity`,
     `tooling-issue`, `quality-concern`, `blocker`, `subagent-quality`), extract
     the top-N most frequent tags via `list_tags.count_tags()`, and list the
     top-3 most recent entry notes (truncated to 120 characters) as examples.
  4. When `--trend week` is set: compute the entry count for the current 7-day
     window vs the previous 7-day window. Emit `rising` (>20% increase),
     `falling` (>20% decrease), or `stable` for each category.
  5. Produce a "Prioritized Action Items" section that ranks categories by a
     combined score of: count × severity_weight (high=3, medium=2, low=1, per
     `default_severity` in `feedback_categories.yaml`). List the top-5 items
     with a one-line recommendation per category (e.g. for `knowledge-gap`:
     "Open doc tickets for these topics: <top-3 tags>").
  6. When `--format json`, output a JSON object with keys `summary`, `by_category`,
     `action_items`, and (when trend was computed) `trends`.
  7. When `feedback.jsonl` is absent or empty, print `(no feedback data found)`
     and exit 0.

  **No external deps beyond stdlib**. Re-use `aggregate.py` and `list_tags.py`
  imports; do not re-implement JSONL reading. Follow project error-handling policy
  (Rule 1–4 in CLAUDE.md): wrap file I/O, never bare except, never silent swallow.

  **DECISION HISTORY block** at the bottom following project convention.

### python-coder — create SKILL.md

- [ ] Create `templates/skills/feedback-analysis/SKILL.md` with:
  - YAML frontmatter: `name: feedback-analysis`, `description`, `allowed-tools: Bash, Read`
  - **§1 Overview** — what the skill does, what scripts it provides
  - **§2 Quick Start** — three example invocations of `trend_report.py`
  - **§3 Available Scripts** — table listing `trend_report.py`, `aggregate.py`,
    `list_tags.py` with one-line descriptions and CLI signatures
  - **§4 Category Reference** — table of all nine categories, their default severity,
    and the actionable signal each represents (drawn from `feedback_categories.yaml`)
  - **§5 Report Interpretation** — how to read the Prioritized Action Items output
    and translate each category into a concrete next step
  - **§6 Integration with retrospective-agent** — note the distinction (this skill
    is for ad-hoc operational triage; retrospective-agent is for post-epic analysis)

### python-coder — create feedback-analyst agent template

- [ ] Create `templates/agents/feedback-analyst.md` with:
  - YAML frontmatter: `name: feedback-analyst`, `model: sonnet`,
    `tools: Bash, Read`, `portable: true`, `signoff: false`
  - `description` (in frontmatter): one-paragraph description for agent picker
  - Agent body with these sections:
    - **Role** — read-only analyst; never modifies any file; never creates tickets
      automatically (presents recommendations for user approval only)
    - **Step 1 — Parse arguments**: extract `--since`, `--until`, `--category`,
      `--trend`, `--format` from `$ARGUMENTS` if provided; default to no filters
    - **Step 2 — Load skill**: read `.claude/skills/feedback-analysis/SKILL.md`
    - **Step 3 — Run analysis**: invoke `trend_report.py` with the parsed arguments;
      capture stdout; if exit non-zero or output empty, note the error and proceed
      with partial data
    - **Step 4 — Interpret findings**: for each actionable category with count > 0,
      produce a one-paragraph interpretation and a concrete recommendation (open a
      doc ticket, fix a hook, clarify a rule, etc.)
    - **Step 5 — Render report**: output a human-readable Markdown report with
      sections: Executive Summary, Category Breakdown table, Prioritized Action Items
      (with suggested follow-up type per item), and Raw Trend Data (collapsible if
      `--trend` was used)
    - **Constraints**: read-only; never auto-apply suggestions; always present
      recommendations as a list for the user to act on

### python-coder — create /feedback-report command

- [ ] Create `templates/workflows/feedback-report.md` with:
  - YAML frontmatter: `description` — one sentence suitable for Claude Code's
    command picker
  - Body: `Invoke the \`feedback-analyst\` agent with the user's arguments: $ARGUMENTS`
  - A brief usage comment listing the supported pass-through flags
    (`--since`, `--until`, `--category`, `--trend week`, `--format json`)

### test-writer

- [ ] Write unit tests for `trend_report.py` in
  `unit_tests/test_trend_report.py` covering:
  - Empty / absent JSONL: exits 0, prints `(no feedback data found)`.
  - Single-category data: correct count, correct top tags extracted.
  - Multi-category data: categories sorted descending by count in output.
  - `--trend week` with data spanning two 7-day windows: trend direction computed
    correctly for rising (>20%), falling (>20%), and stable cases.
  - `--format json`: output is valid JSON with keys `summary`, `by_category`,
    `action_items`.
  - Priority score ordering: high-severity categories rank above equal-count
    low-severity categories in Prioritized Action Items.
  - Pass-through filters (`--since`, `--until`) are forwarded to `aggregate.py`
    and only matching entries are counted.

## Risk & Safety

- Touches money? No.
- Touches data? Read-only. `trend_report.py` and `feedback-analyst` never write to
  `feedback.jsonl` or any other data file. The only write side effect is standard
  output to the user's terminal.
- Reversibility? Fully reversible — all four files are new additions. Dropping the
  ticket leaves the current state (no analysis tooling) intact.
- Shared contract? `aggregate.py` and `list_tags.py` are imported by `trend_report.py`
  as library code. Their public API (`filter_entries`, `count_tags`, `_build_summary`)
  is stable. No changes to those scripts are required by this ticket.
- Build dependency? `templates/skills/feedback-analysis/` is a new skill directory.
  `build_skills()` in `build_phases.py` iterates `skills_template_dir.iterdir()` so
  the new folder is picked up automatically without code changes.
- Naming conflict? `templates/workflows/feedback-report.md` deploys to
  `.claude/commands/feedback-report.md`. Verify no existing command with that name
  exists before writing (current command list: see `templates/workflows/`).
