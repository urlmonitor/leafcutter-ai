---
title: "build-feature defers the epic PR to finalize (no per-ticket PR mid-drive)"
date: "2026-08-12"
time: "17:10"
type: fix
components:
  - build_orchestration
summary: "A /build-feature epic drive no longer opens a pull request per ticket mid-drive; the single epic-level PR is opened once, by finalize-feature."
description: "Extracted a pure selectDispatchPhases(orderedPhases, isEpicMember) helper from driveTicketPhases in templates/workflows-js/build-feature.js and made the epic batch call site pass isEpicMember=true. When true, the pull-request phase is dropped from the dispatched phases (the commit phase is retained so pre-commit hooks still fire per ticket); standalone single-ticket behavior is unchanged. Fixes the regression (surfaced during the BO-2600 drive, which opened PR #409 mid-build) where pull-request ran per ticket with no epic-member distinction — a gap left when the pre-ADR-006 ticket-supervisor close-out was flattened into driveTicketPhases. Covered by BO-2700 (business-analyst-authored ACs) and a behavioral test that executes selectDispatchPhases via node."
breaking: false
---

## Entry

Root cause found via a Fable-5 workflow review; the helper extraction makes the
filtering behavior unit-testable in isolation (the workflow script itself is not
importable). Scope is build-feature.js only — the twin build-ticket.js
(standalone driver) is intentionally unchanged.
