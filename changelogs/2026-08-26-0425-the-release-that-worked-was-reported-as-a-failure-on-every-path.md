---
title: "The release that worked was reported as a failure, on every path"
date: "2026-08-26"
time: 0425
type: manual
components: 
  - build_orchestration
summary: "The release dispatches carried no schema, so the engine returned their reply as text and the reporting logic could never recognise a success — every release, including a wholly successful one, was reported as refused with its criteria falsely listed as stranded."
description: "Follow-up to BO-2400f-10-ii, found by running the lane. The nine release dispatches declared no schema. Per the workflow engine contract agent() then returns the agent final text as a STRING, so reply.released is undefined and buildReleaseOutcomeFields could never reach its success branch. The success path was dead code from the moment it shipped. Observed on run wf_3b98fa8a-241: the release genuinely ran, all three criteria were todo on disk afterwards, and the terminal payload nonetheless said release_attempted false, listed all three as unreleased, and warned that a later run would be refused. That is worse than the silence it replaced, because an operator would go unstick criteria that are already free and would conclude the release fix had not worked. Adds RELEASE_SCHEMA to all nine dispatches so the engine returns a validated object, plus coerceReleaseReply as a fail-safe that parses a JSON string reply while still rejecting prose. The covering tests all stubbed the reply as a dict, a shape the engine only ever produces for a dispatch that declares a schema, which is why they stayed green; a new test feeds the real string form and fails without the fix. Also replaces a source-text proximity heuristic in the structural suite that broke on this commit because an explanatory comment moved the first literal release earlier in the file."
breaking: false
---

## Entry

Two hours after shipping the fix that made the fast lane's release step actually work, a
real run showed it reporting that same working release as a failure.

The run halted at the context-bundle phase, released its three claimed criteria, and left
all three at `todo` on disk — correct, and the first time in the lane's history that an
aborted run has handed its work back. The terminal payload said the opposite:

```
release_attempted: false
unreleased_ac_ids: [BO-2400c-1-i, BO-2400c-1-v, BO-2400c-1-vi]
Release: refused or unreadable ("{\"released\": [\"BO-2400c-1-i\", ...]}")
   — left at in_progress; a later run aimed at those ids will be refused
```

The reply quoted in the error is the **success** shape. It was there all along; the code
just could not see it.

**Why.** None of the nine release dispatches declared a `schema`. Per the workflow engine's
contract, `agent()` without a schema returns the agent's final text as a **string** — so
`releaseReply.released` is `undefined`, `Array.isArray` is false, and
`buildReleaseOutcomeFields` falls to its failure branch. Its success branch was unreachable
from the moment it shipped. Every release on every path would have reported as failed.

**Why the tests missed it.** All of them stubbed the reply as an object —
`_SUCCESSFUL_RELEASE = {"released": [...]}` — and an object is what the engine produces only
for a dispatch that *declares a schema*. The fixtures encoded the shape the code wanted
rather than the shape the engine emits. That is the synthetic-fixture bias `CLAUDE.md`
already documents under "Real-artifact behavioral spot-check", arriving through the one door
still open: the test harness stubs the boundary, so the boundary's real contract is never
exercised.

**The fix.** `RELEASE_SCHEMA` on all nine dispatches, so the engine validates and returns an
object. Plus `coerceReleaseReply` as a fail-safe that parses a JSON string — because reading
a real success as a failure is the worse error of the two, and a future dispatch that forgets
the schema should degrade to correct rather than to alarming. It still rejects prose: an
apology or a truncated reply takes the failure branch, and a test pins that so tolerance does
not quietly become credulity.

**One test was retired rather than appeased.** A structural check took the first literal
`"release"` anywhere in the file and required it within 2000 characters of some `return {`.
That corresponds to nothing — a mention in a comment satisfies it — and it failed here
because an explanatory comment moved the first occurrence, on a commit that made the release
path *more* correct. It now asserts that all nine named release labels exist, and says in
the body that the real proof lives in the harness test that executes the workflow.
