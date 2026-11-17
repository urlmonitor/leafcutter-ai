---
title: "Record verified Aura publication of native Decisions"
date: "2026-10-03"
time: "12:17"
type: docs
components:
  - knowledge_management
summary: "Record six native Decisions in Aura with all 31 authored fields per record verified against their committed YAML."
description: "Add a dated publication and readback receipt, and distinguish the latest hosted verification from the original delivery receipts. The Decision importer was already on main; no importer code changes were needed."
---

Aura was refreshed from source revision
`2d4bee9fe665bc2f9b173baa752081bde69bc34c`. The published generation contains
9,344 nodes and 24,519 relationships, including six Decisions and 62 ADRs.
Live readback verified each Decision's full authored metadata, nested values,
payload and source revision against the committed YAML. All five previous
generations were preserved.

The dated receipt is `reports/native-fields/aura-decisions-2026-10-03.json`.
`delivery.json` links it as the latest publication and readback, while preserving
the original test, publication and visual receipts as historical evidence.
This change records an already completed publication; it does not change the
importer or rerun the full pytest suite.
