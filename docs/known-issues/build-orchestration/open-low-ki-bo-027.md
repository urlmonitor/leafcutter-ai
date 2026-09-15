---
title: "KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path"
description: "KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/build-feature.js` — the `resolve-target` phase, dispatched
  to `status-checker` against `RESOLVE_SCHEMA`

**Symptom.** On the first phase of an epic drive, the resolver returned:

```json
{"target_type":"epic",
 "epic_path":".../leafcutter-ai/tickets/00_inbox/epics/EPIC-TrustThatAGreenCheckActuallyChecked",
 "worktree_path":".../leafcutter-ai/tickets/00_inbox/epics/EPIC-TrustThatAGreenCheckActuallyChecked"}
```

`worktree_path` is the epic's ticket folder **inside the main checkout** — it is not a worktree,
and it is not even a repository root. The value satisfies `RESOLVE_SCHEMA` because the schema
constrains the field to a string, and a path-shaped string is what it got.

**No damage on this run.** A subsequent setup step created a real worktree at
`worktrees/EPIC-TrustThatAGreenCheckActuallyChecked` and returned `status: "created"`, and the
drive used that. Both `.leafcutter` and `.pre-commit-config.yaml` symlinks were present in it,
so the silently-skipped-hooks condition did not arise either.

**Why record it anyway.** The value that came back was wrong, nothing rejected it, and it was
survivable only because a later step happened to overwrite it. Had the second step reused the
first step's answer instead of computing its own, every phase agent would have been pointed at
the user's main checkout on `main` — which is the shape of KI-ACD-007, where `/plan-feature`
wrote its artifacts into the primary checkout for exactly this reason. The resolver failing open
onto a plausible-looking path is the hazard; the recovery was luck, not design.

**Fix direction.** Validate the resolved `worktree_path` before any consumer reads it: it must
be a directory that `git -C <path> rev-parse --show-toplevel` resolves to, and it must not be
the main checkout when the target is an epic. A schema that accepts any string cannot catch
this — the check has to be behavioural.

**Pattern:** a fail-open resolution rescued by a downstream step that did the work again.

---
