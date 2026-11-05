---
title: "How to Add a Shared Workflow Block and Adopt It in a Route"
description: "Add a new shared block under templates/workflows-js/_shared/ and mark it in one route, then make another route start consuming an existing block such as COMMIT-ANSWER, installing and running the identity check each time."
type: how-to
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - build_orchestration
  - documentation_system
related_docs:
  - docs/reference/shared-blocks.md
  - docs/reference/shared-commit-step.md
  - docs/reference/workflow-authoring-contract.md
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-4-i.yaml
related_code:
  - scripts/build_shared_blocks.py
  - scripts/build_shared_validation.py
  - scripts/shared_block_identity.py
---

# How to Add a Shared Workflow Block and Adopt It in a Route

Write logic once under `templates/workflows-js/_shared/`, have the install copy it into the routes that mark a place for it, and prove every installed copy still equals its source. Two procedures follow: A adds a new block (`DEMO-ANSWER`) used by one existing route, B makes a route start consuming a block that already exists (`COMMIT-ANSWER`).

## Prerequisites

- A checkout of this package with `scripts/build.py` runnable (`python3 scripts/build.py --target-dir <dir>`).
- The marker rules in [Shared Blocks: Marker Convention](../reference/shared-blocks.md#marker-convention). The names below (`NAME-START` / `NAME-END`, source file `_shared/<name lowercased>.js`) are taken from there.
- Why the copy exists: workflow bodies cannot `require` ([ADR-030](../architecture/adrs/ADR-030-dual-engine-workflow-support.md)).
- A target directory for the install. For a rehearsal use an empty scratch directory, for example `/tmp/shared-block-try/target`.
- Every path below is relative to the package root. Run each command with absolute paths.

## Steps

### Procedure A: add DEMO-ANSWER, used by one existing route

#### Step 1 — Create the block source

Create `templates/workflows-js/_shared/demo-answer.js`. The file name is the block name lowercased. The source must not be empty ([empty source](../reference/shared-block-install-failures.md#empty-source)). A `{{config.<key>}}` placeholder in it is resolved at install ([unresolvable placeholder](../reference/shared-block-install-failures.md#unresolved-config-placeholder)).

```javascript
// SINGLE SOURCE of the demo answer rule. The install copies this text between the DEMO-ANSWER
// marker lines of each consuming workflow. Never edit a copy in a workflow.
function demoAnswer(reply) {
  return { accepted: reply !== undefined, output_root: "{{config.output_root}}" };
}
```

Names declared in the block become top-level names of every route that takes it, so pick names no consuming route already declares.

#### Step 2 — Mark an empty place in the route template

In the route template, for example `templates/workflows-js/quick-fix.js`, add the two marker lines on consecutive lines where the block text should land, with nothing between them ([text between markers](../reference/shared-block-install-failures.md#text-between-markers)).

```javascript
// DEMO-ANSWER-START
// DEMO-ANSWER-END
```

Only top-level `*.js` files in `templates/workflows-js/` are routes. The name must match a source, or the install refuses ([unknown block name](../reference/shared-block-install-failures.md#unknown-block-name)).

#### Step 3 — Declare the block awaiting adoption only if no route marks it in this change

Skip this step when Step 2 lands in the same change as Step 1: a block that a route uses needs no declaration, and a declaration for it is stale ([stale declaration](../reference/shared-block-install-failures.md#stale-awaiting-adoption-declaration)).

When you land the source before any route marks it, add the block to `templates/workflows-js/_shared/awaiting-adoption.json`, mapping the name to a non-empty list of the records that will adopt it. Without it the install refuses ([unused source](../reference/shared-block-install-failures.md#unused-source)).

```json
{
  "DEMO-ANSWER": ["DEMO-1"]
}
```

Keep the other keys already in the file.

#### Step 4 — Install the package

```bash
python3 scripts/build.py --target-dir <target-dir>
```

The install checks every route and source in one pass and installs nothing if any problem is found. Each failure message is described, with its fix, in [Install Failures](../reference/shared-block-install-failures.md#install-failures).

#### Step 5 — Run the identity check

`check_identity` in `scripts/shared_block_identity.py` has no command line. Two documented ways to run it:

- **The suite's check.** `unit_tests/scripts/test_bo4500b_2_deployed_layout.py` runs it against the shared deployed layout (one package build for the whole run, as the repo's test rules require):

  ```bash
  python3 -m pytest unit_tests/scripts/test_bo4500b_2_deployed_layout.py -q
  ```

- **Against the install you just made.** Save this script outside the package, for example as `/tmp/shared-block-try/check_identity_cli.py`. It builds the config the way the test does and prints the check's report:

  ```python
  """Usage: python3 check_identity_cli.py <package_root> <target_dir>"""

  import sys
  from pathlib import Path

  package_root = Path(sys.argv[1]).resolve()
  target = Path(sys.argv[2]).resolve()
  sys.path.insert(0, str(package_root / "scripts"))

  import build
  from shared_block_identity import check_identity

  config = build.load_config(None, target)
  build._inject_file_size_limits(config, package_root)
  build._inject_changelogs_dir(config, package_root)
  result = check_identity(target / ".leafcutter", package_root, config)
  print(result["message"])
  print("passed:", result["passed"], "inspected_total:", result["inspected_total"])
  sys.exit(0 if result["passed"] else 1)
  ```

  ```bash
  python3 /tmp/shared-block-try/check_identity_cli.py <package-root> <target-dir>
  ```

The output wording is in [Identity Check](../reference/shared-blocks.md#identity-check).

### Procedure B: make a route start consuming COMMIT-ANSWER

#### Step 1 — Mark the empty place in the route

In the route template that should take the block, for example `templates/workflows-js/plan-feature.js`, add an empty pair where the block text should land. `build-feature.js` and `build-ticket.js` never take this block ([Routes](../reference/shared-blocks.md#routes)).

```javascript
// COMMIT-ANSWER-START
// COMMIT-ANSWER-END
```

How the route calls the block is the [COMMIT-ANSWER contract](../reference/shared-blocks.md#commit-answer-contract).

#### Step 2 — Remove COMMIT-ANSWER's whole awaiting-adoption entry in the same change

A declaration is stale as soon as any route marks the block, not when the last listed adopter does. In the change that lands the first adopting route, delete the whole `COMMIT-ANSWER` key from `templates/workflows-js/_shared/awaiting-adoption.json`, including records of other adopters that have not landed yet. The other keys stay. If no key remains the file holds `{}`.

Leaving the entry fails the install ([stale declaration](../reference/shared-block-install-failures.md#stale-awaiting-adoption-declaration)). Update the Routes table in `docs/reference/shared-blocks.md` in the same change.

#### Step 3 — Reinstall

```bash
python3 scripts/build.py --target-dir <target-dir>
```

Failures are listed in [Install Failures](../reference/shared-block-install-failures.md#install-failures).

#### Step 4 — Run the identity check

Use either way from Procedure A, Step 5.

## Verification

Run the identity check (Procedure A, Step 5). A passing run prints one line per block, naming its copies, and the script ends with `passed: True`. After Procedure A the report contains:

```text
DEMO-ANSWER: 1 copies inspected (workflows/quick-fix.js)
```

After Procedure B it also contains:

```text
COMMIT-ANSWER: 1 copies inspected (workflows/plan-feature.js)
```

A block that is still declared awaiting adoption is reported as `not inspected because it awaits adoption` and does not fail. Lines for hand-kept pairs (`not checked: hand-kept (declared)`) are normal. For a failing run see [Troubleshooting](#troubleshooting).

## Troubleshooting

1. **The install prints `N shared-block problem(s) found; no workflow route was installed`.** Each following line is one problem. Find it in [Install Failures](../reference/shared-block-install-failures.md#install-failures), apply the fix, rerun the install. Nothing was installed, so there is nothing to undo.
2. **The check prints `block ... differs from its source at line N`.** An installed copy was edited by hand, or the install is older than the source. Reinstall; do not edit inside an installed pair ([Identity Check](../reference/shared-blocks.md#identity-check)).
3. **The check prints `zero installed copies were inspected`.** The layout root has no installed route with a marker pair. Confirm the `<target-dir>` is the one the install wrote, with a `.leafcutter/workflows` folder inside it.
4. **The check prints `block ... has no installed copy`.** A source exists, no installed route uses it, and it is not declared awaiting adoption. Do Step 2 of Procedure A, or declare the block (Step 3), then reinstall.

## See Also

- [Shared Blocks](../reference/shared-blocks.md): marker convention, the identity check, the COMMIT-ANSWER contract.
- [Install Failures](../reference/shared-block-install-failures.md): every install failure and its fix.
- [Shared Commit Step](../reference/shared-commit-step.md): the commit step's own answer contract.
- [Workflow Authoring Contract](../reference/workflow-authoring-contract.md): why shared logic is copied at build time.
- `templates/workflows-js/_shared/README.md`: the index of block sources.
- [Documentation Index](../INDEX.md)
