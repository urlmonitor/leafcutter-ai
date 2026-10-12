---
title: "KI-BP-018 — No build phase can fail the build, the deploy set is hand-listed in ~26 places, and nothing verifies the deployed tree is complete"
description: "medium — **DOWNGRADED from blocker 2026-09-01**; see \"What has changed\" below."
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

# KI-BP-018 — No build phase can fail the build, the deploy set is hand-listed in ~26 places, and nothing verifies the deployed tree is complete

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — **DOWNGRADED from blocker 2026-09-01**; see "What has changed" below.
  Two of this entry's three findings are fixed and shipped. The third, the hand-listed deploy
  set, is real but no longer blocking: an incomplete deploy now fails the build loudly instead
  of shipping silently, so the remaining defect costs maintenance rather than correctness.
- **Status:** open in part — BP-900g-8 (derive the closure) and BP-900g-9 (fail closed) are
  both **built and merged**. Finding 2 remains, with no AC.

**WHAT HAS CHANGED, 2026-09-01.** This entry was written as three findings. Verified against
`origin/main` today:

1. **"No build phase can fail the build" — FIXED.** BP-900g-9 shipped
   `DeployDeclarationError` with a module-level accumulator; nine declared-deploy sites now
   record every unresolvable entry and `raise_if_deploy_failures()` raises once, which `main()`
   catches and returns 1 on. Verified: nine `record_deploy_failure(` call sites in
   `build_phases.py`, and both `raise_if_deploy_failures()` and
   `_check_intra_package_closure_guard` wired into `build.py`.
2. **"The deploy set is hand-listed in ~26 places" — STILL OPEN, and this is what the entry now
   tracks.** BP-900g-8 derived the *closure* (what a deployed script imports) and the
   *manifest* side; it did not derive the *deploy declaration*. `AC_STORE_DEPLOY_MAP`,
   `AGENT_SUPPORT_SCRIPT_DIRS`/`_FILES`, the per-phase `deploy_scripts` lists and their mirrors
   in `build.py` are all still hand-maintained.
3. **"Nothing verifies the deployed tree is complete" — SUBSTANTIALLY FIXED.** BP-900g-8's
   intra-package closure guard runs as a preflight and can fail the build.

**Why medium and not closed.** The remaining hand-lists are exactly what produced this entry's
recurrence history — four rounds of "add the missing module" before anyone treated the list
itself as the defect. That risk has not gone away. What has gone away is the silence: a
declaration that names a source which is not there now stops the build and names the phase,
the entry and the path. A stale hand-list is discovered at build time rather than discovered
by an adopter whose install was quietly incomplete. That is the difference between a blocker
and maintenance debt.

**The honest residual.** Nine sites fail closed on a *declared* entry whose source is missing.
Nothing yet catches the opposite: a file that *should* be declared and is not. That is the
half the hand-lists still own, and the reason this entry stays open rather than being deleted.
See also `KI-BP-20260831-1014` for seven further declared sources that skip silently with no
log at all.
- **Occurrences:** 1 (structural; it is the mechanism behind KI-BP-003, 005, 006, 008, 009, 012, 016 and 017)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` `_run_phases` (~:1097-1184), `main` return at ~:1714, `_manifest_ac_store_scripts` (~:331-349); `scripts/build_referential_integrity.py:270`

**Why this entry exists.** The register holds fifteen distinct build defects and the great
majority are instances of one thing. Filing them individually has produced four rounds of the
same fix. This entry records the mechanism so the next one is not filed as a sixteenth
symptom.

**Three findings, each reproduced against a real build into a scratch adopter repo
(`git init`, target under `/tmp`, never under the package's own parent — a target under
`package_root.parent` relativizes cleanly and is not representative).**

**1. No build phase can fail the build.** `_run_phases` sums *file-write counts*. A phase that
deployed 0 of its 18 scripts and a phase with nothing to do return the same integer. `main()`
prints the sum and returns 0. The `_install_shims` result list and the `_install_hooks` return
string are both discarded — so `pre-commit install` can fail, print a red `ERROR: pre-commit
install failed`, and the build still reports success **with no git hooks installed**.

Exactly six things can exit non-zero: config-schema validation (skipped when `jsonschema` is
absent and under `--dry-run`), agent-registry validation (skipped under `--dry-run`), the
broken-script-reference guard, the untracked-source guard (no-ops without git), self-description
enforcement (**defaults to `warning`, i.e. off**), and the deploy-path collision guard. Plus
uncaught exceptions — a `shutil.copy2` failure aborts, but a *missing source* does not.

Fifteen fail-open sites were catalogued; none changes exit status. The highest-consequence:

| Site | Effect | Signal |
|---|---|---|
| `build_helpers.py:651-661` | `pre-commit install` failed, no hooks installed | red text, discarded |
| `template_compiler.py:33-37` | see KI-BP-019 — every agent loses its frontmatter | **none, any stream** |
| `build.py:1590-1599` | corrupt `agent_registry.json` downgrades `error` → `warning`, disarming the gate that exists to catch it | bare `except … pass` |
| `build_halt_guard.py:61-69, 89-101` | corrupt lock or no git permanently disarms the breaking-change gate | unlogged |
| `build_referential_integrity.py:198-202, 241-245` | an unreadable template's broken references pass a **hard** gate | DEBUG |
| `build_ac_store_scaffold.py:75-90` | template read failure prints `"already present, skipping"` | success-shaped |
| `build_phases.py:89-105`, `injection_builders.py:275-282, 349-356` | unreadable `components.json` / `doc_types.json` / `paths.json` rendered as apology strings **injected into shipped agent prompts** | the prompt itself |

**2. The deploy set is hand-listed in ~26 independent places and derived in none.** Sixteen
deploy sources, plus six *mirrors* of those lists living in other files — `build.py:416` and
`:657` are the second and third copies of the seven-entry workflow-tools list; `build.py:576`,
`:582`, `:702` and `build_phases.py:916-917` are **four** copies of the
`goal_to_epic.py`/`build_ac_mode_detection.py` pair. Plus two shim maps, two clean-target lists
and three phase registries. Roughly fourteen `glob`/`rglob`/`iterdir` scans do exist — but they
feed the *manifest and guard* side, never the deploy side.

That asymmetry is the whole defect. `_manifest_ac_store_scripts` (`build.py:331-349`) derives the
AC-store set by `iterdir()` over source, and its docstring claims it "match[es] what
`build_ac_store` deploys." It does not. That derived set feeds the broken-reference guard — one
of the six gates that *can* fail the build — so the guard believes `_ac_components.py` is
deployable because it exists in source. **The only hard gate that could catch a deploy omission
is fed by a set that contradicts the hand-list it is supposed to police.** Adding entries to
`deploy_map` cannot close this; it is why KI-BP-006 recurred.

**3. Nothing verifies the deployed tree is complete.** `main()` runs two post-build passes and
both only print: `scan_for_placeholders` greps three hardcoded files for TODO markers, and
`check_referential_integrity` validates the ten path-valued keys of `skills_config.json` — its
own docstring calls it "a post-build warning phase (non-blocking)". `return 0` follows
immediately.

The function that would do the job — `build_referential_integrity.extract_compiled_script_path_refs()`,
which scans the **compiled output tree** — exists, is unit-tested, and has **no production call
site**. Verified: the only references are its own module, a docstring cross-link in
`build_propagation_audit.py`, and `unit_tests/test_bp_900b_1.py`. Its docstring says the wiring
was "intentionally out of this ticket's `files_touched` scope."

The nearest live check is the *pre-build* reference guard, blind here by construction: it scans
source templates rather than the deployed tree, matches only `python scripts/<path>` and
`sys.path.insert(...)` forms so a plain `import` of an undeployed sibling is invisible, and
cannot model a caller's CWD — which is why `scripts/feedback/submit_feedback.py` passes while
failing in every worktree (KI-BP-017).

**Evidence.** One adopter build finished with `_ac_components.py` missing, `doc_types.json`
missing, an orphaned `check_eval_staleness.py` whose template had been deleted, and a **1-line**
`fast-lane-ship.js` (source: 1047 lines). Exit 0. Stale cleanup printed `(no stale files found)`.
A grep of the build log for `PLACEHOLDER`, `INTEGRITY` and `SCRIPT-REF` returned nothing.

**Fix direction.** Build BP-900g-8 and BP-900g-9 — both already `readiness: approved`,
`priority: high`, `work_status: todo`. Derive the closure (including the config and data files a
script reads, not only the modules it imports, per BP-900g-8-ii) and make an incomplete deploy
exit non-zero. Wiring `extract_compiled_script_path_refs()` is a large part of the work already
written. Do **not** fix this by adding to `deploy_map`.

**Pattern:** a build whose report is a count of what it wrote, in a system where the failure
mode is not writing something.

**Related.** KI-BP-20260826-1331 is a different defect with the same consequence: many
worktrees write a shared `.leafcutter/` output root last-writer-wins, so a deployed file may
carry any worktree's revision. This entry explains why an *absent* artifact is never noticed;
that one explains why a *present* artifact cannot be attributed to a commit. Together they mean
the deployed tree does not correspond to any revision. The fixes are complementary, not
overlapping — BP-900g-8/9 derive the deploy closure and fail closed; a source-revision stamp on
each deployed artifact makes provenance checkable.

**Re-verified 2026-09-23: STILL TRUE (as the entry itself already states) — Finding 2 remains
open, kept open at its already-downgraded medium severity.** This entry pre-emptively
downgraded itself to medium on 2026-09-01 because Findings 1 and 3 were fixed and merged;
Finding 2 ("the deploy set is hand-listed in ~26 places and derived in none") is the part this
re-verification checked, and it is unchanged:

```
$ grep -n "extract_compiled_script_path_refs" scripts/*.py
build_propagation_audit.py:21   (docstring cross-reference only)
build_referential_integrity.py:34,333,671   (definition + docstring, no caller)
# no call site in build.py or anywhere else — still zero production callers

$ grep -n "AGENT_SUPPORT_SCRIPT_DIRS\|AGENT_SUPPORT_SCRIPT_FILES" scripts/build.py
58,59: import                       762: for dir_name in AGENT_SUPPORT_SCRIPT_DIRS:
770: for file_name in AGENT_SUPPORT_SCRIPT_FILES:
# still hand-maintained tuples, still consumed by iteration rather than derived from a scan
```

`AC_STORE_DEPLOY_MAP` itself is also still a hand-written tuple (`build_phases_ac_store.py:64`)
— separately, per KI-ACS-007's re-verification today, three new entries were added to it
(`_component_migration_map.py`, `_ac_components.py`, `validate_ac_schema.py`), which is exactly
the kind of hand-maintenance-by-addition this entry's Finding 2 describes as the ongoing cost,
not a derivation. `extract_compiled_script_path_refs()` — the function that would verify the
*deployed* tree — still has no production call site. Nothing in the repo suggests Finding 2 has
progressed since this entry's own 2026-09-01 assessment; kept open, medium, as already recorded.

---
