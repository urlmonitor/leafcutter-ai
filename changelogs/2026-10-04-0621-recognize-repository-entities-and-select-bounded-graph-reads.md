---
title: Recognize repository entities and select bounded graph reads
date: "2026-10-04"
time: "06:21"
type: feature
components:
  - decision_kernel
  - knowledge_management
summary: Use compact repository meanings before intent and let Jev select supported Neo4j reads after routing.
description: "Add an explicitly prepared entity index, bounded recognition of vocabulary, native IDs and Python symbols, permission-aware context handoffs, canonical structured-pointer retrieval, and finite Jev operation/target selection. Preserve explicit knowledge requests, source revisions, paid usage, and incomplete population assessments. Update DK-300 acceptance criteria, tests and product truth."
---

## Entry

Fresh kernel runs interpret repository terminology and artifact references using a
prepared local meaning index before assessing intent. Recognition has independent
size, lookup and time bounds; it does not search repository bodies or call a model.
An explicit `kernel entities build` command prepares or refreshes the index.

After routing, Jev can choose supported knowledge operations and permitted targets.
Python binds their arguments and preserves source permissions, revision provenance
and usage accounting. Unsupported exhaustive queries retain an unresolved assessment
when other research sources return examples. Explicit knowledge requests keep their
existing behavior. Native YAML/JSON references retrieve the selected value.

Validation includes 148 strict entity/bridge tests, a 64-test rerun after the final
selector wording change, 59 adjacent research tests plus five subtests, and five
detected mutation defects. A live AC question selected `get_entities` and retrieved
its criterion from Neo4j with satisfied coverage. No Anthropic calls were used.

Complete ticket-priority enumeration remains unsupported. Initial recognition can
exceed its two-second deadline, and large source excerpts can exhaust retrieval
budgets. The existing five whole-kernel baseline failures are documented in
`reports/entity-context-verification.md`; no full-suite green result is claimed.
Shared defaults do not enable Neo4j automatically; deployment must configure a
backend and eligible graph source.
