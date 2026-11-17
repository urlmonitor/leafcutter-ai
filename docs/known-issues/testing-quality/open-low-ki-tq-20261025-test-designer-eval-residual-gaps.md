---
title: "KI-TQ-20261025-test-designer-eval-residual-gaps — the TQ-200d-3 test-designer scoring does not score the protected fields and reads some name and record shapes strictly, so a live test-designer score can be falsely red or green"
description: "low — the TQ-200d-3 test-designer eval scoring left residual gaps, accepted for now after review. No kind compares the fields the designer must leave byte-identical (criteria, test_intent, assigned_agent, test_required and the rest), so a design that rewrites them passes unless validate_ac_schema.py rejects it. A condition token matches as contiguous words anywhere in a must_catch name, so retry_due_logging satisfies retry_due. The one-entry and distinct-name rules are strict readings the user kept: a gate design with one entry per condition, or one name covering both conditions, scores red. Exact names match by the wrong-version runner's trim-and-casefold key (OQ-15), so a trailing period or an extra word misses. designer_design_written says 'test_design_authorship missing or empty' when the block is present with the wrong step. The live dispatch input may drift from plan-feature.js dispatchTestDesign (OQ-13; the seam test pins only the ingredients). An empty must_catch: [] fails designer_record_schema_valid, not the trap kind. Recorded gold scoring is unaffected."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261025-sql-test-writer-eval-residual-misreads.md
---

# KI-TQ-20261025-test-designer-eval-residual-gaps — the test-designer scoring leaves the protected fields unscored and reads some names strictly

> Filed 2026-10-25. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. Each gap needs a particular record or name shape. The recorded gold rows
  score correctly; a live test-designer run that happens to use one of these shapes can be scored
  falsely red or falsely green. The live before-score is deferred (OQ-11) and user-triggered, so no
  automatic run is affected today.
- **Status:** open, no AC. Accepted for now after the TQ-200d-3 review; items 3 and 4 are
  deliberate readings the user saw and kept, recorded so a live red is read correctly.
- **Occurrences:** 1 (the TQ-200d-3 review, 2026-10-25; found by reading the code and probing the
  kinds directly against the recorded gold records, not seen in a live run).
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers in the TQ-200d-3 work as staged on `fastlane/tq-200d-3`, on top of
  `e697353f8`; the modules under `scripts/evals/designer_eval/` and the set
  `scripts/evals/sets/test-designer.jsonl` are new in that work):

### Scoring gaps (`scripts/evals/designer_eval/kinds.py`)

| Gap | Site | Cause |
|---|---|---|
| A design that rewrites `criteria`, `test_intent` and `assigned_agent` passes all four bug-fix kinds (probed: the gold TDE-9701 with those three fields rewritten scores 4/4) | `KINDS` :180-186; `schema_valid` :109-122 | The template requires these fields, `test_required` and the other `it_requirements` keys to stay byte-identical (`templates/agents/test-designer.md`:160-163), but no kind reads them. Only `designer_record_schema_valid` could notice, and only when the rewrite happens to break the schema. |
| `must_catch: ["revert the fix", "retry_due_logging"]` passes `designer_names_wrong_versions` on the bug-fix row (false pass) | `has_token` :74-77, `words` :69-71, `WORD_RE` :35 | `_` separates words, so `retry_due_logging` reads as `retry due logging` and the token `retry_due` (`retry due`) is found as a contiguous word sequence inside it. The name is not required to say the condition is dropped. |
| A gate design with one entry per condition fails `designer_names_wrong_versions` (probed: `test_window` naming the window-open drop and `test_limit` naming the position-limit drop, each with "the gate always allows", is still missing `'position limit'`) | `names_wrong_versions` :136-146 (:142), `missing_in` :98-106 | All required names must sit in ONE entry: the kind takes the best single entry and never unions entries. A strict reading of the AC, kept by the user. |
| One name covering both gate conditions fails (probed: "drop the window-open and position-limit conditions" and "the window open position limit check skipped" both leave `'position limit'` missing) | `unmatched_tokens` :80-95 | Each token needs a distinct name: the matching assigns one name to one token. A strict reading of the AC, kept by the user. |
| "The gate always allows." and "the gate always allows trades" do not match the exact name "the gate always allows" (false failure); "  The Gate Always Allows  " does | `missing_in` :100-103; `wrong_version_key` / `norm_name` (`scripts/build_orchestration/_wvr_scope.py`:44-52) | Exact names compare by the wrong-version runner's key, which only trims and case-folds; punctuation and extra words are part of the name. This follows OQ-15 and the runner's own matching rule. |
| `designer_design_written` reports "test_design_authorship missing or empty" for a block that is present with `step: it-po` | `design_written` :167-176 (:171, :176) | The wrong-step case and the missing case share one check and one message. Diagnostic only: the row still fails, as it should. |

### Dispatch input (`scripts/evals/designer_eval/dispatch.py`)

| Gap | Site | Cause |
|---|---|---|
| The live input wording may drift from what plan-feature.js sends the designer | `build_dispatch_input` :37-50; `dispatchTestDesign` (`templates/workflows-js/plan-feature.js`:2046-2068) | The eval writes its own prompt text (the row's `input` line first, "Write the test design only", the stripped stdout of `design_prepass.py` at :34) where the pipeline sends a role sentence, an optional feedback line, `JSON.stringify(pre.report)` and both design groups. OQ-13 accepts this; the seam test (`unit_tests/evals/tq200d3/test_tq200d3_seam.py`:35-89) pins only the ingredients — ids, the verbatim report, `ac_store_path`, the test-design group only, nothing the row scores — not the wording. |

### Empty `must_catch` on the trap (`scripts/ac_store/_ac_schema_test_spec_validators.py`)

| Shape | Site | Cause |
|---|---|---|
| A trap design whose entry carries `must_catch: []` fails `designer_record_schema_valid` while `designer_states_neither` passes (probed on the gold TDE-9703) | `_must_catch_field_errors` :156-168 (:164-168); `names_of` (`kinds.py`:63-66), `states_neither` (`kinds.py`:149-159) | The validator rejects an empty list ("absence already means 'none named'"); the trap kind ignores it because it holds no non-blank name. The row is red for the validator's reason, not the trap's. |

## Symptom

A live test-designer eval row fails an assertion although the agent did the right thing (for
example it split the gate design into one entry per condition, covered both conditions in one
name, or wrote "The gate always allows." with a period), or passes although it did not (for
example it rewrote `criteria` or `test_intent` while designing, or named a wrong version
`retry_due_logging` that does not drop the condition). Recorded gold rows are not affected.

## Detection

Read the failing assertion's `detail` in the results file. A "still missing: 'position limit'"
(or `'window open'`) detail on a gate design whose entries do name each condition, a "still
missing: 'the gate always allows'" detail on a name that differs only in punctuation or a trailing
word, a "test_design_authorship missing or empty" detail on a record that has the block, or a
schema-validator failure naming `must_catch` on the trap row, is this issue. For a passing row,
diff the protected fields of the edited record against the fixture record by hand.

## Workaround

Re-read a failing or suspiciously passing live row by hand before acting on its score; for a pass,
compare the protected fields against
`scripts/evals/sets/test-designer/projects/<row>/eval_store/<id>.yaml`.

## Suggested fix

Directions only; nothing here is applied.

- **Protected fields:** add a kind (for example `designer_protected_fields_unchanged`) that loads
  the fixture record from the row's `fixture` and compares `criteria`, `test_required`,
  `test_intent`, `assigned_agent`, `implements_pattern`, `pattern_bindings`, `declared_files`,
  `covered_by`, `delivers_to`, `expects_from` and the other `it_requirements` keys to the edited
  record, and add it to every row.
- **Token matching:** require the token to be the condition the name drops (for example anchor it
  after a drop / remove / skip verb, or require the name to end at the token or its variant)
  rather than any word sequence inside the name.
- **Exact names / strict rules:** none proposed; OQ-15 and the user's decision stand. Revisit only
  if live runs show the designer routinely writes these shapes.
- **Diagnostic:** split the authorship check so a present block with the wrong step reports
  "step is <x>, not test-designer".
- **Prompt drift:** build the input from a shared template with plan-feature.js, or add a seam
  assertion on the wording, if drift is ever seen to change a live score.
- **Empty `must_catch`:** none; the validator's rule is correct. Read a trap-row schema failure
  naming `must_catch` as this shape.

**Related.** `KI-TQ-20261025-sql-test-writer-eval-residual-misreads` is the same family in the
TQ-200d-2 sql-test-writer scoring: residual scoring gaps of a per-agent eval, accepted after review,
that can make a live score falsely red or green while the recorded gold scoring is unaffected.

**Pattern:** a scorer that reads only the fields it was built to judge, and matches names by
words found anywhere in them — so what the agent must leave alone goes unchecked, and a name that
merely mentions a condition reads as naming its removal.
