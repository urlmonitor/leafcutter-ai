# Run report run-d71cd2ba0e234880

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
  "rationale": "Required behaviors map to criteria; prescribed checks map to test_spec. Both complementary obligations are explicitly requested for the named criterion.",
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

- work-df62bbe80ad641c8: completed (depth 0)
