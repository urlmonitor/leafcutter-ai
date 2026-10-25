---
title: "KI-CG-20261023-output-drift-gaps-on-gemini-workflow-scripts — check-output-drift blocks every commit in a maker workspace with 9 GAPs for .gemini/workflows/*.js that no rebuild clears"
description: "high. A plain build over a copy-strategy maker workspace merges into the real .claude/workflows directory, keeps the nine JS workflow scripts as adopter collisions, and carries them into gemini/workflows, a different family. The next copy build lands them in .gemini/workflows. The manifest never records them, so check-output-drift reports them as gaps."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-25'
components:
  - commit_guardian
  - build_pipeline
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2-ii.yaml
---

# KI-CG-20261023-output-drift-gaps-on-gemini-workflow-scripts — check-output-drift blocks every commit in a maker workspace with 9 GAPs for .gemini/workflows/*.js that no rebuild clears

> One known issue, filed directly into `commit-guardian/resolved/` on 2026-10-25, together
> with its fix. Index: [commit-guardian.md](../../commit-guardian.md). Filename severity
> is the three-level index bucket (`high`).

- **Severity:** high
- **Status:** RESOLVED 2026-10-25. Fixed by `BP-1500g-2-ii`. `_sibling_capability_dir` in
  `scripts/build_capability_merge.py` now carries a contested item to the antigravity
  surface only when the package's own output there already holds an item of that name.
  Tests: `unit_tests/portability/test_bp_1500g_2_ii.py`.
- **Occurrences:** 2 (2026-10-23, workspace `feature/ge-127d-6-statements-per-line`,
  base `ae3a1591c`; 2026-10-25, GE-124 epic workspace, pre-fix copies returning, see the
  note at the end)
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-25 (reproduced on `411b87761`)
- **Where:** the symptom shows in hook id `check-output-drift`
  (`templates/scripts/commit_guardian/check_output_drift.py`). The cause is in the build:
  `scripts/build_capability_merge.py`, `_sibling_capability_dir` and
  `_propagate_winner_to_siblings`.

**Symptom.**

Every commit in the workspace failed with exit 2:

```
UNCOMPARABLE: GAP .gemini/workflows/build-epic.js action=this file is not something the build produces, ...
... (one line each for build-feature, build-ticket, commit, create-ticket, fast-lane-ship,
     finalize-feature, plan-feature, quick-fix)
check-output-drift: RESULT verified=552 uncomparable=14 exempt=5 gaps=9 drifted=0 missing=0 unreadable=0
```

Rebuilding the maker's way left drifted=0 and the same 9 GAPs.

**Cause.**

Three builds produce it:

1. The workspace maker builds with `LEAFCUTTER_SHIM_STRATEGY=copy`, so `.claude/workflows`
   is a real directory that holds copies of `.leafcutter/workflows/*.js`.
2. A plain `build.py --target-dir <ws>` runs (strategy `auto`). `install_shims` finds
   `.claude/workflows` real and non-empty, so it merges into it item by item
   (`merge_capability_items`). Ownership is decided from content, so each of the nine
   copies counts as adopter-owned. The run prints `collision: <name>.js -- resolves to
   adopter`, then `_propagate_winner_to_siblings` copies each one to
   `<output_root>/gemini/workflows/<name>.js`. The sibling rule was
   `<output_root>/gemini/<output_rel>` whenever that directory exists. That is right for
   agents, skills and hooks. For `workflows` it is wrong: `gemini/workflows` is
   antigravity's copy of the commands-family workflow markdown, and the JS workflow
   scripts have no antigravity mirror. `shutil.copy2` keeps the source mtime, so the files
   looked as if the first build had written them.
3. The next copy build copies `.leafcutter/gemini` into `.gemini`, so the scripts reach
   `.gemini/workflows/`. The build manifest never records them there, so
   check-output-drift reports each one as a GAP.

The files are written by the build, so an exemption entry would be the wrong fix. It would
also hide every genuinely foreign file in `.gemini/workflows/` from then on.

**Fix.** `_sibling_capability_dir(output_root, output_rel, name)` returns the sibling
directory only when `<output_root>/gemini/<output_rel>/<name>` already exists. In other
words, the carry happens only where the package put its own version of that item on the
antigravity surface. Contested skills, agents and hooks are still carried (BP-1500g-2-i's
"resolves to adopter" stays true on every surface that really mirrors them). A contested
workflow script is no longer copied into a family it does not belong to.

**Tests** (`unit_tests/portability/test_bp_1500g_2_ii.py`, `# covers: BP-1500g-2-ii`):

- A contested `.claude/workflows/<minted>.js` is not carried into `gemini/workflows`
  (red before the fix).
- A contested skill is still carried to `gemini/skills` (the over-correction control).
- End to end in a scratch git project: copy build, then plain build, then copy build,
  then the deployed hook. No GAP under `.gemini/workflows/`, and a hand-planted
  `.gemini/workflows/<minted>.js` is still reported as a GAP (red before the fix).

**Cleanup for an install built before the fix.** The fix stops new copies. It does not
delete the ones already written, because the build cannot tell them from adopter files.
Delete `.leafcutter/gemini/workflows/*.js` and `.gemini/workflows/*.js` by hand, then
rebuild.

**Related, not fixed here.** After a copy-to-auto strategy switch, every copied item in
`.claude/{agents,skills,commands,hooks,workflows}` and the `scripts/` bridges is reported
as an adopter collision ("merged 0 package item(s)"). A plain build therefore does not
update those copied containers; only the next copy build does. This is the content-only ownership rule
(BP-1500g-1) seeing build output it did not record. It is a separate issue.

**Pattern:** a "mirror" rule keyed on a directory name holds only while every family with
that name is the same family. `workflows` means two different things on the two
platforms.

## Observed again, 2026-10-25: the pre-fix copies come back on every rebuild

**Where:** the GE-124 epic workspace (`epic/every-screen-says-which-requirement-it-is`),
during the epic drive.

**What happened.** check-output-drift reported `gaps=9` for the same nine files
(`build-epic`, `build-feature`, `build-ticket`, `commit`, `create-ticket`, `fast-lane-ship`,
`finalize-feature`, `plan-feature`, `quick-fix`) under `.gemini/workflows/`. The fix above
stops the build writing new copies into `.leafcutter/gemini/workflows/`, but the copies an
earlier build wrote there were still present. The gemini shim copies `.leafcutter/gemini` into
`.gemini` on every copy-strategy rebuild, so deleting only `.gemini/workflows/*.js` does not
last: the next rebuild puts them back.

**Workaround used.** The nine `.js` files in `.leafcutter/gemini/workflows/` were moved to a
backup folder, then the install was rebuilt.

**Residual, not tracked elsewhere.** The cleanup paragraph above leaves this to a human
because the build cannot tell these files from adopter files. That is true of `.gemini/`, but
`.leafcutter/gemini/` is the package's own output root. Suggested fix: the build prunes items
under its own shim-source roots (`.leafcutter/gemini/...`) that it no longer produces and that
the previous manifest recorded as its own, or at least warns about them by name.

---
