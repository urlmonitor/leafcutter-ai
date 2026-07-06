---
title: "How to Verify Pre-commit Protection is Active in a Worktree"
description: "Step-by-step guide to running the verify_precommit_active.py probe and interpreting its four checks to confirm that pre-commit hooks will fire in a git worktree."
intent: do
last_updated: 2026-07-06
---

# How to Verify Pre-commit Protection is Active in a Worktree

## When to use this guide

Use this guide when you need to confirm that pre-commit hooks will actually fire in a worktree before committing code. Run the probe after provisioning a new worktree, after a commit succeeds with no hook output, after a WorktreeQualityGateGuard gate reports a failure, or any time you suspect the silent-skip failure mode may be active.

---

## Section 1: Overview

The `verify_precommit_active.py` probe answers a specific question: will pre-commit hooks **fire** on the next `git commit` in this worktree?

The probe does not merely check whether the hook binary is installed or whether a config file appears to be present on disk. It verifies all four conditions that must hold simultaneously for a single hook to run. Passing all four gives you a strong guarantee that hooks are active — not just structurally present.

### The silent-skip failure mode

A fresh worktree created from `origin/main` has neither a `.leafcutter` symlink nor a direct `.pre-commit-config.yaml` file. The `.leafcutter` symlink that provides the config is only created by `install_shims` in the main working tree; a fresh worktree has no equivalent.

When `git commit` runs in this state, the pre-commit framework checks for a config file before running any hooks. Finding none, it exits early — this is the `PRE_COMMIT_ALLOW_NO_CONFIG=1` behavior. Zero hooks fire. Code is committed unchecked. The commit appears to succeed normally.

### How the probe defends against it

The probe detects this condition before any commit lands. Check B fails (config not resolvable) and Check C fails (hook shim not installed). The WorktreeQualityGateGuard system invokes the probe at three lifecycle gates:

- **Create-time gate** — immediately after `setup_ticket_worktree.py` provisions the worktree.
- **Pre-drive gate** — before any ticket agent begins implementation (SKILL.md pre-drive check).
- **Commit-phase gate** — before the commit agent stages and commits changes.

All three gates halt on any probe failure. The silent-skip condition is caught before code lands in a commit, not discovered in a post-merge audit.

---

## Section 2: The Four Checks

The probe runs four checks in order. A failure on any check adds that check's key name to the `failing_checks` list in the output. All four must pass for the probe to exit 0.

### Check A — Binary presence (`binary`)

**Function:** `check_a_binary_on_path()`

Calls `shutil.which("pre-commit")` to verify the pre-commit executable is discoverable on `PATH`. Returns `True` if found, `False` otherwise. No execution occurs.

**What it detects:** pre-commit is not installed, or is installed but not on the `PATH` that git hooks inherit.

### Check B — Config resolvable (`config`)

**Function:** `check_b_config()`

Resolves the pre-commit config file from the current working directory using a two-step lookup:

1. `.leafcutter/pre-commit-config.yaml` — canonical location, present when the `.leafcutter` symlink is installed.
2. `.pre-commit-config.yaml` — direct file in the worktree root (fallback for NTFS/copy-based installs).

If neither exists the check fails immediately. If a path resolves, the file must also be readable, parse as valid YAML, and be non-empty.

**What it detects:** the silent-skip failure mode. A fresh worktree with no `.leafcutter` symlink has no config, so Check B fails and the gate halts before any commit.

### Check C — Git hook installed (`git_hook`)

**Function:** `check_c_git_hook()`

Resolves the shared git hooks directory via `_resolve_git_commondir()`. This helper handles both topologies:

- **Main working tree:** `.git` is a directory; the directory itself is the commondir.
- **Worktree:** `.git` is a `gitdir:` file that references a path containing a `commondir` file, which in turn points to the shared `.git` directory.

Once resolved, the check reads `<commondir>/hooks/pre-commit` and verifies the sentinel string `"pre-commit"` is present inside the file. A hook installed by `pre-commit install` always contains this string; an absent or foreign hook does not.

**What it detects:** `pre-commit install` was never run (hook shim absent), or the hook exists but was not installed by pre-commit (foreign or corrupt hook).

### Check D — Canary emits expected token (`canary`)

**Function:** `check_d_canary()`

Invokes `precommit_canary.py` as a subprocess with a 10-second timeout and inspects stdout for the sentinel `PRECOMMIT_CANARY_OK`. This is the only check that actually executes code end-to-end: it confirms the hook invocation path is not just structurally present but functionally operational.

If the canary times out (after 10 seconds), the check fails closed — the timeout is caught and reported as a failure, not swallowed.

**What it detects:** hook infrastructure appears correct but is broken in practice. The hook exists, the config resolves, but actual hook execution does not produce the expected sentinel output.

---

## Section 3: Running the Probe

Run the probe from the worktree root. The script resolves all paths from the current working directory:

```bash
python scripts/commit_guardian/verify_precommit_active.py
```

The probe always writes a single JSON object to stdout and exits with a code indicating pass or fail. No flags are required — JSON output is always emitted.

**Sample all-pass output (exit code 0):**

```json
{"binary": true, "config": true, "git_hook": true, "canary": true, "failing_checks": []}
```

**Sample failing output — Check B, C, and D failing (fresh worktree, no config or hook):**

```json
{"binary": true, "config": false, "git_hook": false, "canary": false, "failing_checks": ["config", "git_hook", "canary"]}
```

---

## Section 4: Reading the Output

### Output key reference

| Key | Check | Meaning when `false` |
|-----|-------|----------------------|
| `binary` | A | pre-commit executable not found on PATH |
| `config` | B | `.pre-commit-config.yaml` not resolvable in this worktree |
| `git_hook` | C | Hook shim absent or does not contain the `"pre-commit"` sentinel |
| `canary` | D | `precommit_canary.py` subprocess did not emit `PRECOMMIT_CANARY_OK` |

### `failing_checks` list

The `failing_checks` field contains the key name of each failed check, in the order the failure was detected (A through D). An empty list (`[]`) means all checks passed.

### Exit code semantics

- **Exit code 0** — all four checks passed; hooks will fire on the next commit.
- **Exit code 1** — one or more checks failed; commits in this worktree are not protected.

### Interpreting each failing key and what to do

**`binary` fails (Check A) — pre-commit not installed:**

```bash
pip install pre-commit
```

After installing, re-run the probe to confirm Check A passes before proceeding.

**`config` fails (Check B) — config file not resolvable:**

Run the self-heal script. It creates the `.leafcutter` symlink (preferred) or copies `.pre-commit-config.yaml` directly into the worktree root when symlinks are unavailable. The script reads `Path.cwd()` and accepts no positional arguments, so you must first `cd` into the worktree root and then invoke it with no arguments:

```bash
cd <worktree-root>
python scripts/commit_guardian/ensure_precommit_config.py
```

Re-run the probe. If Check B now passes but Check C still fails, proceed to the next step.

**`git_hook` fails (Check C) — hook shim not installed:**

Register the pre-commit hook in the shared git hooks directory:

```bash
pre-commit install
```

Run this from the worktree root after Check B is resolved (the config must be resolvable for `pre-commit install` to succeed).

**`canary` fails (Check D) — hook installed but canary subprocess did not emit `PRECOMMIT_CANARY_OK`:**

Check D is distinct from Check C. Check C verifies the hook file exists and contains the `"pre-commit"` sentinel string; Check D goes further and actually runs `precommit_canary.py` as a subprocess, inspecting its stdout for the `PRECOMMIT_CANARY_OK` token. Check D fails when the hook file exists and Check C passes, but the canary subprocess does not emit the expected token. This can happen if the hook was installed by a different tool, was manually edited after install, or was corrupted after `pre-commit install` ran. Re-install the hook to restore the standard pre-commit shim:

```bash
pre-commit install
```

---

## Section 5: The Silent-Skip Failure Mode

### How a fresh worktree becomes unprotected

When `setup_ticket_worktree.py` provisions a new worktree from `origin/main`, none of the following are present inside it:

- The `.leafcutter` directory (or symlink) — exists only in the main working tree after `install_shims` runs.
- `.pre-commit-config.yaml` — provided by `.leafcutter` in the main tree; not inherited by worktrees.
- The git hook shim — `pre-commit install` must be re-run explicitly in each worktree or the shared hooks directory must already have the shim from a previous install in the main tree.

### What happens when git commit runs without protection

With no config file present, the pre-commit framework exits early before running any hooks. This behavior is governed by `PRE_COMMIT_ALLOW_NO_CONFIG=1` — pre-commit's own mechanism for gracefully skipping when no config exists. From the user's perspective, `git commit` completes normally. There is no error, no warning, and no hook output. The commit lands unchecked.

### How the probe catches it

The probe runs Check B (`check_b_config()`) and finds neither `.leafcutter/pre-commit-config.yaml` nor `.pre-commit-config.yaml` in the worktree root. Check B returns `False` and `"config"` is appended to `failing_checks`.

Check C (`check_c_git_hook()`) independently verifies the shared git hooks directory. If `pre-commit install` was never run in the worktree, the hook shim will be absent (or present from a prior main-tree install but without this worktree's config context). Check C returns `False` and `"git_hook"` is appended.

The gate reads `failing_checks`, finds it non-empty, and halts before any commit is attempted. The self-heal script (`ensure_precommit_config.py`) is surfaced as the remediation action.

---

## Cross-links

**Architecture diagrams:**

- [Probe sequence diagram](../architecture/diagrams/probe-sequence.md) — Check A through D flow with decision points, exit codes, and JSON output structure
- [Self-heal component diagram](../architecture/diagrams/self-heal-component.md) — `ensure_precommit_config` component, git-common-dir resolver, and symlink/copy fallback
- [Parent component overview](../architecture/components/worktree-quality-gate-guard.md) — L2-Container view of the full WorktreeQualityGateGuard system
- [Gates sequence diagram](../architecture/diagrams/gates-sequence.md) — create-time, pre-drive, and commit-phase gates invoking the probe

**Implementation:**

- [`scripts/commit_guardian/verify_precommit_active.py`](../../scripts/commit_guardian/verify_precommit_active.py) — four-check orchestrator probe
- [`scripts/commit_guardian/ensure_precommit_config.py`](../../scripts/commit_guardian/ensure_precommit_config.py) — self-heal script for Check B failures (symlink or copy install)
