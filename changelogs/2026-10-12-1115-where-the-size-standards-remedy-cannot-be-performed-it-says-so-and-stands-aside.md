---
title: Where the size standard's remedy cannot be performed it says so and stands aside
date: "2026-10-12"
time: "11:15"
type: manual
components:
  - commit_guardian
  - precommit_hooks
summary: "check-file-size can now be told that a location's files cannot be split, and stands aside there — still measuring and reporting them — instead of refusing changes no author can satisfy."
description: "Implements GE-127f-5. GE-127f-2 made the oversized-file rule judge the measured lines a change PUT IN rather than net growth, and GE-127f-4 states the resulting obligation as two-for-one. Both assume the remedy GE-127f-3 names: move content out into a smaller companion file. In templates/workflows-js/ that remedy does not exist — per ADR-030 the E2 engine runs each workflow as a top-level body with no module loader, so there is nowhere for content to go, and build.py registers every .js there as an invocable workflow, so a helper sibling would deploy as a workflow and still be unreachable. The gate was refusing changes nobody could satisfy. A new file_size.length_refusal_exemptions config key declares such locations with a reason; the gate consults it only after measuring, so an excused file is still counted and still reported with its length and the recorded reason. A blank reason grants nothing, matching is an exact directory prefix, and every run states the declared set in force — including when it is empty — so a stand-aside is never silent. Files modified: templates/scripts/commit_guardian/check_file_size.py, templates/scripts/commit_guardian/config.py, templates/scripts/commit_guardian/commit_guardian.json, templates/scripts/commit_guardian/README.md."
breaking: false
---

## Entry

### What changed

`check-file-size` gains a declared set of locations where a file's length is
still measured, compared and reported, but is never *refused*. One location is
declared: `templates/workflows-js/`.

### Why

The size standard's refusal assumes an author can act on it. GE-127f-3 names
the action — take the content out, or have a restructuring specialist do it.
For an E2 workflow body there is no such action: the engine executes the file
as a top-level body with no `require`, no `import` and no `fs`, so a sibling
module cannot be reached at runtime. `plan-feature.js` and `finalize-feature.js`
already duplicate a shared helper across two files and each say so in a
comment. Refusing a change for a length that cannot be reduced is a different
failure from a file merely being too long, and it was blocking ordinary work on
the fast lane.

### What this is not

It is not a judgement that `fast-lane-ship.js` is an acceptable size — it
stands at 1590 measured lines against a permitted 1000, and the gate now says
so on every run that touches it rather than going quiet. It is not a scope
change either: `.js` remains a checked kind and the file is still counted under
the same measurement rule. What stands aside is the refusal alone.

### The cost, recorded deliberately

This removes the pressure that would otherwise force the lane's size to be
confronted. The durable fix is to stop expressing orchestration of this size in
a sandboxed JS body. A cheaper interim exists and is unevaluated: the engine's
`workflow()` primitive runs another workflow inline one level deep, so the lane
could delegate whole phases even though it cannot extract helper modules.

### Guardrails on the mechanism itself

- An entry whose reason is blank or missing grants nothing.
- Matching is an exact directory prefix, so `templates/workflows-js-extra/` is
  not excused by `templates/workflows-js/`.
- Every run states the declared set in force, including when it is empty.
- The declaration lives in the published rule surface, not in the hook; the
  tests drive the same staged change under two configs and require the
  verdicts to differ, so a hardcoded path with a decorative config key fails.
