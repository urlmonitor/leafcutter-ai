---
title: "The kernel gathers context before classifying intent"
date: "2026-10-02"
time: "12:28"
type: feature
components:
  - decision_kernel
summary: "New runs gather bounded local context before intent, then retain it through research and host handoffs. An isolated enrichment eval and a paired live intent probe check the behavior."
description: "Adds explicit caller context, permitted repository excerpts with provenance, checkpointed enrichment, honest missing-context outcomes and provider-budget-aware projections. Extends the existing decision lifecycle product truth and adds requirements DK-100 through DK-104."
---

Every new task gets one deterministic, read-only context pass before intent, including tasks
with explicit output contracts. The original request stays intact. Caller-supplied host and
conversation claims remain distinguishable from repository excerpts; registration or documentation
does not establish runtime availability. Source scope, redaction and configured bounds apply.

The kernel checkpoints the result and records `context.enriched` before `intent.assessed`.
Resumes reuse the saved context. Native research and decision judgments, later query hints and
host input artifacts receive that context with its provenance and trust boundaries. Optional
provider projections fit the existing payload allowance; they cannot override a user preference,
grant authority or expand the request. Missing evidence and incomplete gathering stay explicit.

Verification recorded on 2026-10-02:

- [Isolated enrichment eval](../reports/context-enrichment-eval-2026-10-02.json): 10/10 labelled
  cases passed, with zero Jev calls. Cases exercise relevance, provenance, request preservation,
  caller context, unknowns, scope, secrets, adversarial text and bounds.
- [Paired live intent probe](../reports/context-enrichment-live-eval-2026-10-02.json): 5/5 expected
  enriched labels, ten Jev calls. Both arms use the same current prompt. "Same for Zephyr, please."
  changed from `insufficient_context` to `ideas`. The original Leafcutter availability question
  was `evidence` in both arms; the preference case stayed `decision`, and "That." stayed
  `insufficient_context`.
- Focused enrichment and projection checks: 24 tests and 31 subtests passed. Scheduler
  integration checks: five tests passed, including downstream retrieval of a conversation's
  referent and checkpoint reuse on resume.
- [Mutation checks](../reports/context-enrichment-mutations-2026-10-02.json): all eight deliberately
  broken variants were detected, covering field limits, conversation priority, retained-text
  hashing, provider payload projection and data-policy enforcement. Production files were
  unchanged by these checks.
- Full kernel regression: 1,478 tests and 382 subtests passed; seven tests were skipped. The run
  completed in 898 seconds with one existing LangChain `TypeSafeClassifier` beta warning.
- Ruff passed. Kernel type checking passed across 162 files with only `import-untyped` disabled
  for existing third-party dependencies without typing stubs.

The live probe is one observation per arm and case, not a general improvement estimate. Its
unchanged original-question result does not demonstrate that enrichment caused that case to work.
DK-100 through DK-104 are implemented and verified. Product-truth and AC readiness remain
`draft`; execution evidence does not claim persona approval.

The subsequent user-requested BA and IT PO pass used the Claude agent prompts in
`templates/agents/business-analyst.md` and `templates/agents/it-po.md`. The preliminary
DK-100 through DK-104 records are retained as superseded history. The
[DK-200 hierarchy](../docs/acceptance-criteria/decision-kernel/DK-200-context-enrichment/DK-200.yaml)
now contains one outcome, four features, twelve behavioral criteria and twelve edge-case
criteria. IT PO added technical requirements and test contracts without changing BA criteria.

The [traceability audit](../reports/context-enrichment-ac-traceability-2026-10-02.json)
resolves all 47 exact test links to 32 methods and checks their reverse `# covers:` tags,
implementation references and immediate-parent backlinks. Focused verification passes
32 tests and 36 subtests, including added host-artifact/host-resume and native-decision
handoff checks, recent-conversation character limits, expanded-redaction limits and an
observable warning when no context marker fits. Coverage-tag edits preserve the tests'
parsed behavior. This follow-up changes requirements and tests, not production behavior.

Before publication, the feature was integrated with current main (`dd16b4a3`), retaining its
research fixes and adding context handoff to both Claude Code and Codex adapters. The four
kernel context-map documents now describe enrichment, and the detailed context/evaluation
instructions live in a linked how-to. The post-integration affected suite (enrichment, intent,
adapters, grounding, config and contracts) passed 531 tests and 217 subtests in 379.83 seconds,
with one existing LangChain `TypeSafeClassifier` beta warning. Repository-wide Ruff and the
kernel error-handling rules passed. This affected-suite result is separate from the earlier
1,478-test full kernel run. Coverage comments use one AC id per line for the repository's
proof parser; the comment-only normalization preserved all three test modules' parsed ASTs.

PR type checking additionally covers the new test modules. Their source categories now use
`EvidenceCategory`, and JSON assertions validate object shapes with the existing `as_type`
helper before indexing. The exact CI mypy scope passes; the affected 32 tests and 36 subtests
pass again, as does Ruff. This repair changes test typing and assertions, not production code.
