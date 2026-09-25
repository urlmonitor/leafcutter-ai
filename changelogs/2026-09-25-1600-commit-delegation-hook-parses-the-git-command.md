---
title: "The commit-delegation hook now recognises a commit by the git command that runs, not by the words in the command"
date: "2026-09-25"
time: "16:00"
type: manual
components:
  - build_pipeline
  - commit_guardian
summary: "enforce_commit_delegation used to block any Bash command containing the text 'git commit'. It missed `git -C <path> commit` and every other spelling with git global options, and it blocked commands that only quoted the phrase. It now parses the command and blocks only when git's commit subcommand actually runs."
description: "The PreToolUse hook tested `\"git commit\" in command`. That missed `git -C <dir> commit`, `git -c k=v commit` and `git --git-dir=... commit`, which is how five prompt sites commit (finalize-feature.js, build-single-ticket, quick-fix, plan-feature), so commits from those sites were never delegated to the commit agent. The same substring test blocked read-only commands that only mentioned the phrase, such as a `gh pr create --body` text or a grep (KI-CG-016). templates/hooks/enforce_commit_delegation.py now splits the command into simple commands on unquoted `&&`, `||`, `;`, `|`, `&`, newlines and parentheses, and also checks the bodies of `$(...)` and backtick substitutions. It tokenises each simple command with shlex, skips leading VAR=value assignments and git's global options, and blocks when the subcommand is `commit`. It also follows wrappers (env, sudo, xargs ...), `sh -c` scripts and `eval`. If shlex cannot parse a command's quoting, the hook blocks it when a commit word follows a git word (fails closed). The COMMIT_AGENT_MODE=1 exemption is unchanged. AC BP-1100d-3. unit_tests/commit_guardian/test_enforce_commit_delegation_parses_git_argv.py runs the real hook as a subprocess on 17 commands. Reverting the hook turns 10 of them red. Resolves KI-CG-20260925-commit-delegation-hook-misses-git-dash-c and KI-CG-016."
commits: [5fba8382]
breaking: false
---

## Entry

The commit-delegation hook now blocks `git -C <path> commit` and other spellings that use
git's global options. Commands that only mention "git commit" inside a quoted argument,
like a PR body or a grep pattern, are no longer blocked.
