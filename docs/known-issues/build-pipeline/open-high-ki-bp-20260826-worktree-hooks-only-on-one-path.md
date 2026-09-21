---
title: "KI-BP-20260826-worktree-hooks-only-on-one-path — A worktree made with plain `git worktree add` has no hooks, and nothing at commit time says so"
description: "KI-BP-20260826-worktree-hooks-only-on-one-path — A worktree made with plain `git worktree add` has no hooks, and nothing at commit time says so"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260826-worktree-hooks-only-on-one-path — A worktree made with plain `git worktree add` has no hooks, and nothing at commit time says so

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **First entry using the date-and-slug id form.** See "Adding an issue" at the top of this
> file, and KI-BO-024 for why the sequential form was abandoned for new entries.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 3 in one session (2026-08-26), all in the same session by the same operator
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/setup_ticket_worktree.py` — `_establish_pre_commit_config`
  (~:585-670) and the AC-5 fail-fast probe at `~:864-872`. Also `CLAUDE.md` → "Worktree
  pre-commit config (MANDATORY for worktree-based drives)".

**The provisioning code is correct. That is the point of this entry.**
`_establish_pre_commit_config` is well built: no-op if already present, symlink `.leafcutter`
first, fall back to copying `.pre-commit-config.yaml` on filesystems where `os.symlink`
raises, warn and continue if neither source exists — and then a fail-fast probe converts that
last warn-and-continue into a hard `BootstrapError`. Nothing below is a criticism of it.

The defect is that **this is the only path that runs it.** `git worktree add` is the obvious
way to make a worktree, it is what the git documentation teaches, and it performs none of
this. A worktree created that way has no `.pre-commit-config.yaml`, so `git commit` runs with
`PRE_COMMIT_ALLOW_NO_CONFIG=1` and **every package hook is skipped in silence**.

**Evidence — three for three, in one session.** An operator created three worktrees with
`git worktree add` (`po-edit`, `ac-supervisor`, `red-baseline`). All three lacked
`.pre-commit-config.yaml`. This was noticed only because one commit happened to refuse
outright; the other two would have committed clean with no hooks at all.

The cost is not hypothetical. Once the config was in place, the AC guards on ONE of those
branches caught three real defects that would otherwise have merged:

| guard | what it caught |
|---|---|
| `check-ac-governance` | a new AC file with no `origin_agent` |
| `check-ac-parent-covered-by` | **8** missing L2→L3 parent back-links |
| `check-ac-schema` | a `declares_side_effect` mismatch |

Fifty-one new AC records were about to be committed with none of that checked.

**A second, separable defect: the probe's success condition is an OR, and it is wrong.**

```python
if not config_path.exists() and not (leafcutter_path.exists() or leafcutter_path.is_symlink()):
    raise BootstrapError.missing_config(config_path, build_exc)
```

The comment above it states the intent plainly: *"a `.leafcutter` symlink alone is a valid
established state."* **It is not.** `pre-commit` looks for `.pre-commit-config.yaml` at the
repository root and nothing else. Directly observed twice this session: with the
`.leafcutter` symlink present and correct, `git commit` still returned

```
No .pre-commit-config.yaml file was found
- To temporarily silence this, run `PRE_COMMIT_ALLOW_NO_CONFIG=1 git ...`
```

and only began running hooks once the config file itself was copied in. In this workspace
`/home/henzeh/projects/leafcutter/.leafcutter/.pre-commit-config.yaml` does not exist, so the
symlink cannot be supplying it. So the probe passes a worktree in which hooks are entirely
disabled — a fail-open in the guard written specifically to prevent a fail-open. Note that
`CLAUDE.md`'s documented check has the same shape (`ls ... .pre-commit-config.yaml || ls
... .leafcutter`) and will likewise report a healthy worktree that has no hooks.

**Why the silence is the severity.** A skipped hook and a passing hook produce identical
output: nothing. There is no line in the commit output saying "0 hooks ran". The operator
learns about it at merge time, or never. KI-BO-027 records an epic worktree that *did* have
both markers, so this is inconsistent rather than uniformly broken, which is worse — the
condition cannot be inferred from experience.

**Fix direction.**

1. **Detect at commit time, not creation time.** Provisioning at creation only helps
   worktrees created the blessed way. A guard that notices at commit — "this repository has
   `.leafcutter/` but this worktree has no `.pre-commit-config.yaml`" — covers every creation
   path including ones that do not exist yet. This is the highest-value half.
2. **Fix the probe's OR to require `.pre-commit-config.yaml` specifically**, since that is
   the file `pre-commit` actually reads, and correct the comment that asserts otherwise.
   Correct `CLAUDE.md`'s check in the same change.
3. Optionally hook `git worktree add` itself, or make the documentation lead with
   `setup_ticket_worktree.py create-only` rather than presenting the raw git command as
   equivalent.

Do **not** fix this by adding a manual step to a checklist. There already is one — in
`CLAUDE.md`, marked MANDATORY, with both fix recipes — and it was missed three times in one
session by an operator who had read it.

**Pattern:** a correct guard reachable from exactly one entry point, protecting against a
condition whose only symptom is silence.

---
