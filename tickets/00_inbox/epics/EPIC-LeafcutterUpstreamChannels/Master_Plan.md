---
title: "EPIC: LeafcutterUpstreamChannels — set up community feedback channels on leafcutter-ai GitHub repo"
type: epic
status: todo
components:
  - documentation_system
  - infrastructure
created: 2026-05-19
depends_on: []
priority: low
requires_diagram: false
requires_adr: false
---

# EPIC: LeafcutterUpstreamChannels

Set up community feedback channels on the upstream `urlmonitor/leafcutter-ai` GitHub repo by authoring GitHub Issue templates, Discussion templates, CODEOWNERS, CONTRIBUTING.md, and a README feedback section so external consumers of the `leafcutter-ai` submodule can report bugs, propose features, and submit PRs through standard GitHub conventions.

## Context

**Prerequisite**: `EPIC-LeafcutterMVP` ST-3 must have published `github.com/urlmonitor/leafcutter-ai`. This epic has no dependency on `EPIC-LeafcutterPostMVP` sub-tickets 01–04 (it works against the upstream repo independently).

This epic was extracted from `EPIC-LeafcutterPostMVP` original sub-ticket 05. All file changes target the `leafcutter-ai` upstream repo (accessed via the submodule or a separate clone). They are NOT changes to the consumer project itself.

Once `EPIC-LeafcutterPostMVP` ST-2 (submodule replacement) is complete, edits to files inside `leafcutter/` in the consumer project must go through a fork + PR against the upstream — not direct edits in the consumer project.

## Naming Convention

| Context | Name |
|---------|------|
| GitHub repo URL | `https://github.com/urlmonitor/leafcutter-ai` |
| Submodule folder inside any consumer | `leafcutter/` |
| Internal package / module / import | `leafcutter` |

## Locked Design Decisions

1. **CODEOWNERS handle**: use `@urlmonitor` unless user specifies a different GitHub handle before execution.
2. **Blank issues disabled**: `config.yml` sets `blank_issues_enabled: false` and routes general questions to Discussions.
3. **PR workflow**: all changes delivered via a PR against `leafcutter-ai` main branch — no direct push.
4. **Max nesting depth: 3** — sub-tickets here are depth 2; no further epic fanout.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_issue_template_config.md](./01_issue_template_config.md) | Create `.github/ISSUE_TEMPLATE/config.yml` — disable blank issues, route general questions to Discussions | `[ ]` |
| 02 | [02_issue_template_bug.md](./02_issue_template_bug.md) | Create `.github/ISSUE_TEMPLATE/bug.yml` — structured bug report form | `[ ]` |
| 03 | [03_issue_template_feature.md](./03_issue_template_feature.md) | Create `.github/ISSUE_TEMPLATE/feature.yml` — feature request form | `[ ]` |
| 04 | [04_issue_template_compat.md](./04_issue_template_compat.md) | Create `.github/ISSUE_TEMPLATE/compat.yml` — compatibility / consumer integration report form | `[ ]` |
| 05 | [05_discussion_templates.md](./05_discussion_templates.md) | Create `.github/DISCUSSION_TEMPLATE/how-to.yml` and `ideas.yml` | `[ ]` |
| 06 | [06_contributing_md.md](./06_contributing_md.md) | Create `CONTRIBUTING.md` — bugs → Issues; features → Discussions; PR workflow | `[ ]` |
| 07 | [07_codeowners.md](./07_codeowners.md) | Create `CODEOWNERS` — auto-assign `@urlmonitor` on all PRs | `[ ]` |
| 08 | [08_readme_feedback_section.md](./08_readme_feedback_section.md) | Update `README.md` — insert "Reporting feedback" section with links to templates | `[ ]` |
| 09 | [09_open_pr.md](./09_open_pr.md) | Open PR against `leafcutter-ai` main with all the above files | `[ ]` |

## Dependency Graph

```
EPIC-LeafcutterMVP ST-3 (publish repo) — must complete before any ticket here starts
│
├── 01 (config.yml) ──────────────────────┐
├── 02 (bug.yml) ──────────────────────────┤
├── 03 (feature.yml) ─────────────────────┤ all can run in parallel
├── 04 (compat.yml) ──────────────────────┤
├── 05 (discussion templates) ────────────┤
├── 06 (CONTRIBUTING.md) ─────────────────┤
├── 07 (CODEOWNERS) ──────────────────────┤
└── 08 (README update) ───────────────────┘
                                           │
                                           └── 09 (open PR) — runs last, after all files exist
```

Tickets 01–08 can run in parallel (each touches a distinct file). Ticket 09 depends on all of them.

## Success Criteria

- `.github/ISSUE_TEMPLATE/` contains `bug.yml`, `feature.yml`, `compat.yml`, and `config.yml`
- `config.yml` has `blank_issues_enabled: false`
- `.github/DISCUSSION_TEMPLATE/` contains `how-to.yml` and `ideas.yml`
- `CONTRIBUTING.md` explains: bugs → Issues; features → Discussions; maintainer triages internally
- `CODEOWNERS` assigns `@urlmonitor` to all paths (`* @urlmonitor`)
- `README.md` has a "Reporting feedback" section near the top with links to Bug Report, Feature Request, and Compatibility Issue templates
- All changes are delivered via a PR against the `leafcutter-ai` main branch (not direct push)

## Decision History

- **2026-05-19**: Epic extracted from `EPIC-LeafcutterPostMVP` ST-05 by user decision (scope split to ship PostMVP 01–04 faster). CANDIDATE file at `tickets/00_inbox/CANDIDATE-EPIC-LeafcutterUpstreamChannels.md` replaced by this epic scaffold. Nine sub-tickets: 01–08 author the upstream config files in parallel; 09 opens the PR.
