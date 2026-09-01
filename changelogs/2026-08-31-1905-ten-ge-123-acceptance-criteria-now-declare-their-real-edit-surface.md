---
title: "Ten GE-123 acceptance criteria now declare their real edit surface"
date: "2026-08-31"
time: 1905
type: manual
components: 
  - guardrail_engine
  - commit_guardian
  - security_scanner
summary: "Added an edit-surface doc_link to the ten GE-123 records that declared none, so ticket generation no longer falls back to harvesting file paths out of prose."
description: "Ten acceptance criteria in the GE-123 tree (GE-123a-1, GE-123a-1-i, GE-123a-2, GE-123a-3, GE-123c-3, GE-123d-2, GE-123d-3, GE-123d-4, GE-123d-4-i, GE-123d-5) supplied neither of the two structured sources generate_ticket_from_ac.py reads to build a ticket's files_touched: their doc_links carried only related/describes/context relationships, and their it_requirements are list-form prose rather than the object form that would provide a reference_file_path. The generator therefore fell back to harvesting path-shaped tokens out of prose, which produced three tickets whose entire declared surface was bare directories and two that pointed at docs/known-issues/commit-guardian.md — a live document — as the file to modify. The 27-ticket epic drive was stopped over it (KI-ACD-023).

Each record now carries a doc_link with relationship 'modifies' naming the file its work actually changes. The five branch-a and branch-c records point at templates/skills/security-scanner/scripts/scan_secrets.py, which holds the per-file scan short-circuit, the sensitive-filename rule, scan_files, and the allowlist loader that already emits the GE-113c-3-v warn-and-skip diagnostic. Four branch-d records point at templates/scripts/commit_guardian/check_secrets.py, which holds the prose post-filter — _PROSE_FILE_PREFIXES, _is_prose_exempt and _filter_prose_findings — and is the gate that actually blocks a commit. GE-123d-2 names both, because its own path-form requirement and its test_same_verdict_for_relative_and_absolute_path_forms entry exercise the scanner directly while the shape vocabulary must be shared by both entry points.

Both declared paths exist on disk and both are canonical templates/ copies per ADR-001; no build output under scripts/ or .leafcutter/ is named. Two records — GE-123a-1-i and GE-123d-3 — record in their amended_by that their expected production diff may be empty, since both are regression or negative arms whose weight is in their test contract; the surface is declared anyway because it is the only file a change for them could land in.

This is the upstream half of the fix. The generator-side change that stops the prose fallback producing bare directories is TKT-600a-1 and is separate work. The diff is purely additive — 180 insertions, 0 deletions — so no criteria, title, level, req_status or depends_on changed, and every pre-existing doc_link keeps its original relationship, including the known-issues links that remain 'related' context for KI-CG-004 rather than an edit target. validate_ac_schema.py reports all 32 AC YAML files in the tree valid."
breaking: false
---

## Entry
