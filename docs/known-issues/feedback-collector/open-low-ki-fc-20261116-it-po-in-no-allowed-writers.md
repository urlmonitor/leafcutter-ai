---
title: "KI-FC-20261116-it-po-in-no-allowed-writers — it-po is in no category's allowed_writers, so the ticket comment check-ac-limits sends it to write can only record feedback-id: (submit-failed)"
description: "medium — submit_feedback.py refuses it-po for every category ('Phase it-po is not an allowed writer for category complete'). The INF-100c-5 build check that closed KI-FC-003 only covers agents with signoff: true, and it-po sets signoff: false, so nothing catches the gap. check-ac-limits still names it-po as its fix agent, and its override needs an IT PO review recorded as a ticket comment, which check-feedback-id requires to carry a feedback-id. product-owner, business-analyst and test-designer are in no list either."
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector.md
  - docs/known-issues/README.md
  - docs/known-issues/feedback-collector/resolved/resolved-low-ki-fc-003.md
---

# KI-FC-20261116-it-po-in-no-allowed-writers — `it-po` is in no category's `allowed_writers`

> Index: [feedback-collector.md](../feedback-collector.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below.

- **Severity:** medium. The refusal is loud (exit 1, an `ERROR:` line) and the `(submit-failed)` fallback keeps the commit moving. But every `it-po` record is lost, and this is the same class KI-FC-003 was meant to close: the class check has a hole.
- **Status:** open, no AC.
- **Occurrences:** 1 (DIAGraph clone `srf-commit-clone`, 2026-11-16) · **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where:** `templates/config/feedback_categories.yaml` (deployed `.leafcutter/config/feedback_categories.yaml`; the repo copy `config/feedback_categories.yaml` is the same). All nine `allowed_writers` lists (`:31`, `:62`, `:93`, `:102`, `:135`, `:168`, `:202`, `:211`, `:243`) leave out `it-po`. `grep -c` for `it-po|product-owner|business-analyst|test-designer` returns 0 in both copies on `origin/main` `8d76d670a`. The refusal is `templates/scripts/feedback/feedback_validation.py` `validate_writer()` (`:72-86`), called from `submit_feedback.py` `main()` (`:470`). The check that misses it is `scripts/build_phases_feedback_writers.py` `_collect_signers()` (`:88-110`).

## Mechanism

1. INF-100c-5 (the KI-FC-003 class fix) fails the build for any agent that signs off but is in no list. "Signs off" means `signoff: true` in the agent's frontmatter (`_collect_signers`, `:106`).
2. `templates/agents/it-po.md:29` sets `signoff: false`, and so do `product-owner.md`, `business-analyst.md` and `test-designer.md`. The check never looks at them.
3. `it-po` is still sent to write ticket comments. `check_ac_limits.py` names it as the fix agent (`"fix_agent": "it-po"`, `templates/scripts/commit_guardian/hooks/check_ac_limits.py:488`). Its escape hatch, `ac_limit_override: true`, "requires IT PO review" (`:522-523`).
4. That review lands as a `### … — it-po (status: ok)` ticket comment. `check_feedback_id.py` requires a `feedback-id:` line under every new comment heading (`_find_violations`, `:188`). `submit_feedback.py` refuses `it-po` for every category, so the only id it can record is `(submit-failed)`.
5. `validate_writer` runs before the sink is resolved (`submit_feedback.py:470` before `:478`). So in an install whose sink is also unusable, `it-po` sees this refusal first, not the sink one.

## Seen

In the DIAGraph session transcript `feeb7c15…jsonl` (line 4595), an `it-po` subagent set `ac_limit_override: true` on `tickets/01_todo/TICKET-20261022-AGT-300g-1-i.md` in the clone. It reported that stderr read `ERROR: Phase 'it-po' is not an allowed writer for category 'complete'.` and that it recorded `feedback-id: (submit-failed)`. The same install's sink declaration is also stale (see KI-BP-20261116-tracked-sink-declaration-stays-stale), so this record would not have been written even with `it-po` allowed. DIAGraph's older pin printed the allowed list in the error. On main it no longer does (`feedback_validation.py:82`).

**Also missing:** `product-owner`, `business-analyst` and `test-designer` are in no list. None of their templates mentions `submit_feedback` or `feedback-id`, and no refusal has been seen for them. They would hit the same refusal as soon as one is asked to write a ticket comment.

## Fix direction

- Add `it-po` to the six broad categories: `complete`, `knowledge-gap`, `tooling-issue`, `convention-ambiguity`, `blocker` and `success-pattern`. Keep `quality-concern`, `subagent-quality` and `process-finding` restricted. Decide the same for `product-owner`, `business-analyst` and `test-designer`.
- Close the class, not the instance. The INF-100c-5 check should cover every agent that can be asked to write a ticket comment, not only agents with `signoff: true`. For example, it could cover every agent named as a `fix_agent` by a commit-guardian hook, or every registered agent, with an explicit opt-out.
