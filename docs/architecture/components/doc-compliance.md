---
title: "Doc Compliance — Documentation Standards Enforcement"
description: "Documentation compliance verification system that enforces frontmatter presence, description fields, doc-length limits, and coverage requirements across all project documentation."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - doc_compliance
---

# Doc Compliance

## Overview

The Doc Compliance component ensures all documentation in `docs/` meets the project's standards for structure, metadata, and coverage. It operates through pre-commit hooks that inspect staged documentation files.

## Responsibilities

- Verify `description:` field presence in doc frontmatter
- Enforce documentation length limits (300 lines for non-ADR docs)
- Check that architecture components are registered in `docs/components.json`
- Validate doc type and status enum values in frontmatter

## Entry Points

- `scripts/doc_compliance/` — compliance check modules
- `scripts/commit_guardian/check_doc_coverage.py` — coverage enforcement
- `scripts/commit_guardian/check_doc_length.py` — length enforcement
- `scripts/commit_guardian/check_description_field.py` — description field guard

## Severity

Most doc compliance checks are advisory (exit 0 with warnings). The `check_description_field` check is blocking (exit 1) to prevent knowledge-graph queries from failing on docs without metadata.
