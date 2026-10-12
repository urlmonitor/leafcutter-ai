---
title: "GE-122e-3: the eleven protected unnumbered diagrams are pinned by name instead of counted"
date: "2026-10-02"
time: "12:02"
type: manual
components: 
  - commit_guardian
summary: "A test that protects eleven legacy architecture diagrams from being renamed no longer breaks when someone adds an unrelated new diagram, and it now really notices if one of the protected eleven is renamed."
description: "test_ge_122e_3's unnumbered-artifacts check derived its protected set from whatever unnumbered diagrams existed at test time and pinned the folder-wide count at 11. The count broke on unrelated additions (a folder README in PR #635, new decision-kernel docs in PR #981), and because the set was derived from today's tree, a repository-level rename of a protected diagram could only be caught by the count, which one added file would hide. The eleven names from AC GE-122e-3's scope decision are now a module constant; each must exist at its path, stay unnumbered and be unchanged by the uniqueness pass. Three focused tests prove the helper reports a renamed protected diagram even when the unnumbered count stays at 11, reports a changed one, and ignores an extra unrelated unnumbered diagram. The check lives in its own module so the already-oversized test_ge_122e_3.py shrinks instead of growing. Test-only change."
---

## Entry

### Added

- `unit_tests/commit_guardian/test_ge_122e_3_protected_diagrams.py` — the protected unnumbered
  diagrams pinned by name (`_PROTECTED_UNNUMBERED_DIAGRAMS`), the real-collection check, and three
  tests proving the check is load-bearing.

### Changed

- `unit_tests/commit_guardian/test_ge_122e_3.py` — the count-based unnumbered-artifacts test is
  removed (moved to the new module, which also keeps the old file within the file-size ratchet).
