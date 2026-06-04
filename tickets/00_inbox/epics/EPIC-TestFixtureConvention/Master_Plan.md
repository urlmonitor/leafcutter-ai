---
title: "EPIC: Test Fixture Convention"
type: epic
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-06-04
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
---

# EPIC: Test Fixture Convention

Establish a first-class test-fixture convention for the leafcutter-ai project:
a `tests/fixtures/<module>/` directory structure with a `load_fixture()` conftest
helper, a pre-commit hook that detects inline data bloat in test files, agent
prompt updates so test-writer and python-coder follow the convention automatically,
and a CI orphan-detection script that prevents stale fixture directories from
accumulating.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_conftest_fixture_helper.md](./01_conftest_fixture_helper.md) | Add tests/fixtures/ directory structure and load_fixture() helper in tests/conftest.py | `[ ]` |
| 02 | [02_precommit_bloat_hook.md](./02_precommit_bloat_hook.md) | Implement check_test_fixture_bloat pre-commit hook registered in commit_guardian.json | `[ ]` |
| 03 | [03_agent_prompt_updates.md](./03_agent_prompt_updates.md) | Update test-writer and python-coder agent prompts + test README to enforce the fixture convention | `[ ]` |
| 04 | [04_orphan_detection_script.md](./04_orphan_detection_script.md) | Write scripts/ci/check_fixture_orphans.py to flag fixture dirs with no corresponding test file | `[ ]` |

## Risk & Safety

- Touches money? No.
- Touches data? No — adds new files and mutates agent prompt templates; all
  changes are additive or doc-level.
- Reversibility? High — all changes are either new files or soft config
  updates. The hook ships `enabled: false` (warn-only) so migration is
  incremental and can be reverted by flipping a JSON key.
