---
title: "KI-CG-20260928-mermaid-parent-link-dead-in-deployed-layout — check-mermaid-parent-link derives REPO_ROOT from parents[2] of its own file, which lands on .leafcutter/ in the layout the manifest actually invokes, so every architecture doc it looks up is absent and it returns clean"
description: "high — the check resolves its root by counting path segments rather than asking git or the shared resolver. From the deployed path the manifest invokes, that lands inside .leafcutter/, where docs/architecture/ does not exist, so its own not-found guard returns an empty violation list for every document. It is one of the 19 files GE-120b-2's adoption sweep is scoped to migrate."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120b-2.yaml
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
---

# KI-CG-20260928-mermaid-parent-link-dead-in-deployed-layout — a segment-counting root walk that lands inside the deploy directory

- **Severity:** high. The check reports clean on every architecture document, in the layout
  pre-commit actually runs. Not a degraded result — no inspection at all.
- **Status:** open — no AC of its own, but **in scope for `GE-120b-2`**, whose `it_requirements`
  already name `check_mermaid_parent_link.py` in the un-migrated set. This entry is the measured
  consequence of that non-adoption, not a separate defect to fix twice.
- **Occurrences:** 1 (found by the `GE-120b-2-i` provoking-fixture sweep, 2026-09-28; confirmed
  independently twice).
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/scripts/commit_guardian/check_mermaid_parent_link.py:49`, and the
  not-found guards at `:229`, `:284`, `:313`.

## Mechanism

```
REPO_ROOT = Path(__file__).resolve().parents[2]
```

Then every lookup is `abs_path = REPO_ROOT / rel_path`, guarded by
`if not abs_path.exists(): return []` — an empty violation list, i.e. clean.

`parents[2]` is only correct for one of the three layouts this file exists in. The manifest
invokes the **deployed** copy at `.leafcutter/scripts/commit_guardian/…`, and counting two
parents up from there lands on `.leafcutter/` itself, which has no `docs/architecture/`. Every
`abs_path` is therefore missing, and every document reports clean regardless of content.

## Evidence — resolved by execution, all three layouts

| file location | `parents[2]` resolves to | `docs/architecture` present |
|---|---|---|
| `.leafcutter/scripts/commit_guardian/` *(what the manifest invokes)* | `.leafcutter/` | **no** |
| `scripts/commit_guardian/` *(ADR-001 symlink into `.leafcutter/`)* | `.leafcutter/` | **no** |
| `templates/scripts/commit_guardian/` *(canonical source)* | `templates/` | yes — but the wrong tree |

Two independent routes reach the same dead end. Invoked at the deployed path, `.resolve()` has
nothing to dereference and `parents[2]` is `.leafcutter/` directly. Invoked through
`scripts/commit_guardian`, `.resolve()` follows the ADR-001 symlink into `.leafcutter/` and
arrives at the same place. The only layout where the count "works" is `templates/`, and there it
silently scans the template tree's own docs rather than the repository's.

## Why the family's other checks are unaffected

Siblings resolve their root by asking rather than counting — `git rev-parse --show-toplevel`, or
`_resolve_root.find_project_root()`. `_resolve_root.py` already exists and 27 files in the family
already use it. This file simply never got that treatment, which is the finding `GE-120b-2`
states plainly: **the failure is non-adoption, not absence.**

## Fix direction

Do **not** patch `parents[2]` to `parents[3]` or similar. That replaces one segment count with
another and breaks again at the next layout. Migrate this file onto `_resolve_root` as part of
`GE-120b-2`'s sweep, and per that AC's remove-then-adopt rule delete the segment-counting
constant rather than leaving it beside the new call — a private fallback that survives still wins
on failure.

It also needs a negative control: a fixture architecture doc with a known-bad parent link that
the check must object to, exercised from the deployed layout. Without one, a root-resolution
regression is invisible exactly as this one has been.

## Note for whoever runs the GE-120b-2-i comparison

This check's `clean` in the pre-sweep baseline is **not** a gap in the provoking fixture; it is
this defect. If the sweep migrates the file correctly, this check will move from `clean` to
`violation` between the before and after runs. That is a **pass**, not the regression the third
criterion warns about — the only permitted difference is in working copies where resolution
previously failed, and this is precisely one. Record it as expected before running `verify`, or
it will read as a false alarm.

**Pattern:** a root derived by counting path segments rather than asking the VCS — correct in the
one layout its author had open, silently wrong in the layout that actually ships, and failing
closed into a clean result rather than an error.
