---
title: "Wire commit agent to the classifier/learner library + config-array schema"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-1100a-2
ac_coverage:
  - BO-1100a-1-i
  - BO-1100a-2
  - BO-1100a-3
  - BO-1100a-4
  - BO-1100a-5
  - BO-1100b-1
  - BO-1100b-1-i
  - BO-1100b-2
  - BO-1100b-3
  - BO-1100b-3-i
  - BO-1100c-1
  - BO-1100c-1-i
  - BO-1100c-2
  - BO-1100c-3
  - BO-1100c-3-i
  - BO-1100d-2
  - BO-1100d-2-i
  - BO-1100d-3
  - BO-1100d-3-i
  - BO-1100d-4
  - BO-1100e-3
files_touched:
  - templates/agents/commit.md
  - config/commit_message_patterns.json
  - scripts/commit_classifier.py
  - scripts/commit_pattern_learner.py
  - unit_tests/test_commit_classifier.py
  - unit_tests/test_mixed_set_detection.py
agents:
  architect-review: signed_off
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Wire commit agent to the classifier/learner library

## Actor / Goal

As the commit pipeline, I want the commit agent to actually invoke the existing
`commit_classifier` / `commit_pattern_learner` library so that the smart
commit-routing behaviour the BO-1100 ACs specify runs at commit time — instead
of the agent drafting messages free-hand while the tested library sits orphaned.

## Remediation Context (audit 2026-07-14)

**Phantom-done.** `scripts/commit_classifier.py` and
`scripts/commit_pattern_learner.py` are real and green (150 passing tests), but
`templates/agents/commit.md` Step 2 drafts messages free-hand and **never calls
them** — every `change_target: prompt` AC in BO-1100 is unwired. Two config
divergences also exist: `config/commit_message_patterns.json` is a
`group→template` **object** with path rules hard-coded in Python `_PATH_RULES`,
not the AC-specified **array of `{group, path_pattern, template}`** — so a routing
rule cannot be added via config.

**Do: wire, don't rewrite.** The library exists; the work is (a) invoke the
classifier + mixed-set detection + learner from `commit.md`, (b) convert the
config to the AC's array schema and read path rules from it, (c) surface
classification/mixed-commit warnings/rule proposals per the ACs. Preserve the
existing green tests; add tests that assert the agent actually invokes the library.

## Acceptance Criteria

Resolves the 21 leaf ACs listed in `ac_coverage` (see the AC store under
`docs/acceptance-criteria/build-orchestration/BO-1100-smart-commit-routing/` for
verbatim Gherkin). Definition of done: each cited AC's behaviour executes at
commit time and is asserted by a test that names the AC.

## Test Requirements

```yaml
tests:
  - name: test_commit_agent_invokes_classifier
    file: unit_tests/test_commit_classifier.py
    covers: [BO-1100a-2, BO-1100a-3, BO-1100a-4]
    asserts: The commit flow calls the classifier and routes by first-match group.
  - name: test_mixed_commit_warning_surfaced
    file: unit_tests/test_mixed_set_detection.py
    covers: [BO-1100b-1, BO-1100b-2, BO-1100b-3]
    asserts: A mixed change-set produces the enumerated warning and proceed/abort prompt.
  - name: test_routing_config_is_array_schema
    file: unit_tests/test_commit_patterns_config.py
    covers: [BO-1100c-1, BO-1100c-2]
    asserts: config is an array of {group, path_pattern, template}; a new rule is addable via config.
```

## Sign-offs

- [x] architect-review — 2026-07-14 12:55
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-07-14 12:55 — architect-review (status: ok)
feedback-id: fb_2026-07-14_cf0410e9
completion_manifest:
  blast_radius_assessed: true
  classification_made: true
  acceptance_adjustments_noted: true
  requires_adr_set: true
Classified as SMALL. Six files (1 over the 5-file threshold), all in the single build_orchestration component with no cross-module boundary crossing and no always-large triggers. Classification uses the judgment-call clause: 2 of 6 files are tests, the other 4 are tightly-coupled commit-pipeline files (1 agent template, 1 config, 2 scripts that already carry 150 passing tests). The change is a pure wiring fix — the library exists; the work invokes it. Two acceptance adjustments logged: (1) the config loader must handle the legacy flat-object schema gracefully on upgrade; (2) classify_staged_files() must be the PRIMARY Step 2 path, not a fallback after free-hand drafting. No ADR required (1 component, no always-large trigger). escalation: none.
