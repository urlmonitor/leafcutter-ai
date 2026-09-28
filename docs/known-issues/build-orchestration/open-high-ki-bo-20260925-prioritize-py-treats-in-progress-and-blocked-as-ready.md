---
title: "KI-BO-20260925-prioritize-py-treats-in-progress-and-blocked-as-ready — the ticket-prioritizer skill's prioritize.py excludes only done/deferred, so in-progress and blocked tickets are offered as ready"
description: "high — the script behind /pick-next-ticket re-implements selection with a hand-rolled YAML parser and folder-position done detection, instead of ticket_prioritizer.py's EXCLUDED_STATUSES; the same 'omit only done' defect as KI-BO-20260907-0804, in a second place."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260907-0804.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260907-0803.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-BO-20260925-prioritize-py-treats-in-progress-and-blocked-as-ready — the ticket-prioritizer skill's prioritize.py excludes only done/deferred, so in-progress and blocked tickets are offered as ready

- **Severity:** high. A parked or already-driven ticket can be picked and re-driven.
- **Status:** open — no AC. Code read 2026-09-25.
- **Where:** `templates/skills/ticket-prioritizer/scripts/prioritize.py:30` (`DONE_DIR_NAMES`), `:207-218` (`_is_done`: `status in ("done", "deferred")` or folder position), `:309-350` (ready partition), `:64-135` (hand-rolled YAML parser).

## Mechanism

The ready partition skips only nodes where `node["done"]` is true. `_is_done` is true for `done`/`deferred` or a
`done/`-style folder; `in_progress` and `blocked` fall through to ready. Folder position as a done signal
contradicts BO-400a-4, which the skill's own SKILL.md cites.

## Fixed here, not there

`scripts/ticket_prioritizer.py:41-44` already has the right sets (`DONE={done,deferred}`,
`EXCLUDED={done,in_progress,blocked,deferred}`), and KI-BO-20260907-0804 notes it is "not wired up" for the
build-feature planner. `prioritize.py`, documented in the same SKILL.md (`:46-52` vs `:109-145`), was not
mentioned there and carries the same defect. Five status vocabularies coexist (`set_ticket_status.py:49-72`,
`ticket_frontmatter_guard.py:27`, `config/ticket_lifecycle.json`, `check_ticket_state_integrity.py:84-135`,
`roadmap_query.py:41`) — KI-BO-20260907-0803.

## Fix direction

Delete `prioritize.py`'s selection logic in favour of `ticket_prioritizer.get_ready_tickets`; load all status sets
from one `ticket_lifecycle` module over `config/ticket_lifecycle.json`. Cluster 10 of the 2026-09-25 duplication
analysis.
