---
title: A slow retrieval source no longer ends a kernel run with no evidence
date: "2026-11-04"
time: "22:00"
type: manual
components: 
  - decision_kernel
summary: "retrieve.repository now cuts a source that misses its own deadline and keeps the evidence of the sources that answered; timeout retries stay within the active-time budget, and a cut goalless step is named in the limitation."
description: "TICKET-20261102-KernelDecisionGoalRoutingAndRetrievalTimeout AC-3 to AC-5. kernel/capabilities/retrieval/executor.py gives each source search a deadline of 0.6 x capability_timeout_seconds (the knowledge map included) and reports a missed one as an unavailable source. kernel/scheduler/guards.py retries a timeout failure only while one more full timeout fits below max_active_seconds (an unknown attempt time counts as a full timeout); merge.py passes the attempt's elapsed time. unresolved_text names the capability when a work item has no goal (nodes_schedule.py). New tests under tests/kernel/retrieval and tests/kernel/scheduler; two test_guards.py cases now use provider_unavailable as their generic retryable failure. AC-1, AC-2 and AC-6 stay open."
breaking: false
---

## Entry

On 2026-11-04 three kernel runs failed because `retrieve.repository` timed out (3 x 120 s and more)
and every piece of evidence was thrown away. Measured cause: each run re-reads every file of every
source, and the sources of one need run in parallel threads inside one 120 s timeout. A source
that is too slow is now cut on its own, so the run keeps what the other sources found, and
retries no longer use up the run's time before the decision step.
