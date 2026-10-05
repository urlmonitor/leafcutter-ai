# Kernel and knowledge integrations

## Purpose

Connect kernel research requests to the configured knowledge service while preserving
caller scope, source permissions, usage budgets and evidence provenance.

## Key Files

- `knowledge_capability.py` registers the retrieval bridge.
- `knowledge_execution.py` validates requests and maps knowledge results to kernel evidence.
- `knowledge_scope.py` checks trusted repository bindings and returned evidence authorization.
- `graph_offers.py` builds the finite operation and target choices permitted by recognized
  identities, trusted scope and actual backend readiness.
- `graph_selection.py` asks Jev to choose among those options; Python binds the arguments.
- `graph_selection_result.py` records unsupported choices and incomplete populations.
- `graph_population.py` binds the offered hierarchy scope and preserves population
  completeness across authorized source disclosure.
- `knowledge_followups.py` controls progressive source disclosure.
- `query_planning.py` and `query_growth.py` implement the separate configured query-catalog path.

## Critical Context

Explicit knowledge requests retain their existing operation and arguments. Automatic
research uses the Jev selector for built-in operations when the separate query catalog
is not configured. The selector cannot invent Cypher, identifiers or new query templates.
Discovery and source disclosure both enforce authorization. Recognizing an identifier
does not prove an exhaustive population; unsupported complete-list questions retain an
unresolved assessment even when another research source returns examples.

## Maintenance

Add an operation only when its backend implementation and Python argument binding exist.
Keep policy checks on cached meanings and returned evidence aligned. Run
`tests/kernel/entity_context/test_knowledge_operation_selection.py`,
`tests/kernel/entity_context/test_knowledge_selection_fallback.py` and
`tests/knowledge/test_kernel_bridge.py` after changing the bridge. Acceptance criteria
and test links live under `docs/acceptance-criteria/decision-kernel/DK-300-entity-context/`.
Live verification must distinguish Jev selection, executed reads and answer completeness.
