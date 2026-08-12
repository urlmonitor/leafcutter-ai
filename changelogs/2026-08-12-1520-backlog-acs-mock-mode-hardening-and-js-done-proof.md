---
title: "Backlog ACs: mock-mode hardening + JS/vitest done-proof"
date: "2026-08-12"
time: "15:20"
type: manual
components:
  - ux_prototyping
  - build_orchestration
  - testing_quality
summary: >
  Tracked backlog acceptance criteria for the follow-ups surfaced while shipping
  the Atlas mock-mode + flows-view features: four mock-mode hardening items and a
  capability to mechanically prove JS/vitest-covered ACs done.
description: >
  Authored via PO -> BA -> IT-PO; all work_status: todo (backlog, not built).
  Mock-mode hardening as L2/L3 under the shipped L1 UXP-593: UXP-607 (badge
  reflects the resolved runtime mock decision, not the build-time flag), UXP-608
  (production runtime override is default-deny), UXP-609 (CI drift-guard asserts
  isMockActive() before reporting clean), UXP-610 (CI-support API routes gated
  out of the production build). New L1 BO-2500e under the BO-2500 done-proof L0:
  the done-proof oracle discovers `// covers:` tags in .ts/.tsx tests via the
  shared extract_covers_tag seam and runs vitest fail-closed, so JS-covered ACs
  become mechanically markable done — unblocking the 12 UXP-596/UXP-591 ACs
  currently held at in_progress.
pr: 415
breaking: false
commits:
  - dfb8250ed
---

Backlog ACs only (no code). See UXP-607..610 (mock-mode hardening) and BO-2500e
(JS/vitest done-proof) plus their L3 children.
