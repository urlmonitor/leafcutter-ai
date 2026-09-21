---
title: "KI-BP-20260907-bootstrap-swallows-build-failure — `_bootstrap()` catches `build.py`'s own `CalledProcessError` and prints a WARNING instead of failing, so a now-loud build failure still ships a half-deployed worktree"
description: "KI-BP-20260907-bootstrap-swallows-build-failure — `_bootstrap()` catches `build.py`'s own `CalledProcessError` and prints a WARNING instead of failing, so a now-loud build failure still ships a half-deployed worktree"
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

# KI-BP-20260907-bootstrap-swallows-build-failure — `_bootstrap()` catches `build.py`'s own `CalledProcessError` and prints a WARNING instead of failing, so a now-loud build failure still ships a half-deployed worktree

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `templates/scripts/setup_ticket_worktree.py`, `_bootstrap()` — the `build_candidates`
  probe (`:845-849`), the `subprocess.run([sys.executable, str(build_script), "--target-dir",
  str(worktree_path)], cwd=str(worktree_path), check=True)` call (`:852-857`), and the
  `except subprocess.CalledProcessError as exc:` branch that prints `"WARNING: build.py run
  failed in new worktree ({exc}); named-workflow resolution may fail until build.py is run
  manually."` to stderr and falls through (`:858-864`). The AC-5 fail-fast probe a few lines
  later (`:876-884`, `if not config_path.exists() and not (leafcutter_path.exists() or
  leafcutter_path.is_symlink()): raise BootstrapError.missing_config(...)`) does **not** cover
  this case: it only raises when NEITHER `.pre-commit-config.yaml` NOR `.leafcutter` exists at
  the worktree root at all. A `build.py` run that fails partway through — after creating
  `.leafcutter/` and writing some of its subdirectories but not others — leaves `.leafcutter`
  present, so the AC-5 probe's `leafcutter_path.exists()` check is satisfied and it does not
  fire, even though the tree under it is incomplete.

**Symptom.** `/fast-lane-build GE-127b-1` created its worktree off `origin/main` correctly, but
the worktree's `.leafcutter/scripts/` ended up containing only `ac_store` and
`commit_guardian` — `build_orchestration/` was entirely absent. The fast-lane workflow then
died four steps later at its resolve phase with:

```text
python3: can't open file '.../.leafcutter/scripts/build_orchestration/fast_lane.py':
[Errno 2] No such file or directory
```

The `build.py` run inside `_bootstrap()` had in fact raised `subprocess.CalledProcessError`;
`_bootstrap()` caught it at `:858`, printed the WARNING quoted above to stderr, and continued
past both the AC-5 probe (satisfied by the partially-populated `.leafcutter/`) and the rest of
worktree setup — so the operator was shown a confusing "file not found" from an unrelated later
phase instead of "build.py failed." Running `python scripts/build.py --target-dir <worktree>`
by hand wrote 229 files and fixed it.

**Root cause.** This is a defect in the *caller*, not in `build.py`'s own exit-status logic.
KI-BP-018 already documents that, as of BP-900g-9 (2026-09-01), `build.py` itself now fails
loudly on an incomplete deploy — `raise_if_deploy_failures()` raises and `main()` returns
non-zero. `_bootstrap()`'s `subprocess.run(..., check=True)` does convert that non-zero exit
into a Python exception (`check=True` guarantees `CalledProcessError` on any non-zero return),
so the failure signal reaches `_bootstrap()` correctly. The defect is what `_bootstrap()` does
with it: `except subprocess.CalledProcessError as exc:` records the exception into `build_exc`
purely for use in a *later* `BootstrapError` message (`:884`, `BootstrapError.missing_config(
config_path, build_exc)`) that only fires under the narrower AC-5 condition described above —
otherwise the exception is fully absorbed and the function returns normally.

**Why high.** The tool the fast-lane workflow depends on (`.leafcutter/scripts/
build_orchestration/fast_lane.py`) is not in the layer its own setup step deploys, and the
failure is converted into a later, misattributed error at a different phase entirely — the
operator sees a resolve-phase `FileNotFoundError` with no link back to the build failure that
caused it. This is, ironically, the same swallowed-error shape the commit-guardian/gate
philosophy this repo enforces elsewhere exists to prevent: a caller treating "the thing I
depend on failed" as a warning rather than a blocker.

**Fix direction.** Either propagate `build_exc` as a hard `BootstrapError` unconditionally
(not only when the AC-5 marker-existence check also fails), or replace the AC-5 probe's
existence check with a completeness check — verify the `.leafcutter/scripts/` subtree the
workflow layer actually needs is present, not merely that `.leafcutter` exists as a directory.
The narrower AC-5 condition was written to catch "no config sources at all"; it was never
scoped to catch "some config sources, deployed incompletely," which is exactly this defect's
shape.

**Related.** KI-BP-017 and KI-BP-018 document two adjacent halves of the same worktree-bootstrap
surface: KI-BP-017 is `scripts/feedback/` never being provisioned into a worktree at all;
KI-BP-018 is `build.py` itself (pre BP-900g-9) never failing on an incomplete deploy. This
entry is the third, still-open mechanism — even now that `build.py` can fail loudly
(BP-900g-9), its caller here swallows that failure and continues, so KI-BP-018's fix does not
by itself help an operator driving through `setup_ticket_worktree.py`.

**Pattern:** a caller that wraps a dependency's now-correct hard failure in a warning, so the
failure still ships — just relabeled and deferred to a later, unrelated phase.

---
