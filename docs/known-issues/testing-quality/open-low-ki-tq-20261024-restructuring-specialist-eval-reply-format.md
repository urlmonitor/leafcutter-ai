---
title: "KI-TQ-20261024-restructuring-specialist-eval-reply-format — the restructuring-specialist live eval scores 0/2 because the agent's reply does not carry the skills_applied labels the eval reads"
description: "low — the live label eval for restructuring-specialist (scripts/evals/sets/restructuring-specialist.jsonl, threshold 1.0, response_label_field skills_applied) scored 0/2 on 2026-10-24: rs-001 'Model response must supply an explicit boolean for every label axis', rs-002 'No JSON object found in model reply'. The template's report contract asks for a final JSON object with skills_applied, but the replies did not give one the harness could read. Pre-existing, not caused by the produced-tests work; CI's agent-eval job is informational, so it does not block merges."
type: reference
category: reference
status: active
created: '2026-10-24'
last_updated: '2026-10-24'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20261024-restructuring-specialist-eval-reply-format — the eval cannot read the agent's labels

> Filed 2026-10-24. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The eval says nothing about whether the agent picks the right skill, because
  no row gets as far as a label. It blocks nothing: the CI agent-eval job is informational
  (`.github/workflows/agent-evals.yml`:3).
- **Status:** open, no AC.
- **Occurrences:** 1 live run, 2026-10-24 (CLI backend, model sonnet, 0 of 2 rows, both counted as
  invocation failures). Not caused by the TQ-200d produced-tests work, which does not touch this
  agent, its template or its eval set.
- **First seen:** 2026-10-24 · **Last seen:** 2026-10-24
- **Where** (line numbers at `origin/main` `849791105`):
  - `scripts/evals/agent_eval_config.json`:99-110. Label mode, input field `demand`,
    `response_label_field: "skills_applied"`, one axis `complexity-reduction`, threshold 1.0.
  - `scripts/evals/sets/restructuring-specialist.jsonl`:1-2. rs-001 is a complexity demand
    (expects `complexity-reduction: true`), rs-002 a file-size demand (expects `false`). Both name
    `scripts/planner.py`, a file the agent cannot see: the label run disables tools
    (`--tools ""`, `scripts/evals/run_agent_eval.py`:279-280).
  - `templates/agents/restructuring-specialist.md`:145-166, the report contract: end the reply with
    one JSON object whose `skills_applied` always has a `complexity-reduction` boolean.
  - `scripts/evals/run_agent_eval.py`:336-364, `extract_json_object`. Takes the whole reply if it
    parses, else the **first** balanced `{...}` span; none gives "No JSON object found in model
    reply" (:353).
  - `scripts/evals/run_agent_eval.py`:367-378 and :1328-1337. `_extract_labels` returns
    `skills_applied` when it is an object, else the whole reply; a missing or non-boolean axis gives
    "Model response must supply an explicit boolean for every label axis" (:1333).

## Symptom

`run_agent_eval.py --agent restructuring-specialist` reports accuracy 0.0 with
`invocation_failures: 2`: rs-001 fails with "Model response must supply an explicit boolean for
every label axis", rs-002 with "No JSON object found in model reply".

## Mechanism

What the results file shows is the failure, not the reply: the record keeps `predicted: {}` and
the `parse_error`, but not the model's text. The likely causes, not yet confirmed against a saved
reply:

1. **rs-002: no JSON at all.** Asked to restructure a file it cannot read, with no tools, the agent
   answered in prose (for example asking for the file) and skipped the report object.
2. **rs-001: a JSON object the harness reads wrongly.** Either the reply's object lacked a boolean
   `complexity-reduction` under `skills_applied`, or an earlier `{...}` in the reply (a code or
   config snippet) was taken as the first balanced object instead of the final report.
3. **The eval input does not match how the agent is dispatched for real.** The template expects
   to read the file, run the checker and report a measured figure; the eval gives it neither the
   file nor tools, so the agent is pushed off its report contract.

## Detection

A restructuring-specialist results file whose rows carry a `parse_error` and an empty `predicted`.
To see which cause applies, rerun one row and keep the raw reply.

## Workaround

None needed for merging, since the job is informational. Do not read the 0% as a judgement of
the agent's skill choice.

## Suggested fix

Directions only; nothing here is applied.

- **Tighten the template's report section** for the case where the agent cannot act: say that the
  report object is still required (`outcome: "could_not_act"`, `skills_applied` filled in) and that
  it must be the last thing in the reply.
- **Or tighten the eval input**: tell the agent it has no file access and must answer only with the
  report object stating which skills it would apply, or supply the file content in the input.
- **Keep the raw reply on a parse failure** in the results record, so the next failure can be
  diagnosed without a rerun.
- **Consider reading the last balanced object**, not the first, for agents whose contract puts the
  report at the end.
- Rerun the eval after the change.

**Pattern:** an eval that gives the agent a task it cannot do in the eval's setting, then scores
whether it still filled in the report.
