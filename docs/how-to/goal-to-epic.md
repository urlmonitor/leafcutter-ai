---
title: "How to use the goal-to-epic workflow"
description: "Task-oriented guide: invoke /build-ac with a goal-level AC ID to generate a full EPIC folder of tickets in one command."
type: how-to
category: how-to
status: active
created: 2026-06-06
last_updated: 2026-06-06
components:
  - ac-driven-dev
  - build-orchestration
  - ticket-creation
related_docs:
  - docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md
  - docs/architecture/diagrams/c2-004-build-ac-flow.md
  - docs/how-to/approval-gate.md
  - docs/how-to/build-ac-unified.md
  - docs/how-to/ac-driven-development.md
---

# How to use the goal-to-epic workflow

The goal-to-epic workflow turns a goal-level AC (L0 or L1) into a fully
populated EPIC folder of tickets in one command. Instead of generating
tickets one by one, you point `/build-ac` at a goal AC and the system
traverses the AC tree, presents a readiness gate, generates tickets for
all approved leaf ACs, resolves inter-ticket dependencies, and assembles
everything into a numbered EPIC folder.

This guide covers four tasks:

1. [Invoking /build-ac with a goal AC ID](#1-invoking-build-ac-with-a-goal-ac-id)
2. [Understanding the output — what gets created](#2-understanding-the-output)
3. [Using the generated EPIC folder with /build-feature](#3-using-the-generated-epic-folder)
4. [Troubleshooting: L1 with no children](#4-troubleshooting-l1-with-no-children)

**Prerequisites:**

- EPIC-GoalToEpic tickets 01–05 are merged and deployed
  (`build.py` has been run in your project).
- `goal_to_epic.py`, `build_ac_mode_detection.py`, and
  `scan_ac_store.py` are installed under `scripts/`.
- The goal AC (L0 or L1) has at least one approved leaf AC beneath it.
  Use the [AC-driven development guide](ac-driven-development.md) to
  author and approve ACs if needed.

**Related AC IDs:** ACD-1200a-4 (this guide), ACD-1200a (pipeline),
ACD-1200b (readiness gate), ACD-1200c (dependency wiring),
ACD-1200d (target_epic stamping), ACD-1200e (unified entry point).

---

## 1. Invoking /build-ac with a goal AC ID

### Step 1: Find your goal AC ID

List all L0 and L1 ACs that have leaf children beneath them:

```bash
python scripts/ac_store/scan_ac_store.py --level goal --work-status todo --json
```

Note the `id` field of the goal AC you want to build (e.g. `ACD-050`).

### Step 2: Confirm the AC tree is populated

Before invoking the workflow, verify that the goal AC has leaf ACs beneath it:

```bash
python scripts/ac_store/scan_ac_store.py --parent ACD-050 --level leaf
```

If this returns an empty list, the L1s beneath your goal have not been
decomposed yet. See [Troubleshooting](#4-troubleshooting-l1-with-no-children).

### Step 3: Invoke /build-ac

```
/build-ac --ac ACD-050
```

The system will:

1. Detect that `ACD-050` is a goal-level AC (L0 or L1 with children).
2. Print: `ACD-050 is a goal — generating epic from all leaf ACs beneath it.`
3. Traverse the AC tree and collect all leaf AC IDs.
4. Classify each leaf as `approved` or `unapproved` and display the
   **readiness report**.
5. Present the three-choice gate prompt.

For a full walkthrough of the gate prompt options, see the
[approval gate guide](approval-gate.md).

---

## 2. Understanding the output

After you answer `yes` at the readiness gate (or if all ACs are already
approved), the system generates:

### Ticket files

One ticket per approved leaf AC, written to `tickets/00_inbox/epics/EPIC-<Name>/`:

```
tickets/00_inbox/epics/EPIC-ValidateApiInputs/
  01_validate-input-schema.md
  02_return-error-on-invalid-body.md
  03_log-validation-failures.md
  Master_Plan.md       ← optional, if your project uses one
```

The numeric prefixes (`01_`, `02_`, `03_`, …) reflect **topological build
order** — a ticket that depends on another appears after it.

### EPIC folder name

The folder name is derived from the goal AC's `title` field, converted to
PascalCase and prefixed with `EPIC-`. For example:

| AC title | EPIC folder |
|----------|-------------|
| `validate api inputs` | `EPIC-ValidateApiInputs/` |
| `rate-limit enforcement` | `EPIC-RateLimitEnforcement/` |

### target_epic stamping

After the EPIC folder is assembled, `goal_to_epic.py` writes
`target_epic: EPIC-<Name>` into each included AC YAML file. This links the
AC back to the EPIC it belongs to and prevents the AC from being picked up
by `/build-ac` again for a different EPIC without an explicit conflict prompt.

---

## 3. Using the generated EPIC folder

Once the EPIC folder exists, drive it with the standard `/build-feature` workflow:

### Step 1: Open the EPIC

```
/build-feature tickets/00_inbox/epics/EPIC-ValidateApiInputs/
```

`/build-feature` reads the `Master_Plan.md` (if present) and each ticket's
`depends_on` frontmatter to compute the dependency graph. It dispatches
ticket-supervisors in topological order, parallelising tickets with
disjoint `files_touched` sets.

### Step 2: Monitor progress

Each ticket's `agents:` map tracks which phase agents are pending. Check the
overall EPIC status at any time:

```bash
grep -l "status: todo\|status: in_progress" tickets/00_inbox/epics/EPIC-ValidateApiInputs/*.md
```

### Step 3: After all tickets are done

When every sub-ticket in the EPIC folder has `status: done`, `/build-feature`
marks the EPIC complete. One PR covers all commits from the EPIC (the
`pull-request` phase agent opens it on the first ticket and subsequent tickets
push to the same branch).

---

## 4. Troubleshooting: L1 with no children

If `/build-ac` prints:

```
ACD-050 is an L1 with no leaf ACs beneath it.
Decompose into L2/L3 first, or use /ba to generate behavioral specifications.
```

This means the goal AC has no decomposed leaf children yet. To resolve it:

**Option A — Decompose manually:**

```
/business-analyst
```

Pass the L1 AC file path. `business-analyst` will produce L2/L3
behavioural ACs and any documentation ACs required by `documentation_triggers`.

**Option B — Use /ba for an automated decomposition:**

```
/ba --ac ACD-050
```

After decomposition, re-run `it-po` to enrich the new ACs, approve the
ones you want built, and then re-invoke `/build-ac --ac ACD-050`.

---

## Diagram Reference

For the full end-to-end sequence of the goal-to-epic pipeline, see:

- [Goal-to-Epic Dispatch — Sequence Diagram](../architecture/diagrams/c2-005-goal-to-epic-dispatch.md)

---

## See Also

- [How to use the approval gate](approval-gate.md) — readiness report,
  gate prompt options, and the IT PO review-all path.
- [Unified /build-ac entry point](build-ac-unified.md) — how `/build-ac`
  auto-detects leaf vs goal mode.
- [How to use the AC-driven development system](ac-driven-development.md) —
  authoring, approving, and building individual ACs.
