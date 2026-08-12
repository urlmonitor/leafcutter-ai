---
title: "Atlas mock mode (UXP-550) — real Atlas rendered from bundled fixtures"
date: "2026-08-12"
time: "00:00"
type: feature
components: 
  - frontend_coding
  - testing_quality
  - infrastructure
summary: "Released Atlas mock mode (UXP-550) so the real Atlas UI can be served from a bundled fixture repository without a live data source, with a production lock option and a CI drift guard that keeps fixtures valid against real schemas."
description: "1 commit (ab408ffb0). Introduces a repoRoot() seam switching between live loaders and bundled fixtures via LEAFCUTTER_MOCK env var, runtime ?mock query-param/cookie override, and an optional production lock. Ships a visible mock-mode badge in the Atlas sidebar, per-root loader caches, a portable ui-context data_layer bindings block so the mechanism works in any host app, and a fixture-drift.yml GitHub Actions workflow that validates fixture files against real schemas and parses them through real loaders on every PR."
pr: 410
commits: 
  - ab408ffb0
breaking: false
---

## Entry
