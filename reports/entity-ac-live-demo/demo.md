# Live AC question: GE-114-4

**Question:** What is GE-114-4 about? Explain it in plain language.

**Result:** The repaired live run recognized the bare identifier as an acceptance
criterion, selected evidence intent, retrieved the exact criteria field, and
returned one source-verified evidence item with satisfied coverage.

Run: `run-7599d5bd6e4041c9`, 2026-10-03, 18:42:42–18:42:46 UTC.

[Open the successful run in Langfuse](https://cloud.langfuse.com/project/cmuojt32z021fad0cdji8b19j/traces/0c3ba329c6280401b051499c65f75c39).
Use this individual trace to follow the run; the general observation list mixes
events and nested framework spans. Below are the recorded business steps in order.

## What actually happened

| UTC | Step | Observed behavior | Jev calls |
|---|---|---|---:|
| 18:42:42.737 | Start | Accepted the question with `read_repo` permission. | 0 |
| 18:42:44.408 | Recognize context | Found one entity: `GE-114-4`, family `artifact_id`, kind `AcceptanceCriterion`. Loaded its short meaning and canonical reference from a current local index. | 0 |
| 18:42:44.440 | Assess intent | Jev selected `evidence`; reported probability and confidence were both 1.0. These are provider scores, not measured accuracy. | 1 |
| 18:42:44.440–45.068 | Plan research | Routing selected `research` deterministically. Jev selected an `authoritative_guidance` evidence need. Research passed the canonical AC reference to retrieval. | 1 |
| 18:42:45.118–46.339 | Retrieve evidence | Routing selected `retrieve.repository` deterministically. It fetched `GE-114-4.yaml#/criteria` and retained its exact 399-character value. It also searched ordinary documentation and judged two batches of candidates. | 2 |
| 18:42:46.339–46.790 | Resume research | Research consumed the child evidence and made its final evidence assessment. No contradiction, open question or human clarification remained. | 1 |
| 18:42:46.840 | Finish | Returned one source-verified evidence item. `need.authoritative_guidance` was `satisfied`. | 0 |

Recognition used **one lookup, 1,732 serialized context characters, 1.659 seconds,
and zero model calls**. Its stored context contains the AC title and provenance;
the criteria body appears later as independently retrieved evidence. No index
rebuild occurred during intake. Explicit preparation before this run built 9,893
entities, all six recognition families current, with no limitations.

The whole run used **five Jev calls**, model `jev-1.13.0`, 21,440 input tokens and
1,070 output tokens. Reported cost was an estimate of $0.00090048. There were zero
host operations and no Anthropic calls. Kernel events span 4.102 seconds; the CLI
process took 7.740 seconds including startup and completion work. Trace export
reported `ok`.

## What the AC means

GE-114-4 protects existing ticket validation. Adding support for the newer flat
ticket format must preserve counting for tickets with an `Agent Contracts`
section and per-agent subsections. More than seven acceptance criteria for one
agent, or more than twenty for the whole ticket, must still produce the same
violation messages.

This paragraph is the host assistant's explanation of the evidence returned by
the kernel. The kernel's output is an evidence bundle, not a generated prose answer.

The returned evidence exactly matches the canonical `criteria` value after
trimming surrounding whitespace. Its locator remains
`docs/acceptance-criteria/guardrail-engine/GE-114-4.yaml#/criteria`; its content hash
is `c2e20eceb9cc1a94f7ff3ad2f124d72f3c5f4c78b4dcd43701fb888429145711`.
The evidence itself has no limitations and is not truncated.

## Limits of this demonstration

Early recognition is bounded, but downstream research still does broader work:
`repo.docs` scanned 482 files, the total candidate pool was capped at 60, and 19 of
59 non-explicit candidates were not judged. The bundle reports these search
limits and has `truncated: true`, although the selected AC evidence is complete.
This proves exact AC recognition and retrieval; it does not establish that research
avoids unnecessary searches for a simple identifier question.

No paired baseline was run for this actual AC, so the result does not prove entity
context caused Jev to choose evidence intent. One successful query does not
establish that every AC question or long prompt will succeed. Earlier preflight
files, including a deadline-limited recognition result, are retained separately.

## Failure found and repaired

The first approved live run recognized the same AC and selected research, but
retrieval misread `#/criteria` as a Markdown heading. It returned zero evidence
and open coverage despite the process status being `completed`.

[Preserved failed trace](https://cloud.langfuse.com/project/cmuojt32z021fad0cdji8b19j/traces/64e39d714096eb710100f0c917b2bdea).

The repair resolves exact YAML/JSON field pointers, retains canonical provenance,
and keeps existing read permissions and size bounds. Invalid or missing pointers
produce a limitation instead of falling back to the entire record. It changes
`kernel/capabilities/retrieval/locators.py` and
`knowledge/adapters/source_excerpt.py`, with tests and traceability under DK-300d-3.

- Six regression cases failed against the old implementation and pass after repair.
- Independent focused verification: 56 tests plus 3 subtests passed.
- Independent complete entity-context suite: 84 tests passed.
- Broader entity/retrieval/source-boundary suite: 267 tests plus 50 subtests passed.
- An in-memory mutation dropping the field selector was caught by all six cases;
  the restored implementation passed all six again.
- All 32 entity-context AC records validate; generated product truth is current.
- Ruff, documentation and complexity checks pass. Mypy passes with absent YAML
  stubs ignored; no dependencies were installed.

One concurrent test-collection run encountered a disappearing temporary directory;
the sequential rerun passed. The independent review records that anomaly. These
checks do not supersede the five pre-existing whole-kernel failures documented in
the wider feature report. No commit or merge was made for this repair.

## Evidence files

- [Independent repair review](../entity-native-pointer-independent-review.md)
- [Broader verification XML](../entity-native-pointer-core-broad.xml)
- [Canonical AC](../../docs/acceptance-criteria/guardrail-engine/GE-114-4.yaml)

Raw input, successful and failed envelopes, checkpoint exports, index receipts and
chronological events remain local evaluation artifacts. They are not included in
the PR. Their run identifiers and observed outcomes are retained in this report.

Earlier local preflight files and the prepared intent request are retained for
audit; they are not substitutes for the successful live evidence above.
