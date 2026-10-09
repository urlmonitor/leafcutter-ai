---
title: Use native graph names in current Neo4j queries
description: User-requested maintenance derived from approved KM-400a-3-i; remove
  remaining legacy query names while preserving admitted query identities and migration
  support.
created: '2026-10-09'
status: done
priority: medium
depends_on: []
components:
- knowledge_management
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
requires_diagram: false
requires_adr: false
source_ac: KM-400a-3-i
ac_traceability:
  id: KM-400a-3-i
  path: docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-3-i.yaml
agents:
  python-coder: signed_off
  code-review: signed_off
  commit: signed_off
files_touched:
- changelogs/2026-10-09-0905-neo4j-native-query-names.md
- docs/INDEX.md
- docs/how-to/run-knowledge-retrieval.md
- docs/reference/neo4j-native-queries.md
- knowledge/adapters/domain_schema.py
- knowledge/adapters/neo4j_backend.py
- knowledge/adapters/neo4j_domain_build.py
- knowledge/adapters/neo4j_domain_migration.py
- knowledge/adapters/neo4j_projection.py
- knowledge/adapters/neo4j_queries.py
- knowledge/adapters/neo4j_vector_build.py
- knowledge/adapters/neo4j_vectors.py
- knowledge/native_refresh.py
- knowledge/query_admission.py
- knowledge/query_catalog.py
- knowledge/query_compile.py
- knowledge/query_legacy.py
- knowledge/query_models.py
- knowledge/query_store.py
- tests/knowledge/fixtures/query_catalog_v1.json
- tests/knowledge/test_native_refresh_recovery.py
- tests/knowledge/test_neo4j_native_queries.py
- tests/knowledge/test_query_native_compile.py
- tests/knowledge_live/domain_migration_checks.py
- tests/knowledge_live/neo4j_checks.py
- tickets/00_inbox/TICKET-20261009-KM-400a-3-i-native-query-maintenance.md
---

# Use native graph names in current Neo4j queries

## Context

Hendrik requested agents to clean up the remaining KR/KG query naming on
2026-10-09. This maintenance ticket is derived from the approved KM-400a-3-i
native graph contract. The completed feature ticket and its AC lifecycle stay
unchanged. This is implementation cleanup of accepted behavior, not a new
feature or ontology.

## Existing acceptance contract

The applicable clauses below are copied from the source AC:

Given a published repository graph contains acceptance criteria, ADRs, components, source files and tests
When the user explores the current repository snapshot in Aura
Then those entities have the native labels AC, ADR, Component, SourceFile and Test respectively
And each entity exposes its readable canonical identifier, name or source path for its caption
And connections have meaningful native relationship types while retaining their declared direction and provenance
And the normal domain exploration excludes repository and snapshot bookkeeping and retired snapshots

Given the existing Aura database contains retained generations and registered retrieval queries
When the representation is migrated and a subsequent snapshot is published or rolled back
Then canonical identities, source revisions, payloads, relationship counts and retained generations are preserved
And the current marker agrees with the active repository snapshot after the atomic switch
And existing registered retrieval queries and their validation digests remain valid and return the same scoped evidence
And invalid, unowned or cross-generation records cause the migration to refuse before changing the graph

## Maintenance scope

Current adapter operations and newly compiled queries must use the physical
native labels and named relationships directly. Generation isolation, limits,
parameter binding, evidence provenance, atomic publication and vector behavior
must remain intact. Retain explicit old-format migration code and fixtures.
Historical receipts and their exact query text are evidence, not active examples.

Previously admitted catalog entries must still validate against their original
compiler output and digests. New native compiler output requires its own compiler
version; existing active or retained entries must not be silently rewritten or
invalidated. New catalog admissions retain their existing fresh-verification gate.

## Reference audit

The tracked query-name audit found active legacy patterns in the Neo4j adapter,
compiler and native-refresh inspection path. No active query examples in docs,
templates, scripts, config or workflow files used those labels. No KG-prefixed
graph label was found; `KM-KGS` acceptance-criterion identifiers are unrelated.

The intentional remaining boundaries are old-format graph inspection/conversion,
publication guards rejecting unmigrated graphs, frozen version-1 catalog receipt
validation, and their regression fixtures. Historical migration reports preserve
what was actually executed. None of those references is an ordinary native query
alias. This ticket covers Leafcutter's code and query files, as the user clarified.

## Verification plan

Run focused behavioral tests for native statement emission and execution,
repository/generation isolation, retained catalog integrity and tampering
rejection, and explicit migration compatibility. Run changed-file lint and
annotation checks. Do not run the removed full pytest suite or mutate Aura.
Record actual commands and outcomes after execution; none is claimed yet.

## Test Requirements

```yaml
tests:
- name: test_rows_preserves_trusted_statement_literals_and_parameters
  file: tests/knowledge/test_neo4j_native_queries.py
  covers: [KM-400a-3-i]
  asserts: The actual transaction boundary passes trusted statement text and separately bound arguments unchanged.
  framework: unittest
  type: unit
  angle: boundary
- name: test_registered_reads_and_neighbors_emit_native_patterns_with_bound_ids
  file: tests/knowledge/test_neo4j_native_queries.py
  covers: [KM-400a-3-i]
  asserts: Registered reads and neighbor expansion use native types while retaining scoped bound identifiers.
  framework: unittest
  type: unit
  angle: boundary
- name: test_v1_catalog_keeps_admission_digest_and_executes_native_query
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: Public retrieval preserves old active and retained admission identities and receipt bytes while executing native statements.
  framework: pytest
  type: unit
  angle: boundary
- name: test_v1_tampering_or_unknown_compiler_fails_without_rewriting
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: Modified historical receipts and unrecognized compiler versions refuse without changing stored evidence.
  framework: pytest
  type: unit
  angle: failure
```

## Implementation and verification

Current adapters emit native labels and named relationships directly, and the
transaction boundary no longer rewrites Cypher. Old graph inspection uses an
explicit dual-format query shared with native refresh. The compiler emits native
version-2 queries while catalog validation retains the frozen version-1 receipt
verifier and original admitted identities. Compiler-v2 vocabulary is frozen so
later registry additions cannot silently invalidate its stored digests.

Adapter coder verification reported on 2026-10-09:

- `python -B -m unittest tests.knowledge.test_neo4j_native_queries -v`:
  four failures before production edits, then all four passing after the fix.
- Direct execution of all 15 existing native-refresh recovery parameter cases:
  passed. This was a focused invocation, not the full pytest suite.
- Ruff with `--no-cache` over the 13 adapter-owned changed files: passed.
- Mypy with `--follow-imports=silent --no-incremental` over nine production files
  plus the new adapter test module: zero issues across ten files.

Independent root verification reported on 2026-10-09:

- All 28 existing query-admission, boundary and adversarial parameterized cases
  passed through a direct runner, without starting pytest.
- Sixteen existing domain-graph, migration, vector and catalog cases passed on
  disposable local Neo4j at loopback port 18087. They exercised retained version-1
  digest and evidence parity, idempotence, rollback, publication races, vector
  indexing and refusal boundaries.
- The combined changed-Python Ruff check passed; mypy checked all 15 changed
  production modules with zero issues, and `git diff --check` was clean.
- The frozen version-1 verifier matched the original committed compiler's entire
  output and digest for all 1,152 combinations of seed kind, endpoint kind,
  relationship and direction.

Compiler coder verification reported on 2026-10-09:

- `python -m pytest tests/knowledge/test_query_native_compile.py
  tests/knowledge/test_query_admission.py
  tests/knowledge/test_query_growth_boundaries.py
  tests/knowledge/test_query_growth_adversarial.py
  tests/knowledge/test_query_growth_kernel.py -q`: 74 passed in 12.82 seconds.
  This was the named focused set, not the full suite. It includes three checks
  added to preserve compiler-v2 digests across future registry growth.
- Ruff passed for the six compiler/catalog production files and the new test
  module; mypy with `--follow-imports=silent` reported zero issues in those six
  production files.
- The actual local catalog referenced by
  `reports/knowledge-query-growth-aura.json` retained its one version-1 entry,
  valid original digest and unchanged file bytes.

Independent review verified the final private compiler-version binding on
catalog-returned descriptors: `QueryCatalog.get(...).digest` retains the admitted
identity and recomputes after edits or copies, while authored JSON excludes that
private provenance. Fresh admission and runtime execution still compile native
version-2 text. The guide, changelog, ticket metadata and four exact test references
were validated. No unresolved issue remained in the reviewed compiler/catalog
changes. Role sign-offs are recorded below by their actual agents; no Aura
publication, commit, PR or merge is asserted.

## Documentation extraction verification

The doc-length hook required the retrieval guide to shrink. Its coherent native
Aura exploration and field-mapping sections now live in
`docs/reference/neo4j-native-queries.md`, with bidirectional body and metadata
links. A direct comparison against the staged pre-extraction guide confirmed all
131 moved lines were preserved exactly apart from heading depth. The guide has
256 raw lines and the new reference has 158; the original section anchors remain
as linked summaries. The documentation index was regenerated with its supported
script. No instructions, examples or historical evidence were deleted.

Preflight passed the actual staged doc-length hook (three docs), frontmatter hook
(four files), local body/frontmatter link and anchor checks, strict ticket signoff
parity and staged whitespace check. Only existing advisory warnings remain for
the generated index timestamp and absent optional implementation-task section.

## Sign-offs

- [x] python-coder — 2026-10-09 09:11
- [x] code-review — 2026-10-09 09:12

- [x] commit — 2026-10-09 09:25

## Comments

### 2026-10-09 09:11 - python-coder (status: ok)
feedback-id: fb_2026-10-09_971519aa
completion_manifest:
  native_runtime_queries_implemented: true
  versioned_catalog_identities_preserved: true
  focused_compiler_tests_green: true
  lint_and_annotations_green: true
  coordinated_adapter_integration_verified: true
Implemented native compiler-v2 statements with a frozen vocabulary, explicit receipt-only
compiler-v1 reconstruction, unchanged active and retained admission pins, and private
compiler provenance preserving public descriptor digests after reload without stale
identities on edits. The focused compiler/catalog suites passed 74 tests in 12.82 seconds;
ruff and mypy passed for all six changed production modules. The existing real local
version-1 catalog retains its original digests and bytes. Coordinated adapter changes
were verified by the root agent with 16 disposable-Neo4j cases and 1,152 original-v1
output equivalence cases; this sign-off claims only the python-coder phase.

### 2026-10-09 09:12 - code-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  native_query_and_scope_contracts_reviewed: true
  retained_catalog_integrity_reviewed: true
  public_descriptor_digest_compatibility_verified: true
  legacy_boundaries_audited: true
  documentation_and_test_references_validated: true
  cross_layer_seam_answer:
    result: covered
    producing_side: knowledge.query_compile.compile_query and knowledge.query_catalog.QueryCatalog
    consuming_side: knowledge.query_execution.execute_query and knowledge.adapters.neo4j_backend.Neo4jBackend
Reviewed the compiler, catalog, model and adapter changes against KM-400a-3-i.
The review found and resolved future-registry digest drift and the public
catalog descriptor digest regression. Independently exercised the final getter,
compiled runtime identity, private serialization boundary and edited-copy digest
behavior; no unresolved finding remained. Original receipt bytes remain verified
by the frozen compiler, while native runtime statements retain bound inputs,
scope and limits. Root's final two old/new live catalog cases passed again after
the private-version change. The feedback script rejected code-review as an
unregistered writer; this uses the signoff skill's documented submit-failed
fallback without changing role or feedback policy. This is only the actual
code-review phase, not a commit, PR or hosted-publication sign-off.

### 2026-10-09 09:16 - commit (status: ok)
feedback-id: fb_2026-10-09_cfaaf4b6
completion_manifest:
  authorized_scope_reviewed: true
  hook_probe_pass: true
Auto-authorized commit gate for the user's requested native query cleanup:
subject "refactor(knowledge): use native Neo4j query names". The scoped paths
are exactly the 26 entries in this ticket's files_touched list. Existing coder
and review signatures remain unchanged. Commit execution and final phase sign-off
are pending; the ticket remains in_progress until the normal hooks and commit finish.

### 2026-10-09 09:25 - commit (status: ok)
feedback-id: fb_2026-10-09_8ac6fd75
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Created commit 2c074a094e731d7238e02fd29e47c5bcf8b1e350 with subject
"refactor(knowledge): use native Neo4j query names". Verified HEAD moved and
only the approved 26 paths were committed. The initial documentation-length
refusal was resolved by extracting the native-query reference with reciprocal
links and preserving the moved content; the single retry passed all applicable
normal pre-commit and commit-message hooks. No hooks were bypassed and no full
pytest suite ran. Existing coder/review evidence remains intact. This signs off
only the completed commit phase; no PR, CI completion, push or merge is claimed.
The routine commit review identified no additional reusable learning to capture.
