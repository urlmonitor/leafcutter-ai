---
title: "Create auto-updating documentation index for BA and IT PO knowledge acquisition"
status: todo
components:
  - build_pipeline
  - documentation_system
created: 2026-06-03
depends_on:
  - 01_adr_contract_driven_acs.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - scripts/generate_doc_index.py
  - docs/INDEX.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 02a: Auto-Updating Documentation Index

## Business Intent

The BA and IT PO need to know WHERE documentation lives so they can pull it
on-demand, without having everything injected into their context upfront. A
single `docs/INDEX.md` file acts as the table of contents for all project
documentation, auto-regenerated on every PR merge so it never goes stale.

## Context

### The Problem With Upfront Injection

Injecting all docs (components, user flows, diagrams, glossary) into the BA's
context at spawn time is wasteful:
- Most docs are irrelevant to the current ticket
- Context window fills with docs the BA never reads
- Adding new doc types requires updating the BA's prompt

### The Pull-Based Alternative

Give the BA a lightweight index (~50-100 lines) that maps topics to file paths.
The BA reads the index first, identifies which docs are relevant to the user's
request, and pulls only those. The index tells it:

- **Components**: which components exist and where their docs live
- **User flows**: which user flows are documented and their paths
- **Architecture diagrams**: which C4/sequence/ERD diagrams exist per component
- **How-to guides**: available how-tos by topic
- **API conventions**: where to find API patterns, error shapes, auth docs
- **DB schema**: where schema docs and db_schema.json live
- **Glossary**: path to glossary for domain term lookup

### Auto-Update Mechanism

A script (`generate_doc_index.py`) walks the docs tree and generates `INDEX.md`.
It runs:
- On every PR merge (post-merge hook or CI step)
- On-demand via `python scripts/generate_doc_index.py`
- During `build.py` (so deployed projects get it too)

This means the index is always current. New docs automatically appear.
Deleted docs automatically disappear. No manual maintenance.

## Agent Contracts

### python-coder

- [ ] AC-1: `scripts/generate_doc_index.py` exists and generates `docs/INDEX.md` by walking the docs tree
- [ ] AC-2: INDEX.md contains sections for each doc category with file paths and one-line descriptions:
  ```markdown
  ## Components
  | Component | Doc | Description |
  |-----------|-----|-------------|
  | candle_context | [docs/components/candle_context.md](...) | OHLCV candle enrichment context |

  ## Architecture Diagrams
  | Component | Type | Path |
  |-----------|------|------|
  | candle_context | container | [docs/architecture/candle_context_container.md](...) |

  ## User Flows
  | Flow | Path |
  |------|------|
  | Ticket creation | [docs/how-to/create-ticket.md](...) |

  ## How-To Guides
  ...

  ## API Conventions
  ...

  ## DB Schema
  ...

  ## Glossary
  - [docs/glossary.md](...) — project-specific terms and definitions
  ```
- [ ] AC-3: The script extracts one-line descriptions from each doc's YAML frontmatter `description:` field (if present) or the first non-heading line of the doc body (fallback)
- [ ] AC-4: The script is idempotent — running it twice produces identical output
- [ ] AC-5: The script handles missing/empty docs directories gracefully (section shows "No docs found" instead of crashing)
- [ ] AC-6: `build.py` calls `generate_doc_index.py` as part of the build pipeline so consumer projects get a current INDEX.md on deploy
- [ ] AC-7: INDEX.md includes a header with generation timestamp and a note: "Auto-generated — do not edit manually. Run `python scripts/generate_doc_index.py` to regenerate."

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — generates a documentation index file only.
- Reversibility? Fully reversible — one new script, one generated file.
- Risk: docs without frontmatter descriptions produce low-quality index entries.
  Mitigation: fallback to first non-heading line; doc-enforcer can be extended
  to require description in frontmatter.
