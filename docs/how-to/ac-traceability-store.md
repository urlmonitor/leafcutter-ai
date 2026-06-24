---
title: "How to use the AC Traceability Store"
description: "Step-by-step guide for creating, amending, deprecating, and tracing acceptance criteria through the AC Traceability Store and knowledge map."
type: how-to
status: active
created: 2026-06-04
last_updated: 2026-06-22
components:
  - build_pipeline
  - knowledge-management
related_docs:
  - docs/reference/ac-schema.md
  - docs/acceptance-criteria/README.md
  - config/ac_store_schema.json
  - templates/skills/knowledge-query/SKILL.md
---

# How to use the AC Traceability Store

This guide covers the six most common operations on the AC Traceability
Store: creating a new acceptance criterion, amending an existing one,
deprecating one, adding `covers:` tags to existing tests, handling
a deprecated-AC test failure at triage time, and tracing a requirement
to its implementing code and test files via the knowledge map.

After completing this guide you will be able to manage the full lifecycle
of an AC without reading any agent template or skill file.

---

## Prerequisites

- `build.py` has been run at least once; `docs/acceptance-criteria/` exists.
- `check_ac_schema.py` is installed as a pre-commit hook (verify with
  `pre-commit run check-ac-schema --all-files`).
- You have a text editor and `git` available.

---

## How do I create a new AC?

### Step 1: Choose (or create) a component namespace

Open `docs/acceptance-criteria/index.yaml`. Find the component whose ACs
you are adding. If no entry exists for your component, add one:

```yaml
components:
  - id: my-component          # kebab-case, unique
    prefix: MYC               # 2–6 ALL-CAPS letters; used in file names
    description: "ACs for the my-component subsystem"
    owner: null               # or a team/agent identifier
```

### Step 2: Assign the next sequence number

List the files in the component directory:

```bash
ls docs/acceptance-criteria/my-component/
```

The next file name is `MYC-NNN.yaml` where `NNN` is the highest existing
number plus one, zero-padded to three digits (e.g. `MYC-003.yaml` when
`MYC-001.yaml` and `MYC-002.yaml` already exist, or `MYC-001.yaml` for a
new namespace).

### Step 3: Write the AC YAML file

Create `docs/acceptance-criteria/my-component/MYC-001.yaml`:

```yaml
id: MYC-001
title: "One-line human-readable description of this criterion"
component: my-component
status: active
created_by: "tickets/00_inbox/my-ticket.md"  # relative path to the originating ticket
criteria: |
  Given <precondition>
  When <action>
  Then <expected outcome>
  And <additional outcome if needed>
covered_by: []        # fill in after tests are written
implemented_by: []    # fill in after implementation is done
amended_by: []        # leave empty at creation
origin_agent: human   # or business-analyst, debug, ticket-wiring
```

All fields except `superseded_by` are required. Leave `covered_by` and
`implemented_by` as empty lists if tests or code do not yet exist.

### Step 4: Validate the file

Run the schema validator before committing:

```bash
python .leafcutter/scripts/commit_guardian/check_ac_schema.py docs/acceptance-criteria/my-component/MYC-001.yaml
```

Expected output when valid:

```
check_ac_schema: 1 file checked, 0 errors.
```

If errors are printed, fix the YAML fields and re-run until the check exits 0.

### Step 5: Reference the AC from a ticket

In the ticket that introduces this AC, add a reference to the file path in
the `## Agent Contracts` section or in the ticket's context prose. Agents
that read the ticket will discover the AC path and load it automatically.

---

## How do I amend an existing AC?

An amendment changes the `criteria:` text or corrects a field on an AC
that already exists. The AC ID does not change.

### Step 1: Edit the AC YAML file directly

Open `docs/acceptance-criteria/<component>/<ID>.yaml` in your editor.
Apply your changes to the `criteria:` field or any other mutable field
(e.g. `covered_by`, `implemented_by`, `title`).

### Step 2: Record the amending ticket

Add the path of the ticket that authorised the change to the `amended_by`
list:

```yaml
amended_by:
  - "tickets/00_inbox/my-amendment-ticket.md"
```

### Step 3: Validate and commit

```bash
python .leafcutter/scripts/commit_guardian/check_ac_schema.py docs/acceptance-criteria/<component>/<ID>.yaml
git add docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "amend <ID>: <one-line summary of the change>"
```

---

## How do I deprecate an AC?

Deprecated ACs are retained for audit purposes. Set `status: deprecated`
and do not delete the file.

### Step 1: Update the status field

```yaml
status: deprecated
```

If this AC is superseded by a newer one, also set:

```yaml
status: superseded_by
superseded_by: MYC-003    # ID of the replacement AC
```

### Step 2: Validate and commit

```bash
python .leafcutter/scripts/commit_guardian/check_ac_schema.py docs/acceptance-criteria/<component>/<ID>.yaml
git add docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "deprecate <ID>: <reason>"
```

After deprecation, the `check_ac_coverage.py` hook will no longer require
`covered_by` entries for this AC.

---

## How do I add `covers:` tags to existing tests?

The `check_test_ac_tags.py` hook requires each `def test_*` function to
carry a `# covers: XX-NNN` comment linking it to an AC.

### Step 1: Identify which AC the test verifies

Read the test body and match its assertions to an AC in
`docs/acceptance-criteria/`. Note the AC ID (e.g. `MYC-002`).

### Step 2: Add the tag to the test function

Add a `# covers: XX-NNN` comment directly above the `def test_*` line,
or as the first statement inside the function body, or in the function
docstring:

```python
# covers: MYC-002
def test_my_feature():
    """Verifies MYC-002: system rejects invalid input."""
    assert my_function(None) is False
```

All three placements are valid. The hook accepts the first one it finds.

### Step 3: Update the AC YAML file

Add the test file path (with optional `::test_function` suffix) to the
`covered_by` list in the AC YAML file:

```yaml
covered_by:
  - "unit_tests/test_my_feature.py::test_my_feature"
```

### Step 4: Validate and commit

```bash
python .leafcutter/scripts/commit_guardian/check_test_ac_tags.py unit_tests/test_my_feature.py
python .leafcutter/scripts/commit_guardian/check_ac_schema.py docs/acceptance-criteria/<component>/<ID>.yaml
git add unit_tests/test_my_feature.py docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "tag test_my_feature with covers: MYC-002"
```

---

## What happens when a test fails triage because its AC is deprecated?

When `check_test_ac_tags.py` runs in error mode and finds a `# covers:` tag
pointing to a deprecated AC, the hook emits a warning. The test is not
automatically removed — you must decide whether to re-tag it or remove it.

### Option A: Re-tag the test to the superseding AC

If the deprecated AC was superseded by `MYC-003`, change the tag:

```python
# covers: MYC-003
def test_my_feature():
    ...
```

Update `covered_by` in `MYC-003.yaml` to include this test, then remove the
path from `MYC-002.yaml` (or leave it — stale entries in `covered_by` are
not validated by the schema, only the forward link matters).

### Option B: Remove the test if the behaviour it tested no longer exists

If the deprecation reflects a removed feature, delete or skip the test:

```python
import pytest

@pytest.mark.skip(reason="MYC-002 deprecated — feature removed in ticket/...")
def test_my_feature():
    ...
```

Then commit with a note referencing the deprecating ticket.

---

## How do I find the code and tests that fulfil a given acceptance criterion?

Each AC YAML file records two key links once a ticket is built:

| Field | What it points to |
|-------|------------------|
| `implemented_by` | The source file (or file + symbol) that delivers the criterion |
| `covered_by` | The test file (and optional `::function` suffix) that proves it |

The knowledge map exposes these as edges. The procedure below walks you from an AC ID to its code and test files in three steps.

### Step 1: Query the knowledge map for one acceptance criterion

Run `knowledge_query.py` with the title keyword or component prefix of the AC you want to trace. The `--surface acs` flag restricts output to the AC store so the result is focused.

```bash
python scripts/knowledge_query.py --query "Sparse AC parents" --surface acs
```

Replace `"Sparse AC parents"` with any word from the AC's `title` field. You can also use part of the AC ID (e.g. `ACS-100c-2`) if you know it exactly — use a few distinctive words from the title rather than the bare ID, because `--query` matches against the title and description fields, not the id field.

Expected output:

```
# Knowledge Index
Surfaces: 1   Nodes: 1   Edges: 4

## acs (1)
  [acs] ACS-100c-2 — (no description)
    -> implemented_by: scripts/commit_guardian/check_ac_limits.py#_check_limits
    -> covered_by: unit_tests/commit_guardian/test_check_ac_limits.py::TestCheckLimitsSparseAdvisory
    -> covered_by: unit_tests/commit_guardian/test_check_ac_limits.py::TestCheckAcLimitsCLI::test_sparse_advisory_exits_zero
    -> depends_on: ACS-100c
```

If zero nodes are returned, broaden the keyword or drop `--surface acs` to search across all surfaces.

### Step 2: Read the result

Each `->` line is an outbound edge from the AC node. The two edge types you need are:

**`-> implemented_by: <path>`**
This is the source file that delivers the criterion. The path may include a `#symbol` suffix pointing to the specific function or class responsible. Open this file and navigate to the symbol to see the implementation.

Example: `-> implemented_by: scripts/commit_guardian/check_ac_limits.py#_check_limits`
means the `_check_limits` function inside `scripts/commit_guardian/check_ac_limits.py` delivers this criterion.

**`-> covered_by: <path>::<test>`**
This is the test file (and optional `::TestClass::test_function` suffix) that proves the criterion. Run the indicated test to verify the criterion is satisfied.

Example: `-> covered_by: unit_tests/commit_guardian/test_check_ac_limits.py::TestCheckLimitsSparseAdvisory`
means the `TestCheckLimitsSparseAdvisory` test class inside `unit_tests/commit_guardian/test_check_ac_limits.py` covers this criterion.

If either list is empty, the AC has not yet been implemented or tested. Check the AC YAML file directly:

```bash
grep -r "id: <AC-ID>" docs/acceptance-criteria/ -l
```

then open the file to see its current `work_status` and `readiness` fields.

### Step 3: Open the visualization and locate the criterion

The visualization renders every AC node and its edges as an interactive force-directed graph in the browser.

Generate and open the graph:

```bash
python scripts/visualise_knowledge_graph.py
```

To write the file without opening the browser automatically:

```bash
python scripts/visualise_knowledge_graph.py --no-open
```

The HTML file is written to `/tmp/leafcutter_knowledge_graph.html` by default. Open it in any browser.

To focus on the AC store only and reduce visual noise:

```bash
python scripts/visualise_knowledge_graph.py --surface acs
```

Once the graph is open:

1. Use the browser's **Ctrl+F** search if the graph renders a search box, or zoom and pan to the `acs` cluster.
2. Hover over a node labelled with the AC ID (e.g. `ACS-100c-2`) to highlight its direct edges.
3. The `implemented_by` edge leads to a node representing the source file. The `covered_by` edge leads to nodes representing test files.
4. Click a node to fix it in place and read the tooltip showing the full edge targets.

The same information shown in the CLI output (Step 1) is visible here as graph edges. Use whichever representation is easier for the task at hand.

---

## Verification

After each operation, confirm the pre-commit hooks exit cleanly:

```bash
pre-commit run check-ac-schema --all-files
pre-commit run check-test-ac-tags --all-files
pre-commit run check-ac-coverage --all-files
```

All three commands should exit 0 with no error output.

---

## See Also

- `docs/reference/ac-schema.md` — complete field-by-field reference for the AC YAML schema.
- `docs/acceptance-criteria/README.md` — directory structure and quick-start.
- `config/ac_store_schema.json` — machine-readable JSON Schema (draft-07).
- `docs/README.md` — full documentation index.
- `templates/skills/knowledge-query/SKILL.md` — full reference for all `knowledge_query.py` flags and output modes.
