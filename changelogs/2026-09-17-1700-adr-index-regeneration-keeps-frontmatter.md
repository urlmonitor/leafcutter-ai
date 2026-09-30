---
title: "Regenerating the ADR index keeps the README's frontmatter"
date: "2026-09-17"
time: "17:00"
type: manual
components:
  - infrastructure
summary: "`python scripts/adr_refs.py --index --write` keeps every frontmatter field of docs/architecture/adrs/README.md and moves last_updated to today. It used to drop status, created, last_updated and components, which failed check-doc-frontmatter."
description: "_build_index() in scripts/adr_refs.py wrote a fixed frontmatter block containing only title, description and type, so each regeneration of the ADR index removed status, created, last_updated and components. check-doc-frontmatter then refused the README, and the fields were restored by hand when ADR-044 was registered (PR #835). The frontmatter is now built by the new scripts/adr_index_frontmatter.py. When the README exists, its fields are carried over verbatim (quoting and block lists included) with only last_updated advanced. When it does not, a complete block is written with status active, created and last_updated set to today, and components [documentation_system]. The index body is unchanged. The helper is a separate module because adr_refs.py was already over the 400-line limit; adr_refs.py goes from 598 to 597 content lines. AC INF-1300c-5; tests in unit_tests/docs/test_adr_index_frontmatter_preserved.py run the real script as a subprocess, were red before the fix, and a mutation that drops the carry-over turns the preservation test red again. Regenerating the real index produces no change beyond line endings."
commits:
breaking: false
---

## Entry

Regenerating the ADR index with `python scripts/adr_refs.py --index --write` no longer
strips the README's `status`, `created`, `last_updated` and `components` fields. Existing
fields are kept and `last_updated` moves to today.
