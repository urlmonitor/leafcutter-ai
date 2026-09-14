---
title: A test fixture stops renaming everyone who commits to this repository
date: "2026-09-07"
time: "14:20"
type: manual
components:
  - testing_quality
summary: "Closes KI-TQ-012. Two portability fixtures build their scenarios as worktrees of the real repository and set a git identity inside one; worktrees share the config, so the identity escaped to every worktree and every session. It misattributed ten commits in a single day. Identity now comes from the environment and nothing is written to any config file."
description: "Fixed at the seam rather than per call site: both fixtures already had a _GIT_ENV_OVERRIDES dict feeding their subprocess environment, so the identity moved there and all ten git config calls were deleted. Verified by setting the repository identity, running both suites, and re-reading it unchanged — the same run previously guaranteed a poisoned config."
---

## Entry

Two fixtures in `unit_tests/portability/` build their scenarios as **worktrees of the real repository** — `git worktree add` with `cwd=_REPO_ROOT` — and then set a commit identity inside one:

```python
_run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
```

Setting an identity is legitimate: the fixtures make commits and CI has no global one. The defect is **scope**. Worktrees share `$GIT_COMMON_DIR/config`, so a plain `git config` inside one writes to the configuration of the entire repository family — and `tearDownClass` removes the worktree without ever unsetting the keys.

On 2026-09-07 that misattributed **ten commits** to `GE-120e-1 fixture` and `GE-120e-1-i fixture`, several on open pull requests, in worktrees these tests have never heard of. Each was caught only by reading an author line and repaired by hand; the value returned on the next suite run every time.

### Fixed at the seam, not per call site

Both files already had a `_GIT_ENV_OVERRIDES` dict feeding `subprocess.run(env=...)`. The identity moved there as `GIT_AUTHOR_*` / `GIT_COMMITTER_*`, and all ten `git config user.*` calls were deleted.

Environment variables live and die with the subprocess. No configuration file is written at all, so there is nothing to leak and nothing to clean up.

**`git config --worktree` was the obvious alternative and is wrong here.** It scopes correctly, but only where `extensions.worktreeConfig` is enabled — and that lives in untracked `.git/config`. This repository has it set locally, so the one-word fix would have passed every local check and failed on a fresh CI clone. That is the kind of fix that looks verified and is not.

### The count was wrong twice before it was measured

The entry was filed as "four call sites in one file", corrected to "two files, six sites", and the real figure is **two files, ten sites** — eight in `test_ge_120e_1.py`, two in `test_ge_120e_1_i.py`. Both earlier counts were inferred from *which commits happened to be misattributed* rather than from grepping the fixtures. Counting the symptom undercounts the cause.

A repo-wide sweep found roughly forty test files setting `git config user.*`. **Only these two leak.** The rest set identity inside a throwaway `git init` repository, which owns its config and cannot escape. The discriminator is a worktree of the *real* repository, not the presence of a `git config` call — and one file that looks leaky to a naive grep, `test_check_doc_frontmatter_worktree_pathbase.py`, worktrees a temp repo it created itself and is safe.

### Proof

The repository identity was set to a known value, both suites were run — **10 passed** — and the identity was re-read afterwards: **unchanged**. Before this change, the same run guaranteed a poisoned config.

### A duplicate id, left in place

This defect carries **two** entries, both numbered `KI-TQ-012`, filed a week apart by different authors who each missed the other. Both are closed by this change and neither is renumbered, since both are cited by id and the register already carries an unrepaired `KI-CG-012` collision for the same reason. That the same high-severity defect could be filed twice is its own finding: the register is long enough that filing is cheaper than searching.
