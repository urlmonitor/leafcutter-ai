---
title: "Known issues — build-orchestration"
description: "Open, observed defects in the build-orchestration component: the fast-lane build loop, its gates, and the AC lifecycle transitions it performs. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - build_orchestration
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
---

# Known issues — build-orchestration

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-BO-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-BO-001 — Fast lane never writes a changelog entry, so every fast-lane PR is unmergeable

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/fast-lane-ship.js` (commit/PR phases)

**Symptom.** `fast-lane-ship` commits and opens a PR but never produces a
`changelogs/` entry. `Changelog entry present` is a **required** status check, so the
PR it just opened cannot merge. The workflow reports `status: ok` and `"PR opened"`
for a PR that is structurally blocked.

**Evidence.** PR #465, the first AC built end-to-end by the lane: 5 of 6 required
checks green, `Changelog entry present` failed, `mergeable_state: blocked`. Fixed by
hand in `b3124ff25` to let it merge. Zero occurrences of `changelog` in
`fast-lane-ship.js`.

**Fix direction.** Add a changelog phase between the coder and commit phases, or have
the commit phase emit the entry. Whichever, the lane's `status: ok` must not be
reachable while a required check is known-failing.

---

### KI-BO-002 — `mark_done` flips `work_status: done` but leaves `implemented_by: []`

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-17 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_orchestration/fast_lane.py` — `_update_ac_work_status`, used by `mark_done_built_acs`

**Symptom.** The AC is marked done with no link to the code implementing it. The
helper is deliberately status-only ("Status-only change" per its docstring), so
provenance is never written by any automated path.

**Evidence.** TKT-600a-1 after its fast-lane build: `work_status: done`,
`implemented_by: []`. Populated by hand in `b3124ff25`. Same gap hit on 2026-08-17
marking the BO-2400a-3 family done via `scripts/ac_store/mark_ac_done.py`, which also
only sets `work_status` — so this is not unique to the fast lane.

**Fix direction.** Write `implemented_by` from the coder phase's `files_modified` at
mark-done time. An AC claiming done with no provenance is a phantom-done vector: it
asserts completion that nothing can be traced back to.

---

### KI-BO-003 — AC YAML is reformatted on every claim/mark-done, producing huge diffs

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/build_orchestration/fast_lane.py:108` — `_update_ac_work_status`

**Symptom.** The helper round-trips the whole file through `yaml.safe_load` →
`yaml.safe_dump`. A one-field change alphabetises every key and reflows hand-authored
block scalars into folded strings.

**Evidence.** TKT-600a-1.yaml changed **161 lines** in `19eca859a` for what is
semantically `work_status: todo → done`. The docstring's claim that "every other field
is preserved unchanged" is true of values and false of formatting.

**Fix direction.** Do a targeted single-line edit of the `work_status:` line rather
than a YAML round-trip. This also matters for review integrity — a 161-line diff on a
requirements file hides real changes among reformatting noise.

---

### KI-BO-004 — Gate `reason` serialises as the string `"null"`

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/fast-lane-ship.js` — `TEST_WRITER_SCHEMA`

**Symptom.** The schema declares `reason: { type: "string" }`, but
`verify_red_baseline` returns `null` for `reason` when the gate passes. The agent
coerces it, so the recorded value is the four-character string `"null"`.

**Evidence.** Journal entry for the TKT-600a-1 run: `"gate_passed": true,
"reason": "null"`.

**Fix direction.** Allow `["string", "null"]` in the schema. Harmless today because
the workflow branches on `gate_passed`, but it is a trap for anything that later
branches on `reason`.

---

### KI-BO-005 — `injection_builders.py` is invoked as a CLI but has no CLI

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-14 · **Last seen:** 2026-08-14
- **Where:** `templates/workflows-js/fast-lane-build.js:121` → `scripts/injection_builders.py`

**Symptom.** The workflow calls the module as a command-line script
(`injection_builders.py assemble_context_bundle`), but it defines no `argparse` and no
`__main__` block. The path resolves, the call runs, nothing happens.

**Evidence.** Verified zero occurrences of `argparse`/`__main__` in
`scripts/injection_builders.py`. First found during the BP-900g-6 work and recorded in
that PR as out of scope; re-confirmed 2026-08-18.

**Fix direction.** Either give it a real CLI or remove the call. Note this is
**verbatim the failure class `CLAUDE.md` already documents** — "`fast_lane.py` had no
CLI so the runner's `select_batch` call was a silent no-op". It recurred, so whatever
fix lands should be covered by a test that actually executes the command.

---

### KI-BO-006 — `fast-lane-build.js` is deployed but orphaned

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-14 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/fast-lane-build.js`

**Symptom.** Nothing invokes it. The only `Workflow("fast-lane...")` call anywhere is
`fast-lane-ship`, and `/fast-lane-build` routes there. The orphan is still built,
deployed, and maintained — it was updated alongside `fast-lane-ship` in the BO-2400a-3
amendment purely to keep it consistent.

**Evidence.** Grep for `fast-lane-build` call sites returns only the command template,
which dispatches `fast-lane-ship`.

**Fix direction.** Delete it, or document why it is kept. This needs a deletion
decision, not a behaviour promise — do not drag a `test_spec` behind it.

---

### KI-BO-007 — `build-feature` counts a phase as completed when the agent halted without doing it, yielding `status: ok` with no PR

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/build-feature.js` — the per-phase result handling
  that populates `completed_phases`

**Symptom.** A phase agent that runs to completion but deliberately performs **no
action** is recorded in `completed_phases` exactly like one that did the work. The
`pull-request` agent is the reliable trigger: its Confirmation Contract forbids pushing
or calling `gh pr create` without an affirmative user turn, and no user turn exists
inside a workflow dispatch, so it drafts the PR, halts at the gate, and returns a
well-formed message explaining that it stopped. The workflow reads that as success.

The result is a top-level `"status": "ok"` and `"pull-request"` in `completed_phases`
for a branch that was never pushed and a PR that does not exist. The same shape applies
to any phase whose agent can legitimately decline.

**Evidence.** Run `wf_ebe75602-f98` (ticket ACD-1900b-5-i) returned
`{"status":"ok", "completed_phases":[…,"commit","pull-request"]}`. Verified against git:
`git ls-remote --heads origin ticket/TICKET-20260818-ACD-1900b-5-i` returned empty, no PR
existed, and the branch sat at `[ahead 3]` with no upstream. The journal entry for that
agent reads: *"Pre-flight complete, PR drafted, but I am holding at the mandatory
confirmation gate before pushing … No user turn is available in this dispatch to supply
the required affirmative."* The commit phase in the same run genuinely did commit, so
this is not a blanket failure — it is per-phase, and invisible without checking git.

**Related.** The same run skipped `architect-review` and `documentation-verifier` on
`cross_agent` blockers and still reported `status: ok`; skipped-on-blocker phases are
surfaced in `skipped_phases`, which is correct and legible. The defect here is narrower:
a phase in `completed_phases` that did nothing.

**Fix direction.** A phase's completion should be asserted against an observable side
effect, not against the agent returning cleanly — for `pull-request`, that the remote
branch exists and `gh pr list --head <branch>` is non-empty. Failing that, the agent's
own "I halted at the gate" outcome needs a distinct status the workflow routes on, so it
lands in `skipped_phases` (or a new `halted_phases`) rather than `completed_phases`.
Reporting `status: ok` while a required terminal phase silently did not happen is the
phantom-done pattern applied to the build loop itself.

---

### KI-BO-008 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run can never reuse its own worktree and aborts at phase one

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/setup_ticket_worktree.py:232-275` (`_worktree_exists`), called at `:1289` from `cmd_create_fastlane_worktree`; branch built at `:1286` by `_fastlane_branch` (`:487-500`)

**Symptom.** `cmd_create_fastlane_worktree` creates the branch `fast-lane/<slug>` but asks
`_worktree_exists(slug)` whether a worktree already exists. That function matches a branch
against exactly three hardcoded prefixes:

```python
f"refs/heads/feature/{branch}",
f"refs/heads/ticket/{branch}",
f"refs/heads/ac-authoring/{branch}",
```

`fast-lane/` is absent, so the lookup can never match a fast-lane worktree. The reuse
branch is unreachable code. Every invocation falls through to `git worktree add`, which
fails with exit 128 the moment anything already occupies the target path. The workflow
surfaces this as `{"worktree_path": ""}` and halts at its first phase, having done nothing.

**Two consequences, the second worse than the first.**

*Collision.* The worktree path is derived solely from the AC id — `worktrees/<slug>` — so
any pre-existing directory there kills the run. This is how it was found: a hand-created
`worktrees/bo-1500a-5` (made minutes earlier for the same AC) caused
`fatal: '/home/henzeh/projects/leafcutter/worktrees/bo-1500a-5' already exists`, then
`fatal: … contains modified or untracked files, use --force to delete it`.

*Non-idempotency.* Re-running the fast lane on an AC it has already built fails the same
way, against its **own** prior worktree — which is exactly what the reuse branch exists to
prevent. `git worktree list` currently shows `worktrees/bo-2900g-3` on `fast-lane/bo-2900g-3`,
so re-running `BO-2900g-3` today would abort at phase one for this reason alone. A build
tool that cannot be re-run on the same input is the more serious half of this defect; the
collision is just the loud version.

**Evidence.** Confirmed by reading the source at HEAD, not inferred from the failure.
`grep -n "refs/heads/fast-lane" templates/scripts/setup_ticket_worktree.py` returns nothing;
`_worktree_exists(slug)` is called at `:1289` (and at `:1398` in the `scripts/` build-output
copy) while `_fastlane_branch(slug)` returns `fast-lane/<slug>`. Both copies carry it —
`scripts/setup_ticket_worktree.py` is generated from `templates/`, so a fix must land in
`templates/` and be mirrored, never edited in `scripts/` alone.

**Fix direction.** Pass the full branch name and match on it, rather than reconstructing
prefixes inside the lookup — `_worktree_exists` already receives a bare slug from three
other call sites, so the low-risk shape is an optional `prefixes` argument (or a
`full_branch=` overload) with `fast-lane/` added for this caller. Two things worth deciding
at the same time, both of which this AC tree (`BO-1500f-2`) is already specifying for the
authoring path: whether a re-run should reuse the existing worktree or mint a
run-distinct one, and whether the path should carry anything beyond the AC id so two
sessions on one AC cannot resolve to the same directory. Whatever is chosen, the failure
should name the occupying path and say which of the two cases it is, instead of surfacing an
empty `worktree_path`.
