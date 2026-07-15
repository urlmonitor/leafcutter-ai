---
title: "Exclude submodule paths from glossary bootstrap scan"
status: done
components:
  - glossary
  - build_pipeline
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# 08: Exclude submodule paths from glossary bootstrap scan

## Actor / Goal

In order to get meaningful domain-term candidates from glossary bootstrap,
we need the scan to skip submodule directories so it doesn't flood results
with 609+ code identifiers (constants, function names) from vendored code.

## Context

`glossary_bootstrap` (via `glossary_bootstrap_helpers._enumerate_files()`)
currently walks the entire repo tree. When a project contains git submodules
(e.g. `leafcutter/` pointing at the leafcutter-ai package), the scanner
picks up every `.py`, `.md`, and `.sql` file inside, producing hundreds of
false-positive jargon candidates that are really just code symbols.

The fix should be `.gitmodules`-aware: parse `.gitmodules` at scan time and
exclude every listed submodule path. Additionally, a configurable
`exclude_paths` list in `skills_config.json` would let power users exclude
other directories (vendored deps, generated code, etc.).

## Acceptance Criteria

```gherkin
Given a repo with a .gitmodules file listing submodule path "leafcutter"
When glossary_bootstrap scans for jargon candidates
Then no files under leafcutter/ are included in the scan
And the candidate count drops from 609+ to only domain-relevant terms

Given a repo with no .gitmodules file
When glossary_bootstrap scans for jargon candidates
Then behaviour is unchanged (all .md/.py/.sql files scanned)

Given skills_config.json has glossary.exclude_paths = ["vendor/", "generated/"]
When glossary_bootstrap scans for jargon candidates
Then no files under vendor/ or generated/ are included
```

## Implementation Tasks

- [ ] Parse `.gitmodules` in `_enumerate_files()` to extract submodule paths
- [ ] Filter out any file whose path starts with a submodule directory
- [ ] Add `glossary.exclude_paths` key to `skills_config.default.json`
- [ ] Read `exclude_paths` from config and apply as additional exclusion filter
- [ ] Unit tests for submodule exclusion and configurable exclude_paths

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Purely additive filter logic; removing it restores original scan scope.
