# Blind host trial: verified result

**8/12 cases met the frozen shared semantic checks. All twelve host responses were accepted by the kernel and completed the isolated interpretation.** The separate prospective minimality/consistency checks passed all seven applicable cases. Saved Jev outputs score 7/12 on the same shared checks and 1/7 on that separate overlay; its original 7/12 result remains unchanged.

| Evidence | Result |
|---|---|
| Durable accepted submission records | 12, exactly one per original run |
| Completed interpretation runs | 12 |
| Issued host operations | 12 |
| Jev calls during this host trial | 0 |
| Underlying model calls, tokens and exact model | Unknown |
| New model generation after first host outputs | None |

The [acceptance proof](acceptance-proof.json) verifies the durable submission ledger and completed state, and fingerprints [the raw host response bytes](raw-host-responses/N01.json). The [readable per-case results](results.md) show every selected and uncertain dimension, expected result, actual packet, operational input, response and kernel submission.

The [independent review](../../docs/analysis/retrieval-needs-llm-probe-2026-10-03/independent-review.md) separately confirms matching run/wait identities, all twelve accepted ledger hashes, unchanged raw payloads/input bytes, frozen source and both sets of semantic scores.

## What failed

- **N01, N09, N11: a required source field was omitted.** Each asks what tests must demonstrate for `KM-500c-2`. The host correctly retained the literal ID, chose the AC document, avoided population/hierarchy questions and selected `test_spec`. It omitted the frozen required `criteria` field. The test specification alone does not guarantee the acceptance criterion's authoritative behavior is covered. These are field-selection failures, despite structurally valid responses.
- **N10: the unsupported need was expressed with the wrong marker format.** The host honestly retained the unsupported payroll meaning and returned `needs_resolution`. It wrote an explanatory `needs_outside_catalog: ...` string, while the frozen predicate requires a separate exact `needs_outside_catalog` marker. This is an encoding-contract failure, not evidence that it invented a supported answer. Neither output nor gold was repaired.

The other eight cases passed their shared checks, including all-descendant counts, source discovery without an invented ID, parent context, multiple targets, separate lifecycle/work statuses and mixed ADR/schema sources. This measures interpretation only; no graph retrieval or final answer was executed.

## Example: the exact AC question

1. Input: **“For KM-500c-2, what must tests demonstrate?”** The host received the original question, finite offered labels and an unchanged bounded source-scope claim.
2. The kernel issued `interpret_retrieval_needs` with its real output schema and input artifact.
3. The blind host selected `ac`, literal `KM-500c-2`, `test_spec`, and `ac_yaml`. It selected no relationship and reported no uncertain dimensions.
4. It chose `fields`, `single_entity`, `not_applicable` hierarchy and `sufficient` scope, with status `decided`.
5. The kernel accepted the output as schema-valid, request-bound interpretation. The independent frozen semantic check still failed because `criteria` was missing.

See the [exact input](inputs/N01.input.json), [original response bytes](raw-host-responses/N01.json), [accepted ledger](accepted-ledgers/N01.json) and [expected-versus-actual checks](N01.result.json).

## Controller corrections and comparison limits

The first controller pass used `codex:/root/needs_llm_host`, an invalid actor ID because slashes are forbidden. All twelve wrapper attempts were rejected before evaluating their responses. [The original receipts](../retrieval-needs-llm-2026-10-03-evaluation/N01.result.json) remain unchanged. Before retrying, [the wrapper-repair receipt](wrapper-repair.json) verified all original waits and revisions were unchanged and no accepted ledger entry existed. The same blind responses were then submitted as `codex:root:needs_llm_host`, preserving canonical agent provenance `/root/needs_llm_host`. No model rerun occurred.

The frozen controller's `accepted_host_operations` summary label is a reporting defect: it reads `usage_summary.host_operations`, which counts issued waits. In the first rejected pass this label incorrectly says twelve accepted operations. This report instead uses the durable ledger: zero accepted before the wrapper repair, twelve after it. Source/controller bytes and both attempts were preserved rather than retroactively rewritten.

This is an exploratory comparison of equal original questions, supplied context and offered meanings, not byte-identical model prompts. Target-ID descriptions and operational instructions differ between engines. A fresh-context Codex agent provided the LLM responses; this was not a direct call to a configured generative-provider endpoint. Twelve accepted host operations do not establish twelve underlying model calls. Protocol acceptance, semantic correctness and readiness for production are distinct.

The [frozen comparison contract](../../docs/analysis/retrieval-needs-llm-2026-10-03/evaluation-contract.json) remains unchanged. All twenty-nine original scenarios retain their planning-only applicability dispositions in [the summary](summary.json). The experiment is not integrated into production retrieval.

## Remaining work for a subsequent experiment

- Make the authoritative acceptance-criterion field obligation clear enough that a test specification cannot silently replace it; validate on fresh exact-AC questions as well as these unchanged regressions.
- Give unsupported reasons a typed code separate from explanatory text, so an honest explanation cannot miss an exact marker contract.
- Fix the controller's default actor encoding and report accepted submissions from the ledger rather than the issued-operation counter. Preserve this trial's frozen controller and receipts as historical evidence.
- Re-evaluate a new frozen version before production integration. This trial does not test method selection, query execution, source completeness or end-to-end retrieval answers.
