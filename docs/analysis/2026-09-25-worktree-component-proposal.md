---
title: "One standalone workspace script: shape, CLI, result contract and caller rules"
description: "The proposed single standalone component that replaces the seven worktree recipes: its CLI, its one-JSON-object result contract, what it owns and what callers must do. Part of the worktree-consolidation analysis; amended by the 2026-09-25 decisions (clones, real install files)."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - worktree_manager
  - build_orchestration
---

# One standalone workspace script: shape, CLI, result contract and caller rules

Part of [the worktree-consolidation analysis](2026-09-25-worktree-creation-consolidation.md). The decisions taken on 2026-09-25
(per-feature clones, real install files, `origin/main` everywhere, one script run from a skill)
are in section 8 of that page and in [the decision memo](2026-09-25-worktree-isolation-decision-memo.md);
where they change what is written here, they win.

## 5. Proposal: one standalone worktree component

### 5.1 Shape

One stdlib-only Python file, `templates/scripts/worktree.py`. The name is a proposal. It is
deployed through an explicit entry in the build deploy list (see 5.5). No other code path may
run `git worktree add` or `git worktree remove`.

It must be deterministic:

- no LLM decides anything;
- it runs identically from the main loop, a skill, or any shell-permitted agent;
- a workflow body calls it through one shared helper and a schema.

### 5.2 CLI

```
worktree.py ensure   --kind {ticket|feature|ac|fastlane|epic|scratch} --slug S
                     [--repo-root P] [--base origin/main|main|<ref>] [--reset-existing]
                     [--no-bootstrap]
worktree.py locate   (--slug S --kind K | --path P | --branch B) [--repo-root P]
worktree.py bootstrap --path P [--repo-root P]
worktree.py verify   --path P [--repo-root P] [--expect-branch B]
worktree.py remove   --path P [--delete-branch] [--force] [--repo-root P]
worktree.py base     [--repo-root P]          # replaces worktree_repo_facts base
```

`ensure` is the only creation verb. It is idempotent:

- **Registered and verifies:** reuse, then re-verify, then re-bootstrap anything missing.
- **Branch exists, no worktree:** reconnect. The base policy decides between a checkout of
  the existing tip and a `-B` reset. The chosen policy is reported.
- **Occupied by something else:** `refused`.
- **Nothing exists:** fetch, create, bootstrap, verify.

### 5.3 Result contract

stdout carries **exactly one JSON object and nothing else**. All child-process output is
captured and forwarded to stderr, and a test asserts this.

```json
{
  "status": "ok" | "refused" | "error",
  "code": "OK" | "OCCUPIED" | "NO_REPO" | "AMBIGUOUS_REPO" | "FETCH_FAILED"
          | "GIT_FAILED" | "BOOTSTRAP_FAILED" | "VERIFY_FAILED" | "ON_PROTECTED_BRANCH",
  "message": "one human sentence naming the cause",
  "repo_root": "<abs, main checkout>",
  "layout": "dev" | "consumer",
  "worktree_path": "<abs>",
  "branch": "<full name>",
  "base_ref": "origin/main",
  "base_commit": "<sha read from the worktree's HEAD>",
  "base_matches_origin_main": true,
  "fetch": "ok" | "failed" | "skipped",
  "created": true,
  "reused": false,
  "bootstrap": { "pre_commit_config": true, "hook_shim": true, "build_ok": true,
                 "env": "symlink" | "copy" | "absent" },
  "checks": { "is_linked_worktree": true, "same_repository": true,
              "not_protected_branch": true, "branch_matches": true,
              "precommit_active": true },
  "next_steps": ["…"]
}
```

On any status other than `ok`, `worktree_path` is **absent**, not blank.

Exit codes:

| Exit | Meaning |
|---|---|
| 0 | ok |
| 2 | refused (occupied, or a protected branch) |
| 1 | error |
| 64 | usage error |

The JSON object is printed even on exits 1 and 2.

### 5.4 What the component owns

1. **Repository-root resolution, in this order:**
   1. `--repo-root`.
   2. The parent of `git rev-parse --path-format=absolute --git-common-dir` from cwd. This is
      correct inside any linked worktree.
   3. A bounded search of cwd's immediate children, then of cwd's siblings. Exactly one match
      is required; more than one gives `AMBIGUOUS_REPO` with the list.
   4. Otherwise `NO_REPO`.

   The script's own location is **not** used, because deployed copies live outside the
   repository. This unites plan-feature's snippet (`plan-feature.js:2062-2096`),
   `worktree_repo_facts.base`, and `create-only`'s fallback.
2. **Layout and landing directory.** One rule, owned in one place, reported as `layout`. It
   fixes the adopter-misplacement found in section 3 (the consumer layout must be decided from
   the main checkout, not from the script's location).
3. **Fetch and base.** Always `git fetch origin` first. A failed fetch gives `FETCH_FAILED`
   unless `--allow-stale-base` is passed. The default base is `origin/main` for every kind;
   see open question 3. `base_commit` is read back from the worktree.
4. **Naming.** One table maps `kind` to a prefix, with a sanitiser. Reuse matches the exact
   full branch name.
5. **Bootstrap**, always run on `ensure` whether the worktree was created or reused:
   - run `build.py --target-dir <wt>` and fail on non-zero;
   - require a real `.pre-commit-config.yaml` at the worktree root, not only `.leafcutter`;
   - install hook shims;
   - handle `.env` and `.mcp.json` as today.
   Real files, not symlinks, by default; see open question 2.
6. **Verification before reporting ok**:
   - `git -C <wt> rev-parse --git-common-dir` equals the repository's;
   - the path is a linked worktree, not the main checkout;
   - the branch equals the expected branch and is not `main`/`master`;
   - the pre-commit config exists and the hook shim is installed.
7. **Atomic create.** If any step after `git worktree add` fails, remove the worktree and the
   new branch before returning `error`, or mark it so that the next `ensure` repairs it
   rather than reusing it silently. This closes F5 and KI-BO-20260831-1331.
8. **Remove.** The sweep of `sweep_processes.py`, a dirty-tree refusal, `worktree remove`, the
   MAX_PATH fallback on Windows, `prune`, and a safe branch delete. Confirmation stays with
   the caller; the script takes `--force` only as an explicit flag.
9. **Path spelling.** Every path it emits is absolute and in native form, plus a
   `worktree_path_posix` alias for Git Bash/WSL callers. The BO-3900 helpers in the workflows
   then only need to compare paths, never compute them.

### 5.5 What callers must do

- **Halt on anything other than `status: "ok"`.** No caller may fall back to the current
  checkout, the epic folder, `"unknown"`, or an agent-claimed path. Remove the null-path mode
  in plan-feature (`plan-feature.js:2434-2514` and every `authoringWorktreePath ? … : …`
  branch), build-epic, finalize and fast-lane-ship `:841`.
- **Take `worktree_path` only from the component's JSON**, never from prose.
- **Workflow bodies (ADR-030)**: dispatch through one shared helper that:
  - uses `agent({ …, schema: WORKTREE_RESULT_SCHEMA })`, so E2 validates the shape (ADR-030
    §Finding, `docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md:123-124`);
  - sends it to an agent with `permits_shell: true` (worktree-agent, or a new narrow
    "shell-runner"), **never status-checker**;
  - instructs "run this exact command, return stdout verbatim";
  - treats a refusal, non-JSON output or a missing `status` as `error`.
- **Skills and agents** call the script directly in Bash, and stop on a non-zero exit.
- **Deployment.** Add `worktree.py` to the explicit deploy list, per the deploy-manifest rule
  (`CLAUDE.md:280-295`), not to a shallow glob. Callers reference it by a path the component
  itself can print (`worktree.py where`), or by the resolved absolute path that the
  plan-feature pre-flight already computes in the main loop and passes via `args`. Delete
  `leafcutter-ai/scripts/setup_ticket_worktree.py` so there is exactly one source, and stop
  producing `leafcutter-ai/.leafcutter/` (open question 6).
