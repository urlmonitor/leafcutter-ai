---
allowed-tools: Read, Bash(python3 *)
description: >
  Reference skill for the build-ac coordinator. Documents the three routing
  modes (leaf, goal, L1-no-children) added in EPIC-GoalToEpic ticket 05,
  the mode-detection algorithm, and the exact output contracts for each path.
  Load when: implementing or auditing the build-ac agent template, writing
  tests for mode-detection logic, or diagnosing a mis-routing bug.
name: build-ac
---

# build-ac Skill

This skill documents the routing behaviour of the `/build-ac` coordinator
added in ticket 05 of EPIC-GoalToEpic. It is the reference for:

- **Three routing modes** — leaf, goal, L1-no-children.
- **Mode-detection algorithm** — how level + covered_by determine the route.
- **Output contracts** — the exact messages and side-effects each mode produces.

---

## §1 Routing Modes

The `/build-ac` agent reads two fields from the target AC YAML to decide its
routing mode:

| Field | Source | Meaning |
|-------|--------|---------|
| `level` | AC YAML `level:` key | `L0` = root goal; `L1` = sub-goal; `L2`/`L3` = leaf implementation units |
| `covered_by` | AC YAML `covered_by:` key | List of child AC IDs. Empty or absent = no children. |

### Mode Table

| Condition | Mode | Single-ticket path | Epic-generation path |
|-----------|------|--------------------|----------------------|
| level ∈ {L2, L3, unknown} | **leaf** | yes | no |
| level ∈ {L0, L1} AND covered_by non-empty | **goal** | no | yes |
| level ∈ {L0, L1} AND covered_by empty/absent | **l1_no_children** | no | no (error) |

The detection is implemented in `scripts/build_ac_mode_detection.detect_ac_mode()`.

---

## §2 Mode A — Leaf AC (single-ticket path)

**Trigger:** level is L2 or L3 (or any unrecognised level), OR `covered_by`
is absent or empty.

**Backward compatibility guarantee:** the leaf path is identical to the
pre-ACD-1200 build-ac behaviour. No mode message is printed. The agent
proceeds directly to `generate_ticket_from_ac.py`.

### Output contract

```
(no mode-switch message — silent routing)
Found AC: <id> — <title>
Priority: <priority>
Ticket path: <TICKET_PATH>

Build this ticket now? (yes / review / skip)
```

---

## §3 Mode B — Goal AC (epic-generation path)

**Trigger:** level is L0 or L1 AND `covered_by` is non-empty.

The agent switches to epic-generation mode. Before entering the epic flow,
it prints the mode-switch message:

```
<id> is a goal — generating epic from all leaf ACs beneath it.
```

Where `<id>` is the exact AC ID passed to `--ac`. The full template is:

```python
GOAL_MESSAGE_TEMPLATE = "{id} is a goal — generating epic from all leaf ACs beneath it."
```

After printing the message, the agent calls `goal_to_epic.py`:

```bash
python3 {{config.output_root}}/scripts/ac_store/goal_to_epic.py --ac <id> 2>/tmp/build_ac_goal_to_epic_err.txt
```

The epic flow includes:
1. Tree traversal of leaf ACs beneath `<id>` (ACD-1200a-1)
2. Readiness gate with approve/review-all/cancel prompt (ACD-1200b-2)
3. Dependency wiring (ACD-1200c)
4. Ticket generation for each approved leaf (ACD-1200d)
5. Target-epic stamping on each ticket (ACD-1200d-1)
6. Epic folder assembly

### L1-scoped epics

When `--ac` targets an L1 AC (a sub-goal), the epic is scoped to only the
leaves beneath that L1. The flow is identical to the L0 case; the scope is
determined by the tree-traversal function, not the mode-detection code.

### Output contract (Step 3 confirmation prompt for goal mode)

```
Found AC: <id> — <title>
Priority: <priority>
Epic path: <EPIC_PATH>

Build this epic now? (yes / review / skip)
```

---

## §4 Mode C — L1 with No Children (error path)

**Trigger:** level is L0 or L1 AND `covered_by` is empty or absent.

The AC is structured as a composite (goal-level) AC but has no leaf children.
Attempting to generate an epic would produce zero tickets. The agent surfaces
a clear error with a remediation suggestion.

### Output contract

```
<id> is an L1 with no leaf ACs beneath it. Decompose into L2/L3 first, or use /ba to generate behavioral specifications.
```

Where `<id>` is the exact AC ID. The full template is:

```python
L1_NO_CHILDREN_MESSAGE_TEMPLATE = (
    "{id} is an L1 with no leaf ACs beneath it. "
    "Decompose into L2/L3 first, or use /ba to generate behavioral specifications."
)
```

After printing this message:
- No ticket is generated.
- No epic folder is created.
- The agent exits cleanly (no error code to the user).

---

## §5 --dry-run Propagation

The `--dry-run` flag propagates through both the leaf path and the goal path.

| Mode | --dry-run behaviour |
|------|---------------------|
| leaf | `generate_ticket_from_ac.py --ac <id> --dry-run` prints proposed ticket; no file write |
| goal | `goal_to_epic.py --ac <id> --dry-run` prints proposed leaf set and ticket plan; no file write |
| l1_no_children | Same error message; no file write (unchanged — no dry-run needed for an error path) |

---

## §6 Python Helper — `scripts/build_ac_mode_detection.py`

The mode-detection logic is isolated in a pure function:

```python
from scripts.build_ac_mode_detection import detect_ac_mode

result = detect_ac_mode(
    ac_id="ACD-050",
    level="L0",
    covered_by=["ACD-050a", "ACD-050b"],
)
# result == {
#   "mode": "goal",
#   "message": "ACD-050 is a goal — generating epic from all leaf ACs beneath it.",
#   "invoke_goal_to_epic": True,
#   "use_single_ticket_path": False,
# }
```

The function is pure — no I/O, no side-effects. It is safe to call in tests
and in the agent template's inline Python invocations.

### Public constants

| Constant | Value | Use |
|----------|-------|-----|
| `AC_MODE_LEAF` | `"leaf"` | Mode identifier for leaf ACs |
| `AC_MODE_GOAL` | `"goal"` | Mode identifier for goal ACs |
| `AC_MODE_L1_NO_CHILDREN` | `"l1_no_children"` | Mode identifier for the error path |
| `LEAF_MESSAGE_NONE` | `None` | Leaf path has no mode-switch message |
| `GOAL_MESSAGE_TEMPLATE` | `"{id} is a goal — ..."` | Format string for mode B |
| `L1_NO_CHILDREN_MESSAGE_TEMPLATE` | `"{id} is an L1 with no leaf ACs ..."` | Format string for mode C |

---

## §7 Test Coverage

Unit tests live in `unit_tests/agents/test_build_ac_mode_detection.py`.

The test class `TestBuildAcModeDetection` covers:

- **AC-1 / ACD-1200e-1**: L2 leaf with empty covered_by → leaf mode; no message; no epic invocation.
- **AC-2 / ACD-1200e-2**: L0 and L1 with non-empty covered_by → goal mode; correct message; `invoke_goal_to_epic=True`.
- **AC-3 / ACD-1200e-2-i**: L1 with empty covered_by → l1_no_children; correct decompose message; no writes.

Plus boundary cases:
- L0 with empty covered_by → l1_no_children (not leaf).
- L2 with non-empty covered_by → leaf (level is primary discriminator for leaf detection).
