---
title: "The test designer has an eval that checks it names wrong versions for fixes and gates, and none for new behaviour"
date: "2026-10-25"
time: "18:00"
type: manual
components:
  - testing_quality
summary: "New local_only eval set for test-designer in the produced-tests mode. Bug fix: one guarding test entry names 'revert the fix' and a wrong version naming the retry_due condition. Gate: one entry names a wrong version per condition (window open, position limit) and 'the gate always allows'. New behaviour (the trap): any must_catch or discrimination angle fails the row. Every row needs a written, schema-valid design; the bug fix / gate / neither judgement is read from the record's fields, never from the reply."
description: "TQ-200d-3. New sub-package scripts/evals/designer_eval/ (kinds.py: designer_record_schema_valid via validate_ac_schema.py, designer_states_judgement, designer_names_wrong_versions with the runner's wrong_version_key/ALIASES for exact names and word-sequence condition tokens with fixed variants, one distinct name each in one entry, designer_states_neither, designer_design_written; dispatch.py: build_dispatch_input embeds design_prepass.py's stdout verbatim and asks for the test-design group only), spread into produced_tests_scoring.KINDS; produced_tests_mode.row_input uses the config input_builder hook. agent_eval_config.json registers test-designer (local_only, tools Bash/Read/Write/Edit, support_scripts ac_store). Set sets/test-designer.jsonl with pending fixture records and recorded gold designs. User decisions 2026-10-25: OQ-14 superseded (the trap enforces 'for neither, no entry carries must_catch or angle: discrimination'), OQ-15 amended (fixed condition variants), and a written design is required. Existing tests: the agent list and the sets list gain test-designer (sweep recorded). Wrong-version gate: all 11 named versions caught; one must_catch moved to the bug-fix test, since the trap no longer depends on alias matching. Residual gaps filed as KI-TQ-20261025-test-designer-eval-residual-gaps (low)."
commits:
breaking: false
---

## Entry

The test designer now has its own eval. Given a bug fix, it must name the fix undone and a wrong
version that drops the condition involved. Given a gate, it must name one wrong version per
condition and the gate that always allows. Given new behaviour, it must name none at all, since
there was no earlier version to go back to. Its choice is read from the test design it writes into
the requirement record, never from what it says in its reply. The eval runs locally only.
