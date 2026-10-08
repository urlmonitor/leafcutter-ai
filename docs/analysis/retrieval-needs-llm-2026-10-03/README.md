---
title: Isolated LLM retrieval-needs experiment
description: Historical analysis and saved observations for Isolated LLM retrieval-needs
  experiment.
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# Isolated LLM retrieval-needs experiment

The new alternative uses a real kernel host wait and schema-bound submission to interpret which information a retrieval question needs. It does not execute retrieval or activate a production capability. **The blind host passed 8/12 shared semantic checks and 7/7 applicable prospective minimality/consistency checks.** All twelve interpretations were accepted and completed by the kernel; this does not establish answer correctness.

Read the [verified outcome and example](../../../reports/retrieval-needs-llm-2026-10-03-accepted/README.md) and [all twelve expected-versus-actual results](../../../reports/retrieval-needs-llm-2026-10-03-accepted/results.md). Three exact-AC cases omitted the required `criteria` field; the unsupported-payroll case expressed the right uncertainty with the wrong exact marker format. The prior Jev shared result is 7/12, with 1/7 on the separate overlay.

The [independent review](../retrieval-needs-llm-probe-2026-10-03/independent-review.md) confirms the accepted ledgers, unchanged payloads and gold, source freeze, and both sets of scores.

The comparison uses the same twelve original questions, finite offered catalogs and synthetic context as the Jev probe. Gold was retained unchanged. The [prospective comparison contract](evaluation-contract.json) defines common semantic checks and a separate minimality/consistency overlay before any LLM answers. The prior Jev score remains 7/12 under its original checks.

This is an exploratory comparison of equal questions, context and offered meanings, not byte-identical model prompts. The host flow has different operational instructions and paraphrases target-ID descriptions. Protocol acceptance and semantic readiness are reported separately.

Prepared receipts are under [the evaluation directory](../../../reports/retrieval-needs-llm-2026-10-03-evaluation/host-location.json). They include a [freeze](../../../reports/retrieval-needs-llm-2026-10-03-evaluation/freeze.json), twelve actual host packets and exact byte copies of their operational inputs. The public manifest exposes only packet/input references and response destinations. The blind host receives no gold, previous Jev answers, repository excerpts or automatic context enrichment.

The first controller actor ID contained forbidden slashes and all wrappers were rejected. The same untouched responses were then submitted with a valid encoding of the actual actor. [Durable ledger evidence](../../../reports/retrieval-needs-llm-2026-10-03-accepted/acceptance-proof.json) proves zero acceptances before this wrapper repair and exactly one acceptance per run afterwards. No model rerun occurred. The frozen controller incorrectly labels the issued-operation counter as accepted operations; the verified report discloses this and uses the ledger instead.

## Deterministic evidence

- **76 tests and 82 subtests passed in 29.74 seconds**, with `AC_ENFORCE_STRICT=1`, against the new isolated flow, existing host end-to-end/security/submission boundaries and schema catalog. This includes all eighteen new controlled tests; these fixtures are not model-quality evidence.
- The existing query-build host fixture lacked mappings despite already appearing in the legacy schema table. The narrow fixture repair restores those positive regression cases. Adding query-build to the existing forbidden-authority table was verified separately: **9 security tests and 27 subtests passed in 8.18 seconds**.
- Ruff passed for the controller, new tests, restart helper and touched schema/host-rig tests.
- Tests exercised actual host input artifacts, request-bound output validation before acceptance, immutable question/scope, forged fields/IDs/authority, cold process restart, idempotency, multiple IDs/document types/relations, unsupported needs and honest missing model metadata.
- Meaningful REDs preceded the corrections: unexplained `needs_resolution` was silently promoted; thirty-two explicit reasons plus a derived gap overflowed the output schema; overlong host model metadata raised an uncaught conversion error. Final tests require rejection or an honest failed result, never promotion or an uncaught exception.
- One initial assertion incorrectly expected no enrichment record. The kernel correctly stores a disabled diagnostic with zero scanned files/evidence. The assertion now verifies this actual boundary; it does not erase the diagnostic.

The main strict command was:

```text
python -m pytest tests/kernel/retrieval/test_retrieval_needs_llm.py tests/kernel/interaction/test_host_end_to_end.py tests/kernel/interaction/test_host_security.py tests/kernel/interaction/test_submissions.py tests/kernel/contracts/test_schema_catalog.py -q -p no:cacheprovider --basetemp <dedicated external temporary directory>
```

The first prepare attempt failed locally before creating a host wait because the earlier typed catalog included a nested schema-version property. The controller now maps only the five option dictionaries into the host request, whose own version field remains intact. The failed prepare freeze/location are preserved in `reports/retrieval-needs-llm-2026-10-03/`; the successful trial has a fresh freeze in the evaluation directory.

## Interpretation limits

A real blind Codex agent performs the host work. This trial does not invoke a configured generative-provider endpoint directly. Twelve accepted host operations would not prove twelve underlying model requests: one host-agent turn can process multiple packets. Model identity, token counts and request counts remain unknown without an actual receipt. Completing this interpretation does not answer the retrieval question or prove source completeness.
