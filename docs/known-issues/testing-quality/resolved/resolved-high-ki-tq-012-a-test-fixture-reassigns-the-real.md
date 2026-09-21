---
title: "KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture"
description: "KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **DUPLICATE ID** — see the note on the other `KI-TQ-012` earlier in this file. Same
> defect, filed twice a week apart; both closed by the same fix; neither renumbered,
> because both are cited by id.

- **Severity:** high
- **Status:** **RESOLVED 2026-09-07** — identity now supplied via `GIT_AUTHOR_*` /
  `GIT_COMMITTER_*` in `_GIT_ENV_OVERRIDES`; every `git config user.*` call removed from
  both fixtures. Verified by setting the repository identity to a known value, running both
  suites (10 passed), and re-reading it: **unchanged**.
- **Occurrences:** **10** misattributed commits in one session (2026-09-07), several on open
  pull requests. **The count in this line was wrong twice before it was measured** — filed as
  "four sites in one file", corrected to "two files, six sites", and the real figure is
  **two files, TEN sites** (8 in `test_ge_120e_1.py`, 2 in `test_ge_120e_1_i.py`). Both
  earlier counts came from reading the commits that happened to be misattributed rather than
  from grepping the fixtures.
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-07 · **Closed:** 2026-09-07
- **Scope check, so nobody re-audits it:** a repo-wide sweep found ~40 test files setting
  `git config user.*`. Only these two leak. The rest set identity inside a throwaway
  `git init` repository, which has its own config and cannot escape. The discriminator is
  `git worktree add` against the *real* repository root, not the presence of a `git config`
  call. One file, `test_check_doc_frontmatter_worktree_pathbase.py`, looks leaky to a naive
  grep and is not — it worktrees a temp repo it created itself.
- **Why not `git config --worktree`:** it scopes correctly but requires
  `extensions.worktreeConfig`, which lives in untracked `.git/config`. This repository has it
  enabled locally; a fresh CI clone does not, so that fix would pass here and fail in CI. The
  environment works everywhere and writes nothing.
- **Where:** `unit_tests/portability/test_ge_120e_1.py` — lines 234, 300, 344, 543 — **and
  `unit_tests/portability/test_ge_120e_1_i.py`**, 2 more sites (found by grepping
  `fixture@example.com` across the branch after a third misattributed commit; the entry
  originally named one file because that is the one whose identity happened to land first)
  (currently on branch `EPIC-TrustThatAGreenCheckActuallyChecked`, unmerged); leaks into
  `leafcutter-ai/.git/config`, shared by every worktree

**Symptom.** A commit made from the package's main checkout landed with this author:

```text
commit 0a6ccac5e7a2652f2b650c82b9515849e054972f
Author: GE-120e-1 fixture <ge120e1-fixture@example.com>
```

`git config --local --get-regexp '^user\.'` in `leafcutter-ai/` returned:

```text
user.email ge120e1-fixture@example.com
user.name  GE-120e-1 fixture
```

Every prior commit on `main` is authored `BrainCandy <105064581+urlmonitor@users.noreply.github.com>`.

**Cause.** The fixture builds its scenarios as **worktrees of the real repository**, not as
throwaway `git init` sandboxes:

```python
_run_git(["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT)
_run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
_run_git(["config", "user.name",  "GE-120e-1 fixture"],            cwd=self.root)
```

Setting an identity is legitimate — the fixture creates commits and CI has no global
`user.email`. The defect is the **scope**. Worktrees share `$GIT_COMMON_DIR/config`, so a plain
`git config` inside a worktree writes to the **shared configuration of the entire repository
family**, not to the worktree. `tearDownClass` calls `git worktree remove --force` and never
unsets the keys, so the identity outlives the fixture that set it.

This repository already has `extensions.worktreeConfig = true`, which means the correctly-scoped
form — `git config --worktree user.email …` — is available today. The fixture just does not use
it. Four sites, all identical.

**Why this is high and not cosmetic.** The leak is silent, persistent, and repository-wide:

- It affects **every** commit from that checkout afterwards, not just the test run — and
  because worktrees share the config, every worktree of the repo too. Any epic drive or fast-lane
  run committing while this is set produces misattributed commits under an address that is not a
  real contributor.
- `.git/config` is not tracked, so nothing in `git status`, no pre-commit hook, and no CI gate
  reports it. It is visible only if someone reads an author line — which is precisely the field
  everyone skims past.
- Misattribution is not locally repairable once pushed. Rewriting author metadata on merged
  history is a force-push to a protected branch.

**How it was found.** Incidentally, and late. The author line was noticed while confirming an
unrelated commit's contents with `git show --stat`. Nothing surfaced it deliberately. Had the
check not happened, the following fast-lane run would have committed and opened a PR under the
fixture identity, since the lane's worktree inherits the same shared config.

**Remediation.**

1. Change all four sites to `git config --worktree …`, which this repo's
   `extensions.worktreeConfig` already supports. One word per site.
2. Better still, stop mutating repository state at all: pass the identity per invocation with
   `git -c user.name=… -c user.email=… commit`, which cannot outlive the process, or set
   `GIT_AUTHOR_*` / `GIT_COMMITTER_*` in the subprocess environment.
3. Give `tearDownClass` an `unset` for anything it did set, so a mid-run failure cannot strand
   the value.
4. Add a guard: a test that asserts `user.email` in the repository config is unchanged across
   the suite would have caught this on the first run. The suite currently has no notion that
   the real repository is shared mutable state.

**Repair applied.** The two keys were reset to the correct identity and the affected commit
re-authored with `git commit --amend --reset-author` before it was pushed. The fixture itself is
untouched — it lives on an unmerged branch and fixing it belongs with that branch's work, not
with an unrelated docs change.

**Recurrence observed within the hour — this is not a historical leak.** The keys were reset at
roughly 20:00. The next commit, made about an hour later from a *different* worktree, was again
authored `GE-120e-1 fixture`. `git config --show-origin` located the value in the shared
`leafcutter-ai/.git/config`, and no pre-commit hook in that run executes pytest. The test file
does not exist on `main` at all — `unit_tests/portability/` there holds four files, none of them
`test_ge_120e_1.py`. So the re-set came from a **concurrent session running that branch's suite
in its own worktree**, and it reached across into every other worktree of the repository.

Three things follow that the single-occurrence framing above understates:

- The blast radius is the whole repository family, live and concurrent. Any agent committing
  anywhere while another runs this suite inherits the identity, with no signal at either end.
- A one-time repair is worthless. The value returns on the next run, so the fix has to be in the
  fixture, not in the config.
- Under the fleet of parallel agents this repository is designed around, "a test that mutates
  shared repository state" is not an isolation nicety — it is a race with a persistent,
  invisible loser.

**Related.** User-memory `feedback_test_isolation_pitfalls` records the sibling traps (root
`conftest.py` import blast radius; `importlib.reload()` masking cold-import bugs). `KI-TQ-008`
(a repository-global tree-purity guard false-positives under concurrent agents) is the same
underlying assumption from the other direction: tests here treat the real repository as private
scratch space when it is neither private nor scratch.

**Pattern:** a fixture that isolates the *filesystem* (a fresh worktree, removed on teardown)
while sharing the *configuration* that worktree points at — so the visible half of the sandbox
is convincing and the invisible half leaks permanently.

---
