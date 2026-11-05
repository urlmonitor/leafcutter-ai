---
title: "Reference: Produced-Tests Assertion Kinds, Test-Designer Family"
description: "Lookup for the five test-designer assertion kinds of the produced-tests eval, which read the requirement record the designer edits: schema validity, the bug-fix or gate judgement, the wrong-version names and the written design."
type: reference
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
  - documentation_system
related_docs:
  - docs/reference/produced-tests-eval-assertion-kinds.md
  - docs/reference/wrong-version-runs.md
  - scripts/evals/README.md
---

# Produced-Tests Assertion Kinds, Test-Designer Family

Lets a reader look up the five assertion kinds registered in `scripts/evals/designer_eval/kinds.py`. The test-designer writes no test file, so every kind reads the requirement record the designer edited in the row's sandbox. What a kind is and how the family pages fit together is on the [hub](produced-tests-eval-assertion-kinds.md).

## Kinds

| Kind | Reads | Used by |
|---|---|---|
| `designer_record_schema_valid` | edited requirement record | test-designer set |
| `designer_states_judgement` | edited requirement record | test-designer set |
| `designer_names_wrong_versions` | edited requirement record | test-designer set |
| `designer_states_neither` | edited requirement record | test-designer set |
| `designer_design_written` | edited requirement record | test-designer set |

Every kind takes the spec keys `record` (an AC id) and `store` (the sandbox-relative store directory) and reads `<sandbox>/<store>/<record>.yaml`. A missing, unparseable, empty or non-mapping record fails the kind with a detail naming the record.

## Entries

### `designer_record_schema_valid`

**Used by:** the test-designer set, rows `bug-fix`, `gate` and `new-behaviour`.

**Reads:** the edited record, then runs `scripts/ac_store/validate_ac_schema.py` on it with the sandbox as working directory.

**Passes when:** the record loads and the validator exits 0.

**Fails when:** the record cannot be loaded (the validator is then not run), the validator cannot run, or it exits non-zero; the detail quotes its first lines.

**Passing example:** record `TDE-9701` as the designer left it passes ("TDE-9701 passes validate_ac_schema.py").

**Failing example:** the same record with an extra key `invented_key: 1` on a test entry fails, with the validator naming the undeclared key.

**Template sentence:**

> Add no new key; the allowed test_spec item keys stay the closed set.

- templates/agents/test-designer.md

### `designer_states_judgement`

**Used by:** the test-designer set, rows `bug-fix` and `gate`.

**Reads:** the `test_spec` entries of the edited record.

**Passes when:** at least one entry carries a `must_catch` list with a non-blank string, or has `angle` `discrimination`. Either one is the declaration of a bug-fix or gate clause.

**Fails when:** no entry carries either; the detail reads "the design states neither a bug fix nor a gate".

**Passing example:** record `TDE-9701` has the entry `test_bug_fix_guard` with `angle: discrimination` and a `must_catch` list; the kind passes ("1 test entry(ies) state a bug fix or gate").

**Failing example:** the same record with that entry changed to `angle: criterion` and its `must_catch` removed fails.

**Template sentence:**

> an entry carries `must_catch` or angle `discrimination` only when the clause is a bug-fix or gate clause, and that presence is the declaration.

- templates/agents/test-designer.md

### `designer_names_wrong_versions`

**Used by:** the test-designer set, rows `bug-fix` and `gate`.

**Reads:** the `must_catch` names of each `test_spec` entry. Spec keys: `exact` (names matched with the wrong-version runner's own key, so "revert the fix" and "the fix undone" are one name), `tokens` (each must appear as contiguous words in its own distinct non-exact name; `-`, `_` and spaces all separate words) and `variants` (other word sequences that count for a token).

**Passes when:** one single entry names every `exact` name and gives every token a name of its own.

**Fails when:** no entry names them all; the detail lists what the closest entry still lacks.

**Passing example:** row `bug-fix` has `exact` `["revert the fix"]` and token `retry_due`; the entry with `must_catch` `["revert the fix", "drop the retry_due condition"]` passes.

**Failing example:** the same entry with `"drop the window condition"` in place of the second name fails: "still missing: 'retry_due'".

**Template sentence:**

> The strings "revert the fix" (the runner also accepts "the fix undone") and "the gate always allows" are exact

- templates/agents/test-designer.md

### `designer_states_neither`

**Used by:** the trap row `new-behaviour` of the test-designer set.

**Reads:** the `test_spec` entries of the edited record.

**Passes when:** no entry carries a non-blank `must_catch` name and none has `angle` `discrimination`.

**Fails when:** either is present; the detail says the design "states neither a bug fix nor a gate, yet a test entry carries" it.

**Passing example:** record `TDE-9703`, whose entries are `criterion` and `reachability` with no `must_catch`, passes.

**Failing example:** the same record with its first entry changed to `angle: discrimination` fails.

**Template sentence:**

> New behaviour with no earlier version: write no `must_catch` and no `discrimination` entry.

- templates/agents/test-designer.md

### `designer_design_written`

**Used by:** the test-designer set, rows `bug-fix`, `gate` and `new-behaviour`.

**Reads:** the fields `test_spec`, `test_design_authorship` and `test_design_opened_files` of the edited record.

**Passes when:** `test_spec` holds at least one mapping entry, `test_design_authorship` is a mapping whose `step` is `test-designer`, and `test_design_opened_files` is a non-empty list.

**Fails when:** any of the three is missing or empty; the detail lists them.

**Passing example:** record `TDE-9701` with all three fields written passes.

**Failing example:** the same record with `step: planner` fails: "test_design_authorship missing or empty".

**Template sentence:**

> Group 1 is the test design: `test_spec`, `test_design_authorship` and `test_design_opened_files`.

- templates/agents/test-designer.md

## See Also

- [Produced-tests assertion kinds (hub)](produced-tests-eval-assertion-kinds.md) - what a kind is and the other family pages.
- [Wrong-version runs](wrong-version-runs.md) - the runner whose name key `designer_names_wrong_versions` reuses.
- `scripts/evals/designer_eval/kinds.py` - the five kinds.
- `scripts/evals/designer_eval/dispatch.py` - the live input of a designer row.
