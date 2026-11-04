---
title: "Reference: Produced-Tests Eval Assertion Kinds"
description: "Lookup for what an assertion kind of the produced-tests eval is, how a row lists its kinds, the four family pages that hold one entry per kind and the agents each serves, and the tests that keep the entries in step with the scorers and templates."
type: reference
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
  - documentation_system
related_docs:
  - scripts/evals/README.md
  - docs/reference/wrong-version-runs.md
  - docs/how-to/documentation/write-reference.md
  - docs/reference/document-length-standard.md
---

# Produced-Tests Eval Assertion Kinds

Lets a reader look up every assertion kind the produced-tests eval scores with, and find the family page that holds its entry. The 31 registered kinds are described on four family pages; this hub holds no entry.

## Assertion kind

An assertion kind is a named check that scores one part of the output of an agent in the produced-tests eval (`scoring_mode: "produced_tests"`). It is a function registered by name in `KINDS` in `scripts/evals/produced_tests_scoring.py` (the database-setting, sql-test-writer and test-designer kinds are registered by sub-registries it merges).

| Property | Value |
|---|---|
| Listed by | A row's `expected.assertions`: a list of `{"kind": "<name>", ...}` objects, where the other keys are that kind's arguments (`file`, `contains`, `module`, `record`). Rows list kinds by name only; they hold no rule. |
| Result | `{"passed": bool, "detail": str}`. A row passes only when every assertion passes. |
| Unknown name | Fails the assertion with "unknown assertion kind"; it is never skipped. |
| Determinism | Every kind is deterministic and calls no model. A kind reads text, parses source with `ast`, parses YAML and runs `validate_ac_schema.py` (the designer kinds), or runs pytest or the wrong-version runner locally. A judge, when a row has a rubric, is secondary and never decides a test half. |
| What a kind reads | Produced test files, the completion report, the recorded commands of a transcript, the to-run-later file, a wrong-version run verdict, or the requirement record a designer edited. |

## Family pages

Each registered kind has exactly one entry, on the page of the module that registers it.

| Family page | Kinds | Agents whose sets use them |
|---|---|---|
| [Test-writer](produced-tests-eval-assertion-kinds-test-writer.md) | 10: `fixture_seeds_moved_input`, `counts_rows_and_non_null`, `asserts_known_seeded_value`, `test_files_present`, `test_fails_on_wrong_result`, `fails_on_mutants`, `produced_test_green`, `report_mentions`, `report_lists_wrong_version`, `wrong_version_run` (`produced_tests_scoring.py`, `produced_tests_mutants.py`, `produced_tests_runs.py`) | test-writer; `test_files_present` also sql-test-writer; `report_mentions` also test-runner |
| [Database-setting](produced-tests-eval-assertion-kinds-database-setting.md) | 11: `db_test_uses_setting`, `commands_run_checker`, `commands_no_db_address`, `commands_ran_pytest`, `report_names_no_address`, `report_says_unconfigured`, `report_says_not_run`, `report_says_stopped_before_database`, `report_silent_on_setting`, `report_states_outcome`, `report_pass_quotes_a_count` (`produced_tests_db.py`, `produced_tests_commands.py`, `produced_tests_reports.py`) | test-runner and test-writer; `db_test_uses_setting` also sql-test-writer; the three `commands_` kinds test-runner only |
| [SQL-test-writer](produced-tests-eval-assertion-kinds-sql-test-writer.md) | 7: `sql_to_run_later_names_wrong_version`, `sql_counts_rows_and_non_null`, `sql_answers_labelled`, `sql_observed_labels_quote_a_run`, `sql_report_claims_no_observed_run`, `sql_report_names_db_setting`, `sql_report_says_not_run` (`sql_test_writer_eval/`) | sql-test-writer |
| [Test-designer](produced-tests-eval-assertion-kinds-test-designer.md) | 5: `designer_record_schema_valid`, `designer_states_judgement`, `designer_names_wrong_versions`, `designer_states_neither`, `designer_design_written` (`designer_eval/`) | test-designer |

## Entry format

An entry is headed ``### `<kind>` `` and holds seven labelled parts, each once, with content: `Used by`, `Reads`, `Passes when`, `Fails when`, `Passing example`, `Failing example` and `Template sentence`.

| Part | Content |
|---|---|
| `Used by` | The agents' sets, and the rows, that list the kind. |
| `Reads` | What the kind examines and the spec keys it takes. |
| `Passes when` / `Fails when` | The rules as the code applies them now, and the detail a failure gives. |
| `Passing example` / `Failing example` | A concrete input and its outcome. |
| `Template sentence` | A blockquote of the sentence of an agent template the kind checks, word for word, then a line `- templates/agents/<name>.md`; or `none - <reason>` when the kind checks no template sentence. |

## Drift guarantee

Tests in `unit_tests/evals/tq200d1ii/` read the real pages, the real registry and the real templates, so the kind set, the entry parts and the quoted template sentences cannot drift unseen. The Passes when, Fails when and example parts are not tested.

| Test | Fails when |
|---|---|
| `test_every_registered_kind_has_exactly_one_entry` | A kind is registered with no entry, a page has an entry for a kind no longer registered, a kind has two entries, or an entry is on the wrong family page. |
| `test_every_entry_has_all_required_parts` | An entry lacks a part, repeats one or leaves one empty. |
| `test_quoted_template_sentences_appear_verbatim` | A quoted sentence no longer appears, word for word, in the template it cites. |
| `test_evals_readme_links_the_hub_and_lists_no_kind_names` | The eval README loses its link to this page or lists kind names again. |
| `test_reference_index_lists_the_hub_once` | `docs/reference/README.md` does not list this page once, lists a family page, or a family page does not link back here. |

A change to a scorer's rules or to a quoted template sentence edits the matching entry in the same change.

## See Also

- [Eval README](../../scripts/evals/README.md) - the produced-tests mode, its rows and how to score the recorded gold offline.
- [Wrong-version runs](wrong-version-runs.md) - the runner behind `wrong_version_run`.
- [How to write a reference doc](../how-to/documentation/write-reference.md) - the conventions these pages follow.
- [Document length standard](document-length-standard.md) - why the reference is a hub plus four pages.
- `scripts/evals/produced_tests_scoring.py` - the kind registry and `score_row`.
