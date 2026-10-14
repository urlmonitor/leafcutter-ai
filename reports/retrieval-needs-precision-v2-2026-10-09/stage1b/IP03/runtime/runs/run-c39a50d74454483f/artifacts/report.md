# Run report run-c39a50d74454483f

- Status: completed
- Task: I am writing verification for KM-500a-2. Which required behaviors and prescribed checks must the tests prove?

## Output

Schema: `leafcutter.retrieval_needs_output.v1`

```json
{
  "completeness": "single_entity",
  "detail_mode": "fields",
  "engine": "host_llm",
  "hierarchy_levels": [],
  "hierarchy_scope": "not_applicable",
  "model_id": null,
  "original_question": "I am writing verification for KM-500a-2. Which required behaviors and prescribed checks must the tests prove?",
  "rationale": "Required behaviors correspond to acceptance clauses; prescribed checks correspond to the authored verification specification. Both are indispensable to this question about one criterion.",
  "schema_version": "1.0",
  "scope_resolution": "sufficient",
  "selections": {
    "document_types": [
      "ac_yaml"
    ],
    "entity_types": [
      "ac"
    ],
    "relationships": [],
    "required_fields": [
      "criteria",
      "test_spec"
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

- work-6e9ef9cdab3a404b: completed (depth 0)
