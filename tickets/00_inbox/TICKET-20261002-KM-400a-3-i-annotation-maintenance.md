---
title: Correct knowledge retrieval and native metadata annotations
description: User-requested annotation maintenance for the existing KM-400a-3-i delivery;
  no new product feature.
created: '2026-10-02'
status: in_progress
priority: medium
depends_on: []
components:
- knowledge_management
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
source_ac: KM-400a-3-i
ac_traceability:
  id: KM-400a-3-i
  path: docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-3-i.yaml
agents:
  commit: signed_off
  pull-request: needed
files_touched:
- .github/workflows/ci.yml
- integrations/knowledge_capability.py
- integrations/knowledge_execution.py
- integrations/knowledge_followups.py
- integrations/query_answer_planning.py
- integrations/query_graph.py
- integrations/query_growth.py
- integrations/query_planning.py
- kernel/bootstrap.py
- kernel/capabilities/research/assessments.py
- kernel/contracts/verbatim.py
- kernel/service_envelope.py
- knowledge/__main__.py
- knowledge/adapters/domain_schema.py
- knowledge/adapters/neo4j_backend.py
- knowledge/adapters/neo4j_domain_batches.py
- knowledge/adapters/neo4j_domain_build.py
- knowledge/adapters/neo4j_domain_migration.py
- knowledge/adapters/neo4j_projection.py
- knowledge/adapters/neo4j_queries.py
- knowledge/adapters/neo4j_vector_build.py
- knowledge/adapters/neo4j_vectors.py
- knowledge/answers.py
- knowledge/assessment_evidence.py
- knowledge/assessment_impact.py
- knowledge/assessment_interpretation.py
- knowledge/assessment_proof.py
- knowledge/assessment_readiness.py
- knowledge/assessments.py
- knowledge/capability_fit.py
- knowledge/cli_catalog.py
- knowledge/cli_sync.py
- knowledge/config.py
- knowledge/deadlines.py
- knowledge/disclosure.py
- knowledge/environment.py
- knowledge/errors.py
- knowledge/evaluation.py
- knowledge/hybrid.py
- knowledge/native_properties.py
- knowledge/native_types/decision.py
- knowledge/observation.py
- knowledge/populations.py
- knowledge/ports.py
- knowledge/projection/canonical_loader.py
- knowledge/projection/native_metadata.py
- knowledge/projection/validation.py
- knowledge/query_admission.py
- knowledge/query_execution.py
- knowledge/retrieval_steps.py
- knowledge/semantic.py
- knowledge/service.py
- tests/knowledge/test_native_agent.py
- tests/knowledge/test_native_capability.py
- tests/knowledge/test_native_component.py
- tests/knowledge/test_native_decision.py
- tests/knowledge/test_native_decision_corpus.py
- tests/knowledge/test_native_document.py
- tests/knowledge/test_native_flow.py
- tests/knowledge/test_native_glossary_term.py
- tests/knowledge/test_native_mock_data.py
- tests/knowledge/test_native_mockup.py
- tests/knowledge/test_native_properties.py
- tests/knowledge/test_native_roadmap_phase.py
- tests/knowledge/test_native_skill.py
- tests/knowledge/test_native_source_file.py
- tests/knowledge/test_native_test.py
- tests/knowledge/test_native_ticket.py
- tests/knowledge/test_query_admission.py
- changelogs/2026-10-02-1730-knowledge-retrieval-annotations.md
- tickets/00_inbox/TICKET-20261002-KM-400a-3-i-annotation-maintenance.md
---

# Correct knowledge retrieval and native metadata annotations

## Context

The user requested correction of the annotation errors reported after the native
metadata delivery. This maintenance follow-up uses the existing KM-400a-3-i
contract. The completed implementation ticket and its role statuses are unchanged.

## Implementation and verification

Concrete entity and backend contracts replace placeholder object annotations.
Validation helpers narrow optional values accurately, transaction callbacks retain
their result types, and native test documentation no longer resembles Python type
comments. The informational CI check includes changed production modules. The full
pytest job remains disabled.

The coding agents completed the changes and root reviewed them. Local mypy checked
125 original and changed targets with zero errors; CI-rule lint passed. Focused
native metadata tests passed 131 cases, CLI/configuration tests passed 36 cases,
core retrieval checks passed 45 cases, query admission passed 18 cases, and the
assessment/kernel contract checks passed 46 cases. These are scoped checks, not a
full-suite result. Publication and merge remain pending.

## Test Requirements

```yaml
tests:
- name: test_nested_metadata_round_trips_without_json_value_blobs
  file: tests/knowledge/test_native_properties.py
  covers: [KM-400a-3-i]
  asserts: Nested authored metadata retains values, types and structure after the annotation changes.
  framework: pytest
  type: unit
  angle: boundary
```

## Sign-offs

- [x] commit — 2026-10-02 17:45
- [ ] pull-request

## Comments

### 2026-10-02 17:39 - commit (status: ok)
feedback-id: fb_2026-10-02_c6fd6990
The user's existing PR and merge authorization covers this maintenance commit.
Planned subject: "fix(knowledge): correct retrieval and native metadata annotations".
The exact authorized file list is recorded in files_touched above. Worktree hook
configuration is isolated; the binary, config, installed hook and canary probe all
pass. Hook execution and the commit are pending; no unperformed phase is signed off.

### 2026-10-02 17:45 - commit (status: ok)
feedback-id: fb_2026-10-02_083dbfde
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
All applicable staged-file hooks passed in the worktree. The initial attempt was
blocked by a missing installed scanner dependency; isolated runtime provisioning
resolved it. The new maintenance ticket's required depends_on field was supplied.
The message accurately describes the reviewed annotation, validation and CI scope.
The authorized commit includes the exact files_touched list; publication remains
assigned to pull-request. No other phase sign-off is claimed.
