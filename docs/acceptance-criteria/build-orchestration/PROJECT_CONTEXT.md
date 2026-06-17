---
description: "Cross-agent context for authoring and decomposing ACs in the build-orchestration (BO) namespace — conventions, field sets, and standing notes read by PO/BA/IT-PO during pre-flight injection."
---

# build-orchestration — AC store context

Cross-agent context for the build-orchestration (prefix `BO`) AC namespace.
Read by PO, BA, and IT PO during pre-flight injection.

## Component is not registered in index.yaml (but is the live convention)

`build-orchestration` does NOT appear in `docs/acceptance-criteria/index.yaml`,
yet every committed AC in this folder uses `component: build-orchestration` and
the `BO` prefix. This is the established live convention — follow it. Do not
propose a new component or rename existing ACs to a registered namespace.

## L0/L1 field set (benefit-language v3, NOT Gherkin)

L0 and L1 ACs use prose benefit-language in `criteria`, never Gherkin. Match the
BO-1100 / BO-1300 exemplars. Field set:
`id, readiness, priority, title, component, level, status, req_status,
work_status, created_by, criteria, depends_on, doc_links, assigned_agent,
estimated_complexity, delivers_to, expects_from, origin_agent, created,
amended_by, superseded_by, covered_by, implemented_by`. L1 ACs additionally
carry `documentation_triggers`. `created_by` is required by the manual
validator — set it to the parent/source AC YAML path. (Older BO-200 files
predate `created_by`/`readiness`/`priority`; do not copy them as the template.)

## L0 numbering

Next free L0 hundred as of 2026-06-17 (post BO-1300): BO-1400. The 500-series is
densely occupied (BO-500 through BO-560). Scan filenames before picking.

## BO-1300 (PR-native automation) vs FIN-100 (pre-merge safety gate) — framing

BO-1300 ("Every change the automation makes reaches main the same protected way
a person's would", 2026-06-17, PO) is the first BO L0 that `depends_on` a
cross-component `finalize` L0 (FIN-100). Keep these DISTINCT during decomposition:

- FIN-100 (finalize component) already ASSUMES a PR-merge step exists; it covers
  catching integration regressions before merge. It does NOT cover migrating
  today's direct-to-main automation to be PR-native.
- BO-1300 IS that migration: making ticket-supervisor, the commit/pull-request
  phase agents, and finalize-feature open and merge via a PR instead of pushing
  straight to main, so the operator can turn on "require a pull request before
  merging" branch protection without breaking the pipeline.

Framing note for the BA decomposing BO-1300's four L1s:
- BO-1300a (no direct push — every change via PR): the mechanism. The operator
  outcome is that branch protection CAN be enabled. documentation_triggers:
  [sequence-diagram] (changes the multi-actor commit→push→PR→merge flow).
- BO-1300b (merge only when required checks green): a wait-for-checks state
  machine (pending → green/red → merge/hold). Decompose the success path AND the
  "never merge over red or pending" invariant. documentation_triggers:
  [state-diagram].
- BO-1300c (blocked merge surfaced as a clear blocker, never forced): the
  failure-path escalation to the operator — distinct from BO-1300b's success
  gate. documentation_triggers: [sequence-diagram].
- BO-1300d (operator enables the branch rule with confidence): the end-state
  operator-value outcome — the pipeline keeps working with protection on.
  documentation_triggers: [how-to].

The live "Lint (ruff)" CI gate is the canonical example of a required status
check the automation must wait for (BO-1300b).
