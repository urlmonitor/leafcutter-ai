---
title: "KI-BO-20261025-bare-build-drifts-from-the-maker-build — a bare `build.py --target-dir <ws>` in a maker workspace renders changelog outputs in .claude/ and .gemini/ differently from the maker's build, so check-output-drift blocks the next commit; the maker's exact build arguments are documented nowhere"
description: "medium — the workspace maker builds a workspace install with --config-path <ws>/.leafcutter/derived_skills_config.json, a --log-root and LEAFCUTTER_SHIM_STRATEGY=copy. A hand-run build that omits --config-path renders the changelog outputs under .claude/ and .gemini/ from a different config, the manifest records the new hashes, and check-output-drift then refuses commits. docs/how-to/get-a-workspace.md does not give the maker's build arguments, and worktree.py has no verb that rebuilds an existing install the maker's way."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261025-halted-epic-resume-refused-on-new-template-sources.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20261009-epic-worktree-install-goes-stale-per-ticket.md
  - docs/how-to/get-a-workspace.md
---

# KI-BO-20261025-bare-build-drifts-from-the-maker-build — a hand rebuild is not the maker's rebuild

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing wrong lands, because check-output-drift refuses. But a rebuild is the
  documented remedy for a stale install (KI-BP-20261009-epic-worktree-install-goes-stale-per-ticket),
  and the obvious form of that rebuild produces a different install from the one the maker made.
- **Status:** open, no AC.
- **Occurrences:** 1, GE-124 epic drive, 2026-10-25. Hit while working around
  KI-BO-20261025-halted-epic-resume-refused-on-new-template-sources.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where:** cited on `origin/main` `0087a1700`:
  - `templates/scripts/worktree_readiness.py:52-72` (`run_install_build`): the maker runs
    `build.py --target-dir <ws> --config-path <config_path>` with
    `LEAFCUTTER_SHIM_STRATEGY=copy`. Its answer reports the config as
    `bootstrap.config_path`, `<ws>/.leafcutter/derived_skills_config.json`.
  - `docs/how-to/get-a-workspace.md`: does not mention `build.py`, `--config-path`, `--log-root`
    or the shim strategy.
  - `templates/scripts/worktree.py:261-293`: the verbs are `ensure`, `locate`, `list`, `verify`,
    `remove`, `where` and the migrate verb. None rebuilds an existing install without the rest of
    `ensure`.

## Symptom

After `python3 <ws>/scripts/build.py --target-dir <ws>` (no `--config-path`) in a maker workspace,
the next commit failed check-output-drift on the changelog outputs under `.claude/` and `.gemini/`.
They differed from the maker-built versions. Re-running the build with the maker's arguments
cleared it.

## Mechanism

The maker builds from a derived config written into the workspace. A bare build falls back to the
default config lookup, so config-driven outputs render differently. The manifest the bare build
writes then disagrees with what check-output-drift expects from the workspace's own install. The
same split applies to the log root: a build without `--log-root` declares the worktree's own,
disposable root (root CLAUDE.md, "Feedback sink reachable").

Nobody can be expected to reproduce three arguments that are written down only in the maker's
source.

## Workaround used

Rebuild with the maker's exact arguments:

```
LEAFCUTTER_SHIM_STRATEGY=copy python3 <ws>/scripts/build.py --target-dir <ws> \
  --config-path <ws>/.leafcutter/derived_skills_config.json --log-root <recorded root>
```

`<recorded root>` is the `operational_log_root` in `<ws>/.leafcutter/config/knowledge_sink.json`.

## Fix direction

1. **Add a `worktree.py rebuild` verb** (or `ensure --rebuild-only`) that reruns
   `run_install_build` and `restore_build_changes` for an existing workspace and answers in the
   maker's JSON contract. A stale install then has one supported remedy.
2. Failing that, **document the maker's exact build arguments** in `docs/how-to/get-a-workspace.md`,
   and have the maker's answer carry the full command it ran.
3. Optionally, have check-output-drift's refusal say when the manifest was written by a build whose
   config differs from the install's derived config.

**Pattern:** a remedy that exists only as "re-run the build", where "the build" means a specific
command line that lives in one script.
