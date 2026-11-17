---
title: "How to supply and evaluate kernel context enrichment"
description: "Prepare an entity index, supply caller context, inspect meanings before intent, and evaluate recognition separately from later research."
type: how-to
status: active
created: 2026-10-02
last_updated: 2026-10-03
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/architecture/components/decision-kernel.md
related_code:
  - kernel/entity_context.py
  - kernel/entity_index.py
  - kernel/entity_projection.py
  - kernel/config_entity.py
  - tests/kernel/entity_context/eval_runner.py
  - tests/kernel/entity_context/intent_eval.py
---

# How to supply and evaluate kernel context enrichment

First follow [How to run the decision kernel](run-the-decision-kernel.md) for credentials,
configuration and the run/resume workflow. This guide covers the context pass before intent.

## Context before intent

Every new task first gets one bounded, read-only entity recognition pass. It recognizes glossary
terms, document genres, knowledge destination kinds, native artifact kinds, Python declarations
and canonical artifact IDs. Intent receives compact definitions, declaration signatures or titles
with their provenance. Research retrieves supporting bodies only after intent has selected work.
Registered capabilities and definitions describe the integration; they do not prove that a live
kernel call or external service has succeeded.

Prepare the disposable local index explicitly before starting runs:

```bash
python -m kernel entities build --repository-root C:/Users/me/leafcutter
```

Use the same `--config` override for preparation and runs. The default index is
`.leafcutter/kernel/entity-index.json` inside the scoped repository. Rebuild it after changing
canonical sources, source configuration or readers. Preparation uses canonical native readers
and Python syntax parsing; it does not import the scoped repository's Python code.

Recognition reads the prepared index and checks its recorded filesystem metadata. It does not
build an index, search source bodies or call a model. Missing, stale or invalid data yields
explicit coverage limitations. There is no automatic lexical-search fallback. A later routed
capability can still retrieve evidence. Freshness checks detect ordinary edits, additions and
deletions; they are not tamper-proof filesystem attestation.

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

These fields are caller-supplied claims, kept separate from repository meanings. The kernel cannot
read the chat implicitly. Supply only context needed to interpret the request. Neither supplied
claims nor retrieved instructions grant permissions, approve actions, or choose user preferences.

`entity_context` controls the new pass. Defaults admit the entire goal up to 16,000 characters
without trimming whitespace, consider up to 12,000 characters of supplied context with newer
conversation first, perform at most 64 distinct lookups and return at most 16 identities. An
ambiguous name has at most three alternatives. Meanings and signatures are capped at 300
characters; the compact meaning projection has an 8,000-character serialized budget. At most
eight unknown references of 128 characters are retained. The recognition deadline is two
seconds. Configure these through `config/kernel_config.default.json` and overrides; goal
admission is a contract limit, not a runtime override.

The full admitted goal is scanned before bounded candidate selection. Repeated mentions share
one identity card. Coverage distinguishes a completed scan with omitted cards from a scan that
could not finish. Owner-declared aliases are honored; unknown names do not trigger a broad search
or automatically ask a human. Permission checks cover source IDs, read roots, deny rules,
resolved paths, redaction and data policy before names, counts or fingerprints are disclosed.

The run checkpoints `entity_context` and emits `context.recognized` before `intent.assessed`.
Outcomes are `recognized`, `no_matches`, `partial`, `unavailable` and `disabled`. Inspect
`entity.recognition`, `entity.resolution` and `entity.projection` for coverage, work, sizes and
limitations. Recognition makes zero Jev calls; intent and later research have their own calls.
An explicit output contract still gets recognition even when it skips automatic answer-kind
selection. Resume reuses the initial checkpoint, while later evidence has its own provenance.

Native judgments and host artifacts label meanings, caller claims and supporting evidence
separately. Resolved canonical references can guide later retrieval, which reapplies its read
policy. A meaning cannot prove live availability, fulfill an AC or approve a decision.

The native decision and flow sources are indexed for identity recognition but have
`automatic_research: false`. They enter later research through explicit source selection or a
resolved canonical locator, preserving ordinary category-based research behavior. If a native
reader validates a whole store, a narrower run withholds that kind when any required validation
input is denied; its coverage is partial regardless of the hidden input's contents.

On the entity path, the exact serialized Jev state-plus-questions envelope must fit
`jev.max_state_chars`. The original request and required question fields have priority over
optional context. Optional cards and caller projections are reduced with limitations, or omitted
with a warning if even a marker cannot fit. If required fields alone exceed the limit, the request
is rejected before a provider call. The checkpoint stays unchanged. Repository meanings are
withheld from both Jev and the host's optional entity context when
`data_policy.send_repo_excerpts_to_jev` is false; existing task-evidence handling remains a
separate downstream channel.

## Evaluate recognition independently

The isolated offline eval invokes production index preparation and recognition against labeled
fixtures. It scores exact identities, family precision and recall, offsets, provenance, permissions,
coverage and bounds. Empty corpora fail, and negative controls check that wrong identities,
permission bypasses and dropped goal tails cannot pass:

```bash
python -m tests.kernel.entity_context.eval_runner --output reports/entity-context-eval.json
python -m pytest tests/kernel/entity_context -q
```

Set `AC_ENFORCE_STRICT=1` while implementing ACs so a failing test for unfinished work cannot be
reported as an expected failure. Cases are in `tests/fixtures/entity_evaluation/corpus.json`.
The separate `tests.kernel.entity_context.intent_eval.run_pairs(provider)` harness compares
legacy lexical enrichment and entity meanings with identical caller context and records provider
usage. Its caller explicitly supplies either a controlled provider or a configured live Jev
adapter. A controlled-provider result establishes wiring; it is not a live model-quality result.
Neither recognition scores nor a small paired sample establish a general improvement in answers.
The [DK-300 verification report](../../reports/entity-context-verification.md) links the tests,
independent findings, correction loop, live comparison and known regression baseline.

## Existing runs and historical evidence

Old checkpoints retain `context_enrichment`, excerpt provenance and `context.enriched`; resume
does not relabel them or rebuild context. The old `context_enrichment` settings and standalone
`kernel.context_enrichment.gather_context` remain for compatibility. Fresh runs use
`entity_context`; disabling recognition does not restore lexical gathering.

The DK-200 direct-gather tests and the [2026-10-02 isolated report](../../reports/context-enrichment-eval-2026-10-02.json),
[mutation report](../../reports/context-enrichment-mutations-2026-10-02.json) and
[live paired report](../../reports/context-enrichment-live-eval-2026-10-02.json) describe the
historical excerpt implementation. They do not verify the DK-300 entity contract.

The fresh-run wiring criteria DK-200a-1, DK-200a-1-i, DK-200a-2 and DK-200a-4 were
explicitly amended on 2026-10-04 to retain their ordering, routing, snapshot and handoff
invariants under `EntityContext`. Their current test links prove those revised criteria;
their old lexical expectations remain in Git history. DK-300 defines the full new contract.

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
kinds as choices; free text is allowed and is classified as a separately recorded clarification
alongside the unchanged original goal. At most `intent.max_clarifications` questions are asked; after that the run ends with a
plain `unclear_request` message and a suggested rephrasing. If Jev is unavailable the default
`decision_report` is kept. **To bypass the classification set `requested_output_schema`
yourself** (`leafcutter.decision_report.v1`, `leafcutter.evidence_bundle.v1` or
`leafcutter.options.v1`), or supply a typed `input_payload`; an explicit choice always wins.
