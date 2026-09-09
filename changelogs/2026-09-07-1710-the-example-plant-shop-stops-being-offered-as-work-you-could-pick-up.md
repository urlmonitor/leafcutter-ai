---
title: The example plant shop stops being offered as work you could pick up
date: "2026-09-07"
time: "17:10"
type: manual
components: 
  - ac_store
  - ux_prototyping
  - ac_driven_dev
summary: "Three fern-and-fig demo acceptance criteria were being surfaced as ready leaves by the backlog scanner, so an agent could have been dispatched to build a fictional plant shop inside leafcutter; example content is now separated from the project's own record."
description: "scan_ac_store.py offered UXP-210d-4 and UXP-210d-5 as ready work and UXP-210d-6 as blocked-but-coming. They belong to fern-and-fig, the example plant shop that ships alongside leafcutter's own record, and nothing distinguished them from real work: they carry readiness approved, assigned_agent frontend-coder, and share components with real criteria. A new optional `product` field on the AC schema marks example-product ownership, and _is_example_content() in the ready-leaf scanner sets those records aside from both the ready and the blocked sets. Ownership is decided by `product` alone and deliberately never by component/components, because the example and real criteria routinely share a component -- that independence is what UXP-700d-2-ii pins. Set-aside records are reported through the JSON output's set_aside_count rather than dropped: separation, not deletion, since ADR-022 and UXP-550/UXP-593 depend on the example content continuing to exist and remain referenceable. Measured after: no UXP-210 or UXP-220 record appears in the ready set, set_aside_count is 3, and 678 real ready criteria are unaffected. The product-truth derived data on main is separately stale -- five steps of the leafcutter/generate-product-truth flow still carry impl_status done after UXP-510 through UXP-514 were demoted to in_progress. That repair, and the product-root ownership module for UXP-700d-1, are held for a follow-up commit: both touch docs/product-truth/, which triggers a pre-commit eval-freshness gate that cannot currently be satisfied (see KI-TQ-20260908-0900). Splitting them out lets the dispatchability fence land without weakening any gate."
pr: None
adrs: 
  - ADR-022
commits: []
breaking: false
---

## Entry
