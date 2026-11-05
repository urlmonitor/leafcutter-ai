---
title: "KI-TQ-20261030-test-command-single-file-pattern-defaults-to-plain-script — the shipped skills_config key test_command_single_file_pattern defaults to running a test file as a plain Python script, a form that runs no pytest test"
description: "low — config/skills_config.schema.json and docs/reference/skills-config-fields.md give test_command_single_file_pattern the default `python unit_tests/live_trader/<file>.py`, and SETUP.md tells adopters to derive it from the live-trader command. Run that way, a pytest-style file only defines its tests and exits 0, so nothing is tested. No agent template reads the key today, so the default is latent; it is the same plain-script form TQ-200d-4-ii removes from the test-runner template."
type: reference
category: reference
status: active
created: '2026-11-01'
last_updated: '2026-11-01'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/resolved/resolved-low-ki-tq-20261025-test-runner-runs-a-test-file-as-a-script.md
  - docs/reference/skills-config-fields.md
  - docs/acceptance-criteria/testing-quality/TQ-200-per-agent-eval-coverage/TQ-200d-4-ii.yaml
---

# KI-TQ-20261030-test-command-single-file-pattern-defaults-to-plain-script — a shipped default that runs a test file as a script

> Filed 2026-11-01 (id fixed at the TQ-200d final gate on 2026-10-30, OQ-3). Index:
> [testing-quality.md](../testing-quality.md). Filename severity is the three-level index bucket
> (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** low. Latent: no agent template or script reads the key today, so nothing runs the
  default. An adopter or a future template that trusts it would run a test file as a plain script
  and could report success for a run that tested nothing.
- **Status:** open, no AC. Filed during the TQ-200d before-score fixes, which change only the
  test-runner template (TQ-200d-4-ii); this key is out of their scope by the user's decision.
- **Occurrences:** 0 observed runs; found by reading the shipped configuration while planning
  TQ-200d-4-ii.
- **First seen:** 2026-10-30 · **Last seen:** 2026-10-30
- **Where** (at `origin/main` `d62440669`):
  - `config/skills_config.schema.json`:106-110, `test_command_single_file_pattern`, `"default":
    "python unit_tests/live_trader/<file>.py"`.
  - `docs/reference/skills-config-fields.md`:102, the same default, described as the "Shell
    pattern for running a single test file".
  - `SETUP.md`:56, which tells the adopter to "Derive from live_trader command pattern".
  - An installed project's `.leafcutter/derived_skills_config.json` (an install output, not
    tracked) carries the derived value, for this repository `python tests/<file>.py`.
  - No file under `templates/`, `scripts/` or `.claude/` reads the key
    (`grep -rl test_command_single_file_pattern`, 2026-10-30).

## Symptom

None at run time today. The configuration documents and ships a single-file command of the form
`python <path>/<file>.py`.

## Mechanism

1. **The default is a plain script run.** `python <file>.py` imports the module and runs its
   top-level code. A pytest-style file only defines its test functions, and a `unittest` file
   runs only if it ends in `unittest.main()`.
2. **Such a run exits 0.** Nothing is collected or reported, so a caller that reads the exit
   status takes it as a pass. This is how the live test-runner reported "Status: PASS" for a run
   that tested nothing (`KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script`).
3. **The key duplicates a better source.** `testing_context.test_command` names the project's
   test runner; the single-file command is that runner with the file as its argument.

## Detection

`test_command_single_file_pattern` in a project's skills_config, or a default in the schema,
whose value starts with `python ` and does not contain `-m pytest`, `pytest` or `unittest`.

## Workaround

Do not use the key. Run one test file with the configured `testing_context.test_command` and the
file as its argument, or `python -m pytest <file>` when it is unset.

## Suggested fix

Directions only; nothing here is applied.

- **Retire the key.** Remove it from the schema, `docs/reference/skills-config-fields.md` and
  `SETUP.md`, and point readers at `testing_context.test_command` (which TQ-200d-4-iv declares in
  the schema).
- **Or point it at the configured test command.** Change the default and the SETUP guidance to
  `<testing_context.test_command> <file>`, falling back to `python -m pytest <file>`.

**Related.** `KI-TQ-20261025-test-runner-runs-a-test-file-as-a-script` is the same plain-script
form in the test-runner template; TQ-200d-4-ii removes it there.

**Pattern:** a shipped default command that names a concrete form instead of the project's
configured runner, and that exits 0 without testing anything.
