---
title: "The build-phase module is back under the size limit it is meant to enforce"
date: "2026-09-14"
time: "16:48"
type: manual
components: 
  - build_pipeline
summary: "scripts/build_phases.py goes from 2671 counted lines to 340 by moving every phase function into eleven sibling modules and keeping a full re-export surface, so no caller or test changes its imports."
description: "scripts/build_phases.py measured 2671 lines by the check-file-size counter against a 400-line limit for .py, so the GE-127b-1 ratchet refused any change that left it longer -- the same pressure that had already forced the build_precommit, build_phases_knowledge and build_phases_product_truth extractions, now applied to the remainder. Every phase function moves out into a sibling module (agents/skills, workflows, lifecycle, AC store, docs, agent validation, script deploy, reachability, collisions, clean, deploy failures), each under the limit. What stays behind is the state they share: the path constants, the up-to-date counter and the write helpers. build_phases.py re-exports every name, public and private, so build.py, build_helpers.py and roughly thirty-five test modules keep their imports unchanged. Extracted functions reach shared state through a function-scoped `import build_phases as _bp`, which is what keeps `monkeypatch.setattr(build_phases, \"TEMPLATES_DIR\", ...)` working -- a module-level `from build_phases import TEMPLATES_DIR` would bind a stale value at import time and silently ignore the patch. Three things needed more than a move. _compute_phase_mappings now takes its templates root as an argument, bound by a wrapper in the facade: build_helpers loads build_phases.py by file path under a synthetic per-package-root name so two roots in one process cannot read each other's templates, and a sibling imported by bare name cannot see that module object -- left implicit it would have enumerated the wrong package's templates. The deploy-failure registry moved to its own module for the same reason, so the writer and the reader agree on one registry whichever build_phases object a caller holds. And the synthetic-package test fixture now freshens the whole build_phases family rather than one file, because a stale cached sibling pointed at a deleted temporary directory and made a build phase write zero files while still reporting success."
commits: 
breaking: false
---

## Entry
