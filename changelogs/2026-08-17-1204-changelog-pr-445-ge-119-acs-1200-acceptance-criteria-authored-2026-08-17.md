---
title: "Changelog PR #445 — GE-119 + ACS-1200 acceptance criteria authored — 2026-08-17"
date: "2026-08-17"
time: "12:04"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "Wrote (but did not yet build) two new sets of acceptance criteria: one that will make a passing check on a pull request actually mean something was verified, and one that lets a team member jot down a half-formed idea without having to fake extra detail just to get the commit past a safeguard."
description: "3 commits (192d2c31c PO, 7655f100c BA, e9833d32e IT-PO), PR #445 — AC-authoring only, no production code or tests changed (verified via `git diff --stat 192d2c31c^..e9833d32e`: 59 files, all under docs/acceptance-criteria/ plus docs/INDEX.md). Authors GE-119 'Trust that a green check actually checked something' (guardrail-engine: L0 + 4 L1 + 20 L2 + 7 L3, 28 ACs) specifying a three-state check outcome model (ran-fully / ran-with-a-weaker-instrument-labelled-non-authoritative / could-not-check), a per-check cannot-run disposition, layout-independent verdicts, an out-of-process verification harness, and a setup path that refuses to hand over an unprotected working copy — addressing commit-guardian checks that currently degrade silently and report success when they cannot resolve their prerequisites. Also authors ACS-1200 'Capture a half-formed idea without bypassing your own safeguards' (ac_store: L0 + 4 L1 + 15 L2 + 4 L3, 24 ACs) defining a parked-idea marker (parked: true + non-empty parked_reason) so a deliberately parked L0/L1 stub no longer needs SKIP=check-ac-parent-covered-by to commit, while full back-link enforcement is retained for decomposed trees. Cross-tree dependency: GE-119b-1 depends on ACS-1200a. Both trees are readiness: approved, priority: high, authored/backlog only — no implementation ticket exists yet for either. Two prerequisite risks are recorded in the ACs but not fixed on this branch: ACD-1403 asserts a hook that demonstrably still exists was removed, and GE-116a-1-iii is approved but unbuilt."
pr: 445
commits: 
  - 192d2c31c
  - 7655f100c
  - e9833d32e
breaking: false
---

## Entry
