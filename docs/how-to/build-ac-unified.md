---
title: "How to use the unified /build-ac entry point"
description: "Task-oriented guide: /build-ac auto-detects leaf vs goal mode — leaf ACs generate a single ticket, goal ACs generate a full EPIC folder."
type: how-to
category: how-to
status: active
created: 2026-06-06
last_updated: 2026-06-06
components:
  - ac_driven_dev
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md
  - docs/architecture/diagrams/c2-004-build-ac-flow.md
  - docs/how-to/goal-to-epic.md
  - docs/how-to/approval-gate.md
  - docs/how-to/ac-driven-development.md
---

# How to use the unified /build-ac entry point

`/build-ac` is the single entry point for building any AC, regardless of its
level in the hierarchy. You do not need to know whether an AC is a leaf (L2/L3)
or a goal (L0/L1) before invoking it — the system auto-detects the type and
routes to the appropriate pipeline.

This guide covers four tasks:

1. [Auto-detection: how the system decides the mode](#1-auto-detection)
2. [Leaf AC path — single-ticket mode](#2-leaf-ac-path)
3. [Goal AC path — epic-generation mode](#3-goal-ac-path)
4. [L1-with-no-children edge case](#4-l1-with-no-children-edge-case)

**Related AC IDs:** ACD-1200e-3 (this guide), ACD-1200e (unified entry point),
ACD-1200e-1 (mode detection), ACD-1200e-2 (mode message), ACD-1200 (full
ACD-1200 feature family).

---

## 1. Auto-detection

When you run:

```
/build-ac --ac <ID>
```

the system calls `build_ac_mode_detection.detect_ac_mode()` immediately. This
function reads two fields from the AC YAML:

- **`level`** — the hierarchical level of the AC (`L0`, `L1`, `L2`, `L3`).
- **`covered_by`** — the list of child AC IDs (non-empty means this AC is a
  composite/goal that has been decomposed).

Detection rules (evaluated in order):

| AC level | covered_by | Mode | Action |
|----------|-----------|------|--------|
| `L2`, `L3` | any value | **leaf** | Single-ticket path |
| `L0`, `L1` | non-empty | **goal** | Epic-generation path |
| `L0`, `L1` | empty / None | **l1_no_children** | Error — see §4 |

Unknown levels default to **leaf** for backward compatibility.

No user input is needed for detection — it is automatic and instant.

---

## 2. Leaf AC path — single-ticket mode

When the AC is a leaf (L2 or L3), `/build-ac` behaves exactly as it did
before EPIC-GoalToEpic: it generates one ticket and asks for confirmation.

No mode-switch message is printed (the leaf path is silent on detection).

### What happens

1. The system calls `generate_ticket_from_ac.py --ac <ID>`.
2. The generated ticket is written to `tickets/00_inbox/`.
3. You are prompted: `"Next AC: <id> — <title>. Build this ticket now? (yes / review / skip)"`
4. If you answer `yes`, `/build-feature` is dispatched on the ticket.
5. After the build completes, `mark_ac_done.py` sets `work_status: done` on
   the AC YAML.

For the full sequence diagram of this path, see the
[/build-ac execution flow](../architecture/diagrams/c2-004-build-ac-flow.md).

For task-by-task instructions on the leaf path, see
[How to use the AC-driven development system](ac-driven-development.md).

---

## 3. Goal AC path — epic-generation mode

When the AC is a goal (L0 or L1 with children), `/build-ac` switches to
epic-generation mode. The system prints:

```
ACD-050 is a goal — generating epic from all leaf ACs beneath it.
```

### What happens

1. `scan_ac_store.traverse_ac_tree()` collects all leaf AC IDs beneath the goal.
2. `goal_to_epic.classify_readiness()` classifies each leaf as `approved` or
   `unapproved` and displays the **readiness report**.
3. You choose from three gate options (`yes` / `review-all` / `cancel`).
4. For approved ACs, tickets are generated, dependency-sorted, and assembled
   into a numbered EPIC folder.
5. `stamp_target_epic()` writes `target_epic: EPIC-<Name>` into each included
   AC YAML.

For complete task-by-task instructions on this path, see:
- [How to use the goal-to-epic workflow](goal-to-epic.md)
- [How to use the approval gate](approval-gate.md)

For the end-to-end sequence diagram, see the
[Goal-to-Epic Dispatch — Sequence Diagram](../architecture/diagrams/c2-005-goal-to-epic-dispatch.md).

---

## 4. L1-with-no-children edge case

If you invoke `/build-ac --ac <ID>` with an L0 or L1 AC that has an empty
`covered_by` field, the system cannot enter either the leaf or goal pipeline.
It prints:

```
<ID> is an L1 with no leaf ACs beneath it.
Decompose into L2/L3 first, or use /ba to generate behavioral specifications.
```

No files are written and no ticket is generated.

### Why this happens

A goal-level AC (L0 or L1) represents a business capability at a high level
of abstraction. Before it can be built, it must be **decomposed** into
concrete leaf ACs (L2/L3) that each map to a single testable requirement.

If `covered_by` is empty, the AC has never been decomposed, or the
decomposed children are stored under a different ID.

### Remediation

**Option A — Decompose via business-analyst:**

```
/business-analyst
```

Pass the L1 AC file path. `business-analyst` produces L2/L3 behavioural
ACs and writes them to the store. After decomposition, re-run `it-po`
to enrich the new ACs, then approve them and re-invoke `/build-ac`.

**Option B — Manual decomposition:**

Create L2/L3 AC YAML files under `docs/acceptance-criteria/<component>/`
following the [AC YAML schema](ac-traceability-store.md). Set the `parent`
field on each new AC to the L1 ID, and update the L1's `covered_by` list
to include the new child IDs.

After decomposition, validate the store:

```bash
python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/
```

Then re-invoke `/build-ac --ac <ID>`.

---

## Comparison: leaf path vs goal path

| | Leaf path | Goal path |
|---|-----------|-----------|
| **AC type** | L2 or L3 | L0 or L1 with children |
| **Output** | One ticket in `tickets/00_inbox/` | EPIC folder in `tickets/00_inbox/epics/` |
| **Prompt** | `yes / review / skip` | Readiness gate (`yes / review-all / cancel`) |
| **Dependency sorting** | N/A | Topological sort of leaf-to-leaf deps |
| **target_epic stamping** | No | Yes — writes `target_epic:` into each AC YAML |
| **Driver after build** | `/build-feature <ticket>` | `/build-feature <epic-folder>` |

---

## Diagram Reference

- [Goal-to-Epic Dispatch — Sequence Diagram](../architecture/diagrams/c2-005-goal-to-epic-dispatch.md) — goal path end-to-end.
- [/build-ac Execution Flow](../architecture/diagrams/c2-004-build-ac-flow.md) — leaf path end-to-end.

---

## See Also

- [How to use the goal-to-epic workflow](goal-to-epic.md) — complete walkthrough
  of the epic-generation mode.
- [How to use the approval gate](approval-gate.md) — readiness report and
  gate prompt details.
- [How to use the AC-driven development system](ac-driven-development.md) —
  authoring, approving, and building ACs from the beginning.
