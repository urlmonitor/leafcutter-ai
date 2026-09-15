---
title: "KI-BP-023 — The closure guard's \"every script this build will deploy\" covers eight deploy families and the build has ten"
description: "KI-BP-023 — The closure guard's \"every script this build will deploy\" covers eight deploy families and the build has ten"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-023 — The closure guard's "every script this build will deploy" covers eight deploy families and the build has ten

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED 2026-08-31**, but read the correction below — this entry's
  own prescribed fix was wrong and following it would have made the guard worse.
  Set B now covers ten families via two new helpers, and the docstring states that it
  is enumerated rather than claiming completeness. Found in the same third review round
  as KI-BP-022.

**CORRECTION to the Fix direction below (2026-08-31).** This entry said: "Fix
`_manifest_template_standalone_scripts` to `rglob` rather than `glob` while there." **Do
not do that.** `build_template_standalone_scripts` is deliberately non-recursive — its
own docstring says "excluding subdirectories" — so the shallow glob correctly mirrors its
phase. Widening it would have registered `scripts/<name>` deploy paths for files that
phase never writes, adding FALSE entries to Set B and producing spurious "undeployed
dependency" findings against paths nothing ships. A manifest helper must mirror its
PHASE, not its directory. `sync_platforms` needed its own helper, which is what it got.

**A second defect, found only by running the real build (2026-08-31).** Adding
`scripts/doc_compliance/` to Set B immediately produced **14 phantom findings**, every
one naming a dependency prefixed `.leafcutter/`. The cause was not a missing deploy:
`_source_file_for_deploy_path` tries `templates/<deploy_path>`, which for this family is
`templates/scripts/doc_compliance/` — a path that does not exist, because the source
directory is `templates/doc-compliance/` (hyphen, not underscore, and not under
`scripts/`). So resolution fell through to the `direct` rule, `package_root/scripts/
doc_compliance`, which **in any worktree that has run `install_shims` is a symlink into
the deployed `.leafcutter` tree**. The guard followed it and analysed BUILD OUTPUT as
though it were source.

That is worth stating on its own: the fallback silently substitutes deployed output for
source for any family whose source layout does not match one of the two rules above. It
bit nothing before only because every prior family happened to match. The resolver now
carries an explicit branch for doc-compliance and returns a deploy-namespace prefix, and
the fallback is commented as the hazard it is.

None of the unit tests caught this — they exercise the analyser against synthetic
fixtures, and the fault was in path resolution against a real worktree's symlink layout.
Only `python scripts/build.py --dry-run` surfaced it.
- **Occurrences:** 1 (latent — see Exposure)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/build.py:535-573` `_get_source_deployable_scripts` (docstring at
  `:538-539`, `:552-554`); missed phases at `scripts/build_phases.py:1546`
  `build_doc_compliance` and `build_sync_platforms`

**Symptom.** `_get_source_deployable_scripts` is the guard's Set B — the universe it checks
closures against and, per its docstring, the set of "all scripts that will be deployed to
the target project on the next build run." It unions eight per-phase manifest helpers. The
build has at least two more deploy phases that ship `.py` files and neither is among them:

- `build_doc_compliance` (`build_phases.py:1546`) copies `templates/doc-compliance/*` to
  `<target>/scripts/doc_compliance/`. `templates/doc-compliance/cli.py` has five real
  sibling imports — `bootstrap`, `generator`, `verifier`, `scanner`, `config`.
- `build_sync_platforms` deploys `scripts/sync_platforms/sync_platforms.py`, which
  `_manifest_template_standalone_scripts` cannot see because it globs only the **top
  level** of `templates/scripts/` (`.glob("*.py")`, non-recursive, `:529`) and that file
  lives one directory deeper.

Because these paths never enter Set B, the loop at `build.py:1107` never calls
`compute_intra_package_closure` on them at all. An entire deployed Python package is
invisible to the guard, with no warning and no error. Confirmed by querying the function
directly:

```
SET B SIZE: 152
DOC_COMPLIANCE IN SET B: []
SYNC_PLATFORMS  IN SET B: []
```

**Exposure today is nil, and the reason matters.** Both phases deploy their **whole source
directory** — `build_doc_compliance` iterates `dc_dir.rglob("*")` and copies every file.
So all five of `cli.py`'s siblings ship automatically, and a sixth added tomorrow ships
too. These phases are structurally immune to the "one file forgotten from a curated list"
defect that BP-900g-8 exists to close, which is precisely why nobody noticed they were
outside the guard.

**Why file it anyway.** Two reasons, neither hypothetical:

1. **The docstring is wrong in a load-bearing way.** "Eight deployment locations are
   covered" and "every script this build will deploy" are the sentences a future author
   will read before deciding whether a new phase needs registering. They currently say the
   coverage is total when it is enumerated, and nothing detects the divergence — there is
   no test asserting Set B is complete against the `build_*` functions in
   `build_phases.py`.
2. **The immunity is a property of the deploy mechanism, not of the guard.** The moment
   either phase is refactored toward a curated `deploy_map` — which is exactly the pattern
   `build_ac_store` used until this ticket replaced it — the blind spot becomes a live
   silent regression vector with zero guard coverage, and the refactor will look safe
   because it matches the shape of the fix that just landed.

**Fix direction.** Derive Set B rather than unioning hand-written helpers, or — since that
is the larger BP-900g-9 job — add a test that enumerates `build_*` functions in
`build_phases.py` and asserts each one that writes `.py` files has a corresponding manifest
helper, failing on a new phase that has none. Fix `_manifest_template_standalone_scripts`
to `rglob` rather than `glob` while there. Correct the docstring in the same change; a
comment that overstates coverage is how the next author concludes their phase is already
handled.

**Pattern:** a completeness claim written as prose in the docstring of the function whose
incompleteness it is describing.

---
