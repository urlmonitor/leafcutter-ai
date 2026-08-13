---
title: Renumber colliding ADRs and repair the citation graph
date: "2026-08-13"
time: "23:55"
type: manual
components: 
  - documentation_system
  - guardrail_engine
summary: "Every ADR number now resolves to exactly one decision. Four duplicated integers (004x2, 007x3, 017x3, 025x2) were renumbered, the 008 gap filled, and roughly 430 citations repaired across ~200 files. Adds scripts/adr_refs.py, which audits the corpus and regenerates the ADR index."
description: "The corpus had four duplicated integers spread over ten files, a gap at 008, and 382 bare ADR-NNN citations that no longer resolved to a single decision. Root cause: the package was extracted from a predecessor monorepo in one 413-file commit that carried over every file citing ADRs but left docs/architecture/adrs/ behind, then restarted numbering at 001, so a second sequence grew underneath the inherited citations. Six ADRs were renamed as git-tracked renames (tdd-workflow-enforcement to 027, ac-store-schema to 008, test-fixture-convention to 028, dual-engine-workflow-support to 030, worktree-quality-gate-guard to 031, tiered-parallel-code-smell-review to 032). Two decisions that were widely cited but never recorded here were written at free numbers: ADR-029 adr-number-collision-prevention (the record check_adr_collision.py cites in its own docstring) and ADR-033 agent-model-tiers (target of 116 citations to a file that did not exist). The new scripts/adr_refs.py reports duplicates, gaps, citations to numbers with no file, and citations naming a slug with no file; it regenerates the ADR index, which had gone stale at ADR-012. It deliberately never rewrites a bare ADR-NNN citation, because that is ambiguous the moment a number splits. Also removes the predecessor project domain name from every live surface, generalises the BYBIT_API_KEY secret rule to EXCHANGE_API_KEY without weakening detection, and strips hardcoded absolute developer paths from two deployed templates. Audit is clean: 0 duplicates, 0 gaps, 0 dangling references, 0 broken slugs across 33 ADRs and 3422 citations."
---

## Entry
