---
title: "KI-BO-030 — `build.py` never creates two of the four namespace roots, so registering the uniqueness gate would make the package uninstallable"
description: "KI-BO-030 — `build.py` never creates two of the four namespace roots, so registering the uniqueness gate would make the package uninstallable"
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

# KI-BO-030 — `build.py` never creates two of the four namespace roots, so registering the uniqueness gate would make the package uninstallable

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — code is on `main` and live. The *blocking consequence* below additionally
  requires PR #495's fail-closed gate, which is not on `main`; the scaffolding gap itself is,
  and is the precondition that must land first.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `scripts/build.py` / `scripts/build_phases.py` (base install path);
  `scripts/seed_project_docs.py::seed_architecture_scaffolds` (`--seed-docs` path);
  `templates/docs/architecture/`

**Symptom.** A fresh consumer install gets `docs/acceptance-criteria/` (a `README.md` and an
`index.yaml`), but **`docs/architecture/adrs/` and `docs/architecture/diagrams/` are never
created**. With the `KI-CG-007` fail-closed contract in place, both are unresolvable, and an
unresolvable root blocks *regardless of what is staged*.

Measured on a real `git commit` of one unrelated markdown file in a pristine install, with the
gate hand-registered:

```
Check Identifier Uniqueness (GE-122 whole-collection pass).....Failed
- exit code: 1
[check_identifier_uniqueness] decisions: FAILED (0 inspected)
[check_identifier_uniqueness] diagrams:  FAILED (0 inspected)
BLOCKING: the following namespace(s) could not be resolved at all: decisions, diagrams
```

`--seed-docs` does **not** rescue it: that path creates `docs/architecture/adrs/` but writes its
C-diagram to `docs/architecture/c1-001-system-context.md` and never creates a `diagrams/`
subdirectory. Both documented install paths fail.

**Evidence it is still true.** `templates/docs/architecture/` at `37655862` contains
`README.md`, `FRONTMATTER.md`, `c1-001-system-context.md.template`, and an `adrs/` folder
(`README.md` + `ADR-template.md`) — and **no `diagrams/` subdirectory**. Since
`seed_architecture_scaffolds()` mirrors that tree verbatim, no `diagrams/` root can be produced.
`build_phases.py` contains no `mkdir` for either architecture root.
`docs/reference/architecture-docs-layout.md` — written on `main` to answer this issue —
independently records both gaps as outstanding recommendations.

**Root cause of the ordering hazard.** The fix is small: create the two roots empty, since an
**existing-but-empty** root passes cleanly by design. But the ordering is not optional:

1. scaffold the two roots in `build.py`
2. **then** register the hook (see `KI-CG-021`)
3. **then** re-run the deployed-consumer test

Shipping (1) and (2) in one change produces a package that cannot be installed.

**Why nothing caught it.** Five prior review rounds tested the gate by importing the module or
running the script from the source tree, where all four roots exist because this repo is not a
fresh install. The defect is only visible in the layout the code actually ships into.

**Two unrelated fresh-install blockers observed in the same experiment**, each worth its own
ticket:

- `check-secrets` flags ~30 `ENTROPY_HIGH` / `GENERIC_SECRET` hits **in the package's own
  deployed agent templates**.
- `check-hook-parity` looks for `templates/scripts/commit_guardian/` in the consumer, which a
  consumer never has. Still true: `check_hook_parity.py:465` defaults `canonical_template_dir`
  to exactly that path.

With `fail_fast: true` the first aborts the run. **A fresh install cannot currently make one
clean commit, with or without the GE-122 gate.**

**Fix direction.** Guarantee both roots from the BASE install path, not only `--seed-docs`, each
carrying a real placeholder file so git can track it. Resolve together with `KI-CG-028` (the
missing `architecture_diagrams` key in `config/paths.json`) — one change should decide where the
directory lives and how the gate finds it. `BP-900h-6` and `GE-122d-3-ii` are the ACs sized
against this entry.

---
