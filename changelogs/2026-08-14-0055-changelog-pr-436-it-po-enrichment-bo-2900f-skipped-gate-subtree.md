---
title: "Changelog PR #436 — IT-PO enrichment for the BO-2900f skipped-gate subtree"
date: "2026-08-14"
time: "00:55"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "Filled in the technical detail for six acceptance criteria covering the rule that a quality check which never ran must never be mistaken for one that passed, and corrected a wrong assumption about the existing done check before anyone could build on it."
description: "1 commit, PR #436 — feat(ac-store): IT-PO technical enrichment for the six BO-2900f acceptance criteria, which landed on main via PR #424 carrying the business-analyst's behavioral work but with assigned_agent, estimated_complexity, it_requirements, delivers_to and expects_from all null, leaving the subtree unbuildable while sibling subtrees BO-2900a-e were fully enriched. Fills those fields plus test_spec, a string test_rationale, and additional doc_links across BO-2900f-1, f-2, f-2-i, f-3, f-4 and f-5. Five ACs assigned to python-coder; BO-2900f-5 is the reference-doc AC assigned to documentation-expert with test_required false. Every test contract is behavioral rather than structural, because this subtree exists precisely because a structural test stayed green on the double-recording bug it was guarding (BO-1000b-1-i's count guard matched quoted-string arguments but not the template literals that caused the defect): BO-2900f-2 asserts per-gate record counts after a real run rather than the presence of a recording call, per gate rather than in total because a total-only assertion is satisfied by a compensating duplicate-plus-gap pair, and BO-2900f-1's discriminating test is entry-count invariance across an all-enabled and an all-disabled run, a property no filter-before-capture implementation can satisfy. Also corrects a factual error the enrichment introduced in BO-2900f-1 and BO-2900f-3, which stated that adding a fifth skipped status would be refused by the existing done check because it falls outside {signed_off, not_needed}: _check_done_folder in scripts/commit_guardian/_signoff_parity_checks.py tests status in (needed, failed), a denylist, so a new enum value is admitted by default rather than refused, despite the violation message naming an allowlist the code does not implement. Building on the original claim would have shipped a skipped gate that passes the done check in silence — the exact defect this tree exists to end, introduced by the change meant to fix it. Both ACs now record that the branch must be inverted to an allowlist in the same change and that a work item carrying a skipped gate must be driven through the check and asserted refused. The record-surface question (git-tracked ticket versus durable JSONL sink) is left open as the user's decision; surface-dependent constraints name both options and what changes under each. Verified: all 39 AC files in the tree valid against config/ac_store_schema.json with jsonschema importable so schema-level validation was not silently skipped; all AC-store pre-commit hooks pass; diff additive apart from 28 removed null technical fields, no criteria field touched, notes appended rather than rewritten; every reference_file_path exists with its cited symbols present. All six remain readiness draft."
pr: 436
commits: 
  - 63b2a387d
breaking: false
---

## Entry
