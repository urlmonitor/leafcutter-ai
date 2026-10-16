---
title: "KI-CG-20261016-mermaid-parent-link-root-inside-package — check-mermaid-parent-link resolves the repo root inside the package, never finds the staged doc and passes every commit"
description: "high — check_mermaid_parent_link.py sets REPO_ROOT = Path(__file__).resolve().parents[2]. That is templates/ for the source copy and .leafcutter/ when deployed, so _check_arch_doc never finds a staged architecture doc and returns no violation. Diagrams with broken parent links go through, for example c2-001…c2-006, whose parent agent_delivery_workflows.md does not exist at that path. check_adr_cross_reference.py and check_structural_change.py carry the same line."
type: reference
category: reference
status: active
created: '2026-10-16'
last_updated: '2026-10-16'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-009.md
---

# KI-CG-20261016-mermaid-parent-link-root-inside-package — the mermaid parent-link hook checks nothing

> Filed 2026-10-16 after EPIC-RightJobRightAgent. Index: [commit-guardian.md](../commit-guardian.md).

- **Severity:** high. The hook reports success, but it never runs a check. Architecture docs with
  missing parents or one-way parent/child links land unnoticed.
- **Status:** open, no AC.
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

## Same line elsewhere (not verified)

`check_adr_cross_reference.py:64` and `check_structural_change.py:83` set `REPO_ROOT` the same
way and join paths such as `docs/components.json` onto it. They are likely as inert. KI-CG-009
is the same root-resolution class for check-components-integrity.

## Fix direction

- Resolve the root with `_resolve_root.py` (the shared worktree-aware resolver), not `parents[2]`.
- Add a test that runs the deployed copy against a staged broken doc and expects a refusal.
- Then fix the c2-001…c2-006 parents, which needs a call on their real L1/L2 parent.
