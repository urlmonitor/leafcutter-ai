---
title: "Changelog — Feature Delivery History"
description: "Automated changelog entry management system that tracks feature delivery history with structured YAML entries linked to tickets and commits."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - changelog
---

# Changelog

## Overview

The Changelog component provides structured changelog entry emission for the leafcutter-ai package. Entries are emitted by agents during the finalization phase and stored in `changelogs/` as YAML documents.

## Responsibilities

- Emit structured changelog entries keyed by ticket and commit reference
- Support versioned release grouping via `scripts/release/`
- Provide human-readable and machine-parseable formats

## Entry Points

- `scripts/changelog/emit_entry.py` — entry emission script
- `changelogs/` — storage directory for changelog YAML files

## Design

Changelog entries are atomic: one entry per ticket or feature. The `changelog-agent` template coordinates entry creation during epic finalization. Entries must include a ticket reference, a summary, and an impact classification.
