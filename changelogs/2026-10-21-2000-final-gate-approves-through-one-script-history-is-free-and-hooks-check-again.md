---
title: "The final gate approves through one script, decision history no longer counts against file size, and the doc hooks check again (EPIC-RightJobRightAgentFollowUps)"
date: "2026-10-21"
time: "20:00"
type: manual
components:
  - ac_driven_dev
  - ac_store
  - agent_registry
  - commit_guardian
  - documentation_system
summary: "The leftovers of EPIC-RightJobRightAgent are closed. /plan-feature approves at the final gate through approve_acs.py, for exactly the ids the hold report releases, and no agent writes readiness any more. A new protected-fields rule family guards the fields each stage must not change. A rule check without a usable before-state writes nothing. Line-comment DECISION HISTORY blocks no longer count toward file size. The mermaid parent-link and ADR cross-reference hooks resolve the real project root and check again. Requirement writers declare requirement_records."
description: "Approval: approve_acs.py gains an --ids mode and a --priority option. It appends exactly one amended_by entry, leaves earlier entries byte-identical, keeps each file's line endings, restores a record that fails read-back, and is idempotent. /plan-feature runs it from .leafcutter/scripts/ac_store/ (a dry run first, then only the released ids); draft L0/L1 records in the batch are approved and held ones stay held. create_ac_workflow.py uses the same step. After the IT PO hand-back round, /plan-feature commits the test design and runs the rule check as --stage itpo-handback, fail-closed. Rule check: the 'protected fields' family compares each stage's edits against the committed record through one owner map. The hand-back may change the assignment, file-finding decisions and the planner's own enrichment fields. A run with no before-state, an unresolvable ref or an unreadable snapshot writes nothing and reports before_state.given false. The documentation-trigger names live in one list, the schema enum. Ratchet: a block of #, // or -- comments that starts with a whole-text DECISION HISTORY heading is not measured, and the published rule says so. Hooks: check-mermaid-parent-link and check-adr-cross-reference read the real project root, and a staged file they cannot read is could_not_check, not a pass. Existing violations are recorded in KI-DS-20261021. Profiles: product-owner, business-analyst and test-designer declare produces requirement_records and a real change surface, and the profile check flags store writers that declare otherwise. Docs: ADR-075 (the requirement rule check), ADR-072 amendment notes, an updated rule-check reference and the new docs/reference/source-file-length-measurement.md. Also: the four expects_from contracts removed for epic ordering are restored, and the last three informational mypy findings are fixed. KI-ACS-20261015 and KI-CG-20261016 are resolved."
breaking: false
---

## Entry
