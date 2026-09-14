---
title: "A gate stops demanding that files no build can produce match a hash it never recorded"
date: "2026-09-14"
time: "21:40"
type: manual
components:
  - build_pipeline
  - commit_guardian
summary: "check-output-drift exits non-zero on any unregistered deployed file, and four of them were permanently unregisterable — a machine-local settings file, a scheduler lock, the build's own input config, and a scaffold the project appends to. No build could ever reproduce their content, so the gate's own advice to run build.py could not be followed and every commit in a built workspace was refused regardless of its contents. They are now declared exemptions with individually-reasoned grounds. Two further gaps were NOT exempted: both were orphans whose templates no longer exist, so exempting them would have recorded something false about the build, and they are deleted from the deploy tree instead."
description: "Adds four entries to the drift_gate_exemption_registry in templates/scripts/commit_guardian/commit_guardian.json for .claude/settings.local.json (per-developer machine settings, .gitignore:33), .claude/scheduled_tasks.lock (scheduler runtime state carrying a session id and timestamp that change on every acquisition), .claude/skills_config.json (the build's own INPUT, read by config_loader.py to drive every phase, never a file a phase writes deterministic content to), and .claude/changelog_categories.md (write-if-absent scaffold, .gitignore:35). Each carries its own specific ground rather than one boilerplate ground reused four times, matching BP-100k-3's per-artifact requirement. Two other gaps were classified as orphans and deleted rather than declared: .gemini/skills/frontend-design/SKILL.md, whose template carries deprecated: true so build_phases._skill_is_deprecated() makes build_skills() and the manifest computation skip it identically; and scripts/commit_guardian/known_failing_tests.py, whose template build_propagation_audit.py's DECISION HISTORY records as 'deleted outright as dead code' on 2026-08-18. New AC BP-100k-3-iii, a child of BP-100k-3, with 6 behavioural tests across test_bp_100k_3_iii.py and _bp_100k_3_iii_harness.py."
commits:
  - d3a828b2a
breaking: false
---

## Entry

### The gap: a gate that could not be satisfied

`check_output_drift.py` compares the deployed install tree against the build manifest
and exits 0 only when `gaps`, `drifted`, `missing` and `unreadable` are all zero. A
`gap` is a deployed file the manifest does not know about, and the gate's remediation
text for one says `action=run build.py to register it`.

For four files that instruction could never work. They are not build outputs at all:

- `.claude/settings.local.json` — per-developer settings the adopter edits on their own
  machine, gitignored.
- `.claude/scheduled_tasks.lock` — scheduler runtime state, holding a session id and a
  timestamp that change on every acquisition.
- `.claude/skills_config.json` — the build's own **input**, the file `config_loader.py`
  reads to drive every phase, never one a phase writes deterministic content to.
- `.claude/changelog_categories.md` — a write-if-absent scaffold the project appends its
  own content to after seeding, gitignored.

No build run can reproduce their content, so no build can pin a hash for them, so the
gap never clears. The result was a gate that refused **every** commit in a built
workspace regardless of what the commit contained.

This was found once before and fixed for exactly one file. The registry's existing entry
for `.claude/precommit-autofix.json` says so in its own ground text: *"it was simply
never declared, so every commit in a built worktree failed this gate on a file no commit
can contain (it is gitignored)."* Same bug, four more files.

### Two that were not exempted, and why that distinction matters

Two further gaps looked superficially identical and are deliberately handled the
opposite way. Both were **orphans** — files the deploy tree still held whose producing
template no longer exists:

- `.gemini/skills/frontend-design/SKILL.md` — its template carries `deprecated: true`,
  and `build_phases._skill_is_deprecated()` makes `build_skills()` and the manifest
  computation skip it identically. The on-disk copy was dated 2026-06-02, predating the
  deprecation.
- `scripts/commit_guardian/known_failing_tests.py` — no template produces it;
  `build_propagation_audit.py`'s own DECISION HISTORY records the template "deleted
  outright as dead code" on 2026-08-18 once `TQ-100d-1` specified its replacement.

Exempting these would have been the easy way to reach `gaps=0`, and it would have
recorded something false: an exemption asserts *the build deliberately leaves this file
alone*, which is precisely not true of an artifact the build has simply forgotten. The
registry's own governing comment already warns that an orphan is the "candidate for
manual deletion" class. They are deleted from the deploy tree instead, so a later run
finds nothing there to report.

That both readings were available, and produce the same green number by different
routes, is the interesting part. `gaps=0` is not self-validating.

### Verification

All under `AC_ENFORCE_STRICT=1`, without which a failing test on a not-yet-done AC is
downgraded to `xfail` and shows a false green.

- The 6 tests went **red at 4 failed** before the registry entries and **green at 6
  passed** after. Four execute the real deployed gate as a subprocess against the real
  `commit_guardian.json` — no `HOOK_TEST_CONFIG` override — so the evidence is the
  registration surface a real commit is judged against. Two load the real
  `_drift_exemptions` and `build_phases` modules. None greps the JSON for a well-worded
  entry, which would pass on a registry nothing reads.
- **Mutation-proved three times**, including once after the test file was split, to
  confirm the restructure had not quietly decoupled the tests from the registry:
  reverting `commit_guardian.json` to `HEAD` turns 3 of the 6 red — including the
  end-to-end `gaps=0` assertion — and restoring returns all 6 green with a byte-identical
  `diff -q`.
- **No regressions**, measured against a pristine `origin/main` baseline in the same
  environment rather than asserted: baseline **110 failed / 1328 passed**, branch
  **107 failed / 1337 passed**, and the set of failures present on the branch but absent
  on baseline is **empty**. The shared failures are environmental — a worktree without
  `.pre-commit-config.yaml` — plus tests deliberately red on main.
- `test_ge_122e_3`'s "no exemption configuration exists on any surface" was checked
  specifically, since this change adds exemptions. It passes 6/6 with the four entries
  present. Its earlier failure was the missing `.pre-commit-config.yaml`, reached *after*
  it had already passed the exemption surfaces.
- Gate after the fix, against a worktree-local tree built by a real `build.py`:
  `verified=483 uncomparable=5 exempt=5 gaps=0 drifted=0 missing=0 unreadable=0`, exit 0.
  Sibling `check-build-drift` re-verified clean.

### A note on how the green was reached

An earlier iteration reached `gaps=0` by hand-patching the deployed
`commit_guardian.json` and editing `.build_manifest.json`'s recorded hash to match. That
number was real but manufactured — the manifest attested to a state no build had
produced — and it evaporated within the hour when another session ran `build.py`. The
reading above comes instead from a genuine `build.py --target-dir` against the worktree,
which also resolved a `check-hook-parity` failure caused by the shared install tree
carrying an unrelated session's uncommitted hook edits. The branch-side evidence is the
mutation-proved tests; the live gate reading is corroboration, not the proof.
