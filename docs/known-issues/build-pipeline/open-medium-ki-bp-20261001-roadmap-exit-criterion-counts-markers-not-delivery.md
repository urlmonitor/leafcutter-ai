---
title: "KI-BP-20261001 — phase_1's injection exit criterion can only report leftover markers, so it passes while two per-agent injections deliver nothing to any agent"
description: "KI-BP-20261001 — phase_1's injection exit criterion can only report leftover markers, so it passes while two per-agent injections deliver nothing to any agent"
type: reference
category: reference
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20261001 — phase_1's injection exit criterion can only report leftover markers, so it passes while two per-agent injections deliver nothing to any agent

> Index: [build-pipeline.md](../build-pipeline.md).

- **Severity:** medium. The defect is in a *phase exit criterion*, not in shipped behaviour — but a
  criterion that cannot fail on the thing it names lets a phase be declared complete on evidence
  that was never capable of disagreeing.
- **Status:** open
- **Occurrences:** 1 (found 2026-10-01 while authoring the AR-300 tree)
- **Where:** `docs/roadmap.json`, `phases[0].exit_criteria[1]`

**The criterion, verbatim:**

```
build.py --validate-only returns 0 with no template injection errors
```

**What is wrong with it.** It is satisfied today while **two** per-agent registry injections
deliver nothing to any agent. The criterion's only observable is the *absence of an error*, and the
failure mode in question produces no error by construction:

- `scripts/template_compiler.py` guards every one of its 8 registry injections on the placeholder
  being present — `if "{{my_skills_used}}" in body:`, and the same shape for the other seven. An
  **absent** placeholder is therefore not an error path at all. The table is computed from the
  registry and dropped on the floor.
- **0 of 60** agent templates contain `{{my_skills_used}}`. **0 of 60** contain
  `{{my_spawn_allowlist}}`. So both injections are dead for every agent, and neither can ever
  raise the "injection error" the criterion looks for.
- `scripts/build_placeholder_detection.py` — the component that *would* be the natural home for
  such a report — does not check for either token.

So the criterion measures **leftover markers in the output**, which is a real but different
property, and says nothing about whether computed content **arrived**. A build with both
injections dead is indistinguishable, under this criterion, from a build with both working.

**Scope note — it is 120 prompts, not 60.** Dual-platform compilation (ADR-002) emits a second
set of 60 compiled prompts into `<output_root>/gemini/agents/` alongside `<output_root>/agents/`.
Both sets are affected. A criterion or test scoped to one root leaves the other unguarded.

**Evidence basis.** The 0-of-60 counts, the 2-of-120 figure for prompts carrying any skills
section, and the guard at `template_compiler.py` line ~296 were measured directly against the
source tree and the deployed trees. The criterion's wording was read from `docs/roadmap.json`.
`build.py --validate-only` was **not** run as part of this filing — the claim above rests on the
code path (an absent token is not an error) rather than on an observed exit code, which is the
stronger proof but is worth stating plainly so nobody assumes the command was exercised.

**What a better criterion would assert.** That every per-agent block the build *computes* is
present in the compiled prompt of every agent it was computed for, derived from the build's own
declared platform roots rather than an enumerated list, with the inspected count reported so a run
that examined nothing fails instead of passing. That is the guarantee now specified by the AR-300
tree (`AR-300a`, `AR-300b`), which was deliberately worded **not** to restate this criterion.

**Deliberately not fixed here.** Reworded exit criteria change what completing a phase means, so
the wording is the user's call; the user chose on 2026-10-01 to file this rather than fold a
roadmap edit into the AC-authoring branch. `docs/roadmap.json` is untouched.

**Pattern:** a gate whose only observable is the absence of an error cannot see a failure that
produces no error. This is the same shape as the bare-directory validator that exited 0 having
checked zero files (KI-ACS-001) and the stale-ref merge audit that agreed with a broken tree — a
check that *examined nothing* must not look like a check that *found nothing*.
