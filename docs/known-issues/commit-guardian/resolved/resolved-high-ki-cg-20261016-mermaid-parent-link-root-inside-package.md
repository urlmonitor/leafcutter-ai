---
title: "KI-CG-20261016-mermaid-parent-link-root-inside-package — check-mermaid-parent-link resolves the repo root inside the package, never finds the staged doc and passes every commit"
description: "high — check_mermaid_parent_link.py sets REPO_ROOT = Path(__file__).resolve().parents[2]. That is templates/ for the source copy and .leafcutter/ when deployed, so _check_arch_doc never finds a staged architecture doc and returns no violation. Diagrams with broken parent links go through, for example c2-001…c2-006, whose parent agent_delivery_workflows.md does not exist at that path. check_adr_cross_reference.py and check_structural_change.py carry the same line."
type: reference
category: reference
status: active
created: '2026-10-16'
last_updated: '2026-10-21'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-009.md
  - docs/known-issues/documentation-system/open-low-ki-ds-20261021-architecture-docs-with-broken-parent-links.md
  - docs/known-issues/documentation-system/open-low-ki-ds-20261021-adr-cross-reference-findings.md
---

# KI-CG-20261016-mermaid-parent-link-root-inside-package — the mermaid parent-link hook checks nothing

> Filed 2026-10-16 after EPIC-RightJobRightAgent. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high. The hook reports success, but it never runs a check. Architecture docs with
  missing parents or one-way parent/child links land unnoticed.
- **Status:** **RESOLVED** 2026-10-21 by GE-113c-4 (`check_mermaid_parent_link.py`) and GE-113c-5
  (`check_adr_cross_reference.py`). See Resolution.
- **Occurrences:** 1 · **First seen:** 2026-10-14 (the architecture-diagram-author for the
  EPIC-RightJobRightAgent tickets 33/34) · **Last seen:** 2026-10-16
- **Where:** `templates/scripts/commit_guardian/check_mermaid_parent_link.py`, line 49
  (`REPO_ROOT = Path(__file__).resolve().parents[2]`) and `_check_arch_doc()`
  (`abs_path = REPO_ROOT / rel_path`; `if not abs_path.exists(): return []`). It is deployed as
  `.leafcutter/scripts/commit_guardian/check_mermaid_parent_link.py`.

## What happens

1. `parents[2]` of the script is `templates/` for the source copy and `.leafcutter/` for the
   deployed copy, never the repository root.
2. `_check_arch_doc()` joins the staged repo-relative path onto that root. The file is not
   there, so the function returns no violation.
3. Checked on 2026-10-16: importing either copy and calling
   `_check_arch_doc('docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md')` returns `[]`.
   With `REPO_ROOT` set to the real root, the same call returns
   `ARCH-PARENT-NOTFOUND: … declares parent: 'agent_delivery_workflows.md' but that file does not exist.`

## What it let through

- `docs/architecture/diagrams/c2-001` … `c2-006` all declare `parent: agent_delivery_workflows.md`.
  The real file is `docs/architecture/agent_delivery_workflows.md`, and it does not list them as
  children. Fixing only the path will then raise the level-order and bidirectional-link errors
  the hook exists to catch.

## Same line elsewhere (verified 2026-10-21)

`check_adr_cross_reference.py` carried the same `parents[2]` root and was as inert; it is fixed by
GE-113c-5. The original note guessed `check_structural_change.py` was "likely inert too". That was
wrong: it already resolves its root with `_resolve_root.find_project_root()` (`project_root`, line 70)
and reads every path through it. Its `REPO_ROOT = Path(__file__).resolve().parents[2]` (line 83) is
defined but never used, so it is dead code, not a defect. KI-CG-009 is the same root-resolution
class for check-components-integrity.

## Resolution (2026-10-21)

- **GE-113c-4** — `check_mermaid_parent_link.py`: `REPO_ROOT` is `_resolve_root.find_project_root()`.
  A staged architecture, Python or SQL file that cannot be read now emits
  `check_outcome.emit_result(OUTCOME_COULD_NOT_CHECK)` and exits non-zero. Tests:
  `unit_tests/commit_guardian/test_ge_113c_4.py`, which run the installed copy against a staged broken document.
- **GE-113c-5** — `check_adr_cross_reference.py`: the root, `COMPONENTS_JSON_PATH` and the ADR folder
  come from `find_project_root()`; an unreadable staged ADR or docs file emits `could_not_check` and
  exits 1, also without `--strict`. Tests: `unit_tests/commit_guardian/test_ge_113c_5.py`.
- The documents the working checks now refuse are recorded, not exempted:
  [KI-DS-20261021-architecture-docs-with-broken-parent-links](../../documentation-system/open-low-ki-ds-20261021-architecture-docs-with-broken-parent-links.md)
  (19 docs and 6 Python files; c1-001 and c2-001…c2-006 are fixed by GE-113c-4-i) and
  [KI-DS-20261021-adr-cross-reference-findings](../../documentation-system/open-low-ki-ds-20261021-adr-cross-reference-findings.md)
  (155 findings, warnings in pre-commit).
