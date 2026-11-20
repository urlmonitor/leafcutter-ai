---
title: "Knowledge real-corpus tests derive expected counts from the stores instead of pinning them"
status: todo
components:
  - knowledge_system
created: 2026-10-05
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - testing
  - knowledge-projection
  - ci
last_updated: 2026-10-05
agents:
  test-writer: needed
  python-coder: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Knowledge real-corpus tests derive expected counts from the stores instead of pinning them

## Actor / Goal
In order that adding a decision record, flow, mock dataset or mockup does not turn main's test suite red,
we need the tests/knowledge "real corpus" tests to compute what they expect from the stores on disk,
so that only a real reader regression fails them.

## Context
- **Origin (2026-10-05):** PR #1011 re-enabled the full pytest suite (8 shards). On the same day,
  PR #1010 (reusable decision criteria) and PR #1012 (split compound requests) merged content that
  these tests pin by exact count. Their own CI still skipped pytest (#1010) or showed the failure
  next to 12 pre-existing ones (#1012). The user chose to merge #1012 and to ticket the pins.
- **Failing on main** (CI run 37317762249, and #1012's run 37318612185):

| Test (tests/knowledge/) | Pinned | Actual | Added by |
|---|---|---|---|
| test_native_decision_corpus.py:18,20 `test_native_decision_real_corpus_preserves_all_authored_records` (KM-400a-1-xv) | 6 decision records | 8 | #1010 (dec-93c1c730463c1f3c, dec-a070edfb6465bced) |
| test_native_flow.py:174 `test_flow_real_corpus_deep_equality_and_no_rewrites` (KM-400a-1-x) | 25 flows | 27 | #1010 (criteria-library) plus an earlier flow |
| test_native_mock_data.py:131,139,140,147,149 `test_mock_data_real_corpus_preserves_all_records_and_unregistered_dataset` (KM-400a-1-xii) | 3 datasets, 2 registered, 9 entities, 54 sample records, 1 with shape_version | 4 datasets | #1010 (criterion-categories) |
| test_native_mockup.py:124,132-135 `test_mockup_real_canonical_population_includes_unregistered_and_null_renders` (KM-400a-1-xi) | 15 mockups, 14 registered, 10 renders, 5/5 shape fields | 17 | #1012 (decision-split-approve, decision-split-progress) |

- All four also cover KM-400a-3-i. What they protect is real: every authored record is read, nothing
  is rewritten, and unregistered and null-render cases are kept. Only the literal totals are brittle.

## Scope (no acceptance criteria yet; covered ACs: KM-400a-1-x, -xi, -xii, -xv, KM-400a-3-i)
- Replace each literal total with a value derived independently of the reader under test. For example,
  glob the store paths and count the manifest entries in `docs/product-truth/index.json` and
  `docs/decisions/index.json`. Keep every per-record equality and no-rewrite assertion.
- Keep at least one fixed fixture per reader for the edge cases the counts stood in for: an unregistered
  dataset or mockup, a null render, and a record without shape_version.
- Re-run the four tests on main; they pass with today's content and keep passing when one record of
  each kind is added (test that by adding a temporary record in a tmp copy, not in the repo).

## Out of Scope
- The other 8 tests failing on main since #1011:
  - host-operation coverage;
  - live retrieval misses;
  - the knowledge kernel run;
  - the changelog and ticket real-store tests;
  - 4 query-answer-contract tests.

  They have different causes and need their own tickets.

## Comments

## Implementation Tasks
### test-writer
- [ ] Derive the expected totals in the four tests from the stores or manifests; keep the per-record assertions.
- [ ] Fixed fixtures for the edge cases the totals stood in for.

## Risk & Safety
- Touches money? No.
- Touches data? No. Tests only.
- Reversibility? Fully reversible.
