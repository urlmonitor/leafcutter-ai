# Run report run-72f17b89c0bb4c5c

- Status: completed
- Task: For KM-500c-2, what must tests demonstrate?

## Key evidence

The run recorded no separate findings; these are the most relevant excerpts as found.

- knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Fcriteria: Given the original research has obtained results from an existing or newly verified query When its existing evidence evaluation decides whether the question can be answered Then the answer or evidence bundle cites the actual source revision...
- knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Ftest_spec: - name: test_km500_c_2_behavior target_dir: tests/knowledge/ framework: pytest type: integration angle: criterion description: Use actual research answer assessment to show relevant but insufficient evidence remains partial, contradictions ...

## Coverage

- need.question: satisfied

## Sources

- knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Fcriteria
- knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Ftest_spec

## Output

Schema: `leafcutter.evidence_bundle.v1`

```json
{
  "assessments": {
    "need.question": {
      "completeness": {
        "complete": true,
        "exact_total": 1,
        "known_count": 1,
        "limitations": []
      },
      "kind": "retrieval_answer",
      "known_work_status_counts": {},
      "limitations": [],
      "missing_fields": [],
      "original_question": "For KM-500c-2, what must tests demonstrate?",
      "required_fields": [
        "criteria",
        "test_spec"
      ],
      "scope": {
        "entity_ids": [
          "KM-500c-2"
        ],
        "inclusion": null,
        "levels": null,
        "population": "returned_entities",
        "root_id": null
      },
      "status": "fulfilled",
      "work_status_counts": null
    }
  },
  "attempted_sources": [
    "knowledge.graph"
  ],
  "contradictions": [],
  "coverage": {
    "need.question": "satisfied"
  },
  "evidence": [
    {
      "access": "internal",
      "artifact_ref": null,
      "category": "task_context",
      "content_hash": "9cfea912e97757a50beaab42e39ccfd82dd6f2bbf0d6e9425daf3e1d9e2617d3",
      "created_at": "2026-10-10T06:21:22.770979Z",
      "created_seq": 0,
      "excerpt": "Given the original research has obtained results from an existing or newly verified query\nWhen its existing evidence evaluation decides whether the question can be answered\nThen the answer or evidence bundle cites the actual source revision and retrieved items and states which required needs remain unsatisfied\nAnd a successful build, successful query execution and successful answer assessment remain separate recorded outcomes\nAnd zero matches, contradictory evidence and insufficient evidence remain distinguishable with their limitations intact\nAnd any bounded synthesis or follow-up uses the existing research policy rather than silently treating query availability as answer quality.\n",
      "id": "ev-936fb478e09f82b0",
      "limitations": [
        "Derived graph context (not a source quote; scores are ranking signals): {\"seed_id\":null,\"signals\":{},\"path\":[],\"relationships\":[{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"68d2ad4837860e0ae8f8ab1229fcbe58bace4d7ee62ef0832f38f7f3c9daefb4\"},\"source_id\":\"KM-500c\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"covered_by\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"KM-500c\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"228c674c417e3fceef08d43dd844816f1c57c5c20a771719873082b9c2c6da13\"},\"source_id\":\"KM-500e-2\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500f-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"6d0a81e7e391e5834713d3b732ef2b6bb3c9fa4dab76ff0fbe5d73db2a014106\"},\"source_id\":\"KM-500f-2\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500g-1.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"a309e1b0697278034b1b9800a11774c857992773af0727d1651e398fbf6a26d3\"},\"source_id\":\"KM-500g-1\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/components\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"knowledge_management\",\"edge_type\":\"component_membership\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_conflict_recorded\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_failed_child_is_a_limitation_never_an_empty_result\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_unsatisfied_required_need_makes_the_bundle_partial\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestSynthesisAndStop::test_synthesis_resume_finishes_without_replanning_or_more_jev_calls\"}],\"related\":[{\"canonical_id\":\"KM-500c\",\"title\":\"Continue the original research with evidence you can assess\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500e-2\",\"title\":\"Return canonical fields and clauses without changing their meaning\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500f-2\",\"title\":\"Keep declared coverage executed proof and deployment proof separate\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500g-1\",\"title\":\"Show execution and original-question fulfillment in the same observable attempt\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"knowledge_management\",\"title\":\"Knowledge Management\",\"kind\":\"Component\"},{\"canonical_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"title\":\"test_research_graph.py\",\"kind\":\"Test\"}]}"
      ],
      "provenance": {
        "actor": null,
        "invocation_id": "inv-c3edabfd48434271",
        "producer": "knowledge.retrieval",
        "query": null,
        "rank": null,
        "relayed_by": null,
        "relevance": null,
        "schema_version": "1.0",
        "strategy": "knowledge:8377a65a-a9b9-4520-b886-040892d8300f",
        "terms": []
      },
      "schema_version": "1.0",
      "semantic_type": "documentation_fact",
      "source": {
        "id": "knowledge.retrieval",
        "kind": "knowledge_node",
        "locator": "knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Fcriteria",
        "observed_modified_at": null,
        "retrieved_at": "2026-10-10T06:21:22.770979Z",
        "schema_version": "1.0",
        "section_locator": "/criteria",
        "source_version": {
          "commit": "2a8ebc87ce937a0a2fec65ab26220f79a72e4859",
          "dirty": false,
          "schema_version": "1.0"
        },
        "title": "Judge the original question against the evidence actually retrieved"
      },
      "truncated": false,
      "updated_at": "2026-10-10T06:21:22.770979Z",
      "verification": "unverified"
    },
    {
      "access": "internal",
      "artifact_ref": null,
      "category": "task_context",
      "content_hash": "0135126d0fdad3635c10e8dba48a9f0193aa89c4bee56f8085c3c690490398cf",
      "created_at": "2026-10-10T06:21:22.770643Z",
      "created_seq": 0,
      "excerpt": "- name: test_km500_c_2_behavior\n  target_dir: tests/knowledge/\n  framework: pytest\n  type: integration\n  angle: criterion\n  description: Use actual research answer assessment to show relevant but insufficient evidence remains partial,\n    contradictions persist, and newly retrieved evidence answers the original question without false certainty.\n  covers:\n  - KM-500c-2\n  requires_db: false\n",
      "id": "ev-b091d5737fea2ec2",
      "limitations": [
        "Derived graph context (not a source quote; scores are ranking signals): {\"seed_id\":null,\"signals\":{},\"path\":[],\"relationships\":[{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"68d2ad4837860e0ae8f8ab1229fcbe58bace4d7ee62ef0832f38f7f3c9daefb4\"},\"source_id\":\"KM-500c\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"covered_by\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"KM-500c\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"228c674c417e3fceef08d43dd844816f1c57c5c20a771719873082b9c2c6da13\"},\"source_id\":\"KM-500e-2\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500f-2.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"6d0a81e7e391e5834713d3b732ef2b6bb3c9fa4dab76ff0fbe5d73db2a014106\"},\"source_id\":\"KM-500f-2\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500g-1.yaml\",\"locator\":\"/depends_on\",\"content_hash\":\"a309e1b0697278034b1b9800a11774c857992773af0727d1651e398fbf6a26d3\"},\"source_id\":\"KM-500g-1\",\"target_id\":\"KM-500c-2\",\"edge_type\":\"depends_on\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/components\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"knowledge_management\",\"edge_type\":\"component_membership\",\"locator\":\"\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_conflict_recorded\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_failed_child_is_a_limitation_never_an_empty_result\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestCollect::test_unsatisfied_required_need_makes_the_bundle_partial\"},{\"source\":{\"repository_id\":\"leafcutter\",\"source_sha\":\"2a8ebc87ce937a0a2fec65ab26220f79a72e4859\",\"path\":\"docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml\",\"locator\":\"/covered_by\",\"content_hash\":\"785f641b0c92fbb15d795d782add2aa19807106a3ee2761cc9f1f9980b051c75\"},\"source_id\":\"KM-500c-2\",\"target_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"edge_type\":\"covered_by\",\"locator\":\"TestSynthesisAndStop::test_synthesis_resume_finishes_without_replanning_or_more_jev_calls\"}],\"related\":[{\"canonical_id\":\"KM-500c\",\"title\":\"Continue the original research with evidence you can assess\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500e-2\",\"title\":\"Return canonical fields and clauses without changing their meaning\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500f-2\",\"title\":\"Keep declared coverage executed proof and deployment proof separate\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"KM-500g-1\",\"title\":\"Show execution and original-question fulfillment in the same observable attempt\",\"kind\":\"AcceptanceCriterion\"},{\"canonical_id\":\"knowledge_management\",\"title\":\"Knowledge Management\",\"kind\":\"Component\"},{\"canonical_id\":\"tests/kernel/capabilities/test_research_graph.py\",\"title\":\"test_research_graph.py\",\"kind\":\"Test\"}]}"
      ],
      "provenance": {
        "actor": null,
        "invocation_id": "inv-c3edabfd48434271",
        "producer": "knowledge.retrieval",
        "query": null,
        "rank": null,
        "relayed_by": null,
        "relevance": null,
        "schema_version": "1.0",
        "strategy": "knowledge:8377a65a-a9b9-4520-b886-040892d8300f",
        "terms": []
      },
      "schema_version": "1.0",
      "semantic_type": "documentation_fact",
      "source": {
        "id": "knowledge.retrieval",
        "kind": "knowledge_node",
        "locator": "knowledge://leafcutter@2a8ebc87ce937a0a2fec65ab26220f79a72e4859/KM-500c-2?path=docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml&locator=%2Ftest_spec",
        "observed_modified_at": null,
        "retrieved_at": "2026-10-10T06:21:22.770643Z",
        "schema_version": "1.0",
        "section_locator": "/test_spec",
        "source_version": {
          "commit": "2a8ebc87ce937a0a2fec65ab26220f79a72e4859",
          "dirty": false,
          "schema_version": "1.0"
        },
        "title": "Judge the original question against the evidence actually retrieved"
      },
      "truncated": false,
      "updated_at": "2026-10-10T06:21:22.770643Z",
      "verification": "unverified"
    }
  ],
  "evidence_ids": [
    "ev-936fb478e09f82b0",
    "ev-b091d5737fea2ec2"
  ],
  "finding_ids": [],
  "findings": [],
  "limitations": [
    "knowledge status: ok",
    "retrieval choice: Jev selected a supported registered operation and authorized target",
    "Retrieved evidence requires the existing research sufficiency assessment."
  ],
  "need_evidence": {
    "need.question": [
      "ev-936fb478e09f82b0",
      "ev-b091d5737fea2ec2"
    ]
  },
  "need_limitations": {},
  "request_id": null,
  "schema_version": "1.0",
  "truncated": false,
  "unavailable_sources": [],
  "unknowns": []
}
```

## Work items

- work-4173f621a69247fb: completed (depth 0)
- work-f6af8ba3ea7746cd: completed (depth 1)
- work-076ce292073643c8: completed (depth 1)
