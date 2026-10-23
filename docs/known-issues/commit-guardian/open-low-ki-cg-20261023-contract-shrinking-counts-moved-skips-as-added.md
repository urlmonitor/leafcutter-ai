---
title: "KI-CG-20261023-contract-shrinking-counts-moved-skips-as-added — check-contract-shrinking reports every added pytest.skip line, even when it replaces an identical skip or sits in a brand-new test file"
description: "medium. The skip patterns are matched against added diff lines only, with no netting against the removed line they replace and no exemption for new files, so a one-for-one skip refactor or a new live test with an unreachable-database guard is blocked as test weakening and the habitual remedy becomes SKIP=check-contract-shrinking."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20261023-contract-shrinking-counts-moved-skips-as-added — check-contract-shrinking reports every added pytest.skip line, even when it replaces an identical skip or sits in a brand-new test file

> One known issue, filed directly into `commit-guardian/` on 2026-10-23. Index:
> [commit-guardian.md](../commit-guardian.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**`
> line below, unchanged — `medium` indexes as `low` per this register's own
> "How this register is stored" section.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 4 (2026-10-14: three live-test builds, KM-400f-1-i, KM-400b-5-i and
  KM-400f-1-iii; 2026-10-23: the TQ-600a-13 post-merge live-database lane, PR #1322)
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-23
- **Where:** hook id `check-contract-shrinking`, script
  `templates/scripts/commit_guardian/check_contract_shrinking.py`. The weakening patterns
  (around line 113, e.g. `(r"^\+\s*pytest\.skip\s*\(", "pytest.skip added")`) are matched
  one added line at a time across the staged diff. Nothing compares an added skip with a
  removed skip in the same file, and nothing exempts a file whose status is `A` (new).

**Symptom.**

Two shapes, same cause:

1. **A moved skip.** On 2026-10-23 the TQ-600a-13 live lane replaced, in eight existing
   files under `tests/knowledge_live/`, the line
   `pytest.skip(f"live Neo4j not reachable: {exc}")` with
   `pytest.skip(unreachable_reason(exc))`, so all eight share one skip reason. The hook
   blocked the commit with eight `pytest.skip added` violations and listed the eight files
   as "Test files weakened".
2. **A skip in a new file.** On 2026-10-14 three builds each added a brand-new live test
   whose "unreachable database → skip" guard is the normal pattern of that folder. Each
   commit was blocked because the new file's skip line is an added line.

**Evidence.**

- Moved skip, from the staged diff of `tests/knowledge_live/test_km_400f_1.py` (one of the
  eight; the others are identical in shape):

  ```
  -            pytest.skip(f"live Neo4j not reachable: {exc}")
  +            from tests.knowledge_live._live_skip import unreachable_reason  # noqa: PLC0415
  +
  +            pytest.skip(unreachable_reason(exc))
  ```

  One skip removed, one skip added, same position, same condition. The number of skips in
  the file did not change and no assertion changed.
- New-file case: the three 2026-10-14 commits added files that did not exist on
  `origin/main`, so no existing test could have been weakened.
- In every case the commit went through with `SKIP=check-contract-shrinking` and the reason
  in the commit message.

**Why it matters.**

Same erosion as `KI-CG-20260923-contract-shrinking-guard-rename-blind`: the finding is a
false positive on work that keeps or adds coverage, its stated remedy ("change the tests in
a separate commit with no production code") does not fit a refactor that exists because of
the production change, so the practical response is to skip the gate. Every live-database
test that is added or refactored now needs that skip, and a gate that is skipped by habit
cannot catch the genuine skip it exists for.

**Fix direction.** Not implemented — recorded for a future pass.

- Per file, net the added skip/xfail lines against the removed ones of the same kind and
  report only a net increase.
- Ignore files whose diff status is `A` (new): a new file cannot weaken an existing test.
  A new file that skips everything is a coverage question for other gates, not a
  contract-shrinking one.
- Keep the current behaviour for a skip added to an existing test that had none.

**Related.** `KI-CG-20260923-contract-shrinking-guard-rename-blind` (same hook, the
test-name comparison has no rename step) and
`KI-CG-20260914-contract-guard-crashes-on-diff-bytes` (same hook, encoding crash) are the
script's other open defects.

**Pattern:** a guard that judges each added line on its own reports a pure move as a
change, so the sharpest false positive is a refactor that keeps coverage exactly the same.

---
