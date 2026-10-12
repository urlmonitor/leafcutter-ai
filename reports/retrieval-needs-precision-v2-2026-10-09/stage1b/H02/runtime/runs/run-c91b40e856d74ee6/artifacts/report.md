# Run report run-c91b40e856d74ee6

- Status: completed
- Task: Show a source excerpt from one test linked to KM-500a-2 as a covering test.

## Output

Schema: `leafcutter.retrieval_needs_output.v1`

```json
{
  "completeness": "examples",
  "detail_mode": "fields",
  "engine": "host_llm",
  "hierarchy_levels": [],
  "hierarchy_scope": "not_applicable",
  "model_id": null,
  "original_question": "Show a source excerpt from one test linked to KM-500a-2 as a covering test.",
  "rationale": "A source excerpt requires content from a linked covering test record. The named criterion anchors the coverage relationship, and one example is sufficient.",
  "schema_version": "1.0",
  "scope_resolution": "sufficient",
  "selections": {
    "document_types": [
      "code"
    ],
    "entity_types": [
      "test"
    ],
    "relationships": [
      "covered_by"
    ],
    "required_fields": [
      "content"
    ],
    "target_ids": [
      "KM-500a-2"
    ]
  },
  "source_scope": {
    "read_roots": [
      "docs"
    ],
    "repository_id": "leafcutter",
    "revision": "2a8ebc87ce937a0a2fec65ab26220f79a72e4859",
    "source_ids": [
      "knowledge.graph"
    ]
  },
  "status": "decided",
  "uncertain": {
    "document_types": [],
    "entity_types": [],
    "relationships": [],
    "required_fields": [],
    "target_ids": []
  },
  "unresolved": []
}
```

## Limitations

- host-reported; not verified by the kernel
- Interpretation only; no retrieval executed and no answer correctness or classifier approval established.

## Work items

- work-c215525b485349b5: completed (depth 0)
