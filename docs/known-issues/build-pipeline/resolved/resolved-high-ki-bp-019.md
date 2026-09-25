---
title: "KI-BP-019 — A missing `pyyaml` strips the frontmatter from every deployed agent, silently, with no output on any stream"
description: "KI-BP-019 — A missing `pyyaml` strips the frontmatter from every deployed agent, silently, with no output on any stream"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-019 — A missing `pyyaml` strips the frontmatter from every deployed agent, silently, with no output on any stream

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (938d5fb9, PR #680; verified 2026-09-25 by a no-yaml import probe and
  `unit_tests/test_ki_bp_019_yaml_hard_import.py`, 4 passed)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/template_compiler.py:33-37`

**Symptom.** The `yaml` import is wrapped in `except ImportError`, which sets a module flag and
prints **nothing** — not a warning, not a log line, not a stderr byte. `parse_frontmatter` then
returns `{}` for *every* template it is given.

**Consequence.** Every compiled agent loses `name`, `description`, `model` and `tools`. The
sign-off and verification blocks are never appended because the fields that trigger them are
absent. `build_skills` cannot see `internal` or `deprecated`, so skills that should be withheld
ship. The build prints `Total files written: N` — the same N as a correct run, because the files
*are* written — and exits 0.

**Why it is worth an entry of its own.** This is the largest single silent degradation in the
pipeline and it is invisible in the one place anyone would look: the build's own output. Every
other fail-open site in KI-BP-018 leaves at least a warning or a wrong file; this one leaves a
complete, plausible, populated output tree in which every agent has been quietly lobotomised.

**Fix direction.** It should not be caught at all — `pyyaml` is a hard requirement of the
compiler, and an environment without it cannot produce a correct build. Let the `ImportError`
propagate, or re-raise with a message naming the missing dependency. If the catch must stay for
some caller, it must at minimum print to stderr and set a non-zero exit path. Subsumed by
BP-900g-9's fail-closed principle but worth fixing on sight; it is one line.

**Pattern:** an exception handler that makes a missing dependency indistinguishable from a
satisfied one.

**Resolution (verified 2026-09-25).** Fixed by 938d5fb9 (PR #680). `scripts/template_compiler.py`
now has an unguarded `import yaml` (line 41), with a comment citing this KI. No `except ImportError`
and no no-yaml flag remain in the module. Evidence:

- Probe with `sys.modules["yaml"] = None`, then `import template_compiler`, printed
  `ImportError propagated: import of yaml halted; None in sys.modules`. The module no longer
  imports in a degraded mode, so `parse_frontmatter` cannot silently return `{}`.
- `python -m pytest unit_tests/test_ki_bp_019_yaml_hard_import.py -q` gave `4 passed`.

The scope of this entry is `template_compiler.py`, which is fixed. The same "pyyaml missing reads
as no frontmatter" pattern still exists elsewhere. None of these sites strips deployed agents, and
none is claimed by this entry:

- `templates/hooks/ticket_frontmatter_guard.py:128-130`
- `scan_ac_orphans.py`
- the `_load_yaml_safe` copies in `scripts/commit_guardian/check_ac_*.py` and their templates
- the `ticket_prioritizer.py` fallback

`scripts/build_glossary.py:282-286` also still catches an `ImportError` from `template_compiler`
and falls back to the raw text for CLAUDE.md. These sites belong with the general fail-open work
(KI-BP-018 / BP-900g-9), not with this entry.

*The changelog-entry validation gap first drafted here as KI-BP-021 was refiled as KI-CL-001 in
`docs/known-issues/changelog.md`: the `changelog` component owns entry emission and the
`changelogs/` corpus, whereas this register covers the template compiler. That draft was never
published, so the number stayed free and is now taken by the entry below — a different defect
entirely.*

---
