---
title: "KI-CG-20260831-fictional-config-schema-fragment — two approved acceptance criteria declare a package-surface config key that was never created, and the validator that demanded the declaration cannot tell"
description: "KI-CG-20260831-fictional-config-schema-fragment — two approved acceptance criteria declare a package-surface config key that was never created, and the validator that demanded the declaration cannot tell"
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

# KI-CG-20260831-fictional-config-schema-fragment — two approved acceptance criteria declare a package-surface config key that was never created, and the validator that demanded the declaration cannot tell

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 2 (same defect, two sibling records)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml`
  (`it_requirements.config_schema_fragment.hook_trigger_reachability`) and `BP-100k-4-i.yaml`
  (`…hook_trigger_reachability_indeterminate`); `templates/scripts/commit_guardian/_package_surface_registry.py`;
  `check_package_surface_declaration`

**Symptom.** Both records carry a structured `config_schema_fragment` naming a top-level key
of `commit_guardian.json`, complete with `type`, `description` and a `reference_file_path`.
Neither key exists. Measured in the worktree:

```
commit_guardian.json top-level keys                 36
hook_trigger_reachability                       ABSENT
hook_trigger_reachability_indeterminate         ABSENT
```

Both ACs are `work_status: done` and `readiness: approved`. The behaviour they describe
shipped; the configuration surface they declare did not.

**Cause.** `check-package-surface-declaration` requires a record that registers a package
surface to carry a structured `it_requirements` spec. It checks that the declaration is
*present and well-formed*. It does not check that the key it names is *real* — there is no
step that opens `commit_guardian.json` and looks. So the cheapest way to clear the gate is to
write a plausible fragment, and a plausible fragment is indistinguishable from a true one.

**Why this matters more than a stale field.** The spec is machine-checked, which is exactly
what makes it dangerous: a reader who knows the validator ran will trust the fragment
describes the surface. Two records now assert a configuration contract that has never
existed, and the assertion carries the authority of a passed gate. **A spec that is validated
for shape but not for existence is worse than no spec** — no spec prompts a reader to go and
look.

It also propagates. An `it-po` enriching a sibling reached for the same pattern as precedent
and had to be told not to, which would have made three. That near-miss is how this was found.

**Remediation.** Decide per record whether the key should exist. If yes, create it in
`commit_guardian.json` and keep the fragment. If no, remove the fragment and re-derive
whether `package_surface` is truthfully `true` at all. Then close the gap in the validator:
when a `config_schema_fragment` names a key in a `reference_file_path`, open that file and
require the key to be present — the same disk-versus-declaration comparison
`KI-CG-20260831-hook-scripts-never-invoked` asks for one layer down. Both are the same
omission: a check that reads the declaration and never the thing declared.

**Not fixed here, deliberately.** Found while enriching `BP-1600a-2-ii`, which was steered away
from copying the pattern and carries an `it_requirement` saying why. Repairing two approved,
done records is a store-integrity change with its own blast radius and belongs in its own
change rather than riding along with unrelated criteria.

**How it was found.** An `it-po` agent checked whether the precedent it was about to copy
described a real key, instead of copying it because a validator had passed it.

**Related.** `KI-CG-20260831-hook-scripts-never-invoked` (the same declaration-versus-reality
gap, one layer down). `BP-1600a-2-ii` (the record that declined to repeat it). `BO-2000d` (the
thin-or-fictional-spec rule this violates).

**Pattern:** a validator that checks a declaration is well-formed and never checks that what
it declares exists — so the cheapest way to pass it is to invent something plausible.

---
