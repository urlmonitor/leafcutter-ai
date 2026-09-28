---
title: "KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path"
description: "KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED 2026-09-23** — see the dated closure note at the foot of this entry.
  Original line, preserved: open
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

**Closed 2026-09-23.** Re-verified against current code, not this entry's narrative.
`templates/workflows-js/build-feature.js`'s resolve-target step (~line 1344) still dispatches
`status-checker` to guess a `worktree_path`, but that answer is no longer trusted at all:
`resolvedTarget.worktree_path` is initialized to `null`, and the comment at lines 1376-1400
states plainly that `resolveResult.worktree_path` is "DELIBERATELY not copied here", citing
this exact symptom by its own bug id: "BO-1900a-4 (BUG-01, run wf_09a91c7e-d5f): the resolver
returned an epic target whose isolated-working-copy value was a verbatim copy of the epic's
work-store folder. ... Nothing broke only because the very next step overwrote the value —
that is luck, not design."

Before any consumer can read a non-null `worktree_path`, the run calls
`worktree_repo_facts.py facts <path>` and requires `exists && is_linked_worktree &&
!is_main_checkout && same_repository` (build-feature.js:1418-1420) before accepting the
resolver's answer — a behavioral check against the real repository, exactly this entry's own
"Fix direction", not a schema-shape check. A path that fails this validation (such as the
epic folder inside the main checkout) is treated as unresolved and routed through the real
worktree-open path (with its own occupancy and branch-standing checks) instead of being
handed to any phase agent.

Confirmed behaviorally: `python -m pytest unit_tests/prompt_assembly/test_target_resolver_worktree.py -q`
→ 9 passed, 16 subtests passed (2026-09-23), including the test that runs the same scenario
against both twin driver scripts (`build-feature.js` and `build-ticket.js`) and asserts they
produce the same undetermined contract. `BO-1900a-4.yaml`: `work_status: done`, `readiness:
approved`.

This landed via `BO-1900a-4` / `BO-1900a-4-i` / `-ii` (`f8714935` and related commits,
predating the ACD-2100 epic) — unrelated to ACD-2100, but this entry was never updated to
reflect it.

---
