# Agent evaluation scripts

`run_agent_eval.py` runs the configured classifier and artifact evaluations. Gold
rows and pass thresholds live in `agent_eval_config.json` and its referenced sets.

Artifact evaluations use a temporary copy of the configured Product Truth store.
`artifact_dependencies.py` adds only declared schemas, example receipts, planning
sources and referenced ACs, plus the reviewed model resolver's local Python import
closure. It preserves the existing capability marker, rejects linked or escaping
paths, and excludes environment files and caches. It does not call providers.
`artifact_validation.py` checks canonical validator completion and target reports;
`label_scoring.py` contains the classifier's pure scoring calculations.
`cli_envelope.py` reads the `claude` CLI's JSON envelope. When the CLI exits
non-zero with empty stderr, as it does with no credential, the row error carries
the envelope's `result` text, for example `Not logged in · Please run /login`.

Store validation compares new errors with the baseline. The produced flow's
contracts also require an independent successful check, so an unavailable model
or receipt cannot be hidden by an identical baseline error. A crashed validator
is a harness error. Classifier invocation or malformed-response failures stay in
the accuracy denominator without becoming fabricated negative predictions.

Offline verification: `python -m unittest unit_tests.product_truth.test_flow_io_contract_eval`.
Self-test and gold-score modes prove harness behavior, not model quality; they
must not replace live evaluation receipts or their freshness stamps.

## The CI gate is informational

`.github/workflows/agent-evals.yml` (`Agent evals (affected)`) is **not** a
required check. This was the owner's decision on 2026-10-06
(`TICKET-20261006-AgentEvalGateHonestAboutCredentials`).

- **No credential.** The repository has no `ANTHROPIC_API_KEY` secret. When a PR
  affects an agent, the `Preflight — model credentials` step fails before any row
  runs, with an explicit "no model credentials" error and no score. A red check
  from that step means nothing was evaluated. It does not mean an agent regressed.
- **Triggers.** Each agent's `triggers` list in `agent_eval_config.json` names only
  that agent's own files:
  - its template, its own schema and its eval set;
  - the product-truth store paths it reads;
  - the store entry scripts the harness runs;
  - the shared harness.

  The list leaves out the sandbox's transitive contract dependencies, such as
  kernel, knowledge or integrations code, `config/`, `reports/`, `docs/analysis/`
  and AC YAML. So a PR that only touches those affects no agent.
- **Making it blocking.** This needs two repository-settings changes: add the
  secret, then add the check to the main ruleset's required status checks.
