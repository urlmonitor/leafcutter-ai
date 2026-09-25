---
title: "KI-CG-20260925-signoff-parity-enforces-only-under-done-folder — check_ticket_signoff_parity blocks only for paths containing /done/, tickets are no longer moved there, so it is warn-only for every ticket and 51 tickets read done with pull-request still needed"
description: "high — enforcement is keyed on folder position, which EPIC-MoveOnMainOnly retired; the deployed hook passes no --enforce. 51 tickets now carry status: done with pull-request: needed, violating the signoff skill's done-eligible rule."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - commit_guardian
  - build_orchestration
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/build-orchestration/open-blocker-ki-bo-20260831-1930.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260831-1932.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-CG-20260925-signoff-parity-enforces-only-under-done-folder — check_ticket_signoff_parity blocks only for paths containing /done/, tickets are no longer moved there, so it is warn-only for every ticket and 51 tickets read done with pull-request still needed

- **Severity:** high. The parity gate the signoff skill describes as "blocks the commit" blocks nothing; phantom-done tickets accumulate on main.
- **Status:** open — no AC. Hook read and count taken 2026-09-25 (`scratchpad/phantom.py`, frontmatter regex over `tickets/**`).
- **Where:** `templates/scripts/commit_guardian/check_ticket_signoff_parity.py:24-26, 295-310`; deployed registration `.leafcutter/pre-commit-config.yaml:440` (no `--enforce`).

## Symptom

51 tickets have `status: done` while their `agents:` map still lists `pull-request: needed`, by epic:
BuildPipelinePhantomRemediation 9, DocumentationCoverageGuarantee 7, CommitSignoffHardening 6,
FlattenSupervisorChain 4, BuildAcResolves 2, MermaidComplexityGuard 2, InFlightVisibility 1, no epic 20.
(Includes legacy tickets; a narrower epic-scoped count found 18.)

## Mechanism

The hook exits 1 only when `--enforce` is passed **or** the file path contains a `/done/` segment. BO-400c-1 /
EPIC-MoveOnMainOnly made frontmatter `status:` the lifecycle signal and stopped moving tickets into `done/`, so the
auto-enforce branch is unreachable for new work and the registration never passes `--enforce`.

## How the tickets got there

Five recipes write `status: done` and only one checks anything (the `set_ticket_status.py` guard that refuses
"done while an agent is still needed"): `build-feature.js:1114-1122` and `build-ticket.js:955-961` (status-checker
hand-edit, "change nothing else"), `finalize-feature.js:1599-1604` (regex replace), `ticket-supervisor.md:172-195`
(edit + `git mv`), `pull-request.md:231-240` (flips its own ticket). `building-epics/SKILL.md:343-347` additionally
writes `pull-request: signed_off` for a PR phase that never ran — which KI-BO-20260831-1930 L85-88 calls false.

## Fix direction

Key auto-enforcement on frontmatter `status: done`, not folder position. Make `set_ticket_status.py` the only
writer of ticket status (cluster 1 of the 2026-09-25 duplication analysis). Then reconcile the 51 tickets.
