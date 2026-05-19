---
trigger: model_decision
---

# Git Commits & CI Hooks Rule

## NEVER BYPASS PRE-COMMIT HOOKS
You **MUST NEVER** use flags like `--no-verify` or bypass any pre-commit hooks, CI checks, or complexity limits when committing code.

If a commit fails due to a hook (e.g., SQL complexity, linting, formatting), it means the code does not meet the project's standards.

**What you should do instead:**
1. Fix the underlying issue (e.g., refactor the code to lower cyclomatic complexity, run the linter to fix formatting).
2. Attempt the commit again normally.
3. If you cannot fix the issue or believe the hook needs to be bypassed, you **MUST STOP and ask the user for explicit confirmation**.

You are **ONLY** allowed to bypass a hook using `--no-verify` if the user explicitly instructs or confirms you to do so.
