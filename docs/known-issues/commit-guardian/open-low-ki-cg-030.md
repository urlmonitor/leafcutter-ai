---
title: "KI-CG-030 — Staged paths with non-ASCII characters are silently unattributed"
description: "low in this repository, **medium in a consumer project with non-ASCII"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-030 — Staged paths with non-ASCII characters are silently unattributed

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low in this repository, **medium in a consumer project with non-ASCII
  filenames**
- **Status:** open — the instance is on unmerged PR #495 (`_commit_disposition.py`), but the
  **precedent it was copied from is on `main` and live**: `check_ac_schema.py` uses the same
  unsafe form at three call sites
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (precedent re-verified against
  `37655862`)
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py:349`, `:396`, `:439`
  (`_get_staged_ac_paths` and siblings); PR #495's `_commit_disposition.py::_get_staged_paths`

**Symptom.** These call sites use plain `git diff --cached --name-only`, with no `-z` and no
`--no-quote-path`. Under git's default `core.quotePath=true`, a staged path containing
non-ASCII characters comes back **quote-escaped** (e.g. `"tickets/caf\303\251.md"`). That
string does not resolve to a real path, so the check silently fails to match it.

**Why the direction is bad.** For the uniqueness gate the consequence is that a collision the
current commit **did** cause is reported as *unattributed*, which by design does **not**
block. The commit proceeds. A silent miss, on the side that lets work through.

**Evidence.** Found during the first review of `GE-122a-1-i`. It is inherited from
`check_ac_schema.py::_get_staged_ac_paths`, which that AC's own `doc_links` name as its
precedent — so it is a pre-existing convention rather than something the GE-122 work
introduced. On `main` at `37655862` all three `check_ac_schema.py` call sites still use the
bare `--name-only` form.

**Why it is low here.** This repository's numbered artifacts are ASCII by convention
(`GE-122a-1.yaml`, `ADR-029-*.md`, `TICKET-*.md`). Nothing currently in the collection can
trigger it.

**Fix direction.** Use `git diff --cached --name-only -z` and split on NUL, or pass
`--no-quote-path`. **Fix both call sites together** — leaving the precedent unfixed means the
next author copies it again, which is exactly how this instance arose.

---
