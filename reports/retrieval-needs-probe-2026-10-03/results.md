# Isolated Jev retrieval-needs evaluation

This tests only the proposed needs-selection step. It performs no retrieval and produces no final answer.

HTTP send attempts: **1**. Received HTTP responses: **0**. Frozen planning cases attempted: **1/12**. All-predicate passes: **0**. Invalid runs: **1**. A request event alone does not establish that the provider received or processed it.

Expected decisions were authored and independently reviewed before any live response. Each field is evaluated against one shared question/context in a single provider request. Thresholds remain 0.7 selected, 0.3 rejected; intermediate options remain uncertain.

| Case | Question | Result | Differences from preauthored expectation |
|---|---|---|---|
| N01 | For KM-500c-2, what must tests demonstrate? | INVALID | {'type': 'JevUnavailable', 'message': 'jev unavailable after 1 attempts: connection error calling jev (ConnectError)'} |

## N01: For KM-500c-2, what must tests demonstrate?

**Expected:** Retrieve the named criterion's required behavior. Test specification is useful if recorded, not mandatory when criteria are authoritative. No count population or parent/root clarification. Full bounded AC is an acceptable alternative to field projection.

No valid decision: `{'type': 'JevUnavailable', 'message': 'jev unavailable after 1 attempts: connection error calling jev (ConnectError)'}`. This is not a semantic-quality result.

[Request](N01.request.json) · [Actual wire request/response receipt](N01.receipt.json) · [Expected vs actual](N01.result.json)

## Limits of this evidence

The 29 original scenarios have a planning-only applicability map in summary.json. No full downstream scenario has been run by this probe. Topic membership, explicit allowed hierarchy levels, query choice, source completeness, evidence authority, retrieval budgets and final-answer correctness remain later work. An all-descendants need is retained separately from the proposed execution depth bound. `decided` means the interpretation is ready for later retrieval, not that its population or answer has been established. `needs_resolution` does not itself dispatch a human question.
