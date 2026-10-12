---
title: "KI-CG-20261008-build-drift-doc-claims-staged-file-trigger — `docs/build-drift-hook.md` says both drift gates fire on a staged file, but both are `always_run` and never read the staged list"
description: "low — a reader-facing doc misdescribes when the gates fire, which makes an unrelated drift finding look like a property of the commit."
type: reference
category: reference
status: active
created: '2026-10-08'
last_updated: '2026-10-08'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/build-drift-hook.md
---

# KI-CG-20261008-build-drift-doc-claims-staged-file-trigger — `docs/build-drift-hook.md` says both drift gates fire on a staged file, but both are `always_run` and never read the staged list

> One known issue, flagged by the documentation-expert pass on 2026-10-08 and
> verified against the deployed config. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading
> is the `**Severity:**` line below.

- **Severity:** low — documentation only; no gate behaves wrongly.
- **Status:** open — no AC yet.
- **Occurrences:** 1 · **First seen:** 2026-10-08 · **Last seen:** 2026-10-08
- **Where:** `docs/build-drift-hook.md`, the overview table (rows for `check-build-drift` and `check-output-drift`) and the two bullets under it that say each gate "fires when a ... file is staged".

**What the doc says.**

```
| `check-build-drift`  | ... | Template file staged with hash different from manifest |
| `check-output-drift` | ... | Output file staged with hash different from what build.py would render |
```

**What the config says.** Both hooks in `.leafcutter/pre-commit-config.yaml` carry
`pass_filenames: false` and `always_run: true`. Neither is given the staged file list,
and both run on every commit, scanning the whole template tree and the whole output
tree respectively against `.build_manifest.json`. `docs/2b_direction_b_output_drift_detection.md`
already describes `check-output-drift` correctly; this doc contradicts it.

**Why it matters.** A reader who believes the gates are staged-file-scoped will read a
finding about a file they did not touch as a bug in the gate, or as something their
commit caused. That is exactly the misreading that cost time on 2026-10-05: `check-build-drift`
named 13 drifted templates on a commit that staged three unrelated files. The real cause
was a stale manifest (see `KI-CG-20260831-manifest-shadowing`), and the "it fires on staged
files" mental model pointed in the wrong direction.

**Fix.** Rewrite the two table cells and the two bullets to say each gate runs on every
commit and compares the whole tree against the manifest.
