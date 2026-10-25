---
title: "KI-BO-20261025-wv-recover-depends-on-executor-cwd — the wrong-version recover step found its repository from the executor's cwd, so every drive started outside the workspace halted before dispatching a ticket"
description: "high, resolved — wrong_version_runner.py recover took no arguments and ran git rev-parse --absolute-git-dir in Path.cwd(). The build-feature, build-ticket, build-epic and fast-lane routes dispatched it to command-step-runner without naming the workspace as cwd, so a session outside the workspace got ok false and the drive halted at the recover step. Fixed by a --test-root argument on recover, passed by all four routes."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20261025-wv-recover-depends-on-executor-cwd — one step read the process cwd

> Filed and resolved 2026-10-25. Index: [build-orchestration.md](../../build-orchestration.md).

- **Severity:** high. Every drive started from a session whose directory is not inside the workspace
  halted at the first wrong-version step, before any ticket was dispatched.
- **Status:** resolved by the commit that adds this record (branch `feature/wv-recover-cwd`).
- **Occurrences:** every drive from `/home/henzeh/projects/leafcutter`, which is not a git repository.
  The step answered `{"restored": [], "ok": false, "copy_dir": null, "detail": "git rev-parse
  --absolute-git-dir failed: fatal: not a git repository ..."}`.
- **Where:**
  - `scripts/build_orchestration/wrong_version_runner.py`: `main()` called `recover(Path.cwd())`;
    `recover` took no arguments. `_wvr_gate.gate_root` then ran `git rev-parse --absolute-git-dir` there.
  - `templates/workflows-js/build-feature.js` (`wvRecover`), `build-ticket.js` (`wvRecover`),
    `build-epic.js` (drive-head `be-wv-recover`) and `fast-lane-ship.js` (`fastlane-wv-recover`) built
    `python ".../wrong_version_runner.py" recover` with no workspace argument.

## Mechanism

The routes name the workspace as `target.workspace` in the `command-step-runner` request and expect the
executor to run there. The executor ran the command in the session's directory. The other wrong-version
scripts (`wrong_version_writer.py list`, `wrong_version_gate.py finish`, `wrong_version_runner.py run`)
take `--test-root` and run git there, so they never read the process cwd. `recover` was the one
subcommand that did.

## Fix

`recover` takes `--test-root <worktree>`; without it the process cwd is used, as before. All four routes
pass `--test-root "<worktree>"`. A missing directory, or one that is not a repository, still answers
`ok: false` (exit 1), so the step stays fail-closed.

## Verification

`unit_tests/workflows/test_wv_recover_cwd.py` runs the real runner from a non-git cwd (ok true with
`--test-root`; ok false for a missing or non-repository root) and drives each route template under the
E2 harness, asserting the dispatched command carries `recover --test-root "<worktree>"`. Every check
fails on the previous code.

**Pattern:** a workspace named in a dispatch request is not a working directory; a command that reads its
cwd must be given the path.
