# IT-PO learnings — agent assignment by technical surface (leafcutter)

Captured 2026-06-16 during BO-210 / GE-102 technical enrichment.

## The BA tends to assign python-coder uniformly; re-route by surface

When the BA decomposes a feature it often stamps every leaf AC with
`assigned_agent: python-coder`, even for behaviors whose real implementation
surface is NOT Python. The IT-PO must re-assign by the file the work actually
edits:

- **`python-coder`** — `.py` only. Pre-commit hook scripts under
  `scripts/commit_guardian/` and `templates/scripts/commit_guardian/check_*.py`,
  build/config round-trips of `.claude/*.json` + `templates/scripts/.../*.json`
  (the JSON is edited and round-tripped by build.py, so it is python-coder work),
  and `commit_guardian.json` hooks_manifest edits (e.g. adding a `tier` field).
- **`llm-expert`** — `templates/skills/*/SKILL.md`, `templates/agents/*.md`,
  `templates/workflows/*.md`. ANY behavior whose implementation is prompt /
  skill-body / agent-template text: auto-fix re-dispatch routing in the
  precommit-autofix SKILL.md, capsule-emission instructions in the coder agent
  templates (python-coder.md/sql-coder.md/frontend-coder.md), signoff SKILL.md
  capsule documentation, depth-cap / no-sub-agent / shell-convention rules that
  live in template bodies. These are the most commonly mis-assigned ACs.
- **`documentation-expert`** — `docs/**/*.md` how-tos and references.
- **`architecture-diagram-author`** — C4 / sequence / state diagrams.

Rule of thumb: if the criteria describe what an AGENT or SKILL should DO/SAY
(routing logic, prompt instructions, what a coder emits in its sign-off), the
surface is a template/skill body -> `llm-expert`, not python-coder.

## workflow-architect is NOT dispatchable as a ticket-phase agent

`workflow-architect` owns the create-hook / add-skill / add-agent skills, but it
is `tier: supervisor` and `is_ticket_phase: false`. The AC-build loop dispatches
ticket-phase agents only, so an AC assigned to workflow-architect risks being
undispatchable. For hook scaffolding + manifest registration, assign
`python-coder` and put the create-hook scaffold pattern (config key +
hooks_manifest entry with `tier` + doc-index row, ordering transform-before-
validator) in `it_requirements` instead. Confirmed with the user on GE-102c.

## Cross-component contracts: expects_from is single-valued

The AC `expects_from` field holds ONE `{ac_id, contract}`. When a consumer AC
depends on several upstreams (e.g. BO-210c-1 needs the capsule + the
AUTOFIX_AGENT line + blocking_hook_ids + the manifest tier), keep the primary
upstream in `expects_from` and capture the rest as explicit `it_requirements`
plus cross-component `depends_on` entries (per the BA convention that
cross-component links travel via depends_on). Same-folder `covered_by` only.

## Config/template parity is a recurring it_requirement

For any AC editing `.claude/*.json` or `templates/scripts/commit_guardian/*.py`, add an
it_requirement that the deployed file and its packaged template source are
edited together and verified in parity via the build.py round-trip — never edit
one side only. This is a standing leafcutter self-hosting constraint (ADR-001).

## Documentation gate fallback

If a feature ships new user-facing behavior (new hooks) but no parent L1 carries
`documentation_triggers`, the S7b gate is technically skipped — but still flag
the missing how-to coverage as a caveat and offer to author a
`documentation-expert` L2 AC (with `origin_agent: it-po`) depends_on the
behavioral ACs. Done here as GE-102e.

## Feedback-automation routers: .js workflow + Python helpers = python-coder; classifier judgment = llm-expert

Captured 2026-06-17 during ACD-1500 (feedback-router) technical enrichment.

A "router" feature that turns the feedback corpus into shipped work decomposes
into two surfaces, and the BA again stamped all leaves `llm-expert`:

- **Orchestration / queue-build / routing-matrix / confidence-gate / per-run-cap /
  protected-branch guard / resolve-loop / dedup / rate-limit** lives in a NEW
  depth-0 workflow (`templates/workflows-js/feedback-router.js`) plus shelling
  out to existing Python helpers (`scripts/feedback/aggregate.py --unresolved`,
  `resolve_feedback.py`, `submit_feedback.py`, `roadmap_query.py`). Assign all of
  this to **`python-coder`** (the .js workflow body + Python script glue). It is
  NOT llm-expert work even though it is "agent automation".
- **Per-entry judgment** (work_type ∈ {bug-fix,feature,improvement}, size ∈
  {S,M,L}, confidence 0.0-1.0, codifiability) lives in a NEW Haiku-pinned
  classifier agent template (`templates/agents/feedback-classifier.md` +
  `agent_registry.json` entry), dispatched at depth 1 per ADR-006. Assign these
  leaves to **`llm-expert`**. Determinism-across-runs ACs belong here too (pin
  Haiku + temp 0 in the prompt), not on the python orchestration side.

Standing it_requirements to capture IN the YAML (not just the report) for this
class of feature:

1. **submit_feedback.py allowed_writers is a BLOCKING config prerequisite.**
   `config/feedback_categories.yaml` gates category+writer; `process-finding` is
   `allowed_writers: [hook]` ONLY, so a router emitting process-finding is
   rejected (exit 1) until either a new router writer id is PR-added or the
   router emits with hook source. The vocabulary is PR-gated (closed) — flag the
   config decision explicitly as a build prerequisite.
2. **New tunables need a config home, not hard-coding.** confidence_floor,
   per_run_artifact_cap, protected_branches (default [main,master]), and a
   process-feedback rate-limit all belong in a NEW `config/feedback_router.yaml`;
   name the keys in it_requirements.
3. **ADR-006 depth-1 rule recurs:** the router is depth-0 and dispatches the
   classifier at depth 1; it must NOT chain a build supervisor inline. Put this
   in it_requirements on every orchestration/routing leaf.

Idempotency, atomicity (resolve only after confirmed artifact), and fail-safe
(missing roadmap -> park, not assume-aligned) are the recurring policy-level
it_requirements for self-improvement loops — state the WHAT, let python-coder
pick the HOW.

## selection_criteria DSL has no negation/derived-path: "X-without-its-Y" triggers are llm-type (llm-expert), the paired hook is python-coder

Captured 2026-06-17 during GE-104 (enforced-page-docs) technical enrichment.

The agent_registry selection_criteria DSL (scripts/selection_criteria_evaluator.py,
ADR-018) parses only positive atoms `<field> <op> <value>` with op in
{contains, equals, matches} over {files_touched, title, description, components},
combined with AND/OR. There is NO negation operator and NO way to correlate one
files_touched entry with the ABSENCE of a second, DERIVED entry. So any trigger
of the shape "a new X is added WITHOUT its derived doc/companion Y" is NOT
expressible as a dsl-type condition.

Resolution pattern (do this, don't extend the grammar for a one-off):
- Author the trigger as `{ type: "llm", expression: <NL judgment> }` per ADR-018's
  two-tier model. documentation-expert already carries llm-type conditions.
- Known limitation to record IN the AC: llm-type conditions currently raise
  LLMEvaluationRequired and the business-analyst caller falls back to
  default_status until the LLM eval path is wired -> the planning-time trigger
  degrades to not-firing. So pair it with a commit-time HOOK as the authoritative
  backstop; planning-time stays advisory.
- Assignment: authoring a registry trigger EXPRESSION (judgment semantics) is
  **llm-expert**. The companion commit_guardian hook script + the hooks_manifest
  entry + config section is **python-coder**. Same feature splits across both.

## Shared deterministic derivation must be ONE helper across commit-time + planning-time

When the same path->path mapping (e.g. page site/app/<route>/page.tsx ->
docs/reference/frontend/<name>.md) is needed by both a commit hook and a planning
trigger, mandate a SINGLE shared pure helper module (here:
scripts/commit_guardian/frontend_page_docs.py) and forbid inlining the rule in
either layer — otherwise the two enforcement points drift. Pin the algorithm
concretely in the L3 it_requirements: hyphen-join lowercased route segments;
normalize dynamic [param] -> p_param (and [...param]/[[...param]] -> p_param);
raise loudly on unknown route shapes rather than emitting an ambiguous path.
Wire it via delivers_to (producer) / expects_from (consumer) so the contract is
explicit. New-page detection = set-difference present-now minus present-before
(robust to git rename heuristics; deletions produce empty added-set = no gate).
