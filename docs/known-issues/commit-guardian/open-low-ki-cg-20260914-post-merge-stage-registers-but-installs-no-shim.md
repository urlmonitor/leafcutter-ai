---
title: "KI-CG-20260914-post-merge-stage-registers-but-installs-no-shim — a hook on the post-merge stage is registered, renders into the config, and still never fires in any checkout that did not create a ticket worktree"
description: "medium — it silently reproduces the exact defect the registration was meant to end"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-post-merge-stage-registers-but-installs-no-shim — a hook on the post-merge stage is registered, renders into the config, and still never fires in any checkout that did not create a ticket worktree

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — it silently reproduces the exact defect the registration was meant to end
- **Status:** open. The **registration** is on `main` (`5d0792d13`, PR #808) and the hook does fire
  *in this repository*, because a `post-merge` shim happens to be installed here already. The gap
  is in what the package guarantees a **consumer**.
- **Occurrences:** 1
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/commit_guardian.json` — the
  `check-ac-done-on-merge` entry, the first and only `post-merge` member of
  `hooks_manifest.hooks`; `scripts/build_precommit.py`;
  `templates/scripts/commit_guardian/install_pre_commit_shims.py` (`collect_stages`);
  `templates/scripts/setup_ticket_worktree.py`

**Symptom.** `build_precommit.py` renders whatever `stages` the manifest declares, so
`stages: [post-merge]` appears correctly in the generated `.pre-commit-config.yaml`. But a stage
in that file does nothing on its own — git only runs a hook if the corresponding file exists in
`.git/hooks/`. Writing that file is `install_pre_commit_shims.collect_stages`'s job, and a
repo-wide grep finds exactly one caller:

```
git grep -l install_pre_commit_shims
    -> templates/scripts/setup_ticket_worktree.py
    -> scripts/setup_ticket_worktree.py
    -> the module itself
```

So the shim is installed as a side effect of creating a ticket worktree. A consumer who installs
the package and commits normally never runs it. `.pre-commit-config.yaml` says the gate is on the
post-merge stage, `hooks_manifest.hooks` names it, and nothing invokes it.

**Why this is the same defect one layer out.** `KI-CG-021` and `KI-TQ-007` are about a script that
no registry names. This is a script that a registry *does* name, in a config that renders
correctly, where the **runner for that stage was never installed**. Every artifact a reader would
check says the gate is live. Registering `check-ac-done-on-merge` to close the registration gap
therefore reintroduces the gap at the stage-installation layer unless the shim is handled too.

**Verified, both directions.** This repository has `.git/hooks/post-merge`, and it is a genuine
pre-commit shim (`ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=post-merge)`), so
the gate does fire here — which is exactly why the gap is easy to miss from inside this repo. Its
presence is not attributable to the package's install path; it predates the registration.

**Fix direction.** Make shim installation a consequence of `build.py`, not of worktree creation:
`install_shims()` is already idempotent and already derives its stage set from the generated
config, so calling it from the build is a small change with the right blast radius. Then add a
consumer-simulation assertion that after a fresh install, every stage named in
`hooks_manifest.hooks` has a corresponding file in `.git/hooks/` — the same disk-versus-declaration
comparison `KI-CG-20260831-hook-scripts-never-invoked` asks for one layer down.

**Pattern:** a declaration that renders correctly into a config file nothing has been told to act on.

---
