---
title: "KI-DS-20261016-c3-030-number-claimed-on-two-branches — diagram number c3-030 is on main for the requirement rule check and on the BO-4300 workspace epic branch for a different diagram"
description: "low — main has docs/architecture/diagrams/c3-030-requirement-rule-check-components.md (EPIC-RightJobRightAgent, PR #1245). The BO-4300 workspace epic branch (epic/every-piece-of-separate-work-gets-its-workspace) has c3-030-workspace-request-halt-sequence.md and c3-031-workspace-request-states.md. That branch must renumber when it next merges main; c3-034 and c3-035 are free."
type: reference
category: reference
status: active
created: '2026-10-16'
last_updated: '2026-10-16'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
---

# KI-DS-20261016-c3-030-number-claimed-on-two-branches — two diagrams want c3-030

> Filed 2026-10-16. Index: [documentation-system.md](../documentation-system.md).

- **Severity:** low. Nothing is broken on main. The clash surfaces as a duplicate diagram number
  when the BO-4300 epic merges main.
- **Status:** open, no AC. It belongs to the BO-4300 workspace epic. This record is the hand-over
  note; nobody edited that branch.
- **Occurrences:** 1 · **First seen:** 2026-10-14 · **Last seen:** 2026-10-16

## The clash

- **On main (first to land):** `c3-030-requirement-rule-check-components.md`, plus c3-032 and c3-033.
- **On `epic/every-piece-of-separate-work-gets-its-workspace`** (also `lane/bo4300-t14a` and
  `merge/bo4300-main-into-epic-4`): `c3-030-workspace-request-halt-sequence.md` and
  `c3-031-workspace-request-states.md`.
- **Files on that branch that cite the numbers:** BO-4300c-5.yaml, BO-4300d-5.yaml,
  `docs/architecture/components/worktree-manager.md`, `docs/how-to/get-a-workspace.md`,
  `docs/reference/workspace-maker-answer.md`, its ticket 13, and
  `unit_tests/build_orchestration/test_bo_4300_docs.py`.

## What to do

At its next merge of main, the BO-4300 epic renumbers its two diagrams to the next free numbers
(c3-034 and c3-035 were free on 2026-10-16) and updates the references above. That branch also
carries an `ADR-070-…`. Check the ADR number against main at the same time.
