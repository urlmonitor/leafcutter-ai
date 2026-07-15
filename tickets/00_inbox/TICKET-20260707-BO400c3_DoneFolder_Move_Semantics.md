---
title: "Fix done-folder-move prohibition: move-not-presence semantics (BO-400c-3)"
status: todo
components:
  - commit_guardian
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/_signoff_parity_checks.py
  - templates/scripts/commit_guardian/check_ticket_signoff_parity.py
  - unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py
  - config/agent_registry.json
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/6
---

# Fix done-folder-move prohibition: move-not-presence semantics (BO-400c-3)

## Goal
In order to keep the ticket-lifecycle parity guard trustworthy, we need the
done-folder-move prohibition to fire on an actual **move** (a staged path
change into a `done/` folder) rather than on mere path **presence**, so that
routine in-place edits to already-archived tickets are not blocked and
premature branch-side archival into `tickets/99_done/` is caught — while the
sanctioned finalize-feature archive step on `main` still works.

## Context
Surfaced by the code review of PR #217 / TICKET-20260707-restore-ci-test-baseline.
The deployed `_check_done_folder_prohibition`
(`templates/scripts/commit_guardian/_signoff_parity_checks.py`, wired into
`check_ticket_signoff_parity.py`) currently fires on **any** staged path
containing `/done/`, with no rename/move detection. This diverges from the
already-approved BO-400c-3 move-not-presence intent and can hard-block routine
edits to a ticket that already lives under a `done/` folder.

Two new L3 ACs pin the edge behaviors (delivered via AC-authoring PR #221):
- **BO-400c-3-i** — editing an already-`done/` ticket in place (no path change)
  must NOT be blocked.
- **BO-400c-3-ii** — a **branch** commit moving a ticket into `tickets/99_done/`
  MUST be blocked, with a carve-out so the finalize-feature archive step on
  `main` (identified by an explicit context signal) is exempted.

## AC References
- Implements AC BO-400c-3 (move-not-presence parity guard) — the deployed code
  currently diverges from this approved L2.
- Implements AC BO-400c-3-i (edit-in-place under `done/` not blocked).
- Implements AC BO-400c-3-ii (branch move into `tickets/99_done/` blocked, with
  finalize carve-out).

Canonical AC source of truth:
`docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/`.
The Gherkin below mirrors the YAML for review convenience; the YAML wins on divergence.

## Acceptance Criteria
- [ ] AC-1 (move-not-presence): The prohibition fires only when the staged change
  introduces a `done/` path that did not exist at that path in `HEAD` (an
  add+delete pair or a rename into `done/`), not when a file whose path is
  unchanged is merely edited. (BO-400c-3, BO-400c-3-i)
- [ ] AC-2 (edit-in-place allowed): A staged commit that modifies a ticket
  already residing under a `done/` subfolder in place — no path change — is NOT
  blocked, and no "prohibited done-folder move" message is emitted for it.
  (BO-400c-3-i)
- [ ] AC-3 (99_done branch move blocked): A staged BRANCH commit that moves a
  ticket into `tickets/99_done/...` IS detected as a prohibited done-folder move
  and blocked, with a clear message naming the offending file and the
  `tickets/99_done/` destination. (BO-400c-3-ii)
- [ ] AC-4 (finalize carve-out): An explicit context signal (env flag or
  allowlisted invocation) identifies the finalize-feature archive step; when that
  signal is present, moves into `tickets/99_done/` are exempted and NOT blocked.
  When the signal is absent, no 99_done move is exempted. (BO-400c-3-ii)
- [ ] AC-5 (dedup + docstring): Fold the near-duplicate helper
  `_check_done_folder` into the single prohibition helper (no behavior change
  beyond AC-1..AC-4), and tighten the function name/docstring so they match the
  actual (now broadened, move-based) match rule. (review L-1, M-3)
- [ ] AC-6 (registry cleanup): Verify the leftover `behavioral_patterns`
  `pattern_id: "direct-write"` in `config/agent_registry.json` (~line 767) after
  the `skills_invoked` `direct-write` entry was removed in PR #217. Confirm it is
  a valid standalone pattern (leave as-is) or reword/remove it; record the
  read-confirmation in the commit message. (review L-2)

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Comments

<!-- Append-only log — leave blank when authoring. -->

## Implementation Tasks
- [ ] Rewrite the done-folder detection to compare staged paths against `HEAD`
  (move detection) instead of substring `/done/` presence.
- [ ] Broaden the match to catch moves into top-level `tickets/99_done/`, and add
  the finalize context-signal carve-out (define the env flag / allowlist and wire
  the finalize path to set it).
- [ ] Fold `_check_done_folder` into the single prohibition helper; rename +
  fix the docstring to match the move-based rule.
- [ ] Verify / reword the `direct-write` `behavioral_patterns` pattern_id in
  `config/agent_registry.json`.
- [ ] Extend `unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py`
  with the edit-in-place, 99_done-branch-block, and finalize-carve-out cases.
- [ ] Run `build.py` to regenerate the deployed `commit_guardian.json` and confirm
  the full commit_guardian suite is green.

## Out of Scope
- The systemic source↔template byte-parity gate (review M-2) is already covered by
  BP-1000a-1; this ticket only ensures the one-time regenerated `commit_guardian.json`
  is consistent — do not re-implement BP-1000.
- Making the CI pytest job blocking (review L-3) is covered by BP-1200b-1; not in scope here.
- The `ruff` `templates/` exclusion decision is deferred pending intent confirmation.

## Risk & Safety
- Touches money? No.
- Touches data? No — modifies a pre-commit guard hook and its tests.
- Reversibility? Fully reversible (hook logic + tests + one registry field).
- Care point: the finalize carve-out must be correct, or legitimate `/finalize-feature`
  archival on `main` will be blocked. Verify the finalize path sets the context signal
  before relying on the block.
