---
title: "KI-BO-20260925-commit-agent-pkill-kills-parallel-test-runs — commit.md Step 0 runs 'pkill -f pytest', which kills every pytest on the machine, and its failure path uses the shared git stash that quick-fix forbids"
description: "low — in a parallel batch drive (or any concurrent session) one ticket's commit phase kills sibling agents' test runs; the resulting failures look like real test failures. commit.md also uses bare git stash/stash pop, which quick-fix banned in BP-600c-3-ii."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-BO-20260925-commit-agent-pkill-kills-parallel-test-runs — commit.md Step 0 runs 'pkill -f pytest', which kills every pytest on the machine, and its failure path uses the shared git stash that quick-fix forbids

- **Severity:** medium (indexed low). Not yet observed; follows directly from the command once two drives or sessions run together, which is routine (28 concurrent sessions were listed on 2026-09-25).
- **Status:** open — no AC. Template read 2026-09-25; impact inferred.
- **Where:** `templates/agents/commit.md:106-120` (`pkill -f "pytest"`), `:381-384` (`git stash` / `git stash pop`).

## Mechanism

`pkill -f pytest` matches by command line across the whole machine, not the agent's own process tree or worktree.
A sibling ticket's `test-runner`, `test-writer` red check or finalize baseline dies mid-run and reports failure or
an incomplete run.

The stash stack is shared by every worktree of a repository. `templates/skills/quick-fix/SKILL.md:338-345`
forbids a bare stash for exactly that reason (BP-600c-3-ii); commit.md was not updated.

## Fix direction

Scope the cleanup to processes whose cwd is inside the current worktree (or drop it); replace stash with a
worktree-local patch file. Both belong in the single `commit_changes.py` proposed in cluster 6 of the 2026-09-25
duplication analysis.
