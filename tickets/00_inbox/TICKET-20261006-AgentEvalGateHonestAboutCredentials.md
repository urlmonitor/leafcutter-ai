---
title: "Agent-eval gate: fail honestly without model credentials, and trigger only on the agents' own files"
status: in_progress
components:
  - testing_quality
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
roadmap_phase: phase_1
tags:
  - agent-evals
  - ci
  - known-issue
last_updated: 2026-10-06
files_touched:
  - .github/workflows/agent-evals.yml
  - scripts/evals/run_agent_eval.py
  - scripts/evals/cli_envelope.py
  - scripts/evals/agent_eval_config.json
  - scripts/evals/README.md
  - unit_tests/evals/test_cli_failure_detail.py
  - unit_tests/evals/test_agent_eval_config_triggers.py
  - docs/known-issues/testing-quality/open-high-ki-tq-002.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20260908-0900.md
---

# Agent-eval gate: fail honestly without model credentials, and trigger only on the agents' own files

## Actor / Goal
In order that a red `Agent evals (affected)` check means something, we need the job to say
"no model credentials" when it has none, instead of printing a score, and to fire only when a
PR touches an evaluated agent's own files. Then a reader never debugs an agent prompt for what
is really a missing secret, and ordinary PRs are not marked red by a gate that cannot run.

## Context
**Diagnosis (verified 2026-10-06).**
- **No credential.** The repository has no `ANTHROPIC_API_KEY` secret: `gh secret list` shows
  only the three `LEAFCUTTER_NEO4J_*` secrets. `.github/workflows/agent-evals.yml:71` therefore
  passes an empty value to the `claude` CLI. The CLI exits 1 with empty stderr, and its stdout is
  `{"is_error":true,"result":"Not logged in · Please run /login"}`. Every row scores 0/3.
- **Not a required check.** Ruleset `17810993` (`require-ci-lint`) requires exactly five contexts:
  `Lint (ruff)`, `Component vocab style (components.json)`, `Proof-of-done coverage check (BO-2500b)`,
  `Changelog entry present` and `AC store valid`. `Agent evals (affected)` is not one of them.
- **Blank error.** `scripts/evals/run_agent_eval.py:795-797` (`invoke_agent_writer`, artifact mode)
  and `:291` (`invoke_via_cli`, label mode) build the error message from stderr only. So the
  per-row error reads `agent CLI exited 1:` with nothing after it.
- **Widened triggers.** Commit 974fa757f (#1009, 2026-10-05) widened the `triggers` of
  `flow-author` and `mock-data-author` in `scripts/evals/agent_eval_config.json` (`:56-63` and
  `:103-110`). It added the sandbox's transitive contract-dependency roots: `kernel/**/*.py`,
  `knowledge/**/*.py`, `integrations/**/*.py`, `kernel/schemas/**`, `config/**`, `reports/**`,
  `docs/analysis/**`, `docs/acceptance-criteria/**/*.yaml` and `docs/product-truth/**`-wide globs.
  The gate now fires on most PRs. Each time it fires, it fails dishonestly.

**Owner decision, 2026-10-06: "Honest failure + narrow".**
1. With no credential, the job fails up front with an explicit "no model credentials" message
   instead of a score.
2. The widened triggers go back to the agents' own files.
3. The gate stays informational, not required.
4. No API key is added, and nothing is spent on model calls.

**Related known issues.**
- `docs/known-issues/testing-quality/open-high-ki-tq-002.md`: its required-check list is stale and
  names `Test suite (pytest)`.
- `docs/known-issues/testing-quality/open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md`
- `docs/known-issues/testing-quality/open-high-ki-tq-20260908-0900.md`

**File-size ratchet.** `run_agent_eval.py` is already far above its 400-line limit
(GE-127b-1 ratchet). The stdout fallback therefore lives in a new sibling module,
`scripts/evals/cli_envelope.py`. It also takes over the two copies of the envelope-reading code,
so `run_agent_eval.py` gets shorter. This follows the same split pattern as
`artifact_dependencies.py`, `artifact_validation.py` and `label_scoring.py`.

## AC References
- Relates to TQ-200b-2: the gate reports which rows failed, and why.
- Amends the trigger manifest of TQ-200b-3 (`scripts/evals/agent_eval_config.json`). The owner chose
  each agent's own surface over the sandbox's transitive contract dependencies.
- Relates to TQ-200b-4. Its "REQUIRED gate" clause stays unmet by owner decision, so TQ-200b-4
  stays `in_progress`.

## Acceptance Criteria
- [ ] AC-1: With no credential, the job fails before any row runs. It shows an explicit
  infrastructure message ("no model credentials") and reports no score. This applies to a PR that
  touches an agent's trigger closure. A PR that affects no agent still fast-passes and says that
  nothing was evaluated.
- [ ] AC-2: When the CLI exits non-zero with empty stderr, the row error carries the `result` text
  from the CLI's stdout (for example `Not logged in · Please run /login`). This holds in label mode
  (`parse_error`) and in artifact mode (`error`). Non-empty stderr is still reported first.
- [ ] AC-3: The `flow-author` and `mock-data-author` triggers are back to their own files, as before
  974fa757f: their template, their own schema, their eval set, the product-truth store paths they
  already watched, the store's entry scripts and the shared harness. A PR that only edits AC YAML,
  analysis docs or kernel code triggers neither agent.
  - Kept from 974fa757f, because they are the agents' own surface: the harness modules split out
    of `run_agent_eval.py` (`artifact_dependencies.py`, `artifact_validation.py`), and, for
    `flow-author` only, `docs/product-truth/scripts/product_truth_contracts.py`, which the harness
    runs to score the flow target.
  - The new harness module `cli_envelope.py` is added to all three agents.
- [ ] AC-4: The gate stays non-required. The workflow header and `scripts/evals/README.md` document
  it as informational.
- [ ] AC-5: KI-TQ-002's required-check list is corrected to the real five required checks:
  `Lint (ruff)`, `Component vocab style (components.json)`, `Proof-of-done coverage check (BO-2500b)`,
  `Changelog entry present` and `AC store valid`. The other two KIs get a dated note.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | bash simulation of the preflight step (no automated test: workflow shell) | `.github/workflows/agent-evals.yml` | |
| AC-2 | `unit_tests/evals/test_cli_failure_detail.py` | `scripts/evals/cli_envelope.py`, `scripts/evals/run_agent_eval.py` | |
| AC-3 | `unit_tests/evals/test_agent_eval_config_triggers.py` | `scripts/evals/agent_eval_config.json` | |
| AC-4 | review | `.github/workflows/agent-evals.yml`, `scripts/evals/README.md` | |
| AC-5 | review | `docs/known-issues/testing-quality/*.md` | |

## Test Requirements

```yaml
tests:
  - name: test_empty_stderr_row_error_carries_cli_stdout_result
    file: unit_tests/evals/test_cli_failure_detail.py
    covers:
      - TQ-200b-2
    angle: criterion
    framework: pytest
    type: unit
    asserts: |
      A label-mode row (run_label_eval through the real invoke_via_cli) and an artifact-mode call
      (invoke_agent_writer) both run against a CLI that exits 1 with empty stderr and the
      not-logged-in envelope on stdout. Each row error / raised message contains
      "Not logged in · Please run /login".
  - name: test_stderr_still_wins_and_non_json_stdout_is_quoted_raw
    file: unit_tests/evals/test_cli_failure_detail.py
    covers:
      - TQ-200b-2
    angle: boundary
    framework: pytest
    type: unit
    asserts: |
      Non-empty stderr is reported, not the stdout result. With empty stderr, a stdout that is not
      JSON is quoted raw. A zero exit still returns the envelope's result text.
  - name: test_change_outside_the_agents_own_files_triggers_no_agent
    file: unit_tests/evals/test_agent_eval_config_triggers.py
    covers:
      - TQ-200b-3
    angle: criterion
    framework: pytest
    type: unit
    asserts: |
      Against the real agent_eval_config.json, a change that only touches an AC YAML, an analysis
      doc, kernel/knowledge/integrations code, kernel schemas, config/ or reports/ leaves every agent
      unaffected.
  - name: test_the_agents_own_files_still_trigger_them
    file: unit_tests/evals/test_agent_eval_config_triggers.py
    covers:
      - TQ-200b-3
    angle: criterion
    framework: pytest
    type: unit
    asserts: |
      Each agent's template and eval set still triggers that agent. The shared harness modules,
      including cli_envelope.py, trigger all three agents.
```

## Comments

## Implementation Tasks
- [x] `agent-evals.yml`:
  - Split the selection into its own step, which publishes `affected` as a step output.
  - Add a `Preflight — model credentials` step. It runs only when agents are affected, and when
    `ANTHROPIC_API_KEY` is empty it fails with `::error title=Agent evals - no model credentials::`. The title uses a dash because a
    colon would end the annotation's `title` property.
  - Gate the CLI install and the eval steps on there being affected agents.
  - Rewrite the header so it documents the gate as informational, citing the owner decision of
    2026-10-06.
- [x] `scripts/evals/cli_envelope.py`:
  - `failure_detail(stderr, stdout)` returns stderr, else the stdout envelope's `result`, else the
    raw stdout.
  - `envelope_result(completed, label, error)` returns the reply text and raises the caller's error
    type with the real cause.
- [x] `run_agent_eval.py`: both invokers use `envelope_result`. `invoke_via_cli` runs with
  `check=False`, so a non-zero exit reaches the same reporting path. The file gets shorter.
- [x] `agent_eval_config.json`: narrow the triggers as AC-3 describes, add `cli_envelope.py` to all
  three agents, and note in each artifact agent's `notes` why the closure is narrow.
- [x] `scripts/evals/README.md`: add an informational-gate section.
- [x] KI updates (AC-5).
- [x] Tests (see Test Requirements).

## Out of Scope
- Adding an API key or any other credential, or spending on model calls.
- Making `Agent evals (affected)` a required check.
- Implementing `invoke_via_api`.
- Splitting derived from authored product-truth paths in the trigger closures (fix-direction 4 of
  KI-TQ-20260907).
- The local `check-eval-staleness` hook's wording. Its fail-open warning
  (`templates/scripts/commit_guardian/check_eval_staleness.py`) and its `_comment` in both
  `commit_guardian.json` manifests still call the CI eval check "required". Correcting that is a
  follow-up, because those files are package templates and need a rebuild.

## Risk & Safety
- **Touches money?** No. No key is added and no model is called.
- **Touches data?** No.
- **Reversibility:** a plain revert. The check is not required, so no merge is blocked either way.
- **Contract risk:** fewer PRs trigger the live evals, so a change to a sandbox dependency (for
  example a kernel model module) no longer re-runs `flow-author`. The owner accepted this on
  2026-10-06. The gate cannot run without a credential anyway.
