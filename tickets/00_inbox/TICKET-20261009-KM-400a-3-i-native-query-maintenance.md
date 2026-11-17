---
title: Remove legacy Neo4j compatibility and replace saved queries
description: 'User-requested native-only cleanup under KM-400a-3-i: remove all legacy
  graph and compiler paths, freshly verify saved native queries, and replace the actual
  local catalogs with an auditable digest mapping.'
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
- docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-3-i.yaml
- docs/how-to/kernel-query-growth.md
- docs/how-to/run-knowledge-retrieval.md
- docs/reference/neo4j-native-queries.md
- knowledge/README.md
- knowledge/adapters/domain_schema.py
- knowledge/adapters/neo4j_backend.py
- knowledge/adapters/neo4j_domain_batches.py
- knowledge/adapters/neo4j_domain_build.py
- knowledge/adapters/neo4j_domain_migration.py
- knowledge/adapters/neo4j_inspection.py
- knowledge/adapters/neo4j_projection.py
- knowledge/adapters/neo4j_queries.py
- knowledge/adapters/neo4j_vector_build.py
- knowledge/adapters/neo4j_vectors.py
- knowledge/domain_migrate.py
- knowledge/native_refresh.py
- knowledge/query_admission.py
- knowledge/query_catalog.py
- knowledge/query_compile.py
- knowledge/query_legacy.py
- knowledge/query_models.py
- knowledge/query_store.py
- reports/neo4j-native-query-cutover-2026-10-09.json
- tests/knowledge/fixtures/query_catalog_v1.json
- tests/knowledge/test_native_inspection.py
- tests/knowledge/test_native_refresh_recovery.py
- tests/knowledge/test_neo4j_native_queries.py
- tests/knowledge/test_query_native_compile.py
- tests/knowledge_live/domain_migration_checks.py
- tests/knowledge_live/native_inspection_checks.py
- tests/knowledge_live/neo4j_checks.py
- tickets/00_inbox/TICKET-20261009-KM-400a-3-i-native-query-maintenance.md
---

# Remove legacy Neo4j compatibility and replace saved queries

## Context

On 2026-10-09 Hendrik expanded the cleanup to remove all legacy KR/KG
compatibility and update the actual saved queries. This explicit instruction
supersedes the initial compatibility-preserving implementation in PR #1085.
The accepted native graph, declared component membership and scoped evidence
contracts remain in force. The narrow source-AC clause promising unchanged old
catalog digests is amended to a verified native replacement with an explicit
old-to-new identity mapping.

## Maintenance scope

Remove legacy graph migration, dual-format query paths, frozen compiler-v1
reconstruction, and serving-time admission compatibility. Current code and
active query files must use the native graph format exclusively. Preserve
parameter binding, repository/snapshot isolation, limits, native inspection,
field readback and atomic publication/rollback behavior.

Saved catalog replacement is an explicit one-time data operation. Back up the
original catalog outside Git, recover reviewed candidate arguments, freshly
verify the native query against its pinned retained source, then replace the
catalog under a conflict check. Record old and new descriptor/digest identities.
Do not rewrite old execution proof as if it measured the new query. Old pins in
historical receipts and checkpoints remain history; active saved consumers must
receive the new catalog identity. Runtime rejects unsupported compiler versions.

## Reference audit

The original tracked query-name audit found legacy paths in the adapters,
compiler and native-refresh inspection. The new scope removes those paths and
their executable fixtures. Historical changelogs, ADRs and measured receipts
retain the facts of what ran. `KM-KGS` acceptance-criterion identifiers are
unrelated to graph labels and remain unchanged.

Two actual local catalogs were found under the application's query-catalog-km500
root: its catalog.json and the 14f901a2-8798-4f4c-9539-6a40fbffa626 substore's
catalog.json. Both originally contained get_component_tests version 1 under compiler 1; both
now contain the freshly admitted compiler-2 entry documented below.
No active query-catalog setting or pinned request was found in either inspected
workspace .leafcutter configuration directory. The code/query-file task does not
assert a browser favorites migration.

## Verification plan

Run focused behavioral tests for native statement emission and execution,
repository/generation isolation, retained catalog integrity and tampering
rejection, native-only inspection and explicit saved-query replacement. Run changed-file lint and
annotation checks. Do not run the removed full pytest suite or mutate Aura.
The current-scope results below record actual execution separately from the
superseded compatibility-preserving run.

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
- name: test_native_catalog_preserves_active_and_retained_pins
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: Public retrieval preserves admitted native active and retained identities, immutable receipt bytes, scopes and bounded execution.
  framework: pytest
  type: unit
  angle: boundary
- name: test_unsupported_catalog_compiler_requires_readmission
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: Obsolete or unknown compiler versions refuse without changing stored evidence and require fresh native admission.
  framework: pytest
  type: unit
  angle: failure
- name: test_stale_or_missing_verification_cannot_be_reused
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: A current compiled entry cannot reuse missing or obsolete compiler verification.
  framework: pytest
  type: unit
  angle: failure
- name: test_missing_pinned_digest_never_falls_back_to_active_query
  file: tests/knowledge/test_query_native_compile.py
  covers: [KM-400a-3-i]
  asserts: A removed digest is rejected rather than substituted with the current active operation.
  framework: pytest
  type: unit
  angle: boundary
- name: test_native_inspection_is_read_only_and_preserves_evidence
  file: tests/knowledge_live/native_inspection_checks.py
  covers: [KM-400a-3-i]
  asserts: Inspection validates retained native snapshots without changing their physical or canonical evidence.
  framework: pytest
  type: integration
  angle: real_artifact
- name: test_publication_rejects_unsupported_control_schema_without_mutation
  file: tests/knowledge_live/native_inspection_checks.py
  covers: [KM-400a-3-i]
  asserts: Publication and pointer switching refuse unsupported control records before any write.
  framework: pytest
  type: integration
  angle: boundary
```

## Current native-only verification

Compiler coder: the targeted obsolete-compiler and stale-proof tests first failed
in six cases before production edits. The focused five-module compiler/catalog
suite then passed 78 tests in 30.42 seconds. Ruff and mypy passed over the five
surviving compiler modules (Ruff also checked the test module).

Adapter coder: native read, index naming and prewrite refusal checks each exposed
a failing baseline; the final two unittest modules passed nine tests. All 15
existing refresh-recovery parameter cases passed by direct execution. Ruff passed
nine changed/new files and mypy passed seven files.

Independent root: 19 real-Neo4j cases passed across domain graph, native
inspection, vectors and catalog execution. They include read-only corruption,
missing-relationship, contradictory-label, foreign-repository and cross-generation
refusal, safe publication/rollback, and native vector index behavior. A read-only
Aura inventory found no vector indexes or old vector labels requiring cutover.

The two actual saved catalogs were backed up and atomically replaced under a
lock and unchanged-original-bytes check at 2026-10-09T09:43:43Z. Each retains its
one original descriptor and operation version 1. Fresh Aura verification at its
original pinned source passed positive (four expected tests), empty, invalid-input,
injection and foreign-scope checks. No Aura data was written. Independent review
confirmed original backup/current file hashes, descriptor equality, one-entry
retention, native compiled bytes, active-pointer mapping and proof integrity.

After compatibility removal, a fresh process exercised QueryCatalog.request,
build_retriever and retrieve for both catalogs: four public reopen checks passed
(two positive results of four and two empty results), without truncation and with
the new operation digest. The sanitized committed receipt is
reports/neo4j-native-query-cutover-2026-10-09.json; private backups and full run
receipts remain outside Git. Historical checkpoint/deployment pins are retained
as history; the inspected local .leafcutter configurations contain no active old
pinned consumer requiring another update.

## Prior implementation verification (superseded scope)

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

## Prior documentation extraction verification

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

- [x] python-coder — 2026-10-09 09:52
- [x] code-review — 2026-10-09 09:56

- [x] commit — 2026-10-09 10:21

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
  historical_seam_review:
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

### 2026-10-09 09:42 - code-review (status: handoff)
feedback-id: (submit-failed)
The user's explicit new scope removes every legacy compatibility path and updates
actual saved catalogs. Reopening code-review and handing the new implementation
back to python-coder and subsequent packaging to commit. Earlier successful
phase comments remain evidence for the previous scope only. The feedback writer
again rejected the unregistered code-review role; the documented submit-failed
fallback applies. No new implementation or saved-catalog migration is signed off.

### 2026-10-09 09:52 - python-coder (status: ok)
feedback-id: fb_2026-10-09_64382923
completion_manifest:
  obsolete_compiler_and_fixture_removed: true
  native_only_catalog_admission_enforced: true
  saved_catalog_backups_and_fresh_proofs_verified: true
  retired_digest_pins_refused: true
  focused_tests_green: true
  lint_and_annotations_green: true
  cross_layer_seam_answer:
    result: covered
    producing_side: knowledge.query_compile.compile_query and knowledge.query_admission.QueryAdmission
    consuming_side: knowledge.query_store.validate_entry and knowledge.query_execution.execute_query
Removed the obsolete compiler, fixture and private descriptor compiler provenance;
native-only catalog validation now requires current compiler output and current
fresh verification instead of accepting a rehashed stale proof. Before removal,
independently checked both actual migrated catalogs, fresh proof hashes, receipt
mappings and byte-identical original backups; both native catalog getters still
validate and both retired exact pins explicitly refuse. Captured six expected
failing regression cases before implementation, then 78 focused cases passed in
30.42 seconds, with clean Ruff and Mypy over five surviving production modules.
Root separately verified four public Aura catalog reopen/retrieval cases under
the final code. This supersedes the earlier compatibility-scope coder signoff
and claims only the completed python-coder phase.

### 2026-10-09 09:56 - code-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  native_only_compiler_catalog_contract_reviewed: true
  native_inspection_and_prewrite_refusal_reviewed: true
  vector_identifier_boundary_reviewed: true
  actual_catalog_cutover_and_reopen_evidence_reviewed: true
  active_test_and_documentation_links_validated: true
Independent review found no unresolved findings in the current native-only changes.
The compiler/store boundary rejects obsolete compilation and stale verification;
public requests reject retired pins, while current native retained versions remain
addressable. Native inspection preserves canonical payload, count and ownership
checks; unsupported control records are refused before publication writes. Vector
identifiers use the trusted native namespace, with root's inventory confirming no
deployed vector indexes required replacement. The current coder seam declaration
covers compiler/admission through catalog validation and runtime execution; the
older declaration is retained under historical_seam_review for its original scope.

Independently checked the actual catalog replacement hashes, original descriptor
retention, native compiled identities and proof integrity; the sanitized report
includes all four fresh public reopen outcomes. Reviewed reported 78 compiler,
nine adapter unit, 15 recovery and 19 real-Neo4j passing cases. AC schema, all
current declared-file and covered-test references, local documentation links and
anchors, staged doc-length/frontmatter and whitespace checks passed. The feedback
writer rejects the unregistered code-review role; this uses the skill's documented
submit-failed fallback. This signs off only the actual code-review phase. Packaging
and CI for the expanded scope remain separate; no commit or merge is claimed.

### 2026-10-09 09:57 - commit (status: ok)
feedback-id: fb_2026-10-09_2be19b20
completion_manifest:
  expanded_scope_authorized_and_reviewed: true
  hook_probe_pass: true
Auto-authorized commit gate for the user's expanded legacy-removal request:
subject "refactor(knowledge): retire legacy Neo4j compatibility". The approved
incremental scope is 29 paths, including explicit deletions, native inspection,
updated source-AC links, saved-query cutover receipt and the generated docs index.
The existing files_touched ledger covers the cumulative PR scope. Earlier commit
comments remain historical evidence; this expanded commit phase is reopened and
the ticket remains in_progress until the normal hooks and commit finish.

### 2026-10-09 10:21 - commit (status: ok)
feedback-id: fb_2026-10-09_27342b50
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Completed the user-expanded cleanup in two dependent commits:
05cfe162a01442b616d3eef157de429d959d1870 replaces obsolete compatibility coverage;
1f3b2f444a07dce59a41bdffe0de7a15164360d3 retires legacy Neo4j compatibility and
records the saved-query cutover. The contract-shrinking hook required the separate
test commit; the AC governance hook required truthful amendment attribution,
provided after the actual business-analyst review. All applicable normal hooks
passed for both commits, including AC governance, schema and Done Proof. No hook
was bypassed, no full pytest suite was run and no graph data was changed by this
commit phase. Verified HEAD advanced. The aggregate scope is the approved 29
paths, with native inspection represented as a rename. Earlier phase comments
remain historical evidence. This signs off only the completed commit phase;
updated PR publication, hosted CI and merge are not claimed here. Knowledge
capture was considered; the two resolved gates already document their remedies.
