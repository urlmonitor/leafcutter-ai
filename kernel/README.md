# Decision kernel

## Purpose

Run Leafcutter goals through bounded context enrichment, intent assessment, capability
routing, evidence collection and persisted interactions.

## Key Files

- `adapters/cli.py` exposes run, resume, status and entity-index commands.
- `entity_index.py` builds the explicit repository meaning index.
- `entity_context.py`, `entity_matching.py` and `entity_projection.py` recognize and
  project compact meanings before intent assessment.
- `entity_owners.py` and `entity_owner_scope.py` resolve authoritative artifact owners.
- `intent/` classifies the enriched goal.
- `scheduler/` persists and advances the run.
- `capabilities/research/planning.py` splits research into scoped child requests.
- `capabilities/research/assessments.py` preserves unresolved answer obligations.

## Critical Context

Entity meanings help interpretation; they are neither answer evidence nor authorization.
Research must retrieve evidence under the current scope. Graph children retain their
selected graph sources, while repository children retain permitted file locators.
The optional knowledge bridge in `integrations/` can use Jev to select registered reads.
An unsupported exhaustive question remains incomplete even if other sources find examples.

## Maintenance

Keep wire contracts and generated schemas aligned. Rebuild the explicit entity index
after changing indexed repository content. Run the relevant suites under `tests/kernel/`
and `tests/knowledge/` for routing changes. The full lifecycle and configuration are
documented in `docs/how-to/run-the-decision-kernel.md` and
`docs/architecture/components/decision-kernel.md`.
