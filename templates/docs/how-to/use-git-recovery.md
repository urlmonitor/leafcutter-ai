---
title: "How to use the guided git recovery helper"
type: how-to
status: active
created: 2026-07-07
last_updated: 2026-07-07
components:
  - build-orchestration
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
---

# How to use the guided git recovery helper

This guide explains how to run the guided git recovery helper after a
corruption-detection halt has stopped an automatic drive loop and reported
that the shared git repository is damaged.

After completing this guide you will be able to run the helper, review the
repair plan, confirm execution, and verify that the repository is healthy
again.

---

## Prerequisites

- You have received a halt message reporting git object-store corruption
  (zero-byte loose objects, broken branch refs, or a poisoned index).
- `build.py` has been run at least once and `scripts/git_recovery.py` is
  present in your project.
- Python 3.10 or later is available (`python3 --version`).
- You are running the helper from an interactive terminal (not a pipe or
  CI runner).

---

## When to use this helper

Use this helper **only** after a corruption-detection halt has stopped a
parallel drive loop and reported repository damage. Do **not** invoke it
automatically from any script, CI job, or drive loop. The repair process
requires human review and a deliberate confirmation step.

---

## Step 1: Review the halt report

The halt message names the repository path and describes the detected
corruption. Note the repository path — you will pass it to `--repo`.

---

## Step 2: Run the helper in dry-run mode (default)

From your project root, run:

```bash
python scripts/git_recovery.py --repo /path/to/repo
```

Replace `/path/to/repo` with the repository path named in the halt report.
If the repository is your current working directory, you can omit `--repo`:

```bash
python scripts/git_recovery.py
```

The helper will:

1. Detect corruption (zero-byte objects, corrupt branch refs, poisoned index).
2. Print a numbered repair plan describing every action it will take.
3. Prompt: `Execute this plan? [yes/N]:`

Do **not** type `yes` yet — read the plan first.

---

## Step 3: Review the repair plan

The printed plan lists every step the helper will perform, labeled
`[SAFE]` or `[HEAVY]`. Common steps include:

| Label | Example step | What it does |
|-------|-------------|--------------|
| `[SAFE]` | Delete N zero-byte loose object(s) | Removes corrupt empty blobs from the object store. |
| `[SAFE]` | `git fetch --refetch origin` | Re-downloads all missing objects from the remote. |
| `[SAFE]` | `git read-tree HEAD` | Rebuilds the index in-place. |
| `[HEAVY]` | Create fresh worktree for branch `<name>` | Creates a new worktree alongside a poisoned linked worktree; you re-point your work to the new path. |

If any step looks unexpected, type `N` or press Enter to abort. No changes
are made when you abort.

---

## Step 4: Confirm execution

If the plan looks correct, type `yes` at the prompt:

```
Execute this plan? [yes/N]: yes
```

The helper executes the plan in order. If any step fails, execution halts
immediately and the error is printed. The repository is left in its
pre-halt state on the failed step's first write — no further deletions are
attempted after an unrecoverable origin is detected.

A successful run prints:

```
Recovery complete.
```

---

## Step 5: Verify recovery

After the helper reports `Recovery complete.`, run a quick integrity check:

```bash
git -C /path/to/repo status
git -C /path/to/repo log --oneline -5
```

If both commands complete without error, the repository is healthy.

---

## Running without interactive confirmation (--execute flag)

For scripted use where you have already reviewed the plan in a prior
dry-run, you can bypass the interactive prompt:

```bash
python scripts/git_recovery.py --repo /path/to/repo --execute
```

The `--execute` flag skips the confirmation prompt and runs the plan
immediately after printing it. Use this only when you have already reviewed
and accepted the plan in a previous dry-run invocation.

---

## Command-line reference

Run `python scripts/git_recovery.py --help` for the full flag listing.

| Flag | Default | Description |
|------|---------|-------------|
| `--repo PATH` | current working directory | Path to the git repository to recover. |
| `--execute` | off | Skip the interactive confirmation prompt and execute the plan immediately after printing it. |

---

## Troubleshooting

### "Recovery requires interactive confirmation"

The helper detected that stdin is not attached to a terminal (non-TTY
environment, such as a pipe or CI runner). Run the script from an
interactive terminal.

### "origin cannot supply the needed objects"

The remote (origin) has lost the corrupt objects too. The helper stops
without making further changes. In this case:

1. Confirm that `origin` is the correct remote and is reachable.
2. If a backup or mirror of the repository exists, add it as a remote and
   run `git fetch --refetch <backup-remote>` manually.
3. Contact the repository owner if no backup exists — the objects may be
   permanently lost.

### "Recovery refused: shallow or bare clone detected"

The helper does not support shallow or bare clones. If your repository is
a shallow clone, convert it to a full clone first:

```bash
git fetch --unshallow
```

Then re-run the helper.

---

## See Also

- `python scripts/git_recovery.py --help` — full flag reference for the
  deployed copy in your project.
- `docs/architecture/adrs/ADR-001-self-hosting-boundary.md` — explains how
  `build.py` deploys scripts from the package source tree to consumer
  projects and why the how-to lives here rather than in the package source
  repository's root documentation.
