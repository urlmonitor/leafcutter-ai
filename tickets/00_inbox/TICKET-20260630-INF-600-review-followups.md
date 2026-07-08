---
title: "Resolve MEDIUM code-review findings from EPIC-SelfDescribingAgentsCorrections (skills xref noise + hook logic duplication + card-gen perf)"
status: todo
components:
  - infrastructure
created: 2026-06-30
depends_on: []
priority: medium
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - scripts/registry_validator.py
  - scripts/generate_agent_cards.py
  - scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
  - templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Resolve MEDIUM code-review findings from EPIC-SelfDescribingAgentsCorrections

## Actor / Goal

In order to keep the self-describing-agents validation tooling low-noise,
drift-free, and fast, we need to resolve the MEDIUM findings raised by the
post-epic code review of EPIC-SelfDescribingAgentsCorrections plus a card-gen
performance problem discovered at finalize, so that the build-time agent
validators and card generator stay trustworthy, maintainable, and quick.

## Context

EPIC-SelfDescribingAgentsCorrections (INF-600 corrections) shipped on
`origin/main` via PR #179 (squash `2406aa87`). A post-epic deep code review
(`code-review-architect`) confirmed all 10 ACs are behaviorally implemented and
the two HIGH defects (H-1 `rstrip` suffix bug, H-2 non-deterministic `os.walk`
resolution) were already fixed on-branch. This ticket captures the remaining
MEDIUM findings plus one performance regression found while regenerating cards
during finalize:

- **M-2 — skills_invoked cross-reference floods the showcase agent with false
  positives.** `check_skills_invoked_xref` (ticket 03, INF-600g-3) emits
  "undeclared skill" warnings for `research-agent`'s `.claude/skills/...`
  domain skills. Scope Direction-1 (template-references-skill-not-in-registry)
  so project-local / non-portable skill references do not produce spurious
  warnings.

- **M-5 — the spawn-consistency hook duplicates validator logic verbatim.**
  `check_agent_spawn_consistency` (ticket 01, INF-600g-1) re-implements
  `_check_asymmetric_spawns` from `scripts/registry_validator.py` including its
  constants and error strings — a guaranteed drift point. The hook should
  import / share the single source of truth.

- **PERF — `_resolve_source_to_path` Strategy 3 is pathologically slow.** The
  H-2 fix made Strategy 3 collect ALL `os.walk` matches (bounded at depth 4)
  for every non-unique/missing source, instead of returning the first match.
  Against a real tree this exhausts a full walk per unresolved source; a full
  `build_agent_cards` run over ~55 agents took minutes, and against a package
  root containing `.git` (loose objects at depth 3) it did not complete in 5+
  minutes. Finalize had to regenerate cards against a `.git`-free copy. Fix by
  building a single filename->paths index once (or pruning `.git`/large dirs
  and depth-capping) so resolution is O(1) per source rather than O(tree) per
  source. Also fold in the review's related note that
  `python-coder.card.md` regenerates at ~78 KB because the AC-assignments
  section lists every AC store-wide where python-coder is the assigned agent —
  cap or summarize the list.

See the post-epic review report (`/tmp/sda_code_review.md`, findings M-2, M-5;
LOW findings L-1 backslash escaping, L-2 os.path/pathlib mix, L-4 stale
docstring MAY be folded in opportunistically but are not required).

## Acceptance Criteria

```gherkin
Scenario: skills_invoked xref does not warn on project-local skills (M-2)
  Given an agent template (e.g. research-agent) that references skills which
    resolve only via the project-local .claude/skills/ fallback
  When the skills_invoked cross-reference check runs during build validation
  Then no "undeclared skill" / "template references skill not in registry"
    warning is emitted for those project-local skill references
  And genuine mismatches for portable (package) skills are still reported.

Scenario: spawn-consistency hook shares validator logic (M-5)
  Given the check_agent_spawn_consistency pre-commit hook and
    registry_validator._check_asymmetric_spawns
  When the asymmetric-spawn detection logic or its error strings change in
    registry_validator.py
  Then the pre-commit hook reflects the change without a second edit
    (the hook imports/reuses the validator's logic rather than duplicating it)
  And the hook still passes for a reciprocal registry and fails for an
    asymmetric one, producing the same error string as the validator.

Scenario: card generation resolves doc-links without a full tree walk per source (PERF)
  Given a package root with the full docs tree present
  When build_agent_cards regenerates all agent cards
  Then doc-link source resolution does not perform an os.walk of the whole
    tree once per unresolved source (a filename index is built at most once)
  And a full regeneration of all agent cards completes in seconds, not minutes
  And running against a root that contains a .git directory does not hang.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| M-2 | | | |
| M-5 | | | |
| PERF | | | |

## Implementation Tasks

- [ ] Scope `check_skills_invoked_xref` Direction-1 to portable skills (suppress project-local `.claude/skills/` references).
- [ ] Refactor `check_agent_spawn_consistency` to import/share `_check_asymmetric_spawns` (and its constants/strings) from `registry_validator.py`; update both the deployed hook and its `templates/` source.
- [ ] Replace the per-source `os.walk` in `_resolve_source_to_path` Strategy 3 with a single cached filename index (and/or prune `.git` and depth-cap); cap/summarize the AC-assignments list to avoid multi-KB cards.
- [ ] Add/extend regression tests: research-agent no-false-positive; hook<->validator parity; card-gen completes quickly and does not hang on a `.git`-containing root.
- [ ] Run the registry-validator, generate-agent-cards, and hook test suites green.

## Risk & Safety

- Touches money? No.
- Touches data? No — build-time validation + card-generation tooling only.
- Reversibility? Fully reversible; isolated to validator, generator, and hook.

## Comments
