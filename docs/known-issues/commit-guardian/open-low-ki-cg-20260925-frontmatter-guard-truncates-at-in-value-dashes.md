---
title: "KI-CG-20260925-frontmatter-guard-truncates-at-in-value-dashes — ticket_frontmatter_guard (and check-doc-frontmatter) end the frontmatter at the first triple dash anywhere, including inside a value"
description: "low — a find for the closing triple dash starts at offset 3 and matches inside a value such as a title containing three dashes, so the parse yields a truncated mapping and the guard blocks the write with a misleading missing-field message. A missing pyyaml also reads as 'no frontmatter'. Reproduced a second time by check-doc-frontmatter refusing this very file on 2026-09-25."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/build-pipeline/resolved/resolved-high-ki-bp-019.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-CG-20260925-frontmatter-guard-truncates-at-in-value-dashes — ticket_frontmatter_guard ends the frontmatter at the first '---' anywhere, including inside a value

- **Severity:** low. Fails closed (blocks a valid write) with a message naming the wrong cause.
- **Status:** open — no AC. Reproduced 2026-09-25 (sub-agent probe).
- **Where:** `templates/hooks/ticket_frontmatter_guard.py:112` (delimiter search), `:129` (pyyaml-absent path).

## Symptom

A ticket with `title: fix a---b` parses as `{'title': 'fix a'}`; the guard then reports every other required
field as missing.

## Mechanism

`content.find("---", 3)` finds the next three dashes at any position, not a delimiter line. The same truncation
class is inferred in `mark_ac_done.py:65-76` and `check_ticket_ac_status_parity.py:108` (`split("---", 2)`).
Five other readers (`_signoff_parity_checks.py:202`, `frontmatter_validators.py:39`, `repair_epic_member_pr_phase.py:87`,
`extract_epic_facts.py:69`, `epic_tickets._read_ticket_frontmatter:80`) use a line-based delimiter and agree with
each other. KI-BP-019's silent-pyyaml-absent pattern was fixed in `template_compiler.py` only; this guard still
returns "no frontmatter" when pyyaml is missing.

## Second reader, observed 2026-09-25

The commit-time hook `check-doc-frontmatter` has the same defect. When this KI was
first committed, its title and description quoted the three-dash string literally,
and the hook refused the file with `Missing YAML frontmatter.` even though a
well-formed block was present. The title was reworded to get the commit through,
so the hook's reader belongs in the same shared-reader fix.

## Fix direction

One shared `read_frontmatter(text)` that splits on a `^---\s*$` line and raises when pyyaml is absent; every
ticket-frontmatter reader imports it.
