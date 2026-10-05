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

Store validation compares new errors with the baseline. The produced flow's
contracts also require an independent successful check, so an unavailable model
or receipt cannot be hidden by an identical baseline error. A crashed validator
is a harness error. Classifier invocation or malformed-response failures stay in
the accuracy denominator without becoming fabricated negative predictions.

Offline verification: `python -m unittest unit_tests.product_truth.test_flow_io_contract_eval`.
Self-test and gold-score modes prove harness behavior, not model quality; they
must not replace live evaluation receipts or their freshness stamps.
