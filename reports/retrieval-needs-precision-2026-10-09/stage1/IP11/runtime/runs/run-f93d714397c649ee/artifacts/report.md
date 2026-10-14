# Run report run-f93d714397c649ee

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
  "rationale": "The named criterion and its declared tests can be identified using offered meanings, but the requested outcome and run provenance require information outside the catalog. Source revision, work status, lifecycle status and authored test plans cannot substitute for execution evidence.",
  "schema_version": "1.0",
  "scope_resolution": "unknown",
  "selections": {
    "document_types": [
      "ac_yaml"
    ],
    "entity_types": [
      "ac"
    ],
    "relationships": [
      "covered_by"
    ],
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
    "The catalog cannot represent latest CI execution results, the CI run identity or the commit actually tested. Declared test references can identify relevant tests but cannot establish whether they passed. The supplied scope provides no confirmed CI execution source.",
    "scope_resolution"
  ]
}
```

## Limitations

- host-reported; not verified by the kernel
- Interpretation only; no retrieval executed and no answer correctness or classifier approval established.

## Work items

- work-27e36cfe31c84a5d: completed (depth 0)
