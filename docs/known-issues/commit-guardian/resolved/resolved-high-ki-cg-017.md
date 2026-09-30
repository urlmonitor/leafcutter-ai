---
title: "KI-CG-017 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes"
description: "KI-CG-017 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-017 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Minted as `KI-CG-016`, renumbered to `017` before merge.** A concurrent session claimed
> `KI-CG-016` for a different defect (the delegation hook substring-matching command text) in a
> PR authored at the same time. Renumbered here rather than there because that PR's description
> was already written around `016`, and because filing a duplicate in the same commit that flags
> the `KI-CG-012` duplicate would be self-defeating. Both numbers are free on `origin/main` at
> the time of writing; if the other PR lands as something else, this entry keeps `017` regardless
> — the number is arbitrary, the collision is not.

- **Severity:** high
- **Status:** **RESOLVED** (`ab9e91c4`, PR #593 — BP-100k-4; follow-up `10c711f1`, PR #730 —
  BP-100k-4-ii; verified 2026-09-25 by reading the hook manifest, running
  `check_hook_trigger_reachability.py` (unreachable=0) and running `pre-commit run
  check-build-drift --files templates/agents/README.md` (Passed, not Skipped)). See Resolution.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the generated `.pre-commit-config.yaml`, `check-build-drift` entry — `files: ^leafcutter/templates/`

**Symptom.** The hook exists to catch a template edited without a rebuild. Its file filter is
`^leafcutter/templates/`, which is where templates live in a **consumer** install, where the
package is vendored under `leafcutter/`. In this repository — the package itself — templates
live at `templates/`. The pattern therefore matches nothing here, the hook has `pass_filenames:
false` and no `always_run`, and pre-commit skips it. The one repository where every template
change originates is the one repository where the drift gate does not run.

**Evidence.** Observed in two consecutive commits on `fix/signoff-tool-allowlist`, which is
what makes it unambiguous rather than inferred:

```text
commit 1 — staged five files under templates/agents/
  Check Build Drift (leafcutter)........................(no files to check)Skipped

commit 2 — staged only changelogs/ and docs/acceptance-criteria/
  Check Build Drift (leafcutter)........................Failed
```

Skipped on the commit that changed five agent templates; ran on the commit that changed no
template at all. The second run failed for an unrelated reason (KI-BP-011 — a manifest with no
`output_mappings`), and only because the worktree was mid-bootstrap and briefly held an older
config in which the entry carried `always_run: true`. Once the canonical build regenerated the
config, the `^leafcutter/templates/` filter came back and the hook skipped again.

**Why the severity is high rather than medium.** This is the gate whose absence lets every
other deploy-staleness issue in the build-pipeline register survive. KI-BP-004 (worktree hooks
frozen at build time) and KI-BP-008 (a skipped workflow-install phase leaving a deployed
workflow 1497 lines stale) both propose extending `check_build_drift` as the natural home for
the fix. Both proposals are unreachable while the hook never fires in the package repo.

**A DETECTOR ALREADY EXISTS, AND IT IS RED — found while committing this entry.**
`check-hook-trigger-reachability` (BP-100k-4) does exactly this analysis and fires on it. It
ran on the commit that added this section and failed, naming **five** unreachable hooks, not
one:

```text
UNREACHABLE: check-build-drift            files pattern '^leafcutter/templates/'
UNREACHABLE: check-infra-docs             files pattern '(docker-compose.*\.ya?ml|...)'
UNREACHABLE: check-paths-integrity        files pattern '^leafcutter/config/paths\.json$'
UNREACHABLE: check-architecture-scaffolds files pattern '^leafcutter/templates/docs/architecture/'
UNREACHABLE: check-output-drift           files pattern '^(\.claude/agents/|\.claude/skills/|...)'
check-hook-trigger-reachability: RESULT total=50 unreachable=5 exempt=0
```

So the correction to this entry's original framing: the gap is **not** that nothing detects the
condition. It is that the condition is unresolved across five hooks, and the gate that reports
it blocks commits touching unrelated files, which makes it likely to be skipped rather than
acted on. Three of the five (`check-build-drift`, `check-paths-integrity`,
`check-architecture-scaffolds`) are the `^leafcutter/`-anchored consumer-path class this entry
describes. `check-output-drift` is the same class pointing at `.claude/`, which is gitignored
here. `check-infra-docs` is different in kind — this repo genuinely has no docker-compose or
`.env.example`, so that one may be legitimately inapplicable rather than misconfigured, and an
`exempt` mechanism exists (`exempt=0`) that nobody has used.

That distinction is the real work: the reachability gate currently cannot tell "this filter is
written against the wrong layout" from "this hook does not apply to this repository". Until it
can, its verdict is unactionable in bulk and gets skipped, which is how five accumulated.

**Fix direction.** Derive the filter from the layout rather than hardcoding one of the two, or
match both — `(^|/)templates/`. Do it for all three consumer-path hooks at once, mark
`check-infra-docs` exempt if it is genuinely inapplicable, and decide what `check-output-drift`
should point at given `.claude/` is gitignored. Verify by staging a template change in the
package repo and observing `check-build-drift` actually run — the skip line is quiet and reads
like a pass.

**Trap.** `(no files to check) Skipped` is visually indistinguishable from a hook that ran and
had nothing to say, and it appears in the middle of a long green hook list. Nothing in a normal
commit surfaces the fact that the drift gate has been inert for the life of the repository.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2's filter form: source and deployed
layouts differ, and the gate is configured against the layout it is not running in.

## Resolution (verified 2026-09-25)

The fix landed in `ab9e91c4` (PR #593, BP-100k-4, 2026-08-26), and it is on `origin/main`. The
entry stayed `open` for a month after that. Each claim was checked against `main` at `d2fe85a1`:

- **`check-build-drift`.** `templates/scripts/commit_guardian/commit_guardian.json` no longer
  has `files: ^leafcutter/templates/`. It now has `always_run: true`, and the `_comment` cites
  BP-100k-4. The generated `.pre-commit-config.yaml` has the same entry (line 22). Running
  `pre-commit run check-build-drift --files templates/agents/README.md` printed
  `Check Build Drift (leafcutter)....Passed`. The hook ran; the old output was
  `(no files to check) Skipped`.
- **`check-paths-integrity`.** The filter is now `^(leafcutter-ai/)?config/paths\.json$`, which
  matches both layouts.
- **`check-architecture-scaffolds`.** The filter is now
  `^(leafcutter-ai/)?templates/docs/architecture/`.
- **`check-output-drift`.** The gitignored `.claude/` filter was replaced by `always_run: true`.
- **`check-infra-docs`.** The filter was kept on purpose. Commit `10c711f1` (PR #730,
  BP-100k-4-ii) taught the reachability gate the difference this entry called "the real work".
  The gate now reports this hook as `NOTHING-TO-MATCH` (a correct kind-based filter with no
  matching file in this repo), not as `UNREACHABLE`.
- **The detector.** `python .leafcutter/scripts/commit_guardian/check_hook_trigger_reachability.py`
  now prints `RESULT total=67 unreachable=0 exempt=0 nothing_to_match=1 ...` and exits 0. It was
  red with `unreachable=5` when this entry was filed.

---
