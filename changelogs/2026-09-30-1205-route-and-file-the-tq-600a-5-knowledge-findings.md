---
title: "Route and file the TQ-600a-5 knowledge findings"
date: "2026-09-30"
time: "12:05"
type: manual
components: 
  - knowledge_management
  - ac_driven_dev
  - build_orchestration
  - commit_guardian
summary: "Files three new known issues, corrects an understated occurrence count, and adds a CLAUDE.md rule that a repo convention outranks a ticket's own test_spec."
description: "Five findings from the TQ-600a-5 drive routed through the route-knowledge decision tree and applied. CLAUDE.md's Verify Behaviorally Not by Grep section gains an explicit rule that the convention outranks a ticket's own type and angle declaration, because the same authoring pass writes both the weak test and the spec that blesses it; the pytest 9.0.3 strict-markers instance is recorded as the evidence, and the growth was paid for by compressing adjacent prose rather than skipping the doc-length gate. KI-ACD-20260929 files a cross-field dependency cycle that is invisible to two tools at once: the ticket generator now treats expects_from as an ordering edge and warns when it drops one, while check_ac_circular_deps.py contains zero occurrences of expects_from, so the tool that believes the edge exists cannot refuse and the tool that can refuse does not believe it. KI-BO-20260930 files finalize-feature Step 3.5 closing every inbox ticket store-wide, graded blocker because done is load-bearing for both ticket-prioritizer and ac_prioritizer, so falsely closed work leaves the backlog and unblocks dependents whose prerequisites do not exist; the manual sibling-baseline closure technique is recorded in that entry's Workaround field rather than promoted to a how-to. KI-KM-20260930 files that the entry-kind vocabulary declares 23 members and none is a known-issues register, so defect knowledge is structurally unroutable by the harvester while declaration, router and parity guard all agree with each other and are jointly wrong. The em-dash drift entry's occurrence count is corrected from 2 to 19 distinct refused commits across at least 5 worktrees, and its model corrected from the second commit to every commit after the first."
---

## Entry
