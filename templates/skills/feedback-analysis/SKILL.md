---
name: feedback-analysis
description: >
  Read-side analysis pipeline for the Central Feedback Collection System.
  Provides trend_report.py — an orchestrator that calls aggregate.py and
  list_tags.py, groups results by category, runs trend detection, and produces
  a prioritized report structure. Use when an operator wants an on-demand
  "inbox triage" view of accumulated feedback data across all categories,
  without requiring a completed epic. Distinct from retrospective-agent, which
  requires an EPIC-Name and produces a full post-epic analysis document.
allowed-tools: Bash, Read
---

# feedback-analysis

This skill provides the read-side analysis pipeline for the Central Feedback
Collection System (CFCS). It enables operators and the `feedback-analyst` agent
to generate a prioritized, cross-category report from `feedback.jsonl` at any
time — no completed epic required.

---

## §1 Overview

The feedback write side is handled by `scripts/feedback/submit_feedback.py`,
which appends JSONL entries to `debugging/logs/feedback.jsonl`. Two read-side
query scripts already exist:

- `scripts/feedback/aggregate.py` — filters entries by ticket, category, phase,
  date range, and source; returns JSON or table output. The authoritative query engine.
- `scripts/feedback/list_tags.py` — tag-frequency counter, optionally filtered by
  category.

This skill adds the analysis layer on top of those two scripts:

- `templates/skills/feedback-analysis/scripts/trend_report.py` — orchestrator
  that calls `aggregate.py` and `list_tags.py`, runs cross-category aggregation,
  optional trend detection (week-over-week), and produces a prioritized report.

**What this skill does NOT do:**

- It does not write to `feedback.jsonl` or any other data file.
- It does not create tickets automatically (it presents recommendations for
  user approval only).
- It does not replace `retrospective-agent` (which requires a completed epic
  and produces a full retrospective document).

---

## §2 Quick Start

**Basic report (all data, text output):**

```bash
python .claude/skills/feedback-analysis/scripts/trend_report.py
```

**Report limited to the last 30 days with trend indicators:**

```bash
python .claude/skills/feedback-analysis/scripts/trend_report.py \
  --since 2026-05-01 \
  --trend week
```

**JSON output, single category:**

```bash
python .claude/skills/feedback-analysis/scripts/trend_report.py \
  --category tooling-issue \
  --format json
```

---

## §3 Available Scripts

| Script | Description | CLI Signature |
|---|---|---|
| `trend_report.py` | Orchestrates aggregate.py + list_tags.py; produces prioritized cross-category report with optional trend detection. | `[--jsonl PATH] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--category ID] [--trend week\|month\|none] [--format text\|json] [--top-tags N]` |
| `scripts/feedback/aggregate.py` | Low-level JSONL filter and query engine. Filters by ticket, category, phase, date range, source. | `[--ticket PATH] [--category ID] [--phase AGENT] [--since DATE] [--until DATE] [--source agent\|hook] [--format json\|table]` |
| `scripts/feedback/list_tags.py` | Tag-frequency counter. Returns most-common tags, optionally by category. | `[--category ID] [--top N] [--jsonl PATH]` |

**Reuse contract:** `trend_report.py` MUST NOT re-implement data loading or
filtering logic already present in `aggregate.py` or `list_tags.py`. It calls
those scripts (via direct import or subprocess) and adds aggregation, trend
detection, and report generation on top.

---

## §4 Category Reference

All nine feedback categories from `config/feedback_categories.yaml`:

| Category | Default Severity | Actionable Signal |
|---|---|---|
| `knowledge-gap` | medium | Missing docs or context — create doc tickets for the flagged topics |
| `convention-ambiguity` | medium | Unclear rules — clarify in the relevant SKILL.md or CLAUDE.md |
| `tooling-issue` | medium | Broken hooks/scripts — fix the identified tool failures |
| `quality-concern` | high | Code quality regressions — flag for pr-reviewer follow-up |
| `blocker` | high | Recurring blockers — surface recurring external dependencies |
| `subagent-quality` | medium | Weak phase agents — feeds agent trust ladder review |
| `success-pattern` | low | Patterns worth codifying — propose new knowledge items |
| `complete` | low | Baseline volume metric — not actionable alone |
| `process-finding` | low | Hook-detected violations — flags process drift |

**Priority score formula:** `count × severity_weight` where `high=3, medium=2, low=1`.

The Prioritized Action Items section of the report ranks actionable categories
by this score, so high-severity categories with even modest counts outrank
low-severity categories with higher counts.

---

## §5 Report Interpretation

### Reading the Prioritized Action Items output

Each action item in the report includes:

- **Category name** — which feedback bucket this covers.
- **Count** — total entries in the filtered date range.
- **Score** — `count × severity_weight`; higher = more urgent.
- **Recommendation** — a one-line suggested next step including the top tags
  (e.g. "Open doc tickets for these topics: missing-readme, no-adr, stale-skills").

**Translating categories to concrete next steps:**

| Category | Concrete next step |
|---|---|
| `knowledge-gap` | Open a `documentation-expert` ticket for each of the top 3 tags. |
| `convention-ambiguity` | Edit the relevant SKILL.md to add a clarifying rule, or open a ticket targeting the ambiguous section. |
| `tooling-issue` | Reproduce the tool failure locally, open a fix ticket with the failing hook name as context. |
| `quality-concern` | Review the flagged entries with `pr-reviewer`; open a rework ticket if the issue persists. |
| `blocker` | Surface the top blocker tags to the project owner as a dependency list. |
| `subagent-quality` | Cross-reference the flagged agent name(s) against recent retrospectives; consider a retry-cap reduction or a targeted agent improvement ticket. |

### Trend indicators

When `--trend week` is set, each category row shows `rising`, `stable`, or
`falling` based on comparing the current 7-day window against the previous 7-day
window:

- `rising`: current count > previous count by more than 20%.
- `falling`: current count < previous count by more than 20%.
- `stable`: change within ±20%.

A **rising** `tooling-issue` trend signals that hook failures are increasing and
warrants immediate investigation. A **falling** `knowledge-gap` trend indicates
that documentation efforts are reducing agent confusion.

---

## §6 Integration with retrospective-agent

`feedback-analyst` (which loads this skill) and `retrospective-agent` serve
different purposes:

| Aspect | `feedback-analyst` / this skill | `retrospective-agent` |
|---|---|---|
| **Trigger** | Any time; operator invokes `/feedback-report` | After an epic completes |
| **Input** | The full `feedback.jsonl` corpus (or filtered window) | A specific `EPIC-Name` |
| **Output** | Operational "inbox triage" report: what needs attention today | Full retrospective document with KIs, friction points, what went well |
| **Scope** | Cross-epic, cross-agent, cross-category | Single epic, all tickets |
| **Creates tickets** | Never (presents recommendations for user approval only) | Never directly (but retrospective doc informs future ticket creation) |

Use `feedback-analyst` for routine operational triage between epics. Use
`retrospective-agent` for end-of-epic analysis and knowledge capture.
