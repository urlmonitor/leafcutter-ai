---
title: "Kernel Trace Review - Decision Records Run"
description: "Step-by-step reading of live kernel run run-5d246775f5e54f11 (Langfuse trace 954274b2…), which asked how decision records should be filed under docs/. Covers what the kernel did, why the evidence loop did not converge, why outside best practice arrived late and by chance, how research ignored the gaps synthesis had named, and what the telemetry makes hard to read, with proposed fixes."
type: explanation
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - decision_kernel
related_docs:
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta.md
---

# Kernel trace review: the decision-records run

## Summary

The kernel's mechanics held up. Every hop was logged. Claude (the host) was never allowed to choose, model-proposed options went to a human for approval, and options had to cite evidence. The run still did not reach a decision. It went round an evidence loop that barely moved its own scores, and nothing in it checks for progress. Three causes:

1. **The approval gate is practically unreachable.** No option clears 0.8 on more than two of the six required criteria.
2. **Research is not targeted.** Every round searched the goal text again. Neither the criteria nor the gaps a synthesis had already named were used as search terms.
3. **Outside best practice came in last, by a narrow margin.** It was researched only after the options had been generated and approved, and only because a Jev score landed at 0.51 against a 0.5 cut-off.

## The run

| | |
|---|---|
| Goal | "Decide how Leafcutter should file decision records as JSON or YAML files under docs/ so later kernel runs can find and reuse them as precedent: which fields a record needs, which classification filters it carries (component, file type or language, repository-wide, roadmap phase), the folder layout and file naming, and how human approval and later corrections are recorded." |
| Run | `run-5d246775f5e54f11`, started 2026-10-01 08:07:48 UTC; repository root `worktrees/kernel-research` |
| Trace | Langfuse `954274b26bf886b3d7658e0345453cbb`, project `leafcutter-local` |
| State when read | 09:07:57 UTC, 503 observations; status `waiting_host`, a sixth host task open |

## What the kernel did, step by step

Times are UTC. "Claude" is the host: the kernel pauses and hands it a bounded task.

| # | Time | Who | What happened |
|---|---|---|---|
| 1 | 08:07:49 | Jev | Classified the goal as a **decision** (probability 1.0). |
| 2 | 08:07:49 | Kernel | Decision had no options, criteria or evidence, so it asked Research for a decision basis. |
| 3 | 08:07:50 | Kernel | Research took a fixed plan of three needs (task context, existing patterns, prior decisions; no Jev call). It ran **3 parallel keyword searches** (33 s) over about nine sources each. The AC store took 33 s (4,468 files) and tickets took 20 s (1,486 files). Jev reranked the hits; **10 evidence excerpts** were kept. |
| 4 | 08:08:23 | Jev | Do the sources conflict? 0.24. Can research answer from this evidence alone? **0.20**, so no. |
| 5 | 08:08:24 | Claude | Synthesized the 10 excerpts into **10 findings** (120 s). The kernel logged a `host_only` gap. |
| 6 | 08:10:25 | Claude | Still no options, so Claude proposed **5 options and 6 criteria**, each citing evidence (90 s). |
| 7 | 08:11:56 | Human | Model proposals need approval. About 49 minutes later the human approved all 6 criteria and 3 of the 5 options. They rejected "single JSON registry" and "Markdown ADR-style" (the latter breaks the goal's "JSON or YAML") and **added their own option**, "Kernel-contract YAML per decision". |
| 8 | 09:01:08 | Jev | 33 yes/no questions in 0.7 s: is there enough evidence to judge each criterion, and does each option meet each criterion according to the evidence? Sufficiency came out at **0.55–0.64 against a 0.8 gate**: *needs evidence* ("missing decision basis"). |
| 9 | 09:01:10 | Jev / Kernel | Research planned its needs with Jev. "External practices" scored **0.45**, under the 0.5 supporting cut-off, so it was dropped. **4 parallel repo searches** ran (up to 88 s) and kept 6 excerpts, 2 of them repeats from round 1. Answer alone? 0.10. |
| 10 | 09:02:42 | Claude | Synthesized again: **6 findings** (141 s). |
| 11 | 09:05:04 | Jev | Re-assessed. Sufficiency moved by at most ±0.04 (now **0.57–0.67**): *needs evidence* again, now "missing implementation fact". |
| 12 | 09:05:05 | Jev / Kernel | The same need-planning question, asked again, scored external practices at **0.51**, so it was included as a supporting need. 2 repo searches ran (21 s). |
| 13 | 09:05:29 | Claude | **Researched outside the repo** (140 s). It fetched the MADR template and adr-tools from GitHub: 5 excerpts with URLs and content hashes, 4 findings, coverage "partial". |
| 14 | 09:07:50 | Jev → Claude | Answer alone? 0.10. Another host task opened at 09:07:57. |

Jev's cost for the whole run is under half a cent. Nearly all of the time and cost goes to Claude (over 10 minutes across five tasks, token cost unreported) and to lexical search (about 2.5 minutes).

## Findings

### 1. The evidence loop does not converge

Two decision assessments, before and after a full extra round (4 searches, 6 new excerpts, 6 findings, about 4 minutes of work):

| Criterion | Sufficiency 09:01 | Sufficiency 09:05 |
|---|---|---|
| `crit.enforced_ids_and_links` | 0.64 | 0.67 |
| `crit.findable_by_filters` | 0.59 | 0.63 |
| `crit.knowledge_map_readable` | 0.63 | 0.62 |
| `crit.provenance_complete` | 0.64 | 0.61 |
| `crit.reuses_conventions` | 0.63 | 0.66 |
| `crit.reviewable_diffs` | 0.55 | 0.57 |

The run is bounded only by general budgets (`max_host_operations: 8`, `max_active_seconds: 300` in `config/kernel_config.default.json`). It will most likely end on a budget guard as *partial*, not on a judgement. Nothing compares one round with the next.

### 2. The gate is practically unreachable

`combine.py` requires every required criterion to reach a sufficiency of 0.8, and the chosen option to satisfy every criterion at 0.8 or more. Satisfaction scores at 09:05:

| Criterion | Human-added | Reuse AC store | YAML + generated index | YAML per component folder |
|---|---|---|---|---|
| enforced ids and links | 0.20 | 0.66 | 0.19 | 0.24 |
| findable by filters | 0.65 | 0.69 | **0.89** | 0.50 |
| knowledge-map readable | 0.49 | 0.68 | 0.53 | 0.38 |
| provenance complete | 0.74 | 0.42 | **0.88** | **0.88** |
| reuses conventions | 0.28 | **0.83** | 0.30 | 0.25 |
| reviewable diffs | 0.71 | 0.72 | 0.58 | 0.74 |

The best option passes 2 of 6. With six required criteria and both bars at 0.8, the gate can open only if Jev's scores move far above where they cluster (about 0.2–0.9, mostly 0.5–0.7). This is the calibration problem from live QA, now with numbers.

### 3. Outside best practice: late, and decided by noise

| Round | Needs searched | Outside practice? | Why |
|---|---|---|---|
| 1 (08:07), feeds option generation | task context, existing patterns, prior decisions | No | Fixed plan; the category is not even a candidate |
| 2 (09:01), after approval | prior decisions, principles, patterns, task context | No | Jev 0.45 < `need_supporting_threshold` 0.5 |
| 3 (09:05) | patterns, principles, prior decisions, **external practices** | Yes, via Claude | Jev 0.51 on the unchanged question |

This goes against the design in three ways:

- **Order.** The spec's research catalogue (§10.2) defines `external_practices` as *"What relevant alternatives or experience merit comparison?"*. That is the input options should be generated from. Here options were generated at 08:10 and approved at 09:01 using repository evidence only.
- **No mandate.** §10.2 step 1 keeps "mandatory categories established by the caller or policy". No policy makes outside practice mandatory for design or decision questions, so inclusion hangs on a borderline Jev score. The swing from 0.45 to 0.51 on the same question is noise. The missing policy is expected in V0: there is no policy catalog yet (ADR-054 §4), and policies arrive with `phase_kernel_3_workflows`.
- **Weight.** When it finally ran, it was a *supporting* need. It could not hold up the decision and was not aimed at any specific claim.

The bounded host research path itself (§10.3) worked once triggered. Claude cited real sources and recorded honest limits: "not a survey", and "no external practice for structured JSON or YAML decision records with scope filters was found".

### 4. Research ignored the gaps synthesis had named

At 08:10 the first synthesis recorded exactly what was missing:

- `kernel/contracts/decision.py` was not among the evidence.
- There was no evidence on a file-type or language filter, a `decision_type` vocabulary, or how approvals and corrections are recorded.
- The Neo4j colony-memory concept and the Stage 0 delta's "decisions needed" part were not retrieved.

None of these became a search target. Every later query was the goal text with a need-template prefix:

```text
round 1: concrete candidates items facts project scope leafcutter file records json yaml files docs later kernel runs find reuse precedent fields record classification filters carries
round 2: decided assumptions leafcutter file records json yaml ... classification filters carries component type language repository-wide
```

`extract_terms` (`kernel/capabilities/retrieval/terms.py`) keeps the first 24 distinct terms. Template filler ("concrete candidates items facts") uses up slots, and the end of the goal is cut off. As a result **approval, corrections, naming and layout were never searched for**, and the text of the approved criteria (knowledge-map ingestion, `paths.json`, `check-identifier-uniqueness`) never reached a query either.

### 5. Verifying the human-added option was right; the aim was wrong

`assess.py` asks whether an option satisfies a criterion *"according to `evidence`"*. The human-added option has no evidence behind it, so it scored low (0.20 on ids and links, although its text says the schema is validated at commit and the ids are kernel-minted).

That is intended: a human's proposal is a claim to verify, not a fact, and follow-up research was the right move. The defect is that the follow-up research could not find evidence for the option's actual claims. It never searched for them (finding 4), and outside practice arrived too late to inform the comparison (finding 3).

A related shape issue: the goal bundles five sub-decisions (fields, filters, layout, naming, approval and corrections) into a single "pick one of N". The human's added option was a composite spec rather than an alternative.

### 6. Option generation ignored a goal constraint

The goal says "JSON or YAML files", yet Claude proposed "Markdown with YAML frontmatter, ADR-style". It did flag the deviation, and the human rejected it. Constraints stated in the goal should be enforced before options are shown.

### 7. The trace is hard to read

- **Most of the 503 observations are LangGraph plumbing** (`after_route`, `_after_plan`, `__start__`, `<unknown>`) from the LangChain callback. They duplicate the kernel's own `kernel.*` spans, and capability spans sit beside the graph node that ran them instead of under it.
- **Jev generations show 0.00 s.** Their metadata has `latency_ms` of 264–677, so Langfuse latency analytics for Jev are meaningless.
- **Host usage is blank.** Claude's tokens and cost are `null` with `cost_provenance: unavailable`, though Claude is the dominant cost.
- **Retrieval spans don't say what was found.** Retriever outputs carry counts only, and rerank outputs score `c1…c20` with no paths or evidence ids, so the trace alone cannot show which files became evidence. The ADR-056 analytics job needs that link.
- **Smaller issues.** The first segment's spans carry `root_task_id: "pending"`. The OTel service name is `unknown_service:python.exe`. Interrupts appear as Python `repr` strings in `statusMessage`.

## Proposed fixes

Fixes 1, 2 and 4–8 are V0 work. Under the repository's ticket rule, each needs its own ticket before any change. Fix 3 is roadmap scope, not a V0 ticket.

| # | Fix | Addresses |
|---|---|---|
| 1 | Add a progress check to evidence rounds. If no criterion's sufficiency rises by about 0.05, stop researching and ask the human to decide on the current evidence or to name what is missing. | Finding 1 |
| 2 | Calibrate the gate, for example per-criterion bars or required vs nice-to-have criteria, using recorded outcomes. | Finding 2 |
| 3 | **Belongs to `phase_kernel_3_workflows`, not V0.** V0 has no policy catalog (ADR-054 §4). This run is a worked example for that phase and suggests its first candidate policy: when a decision's options are unknown, `external_practices` is a required need, researched **before** `generate_options`. | Finding 3 |
| 4 | Turn the gaps a synthesis names, and the concrete claims of human-added options, into evidence needs with their own queries. | Findings 4, 5 |
| 5 | Build queries goal-first. Put criteria text into queries. Revisit the 24-term cap and the need-template prefixes. | Finding 4 |
| 6 | Let the decision capability split compound goals into sub-decisions. | Finding 5 |
| 7 | Validate generated options against constraints stated in the goal. | Finding 6 |
| 8 | Trace fixes: drop or nest the LangGraph callback spans; give Jev generations real start and end times; put paths and evidence ids into retriever and rerank outputs; backfill `root_task_id`; set `service.name`. | Finding 7 |

## Re-reading this trace

Our Langfuse organization returns `410 LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION` on `GET /api/public/traces/{id}`. Read traces through `GET /api/public/v2/observations` with `traceId`, a mandatory `fromStartTime`/`toStartTime` window, and `fields=core,basic,io,metadata,…`. A small client lives in the workspace-root `scripts/langfuse/` folder (outside this repository): `fetch_trace.py <trace id or URL> [--io] [--out file.json]`.

The run's local artifacts (`run.json`, `events.jsonl`, interaction packets, submissions) were written to a Claude Code session scratchpad and are temporary. The Langfuse trace is the durable record.
