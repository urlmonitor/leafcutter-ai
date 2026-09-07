---
title: "Changelog 2833a3738 — specify the knowledge loop's caller and sink (INF-700a, INF-400c-4, ADR-040)"
date: "2026-09-07"
time: "11:07"
type: manual
components: 
  - knowledge_system
  - ac_store
summary: "Wrote the missing specification for how captured agent learnings get routed into the codebase, closing the last two gaps in the knowledge-capture loop — who calls the harvester and where its output lands — with no code changed yet."
description: "Single commit (2833a3738). Enriches acceptance criteria INF-700a (the harvester's caller, 5 child records) and INF-400c-4 (the sink path, 4 child records) under docs/acceptance-criteria/infrastructure/INF-400-agent-learning/, and adds ADR-040, which records that knowledge writes ride the completion path's own existing commit rather than getting a separate commit, branch, or PR of their own. Specification-only: no AC is marked done, and no source code or tests changed."
pr: 723
adrs: 
  - ADR-040
  - ADR-034
  - ADR-011
commits: 
  - 2833a3738
breaking: false
---

## Entry

Capture already emits a routable record (`INF-700b-1`, separate PR). Nothing routes it: the harvester has no caller, and the sink is a bare relative path resolved against whatever the caller's CWD happens to be. This commit (`2833a3738`) specifies both, and records the publication decision that had previously been answered only by implication.

**No code changed and no AC is marked done.** This is specification only — enriching acceptance criteria and adding an ADR.

### ADR-040 — knowledge writes ride the completion path's own commit

Learnings land in the normal worktree PR, alongside the work that produced them. The routing step creates no commit, no branch and no PR of its own.

This is **forced, not preferred**: `INF-700a-5`'s `test_a_unit_of_work_produces_the_same_number_of_commits_with_and_without_records_to_route` excludes every alternative by construction — a separate PR, an extra commit in the same PR, and a batched periodic PR all fail it identically, because it asserts the commit count is the same whether or not there was anything to route. Direct-to-main is moot under branch protection.

Authored as ADR-039 and renumbered to 040 before this commit — `check_adr_collision` found 039 already claimed by `ADR-039-fast-lane-occupied-workspace-refusal` on an in-flight remote branch, even though local `ls` and `adr_refs.py` both reported 039 free (both look only at what has landed).

Two dispatch anchors in the ADR's first draft were wrong and are recorded in the ADR as corrections rather than silently fixed: `phaseOrder` is a sort key, not a dispatch list (dispatch is driven by the ticket's own `agents:` frontmatter, and nothing will ever declare the new phase); and `build-epic.js` does not inherit `build-ticket.js`'s wiring — it dispatches the `ticket-supervisor` agent, which drives an independent ordering table of its own.

### The sink (`INF-400c-4` and children)

A build-generated config artefact carrying an absolute path, written by `build.py` from the target root it already resolves — a new build output needing a deploy-manifest entry, and one that must stay untracked (the same property that disqualified `paths.json`).

### The caller (`INF-700a` and children)

Five L2 acceptance criteria (unchanged in count) specify the manifest requirement: a parseable path list, written not attempted, empty-not-absent. `harvest_learnings.py` gains a required `--worktree` argument.

Refs: `INF-700a`, `INF-400c-4`, `ADR-040`, `ADR-034`, `ADR-011`
