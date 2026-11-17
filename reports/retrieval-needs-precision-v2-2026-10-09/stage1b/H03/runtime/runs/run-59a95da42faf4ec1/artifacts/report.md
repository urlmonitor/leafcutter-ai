# Run report run-59a95da42faf4ec1

- Status: completed
- Task: Return the complete set of source locators for test records linked as covering KM-500c-1.

## Output

Schema: `leafcutter.retrieval_needs_output.v1`

```json
{
  "completeness": "exhaustive_set",
  "detail_mode": "fields",
  "engine": "host_llm",
  "hierarchy_levels": [],
  "hierarchy_scope": "not_applicable",
  "model_id": null,
  "original_question": "Return the complete set of source locators for test records linked as covering KM-500c-1.",
  "rationale": "The requested population is every test record linked as covering the named criterion, and the requested fact for each is its source locator. Full coverage of this linked set is required.",
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
      "source_locator"
    ],
    "target_ids": [
      "KM-500c-1"
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

- work-87c27e5c9d0844a7: completed (depth 0)
