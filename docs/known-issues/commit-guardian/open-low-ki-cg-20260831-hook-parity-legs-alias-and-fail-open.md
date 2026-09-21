---
title: "KI-CG-20260831-hook-parity-legs-alias-and-fail-open — `check_hook_parity`'s two parity legs alias to one directory in a worktree, it compares another branch's build against your templates, and it fail-opens when its roots do not resolve"
description: "KI-CG-20260831-hook-parity-legs-alias-and-fail-open — `check_hook_parity`'s two parity legs alias to one directory in a worktree, it compares another branch's build against your templates, and it fail-opens when its roots do not resolve"
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

# KI-CG-20260831-hook-parity-legs-alias-and-fail-open — `check_hook_parity`'s two parity legs alias to one directory in a worktree, it compares another branch's build against your templates, and it fail-opens when its roots do not resolve

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> Authored as `KI-CG-035` and renamed here: `KI-CG-20260831-hook-scripts-never-invoked` above was
> *also* authored as `KI-CG-035` on another branch the same afternoon. Three concurrent additions,
> one number — exactly the collision `KI-BO-024` describes. Inbound references in commits
> `3846de046` and `1d4ab5e28` use the old id.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/check_hook_parity.py` — `main()`'s
  `project_root = Path.cwd()` and the `runtime_dir` / `deployed_dir` assignments that follow;
  the `hook_parity` block of `templates/scripts/commit_guardian/commit_guardian.json`

**Three defects, one root.** The hook resolves four directories from `Path.cwd()` and runs two
parity legs: **A** runtime-vs-canonical, **B** canonical-vs-deployed. Its config names them
distinctly:

```
"runtime_dir":            "scripts/commit_guardian",
"canonical_template_dir": "templates/scripts/commit_guardian",
"deployed_output_dir":    ".leafcutter/scripts/commit_guardian",
```

**A — the two legs are the same comparison.** In any worktree `build.py` has provisioned,
`scripts/commit_guardian` is a **symlink** to `../.leafcutter/scripts/commit_guardian`:

```
$ readlink -f scripts/commit_guardian .leafcutter/scripts/commit_guardian
.../.leafcutter/scripts/commit_guardian
.../.leafcutter/scripts/commit_guardian
```

`runtime_dir` and `deployed_output_dir` are the *same directory*. Leg A re-runs leg B under
another name, and the question leg A exists to ask — *is the live runtime copy in sync with
canonical?* — is never asked. A passing run prints **nothing**, so there is no per-leg accounting
that would reveal it.

**B — in the recommended layout it fails on files that are not yours.** `CLAUDE.md`'s pre-drive
checklist says to point a worktree's `.leafcutter` at the **main tree's** install. Then
`deployed_dir` — and via A, `runtime_dir` — resolve into a tree built from whatever branch the
main checkout last built. Observed while committing GE-120 work:

```
[check-hook-parity] BLOCKED — hook parity violations detected:
  Script 'check_identifier_uniqueness.py' exists in runtime dir (…/scripts/commit_guardian)
  but is absent from canonical template dir (…/templates/scripts/commit_guardian).
  … (2 more of the same shape, then 4 content divergences)
```

`check_identifier_uniqueness.py` is from **PR #495, not merged into that branch**. The hook
reported another branch's file as a defect in this one. Under this layout it cannot pass on any
branch whose templates differ from the main checkout's last build — every feature branch.

**Its remediation advice is actively harmful here.** Every violation line ends
`Fix: run build.py to regenerate the deployed output.` From a worktree whose `.leafcutter` is the
shared symlink, that deploys **unmerged templates over the install tree every other worktree and
session reads** — the `KI-BP-016` / `KI-BP-017` failure mode. The hook names the one action its
operating context makes unsafe, and names it as the fix.

**C — it fail-opens to a silent 0 when the roots do not resolve.** Run from any subdirectory both
legs are skipped and it still reports success:

```
$ env --chdir=<worktree>/docs python templates/scripts/commit_guardian/check_hook_parity.py
check-hook-parity: WARNING — cannot read canonical manifest … Skipping manifest parity check.
check-hook-parity: INFO — deployed output dir not found or not a directory (…)
exit: 0
```

The contrast is the point: `check_build_drift` resolved correctly from that same directory
(`verified=161`) and `check_hook_trigger_reachability` fail-**closed** with exit 1. Only this hook
treats "I could not find the things I compare" as a pass — the `GE-120a-1` rule violated by a
member of the family adopting it.

**Cause.** `project_root = Path.cwd()` with plain `/` joins and no resolution or comparison of the
results. It never asks whether two of its four configured directories are the same inode, whether
the tree it calls "runtime" belongs to the working copy being committed, or whether it found them
at all. Same cwd-derived-root shortcut as `KI-CG-027`, with a worktree-specific consequence.

**Workaround.** `SKIP=check-hook-parity`. Every other guardrail hook passed on the same commits.
Do **not** run `build.py` to clear it unless the worktree's `.leafcutter` is a real directory
rather than a symlink to the shared tree.

**Fix direction.** Resolve all four paths and detect aliasing: if `runtime_dir` and
`deployed_output_dir` are one path, report leg A as *not run* rather than silently passing it
twice — an unrunnable leg is a gap, not a pass. Establish whether the deployed tree belongs to
this working copy before comparing against it; when it does not, the honest result is
`unverified`, not `BLOCKED`. Make the remediation string conditional on that answer.

**Related.** `KI-CG-027` (same root derivation). `KI-CG-009` (a hook resolving to the main
checkout instead of the worktree). `KI-BP-016` / `KI-BP-017` (what `build.py` against a shared
`.leafcutter` does). `KI-CG-034`, `KI-CG-20260831-hook-scripts-never-invoked` (siblings).

**Pattern:** two configured paths that are one path, and a fix instruction that is safe in the
layout the author imagined and destructive in the layout the project recommends.

---
