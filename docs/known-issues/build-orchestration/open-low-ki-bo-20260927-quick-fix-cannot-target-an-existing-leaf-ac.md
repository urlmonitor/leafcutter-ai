---
title: "KI-BO-20260927-quick-fix-cannot-target-an-existing-leaf-ac — /quick-fix always authors a new AC, so it cannot build an approved leaf that /plan-feature wrote for it, and a file with no L1 mapping can only go through a full /plan-feature round"
description: "medium — quick-fix.js has no ac_id input; Phase 1 unconditionally creates a new L2/L3 and blocks when no L1 covers the file. Observed 2026-09-25 with KM-300a-1 (duplicate L2 avoided by driving phases by hand) and with scripts/generate_doc_index.py (no directory_patterns mapping)."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260927-quick-fix-gitignored-target.md
---

# KI-BO-20260927-quick-fix-cannot-target-an-existing-leaf-ac — /quick-fix always authors a new AC, so it cannot build an approved leaf that /plan-feature wrote for it, and a file with no L1 mapping can only go through a full /plan-feature round

- **Severity:** medium. There is a workaround (drive the phases by hand, or run a full `/plan-feature`), but the two entry points do not fit together. The planning pipeline produced an input that the fast bug-fix pipeline cannot accept.
- **Status:** open — no AC. Confirmed in code: the workflow has no parameter for an existing AC.
- **Occurrences:** 2 in one session (2026-09-25): KM-300a-1, and `scripts/generate_doc_index.py`
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/workflows-js/quick-fix.js` — the diagnosis destructure at `:226` (`target_file, location_hint, symptom, root_cause, divergence_decision`, and no `ac_id`); Phase 1 "AC Creation" at `:364-448` runs unconditionally; the "no existing L1" block is at `:394-396`, and the component block for files with no `directory_patterns` match is at `:373-376`.

## Symptom

1. `/plan-feature` produced `KM-300a-1`, an approved leaf authored expressly as the target for
   a quick fix. Running `/quick-fix` would have created another L2 under the same L1 for the
   same behaviour, and AC files are permanent by design (`:378`).
   The red, fix, green and mutation phases were driven by hand instead.
2. For `scripts/generate_doc_index.py`, `index.yaml` had no `directory_patterns` entry that
   matched, so Phase 1 blocked (`:375-376`). The only way forward the pipeline offers is a full
   `/plan-feature` round for a one-line fix.

## Mechanism

Phase 1 is not optional. It always tells the agent to "Create an acceptance criterion" (`:367`) and
destructures `ac_id` from that agent's reply (`:448`). Every later phase (red test `# covers:`
tag, mutation proof, commit) keys on that `ac_id`, so a caller cannot supply an existing one. The
blocking rules in steps 1 and 2 are deliberate (new L0/L1 nodes are `/plan-feature` territory),
but there is no lighter path for "the right parent does not exist yet".

## Fix direction

- Accept an optional `ac_id`. When it is given, validate that it is an existing leaf with
  `work_status` not `done` and readiness `approved`, skip Phase 1, and read `ac_path`,
  `component_id` and `ac_title` from the record. Every later phase already works from `ac_id`.
- Have `/plan-feature` print the exact `/quick-fix ... ac_id=<id>` invocation when it authors
  a leaf meant for quick-fix, so the handoff is explicit.
- For a file with no `directory_patterns` match, report the missing mapping as its own
  finding (an index.yaml gap) and name the one-line fix, rather than routing to a full planning round.

**Pattern:** two pipelines that each own "the AC", where the upstream one's output is not a valid input to the downstream one.
