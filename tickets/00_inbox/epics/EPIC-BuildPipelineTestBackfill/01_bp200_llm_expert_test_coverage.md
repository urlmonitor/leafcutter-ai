---
title: "Backfill green test coverage for BP-200 (llm-expert-agent) artifact ACs"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
source_ac: BP-200a-1
ac_coverage:
  - BP-200a-1
  - BP-200a-2
  - BP-200a-3
  - BP-200a-3-i
  - BP-200a-4
  - BP-200a-4-i
  - BP-200a-5
  - BP-200b-1
  - BP-200b-2
  - BP-200b-3
  - BP-200b-4
  - BP-200b-5
  - BP-200c-1
  - BP-200c-1-i
  - BP-200c-2
  - BP-200c-3
  - BP-200c-4
  - BP-200d-1
  - BP-200d-2
  - BP-200d-2-i
  - BP-200d-2-ii
  - BP-200d-3
  - BP-200d-4
  - BP-200d-5
  - BP-200e-1
  - BP-200e-2
  - BP-200e-3
files_touched:
  - unit_tests/agents/test_llm_expert_artifacts.py
  - templates/agents/llm-expert.md
  - docs/agents/llm-expert/PROJECT_CONTEXT.md
  - config/agent_registry.json
  - templates/skills/prompt-audit/SKILL.md
  - docs/agents/README.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
---

# 01: Green test coverage for BP-200 (llm-expert-agent)

## Actor / Goal

As the AC store, I want every BP-200 AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST.** Per the 2026-07-14 audit, all 27 BP-200 ACs are implemented
as real artifact content but have **zero dedicated tests** — normal for prompt/doc/config
surfaces. **Do NOT rewrite the artifacts.** The work is to author asserting tests that
read the shipped artifact files and assert their structure/content against each AC's
`criteria`. All artifacts already exist; the tests should go GREEN immediately (this is
a backfill, not TDD-red).

The surfaces under test (read-only):
- `templates/agents/llm-expert.md` (agent template — frontmatter + body sections)
- `docs/agents/llm-expert/PROJECT_CONTEXT.md` (six knowledge sections)
- `config/agent_registry.json` (llm-expert registry entry + ticket-supervisor spawn_allowlist)
- `templates/skills/prompt-audit/SKILL.md` (read-only audit skill)
- `docs/agents/README.md` (phase-agents table row)

## What each test must assert

Read each AC's `criteria` in
`docs/acceptance-criteria/build_pipeline/BP-200-llm-expert-agent/<AC>.yaml`. Summary:

- **BP-200a-1** — parse `llm-expert.md` frontmatter; assert `name: llm-expert`,
  `model: sonnet`, `tools` lists `Bash, Read, Edit, Write, Agent`, `portable: true`,
  `signoff: true`, `domain: null`, `requires_verification: true`, and a non-empty
  `default_artifact_checklist` list.
- **BP-200a-2** — the "Prompt-Quality Checklist" section has exactly 6 numbered items
  (as enumerated), each with a "Violation" and "Correct form" example, and a statement
  that a failing item is a blocker. (Audit note: items 5 & 6 may lack a "Correct form"
  line — assert to the AC; if genuinely absent the test is a real RED for those items.)
- **BP-200a-3** — "Stop-and-Ask Rule" names `workflow-architect` for registry/build/
  guardian edits and lists the user-confirmation conditions.
- **BP-200a-3-i** — "Constraints" prohibits editing `.py/.sql/.ts/.tsx/.html/.css`,
  registry/build files, forbids Grep/Glob/MCP search, requires reading before Edit,
  and surfaces `(status: blocker)` on refused edits.
- **BP-200a-4** — "Pre-Flight Reads" lists PROJECT_CONTEXT.md first, then signoff SKILL,
  ticket body, existing template.
- **BP-200a-4-i** — graceful degradation: log one debug line and continue when
  PROJECT_CONTEXT.md is absent (does not abort).
- **BP-200a-5** — "Skills" table lists exactly 3 skills (add-agent-to-package,
  add-skill-to-package, signoff) with invocation conditions + SKILL.md paths.
- **BP-200b-1** — PROJECT_CONTEXT.md has exactly the 6 named sections in order.
- **BP-200b-2** — Section 1 (Shell Convention) has the single-command rule, a detection
  heuristic table (&&, ;, ||, cd-chain, side-effect pipe), ≥4 Wrong + ≥4 Right examples,
  and the `ENV=val command` note.
- **BP-200b-3** — Section 2/3 distinguish required hand-authored vs build-injected fields
  and list model enum + skill required fields.
- **BP-200b-4** — Section 4 documents the three-place parity rule + `YYYY-MM-DD HH:MM`
  format + three status tags.
- **BP-200b-5** — Section 5 documents the depth cap table + spawn_allowlist/spawned_by
  contract + empty default spawn_allowlist.
- **BP-200c-1** — registry entry fields (id/name/tier/role/portable/domain/is_ticket_phase/
  model/template_path) + default_status `not_needed`.
- **BP-200c-1-i** — default_status `not_needed` means no auto-dispatch on existing tickets.
- **BP-200c-2** — trigger_conditions has dsl entry matching the template globs + llm entries.
- **BP-200c-3** — ticket-supervisor spawn_allowlist includes `llm-expert`; llm-expert
  spawned_by includes ticket-supervisor; spawn_allowlist includes research-agent; skills_used.
- **BP-200c-4** — README phase-agents table has an "LLM Expert" row with tier/role/description.
- **BP-200d-1** — prompt-audit SKILL frontmatter: `name: prompt-audit`, description mentions
  audit/checklist/violations, `allowed-tools` is exactly `Bash, Read` (no Edit/Write/Agent).
- **BP-200d-2** — six named checks each with numbered detection steps + severity levels.
- **BP-200d-2-i** — Check 4 skipped (N/A, field null) when signoff:false.
- **BP-200d-2-ii** — Check 2 classifies undeclared-tool as error, over-permissive as warning.
- **BP-200d-3** — structured report schema with the listed fields; violations sorted by line.
- **BP-200d-4** — constraints state read-only, no auto-fix, remediation belongs to llm-expert.
- **BP-200d-5** — single-file + batch workflows + isolated-check invocation documented.
- **BP-200e-1** — Implementation Sequence step 5 runs the checklist between draft (4) and write (6).
- **BP-200e-2** — Response Payload has the "Prompt-Quality Checklist Results" table (6 rows,
  Status pass/fail, Notes).
- **BP-200e-3** — Check 3 distinguishes side-effect vs read-only pipes and assigns severities.

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it (`# covers: <AC>`) and asserts its
behaviour; its `covered_by` records the test path (`::test_function`); `work_status: done`
only after green (mark-done is a follow-up).

## Test Requirements

```yaml
tests:
  - name: test_bp200_llm_expert_artifacts
    file: unit_tests/agents/test_llm_expert_artifacts.py
    covers: [BP-200a-1, BP-200a-2, BP-200a-3, BP-200a-3-i, BP-200a-4, BP-200a-4-i, BP-200a-5, BP-200b-1, BP-200b-2, BP-200b-3, BP-200b-4, BP-200b-5, BP-200c-1, BP-200c-1-i, BP-200c-2, BP-200c-3, BP-200c-4, BP-200d-1, BP-200d-2, BP-200d-2-i, BP-200d-2-ii, BP-200d-3, BP-200d-4, BP-200d-5, BP-200e-1, BP-200e-2, BP-200e-3]
    asserts: >
      Each listed AC has at least one green test naming it that parses the shipped
      artifact (template / PROJECT_CONTEXT / registry JSON / skill body / README) and
      asserts the structure or content required by that AC's criteria.
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit

## Comments
