# Run report run-efa1fb21ac674df0

- Status: completed
- Task: What behavior does KM-500c-2 require?

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
  "original_question": "What behavior does KM-500c-2 require?",
  "rationale": "The request concerns only the required behavior of one criterion, which is expressed by its acceptance clauses.",
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
      "criteria"
    ],
    "target_ids": [
      "KM-500c-2"
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

- work-6dc33da8647f443a: completed (depth 0)
