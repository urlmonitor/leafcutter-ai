---
title: "Backfill green test coverage for BP-700 (unified-frontend) ACs"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
source_ac: BP-700a-1
ac_coverage:
  - BP-700a-1
  - BP-700a-1-i
  - BP-700a-2
  - BP-700a-3
  - BP-700a-4
  - BP-700a-5
  - BP-700b-3
  - BP-700c-1
  - BP-700c-2
  - BP-700c-2-i
  - BP-700c-3
  - BP-700c-4
  - BP-700c-5
  - BP-700d-1
  - BP-700d-1-i
  - BP-700d-1-ii
  - BP-700d-2
  - BP-700d-3
  - BP-700d-4
files_touched:
  - unit_tests/agents/test_frontend_coder_unified.py
  - templates/agents/frontend-coder.md
  - config/agent_registry.json
  - scripts/build.py
  - scripts/build_phases.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Green test coverage for BP-700 (unified-frontend)

## Actor / Goal

As the AC store, I want every BP-700 AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST.** Per the 2026-07-14 audit, BP-700 shipped
(`templates/agents/frontend-coder.md` with embedded design principles, the
`config/agent_registry.json` entry, the build-migration in `scripts/build.py` /
`scripts/build_phases.py`, plus how-to/reference/upgrade docs) but 19 of its leaves are
untested. **Do NOT rewrite the template/registry/build code.** Author asserting tests for
the 19 CODE_NO_TEST leaves. (BP-700b-1, b-2, b-2-i are already FULLY tested by
`unit_tests/test_frontend_coder_llm_trigger.py` and are excluded.)

Audit note: `unit_tests/test_frontend_coder_llm_trigger.py` currently tags all three of
its sibling ACs with a single `# covers: BP-700b-2-i` — do not repeat that; each new test
must name exactly the AC it asserts. `skill_registry.json` still lists `frontend-design`
as installable (stale, but deploy is gated by `deprecated: true`) — this is expected.

The surfaces under test (read-only):
- `templates/agents/frontend-coder.md` (unified template — embedded principles, checklist,
  preserved capabilities)
- `config/agent_registry.json` (frontend-coder entry: preserved metadata, skills list)
- `scripts/build.py` + `scripts/build_phases.py` (build-time migration: deploy unified
  template, remove legacy `frontend-design` skill dir, update skills_config.json)
- how-to/reference docs under `docs/how-to/` and `docs/reference/` (BP-700a-4, a-5, c-5, d-4)

## What each test must assert

Read each AC's `criteria` in
`docs/acceptance-criteria/build_pipeline/BP-700-unified-frontend/<AC>.yaml`. Summary:

- **BP-700a-1** — template body embeds all five design principles + 6-question pre-write
  checklist; no instruction to load an external frontend-design SKILL.md.
- **BP-700a-1-i** — behaviour/contract: agent does not read a leftover
  `.claude/skills/frontend-design/SKILL.md`; uses only embedded principles (no double-apply).
- **BP-700a-2** — applies embedded principles with no skill install; completion report has
  `design_principles_applied: true`; no "frontend-design: not installed" warning.
- **BP-700a-3** — PROJECT_CONTEXT `design_system` values (primary_colour/font) override
  embedded defaults; embedded principles fill unspecified aspects.
- **BP-700a-4** — a how-to under `docs/how-to/` covers the four listed design-integration topics.
- **BP-700a-5** — a component diagram under `docs/architecture/` shows the unified agent at
  priority 8, no separate frontend-design box, relationships to PROJECT_CONTEXT + webapp-testing.
- **BP-700b-3** — no output/side effects when the repo has no frontend files (agent not spawned,
  not referenced in dispatch/log).
- **BP-700c-1** — every behavioural rule from frontend-design SKILL sections 2–5 has a
  corresponding instruction in the unified template; nothing dropped/weakened; project-context
  hook preserved with same precedence.
- **BP-700c-2** — every listed frontend-coder capability (stop-and-ask, contract mode,
  pre-flight reads, file-size limits, research delegation, completion report, signoff artifact
  checklist) is present in the unified template.
- **BP-700c-2-i** — framework-agnostic: Vue-appropriate output for .vue, plain HTML/CSS for
  .html/.css, no React-specific code, no unrequested framework import.
- **BP-700c-3** — webapp-testing stays a separate optional skill detected by file existence;
  Antigravity override preserved.
- **BP-700c-4** — registry entry preserves id/tier/priority:8/owns_file_extensions/spawn_allowlist/
  requires_verification/category; skills lists drop `frontend-design`, keep webapp-testing +
  signoff conditional.
- **BP-700c-5** — a reference doc under `docs/reference/` catalogues carried-forward principles,
  behavioural rules, webapp-testing status, and an old→new comparison table.
- **BP-700d-1** — build.py overwrites `.claude/agents/frontend-coder.md` with the unified
  template, removes `.claude/skills/frontend-design/`, needs no manual edits, reports the migration.
- **BP-700d-1-i** — fresh install: deploys unified template, no error about a missing
  frontend-design dir to remove, exit 0, dir not created.
- **BP-700d-1-ii** — upgrade preserves a customised PROJECT_CONTEXT.md design_system (not
  modified/deleted); unified agent reads the custom values.
- **BP-700d-2** — onboard wizard no longer offers frontend-design as a separate skill; still
  lists webapp-testing.
- **BP-700d-3** — build.py updates `skills_config.json` frontend.optional_skills to drop
  frontend-design (keeps webapp-testing); preserves other frontend keys; no-op when absent.
- **BP-700d-4** — a how-to under `docs/how-to/` documents the upgrade path (what changes,
  removed/updated files, no manual steps, verification, rollback).

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it (`# covers: <AC>`) and asserts its
behaviour/contract; its `covered_by` records the test path (`::test_function`);
`work_status: done` only after green (mark-done is a follow-up).

## Test Requirements

```yaml
tests:
  - name: test_bp700_frontend_coder_unified
    file: unit_tests/agents/test_frontend_coder_unified.py
    covers: [BP-700a-1, BP-700a-1-i, BP-700a-2, BP-700a-3, BP-700a-4, BP-700a-5, BP-700b-3, BP-700c-1, BP-700c-2, BP-700c-2-i, BP-700c-3, BP-700c-4, BP-700c-5, BP-700d-1, BP-700d-1-i, BP-700d-1-ii, BP-700d-2, BP-700d-3, BP-700d-4]
    asserts: >
      Each listed AC has at least one green test naming it that parses the unified
      frontend-coder template, the agent-registry entry, the build.py/build_phases.py
      migration code, or the how-to/reference docs and asserts the structure or migration
      behaviour required by that AC's criteria.
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
