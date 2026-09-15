---
title: "KI-CG-20260831-glossary-coverage-detector-path-unreachable — `check-glossary-coverage` has never run in this repo: it loads its detector from a path no leafcutter layout has, and its own \"detector not found\" message is dead code"
description: "KI-CG-20260831-glossary-coverage-detector-path-unreachable — `check-glossary-coverage` has never run in this repo: it loads its detector from a path no leafcutter layout has, and its own \"detector not found\" message is dead code"
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

# KI-CG-20260831-glossary-coverage-detector-path-unreachable — `check-glossary-coverage` has never run in this repo: it loads its detector from a path no leafcutter layout has, and its own "detector not found" message is dead code

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/check_glossary_coverage.py` — `_load_detector()`'s
  `spec_from_file_location(... find_project_root() / "scripts" / "glossary_detector.py")` branch,
  its `if spec is None or spec.loader is None` guard, and the blanket `except Exception` in
  `check_glossary_coverage()`

**Symptom.** The hook is registered live on `.*\.(md|py|sql)$` — it fires on nearly every commit —
and every one of those runs has been a no-op:

```
$ python .leafcutter/scripts/commit_guardian/run_hook.py .../check_glossary_coverage.py
check-glossary-coverage: WARNING — unexpected error: [Errno 2] No such file or directory:
  '.../EPIC-TrustThatAGreenCheckActuallyChecked/scripts/glossary_detector.py'.
  Glossary coverage check skipped (fail-open).
exit: 0
```

**Three compounding layers.**

1. **The path cannot exist.** `glossary_detector.py` is present at `templates/scripts/` and
   `.leafcutter/scripts/`, never at `scripts/` — confirmed absent from the worktree *and* the main
   checkout. `scripts/` holds only whole-directory symlinks (`commit_guardian`, `doc_compliance`,
   `feedback`), so a loose file is structurally unreachable there. Permanent state of the layout,
   not a local accident.
2. **The dedicated diagnostic is unreachable.** Its specific message — *"glossary_detector.py not
   found. Skipping glossary coverage check."* — is guarded by
   `if spec is None or spec.loader is None`. But `spec_from_file_location` on a **nonexistent**
   path returns a populated spec:
   ```
   $ python -c "import importlib.util; print(importlib.util.spec_from_file_location('g','/nope/g.py'))"
   ModuleSpec(name='g', loader=<SourceFileLoader ...>, origin='/nope/g.py')
   ```
   So the guard is false, control reaches `exec_module`, that raises `FileNotFoundError`, and the
   blanket handler relabels it a generic *"unexpected error"*. The one message written for this
   exact condition can never print, and the one that does misattributes the cause.
3. **The project documents it as working.** `CLAUDE.md`: *"the `check-glossary-coverage`
   pre-commit hook detects novel terms in staged files and dispatches the `glossary-triage` agent
   automatically."* It has dispatched nothing, ever.

**Fix direction.** Resolve the detector the way the rest of the family resolves shared modules
(`_resolve_root.py`) and try the deployed location, not a `scripts/` path that exists only in an
imagined layout. Replace the `spec is None` guard with an explicit `path.is_file()` check before
`spec_from_file_location` — the only form that can detect absence. Narrow the blanket
`except Exception`. Then decide deliberately whether a missing detector should fail open at all: a
gate `CLAUDE.md` presents as enforcing is a poor candidate for silent fail-open.

**Related.** `KI-CG-019` (same shape — fail-opening on an import it can never satisfy — different
hook and prerequisite). `KI-CG-034`, `KI-CG-012` (sibling exit-0-having-checked-nothing routes).

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5, aggravated by the absence being
documented as presence.

---
