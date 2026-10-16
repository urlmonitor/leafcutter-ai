---
title: "Reference: AC Examples and Required Runtime Inputs"
description: "An AC record example and the declared runtime-input schema, answer scope, and budget semantics."
type: reference
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - build_pipeline
related_docs:
  - docs/reference/ac-schema.md
  - config/ac_store_schema.json
---

# AC Examples and Required Runtime Inputs

> **Parent document:** [AC store schema](ac-schema.md)

### Full example

```yaml
id: FIN-001
title: "Merge main before running tests"
component: finalize
status: active
created: 2026-06-04
criteria: |
  Given a worktree branched from an older commit of main
  When the finalize-feature workflow begins
  Then it merges origin/main into the current branch before running any tests
  And it aborts with a clear error message if the merge produces a conflict
covered_by:
  - "unit_tests/test_finalize.py::test_merge_main_before_tests"
implemented_by:
  - "scripts/finalize.py#merge_main"
amended_by: []
origin_agent: business-analyst
```


## Required runtime inputs

An AC may add this optional declaration alongside its ordinary fields:

```yaml
required_inputs:
  - id: whitespace_policy
    question: How should internal whitespace runs be handled?
    choices:
      - collapse
      - preserve
```

Each item requires an `id` matching `^[A-Za-z][A-Za-z0-9_.-]{0,63}$` and a
nonblank `question`. Optional `choices` must be a nonempty list of unique,
nonblank strings. Other item properties, including values, sources and autofill,
are prohibited. The worker planner rejects duplicate IDs within one AC.

These are runtime human decisions, separate from unresolved requirements that
prevent feature admission. Answers are stored separately, bound to the declaring
AC, input ID and feature digest. Descendants may reuse the same ancestor input;
sibling declarations cannot borrow each other's answers. Changed scope requires
revalidation. The declaration itself never supplies an answer.

Missing declared inputs block before model dispatch. Read-only discovery uses
shared capacity and cumulative AC time, but only writable implementation consumes
one of the three implementation attempts. The deterministic input gate must be
satisfied before writable work begins.
