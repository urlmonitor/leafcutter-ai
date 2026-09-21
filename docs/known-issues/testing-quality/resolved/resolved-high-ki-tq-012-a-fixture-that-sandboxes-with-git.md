---
title: "KI-TQ-012 — A fixture that sandboxes with `git worktree add` sets its identity in the *real* repository's config, and every worktree and every session inherits it"
description: "KI-TQ-012 — A fixture that sandboxes with `git worktree add` sets its identity in the *real* repository's config, and every worktree and every session inherits it"
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

# KI-TQ-012 — A fixture that sandboxes with `git worktree add` sets its identity in the *real* repository's config, and every worktree and every session inherits it

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **DUPLICATE ID.** A second, independently-filed `KI-TQ-012` exists further down this
> file ("A test fixture reassigns the real repository's commit identity…"). Same defect,
> same two files, filed twice on different days without either author seeing the other.
> Both are closed by the same fix. Neither is renumbered: both are cited by id elsewhere,
> and this register already carries an unrepaired `KI-CG-012` collision for the same reason.
> That two people could file the same high-severity defect a week apart is itself the
> finding — the register is long enough that filing is cheaper than searching.

- **Severity:** high
- **Status:** **RESOLVED 2026-09-07.** The identity now comes from `GIT_AUTHOR_*` /
  `GIT_COMMITTER_*` in `_GIT_ENV_OVERRIDES`, and every `git config user.*` call is gone
  from both fixtures. Environment variables live and die with the subprocess, so no
  configuration file is written and nothing can outlive the run.
  **Proven, not asserted:** the repository identity was set to a known value, both suites
  were run (10 passed), and the identity was re-read afterwards — unchanged. Before the fix
  the same run guaranteed a poisoned config.
- **Occurrences:** **10** misattributed commits in a single session on 2026-09-07, several
  on open pull requests, across worktrees these tests have never heard of
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-07 · **Closed:** 2026-09-07
- **Where:** `unit_tests/portability/test_ge_120e_1_i.py` — the merge fixture's `build()`
  (`git worktree add` at ~L264, `git config user.*` at L270-271) and its `tearDownClass`
  (`git worktree remove --force`, ~L338)

**Symptom.** 42 commits across this repository's local branches — authored by several unrelated
concurrent sessions over roughly eleven days — carry the author
`GE-120e-1-i fixture <ge120e1i-fixture@example.com>`. None of those sessions was running the
GE-120 tests. Found while inspecting an unrelated build-output commit:

```
$ git log --all --author="ge120e1i-fixture" --oneline | wc -l
42
$ git config --list --show-origin | grep user\.
file:/home/henzeh/.gitconfig                     user.email=<the real identity>
file:.../leafcutter-ai/.git/config                user.email=ge120e1i-fixture@example.com
file:.../leafcutter-ai/.git/config                user.name=GE-120e-1-i fixture
```

**Cause.** A linked git worktree **does not have its own config** — it shares `.git/config` with
the parent repository. The fixture builds its sandbox with
`git worktree add --detach <tmpdir> HEAD` run at `cwd=_REPO_ROOT`, then sets an identity with
`git config user.email …` / `user.name …` at `cwd=<the sandbox>`. Because the sandbox is a linked
worktree rather than a standalone repo, that `git config` — no `--file`, no `--worktree` — lands
in `leafcutter-ai/.git/config`. The fixture believes it is scoping an identity to a throwaway
directory; it is in fact setting the identity for the whole repository.

**Blast radius.** Repo-wide and cross-session. Every one of this workspace's 80+ worktrees reads
that one config file, so a single test run silently re-authored every subsequent commit made by
every parallel agent and every human, on every branch, until someone noticed.

**Teardown does not save it.** `tearDownClass` runs `git worktree remove --force`. It never
unsets the two keys, so the pollution outlives the fixture, the test run, and the session.

**Why it stayed invisible for eleven days.** Nothing in the pipeline reads commit authorship, so
no gate could object. And `origin/main` is **clean** — 0 of the 42 are reachable from it — because
GitHub's squash-merge rewrites the author to the PR account. So the one surface anybody reviews
shows the correct name, while the local history that shows the wrong one is never looked at. The
defect is invisible from exactly where people look and visible only from where they don't.

**The correct pattern is already in this repo.**
`unit_tests/commit_guardian/test_check_doc_frontmatter_worktree_pathbase.py` builds its sandbox
with `git init -b main` — a standalone repo with its **own** config — and then sets the identity
there. That is safe, and it is the only other fixture that both creates a git sandbox and sets an
identity; of the 11 fixtures using `git worktree add`, this one is the sole offender. So the fix
is not novel work, it is applying the sibling's approach.

**Fix direction.** Never run `git config` inside a `git worktree add` sandbox. In preference
order: (1) pass the identity per invocation — `git -c user.name=… -c user.email=… commit …`;
(2) set `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` / `GIT_COMMITTER_NAME` / `GIT_COMMITTER_EMAIL` in
the subprocess environment; (3) `git init` a standalone temp repo instead of adding a worktree.
The first two **cannot leak by construction**, which is why they beat "remember to unset it in
teardown" — a teardown that must run correctly is the thing that already failed here.

**Guard.** Cover it with a test that snapshots `git config --local --get user.email` in the real
repo before and after the suite runs and fails on any change. Note that a guard asserting only
"the fixture set an identity" passes against the defect — the assertion has to be about the
**parent repo's** config, which is the thing the fixture never meant to touch.

**Remediation applied 2026-08-31.** Both keys were unset from `leafcutter-ai/.git/config`;
committing now resolves to the real global identity again. The 42 existing commits were left
as they are — rewriting author metadata across 80+ live worktrees and open PR branches costs
considerably more than the misattribution does, and none of it reached `main`.

**Worth noting.** The fixture belongs to GE-120 — the epic whose stated purpose is *"trust that a
green check actually checked something"* — and to `GE-120e-1-i` specifically, a criterion about
attributing a change set to its real author. Its own harness silently misattributed 42 commits in
the repository it was written to verify, and every check stayed green throughout.

**Related.** `KI-CG-009` (a hook resolving the repo root to the main checkout rather than the
worktree — the same "worktrees share more than you think" family).

**Pattern:** shared mutable state reached through a handle that looks scoped.

---
