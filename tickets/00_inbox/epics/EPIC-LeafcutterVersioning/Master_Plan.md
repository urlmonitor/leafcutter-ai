---
title: "EPIC: LeafcutterVersioning — SemVer, Breaking-Change Discipline, and Release Automation for leafcutter"
type: epic
status: todo
components:
  - documentation_system
  - infrastructure
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
---

# EPIC: LeafcutterVersioning

Introduce automated SemVer versioning, a breaking-change signal in per-file changelog entries, and a release script so that every release of `leafcutter` is tagged deterministically — no human judgement at release time. Phase 2 adds consumer-side robustness (build-time halt-guard and a schema-diff CI gate that closes the "silent omission" gap mechanically).

## Context

`leafcutter` has been extracted from `bybit-trader` and published as the `leafcutter-ai` package on its own upstream git repo. This epic implements the versioning infrastructure for that extracted package.

- **Sub-tickets 01, 04** modify files already under `leafcutter/` and can be executed in the bybit-trader worktree using the `leafcutter/` submodule path.
- **Sub-tickets 02, 03, 05** presuppose the upstream repo exists (CI workflows, release tags). They should be started only after extraction is confirmed, or treated as stubs that get wired to CI at extraction time.

If further extraction work is needed before this epic enters `01_todo/`, add the relevant ticket filename to `depends_on` on sub-tickets 02, 03, and 05.

## Decided Design (Locked — Do Not Re-Debate)

### Versioning

Automated SemVer, derived at release time by scanning per-file changelog entries since the last `v*` tag:

- Any entry with `breaking: true` → bump MAJOR
- Any entry with `type: feature` (and no `breaking: true`) → bump MINOR
- Otherwise → bump PATCH

A release script (`leafcutter/scripts/release/compute_next_version.py`) does the scan and stamps the tag — zero human judgement.

### Breaking-Change Signal

Two new fields on per-file changelog entry frontmatter:

- `breaking: true|false` — the mandatory bump trigger; defaults to `false` when absent.
- `migration_steps: list[str]` — required non-empty when `breaking: true`.

`emit_entry.py` validates on write: rejects `breaking: true` without at least one `migration_steps` entry.

## Residual Risk: Silent Omission

All three brainstorm perspectives flagged this: a developer who introduces a genuinely breaking change but simply does not set `breaking: true` will produce an incorrect MINOR or PATCH bump. The Phase 1 mitigation (`emit_entry.py` validation) catches *malformed* entries that *declare* `breaking: true`; it does not catch silent omission.

**Full mitigation requires Phase 2 sub-ticket 05** (schema-diff CI gate). Until that gate lands, release quality depends on author discipline. The residual risk is accepted for Phase 1.

## Locked Design Decisions

1. **`v*` tag convention** — release script scans for `v*` tags (e.g. `v1.2.3`); `deploy-*` tags are the bybit-trader deployment convention and are distinct.
2. **`breaking` defaults to `false` when absent** — `emit_entry.py` accepts entries without the field; only entries that explicitly set `breaking: true` are scrutinised for `migration_steps`.
3. **Changelog entries live in `changelogs/`** — the directory resolved by `_load_changelogs_dir()` in `emit_entry.py`; the release script uses the same resolution.
4. **Release script is invokable manually and from CI** — no magic environment dependencies beyond git and Python stdlib.
5. **Phase 2 halt-guard uses a `.leafcutter.lock` file** — written by `build.py` after each successful build, records the package SHA at build time. The guard reads this to know "since which commit should I scan changelog entries?"
6. **Max nesting depth: 3.** Sub-tickets in this epic are depth-2. No further epic fanout.

## Sub-Tickets

### Phase 1 — Core Versioning (do these before declaring versioning "live")

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_frontmatter_schema_extension.md](./01_frontmatter_schema_extension.md) | Extend `emit_entry.py` with `breaking` + `migration_steps` fields; cross-validation; update changelog skill docs | `[ ]` |
| 02 | [02_release_script.md](./02_release_script.md) | New `scripts/release/compute_next_version.py`; scans changelog entries since last `v*` tag; computes and stamps next SemVer | `[ ]` |
| 03 | [03_ci_workflow.md](./03_ci_workflow.md) | GitHub Actions workflow that invokes the release script on push-to-main; opens release PR or pushes tag | `[ ]` |

### Phase 2 — Consumer Robustness (deferred; do not block Phase 1)

| # | File | Description | Status |
|---|------|-------------|--------|
| 04 | [04_build_halt_guard.md](./04_build_halt_guard.md) | `build.py` halt-guard: reads `breaking: true` entries since consumer's pinned SHA; halts with migration notice + `--force` escape hatch | `[ ]` |
| 05 | [05_schema_diff_ci_gate.md](./05_schema_diff_ci_gate.md) | Pre-commit / CI check comparing `skills_config.schema.json` against previous tag; fails on backwards-incompatible change without `breaking: true` entry | `[ ]` |

## Dependency Graph

```
01 (frontmatter schema + emit_entry validation)
└── 02 (release script — reads changelog entries produced by 01's schema)
    └── 03 (CI workflow — invokes release script from 02)

01 (frontmatter schema — breaking field)
└── 04 (build halt-guard — reads breaking entries) [Phase 2]

01 (frontmatter schema) + 02 (release script / tag convention)
└── 05 (schema-diff CI gate — compares against v* tags) [Phase 2]
```

Phase 1 tickets are strictly sequential: 01 → 02 → 03.
Phase 2 tickets are independent of each other but both depend on 01.
Phase 2 does NOT block Phase 1.

## Success Criteria

- `emit_entry.py` rejects any payload with `breaking: true` and an empty or absent `migration_steps`; accepts `breaking: false` and entries that omit the field entirely.
- `compute_next_version.py` scans `changelogs/` since the last `v*` tag, prints the computed next version, and (with `--tag`) stamps a `vX.Y.Z` git tag.
- A GitHub Actions workflow triggers on push-to-main, runs `compute_next_version.py`, and either opens a release PR or pushes the version tag — no manual intervention required.
- **(Phase 2)** `build.py` halts with a structured migration notice when the package has `breaking: true` entries since the consumer's pinned SHA; `--force` overrides the halt.
- **(Phase 2)** A pre-commit or CI check fails when `skills_config.schema.json` has a backwards-incompatible change (removed key, new required key, type narrowing) without a matching `breaking: true` changelog entry.

## Decision History

- **2026-05-19**: Epic opened by create-ticket under name EPIC-PortableWorkflowVersioning. Design is fully decided (3-perspective brainstorm consensus). Five sub-tickets across schema, release tooling, CI, build-guard, and validation gate. Phase 1 (01–03) targets the package's first versioned release; Phase 2 (04–05) targets consumer robustness.
- **2026-05-19**: Renamed from EPIC-PortableWorkflowVersioning to EPIC-LeafcutterVersioning by EPIC-LeafcutterPostMVP ticket 04. The `leafcutter` package has been extracted and published as `leafcutter-ai`; all `leafcutter` path references updated to `leafcutter/`.
