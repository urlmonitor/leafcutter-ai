---
title: Two guardrails that were wrong about the repository rather than about the commit
date: "2026-08-31"
time: "20:50"
type: manual
components:
  - commit_guardian
  - testing_quality
summary: "Two defects found during pre-flight for a fast-lane run: check-build-drift picks the first .build_manifest.json it finds and reported all 170 templates as unregistered from an obsolete one, and a test fixture reassigned the real repository's commit identity so subsequent commits were authored by the fixture."
description: "Neither defect was in the change being made. A commit staging one AC YAML file was refused by check-build-drift with 170 findings and verified=0 — the hook had compared nothing, having resolved an August 26 manifest that predates the package_root offset field, whose absence it degrades to an empty string. Separately, unit_tests/portability/test_ge_120e_1.py sets user.name/user.email inside worktrees of the real repository; worktrees share $GIT_COMMON_DIR/config, so the identity leaked repository-wide and outlived the fixture. Both are filed with reproductions, measured figures, and remediation."
---

## Entry

Two defects, both found while preparing a fast-lane run and neither in the work being prepared.

### `check-build-drift` reported every template in the repository as unregistered

A commit staging exactly one AC YAML file — no Python, no templates — was refused with 170 findings:

```text
check-build-drift: RESULT verified=0 uncomparable=170 exempt=0 gaps=170 drifted=0 missing=0 unreadable=0
```

`verified=0` is the tell: the hook did not find drift, it compared **nothing** and then failed on its own inability to compare. `drifted=0` confirms it from the other side.

Two defects compounded. `_resolve_manifest_path()` returns the **first** `.build_manifest.json` found across candidate roots, with no freshness or completeness check — and an August 26 manifest sat at the git toplevel (priority 1) while the current one sat at the workspace root (priority 2). Then, because that older manifest **predates the `package_root` offset field**, the hook's backward-compatibility fallback

```python
package_offset = manifest.get("package_root", "") or ""
```

degraded a missing offset to `""` when the true offset was `leafcutter-ai`. Lookup keys came out as `templates/agents/README.md` against manifest keys spelled `leafcutter-ai/templates/agents/README.md`.

That mismatch is why the count is **170 and not 113**. Only 113 templates are genuinely absent from the stale manifest; 61 are present under a key spelling the hook never generated. Reporting all 170 is the signature of a total key-namespace miss rather than staleness.

It only fires in the package's own main checkout. From a worktree, priority-1 is the worktree root, which holds no manifest, so the search falls through to the good one — and nearly every commit here is made from a worktree. `.build_manifest.json` is gitignored, so the stale file never appears in `git status` either.

Filed as `KI-CG-20260831-manifest-shadowing` (high). Worth noting the irony recorded there: the comment above that fallback explains the git-based heuristic it replaced "failed open", which "is the failure mode this whole ticket exists to remove". The replacement fails *closed* — at a 100% false-positive rate on a commit touching nothing it guards, which is the fastest way to train everyone to reach for `SKIP=`.

### A test fixture reassigned the repository's commit identity

A commit landed authored `GE-120e-1 fixture <ge120e1-fixture@example.com>`. Every other commit on `main` is authored `BrainCandy`.

`unit_tests/portability/test_ge_120e_1.py` builds its scenarios as **worktrees of the real repository** (`git worktree add` with `cwd=_REPO_ROOT`) and then sets an identity inside them:

```python
_run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
```

Setting an identity is legitimate — the fixture makes commits and CI has no global one. The defect is the scope: worktrees share `$GIT_COMMON_DIR/config`, so a plain `git config` writes to the configuration of the **entire repository family**. `tearDownClass` removes the worktree and never unsets the keys, so the value outlives the fixture. Four call sites, all identical.

This repository already sets `extensions.worktreeConfig = true`, so the correctly-scoped `git config --worktree` is available today; the fixture simply does not use it.

Filed as `KI-TQ-012` (high). The leak is silent — `.git/config` is untracked, so no hook, gate or `git status` reports it, and it is visible only in an author line. It was caught incidentally while confirming an unrelated commit with `git show --stat`. Had it not been, the following fast-lane run would have committed and opened a PR under the fixture identity, since the lane's worktree inherits the same shared config.

The two keys were reset and the affected commit re-authored with `--reset-author` before being pushed. The fixture itself is untouched — it lives on an unmerged branch and belongs with that branch's work.

**It came back within the hour, and that changes the severity.** The commit carrying this very changelog was *also* authored `GE-120e-1 fixture`. No pre-commit hook in that run executes pytest, and the test file does not exist on `main` — so the re-set came from a concurrent session running that branch's suite in a **different worktree**, reaching across into this one through the shared `.git/config`. A one-time config repair is therefore worthless; the fix has to be in the fixture. Under a fleet of parallel agents, a test that mutates shared repository state is a race whose loser is silent and persistent.

### Index

`docs/known-issues/README.md`'s per-register counts were 20 low across six rows, having drifted again within hours of the note above them announcing a recount. Recounted; every figure is `grep -c '^### KI-'` over the file, and the note now says to re-run the count rather than trust the table — a hand-maintained index beside files appended by many agents will always lag.
