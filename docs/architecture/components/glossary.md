---
title: "Glossary — Project Terminology Registry"
description: "Project terminology registry with automated coverage checks that ensure novel jargon is triaged and documented consistently across all project artifacts."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - glossary
---

# Glossary

## Overview

The Glossary component maintains `docs/glossary.md` and `docs/glossary_blacklist.md` as the authoritative project terminology registry. The `check-glossary-coverage` pre-commit hook automatically detects novel terms in staged files and dispatches the `glossary-triage` agent for classification.

## Responsibilities

- Track all project-specific terms and their definitions
- Blacklist common English words that are not jargon
- Auto-detect novel terminology candidates in staged commits
- Provide a triage workflow for classifying candidate terms

## Entry Points

- `docs/glossary.md` — the glossary itself
- `docs/glossary_blacklist.md` — blacklisted non-jargon terms
- `scripts/build_glossary.py` — glossary build utility
- `scripts/commit_guardian/check_glossary_coverage.py` — pre-commit hook

## Constraints

Manual edits to add entries are prohibited. All additions must flow through the `glossary-triage` agent to maintain blacklist consistency.
