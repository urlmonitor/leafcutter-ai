---
title: "A dead agent is no longer counted as a completed phase, ticket, or epic"
date: "2026-08-25"
time: "22:10"
type: manual
components: 
  - build_orchestration
  - supervisor_system
summary: "The build workflows now fail closed on a missing, unrecognised, or undetermined agent result, and the three unanswerable plan-feature gates no longer default to discarding work."
description: "KI-SS-001, partially remediated. A subagent has no idle state: emitting text with no tool call ends the agent, and that text becomes its result. So an agent that parks returns prose carrying no status, and agent() itself resolves to null when an agent dies or is stopped. The workflow runtime read both as success. build-epic.js reduced a dead planner to a blank plan and then reported status ok with the message all tickets are done, having dispatched nothing; it separately coerced a missing ticket result to ok through a ternary, so a dead ticket-supervisor counted toward tickets_completed. build-feature.js carried the identical coercion in its epic loop. In both files a thunk that threw resolved to null under parallel() and was then dropped from the batch entirely, so a crashed ticket shrank the batch rather than failing it. Both per-phase guards tested truthiness while their own comments promised unrecognised status, so a hallucinated but truthy status passed the guard and then matched no branch, landing back in the silent-success hole the guard existed to close. plan-feature.js defaulted three unanswerable user gates to cancel, which made a transport failure indistinguishable from the user genuinely choosing to cancel; the third of those discards already-authored ACs. Every one of these now fails closed, and a new undetermined status gives an agent a truthful way to report that it could not perform its task instead of borrowing a status that means something else. Coverage is behavioural rather than structural: the new tests execute the real workflow scripts under the E2 stub harness with agent() returning null and assert on the terminal payload. They were proved to discriminate by running the same assertions against pristine origin/main, where the old code did report ok with all tickets are done. One pre-existing grep-only test that asserted the literal old guard text was updated to track the stronger form and annotated to point at the behavioural coverage. This narrows the blast radius of KI-SS-001 but does not close it: nothing yet stops an agent parking in the first place, and the registry spawn rule and the SubagentStop veto hook remain unbuilt."
commits: []
breaking: false
---

## Entry
