# Run report run-1c77269a9dc1403b

- Status: completed
- Task: For KM-500a-2, give the latest CI execution verdict with its run reference and tested commit.

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
  "original_question": "For KM-500a-2, give the latest CI execution verdict with its run reference and tested commit.",
  "rationale": "The request concerns execution evidence for the literal criterion. The catalog cannot express that answer; test source or declared coverage could only provide optional discovery leads.",
  "schema_version": "1.0",
  "scope_resolution": "unknown",
  "selections": {
    "document_types": [],
    "entity_types": [],
    "relationships": [],
    "required_fields": [],
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
  "status": "needs_resolution",
  "uncertain": {
    "document_types": [],
    "entity_types": [],
    "relationships": [],
    "required_fields": [],
    "target_ids": []
  },
  "unresolved": [
    "needs_outside_catalog",
    "Latest CI execution verdict, run reference and tested commit have no offered execution-evidence representation. Canonical source revision and implementation or lifecycle status do not express the tested commit or execution outcome.",
    "entity_types",
    "document_types",
    "required_fields",
    "scope_resolution"
  ]
}
```

## Limitations

- host-reported; not verified by the kernel
- Interpretation only; no retrieval executed and no answer correctness or classifier approval established.

## Work items

- work-9f93ac924eda4f6c: completed (depth 0)
