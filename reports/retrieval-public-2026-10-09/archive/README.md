# Retrieval receipt archive

`receipt-relocations.json` maps every original JSON path to its current path and SHA-256. All 312 JSON receipt bytes are preserved by this packaging step. Cases and attempts have their own folders so evidence can be reviewed without exceeding folder-density limits.

Embedded absolute paths and relative receipt strings inside the original JSON remain historical provenance. The relocation manifest is the current local index. Requests, responses, outcomes, budgets and tested runtime fingerprints were not rewritten. The controlled-count continuation was redacted earlier and carries separate redaction metadata.

The controller scripts are preserved historical tooling. Their command entrypoints refuse new execution in this immutable archive; a new evaluation needs a new output directory and its own frozen plan. Report readers resolve original receipt names through `report_support/layout.py`.
