---
title: "KI-ACD-20261012-ids-mode-names-the-epic-after-its-first-prerequisite — goal_to_epic --ids takes the epic's folder name, Master_Plan title and source_ac from whichever id comes first, and on the documented path that is a prerequisite, not the goal"
description: "high — build_epic_from_ids() derives the folder name, the plan's title and its source_ac from ids[0]. The documented caller passes the connected build set in dependency order, so ids[0] is the first prerequisite leaf, often from another AC tree. There is no flag that names the goal. Observed 2026-10-12: a 48-ticket epic for ACD-2500 came out as EPIC-AnAcMissingFileTargetsOrATestContractIs, with source_ac ACD-1600c-1."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-low-ki-acd-011.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-014.md
  - docs/how-to/goal-to-epic.md
---

# KI-ACD-20261012-ids-mode-names-the-epic-after-its-first-prerequisite — goal_to_epic --ids takes the epic's folder name, Master_Plan title and source_ac from whichever id comes first, and on the documented path that is a prerequisite, not the goal

- **Severity:** high. The epic's identity names the wrong requirement, and two of the three
  fields do it silently. The folder name is visible and gets fixed by hand. The Master_Plan
  `title` and `source_ac` (the plan's only record of which requirement the epic was built for)
  are not checked by anything. Renaming the folder afterwards also breaks every `implemented_by`
  back-reference the run pointed at the old name, on platforms where that repoint works at all
  (see `KI-BO-014`, Occurrence 2).
- **Status:** open, no AC. Repaired by hand in the scaffold commit `32a542a6`
  (branch `ac-authoring/itpo-split-epic`, PR #1145).
- **Occurrences:** 1 (2026-10-12, `goal_to_epic.py --ids` with 48 ids, scaffolding
  `EPIC-RightJobRightAgent`). Structural: every `--ids` run does this.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** line numbers verified on origin/main `a104d934` (the run's branch base `a4ba3d37`
  has identical `scripts/ac_store/` code):
  - `scripts/ac_store/epic_pipeline.py` `build_epic_from_ids()`: the name at `:229`, and the
    plan's goal id and goal title at `:271-274`;
  - `scripts/ac_store/epic_master_plan.py`: `title: "EPIC: <goal_title>"` at `:237`,
    `source_ac: goal_ac_id` at `:243`;
  - `scripts/ac_store/epic_cli.py` `_build_parser()` (`:47-128`): no flag that names a goal;
  - the caller contract: `scripts/build_orchestration/fast_lane.py`
    `resolve_connected_build_set()` (docstring `:162-200`) and `templates/agents/build-ac.md`
    (`:419-428`).

## Symptom

The goal was `ACD-2500`, "Every part of a requirement is written by whoever can actually get it
right". The id list started with `ACD-1600c-1`, an L2 from the `ACD-1600` tree: a cross-tree
prerequisite. The run wrote:

| Field | Written | Should name |
|---|---|---|
| epic folder | `EPIC-AnAcMissingFileTargetsOrATestContractIs` | the goal |
| Master_Plan `title` | `EPIC: An AC missing file targets or a test contract is flagged not implementation-ready` | `ACD-2500`'s title |
| Master_Plan `source_ac` | `ACD-1600c-1` | `ACD-2500` |

Reproduced on this branch. `_derive_epic_name()` on `ACD-1600c-1`'s title returns
`AnAcMissingFileTargetsOrATestContractIs`. The naive PascalCase name is 68 characters, the LLM
summariser returned `None`, and the result is the 40-character truncation.

## Mechanism

1. **`build_epic_from_ids()` has no goal id, so it uses the first id.** It sets
   `epic_name = _derive_epic_name(_get_ac_title(ids[0], store_root))` (`:229`). It then passes
   `ids[0]` to `_write_master_plan_safely()` as the goal AC id, which becomes `source_ac`, and
   `_get_ac_title(ids[0], ...)` as the goal title, which becomes `title` (`:272-273`). This is
   deliberate: the module's DECISION HISTORY entry of 2026-10-06 says
   "build_epic_from_ids() the first id's AC title".
2. **On the sanctioned path the first id is not arbitrary.** `/build-ac` passes the output of
   `resolve_connected_build_set()`. Its docstring promises dependency order: "a prerequisite leaf
   always appears before any leaf that (transitively) depends on it". So `ids[0]` is, by
   construction, a leaf with nothing in the set ahead of it, which means a foundational
   prerequisite. For a goal with cross-tree prerequisites it is an AC from a different tree. A
   goal above L2 (ACD-2500 is an L0) is not in the list at all, because the set holds only
   not-done L2/L3 leaves.
3. **The caller knows the goal and has no way to pass it.** The parser offers `--ac`, `--ids`,
   `--store-root`, `--inbox-dir`, `--dry-run`, `--yes` and `--approved-only`. There is no
   `--name` or `--goal`. (`--yes` and `--approved-only` have no effect in `--ids` mode either:
   `_run_ids_mode()` never receives them. The how-to documents that as "No readiness gate".)
4. **`--ac` does not have this defect.** `run()` names the epic from the goal id it was given
   (`epic_pipeline.py:111-112`) and records that id as `source_ac` (`:162`). The how-to describes
   only that behaviour ("The folder name is derived from the goal AC's `title` field",
   `docs/how-to/goal-to-epic.md:124`) and says nothing about naming in `--ids` mode.

## Detection

Compare a generated Master_Plan's `source_ac` with the goal the epic was built for. In an
`--ids` epic, a `source_ac` equal to the `01_` ticket's `source_ac` is this defect.

## Workaround

Rename the folder, correct `title` and `source_ac` in `Master_Plan.md` by hand, and repoint every
`implemented_by` entry at the renamed folder. That is what `32a542a6` did. Where the goal's leaf
set has no cross-tree prerequisites, `--ac <goal>` avoids the problem.

## Fix direction

- Give `--ids` a `--goal <ac_id>`, and `build_epic_from_ids()` a keyword-only `goal_ac_id`, and
  use it for the name, the title and `source_ac`. `/build-ac` already holds this id and should
  pass it.
- Without `--goal`, do not guess. Either refuse, or use a neutral name and record the id list as
  the provenance. Never let one member stand for the whole set.
- An `--epic-name` override, also asked for in `KI-ACD-011`, makes the naming survivable either
  way.
- Regression test: a two-id set whose first id belongs to another tree. Assert that the folder
  name, `title` and `source_ac` come from the goal.

## Secondary finding on the same path: the LLM summariser cannot succeed

A long title goes to `_summarise_title_via_llm()` (`scripts/ac_store/epic_naming.py:190`), which
pins `model="claude-3-5-haiku-latest"` (`:225`). Anthropic's model list records Claude Haiku 3.5
as retired on 2026-02-19. The current Haiku-tier id is `claude-haiku-4-5`. The function was added
on 2026-06-08, after the retirement, so in this repository the branch has probably never returned
a name. Two layers make it fall back:

- `anthropic` is not a declared dependency. `requirements-dev.txt` lists the runtime imports as
  pyyaml, jsonschema, referencing, docstring_parser and psutil. On a dev or CI machine the import
  fails and the function returns `None` without logging anything. Verified on Windows with
  Python 3.14: the call returned `None`.
- With the SDK installed, the request would fail on the retired model id. The function catches
  that, logs a WARNING and falls back.

The tests patch the function (`unit_tests/ac_store/test_concise_epic_name.py`), so nothing has
ever exercised the real call. In practice truncation is the only naming path, and its quality is
`KI-ACD-011`.

**Related.** `KI-ACD-011` (truncation ends on a dangling word: this run's name ends on `Is`).
`KI-ACD-010` (a bad name propagates into store fields). `KI-BO-014` (the two entry paths drift
apart; this is a third difference between them). `KI-ACD-20260914-0657` (Master_Plan frontmatter).

**Pattern:** an entry point that is handed a set and lets one member stand for all of it.
