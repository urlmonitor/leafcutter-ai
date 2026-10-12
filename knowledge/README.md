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

Catalog writes require the configured directory and explicit application authorization. The standalone registration command requires `--allow-catalog-write`; the kernel activation capability requires its dedicated permission. Descriptor/Cypher and verification digests are checked on reopening. Retained native versions keep their admitted requests stable; an explicit catalog-format replacement requires the new digest. Fresh verification receipts stay tied to the current research SHA even when the same query already exists.

## Maintenance

Aura stores native `AC`, `ADR`, `Component`, `SourceFile` and `Test` nodes with
uppercase relationship types. `name` is the readable canonical identifier;
`title` and `source_path` provide details. `components` contains all directly
declared memberships, without propagating ownership to linked tests or files.
`current` follows the publication pointer atomically, including rollback.
`Repository` and `Snapshot` are diagnostic metadata, excluded from the saved
component search. In Aura, choose **In Scene** to hide unused legend categories.

`native_types/registry.py` also registers Agent, Skill, Ticket, Document,
RoadmapPhase, GlossaryTerm, Flow, Mockup, MockData, ChangelogEntry, Capability and
approved Decision source readers. Readers preserve complete authored fields;
`native_properties.py` exposes typed leaves with lossless shape metadata, and
`projection/native_metadata.py` keeps authored and derived fields separate.
`reports/native-fields/` contains the per-type reviews and verification receipts.
Use `python -m knowledge.native_refresh` to inspect an expansion at the existing
published source commit; explicit apply requires a private backup and writer
credentials. The new generation is read back before activation; historical
canonical data is preserved. Ordinary sync uses the same complete mapping.

The adapter executes native label and relationship names directly. The serving
catalog accepts only the current native compiler format; obsolete versions and
pins are rejected. Replace an obsolete saved catalog only after private backup
and fresh native-query verification, with an explicit digest mapping and a
conflict-checked atomic replacement. The native inspection and refresh paths do
not translate generic graphs. See
[the native graph and saved-query reference](../docs/reference/neo4j-native-queries.md)
for the completed application-catalog cutover and its measured scope.

Run the focused `tests/knowledge/test_query_admission.py` and independent boundary tests. Run `tests/knowledge_live/query_growth_checks.py` against the isolated Neo4j service before claiming generated-query compatibility. Update the component architecture and operational guide when changing the compiler language. Candidate expected IDs are authored judgments: successful checks do not establish general semantic usefulness.
