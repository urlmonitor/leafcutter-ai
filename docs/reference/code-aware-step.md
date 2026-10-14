---
title: "Reference: Code-Aware Test Design Step"
description: "Lookup reference for the code-aware test design step: the deterministic design pre-pass (CLI, report shape, state and scope rules, the same-type and same-area definitions, determinism and failure behaviour) that gives the code-aware agent its file facts."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/test-intent.md
  - docs/reference/requirement-rule-check.md
  - docs/reference/ac-declared-files.md
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-072-code-aware-test-designer-may-read-source.md
  - scripts/ac_store/design_prepass.py
  - scripts/ac_store/_rc_design_grounding.py
---

# Code-Aware Test Design Step

The code-aware step writes the test design (`test_spec`) for requirement records that carry `test_intent` (ADR-071); its agent may read source files (ADR-072). This page defines the parts of the step that scripts decide, so the agent never guesses them. Later sections are added by the tickets that build the other parts.

---

## Design pre-pass

`scripts/ac_store/design_prepass.py` prints the mechanical file facts of a batch. It never writes. Deployed to `<root>/scripts/ac_store/` (`RULE_CHECK_DEPLOY_MAP`).

```
python design_prepass.py --ids A,B,C [--store-root DIR] [--repo-root DIR] [--test-root unit_tests/]
```

| Flag | Meaning |
|---|---|
| `--ids` | Required. Comma-separated record ids. |
| `--store-root` | Default `<repo-root>/docs/acceptance-criteria`. |
| `--repo-root` | Default: nearest ancestor of the cwd holding `docs/acceptance-criteria`. |
| `--test-root` | Default: `testing_context.test_root` of the project's `skills_config.json`, else `unit_tests/`. |

### Report

stdout is exactly one JSON document; every path is repo-root-relative POSIX with no trailing slash on a directory.

```json
{"batch": ["ID"], "records": [{"id": "ID",
  "declared_files": [{"path": "p", "state": "exists | to_be_created | neither"}],
  "test_dirs": [{"path": "d", "exists": true}],
  "reference_files": [{"path": "r", "exists": true, "same_type": true, "same_area": true}]}]}
```

### Rules

| Part | Rule |
|---|---|
| Scope (`batch`, `records`) | An id whose record is a leaf (`level` L2 or L3) and has a non-empty `test_intent`, declared files, or `package_surface: true`. Any other id is skipped silently, so L0/L1 composites are harmless. |
| `declared_files[].state` | The tree wins: on disk is `exists`; else declared `to_be_created` is `to_be_created`; else `neither`. A path with `..` or an absolute form is `neither` and is never resolved outside the repo. A record with no declared files has `declared_files: []`, read as "not evaluated: no declared files". Read only through `declared_files.get_declared_files`. |
| `test_dirs` | The distinct `target_dir` values of the record's `test_spec`, plus `<test-root>/<name of the parent directory>` for each declared file (`scripts/ac_store/x.py` gives `unit_tests/ac_store`); sorted, each with `exists`. |
| `reference_files` | The record's `it_requirements.reference_file_path`, plus, only when `hold_reason` is `reference file pending`, up to 10 candidates: the files in the deliverable's directory with the deliverable's suffix, excluding the deliverable, sorted. |
| Deliverable | The first declared file with state `to_be_created`, else the first declared file. |
| **Same type** | The reference file has the same lower-cased suffix as the deliverable (`.py` and `.PY` match; `.py` and `.md` do not). |
| **Same area** | The reference file has the same parent directory as the deliverable. |

`same_type` and `same_area` are judged from the paths alone; `exists` is a separate fact, so a reference that is not on disk still reports both. The constants (`DEFAULT_TEST_ROOT`, `PENDING_MARKER`, `MAX_CANDIDATES`) sit at the top of the module.

### Determinism and failure

Two runs on the same batch and tree give byte-identical stdout: LF only, sorted keys, records sorted by id, lists sorted by path, no timestamps. Any error (an unknown id, an unreadable record, a bad flag) prints nothing on stdout, a message on stderr, and exits non-zero (`1` failure, `2` usage). The workflow treats "no report" as batch failure and does not dispatch the agent.

---

## See Also

- [test-intent.md](test-intent.md) - `test_intent`, the design fields and the legacy-design predicate.
- [requirement-rule-check.md](requirement-rule-check.md) - the `test design grounding` family that judges the written design.
- [ac-declared-files.md](ac-declared-files.md) - the declared-files seam the pre-pass reads.
