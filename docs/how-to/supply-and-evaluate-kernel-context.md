---
title: "How to supply and evaluate kernel context enrichment"
description: "Supply caller context, configure the bounded pre-intent gathering pass, and run isolated and paired intent evaluations."
type: how-to
status: active
created: 2026-10-02
last_updated: 2026-10-02
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/architecture/components/decision-kernel.md
related_code:
  - kernel/context_enrichment.py
  - kernel/enrichment_projection.py
  - kernel/config_context.py
  - tests/kernel/enrichment/eval_runner.py
  - tests/kernel/enrichment/live_eval.py
---

# How to supply and evaluate kernel context enrichment

First follow [How to run the decision kernel](run-the-decision-kernel.md) for credentials,
configuration and the run/resume workflow. This guide covers the context pass before intent.

## Context before intent

Every new task first gets one bounded, read-only context pass. It gathers workspace identity,
registered capabilities and relevant excerpts from permitted repository sources. The original
goal is preserved verbatim. Source ids, locators and content hashes make the excerpts auditable;
registered capabilities and documentation describe the integration, but do not prove that a live
kernel call or external service has succeeded.

Supply relevant host and conversation context explicitly in the optional `context` object:

```json
{
  "goal": "Can you use leafcutter now? I mean run the kernel and know about it?",
  "caller": {"id": "codex", "kind": "host"},
  "scope": {"workspace_id": "leafcutter", "repository_root": "C:/Users/me/leafcutter"},
  "context": {
    "host": "Codex desktop session",
    "capabilities": ["Can invoke the local Python kernel CLI"],
    "conversation": ["The user is asking about the installed Leafcutter integration."],
    "observations": ["No live availability check has been performed in this session."]
  }
}
```

These fields are caller-supplied claims, kept separate from gathered evidence. The kernel cannot
read the chat implicitly. Supply only context needed to interpret the request. Neither supplied
claims nor retrieved instructions grant permissions, approve actions, or choose user preferences.

`context_enrichment` in the config controls `enabled`, `source_ids`, `max_sources`, `max_files`,
`max_evidence`, `max_excerpt_chars`, `max_chars` (total excerpt text), `max_context_chars` (caller
context) and `max_seconds`. Retrieval still obeys the source catalog, task read roots, deny rules,
redaction and data policy. This pass performs no Jev call or host operation and never waits for a
human. It is an initial grounding pass, not recursive research or a live runtime probe.

The run checkpoints its context and emits `context.enriched` before `intent.assessed`. Its status
is `gathered`, `no_evidence`, `partial`, `unavailable` or `disabled`, with limitations and
truncation recorded honestly. Intent receives that outcome and may still ask about a missing
preference, unclear user intent or a fact the available context cannot establish. An explicit
output contract skips automatic answer-kind selection, but still gets context enrichment. Resume
uses the same run's checkpointed context; a new task starts a fresh pass.

The same saved context travels into native research and decision judgments and into the host's
input artifact with provenance and trust boundaries attached. Supplied conversation and
observations also inform later repository query hints, so a resolved reference remains usable
after intent classification. The Claude Code and Codex adapters supply relevant context they already know;
other callers can populate the same `TaskInput.context` fields.

Enrichment shares the receiving Jev batch's `jev.max_state_chars` allowance. When a complete
snapshot will not fit alongside the request, its optional context projection is shortened and
marked as truncated; the original request and full checkpointed snapshot stay intact. If even
a small truncation marker cannot fit, context is omitted from that batch with a warning. Context
does not increase the configured provider payload limit. Repository excerpts are withheld when
`data_policy.send_repo_excerpts_to_jev` is false.

The isolated, offline enrichment eval invokes production gathering without intent or final-answer
grading:

```bash
python -m tests.kernel.enrichment.eval_runner --output reports/context-enrichment-eval.json
python -m pytest tests/kernel/enrichment tests/kernel/intent/test_context_enrichment_wiring.py -q
```

The labelled cases live in `tests/kernel/fixtures/eval/context_enrichment.json`; case results cover
relevant-source discovery, provenance, caller context, unknowns, read scope, redaction and bounds.
The [2026-10-02 isolated report](../../reports/context-enrichment-eval-2026-10-02.json) records
10/10 cases passing with zero Jev calls.
The [regression mutation report](../../reports/context-enrichment-mutations-2026-10-02.json)
records eight deliberately broken variants detected by the tests, covering field limits,
conversation priority, retained-text hashes, payload projection and data-policy enforcement.
The variants were applied in memory; production files were not modified.

To measure the effect on real intent classification, set `LEAFCUTTER_KERNEL_LIVE=1` in the
environment and run the separate paired probe with configured Jev credentials:

```bash
python -m tests.kernel.enrichment.live_eval --output reports/context-enrichment-live-eval.json
```

It makes at most ten assessments: five cases with and without enrichment, using the same current
intent prompt. The [2026-10-02 live report](../../reports/context-enrichment-live-eval-2026-10-02.json)
records 5/5 expected enriched labels with ten Jev calls. In that run, "Same for Zephyr, please."
changed from `insufficient_context` to `ideas`; the original Leafcutter availability question
was `evidence` in both arms. A preference-dependent choice stayed `decision`, and "That." stayed
`insufficient_context`. This small probe records one observation per arm; it does not establish a
general improvement rate, prove live runtime availability, or show that enrichment alone fixed
the earlier availability-question failure.

## Answer kinds after enrichment

**What kind of answer does the goal need?** When you do not set `requested_output_schema`, the
kernel asks Jev one bounded question about the goal and enriched context and picks the answer kind itself:

| Answer kind | The goal asks to... | Result |
|---|---|---|
| `decision` | choose between options or approaches, or decide what to do | `decision_report.v1` from the decision capability |
| `evidence` | find or locate facts in this repository | `evidence_bundle.v1` from research |
| `ideas` | generate options or ideas without deciding | `options.v1` from `host.generate_options`; every option stays `proposed` |
| `change` | implement, edit or modify something | declined: status `blocked`, limitation `out_of_scope_write` (the V0 kernel is read-only) |
| `out_of_domain` | something unrelated to software engineering or this repository | declined: status `blocked`, limitation `out_of_domain`; never a build opportunity |

If Jev is unsure (thresholds in `config.intent`), the run pauses with a question that offers these
kinds as choices; free text is allowed, and the answer is classified again as the new statement of
the goal. At most `intent.max_clarifications` questions are asked; after that the run ends with a
plain `unclear_request` message and a suggested rephrasing. If Jev is unavailable the default
`decision_report` is kept. **To bypass the classification set `requested_output_schema`
yourself** (`leafcutter.decision_report.v1`, `leafcutter.evidence_bundle.v1` or
`leafcutter.options.v1`), or supply a typed `input_payload`; an explicit choice always wins.
