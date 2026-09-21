---
title: "KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them"
description: "KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them"
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

# KI-BP-009 — `.claude/skills/` is symlinked wholesale to the generated tree, so an adopter's own skills have nowhere to live and `--clean` targets them

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **RE-VERIFIED 2026-08-25 — LIVE, and worse than recorded. Severity should rise.**
> The entry marked the deletion as *code reading, not empirically confirmed*, because
> `--clean` has no dry-run path. It is now confirmed. On a scratch adopter I placed
> `adopter-prod-deploy/SKILL.md` under `.leafcutter/skills/` and ran a `--clean` build:
> `Removing stale artifact: .../.claude/skills/adopter-prod-deploy`, and the directory was
> gone. It deletes through the symlink via the `rmtree` branch, exactly as predicted.
>
> **The new finding is more serious than the `--clean` case.** I then tried the obvious
> adopter workaround — replace the symlink with a *real* `.claude/skills/` directory — and
> ran an **ordinary build with no flags**. Output: `✓ removed stale: .claude/skills`, then
> `shim: .claude/skills -> skills (symlink)`. The adopter's directory was gone. `.claude/skills`
> is in **both** `_PRE_CONSOLIDATION_PATHS` (`build.py:1189`) and `shim_map`
> (`build_helpers.py:331`), so `_cleanup_stale_paths` `rmtree`s any real directory there and
> the shim then replaces it — on every build, reported with a **green checkmark**.
>
> So the adopter has no safe placement at all: inside the symlink, `--clean` reaps it;
> outside it, the default path reaps it. This is no longer "nowhere good to put it" — it is
> "the build deletes your work and calls it success."
>
> Same constant confirms KI-BP-010: `_MANAGED_ARTIFACT_DIRS["workflows"] = ".claude/workflows"`
> is joined as `claude_dir / subdir_name`, yielding `<target>/.claude/.claude/workflows`. The
> `--clean` run touched no workflow.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** the shim-install step (`scripts/build.py` `_install_shims`) ·
  `scripts/build_phases.py:2820-2825` (`_MANAGED_ARTIFACT_DIRS`) and `:2828-2880`
  (`clean_stale_artifacts`) · `scripts/build.py:1202-1236` (`_build_source_manifests`)
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** `build.py` installs `.claude/skills` as a **symlink into the package's own
output tree**:

```text
.claude/agents  -> ../.leafcutter/agents
.claude/hooks   -> ../.leafcutter/hooks
.claude/skills  -> ../.leafcutter/skills
```

Claude Code discovers project skills only at `.claude/skills/`. Because leafcutter owns that
entire directory, an adopter's own skills have **no location that is both discoverable and
outside the generated tree**. The only way to have a working project-local skill is to put
it somewhere the package documents as build output. DIAGraph did exactly that — four
adopter-owned skills (`prod-deploy`, `create-slides`, `diagraph-mcp`, `gen-ui-library`) live
in `.leafcutter/skills/` and exist in no `templates/skills/` anywhere.

**Why that placement is unsafe.** `clean_stale_artifacts` iterates `<target>/.claude/skills/`
— following the symlink into `.leafcutter/skills/` — and removes anything whose base name is
absent from the manifest:

```python
for item in sorted(managed_dir.iterdir()):
    if item.name not in expected_names:
        print(f"Removing stale artifact: {item}")
        if item.is_dir() and not item.is_symlink():
            _shutil.rmtree(item)
```

`_build_source_manifests` populates `skills` from `templates/skills/` subdirectory names
only, so every adopter skill matches the removal condition and is a real directory, not a
symlink — the `rmtree` branch. `--clean` should therefore delete all four.

**Confidence.** Code reading, **not empirically confirmed** — the reporter declined to run
it, and rightly: `clean_stale_artifacts` takes no `dry_run` parameter and `--clean`
(`build.py:1476`, dispatched at `:1684-1685`) has no dry-run path, so the only way to observe
the behaviour is to perform it. Confirm on a scratch copy before treating the mechanism as
settled. **The placement problem stands regardless of how the deletion question resolves.**

Mitigating factor: those files are git-tracked in the adopter repo, so a deletion shows up in
`git status` rather than vanishing. That is the only thing separating this from their
`site/middleware.ts` incident, where an untracked file disappeared silently and left
production ungated for two weeks.

**A second, independent defect in the same function, found while verifying** — a doubled path
segment that has made clean-mode's `workflows` entry unreachable since it was added. Filed
separately as **KI-BP-010**, where it can be picked up on its own.

**Correction, 2026-08-25.** An earlier revision of this paragraph claimed the typo was
"load-bearing" because `_build_source_manifests` returns no `"workflows"` key, so fixing the
path alone would delete every deployed workflow. **That is wrong.** The key exists —
`scripts/build.py:1246-1258` populates it from `templates/workflows-js/*.js`. The manifest
side is correct and the entry is simply never consulted, so repairing the path is safe and is
the fix, not a hazard. The mistake mattered in the one direction that costs something: it
argued for leaving a broken cleanup step alone. Corrected in KI-BP-010, which carries the
verified analysis.

**Confidentiality angle worth flagging.** `prod-deploy/SKILL.md` in the reporting repo holds
Roche sandbox infrastructure detail — subscription name, ACR name, Container App names,
FQDNs. Leafcutter ships an `add-skill-to-package` skill whose stated purpose is promoting
project-local skills *into* the shared package. Run against that skill, it would publish
that detail into a repo owned outside the adopter. Adopter skills need a home that is
structurally outside the promotion path, not merely one nobody has promoted yet.

**~~The concept already exists in the code; the layout contradicts it.~~ CORRECTED
2026-09-08 — the code this paragraph sends you to was deleted before the paragraph was
written.** It read: *"`build_phases.py:1930` computes `project_skills_dir = target_root /
".claude" / "skills"` and `:2020` uses it as `in_project = (project_skills_dir / skill_id)
.exists()` to decide whether a skill is project-local. Under the symlink that predicate can
never distinguish anything."*

The reasoning about the symlink is sound. The premise is not: **that resolution leg no longer
exists.** It was removed on 2026-08-18 under BP-1300a-1 — six days *before* the
`RE-VERIFIED 2026-08-25` block above was written — and the only trace of `in_project` left in
`build_phases.py` is a DECISION HISTORY comment recording the removal, which states the leg
"could report `in_project = True` for a since-removed skill, masking a genuinely missing
one."

Left struck through rather than deleted, because the misdirection is the useful part: an
implementer told "the concept already exists, the layout contradicts it" budgets for a repair
and finds a build. There is **no** project-local predicate to fix. Whatever distinguishes
adopter content from package content has to be built, not restored — which is a materially
larger piece of work than this entry has implied for two weeks.

Found while enriching `BP-1500g`, the AC set that now owns this repair.

**Fix direction.** Symlink **per skill** rather than symlinking the parent. `.claude/skills/`
becomes a real directory holding one symlink per package-provided skill; `clean_stale_artifacts`
then only removes symlinks it created, and adopter directories are structurally untouchable
rather than protected by a list someone has to maintain. It also makes the `in_project`
predicate at `:2020` mean what it says.

Smaller fallback if per-skill symlinking is too large: have `clean_stale_artifacts` read an
allowlist (e.g. `skills_config.json` → `project.owned_skills`) and never remove listed names.
That is strictly weaker — it protects skills someone remembered to declare — but it is a
same-day change.

Either way, give `--clean` a dry-run path. A destructive mode whose only observation method
is to run it destructively cannot be verified by the people most at risk from it.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, in its ownership form: the
deployed tree and the adopter's tree are the same directory, so the package cannot tell its
own output from someone else's source.

---
