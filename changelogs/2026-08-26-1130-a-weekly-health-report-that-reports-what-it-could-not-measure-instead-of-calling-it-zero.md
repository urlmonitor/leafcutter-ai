---
title: "feat(agent-telemetry): a weekly health report that reports what it could not measure, instead of calling it zero"
date: "2026-08-26"
time: "11:30"
type: manual
components:
  - agent_telemetry
  - build_orchestration
summary: "A single command answers how healthy the system is week over week and whether delivery is speeding up, built from signals the build system cannot self-certify, and reporting a figure it failed to obtain as unknown rather than as a zero."
description: "Adds scripts/agent-health/weekly_health.py, a week-over-week delivery-health report grouped into trust, autonomy and velocity tiers plus a code-volume-by-language breakdown. Metrics come from git history, GitHub merge state and reopen events rather than from the AC store's own work_status field, because that field has a documented phantom-done history. Two silent-undercount defects were found and fixed while verifying the report against this repository."
breaking: false
---

## Entry

`python scripts/agent-health/weekly_health.py --weeks 8` now answers two questions in one
run: is the system healthier than last week, and is delivery speeding up. Output is
Markdown, JSON, or TSV.

**Why the metrics avoid the AC store's own status fields.** Every "done" signal this
system emits has a documented history of being wrong — 46 criteria were reopened in the
week to 2026-08-26, and `KI-ACS-004` ("an AC is marked `done` with no link to the code
implementing it") stands at 18 occurrences. A report built on `work_status` would measure
the rate at which the system produces claims, not capability. So the numerator comes from
git history and GitHub merge state, and the trust tier is anchored on **reopen events** —
trusted precisely because a reopen is a confession: the store only ever records one
against its own prior claim.

Three tiers print in dependency order, and the ordering is the point. Tier 1 (trust:
reopen rate, known-issue drain, repeat defects) gates tier 3 (velocity: net verified
criteria, feature share, production-code density, cycle time), because velocity measured
over an untrusted store is fiction. Tier 2 (autonomy) reads the telemetry sink. A fourth
section breaks code volume down by language, separating code from spec from prose.

**Unknown is never rendered as zero.** Two defects of exactly that shape were found by
running the report against this repository and comparing runs, and both are fixed:

| Defect | Symptom | Fix |
|---|---|---|
| Transient `gh` failure | TSV reported `0` merged PRs for every week, indistinguishable from "nothing merged" | PR counts are `None` when unobtainable — `—` in Markdown, empty in TSV, with a `prs_available` column carrying the fact |
| Capped GitHub result page | `--weeks 2` reported 51 PRs for the week of 2026-08-17 while `--weeks 8` reported 59 for that same week — `gh pr list` returns the N most recent merges repository-wide, so an under-provisioned `--limit` stops short without erroring | Budget raised to 250/week (min 400), and `pr_coverage_floor` detects a capped page and marks weeks beyond its reach unknown rather than undercounted |

A third defect was caught before it could produce a number: the store was initially keyed
by file path, so a criterion moving into a feature folder scored as one record filed and
another vanished — and, when the record was already closed, as newly done. Keying is now
by criterion identifier, with the birth-date index following suit so a move no longer
resets a criterion's age.

The autonomy tier currently reports **no lane data**: the sink holds 28 events, none of
them lane-run events. It says so, and names the reason, rather than printing a 0%
completion rate — an unwired emitter and a lane that fails every run are different facts
(`KI-BO-012`). The lane-event vocabularies are therefore provisional and flagged as such
in the README; they could not be verified against data that does not exist yet.

Lane aggregates reuse `build_lane_comparison_report` from `generate_health_report.py`
rather than re-reading the sink independently, so the two reports cannot disagree about
the same file.

54 unit tests cover the pure computations and the honesty guarantees — including that a
real zero still renders as `0` while an unmeasured figure renders empty.

**Known gap:** this landed without acceptance-criteria traceability, against the
`/plan-feature` → `/build-ac` rule in `CLAUDE.md`. ACs covering it are authored in a
follow-up rather than retrofitted into this entry.
