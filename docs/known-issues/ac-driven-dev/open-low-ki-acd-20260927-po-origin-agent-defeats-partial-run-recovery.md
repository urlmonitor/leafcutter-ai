---
title: "KI-ACD-20260927-po-origin-agent-defeats-partial-run-recovery — the product-owner template tells the PO to write the user's name into origin_agent, and partial-run recovery only recognises drafts whose origin_agent is an agent id, so a crashed run's PO drafts are never offered back"
description: "low — the PO template (<user's name>, examples 'Jamie') and the §PRR orphan qualifier (product-owner / business-analyst / it-po only) disagree. Observed as origin_agent: BrainCandy on six ACs in run wf_734389cf-248. Template and qualifier verified at main 93bd801c."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/reference/ac-schema.md
---

# KI-ACD-20260927-po-origin-agent-defeats-partial-run-recovery — the product-owner template tells the PO to write the user's name into origin_agent, and partial-run recovery only recognises drafts whose origin_agent is an agent id, so a crashed run's PO drafts are never offered back

- **Severity:** low. No data is lost, because the drafts stay on disk in the authoring worktree. But the recovery path built for them silently skips them, and the user re-authors or finds them by hand.
- **Status:** open. No AC.
- **Occurrences:** 1 run (`/plan-feature` `wf_734389cf-248`, 2026-09-25: all six ACs the product-owner stage wrote carried `origin_agent: BrainCandy`, the git user name. Session observation. The run ended `pause_persist_failed` and those drafts are not on main, so this is not re-verified here).
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/agents/product-owner.md:438`. The §PRR qualifier is at `scripts/ac_store/scan_ac_orphans.py:344-346`, `:462-467`, `templates/workflows-js/plan-feature.js:695-697` and `templates/skills/plan-feature/SKILL.md:295-298`.

## The mismatch (verified)

- **What the PO is told to write.** `product-owner.md:438`, handoff payload: `"origin_agent": "<user's name>"`. Every worked example writes a person's name, not the agent: `origin_agent: Jamie` at `:557`, `:584`, `:609`, `:634`, `:659`, `:684`. The field list at `:295` names `origin_agent` with no value rule. So the agent writing `BrainCandy` is following its template.
- **What recovery accepts.** `_AUTHORING_AGENTS = frozenset({"product-owner", "business-analyst", "it-po"})` (`scan_ac_orphans.py:344-346`). A record whose `origin_agent` is not in that set is skipped with `continue` (`:466-467`), and no message says why. The workflow's own in-body scan has the same set (`plan-feature.js:696-697`), and the skill's §PRR procedure says *"Check the `origin_agent` field. Accept only: `product-owner` / `business-analyst` / `it-po`"* (`SKILL.md:295-298`).
- **The PO is not even consistent.** `ACD-2500.yaml`, authored by the PO on 2026-09-25, carries `origin_agent: product-owner`. Whether a PO draft is recoverable depends on which of its two habits it follows.

## Not the defect: quick-fix

`templates/skills/quick-fix/SKILL.md:500` and `:526-528` deliberately set `origin_agent` to *"the committing user's identity; fall back to a recognised authoring agent name only when no human identity is available."* The schema allows any non-empty string (`config/ac_store_schema.json:121-125`), and `docs/reference/ac-schema.md:45` lists `BrainCandy (human author)` as a valid example. 1,588 ACs on main carry `origin_agent: BrainCandy`. So "a person's name in origin_agent" is legitimate in general. The defect is narrower: `/plan-feature`'s own PO stage writes a value that `/plan-feature`'s own recovery then refuses.

## Detection

After a `/plan-feature` run that stops mid-authoring, `grep -l '^origin_agent:' <authoring-worktree>/docs/acceptance-criteria -r` on the untracked or modified drafts. Any `readiness: draft` record with a non-agent `origin_agent` is invisible to §PRR. Nothing reports the skip.

## Workaround

Recover the drafts by hand from the authoring worktree. Or temporarily set their `origin_agent` to `product-owner` and re-run `/plan-feature` so §PRR offers them.

## Suggested fix

Pick one rule for `/plan-feature`'s own stages. Either (a) change `product-owner.md:438` and its examples to write `origin_agent: product-owner`, matching the BA and IT PO templates (`business-analyst.md:724` and others write `business-analyst`), or (b) qualify §PRR drafts by something the workflow controls (the run's own authoring branch or a run-id stamp) instead of a free-form provenance field. (a) is one prompt edit. (b) also covers quick-fix-style human values. Both qualifiers (Python and JS) must change together.

**Pattern:** a free-form provenance field reused as a machine filter by a reader that assumes the one writer it knows about.
