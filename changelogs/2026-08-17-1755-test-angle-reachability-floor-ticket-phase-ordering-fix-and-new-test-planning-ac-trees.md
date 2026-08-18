---
title: "Test-angle reachability floor, ticket-phase ordering fix, and new test-planning AC trees"
date: "2026-08-17"
time: "17:55"
type: manual
components: 
  - ac_store
  - testing_quality
  - supervisor_system
  - build_orchestration
summary: "Closed three ways test work could look finished without actually being verified: derived tests must now prove they call the real code, three build-pipeline checks that could silently run after a commit went out were moved back in front of it, and two new acceptance-criteria trees record the remaining gaps to close next."
description: "3 commits on fix/test-angle-reachability-floor (origin/main..HEAD): c18cba48 feat(ac-store), 3cba6f29 fix(workflows), 8d33ec2b docs(ac). (1) c18cba48: the criteria-derived fallback in generate_ticket_from_ac.py (_derive_tests_from_criteria — the path ~86% of AC records take, 394 of 2888) now tags its one-test-per-Gherkin-Then output angle: criterion and appends a mandatory angle: reachability descriptor requiring the test to invoke the production entry point; config/ac_store_schema.json declares two previously-rejected fields (declares_side_effect, test_spec[].angle — additionalProperties: false had blocked both); test-writer Rule 3 (cross-layer seam test) is rescoped from test-repair-only to all work; adds docs/testing/test-angles.md and a 16-check verification flow (3 passing, 10 failing, 2 blocked, 1 unverified, left open on purpose). (2) 3cba6f29: ac-validator (registry priority 11.5), ac-fulfillment-gate (11.7) and live-surface-tester (11.8) were absent from the phaseOrder array in both build-ticket.js and build-feature.js, so getPriority() fell back to phaseOrder.length (21) for all three, sorting them after commit (19) and pull-request (20) — their AC-coverage and fulfillment gates ran after the commit/PR had already happened. Fixed in both twins; the fallback now emits a diagnostic instead of failing silently; a new test executes the real comparator and asserts every is_ticket_phase registry agent appears in both arrays. (3) 8d33ec2b: authors BO-2900g (the ask: 5 L2s + 2 L3s) and BP-1100g (the record: 7 L2s + 3 L3s) — 21 files touched (19 new AC records, 2 parent covered_by back-link updates) — covering six confirmed gaps at the ticket-generator/test-writer seam. Nothing is readiness: approved; none of it is buildable yet."
commits: 
  - c18cba48
  - 3cba6f29
  - 8d33ec2b
breaking: false
---

## Entry
