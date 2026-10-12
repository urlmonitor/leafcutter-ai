---
title: "Decision Kernel V0 Design - Part 4 of 6: Jev Adapter and Capabilities"
description: "The narrow Jev port and its langchain-typesafe adapter (question templates, batching, retries, error semantics), the native decision and research graphs with continuation state, the read-only repository retrieval adapter and source catalog, the bounded host operations, human interactions, and deterministic capability-gap recording with deduplication."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-10-01
components:
  - decision_kernel
---

# Decision Kernel V0 Design — Part 4 of 6: Jev adapter and capabilities

Spec: §9, §10, §14 ([spec part 4](2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md),
[spec part 6](2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md)).
Back to [part 1](2026-09-30-decision-kernel-design.md).

## Jev port (`providers/base.py`, P1) and adapter (`providers/jev.py`, P3)

Only `providers/jev.py` imports `langchain_typesafe`. Every graph uses the port.

```python
class QuestionSpec(KernelModel):   # id, kind: "noul"|"choice"|"score", template_id, template_version,
                                   # instructions: str | dict, criteria: dict[str, str] | list[str] | None
class JevBatch(KernelModel):       # purpose, state: dict (JSON), questions: list[QuestionSpec], correlation
class NoulAnswer / ChoiceAnswer / ScoreAnswer   # probabilities, confidence (None for noul), choice
class JevResult(KernelModel):      # model_id, request_id, answers: dict[str, Answer], usage: Usage,
                                   # latency_ms, input_fingerprint
class JevPort(Protocol):
    async def assess(self, batch: JevBatch) -> JevResult: ...
```

**`TypeSafeJevAdapter`** implements the port:

- **Construction:** `TypeSafeClassifier(api_key=secrets.jev_api_key, model=cfg.jev.model, timeout=cfg.jev.timeout_seconds)`.
- **Call:** `await classifier.ainvoke({"state": …, "questions": {id: Noul|Choice|Score}}, config={"callbacks": tracer.langchain_callbacks(corr), "run_name": f"jev.{purpose}", "metadata": corr})`.
- **Retries:** at most `limits.max_retries`, on `TypeSafeRateLimitError`, `TypeSafeInternalServerError`, `TypeSafeAPITimeoutError` and `TypeSafeAPIConnectionError`. Backoff honours `retry_after`. The class itself has no retry.
- **Exhausted retries or authentication errors** raise `JevUnavailable`.
- **Malformed answers** raise `JevInvalidResponse`: a missing id, a choice outside the criteria, or probabilities that do not sum to 1 ± 0.02.
- **Size guard:** questions are split to at most `jev.max_questions_per_call`. A state serialized above `jev.max_state_chars` raises `JevPayloadTooLarge`, and the caller truncates excerpts. The provider limit is 32k tokens for the state plus the longest question.
- **Traced data:** every call records the returned `model_id`, the template ids and versions, the input fingerprint, raw distributions and thresholds (part 5).
- **Test double:** `ScriptedJev` (`providers/fakes.py`, P1) answers from a script keyed by `(purpose, question-id glob)`. It can raise `JevUnavailable` and records every batch.

**Error semantics (§13.4):**

- `JevUnavailable` becomes `failed` with `error.code=provider_unavailable`.
- It is never a capability gap and never a fabricated decision.
- Routing failure blocks the item with diagnostics, and the run finishes `failed` or `blocked` with state preserved.

**Template rules** (`questions.py` rules and TypeSafe J8):

- One literal judgement per question.
- The state names its parts, and questions point at them in backticks.
- Nothing that code can compute goes to Jev.
- Every template has an id and a version.

## Routing template (`scheduler/routing_templates.py`, P4)

The state is `{"request": {kind, goal, question, payload_summary}, "task": {goal, component_ids}}`.
Each item that needs semantic routing gets one question, `route.<work_item_id>`: a `choice` whose
criteria are the eligible ids (text = descriptor `description`) plus `__NONE__` and
`__NEEDS_CONTEXT__`. Independent items share one batch (§9.3).

| Answer | Outcome |
|---|---|
| `__NONE__` | `no_match` |
| `__NEEDS_CONTEXT__` | `insufficient_context` |
| An eligible id with p ≥ `min_selected_probability` and confidence ≥ `min_confidence` | `selected` |
| Any other answer | `insufficient_context` with reason `low_confidence`. The top candidate is never selected silently (§6.1). |
| An id outside the eligible set | `JevInvalidResponse` |

## Decision capability (`capabilities/decision/`, P5) — native graph

- **Accepts:** `goal_request.v1` and `decision_request.v1`. **Produces:** `decision_report.v1`.
- **Continuation** (`DecisionContinuation`): `phase`, `attempt`, `requested: list[dedup_key]`, `options_version`, `criteria_version`, `last_assessment_fp`.
- **Execution:** the graph is compiled once and has **no** checkpointer. The kernel owns durability. Each invocation runs it with `ainvoke`.
- **Constraints.** `ExecutionContext.constraints` is a tuple of texts (`[severity] kind: value`) that the scheduler builds from `TaskInput.constraints` for every worker. `assess` quotes them first in the Jev `constraints` state, before constraint evidence and human inputs, so a caller constraint reaches Jev without being stored as evidence.

| Node | Behaviour |
|---|---|
| `load` | Question, options and criteria come from the payload or from child outcomes (`options.v1` proposals and their `proposed_criteria`, and the human answer that approves or edits proposed criteria). Evidence excerpts are read through `ctx.evidence(ids)`. Constraints and approval requirement are loaded. |
| `validate_basis` | Deterministic checks. No options: `waiting` with an `options` request (`options_request.v1`, `propose_criteria=true`). Options exist but no criteria: the criteria-proposal path below; `assess` does not run until the criteria are approved. If the continuation shows the same request already failed, the result is `blocked`. |
| `assess` | One Jev batch. **`sufficient.<crit>`** (noul): "Does `evidence` contain enough information to judge each option in `options` against `criteria.<crit>`?" **`satisfies.<crit>.<opt>`** (noul): "According to `evidence`, does option `options.<opt>` satisfy `criteria.<crit>`?" **`missing`** (choice): the MissingKnowledge taxonomy plus `none`. **`preference`** (noul): "Does choosing between `options` depend on a user preference, requirement or authorization that `constraints` do not state?" **`conflict`** (noul): "Do items in `evidence` contradict each other on a point that affects `question`?" |
| `combine` | Pure, thresholds from `decision.*`. **Resolved only if all hold (§9.4):** every required criterion has `sufficient ≥ T_suff`; the selected option passes every required criterion (`satisfies ≥ T_sat`, fail when ≤ 1−T_sat, otherwise uncertain); exactly one option passes (supporting criteria break ties); the option was supplied; `conflict < T_conf`; `preference < T_pref`; and approval is either not required or obtained. **Otherwise `needs_*`, in this precedence:** unknown options → `needs_options`; insufficient required criteria → `needs_evidence`, with categories from the `missing` answer and the map below; sufficient but uncertain, or conflict → `needs_synthesis`; preference, a tie, or approval → `needs_human`. |
| `emit` | `resolved`: `completed` with the report; the rationale is template-built and labelled `origin: template`; `approval_status` is `proposed` when criteria or options are only proposed. `needs_*`: `waiting` with child proposals — evidence goes to `research_request.v1` (needs pre-filled), options to `options_request.v1`, synthesis to `synthesis_request.v1`, human to `human_question_request.v1`. The same `needs_*` with an unchanged `evidence_revision` makes the result `partial` with open questions (no-progress). |

**Criteria-proposal path (options supplied, criteria missing).** User decision, BrainCandy,
2026-09-30. It replaces the earlier design, which sent this case straight to a `human` request
asking for criteria. Jev decides only against criteria that a human has approved:

1. **An LLM proposes criteria as host work.** `validate_basis` returns `waiting` with an
   `options_request.v1` that lists the supplied options in `existing_option_ids`, sets
   `max_options=0` and `propose_criteria=true`. `host.generate_options` serves it. The returned
   `proposed_criteria` carry `proposal_status=proposed` and `approval_status=proposed`.
2. **The run pauses for human approval or edit.** On continuation, `validate_basis` returns
   `waiting` with a `human_question_request.v1` that shows the proposed criteria and asks the
   human to approve or edit them. The run stays in `waiting_human` until answered or cancelled.
3. **Jev decides against the approved criteria.** `assess` runs only after the answer arrives.
   It uses the criteria as approved or edited, marked `approval_status=approved` with
   `approved_by` set to the human. Unapproved proposals never reach `assess` on this path.

Open for P5/P6: how an edit is expressed. `human_answer.v1` carries either a `choice_id` or
`free_text`, and nothing yet turns free text into `Criterion` entries.

MissingKnowledge maps to evidence needs as follows:

| MissingKnowledge | Evidence need or request |
|---|---|
| `missing_decision_basis` | `prior_decisions` |
| `missing_authoritative_guidance` | `authoritative_guidance` |
| `missing_internal_principle` | `internal_principles` |
| `missing_implementation_fact` | `existing_patterns` |
| `missing_task_fact` | `task_context`; a `human` request if no source resolves |
| `unknown_options` | options request |
| `conflicting_evidence` | synthesis request |
| `human_preference_or_authorization` | human request |

## Research capability (`capabilities/research/`, P5) — native graph

- **Accepts:** `goal_request.v1` and `research_request.v1`. **Produces:** `evidence_bundle.v1`.
- **Continuation** (`ResearchContinuation`): `phase` (planned, collected or synthesizing), `needs`, `child_map: dict[need_id, list[work_item_id]]`.

1. **`plan_needs`.** Needs mandated by the caller or policy are kept as `required`. For the remaining categories, one Jev batch of nouls `need.<category>` asks "Is `category` evidence needed to answer `question`?". Descriptions come from `research.category_descriptions`. p ≥ `need_required_threshold` makes the need required; p ≥ `need_supporting_threshold` makes it supporting.
2. **`resolve_sources`** (deterministic). For each need, select the sources in `config.sources` whose `categories` include it, filtered by `scope.source_ids`, `read_roots` and `technologies`, and by availability.
   - A native source becomes a `retrieval_request.v1` child, bound to `retrieve.repository`.
   - A need with no native source becomes a `host.research` child if `host.enabled`; otherwise the need is marked `unavailable` with its reason.
   - The result is `waiting` with all children; independent children run in parallel.
3. **`collect`** (on continuation). Merges the child bundles and computes coverage per need, `unavailable_sources` and limitations. One `conflict` noul runs over the whole bundle; a positive answer records a contradiction. Conflicts are never averaged away (§10.5).
4. **`evaluate`.** The `evaluable` noul asks "Can `question` be answered directly from `evidence` without further analysis?".
   - Below `evaluable_threshold`, when `allow_synthesis` is on and no synthesis has run yet: `waiting` with a `synthesis_request.v1` child.
   - Otherwise: `completed` with the bundle. It is `partial` if a required need is unsatisfied.
5. **Stop conditions (§10.5).** No re-planning happens without new evidence, and there is no research loop "to raise confidence".

## Retrieval adapter `retrieve.repository` (`capabilities/retrieval/`, P5) — native function

**Accepts** `retrieval_request.v1`; **produces** `evidence_bundle.v1`. It is read-only.

**Default `sources`** (`config/kernel_config.default.json`). Category names are generic; source
bindings carry the specifics.

| Source id | Kind | Categories | Roots / surfaces |
|---|---|---|---|
| `repo.principles` | repo_text | internal_principles | `CLAUDE.md`, `docs/conventions`, `docs/vision.md` |
| `repo.decisions` | repo_text | prior_decisions | `docs/architecture/adrs` |
| `knowledge.decisions` | knowledge_map | prior_decisions | surface `adrs` |
| `repo.patterns` | repo_text | existing_patterns | `kernel`, `scripts`, `docs/architecture` |
| `knowledge.components` | knowledge_map | existing_patterns, task_context | surfaces `components`, `skills`, `agents` |
| `host.research` | host_research | authoritative_guidance, external_practices | none (host handoff) |

**Strategies:**

- **`repo_text`** (`repository.py`, `terms.py`).
  - Query terms are extracted deterministically from the need's question and `scope.technologies`: lowercase tokens of 3 or more characters, minus a stopword list.
  - It walks allowlisted roots under `scope.repository_root` using `Path.resolve()` containment and skips `retrieval.deny_globs` and files larger than `max_file_bytes`.
  - Files are ranked by term hits. Excerpts cover ±`excerpt_context_lines` around hits and are capped at `max_excerpt_chars`.
  - All reads sit inside `try/except OSError`, which satisfies the IO-001 rule.
- **`knowledge_map`** (`knowledge_map.py`).
  - Loads `scripts/knowledge_query.py` with `importlib.util.spec_from_file_location`.
  - Calls `build_knowledge_map(root, root/"config/paths.json", surface_filter=…)`, caches per process and surface, then filters node title and description by the terms.
  - A load failure marks the source unavailable. It is never reported as "no results".
- **Reranking.** One Jev batch of `relevant.<candidate>` nouls, capped at `max_candidates`: "Is `candidates.<id>` relevant to answering `need`?". It keeps p ≥ `relevance_threshold` and the top `top_k`.
- **Evidence output.** `source.kind=repository_file` or `knowledge_node`, `locator=path#Lx-Ly`. `source_version={commit, dirty}` comes from `git rev-parse HEAD` and `git status --porcelain`, run in `try` and cached per run. Each item also carries `content_hash=sha256(excerpt)`, a `truncated` flag and provenance (`strategy`, `terms`, `rank`, `relevance`).
- **Untrusted content (§13.3).** Excerpt text is evidence, not instructions. It is never interpolated into templates except as quoted state values.

## Host operations (`capabilities/host/`, P8)

Descriptors with `execution_mode: host_handoff` are **not** executed in-process. `route` sends them
to `open_interactions`, which builds a `HostWorkRequest` (part 5, packet).

| Capability | Operation | Input → output schema | Allowed operations |
|---|---|---|---|
| `host.generate_options` | generate_options | options_request.v1 → options.v1 | read_supplied_artifacts, propose_options |
| `host.synthesize` | synthesize_evidence | synthesis_request.v1 → findings.v1 | read_supplied_artifacts, synthesize |
| `host.research` | bounded_research | retrieval_request.v1 → evidence_bundle.v1 | read_supplied_artifacts, read_repo_paths, web_fetch |
| `host.formulate_question` | formulate_question | human_question_request.v1 → human_question_request.v1 | read_supplied_artifacts |

- **Forbidden for every host operation:** `edit_repository`, `approve_policy`, `change_permissions`, `choose_next_step`, `run_other_leafcutter_commands`.
- **`conversion.py`** turns a validated host output into a `CapabilityResult(completed)`:
  - Host evidence gets `verification=host_reported` and usage provenance `unavailable` unless the host reports usage.
  - Options stay `proposal_status=proposed`.
- **Invalid output** is rejected (part 3, resume step 5). Once `max_repair_attempts` is exhausted, the item fails.
- **Telemetry:** every host operation also records a `host_only` gap observation for fallback-reliance telemetry (§14).

## Human interaction (P6)

- **Where a `human` request comes from:** a capability proposal, or an `insufficient_context` routing outcome.
- **Wording:** the request becomes a `HumanQuestion`. It uses template wording, or a preceding `host.formulate_question` when `host.formulate_questions=true`.
- **Answer handling:** the answer (`human_answer.v1`) becomes `Evidence(category=task_context, semantic_type=human_input, source.kind=human, provenance.actor=<id>, relayed_by)`. The owning parent then resumes.
- **Unanswered questions:** silence answers nothing. An unanswered question keeps the run in `waiting_human` indefinitely, until it is cancelled.

## Capability gaps (`persistence/gap_store.py` P2; `scheduler/nodes_gaps.py` P4 basic, P9 fallback)

| Gap type | Recorded when | Backlog draft? |
|---|---|---|
| `unsupported` | Routing returns `no_match` (Jev chose `__NONE__`, or no candidate matched kind or schema) | yes |
| `host_only` | A `host.*` capability ran, because no native implementation exists | yes |
| `provider_failure` | Jev or the host was unavailable | no — diagnostics only |
| `permission` | Eligibility excluded every candidate for permission or side effects | no |
| `ambiguous` | `insufficient_context` | no |

- **Dedup key (§14).** `gap_key = sha256(canonical({gap_type, request_kind, input_schema, output_schema, normalized_need, sorted(scope.component_ids)}))`.
  - For evidence requests, `normalized_need` is the need category.
  - For options and synthesis requests, it is the operation.
  - For `capability` requests, it is the sorted set of up to 12 goal tokens after stopword removal.
- **Observations.** `gap_store.record(gap)` appends an observation to `gaps/observations.jsonl`, best-effort. A write failure logs a WARNING and becomes a run limitation.
- **Aggregation.** `load_gaps()` aggregates the observations into `occurrence_count`, `first_seen`/`last_seen` and `example_run_ids` (at most 5).
- **Drafts.** `write_draft()` renders `gaps/drafts/<gap_key>.md` from a template (author `template`). It holds purpose, contracts, examples, closest capabilities and uncertainties. A draft is never a registry entry.
- **Fallback.** Allowed only when all hold: `host.fallback_on_no_match`; the request kind maps to an approved `host.*` capability that passes eligibility; budget remains; and the gap type is not `permission`. Allowed: the item is rebound, with `fallback_outcome` updated when the host result arrives. Not allowed: the item is blocked with `no_capability`.
- **No evasion.** A denied native action is never re-routed through a host fallback (§14).

## As built (P8 and integration)

- **Compiled packets.** Each host operation compiles its task statement and output requirements deterministically from the request payload, output schema, allowed operations, cited evidence and limits (ADR-052), redacted and fingerprinted. The template id and fingerprint travel as the last `output_requirements` line (`HostWorkRequest` is a frozen P1 contract); invocation `versions` carry `host_template` (`<capability>.task@1.0.0`), and `host.<operation>` telemetry events carry the fingerprint, time to answer and usage. The input artifact is `input-<interaction id>.json`; the packet operation is the descriptor's first operation.
- **Conversion rules** (total: a failure returns a non-retryable failed result). Host evidence is `verification=host_reported`; options and criteria stay `proposed`, excess options and unrequested criteria are dropped with a limitation, and a criterion's `weight_rule` and `decision_basis` are cleared; research coverage is clamped to what the evidence shows and the bundle `request_id` is dropped; findings citing evidence that does not exist are dropped (`findings.v1` has no semantic check, so they are not repaired). `host.formulate_question` keeps the original choice ids, flags, decision and subject ids and adopts only the host's question text and choice labels.
- **Routing of `host.formulate_question`.** Behind `host.formulate_questions` (default `false`): a human request first spawns a `capability` child bound to `host.formulate_question` and waits; on resume the converted `human_question_request.v1` replaces the human request's payload and the kernel creates the human interaction itself (Rev 3 section 11.6). A missing, failed or refused formulation leaves the original question. Flag off: unchanged.
- **Telemetry.** Every executed host operation records one `host_only` gap observation (see part 3).

## As built (grounding)

- **Grounded options.** A decision whose options are unknown and that holds no evidence first emits one bounded research request (`ground:options`, `evidence_needs_only`, best-effort): `task_context`, `existing_patterns` and `prior_decisions`, worded for the option space. Research then plans exactly those needs (no Jev planning call). On resume the options request carries the researched evidence ids (at most `decision.max_grounding_evidence`), and `require_grounding` when `decision.require_option_grounding` is on. Evidence the caller already supplied skips the research. If research found nothing and grounding is required the decision blocks with `options_ungrounded`; otherwise it asks for options and records a limitation. The approval question lists what each option cites (`grounded in ev-...` or `no cited evidence`).
- **`host.generate_options` has no repository access.** The safer coherent choice: `permissions_required` stays empty and the packet says so. A host reading files itself would bypass the kernel's deny globs, size limits and revision stamps and produce claims the kernel cannot verify. Grounding comes from kernel-retrieved evidence in the input artifact; options cite it in `source_refs`. Conversion keeps only references to supplied evidence ids, flags an option that cites none (`not grounded`) and refuses it when `require_grounding` is set. Criteria are not subject to grounding.
- **Native sources.** The default catalog now also reads `repo.docs` (README, how-tos, explanations, reference, testing, workflows, known issues, glossary), `repo.acceptance_criteria`, `repo.roadmap` (roadmap and vision), `repo.tickets`, `repo.config` (with per-source deny globs for secrets) and `repo.tests` (test READMEs and `pytest.ini`). A source may carry `deny_globs` that extend `retrieval.deny_globs`. Measured on this checkout, one search costs 2.5 s for the acceptance-criteria store (4468 files), 1.2 s for tickets and under 0.6 s for every other source; each source returns at most `retrieval.max_candidates` and the merged list is cut to the same bound before the single rerank batch.
- **Coverage.** A need is `satisfied` only when at least one kept item has judged relevance at `retrieval.coverage_relevance_threshold` (0.7 by default; `relevance_threshold` stays the keep bar at 0.5). Weaker or unjudged items stay in the bundle as context and leave the need `partial` with a limitation.
- **Contradictions.** `Collected.add_contradictions` records each once by evidence pair (either order) and claim, so a resumed collect no longer re-adds them. Jev's bundle-wide conflict is recorded once with the note prefix `unlocalised:` and not at all beside a localised contradiction.
- **Verbatim evidence.** `Evidence`, `EvidenceInput` and `InteractionSubmission` keep string values verbatim (the base model's whitespace stripping rewrote host excerpts and broke the host's own hash). A missing evidence `id`/`content_hash` or finding `id` is computed on input, and the host packet schema for `evidence_bundle.v1` no longer requires them, matching the instruction not to invent them; the kernel-side schema file is unchanged apart from its description.

## As built (grounding, round 5)

- **Trusted knowledge-map bridge.** `scripts/knowledge_query.py` is loaded only from the kernel's own installation (`knowledge_map.trusted_root()`, the checkout the `kernel` package lives in), never from the scope repository, which is passed to `build_knowledge_map` as data. A scope without `config/paths.json` (which the script reads) leaves the source unavailable with a reason, and a missing trusted script does too. No other kernel module imports or executes code dynamically (guarded by a test).
- **Read-only git.** Every kernel git call is a read-only command (`rev-parse`, `status`) run without a shell and with `GIT_OPTIONAL_LOCKS=0`, so `git status` cannot refresh or write the scope's index.
- **Named options.** When the goal names the options to choose between, the host's options step returns them with `named_in_goal` (extraction is generative work, ADR-053); the kernel verifies deterministically that the title appears in the goal text (normalized substring, else all significant tokens) and then creates `named_options`: supplied options with only the caller's title, `proposed_by: caller_goal`, no approval and no grounding requirement. A claim that fails the check stays an ordinary proposal. A host cannot return `named_options` itself (semantic check). Asking at intake whenever the goal enumerates was not chosen: it costs a host call on every goal.
- **Approval can add options.** `human_answer.v1` accepts `added_options` (title, description); they become human-supplied, approved options (`opt.added.N`, `approved_by` the human). The approval question says so and lists the options taken from the request.
- **Sources.** `repo.analysis` (`docs/analysis`) and `repo.components` (`docs/architecture/components`) are default sources for task context, prior decisions and existing patterns.

## As built (V0.1)

- **Criterion kind and ranking (fix A).** A criterion is `evidence_answerable` or `design_judgement`; one `kind.<criterion>` noul rides the assess batch (`decision.design_judgement_threshold`). Options are ranked deterministically: required criteria passed, required mean, supporting mean, declaration order. `option_context` (title, description, `cited_refs`, `human_added`) goes with every research request made after options exist.
- **Section-aware retrieval (fix B).** Markdown is chunked by heading (the heading path is in the locator), code by top-level definition, with up to `retrieval.sections_per_file` windows per file. The pre-filter pins files whose path carries an identifier the question names and gives every source a turn (`source_candidate_floor`, `source_candidate_ratio`), bounded by `retrieval.max_candidates` (60). `retrieval_request.explicit_locators` (`path`, `path#Lx-Ly`, `path#heading`, `path::Symbol`, at most `retrieval.max_explicit_locators`) are fetched first under the same read policy; a refused or missing locator is a limitation.
- **Research consumes `option_context` (wave 2).** The paths an option cites (any `cited_refs` entry shaped like a repository path, `path#anchor` or `path::Symbol`; evidence ids and bare symbols stay context) become `explicit_locators` on every native retrieval child, and the child's `source_ids` also name the sources whose roots hold those files (a locator is read only from a requested source, and a need's own sources rarely hold what an option cites; a search still covers only sources serving the need's category). Query hints are the goal, then the approved criteria's questions (`criteria_context`), then option titles and descriptions.
- **Goal-first queries.** `build_query_terms` takes the goal whole (up to three quarters of `retrieval.max_query_terms`, 48), then the other hints, then the need-template wording; the old first-24-terms rule cut the end of a long goal. Identifiers in the hints also drive the path pre-filter.
- **Targeted needs.** The unknowns a synthesis names travel in `evidence_bundle.unknowns`; the decision keeps the newest as `gaps` and sends them in the next research request. Each gap, and each human-added option's claims, becomes a supporting `existing_patterns` need (`need.gap.N`, `need.claim.<option>`) with its own hints and the locators its own text names, at most `research.max_targeted_needs`.
- **Answer-aware coverage.** Relevance only says a hit is on topic. For each need retrieval called `satisfied`, the existing `research.assess` batch carries one `answers.<need>` noul ("do the kept evidence items answer the question?", the question and evidence ids quoted as state under `answer_checks`; text that only proposes or aspires does not answer a question about today). Below `research.answer_threshold` the need drops to `partial` with a limitation, the evidence stays as context, and the downgrade survives a synthesis resume (`unanswered` in the continuation). `research.answer_aware_coverage` switches it off. No Jev call is added; the question is skipped when no need has passing evidence.
- **Host-only supporting needs.** The 0.51 against 0.5 case was not given its own threshold: the user's trace review moves outside practice earlier (a phase_kernel_3 policy), so `host.research` keeps the existing deferral and `need_supporting_threshold`.

## As built (V0.1 round E)

- **Criterion-kind question (template v2) and backstop.** `kind.<criterion>` is a literal, atomic true or false judgement that names both readings with a boundary example each: a property each proposed option would have if built (reviewable diffs, readable by an existing parser) versus a fact already true in the repository today (the project already uses YAML). Round 6 put P(design_judgement) at 0.12 to 0.54 for six such criteria under the old "weigh the designs" wording. Backstop (`kind_source: rule`): while every usable option is a proposal (`proposed_by` set: host, human-added or named in the goal) a criterion whose text starts with an interrogative auxiliary (does, do, can, could, is, are, will, would, should, must, has, have) is a design judgement unless Jev's probability is below `1 - decision.design_judgement_threshold` (confidently evidence-answerable). Options a caller supplied as structured input may be existing artifacts and are not covered by the rule. The wording test is code because it is grammar; the confidence escape keeps Jev's say on criteria about existing facts.
- **Cheaper research.** `retrieval.rerank_max_per_need` (20) bounds the candidates one need sends to Jev, so a need is one rerank call; `retrieval.max_candidates` (60) stays the pre-filter pool. The pool is ordered by sending priority: explicit locators (kept regardless and no longer judged), then every source's best candidates, then the rest by term hits across sources; each cut (pool and batch) is a limitation. A further batch is judged (up to `retrieval.rerank_max_batches`, 3) only while nothing relevant was found: with one batch of 20 a live goal found no evidence at all, which the old 60-candidate pool had grounded; a later batch the budget cannot fund keeps the earlier results. Decision-driven research plans exactly the categories the decision named (`evidence_needs_only`, no Jev planning call) and `research.max_targeted_needs` is 2 (claims first). A round of n needs costs n rerank calls plus one judgement (`kernel/capabilities/call_costs.py`).
- **Retrieval selection.** YAML front matter is never a section when a body exists. A file is ranked by one number: content hits plus `retrieval.path_match_weight` per distinctive path word; words in the path of most files and the project's own names (workspace id, folder) are not distinctive. A need is `satisfied` only with `retrieval.satisfied_min_items` items at or above the coverage bar or one item at `satisfied_strong_threshold`. A candidate that repeats at least `retrieval.self_reference_ratio` of the goal's five-word runs, and is not explicitly cited, is a review of the asking run: its relevance is multiplied by `self_reference_penalty`. An explicit locator must look like a repository path and name an existing file (`-NNN.yaml` is dropped with a debug note); `docs/components.json` and `docs/build-dataflow.json` are the `repo.registries` source.
- **Query noise.** With hints, the need's own wording (category template filler) is not searched and does not drive path matching.
- **Partial coverage is visible.** A completed evidence bundle puts partial needs, the answer-aware notes and the synthesis unknowns in its result limitations (so the envelope shows them) and report.md gains Coverage and Unknowns sections; key evidence is ordered by judged relevance.

## As built (V0.1 round F)

Round E made research cheap but the first rerank batch filled with registry JSON, ticket comments and AC yaml while the files that answer sat unjudged. Round F measures this first (`tests/kernel/retrieval/test_retrieval_benchmark.py`, an offline benchmark of the lexical stage over the real checkout: the first batch of 20 per case, plus the real rerank loop run with a scripted oracle) and then fixes it.

- **Ordering (N1).** Candidates are ordered by a BM25-style score (`retrieval/scoring.py`), never by raw term hits: a term's weight is its rarity over the sections scanned, a section's length is measured against the mean of its own source (`retrieval.bm25_k1`, `bm25_b`), a file named after the topic adds `path_match_weight` rarity units (`run_store.py` for "store"), a registry's `nodes` section is cut into windows of `max_section_lines`, and a JSON object holding one collection is split by entry and pinned when the goal speaks its vocabulary (`registry_pin_min_terms`). The score only orders the pre-filter (spec section 17); Jev still judges relevance. The pool keeps `pool_fair_share` best candidates of every source (when they score `pool_fair_min_ratio` of the best), at most `pool_sections_per_file` sections of a file in the first batch, and sorts that batch by score; "strongest not judged" uses the same score.
- **Deeper reranking (N3, R2).** A need judges further batches (up to `rerank_max_batches`) until it has enough on-topic evidence: it would count as satisfied AND `rerank_min_items` items passed the keep bar. It stops when the best unjudged candidate scores below `rerank_stop_ratio` of the judged ones, or at the budget. Research gives each retrieval child `max_rerank_batches` (the Jev calls beyond the plan and the decision's reserve, shared evenly: `call_costs.batch_allowance`), so a decision-driven round cannot spend into the reserve.
- **Synthesis on coverage (N2).** Research asks the host to synthesize when a planned need is partial, open or unanswered, or no need is satisfied, as well as when `evaluable` is low, if a work item is left; evidence is never synthesized when there is none.
- **Review of the asking run (R3).** A document that reviews a kernel run of this goal is recognised per document (a `trace-review` file name, or a quote of the goal beside a run or trace id): it is demoted like a goal repeat unless cited and does not take a place of the first batch.
- **Smaller fixes.** The thin-coverage note names its need (N4); a source may carry its own `max_file_bytes` (the registries source reads the 812 KB `docs/build-dataflow.json`) and a file still skipped for size is named once with the remedy (N5).
- **Benchmark (must-have places in the first batch of 20; judged by the real loop with the oracle):**

| Case | Round E first batch | Round F first batch | Round E judged (calls) | Round F judged (calls) |
|---|---|---|---|---|
| goal 5, how the kernel stores decisions | 0 of 3 | 1 of 3 (gap_store.py) | 1 of 3 (2) | 3 of 3 (2) |
| goal 2, where tests are saved | 1 of 3 | 3 of 3 | 1 of 3 (1) | 3 of 3 (1) |
| decision records goal | 2 of 4 | 2 of 4 | 2 of 4 (1) | 2 of 4 (1) |
| thresholds (lessons 18) | 0 of 2 | 1 of 2 | 1 of 2 (3) | 1 of 2 (3) |
| approval provenance (lessons 16) | 1 of 2 | 2 of 2 | 1 of 2 (1) | 2 of 2 (2) |

  What a lexical score does not reach stays in the fixture as the gap for semantic retrieval: design-3 section Persistence layout (pool position 38), Stage-0 delta part 4 and concept parts 3 and 4 (outside the pool), the default config JSON.

## As built (decision store)

- **Precedent node.** The decision graph is load, precedent, validate_basis, assess, combine, emit. `precedent` asks `ctx.memory.find_decisions` once per decision (components and phase where known, text match, top `memory.max_precedents`). With no options yet no assessment is coming, so ONE Jev call (`decision.precedent`, one literal noul per precedent) judges them; otherwise the `precedent.<dec id>` questions ride the assess batch (no extra call) and an applicable precedent is evidence only. At `applies_threshold` a precedent becomes `prior_decisions` evidence (record path, approver; no `provenance.actor`); at `reuse_threshold`, with no options of its own and not superseded, the best one is offered in the short confirm question.
- **Confirm, reuse, decide anew.** `reuse` resolves with the precedent's option, the CURRENT human as approver, the rationale citing the precedent and a new record with `related` (and no `supersedes`); `decide_anew` continues normally and a different final choice stages `supersedes`. The older record is never edited by the kernel; `decisions publish --correct <old id>` appends the correction. A vanished record falls back to deciding anew; an exhausted budget skips the precedent instead of blocking.
- **Staging gate.** `kernel/memory/builder.py` refuses a decision that is not resolved, approved, by a human actor (`human` / `human:<id>`, a bare id gets the prefix, host and Jev ids are refused) with an approval time. Nothing is staged for any other decision.
- **Round-8 defects.** (a) Evidence a `need.claim.<option>` found is linked to that option (`need_evidence`), so the ranked packet cites it. (b) `trace_refs` is filled. (c) The Decision section of report.md. (d) Retrieval cut notes collapse to one `retrieval cut for need <id>` line per need in the decision's limitations and repeats are dropped; the research bundle keeps every raw line. (e) A criterion assessment cites the evidence relevant to it (word overlap plus what the option cites, at most `criterion_evidence_max`) instead of all evidence. (f) A class or contract named in an option or gap ("Decision contract") adds `path::Symbol` locators for each cited Python file that defines it.
