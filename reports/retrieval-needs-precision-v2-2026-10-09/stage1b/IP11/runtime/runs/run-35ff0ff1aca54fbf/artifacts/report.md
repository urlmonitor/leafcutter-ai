# Run report run-35ff0ff1aca54fbf

- Status: completed
- Task: Did KM-500c-2's tests pass on the latest CI run? Cite the run and tested commit.

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
  "original_question": "Did KM-500c-2's tests pass on the latest CI run? Cite the run and tested commit.",
  "rationale": "The literal criterion is the anchor, but the requested answer concerns execution evidence absent from the offered catalog. Coverage references could be a discovery lead, but they are not requested execution facts.",
  "schema_version": "1.0",
  "scope_resolution": "unknown",
  "selections": {
    "document_types": [],
    "entity_types": [],
    "relationships": [],
    "required_fields": [],
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
    "The catalog does not represent latest CI test-execution outcomes, the corresponding run reference, or the tested commit. Source revision, lifecycle status, implementation progress and test specifications cannot substitute for these facts.",
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

- work-cadc697d19e0408a: completed (depth 0)
