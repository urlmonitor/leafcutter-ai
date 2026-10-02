---
title: "check-secrets: the TICKET/EPIC prose exemption reads the truncated excerpt, not the line"
status: todo
components:
  - commit_guardian
created: 2026-10-02
depends_on: []
priority: low
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - pre-commit
  - false-positive
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# check-secrets: the TICKET/EPIC prose exemption reads the truncated excerpt, not the line

## Actor / Goal
In order to stop false ENTROPY_HIGH blocks on long prose lines, we need `_is_prose_exempt()` to judge the full source line instead of the finding's truncated excerpt.

## Context
- **Where:** `_filter_prose_findings()` in `.leafcutter/scripts/commit_guardian/check_secrets.py` (source: `templates/scripts/commit_guardian/check_secrets.py`) calls `_is_prose_exempt(finding.excerpt, file_path)`.
- **The defect:** the excerpt is a preview of about 100 characters.
  - A `TICKET-YYYYMMDD-*` or `EPIC-*` token past that cut-off is never seen, so `has_known_token` is False and the line is not exempted.
  - This is so even when that ticket id is the only high-entropy token on the line.
- **Seen on 2026-10-02:** a provenance note in `docs/product-truth/mock-data/leafcutter/decisions.mock.json` named `TICKET-20261002-DecisionLifecycleProductTruth` at about character 130 and was blocked (entropy 4.56). The workaround was to remove the id from the note.

## Scope
- Pass the full line (read from the staged blob at `finding.line`) to `_is_prose_exempt()`.
- Add a test: a long line whose only high-entropy token is a TICKET id beyond the excerpt length is exempt, and a real high-entropy secret on the same line is still flagged.

## Out of Scope
- Changing the entropy threshold or the token regex.

## Comments
