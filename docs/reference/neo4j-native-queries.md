---
title: Neo4j native graph and query compatibility
type: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
- knowledge_management
- decision_kernel
description: Native Neo4j labels, component filters, authored metadata, migration commands and retained query identity rules.
related_docs:
- docs/how-to/run-knowledge-retrieval.md
- docs/reference/knowledge-retrieval-answers.md
- docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
---

# Neo4j native graph and query compatibility

This reference describes the native graph representation and its migration and
query-identity boundaries. For credentials, ordinary publication and retrieval,
use the [standalone retrieval guide](../how-to/run-knowledge-retrieval.md).

## Explore the graph in Aura

The domain graph exposes native labels including `AC`, `ADR`, `Component`,
`Agent`, `Skill`, `Ticket`, `Document`, `RoadmapPhase`, `GlossaryTerm`, `Flow`,
`Mockup`, `MockData`, `ChangelogEntry`, `Capability`, `Decision`, `SourceFile`,
and `Test`. A label has nodes only when the pinned source contains that type.
Use `name` for captions (canonical identifiers), and inspect `title`, `source_path`
and `source_revision` for context. Relationships use their actual types, such as
`COMPONENT_MEMBERSHIP`, `DEPENDS_ON`, `COVERED_BY`, and `IMPLEMENTED_BY`.
These remain source declarations, not proof that implementation or testing passed.

In Aura **Bloom**, use the saved search phrase **Component finalize**, select the
matching suggestion, then run it. Replace `finalize` with another component name
to view its direct assignments. The saved phrase selects only current nodes and
relationships. Results depend on the active mapper and source revision; the native
field expansion also admits direct component assignments from newly supported types.
Choose **In Scene** in the legend to show the categories present in this view.
Aura resets this choice to **All** after a reload, so select **In Scene** again.
The free instance uses its Default Perspective; an additional perspective requires
an Aura upgrade. The saved captions use `name` for AC, ADR, Component, SourceFile
and Test, and `title` for Ticket, Document and ChangelogEntry; titles appear on hover.
The verified mapper-7 scene at source `59269e02` contains 74 nodes and 74
relationships: 63 ACs, one ADR, one Component, three Tickets, two Documents and
four ChangelogEntries. See `reports/native-fields/aura-ui.json` for visual evidence.

Show items explicitly assigned to a component in the active snapshot:

```cypher
MATCH (n)
WHERE n.current = true AND 'finalize' IN n.components
RETURN n;
```

Show those items connected to the component:

```cypher
MATCH p = (n)-[:COMPONENT_MEMBERSHIP]->(c:Component {name: 'finalize'})
WHERE n.current = true AND c.current = true
RETURN p;
```

`components` is a list because an item may declare more than one membership.
It includes direct assignments only; a test referenced by an AC does not acquire
the AC's component automatically. Keep `current = true` in ordinary exploration
to exclude retained historical copies. The component search omits `Repository`
and `Snapshot`; they remain available for diagnostics. Ordinary label searches
can still include historical copies unless a current filter is applied.

Current retrieval, publication and vector queries use the native labels directly.
The adapter sends compiler-owned Cypher to Neo4j without rewriting its label or
relationship names. Saved queries entered directly in Aura must also name native
labels and relationships; older generic query names are not aliases in Aura.
For example, use `AC` for acceptance criteria, `Repository` and `Snapshot` for
bookkeeping, and the declared relationship type for each connection.

Registered queries admitted by compiler version 1 keep their original immutable
catalog entries and verification digests, including the `digest` of a descriptor
returned by `QueryCatalog.get()`. A separate compatibility verifier
reconstructs their historical compiled text solely to check those receipts;
executing the retained descriptor generates native Cypher. New admissions use
compiler version 2 and the ordinary fresh-verification process. To replace an
existing operation with a new admission, increment its descriptor version and
supply the prior active digest. Do not edit stored digests or verification
receipts by hand. Legacy names remain in explicit old-graph migration code and
fixtures so migration can still recognize the format it converts.

Existing generic graphs can be inspected without writes:

```sh
python -m knowledge.domain_migrate --root REPOSITORY --repository-id leafcutter --expected-host AURA_HOST
```

After updating readers, add `--apply --backup ABSOLUTE_BACKUP_PATH` with explicitly
configured writer credentials to perform the migration. Backups contain source
evidence and should remain private and outside Git. Migration validates every
retained snapshot, preserves entity keys, payloads, source revisions and counts,
and replaces each legacy relationship atomically with its native typed equivalent.
Interrupted runs can be inspected and resumed with a new backup path. Publication
changes, corrupt records and cross-generation edges are rejected. Old writer
versions must not be used after migration.

## Inspect complete native fields

Simple authored fields appear directly, for example `criteria`, `priority`,
`test_required` and `depends_on`. Nested leaves use JSON Pointer names, retaining
list positions and parent objects. For example, the first test specification's
name is `/test_spec/0/name`. Quote these names with backticks in Cypher:

```cypher
MATCH (n:AC {current: true})
WHERE 'finalize' IN n.components
RETURN n.id, n.criteria, n.test_required, n.`/test_spec/0/name`;
```

Authored names that collide with graph bookkeeping use pointers too: `/id`,
`/title`, `/components`, `/current`, and `/payload` preserve exact source values.
The ordinary `components` property deduplicates explicit source declarations and
direct membership edges. Unresolved declarations remain filterable and are reported
in snapshot diagnostics; indirect connections do not imply membership.
Registry data stays separate from template frontmatter, bodies and context, which
appear under `_native_derived/derived/...`. Those fields are inspection aids,
not additional authored attributes of the registry entry.

Neo4j cannot store maps, nested lists or null as ordinary property values. The
mapping exposes their non-null leaves and records null paths in
`_native_null_paths`, empty containers in `_native_empty_paths`, and exact structure
and types in `_native_shape`. A missing field is different from any of these.
The lossless canonical payload remains available; low-disclosure retrieval retains
its existing field allowlist and does not reveal the full source automatically.

The maintained type registry is `knowledge/native_types/registry.py`; the reviewed
inventory and individual field contracts are in `reports/native-fields/`. Each
reader preserves extension fields as well as the currently declared schema fields.
To inspect a native-field refresh at the existing active source commit:

```sh
python -m knowledge.native_refresh --root ENVIRONMENT_ROOT --source-root TRUSTED_CHECKOUT --repository-id leafcutter --expected-host AURA_HOST
```

Add `--apply --backup ABSOLUTE_PRIVATE_BACKUP_PATH` only for an authorized refresh
with writer credentials. It builds a new mapper generation, verifies written fields
before activation, and preserves the previous generations and their canonical data.
It does not publish uncommitted files or claim missing source records exist.
The 2026-10-02 publication contained 9,047 current nodes and 23,612 relationships,
with all four earlier generations preserved; that source had no Decision records.
Its counts and field readback remain recorded in
`reports/native-fields/aura-publication.json` and `aura-readback.json`. The
2026-10-03 publication added six Decisions with all 31 authored fields verified;
see `reports/native-fields/aura-decisions-2026-10-03.json`. These receipts describe
their pinned source revisions. Inspect the active snapshot for current counts.

## See also

- [Standalone knowledge indexing and retrieval](../how-to/run-knowledge-retrieval.md)
- [Retrieval answer and evidence contracts](knowledge-retrieval-answers.md)
- [ADR-062: standalone knowledge retrieval](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md)
