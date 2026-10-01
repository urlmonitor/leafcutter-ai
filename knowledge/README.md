# Knowledge package

## Purpose

Independently executable retrieval and immutable Neo4j projection. Canonical project sources remain in Git. The kernel calls the shared retrieval port.

## Key Files

- `contracts.py`, `service.py`: strict requests, bounded evidence and provenance.
- `query_models.py`, `query_compile.py`: authored typed recipes compiled into scoped parameterized Cypher.
- `query_catalog.py`, `query_store.py`: verified version discovery, immutable digests and atomic active pointers.
- `query_admission.py`: freshly executes declared expectations and mandatory boundary checks before activation.
- `cli_catalog.py`: discovery, verification and explicit registration commands.
- `adapters/`, `projection/`: optional infrastructure and source projection.

## Critical Context

No model-supplied Cypher or Python is executed. Recipes support at most two declared directed relationships, twenty seeds and ten neighbors per step. A one-item lookahead reports actual fanout saturation, including when later expansion yields no evidence. Required source kinds and memory relationships fail explicitly if the generation lacks approved mapping. Evidence sufficiency remains the research consumer's responsibility.

Catalog writes require the configured directory and explicit application authorization. The standalone registration command requires `--allow-catalog-write`; the kernel activation capability requires its dedicated permission. Descriptor/Cypher and verification digests are checked on reopening. Retained versions keep old requests stable. Fresh verification receipts stay tied to the current research SHA even when the same query already exists.

## Maintenance

Run the focused `tests/knowledge/test_query_admission.py` and independent boundary tests. Run `tests/knowledge_live/query_growth_checks.py` against the isolated Neo4j service before claiming generated-query compatibility. Update the component architecture and operational guide when changing the compiler language. Candidate expected IDs are authored judgments: successful checks do not establish general semantic usefulness.
