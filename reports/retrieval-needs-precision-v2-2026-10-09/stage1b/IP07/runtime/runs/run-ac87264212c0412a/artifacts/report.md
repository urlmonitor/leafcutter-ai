# Run report run-ac87264212c0412a

- Status: completed
- Task: List only the declared test references on KM-500c-2; do not inspect their implementations or infer outcomes.

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
  "original_question": "List only the declared test references on KM-500c-2; do not inspect their implementations or infer outcomes.",
  "rationale": "The requested facts are the declared test-reference values stored on the criterion. The question does not request facts from linked test records.",
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
      "covered_by"
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

- work-038a6c762c964ce5: completed (depth 0)
