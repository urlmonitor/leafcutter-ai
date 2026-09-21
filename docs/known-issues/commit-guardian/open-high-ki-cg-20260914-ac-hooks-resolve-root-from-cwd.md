---
title: "KI-CG-20260914-ac-hooks-resolve-root-from-cwd"
description: "All six AC commit-guardian gates derive both their project root and their staged file set from the current working directory, so from the wrong cwd they validate zero files and exit 0."
type: reference
category: reference
status: active
created: '2026-09-14'
last_updated: '2026-09-14'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-ac-hooks-resolve-root-from-cwd — all six AC gates take their project root AND their file set from the current directory, so from the wrong cwd they validate zero files and exit 0

- **Severity:** high — a false *green*, not a false red. The gate reports success having examined nothing, and the wrong cwd is the normal case rather than an edge case, so the failure is routine rather than exotic.
- **Status:** open. Filed on sight 2026-09-14 while committing `8b2b899ae`; not fixed there, which was a behaviour-preserving refactor of an unrelated script.
- **Occurrences:** 3 in a single session (a `commit` agent's Step 0a pre-flight probe; an `it-po` agent twice, on separate tasks). Each initially read the result as a pass.
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py:673` — `root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))` · `:678-679` the fallback warning · `:307` `_get_staged_ac_paths()`, whose `git diff --cached` inherits the process cwd · `:109` a second independent `[Path.cwd(), *Path.cwd().parents]` walk

**Symptom.** Run from outside the repository worktree, the hook prints one line and exits 0:

```text
WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter; falling back to manual field validation.
```

It has validated **zero** files. Run from the worktree root, the same command against the same index loads the real schema, emits no warning, and validates all 29 staged records — turning up 13 genuine violations.

**Mechanism — two cwd dependencies, not one.** That the *schema path* is cwd-relative is already recorded (see `KI-CG-001`), and on its own it only degrades to weaker manual field validation. The half that makes this a false green is that the *file set* is cwd-relative too: `_get_staged_ac_paths()` shells out to `git diff --cached`, which resolves against the process cwd, so outside a git worktree it returns nothing. Weaker checks over zero files is not a degraded pass — it is a vacuous one.

**Why it fires so reliably.** A session's default cwd in this workspace is `/home/henzeh/projects/leafcutter`, the untracked build-output parent, which is **not a git repository**. So the default invocation is the broken one. Every agent that reaches for these hooks without an explicit `env --chdir` gets the vacuous pass first.

**The AC family is the outlier, and the fix already exists in the package.** `templates/scripts/commit_guardian/_resolve_root.py` provides `find_project_root()`, which prefers `git rev-parse --show-toplevel` and is correct under symlinked and linked-worktree layouts. **31 hooks already import it** — `check_file_size`, `check_secrets`, `check_doc_length`, `check_done_proof`, `check_build_drift` among them. **All six AC gates import none of it**: `check_ac_schema`, `check_ac_governance`, `check_ac_limits`, `check_ac_parent_covered_by`, `check_ac_circular_deps`, `check_ac_pattern_refs`. So the fix is to route the six through the existing resolver, not to invent anything.

**Fix direction.** Replace the `Path.cwd()` default with `find_project_root()` in all six, keeping `HOOK_ROOT` as the explicit override. Do NOT fix this by documenting "always run from the repo root" — that instruction already exists in the AC-hook notes and it has not prevented three recurrences. A second, independent arm is worth considering: make an absent schema **fail-closed** rather than silently degrade, so a missing `config/ac_store_schema.json` refuses instead of falling back. A gate that cannot load its own rules has not passed.

**Interim recipe until fixed.** Invoke every AC hook under `env --chdir=<worktree-root>`, and before believing any green, confirm the hook actually saw files — run its own selection query, `git diff --cached --name-only --diff-filter=AM -- docs/acceptance-criteria/`, and check the count is non-zero. Absence of the warning line is the positive signal that the schema loaded.

**Related.**
- `KI-CG-001` — AC hooks are scoped to the git index, so parent-level drift is unreachable. Same family; that entry covers *which* files the hooks see, this one covers the case where they see **none** and say nothing.
- `KI-CG-012` (`check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set) — the same vacuous pass reached by a different route. Fixing the root resolution here does **not** close that one: an empty staged set from the correct cwd still fails open.
- `KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look` — the same cwd-derived-root family in `verify_precommit_active.py`, with the polarity inverted: that one fails *closed* (false refusal), these fail *open*.
- `KI-ACS-001` — the AC-store validator's bare-directory glob, which exited 0 having checked zero files for eight days. Already fixed there by making a zero-file resolution exit non-zero; that remedy is directly transferable.

**Pattern:** a gate whose scope is derived from ambient process state rather than from its subject, so running it the ordinary way silently empties its input and the emptiness is indistinguishable from a clean result. A check that examined nothing must not look like a check that found nothing.
