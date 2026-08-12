---
title: "How to run the fast-lane build loop"
description: "Run the lean two-agent batch build loop that selects a cohesive AC batch, writes failing test stubs, gates on red baseline, implements the batch, and gates on green coverage before staging a commit."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-08-11
components:
  - build_orchestration
related_docs:
  - docs/how-to/choose-build-path.md
  - docs/how-to/prove-ac-done.md
  - docs/architecture/diagrams/c3-fast-lane-build-loop-sequence.md
  - docs/architecture/diagrams/c2-fast-lane-build-path-components.md
  - docs/architecture/components/build-orchestration.md
---

# How to run the fast-lane build loop

The fast-lane build loop is a lean alternative to the full ticket-supervisor
pipeline. It runs a single test-writer agent to produce failing stubs for a
cohesive set of ACs, confirms the red baseline with a deterministic Python gate,
runs a single coder agent to make them green, and confirms green state and AC
coverage with a second deterministic gate before staging the output for commit.
Total LLM dispatches for the loop: two, regardless of set size.

**One-command entry (recommended): `/fast-lane-build <AC-id>`.** Point the
command at any one acceptance-criterion id and it does the whole arc with no
other input (BO-2400f): it opens a fresh isolated worktree off the latest
`origin/main`, resolves that AC's **connected build set** (its subtree plus any
unmet `depends_on` prerequisites, in dependency order, readiness-agnostic —
pointing at the AC is the go-ahead), runs the lean loop above scoped to that set,
then auto-commits and opens a pull request. This is the `fast-lane-ship`
workflow, shimmed by [templates/commands/fast-lane-build.md](../../templates/commands/fast-lane-build.md).
The lean loop itself (`fast-lane-build.js`) remains the inner primitive it drives.

To see everything that still needs building first, export the build backlog as a
JSON dataflow:

```bash
python scripts/build_orchestration/build_dataflow.py \
  --ac-root docs/acceptance-criteria --out docs/build-dataflow.json
# or scope to one AC's connected set:
python scripts/build_orchestration/build_dataflow.py \
  --ac-root docs/acceptance-criteria --ac BO-2400f
```

This guide covers:

1. [Prerequisites](#1-prerequisites)
2. [Invocation](#2-invocation)
3. [The six steps of the loop](#3-the-six-steps-of-the-loop)
4. [When a gate blocks the loop](#4-when-a-gate-blocks-the-loop)
5. [Contrast with the heavy path](#5-contrast-with-the-heavy-path)

---

## 1. Prerequisites

Before invoking `/fast-lane-build`, confirm the following.

**The workflow is deployed.** Verify `fast-lane-build.js` is present in the
Claude Code workflows directory:

```bash
ls .claude/workflows/fast-lane-build.js
```

If the file is absent, run `build.py` using a leafcutter-ai version that
includes the `fast-lane-build.js` workflow template.

**The gate script is deployed.** Verify the gate script is reachable from the
worktree root:

```bash
ls scripts/build_orchestration/fast_lane.py
```

**At least one approved AC exists.** The `select_batch` gate returns an empty
list if no ACs are ready. Confirm there is at least one leaf-level AC with
`status: active`, `readiness: approved`, and `work_status: todo` whose
`depends_on` ACs are all done:

```bash
python scripts/build_orchestration/fast_lane.py select_batch \
  --ac-store docs/acceptance-criteria \
  --batch-size 5
```

Expected output: a JSON array of AC ids (e.g. `["ACS-042", "ACS-043"]`). An
empty array (`[]`) means no ready ACs exist — author and approve ACs via
`/plan-feature` before proceeding.

**You are working in an isolated worktree.** The fast lane writes test files and
production code directly into the worktree. The workflow halts immediately if no
`worktree_path` argument is provided. Do not pass the main clone path.

**Routing condition met.** The fast lane is valid only when:
- `scope == "scoped"` — the batch touches a single, coherent area of the codebase.
- `attended == true` — you are present to react to gate failures.
- `defect_cost == "low"` — a defect in this batch does not have high downstream risk.

If any condition is unmet, use the heavy path (`/build-feature`). See
`docs/how-to/choose-build-path.md` for the routing decision tree.

---

## 2. Invocation

### One-command AC-scoped build (recommended)

Pass a single acceptance-criterion id. Nothing else is required — no worktree,
no batch size, no manual PR:

```
/fast-lane-build BO-2400f
```

The `fast-lane-ship` workflow then, in fixed code-defined order:

1. **Worktree** — `create-fastlane-worktree <slug>` opens `fast-lane/<slug>` off
   the latest `origin/main`, bootstrapped.
2. **Resolve** — `select_connected --ac <id>` computes the connected build set.
   An empty set (already done, or nothing not-done) is a clean no-op: no PR.
3. **Lean loop** — the two-agent test-writer → coder loop, scoped to the resolved
   ids and gated by `verify_red_baseline` and `verify_green_and_coverage`.
4. **Commit + PR** — a commit agent marks the built ACs done (coverage-gated) and
   commits; a pull-request agent opens the PR against `main`.

The green+coverage gate is the arbiter: if it does not pass, **no PR is opened**
and the failing AC ids are reported.

### Inner primitive (advanced)

The lean loop is also runnable directly as the `fast-lane-build` workflow when you
already have a worktree and want the global ready-batch rather than one AC's
connected set:

| Argument | Required | Default | Description |
|---|---|---|---|
| `worktree_path` | Yes | — | Absolute path to the isolated worktree. |
| `batch_size` | No | `5` | Maximum number of ready ACs to select. |
| `ac_store_root` | No | `"docs/acceptance-criteria"` | Path (from the worktree root) to the AC YAML store. |

Most users should prefer the one-command form above; the inner primitive does not
create a worktree, commit, or open a PR.

### Programmatic API — exclude_structural_parent

When calling `resolve_connected_build_set` from Python (rather than through the
`select_connected` CLI subcommand), one keyword-only argument is available that
the CLI does not expose:

```python
from pathlib import Path
from scripts.build_orchestration.fast_lane import resolve_connected_build_set

ids = resolve_connected_build_set(
    "BO-2600a-1",
    ac_root=Path("docs/acceptance-criteria"),
    exclude_structural_parent=True,
)
```

**`exclude_structural_parent`** (`bool`, default `False`) — when `True`, the
transitive `depends_on` closure walk skips any dependency that is the structural
parent of the node currently being expanded. The structural parent is computed
by `derive_parent_id(node)` from `scripts/ac_store/ac_parent_id.py`. Use this
flag when a node lists its own L1 or L2 composite parent as a `depends_on`
entry and you do not want that parent's subtree pulled into the build set via
the closure walk.

Behaviour summary:

| `exclude_structural_parent` | A structural-parent dep in `depends_on` | Result |
|---|---|---|
| `False` (default) | Walked normally | Parent composite expands into the build set |
| `True` | Skipped during closure walk | Parent composite is NOT added to the build set |

Genuine (non-structural-parent) `depends_on` entries are always walked
regardless of this flag. The subtree union (via `traverse_ac_tree`) is
**unaffected** — the AC's own children enter the set through the subtree step,
not through the closure walk, so excluding the structural parent never drops the
AC's real children.

Callers that do not pass this argument get the default `False` behaviour, which
is byte-identical to the pre-BO-2600 traversal. All existing callers remain
compatible without change.

---

## 3. The Six Steps of the Loop

The workflow executes these steps in fixed order. Steps 1, 3, and 5 are
deterministic Python gate scripts — they invoke no LLMs. Steps 2 and 4 are the
only LLM dispatches.

### Step 1 — select_batch (deterministic gate)

The workflow constructs the `select_batch` invocation and passes it to the
test-writer as its discovery command. The gate itself is not dispatched as an
LLM — it is a single Python call:

```bash
python3 <worktree_path>/scripts/build_orchestration/fast_lane.py select_batch \
  --ac-store <worktree_path>/docs/acceptance-criteria \
  --batch-size <batch_size>
```

**What it selects.** The gate reads every AC YAML file under `ac_store_root` and
filters to ACs that satisfy all of:

- `level` is `L2` or `L3` (leaf level — not a goal or feature AC)
- `status: active`
- `readiness: approved`
- `work_status: todo`
- every id in `depends_on` has `work_status: done`, or `depends_on` is empty

**Sort order.** Ready ACs are sorted by priority ascending (`critical` < `high` <
`medium` < `low`), then by estimated complexity ascending (`S` < `M` < `L` <
`XL`), then by id ascending. This sort order is identical to `scan_ac_store`, so
the same store state always produces the same ordered list.

**Output.** A JSON array of up to `batch_size` AC ids in priority order. The
same store state always produces the same list — the gate is deterministic and
does not modify any file.

If the array is empty, the workflow returns a halting error: no ACs are ready.

---

### Step 2 — test-writer (LLM dispatch 1 of 2)

One agent dispatch covers the entire batch, regardless of how many ACs are in
it. The test-writer:

1. Runs the `select_batch` command (its first Bash call) to obtain the ordered
   AC id list.
2. Reads each AC YAML from `ac_store_root`.
3. Writes a minimal failing test stub for each AC, asserting the AC's behavior.
   Each stub must carry a `# covers: <id>` annotation so the gate scripts can
   link the test to its AC.
4. Runs the full test suite and confirms that every new stub is RED (non-zero
   exit). The test-writer does not write any production code.
5. Returns `{"status": "ok", "tests_written": [...], "message": "..."}`.

If the test-writer returns any status other than `"ok"`, the workflow halts
immediately with `classification: halt`. The red-baseline gate is not run and
the coder is not dispatched.

---

### Step 3 — verify_red_baseline (deterministic gate)

This gate runs before the coder is dispatched. It is a deterministic Python
script with no LLM involvement.

**What it checks.** The gate scans the test root for files containing
`# covers: <id>` annotations that match any AC id in the batch. For each linked
test, it runs pytest and verifies that the test **fails**. A test that passes
at baseline is a gate violation: it means either the production code already
exists (and this AC may be a duplicate) or the test is under-specified and not
actually asserting the behavior.

**Gate invocation:**

```bash
python3 <worktree_path>/scripts/build_orchestration/fast_lane.py verify_red_baseline \
  --worktree <worktree_path>
```

**Pass condition.** `all_red: true` — every test linked to any AC id in the
batch fails.

**Failure output.** When a test passes at baseline, the gate returns:

```json
{
  "all_red": false,
  "offender": "tests/test_my_module.py::test_feature_x",
  "offender_ac_id": "ACS-042"
}
```

The coder is NOT dispatched when `all_red` is false. Investigate why the
offending test already passes and either fix the test stub or confirm that
the AC is already implemented (see `docs/how-to/prove-ac-done.md`).

---

### Step 4 — python-coder (LLM dispatch 2 of 2)

One agent dispatch covers the entire batch — this is the second and final LLM
dispatch in this workflow. The coder:

1. Runs the test suite to see which batch tests are failing.
2. Implements the minimum production code to make every failing batch test pass.
3. Runs the test suite to confirm all batch tests are GREEN (zero exit).
4. Returns `{"status": "ok", "files_modified": [...], "message": "..."}`.

The coder does not gold-plate: it implements only what the failing tests require.

If the coder returns any status other than `"ok"`, the workflow halts with
`classification: halt`. The green-and-coverage gate is not run and no output is
staged.

---

### Step 5 — verify_green_and_coverage (deterministic gate)

This gate runs after the coder finishes. Two conditions must both hold before
commit staging proceeds.

**Gate invocation:**

```bash
python3 <worktree_path>/scripts/build_orchestration/fast_lane.py verify_green_and_coverage \
  --worktree <worktree_path> \
  --ac-store <worktree_path>/docs/acceptance-criteria
```

**Condition (a) — all linked tests pass.** Every test linked to any AC id in
the batch via `# covers: <id>` must have a `PASSED` outcome. XFAIL, SKIPPED,
FAILED, and ERROR outcomes do not count as passing. The gate collects the pytest
nodeid of every non-passing test and returns them in `failing_tests`.

**Condition (b) — every AC id has at least one covering test.** Every AC id in
the batch must have at least one `# covers: <id>` test in the test root. An AC
with no linked test is returned in `uncovered_ac_ids`. Coverage is resolved
using `verify_done_eligible` from `done_proof.py`, so the semantics stay in
sync with the done-proof gate.

**Pass condition.** `green: true` AND `coverage_ok: true`. Commit staging is
gated on both — neither alone is sufficient.

**Failure output (partial example):**

```json
{
  "green": false,
  "coverage_ok": true,
  "uncovered_ac_ids": [],
  "failing_tests": ["tests/test_my_module.py::test_feature_x"]
}
```

When the gate fails, investigate the failing tests or uncovered ACs before
re-running the coder or adding missing test annotations.

---

### Step 6 — commit staging

When `verify_green_and_coverage` passes, the batch output is staged for commit.
The workflow returns:

```json
{
  "status": "ok",
  "message": "Fast-lane batch complete. ...",
  "worktree_path": "<worktree_path>",
  "batch_size": 5,
  "tests_written": ["<path>", ...],
  "files_modified": ["<path>", ...],
  "gates_passed": ["select_batch", "verify_red_baseline", "verify_green_and_coverage"]
}
```

After the workflow returns `status: ok`, commit the staged output using
`/commit` (or `COMMIT_AGENT_MODE=1` in a supervised batch drive). The workflow
itself does not commit.

---

## 4. When a Gate Blocks the Loop

Each gate halts the workflow with a structured error rather than producing a
partial result.

**select_batch returns empty.** No ACs are ready. Author and approve ACs
(`/plan-feature`) or check whether `depends_on` blockers are resolved.

**test-writer returns non-ok.** The test stubs are incomplete. Read the
`testWriterResult.message` field in the halt payload. Common causes: the AC
YAML is malformed, the test file target directory is missing, or the test suite
itself is broken before the stubs were written.

**verify_red_baseline finds a passing test.** The stub is not genuinely failing.
Either (a) the production code already implements this behavior — confirm with
`docs/how-to/prove-ac-done.md` and flip the AC to `work_status: done` — or
(b) the test stub asserts a condition that is trivially true and needs to be
sharpened.

**python-coder returns non-ok.** The implementation is incomplete. Read the
`coderResult.message` field in the halt payload. Re-run the coder manually
against the red-baseline tests, or escalate to the heavy path if scope has
expanded beyond the original batch.

**verify_green_and_coverage fails.** Either tests still fail or an AC has no
linked test. Add the missing `# covers: <id>` annotations to the test stubs,
fix the implementation, and re-invoke the coder manually before re-running the
gate.

---

## 5. Contrast with the Heavy Path

The fast lane and the heavy path (`/build-feature`) produce the same outcome —
green tests, covered ACs, staged commit — but through very different mechanisms.

| Dimension | Fast lane | Heavy path |
|---|---|---|
| LLM dispatches | **2** (test-writer + coder) | Many — planner, test-writer, coder, pr-reviewer, ac-validator, ac-fulfillment-gate, commit, pull-request, each as a separate agent |
| Batch handling | Single dispatch per phase for the entire AC batch | One ticket-supervisor per ticket, each dispatching its own phase agents |
| Deterministic gates | 3 Python gates (select_batch, verify_red_baseline, verify_green_and_coverage) | Fewer Python gates; more LLM judgment in review and validation agents |
| Supervisor chain | None | ticket-supervisor per ticket |
| LLM planner | None | LLM planner reads ticket frontmatter and returns the ordered phase list |
| Worktrees | Single shared worktree for the whole batch | Per-ticket worktrees (in epic mode) |
| PR creation | Not included — caller commits and opens the PR | Automated via pull-request agent |
| Review agents | Not included | pr-reviewer, ac-validator, ac-fulfillment-gate |
| Routing condition | `scope==scoped`, `attended==true`, `defect_cost==low` | Any scope, any attendance, any defect cost |

**When to use the fast lane.** Use it for a tightly scoped, attended batch of
low-risk ACs where you want to reduce LLM overhead and keep the gate logic
deterministic. The three Python gates catch the two most common failure modes
(red baseline violated, coverage incomplete) before a commit ever reaches review.

**When to use the heavy path.** Use it when any of the fast-lane routing
conditions is unmet: the scope is broad, you will not be present to react to
gate failures, or the defect cost of a missed AC is high. The heavy path adds
the review, validation, and PR layers that the fast lane intentionally omits.
See `docs/how-to/choose-build-path.md` for the full routing decision tree.

---

## See Also

- [How to choose a build path](choose-build-path.md) — routing decision tree
  for fast lane vs heavy path vs manual.
- [How to prove an AC is done](prove-ac-done.md) — how `verify_done_eligible`
  works and when to use it directly.
- [C3 sequence diagram — fast-lane build loop](../architecture/diagrams/c3-fast-lane-build-loop-sequence.md) —
  swim-lane view of the six-step loop.
- [C2 component diagram — fast-lane build path](../architecture/diagrams/c2-fast-lane-build-path-components.md) —
  component-level view of the gate scripts and agents.
- [Build orchestration component](../architecture/components/build-orchestration.md) —
  architecture reference for the `build_orchestration` component.
