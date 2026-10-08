---
title: "Knowledge real-corpus tests derive their census from the stores, and a changelog without frontmatter fails extraction"
status: todo
components:
  - knowledge_management
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
tags:
  - testing
  - knowledge-projection
  - changelog
  - ci
last_updated: 2026-10-06
files_touched:
  - tests/knowledge/test_native_changelog_entry.py
  - tests/knowledge/test_native_decision_corpus.py
  - tests/knowledge/test_native_flow.py
  - tests/knowledge/test_native_mock_data.py
  - tests/knowledge/test_native_mockup.py
  - tests/knowledge/test_native_ticket.py
  - knowledge/native_types/changelog_entry.py
  - changelogs/2026-10-05-1602-changelog-5d5d0792-ee022375-2026-10-05.md
  - docs/known-issues/changelog/open-low-ki-cl-001.md
  - docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-1-xiii.yaml
  - docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-3-i.yaml
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Knowledge real-corpus tests derive their census from the stores, and a changelog without frontmatter fails extraction

## Actor / Goal
In order that adding a changelog, decision, flow, mock dataset, mockup or ticket does not turn
main's test suite red, we need the six `tests/knowledge` real-corpus tests to compute what they
expect from the stores on disk, so that only a real reader regression fails them. A changelog
with no frontmatter must fail extraction loudly instead of becoming an empty record.

## Context
- **Supersedes** `TICKET-20261005-KnowledgeRealCorpusTestsDeriveCounts`. That ticket exists only
  on open PR #995, names the wrong component (`knowledge_system`) and covers four of the six
  tests. This ticket covers all six, plus the masked changelog defect.
- **Covered ACs:** KM-400a-1-x (Flow), -xi (Mockup), -xii (MockData), -xiii (ChangelogEntry),
  -xv (Decision) and -vi (Ticket), all under KM-400a-3-i. The ACs' notes call their dated counts
  evidence scope, "not permanent population requirements". The tests pin them anyway:

| Test (tests/knowledge/) | Pinned literal |
|---|---|
| test_native_changelog_entry.py | 551 entries (twice) |
| test_native_decision_corpus.py | 6 decisions (twice) |
| test_native_flow.py | 25 flows; 14 "summaries differ"; `all(registered)` |
| test_native_mock_data.py | 3 datasets, 2 registered, 9 entities, 54 samples, 1 with shape_version |
| test_native_mockup.py | 15 mockups, 14 registered, 10 renders, 5 shape_version, 5 realization |
| test_native_ticket.py | 1560 tickets, 44 distinct fields, 92 epics |

- **History.** Commit 4f5643d97 replaced the exact counts with store-derived ones. Merge
  3fdc5286d put back a "reviewed exact census". Every later content addition then broke main.
- **Kept on purpose.** KM-400a-1-xiii names "the three reviewed malformed writer outputs". Those
  three compatibility recoveries stay pinned (`recovered == 3`), now also by source path.
- **Masked second failure.** `changelogs/2026-10-05-1602-changelog-5d5d0792-ee022375-2026-10-05.md`
  was committed as a 0-byte file in deb626b44 (PR #1015). The reader turned the missing
  frontmatter into `{}` (`changelog_entry.py` via `common.frontmatter`). The test oracle's
  `yaml.safe_load('')` gives `None`, so the oracle would fail on it. The count failure hid this.
- **Owner decision (2026-10-06).** A changelog with no frontmatter must fail extraction, naming
  the file and the reason, per KM-400a-1-xiii: "malformed shapes outside those narrow recovery
  rules fail with the affected source and reason". `common.frontmatter` is shared by the ADR,
  Agent, Skill, Document and Ticket readers, so the rule goes in `changelog_entry.py` only.

## Acceptance Criteria
- [ ] AC-1: With one record of each kind added in a tmp copy, all six tests still pass. No
  literal store total, field count or population sum remains in them.
- [ ] AC-2: Expected sets come from globbing the stores and reading
  `docs/product-truth/index.json`, never from the reader's own output. Set equality, deep
  equality, the round trip and the byte-for-byte no-rewrite checks are unchanged.
- [ ] AC-3: Each test asserts a non-empty census plus named reviewed anchors, each verified to
  exist on 2026-10-06:
  - the three changelog recoveries, pinned by source path;
  - `guardrails/frontend-ac-declarations` and `fern-and-fig/sign-in` unregistered;
  - the `fern-and-fig/cart` summary differs from its registration;
  - at least one null-render mockup.
- [ ] AC-4: A mutated reader (one dropped record or one rewritten field) still fails each test.
- [ ] AC-5: A changelog with no frontmatter fails extraction, naming the file and the reason,
  with a test.
- [ ] AC-6: The 0-byte changelog is fixed in content, and KI-CL-001 records a new occurrence.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Test Requirements

```yaml
tests:
  - name: test_changelog_real_corpus_accounts_for_all_fields_and_three_recoveries
    location: tests/knowledge/test_native_changelog_entry.py
    type: integration
    covers: KM-400a-1-xiii
    description: |
      Census from the configured and legacy store globs. Frontmatter and body are checked against
      an independent split of each file. The three reviewed recoveries are pinned by path, rule
      and field, and their sibling fields are checked against strict YAML.
  - name: test_changelog_without_frontmatter_fails_naming_source_and_reason
    location: tests/knowledge/test_native_changelog_entry.py
    type: unit
    covers: KM-400a-1-xiii
    description: |
      An empty file, a body with no `---` block, and a block that parses to nothing (comment
      only) each raise ValueError naming the source path and the reason. The file is not
      rewritten.
  - name: test_native_decision_real_corpus_preserves_all_authored_records
    location: tests/knowledge/test_native_decision_corpus.py
    type: integration
    covers: KM-400a-1-xv
    description: Census from docs/decisions/dec-*.yaml, with named decision anchors.
  - name: test_flow_real_corpus_deep_equality_and_no_rewrites
    location: tests/knowledge/test_native_flow.py
    type: integration
    covers: KM-400a-1-x
    description: |
      `registered == (id in manifest)` for every flow (the 4f5643d97 form). Anchor:
      leafcutter/finalize-feature's summary differs from its shorter registration.
  - name: test_mock_data_real_corpus_preserves_all_records_and_unregistered_dataset
    location: tests/knowledge/test_native_mock_data.py
    type: integration
    covers: KM-400a-1-xii
    description: |
      No population sums. Anchor: guardrails/frontend-ac-declarations is unregistered and has no
      shape_version.
  - name: test_mockup_real_canonical_population_includes_unregistered_and_null_renders
    location: tests/knowledge/test_native_mockup.py
    type: integration
    covers: KM-400a-1-xi
    description: |
      No population sums. Anchors: fern-and-fig/sign-in unregistered, the fern-and-fig/cart
      summary differs from its registration, at least one null-render mockup.
  - name: test_ticket_real_store_preserves_every_frontmatter_field
    location: tests/knowledge/test_native_ticket.py
    type: integration
    covers: KM-400a-1-vi
    description: |
      No ticket total, field count or epic count. Anchors: an archived epic master plan and one
      of its child tickets, plus tickets/README.md not admitted.
```

## Out of Scope
- The other tests/knowledge failures, such as test_kernel_run and the query_answer_contract
  tests. They have different causes and their own ticket.
- `common.frontmatter`'s missing-frontmatter-is-`{}` rule for the other readers.
- A shape check for changelog entries (KI-CL-001's fix direction).

## Comments

## Implementation Tasks
### test-writer
- [ ] Rewrite the six pins. Do not bump numbers, use `>=` floors, read expectations from the
  reader under test, drop set-equality or byte checks, skip or xfail, loosen `recovered == 3`,
  or filter odd files out of the glob.
- [ ] Add the no-frontmatter failure test, and add it to the `covered_by` lists of
  KM-400a-1-xiii and KM-400a-3-i.
### python-coder
- [ ] `changelog_entry.py`: no frontmatter block, or an empty one, raises ValueError naming the
  source path and the reason.
- [ ] Write the 0-byte changelog from `git log 5d5d0792..ee022375`. Append Occurrence 2 to
  KI-CL-001.

## Risk & Safety
- Touches money? No.
- Touches data? Fills in one empty changelog entry and appends a KI occurrence. No other source
  record is rewritten.
- Reversibility? Fully reversible.
- Behaviour change: knowledge projection now refuses a checkout that contains a changelog without
  frontmatter. Before, it published that changelog as an empty record. No historical revision
  used by tests carries such a file (checked at 9d115947 and 59269e02).
