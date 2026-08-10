# IT-PO learning — package-surface validator forces the python-coder/llm-expert split on greenfield build-orchestration ACs

Captured 2026-07-21 during BO-2400 (fast-lane-build) technical enrichment.

## The classifier: python-coder + scalar `component: build-orchestration` == package-surface

`scripts/ac_store/validate_ac.py` (BO-2000d gate, also run by check-ac-schema)
classifies ANY AC with `assigned_agent: python-coder` AND scalar
`component in {build_pipeline, build-orchestration}` as *package-surface*. Such an
AC MUST have `it_requirements` as a **structured object** with all five keys:
`config_schema_fragment`, `reference_file_path`, `n_location_rule`,
`required_skills` (non-empty), `post_write_commands`. Critically,
**`reference_file_path` must resolve to a file that already exists in the repo** —
the validator does `(repo_root / ref).exists()`.

The classifier keys on the SCALAR `component`, not the `components` list.

## Consequence for greenfield features: it drives the agent-assignment split

A brand-new capability (fast lane) creates many NEW files with no existing
reference. You cannot make a python-coder + build-orchestration AC for a
greenfield file pass the validator (no real `reference_file_path`). So the
package-surface rule effectively PARTITIONS the leaves:

- **Deterministic Python helpers that EXTEND a real existing module → python-coder**,
  with `reference_file_path` pointed at that real file. On BO-2400:
  - batch selection → `scripts/ac_store/scan_ac_store.py`
  - green + coverage-tag gate → `scripts/ac_store/test_enforcement.py` (reuses
    `extract_covers_tag`)
  - prompt-assembly layout / cache TTL / prefix-churn checksum / prior-phase
    threading → `scripts/injection_builders.py`
  - per-invocation telemetry emit + fail-loud → `scripts/feedback/submit_feedback.py`
    (the canonical "append structured JSONL record + WARN-on-failure" surface;
    the 23-submit-failed incident behavior already lives there)
  - lane comparison report → `scripts/agent-health/generate_health_report.py`
    (already reads agent_telemetry.jsonl)
- **Loop orchestration / routing / gate flow-control (greenfield .js workflow +
  documented decision rule) → llm-expert.** These escape the package-surface
  classifier (agent != python-coder) and take a plain-list `it_requirements`.
  On BO-2400: the two-agent-invocation invariant, red-baseline gate + halt,
  green-gate commit refusal, "no heavy-path constructs", and the whole path-router
  (fast/heavy decision rule, ambiguous-default, override-wins) went llm-expert.

Note this diverges from the older memory rule "the .js workflow body =
python-coder". The registry gives llm-expert ownership of
`templates/workflows/*.md` (command prose) and agent/skill bodies, and NEITHER
agent formally owns `templates/workflows-js/*.js`. For greenfield build-orchestration
loop/orchestration work, routing to llm-expert both matches the "authoring the
loop/command surface" framing AND sidesteps the package-surface existing-file trap.
Flag as a caveat: if a deterministic gate is later implemented as a standalone new
Python module rather than as loop flow-control, re-route that AC to python-coder at
build time (it will then need a real reference_file_path — i.e. the file it creates
must exist first, or point at the module it extends).

## Reusable enrichment defaults for this feature class

- Structured `it_requirements` can carry a `constraints:` list (like BO-2200d-2)
  to hold the policy-level WHATs alongside the five machine-checked keys.
- Config knobs (cohesion cap M, cache TTL) belong in `config_schema_fragment` and
  an it_requirement "read from config, not hard-coded".
- Backfill/emit idempotency + fail-loud-on-sink-failure are recurring policy
  it_requirements; state the WHAT, let python-coder pick the HOW.
- Documentation gate (S7b): BO-2400a triggered [how-to, sequence-diagram,
  component-diagram] → 1 documentation-expert + 2 architecture-diagram-author ACs;
  reference-doc/how-to → documentation-expert. Doc ACs take `test_required: false`.
