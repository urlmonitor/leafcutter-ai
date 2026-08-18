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

### KI-BO-002 — moved to `ac-store`

Refiled 2026-08-18 as **KI-ACS-001** in
[`docs/known-issues/ac-store.md`](ac-store.md): *an AC is marked `done` with no link
to the code implementing it.*

Found during a fast-lane run and the call site is in `fast_lane.py`, but what
`implemented_by` must contain — and what a claim of "done" has to prove — is
provenance semantics owned by `ac-store`, not by the lane that invokes it. The id is
retired here rather than reused, so the numbering gap is intentional.

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
