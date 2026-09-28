---
title: "KI-BP-20260928-closure-guard-reads-comparison-literals-as-file-reads — the intra-package closure guard treats any dir/file.ext string literal as a data-file read, even when the script only compares paths against it"
description: "low — build_referential_integrity_closure.py (BP-900g-8-ii) flags every standalone string literal shaped like dir/file.ext that resolves to a real file as a data-file dependency needing a deploy mapping, whether or not the script ever opens it. A hook that only uses such a literal to decide whether a staged path is in scope fails the build with a false 'missing deploy mapping'. There is no sanctioned way to mark a literal as a pattern, so authors restructure the literal to get past it."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/acceptance-criteria/guardrail-engine/GE-113-artifacts-cant-land-in-the-wrong-place/GE-113c-1-vi.yaml
---

# KI-BP-20260928-closure-guard-reads-comparison-literals-as-file-reads — comparison literals are read as file dependencies

- **Severity:** low. It fails closed, blocking a valid build, and never lets a real missing
  mapping through. But it pushes authors to disguise ordinary path literals, which makes code
  harder to read and hides real dependencies from the guard.
- **Status:** open, no AC.
- **Where:** `scripts/build_referential_integrity_closure.py`,
  `_extract_data_file_literal_candidates` (the BP-900g-8-ii closure guard), consumed by
  `build.py` as a hard `[CLOSURE GUARD]` failure.

## Symptom

While building GE-113c-1-vi (2026-09-28), `check_agent_registry.py` gained a scope test that
compares staged paths against `"config/agent_registry.json"` and
`"config/agent_registry.schema.json"`. The hook never opens either file; the registry
validator does, from a runtime `package_root`. The build still aborted with a missing deploy
mapping for `config/agent_registry.json`, which broke `test_ge_122a_1.py`, because that test
runs `build.py` as a subprocess.

## Cause

The guard treats a standalone string literal as a data-file read when two things are true:
it matches a `dir/file.ext` shape, and it resolves to a real file on disk. It doesn't
distinguish a literal passed to `open()` or `read_text()` from one used in `==`, `in`,
`startswith` or tuple membership. The only exclusion is a blanket `templates/` prefix skip.
There is no pragma, allow-list or comment marker.

## Workaround

Build the path from segments, e.g. `("config", "agent_registry.json")`, compare it with
`parts[-2:]`, and join it with `Path.joinpath(*parts)` only for display. GE-113c-1-vi does
this and documents why in its ARCHITECTURE docstring and DECISION HISTORY.

## Suggested fix

Give the guard a way to tell a comparison or pattern literal from a read:
- only count literals that reach a read call such as `open`, `read_text`, `read_bytes`,
  `json.load` or `Path(...)` followed by a read; or
- honour an explicit marker, such as a trailing `# closure: pattern` comment or a
  module-level allow-list.

Either way, keep failing closed on real reads.
