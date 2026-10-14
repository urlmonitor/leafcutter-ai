---
title: "Five defects found while building GE-127g are filed as known issues, and a sixth gets a recurrence note"
date: "2026-10-14"
time: "16:20"
type: manual
components:
  - build_orchestration
  - build_pipeline
  - commit_guardian
summary: "Recorded five defects found during the GE-127g work in the known-issues registers and added a recurrence note to an existing one, with no code or behaviour change."
description: "Documentation only. Five new known-issue entries and one recurrence note, each with code claims checked against main and cited by file and line. No code changes."
breaking: false
---

## Entry

Documentation only. No code or behaviour changes.

- New: `KI-BO-20261014-fast-lane-build-targets-the-shared-install` (high). The fast lane never runs `build.py` itself, so the coder step chose a target on its own and deployed an unmerged gate over the shared install that every session's hooks run.
- New: `KI-BO-20261014-fast-lane-dependency-walk-omits-a-prerequisites-children` (high). The connected build set treats any L2/L3 prerequisite as a leaf, so that prerequisite's own children are never built, and nothing checks children before the run reports everything done. Reproduced read-only against the store.
- Recurrence note on `KI-BO-20261009-fast-lane-changelog-publishes-absolute-local-paths`: it happened again in the GE-127g lanes, and main now carries 15 entries with absolute paths, up from 12.
- New: `KI-BP-20261014-halt-guard-widens-to-every-changelog-when-the-pin-is-unreachable` (medium). When `git log <pin>..HEAD` fails, `build_halt_guard` silently treats every changelog entry as new, so an already-applied breaking migration halts the build again.
- New: `KI-CG-20261014-doc-length-gate-crashes-instead-of-reporting` (low). The doc-length gate raises a traceback instead of reporting in two cases: a set-aside document matching no declared entry, and a configuration file that is not valid UTF-8. Both still refuse the commit.
- New: `KI-CG-20261014-no-gate-keeps-the-document-length-standard-in-step` (low). Nothing keeps `docs/reference/document-length-standard.md` in step with the `doc_length` declaration, unlike the code-side rule, which has a parity gate.
- The commit-guardian, build-orchestration and build-pipeline indexes gain a row for each new entry, with their open counts recounted from the directories.
