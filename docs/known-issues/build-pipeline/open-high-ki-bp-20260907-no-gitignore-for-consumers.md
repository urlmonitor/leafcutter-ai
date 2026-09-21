---
title: "KI-BP-20260907-no-gitignore-for-consumers — `build.py` deploys no `.gitignore` to consumers, so a deployed module's compiled bytecode gets tracked and every import re-fails the next commit"
description: "high — blocks ordinary commits once any hook importing a deployed module is registered as required"
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

# KI-BP-20260907-no-gitignore-for-consumers — `build.py` deploys no `.gitignore` to consumers, so a deployed module's compiled bytecode gets tracked and every import re-fails the next commit

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — blocks ordinary commits once any hook importing a deployed module is registered as required
- **Status:** open — no AC. The trigger is suppressed for one caller (see below); the root cause is not.
- **Occurrences:** 2
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `scripts/build.py:405`, `:1147` and `scripts/build_phases.py:2429` (comments *about* the gap, not code that closes it) · `templates/scripts/commit_guardian/check_file_size.py:43` and `check_build_drift.py:84` (`from _resolve_root import find_project_root` — the shared import that triggers the symptom) · `templates/scripts/commit_guardian/run_hook.py:114-125` (docstring stating the mechanism), `:131-132` (`env["PYTHONDONTWRITEBYTECODE"] = "1"`, the suppression) · `docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-2.yaml:41` (the same gap worked around for the test harness's own scratch repo)

**Symptom.** `grep -rn "gitignore" scripts/build.py scripts/build_phases.py scripts/build_helpers.py` returns exactly three hits, and all three are comments *about* gitignored paths — none of them deploy code. `find templates -iname "*gitignore*"` returns zero files: there is no `.gitignore` template anywhere under `templates/` for `build.py` to deploy. A fresh consumer install therefore has no rule excluding `__pycache__/` or `*.pyc`.

**Mechanism.** Without that exclusion, a first `git add -A` in a consumer project tracks the `.pyc` files sitting beside deployed Python modules. Any tool that later imports one of those modules causes CPython to rewrite the tracked `.pyc`. Pre-commit judges a hook FAILED when the working tree differs before and after it runs, so the hook fails on that ground alone regardless of its own verdict — on an ordinary commit to an unrelated, well-under-limit file. `run_hook.py`'s own docstring (`:114-125`) states this precisely: "pre-commit decides a hook FAILED when the working tree differs before and after it runs... In a project whose `.gitignore` does not exclude `__pycache__` — which every fresh consumer install is, since `build.py` deploys no `.gitignore` — those `.pyc` files are tracked, so every hook run rewrites tracked files and pre-commit reports 'files were modified by this hook' no matter what the hook itself decided."

Registering the `check-file-size` hook turned this from latent to blocking: an ordinary commit was refused while the gate itself printed `✅ PASSED`. Reproduced independently via a manual `build.py --target-dir <tmp>` + `git init` + `pre-commit run` round trip, and again on `check-build-drift` — both hooks import the same helper module (`check_file_size.py:43`, `check_build_drift.py:84`).

This repo's own `.gitignore` masks the symptom locally — `__pycache__/` and `*.pyc` are present at lines 41-42 — so the condition is invisible in this repo's own development loop and only shows up downstream, in a consumer install that has no `.gitignore` at all.

**PR #728 (branch `fast-lane/ge-127a-1`, this worktree) suppresses the trigger, not the root cause.** `run_hook.py` now sets `PYTHONDONTWRITEBYTECODE=1` on the environment used to delegate to the actual hook script (`:131-132`), which stops commit-guardian's own delegated hook processes specifically from writing bytecode. It does **not** remove the underlying condition — no `.gitignore` is deployed to consumers — and it does **not** help any other tool that imports a deployed module.

**Scope.** Nobody has counted how many other tools import a deployed module the way commit-guardian's hooks do. That unmeasured blast radius is why this is filed as a known-issue rather than an acceptance criterion right now — an AC should follow once the blast radius is counted, so the fix (most likely: ship a `.gitignore` template and deploy it, per `docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness`'s own deployment-completeness framing) can be scoped against the real set of affected callers rather than guessed.

**The gap was already known in one place and never generalised.** `BP-900h-2.yaml:41` — the test harness's own `it_requirements.constraints` list — already reads: "Exclude `__pycache__` and `*.pyc` from the scratch repository via `.gitignore`; compiled bytecode legitimately differs between runs and would make the check permanently red." That is the same gap, worked around locally for a scratch repo the harness controls, without the underlying fix (a deployed `.gitignore`) ever reaching real consumer installs.

**Related.**
- `KI-BP-20260907-bootstrap-swallows-build-failure` (`docs/known-issues/build-pipeline.md:1990`) — same file, same day, a different way a build can leave a consumer half-provisioned without saying so.
- `KI-BO-20260907-resume-replays-cached-resolver` (`docs/known-issues/build-orchestration.md:2886`) — different file, cross-referenced here only as a same-day neighbour in the sibling register, not because it shares this defect's mechanism.
- `KI-CG-012` (`docs/known-issues/commit-guardian.md:800` — the "check-ac-schema fails open on an empty staged set" entry, one of two entries in that register sharing the `KI-CG-012` number by a documented, deliberately-unrepaired collision). Its own `Occurrences` field already reads 5 as of today, per its own "Fifth occurrence, 2026-09-07" note (`commit-guardian.md:920`) — but that occurrence describes an unrelated mechanism (a wrong-cwd root causing a schema-validation fallback), not the bytecode-tracking issue filed here. This entry is **not** a sixth occurrence of `KI-CG-012` and does not add to that count; it is cross-linked only because both surfaced the same day against the same `run_hook.py` delegation path.

**Fix direction.** Ship a `.gitignore` template under `templates/` covering at minimum `__pycache__/` and `*.pyc`, and add it to a deploy phase in `build.py`/`build_phases.py` so every consumer install gets it — the same "deploy list" discipline this repo's own `CLAUDE.md` already requires for new hook/gate dependencies. Before closing, count how many commit-guardian hooks (and any other deployed tooling) import a deployed module, so the fix is verified against the actual blast radius rather than the two occurrences that happened to be observed first.

**Pattern:** a workaround at the one call site that happened to get instrumented, standing in for a fix at the one deploy step that would have prevented it everywhere.

---
