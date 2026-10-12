# Run report run-222c09f6167341a3

- Status: completed
- Task: Show the source of one test declared to cover KM-500c-2.

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
  "original_question": "Show the source of one test declared to cover KM-500c-2.",
  "rationale": "The question asks for the source text of one example test reached through the named criterion's declared coverage relationship. It does not request a whole source file or every covering test. The supplied source scope remains unchanged.",
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

- work-396898d7b41645c1: completed (depth 0)
