# Bounded natural graph-operation selection: test-first record

Date: 2026-10-03. Worktree: `kernel-entity-context`. No live provider, network, or graph database is used by these checks. The real entity builder/recognizer, registered retrieval binding, research planner/continuations, serializers, and public run service are exercised; only external Jev and knowledge ports are controlled.

## Acceptance coverage

`tests/kernel/entity_context/test_knowledge_operation_selection.py` contains 16 functions / 51 parameter cases:

| AC | Behavioral checks |
|---|---|
| DK-300d-4 | Four actual service flows, finite targets, recognized components, natural descendants and typed dependent scope, canonical `all` collisions, actual catalog compatibility, actual KnowledgeService population execution |
| DK-300d-4-i | Nine rejected selections/bounds including paid missing/wrong-type answers, three paid-selection downstream failures |
| DK-300d-4-ii | Eight input/result scope restrictions, hostile meanings/caller data and exact serialized state bound, graph/native planner separation, denied population discovery with zero source reads |
| DK-300d-5 | Explicit exact/hybrid zero-selector bypass, two real repository fallback scope cases, four existing ordinary/empty/unavailable paths |
| DK-300d-5-i | Three unsupported exhaustive Ticket questions, both sibling merge orders and durable continuation/synthesis resume |

The Ticket question requests **all matching high or critical priority tickets**. It does not request sorting. Exact-record retrieval and ranked repository samples cannot establish this population's completeness. The classifier's separate `unsupported_population` choice preserves this limitation; ordinary `unsupported` does not universally veto a useful repository sibling.

## Strict red evidence

All commands use `C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe`, `AC_ENFORCE_STRICT=1`, `-q --tb=short -p no:cacheprovider`, and `tests/kernel/entity_context/test_knowledge_operation_selection.py`.

1. Core handoff: `--basetemp=reports/tmp-graph-select-red-core --junitxml=reports/entity-graph-selection-red-core.xml`: **9 failed, 5 passed**, 20.02 s. No errors/skips.
2. Complete specified functions: `--basetemp=reports/tmp-graph-select-red-corrected --junitxml=reports/entity-graph-selection-red-corrected.xml`: **23 failed, 11 passed**, 23.35 s. All failures are behavioral assertions; no errors/skips. This corrects an initial hostile-caller fixture field typo (`conversation_summary` to real `conversation`). The earlier edge report is retained without treating that fixture exception as valid red proof.
3. Additional completeness seam: `-k completeness_limitation --basetemp=reports/tmp-graph-select-red-siblings-corrected --junitxml=reports/entity-graph-selection-red-siblings-corrected.xml`: **2 failed, 34 deselected**, 17.60 s. Both fail because research reports `completed` after real native evidence and unsupported graph retrieval are merged. An earlier probe incorrectly identified the graph child by source-list equality; real planner also attached native locator-owner sources, so detection was corrected to membership.

Passing pre-implementation controls preserve existing explicit bypass, ordinary native retrieval, empty-vs-unavailable results, and preread denial behavior. They are reported honestly, not made artificially red. The oversize test was already protected by the common state bound. These existing controls remain subject to final verification and targeted mutation checks.

```yaml
completion_manifest:
  test_stubs_created: true
  all_tests_red: {result: true, meaning: "strict suite returned nonzero; existing passing controls retained"}
  red_baseline_captured: true
  ac_ids_covered: [DK-300d-4, DK-300d-4-i, DK-300d-4-ii, DK-300d-5, DK-300d-5-i]
  cross_layer_seam_answer:
    result: covered
    producing_side: "real entity builder/recognizer and research source planner"
    consuming_side: "registered retrieve.repository, real child artifact serializer and resumed research"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "RunService.start_run and build_bindings(...).resolve('retrieve.repository', '1.0.0').ainvoke"
red_baseline:
  - test_name: test_entity_question_selects_bound_graph_operation_and_yields_evidence[exact-ac]
    file: tests/kernel/entity_context/test_knowledge_operation_selection.py
    error: "AssertionError: ['kernel.intent', 'research.plan_needs', 'retrieval.rerank', 'research.assess']; assert 0 == 1"
  - test_name: test_selector_low_confidence_unknown_choice_and_budget_fail_closed[low_probability]
    file: tests/kernel/entity_context/test_knowledge_operation_selection.py
    error: "assert len(selection.operation_batches()) == expected_calls; assert 0 == 1"
  - test_name: test_selector_usage_is_preserved_on_execution_failure[foreign_result]
    file: tests/kernel/entity_context/test_knowledge_operation_selection.py
    error: "assert len(selection.jev.batches) == expected; assert 0 == 1"
  - test_name: test_repository_fallback_executes_native_retrieval_with_same_scope[True]
    file: tests/kernel/entity_context/test_knowledge_operation_selection.py
    error: "assert len(batches) == 1; assert 0 == 1"
  - test_name: test_ticket_completeness_limitation_survives_sibling_merge_and_resume[True]
    file: tests/kernel/entity_context/test_knowledge_operation_selection.py
    error: "AssertionError: ranked sibling hits cannot establish an exhaustive population; assert 'completed' != 'completed'"
```

Full parameter-level failure records are retained in the XML files.

## Review additions and corrections

Additional strict red reports preserve the evaluator/correction loop:

- `entity-graph-selection-red-malformed.xml`: wrong-type paid answer loses usage; missing-answer control already passed (1 failed / 1 passed).
- `entity-graph-selection-red-targets.xml`: recognized Component absent from the real index, descendants/dependent operations not offered for their valid targets, and graph child widened with a native source owner (4 failed).
- `entity-graph-selection-red-catalog.xml`: an unimplemented policy operation was offered and scalar component `all` selected the first component (2 failed / 1 passed). The entity-collision fixture was then strengthened to retain the existing AC component registration and require both actual candidates; the initial green was vacuous because replacing that registry had invalidated the AC fixture.
- `entity-graph-selection-red-returned.xml`: selected graph source deny rule was ignored for returned evidence (1 failed / 2 corrected collision controls passed).
- `entity-graph-selection-red-population-final.xml`: actual KnowledgeService produced no natural-descendant evidence; dependent disclosure lost population completeness (2 failed / 2 source-denial controls passed). Earlier population probes incorrectly required one direct disclosure call and a satisfied research coverage result; those assumptions were corrected. The frozen test requires discovery level 0, authorization, exact source disclosure level 3, preserved answer completeness, and independently unjudged research coverage remaining partial.

The actual service population fixture uses immutable typed graph storage rows and real YAML serialization/source-pointer extraction. KnowledgeService, population enumeration, progressive authorization/disclosure, answer assessment, and kernel evidence conversion are production code. No fake answer sentinel substitutes for population behavior.

Two historical automatic-selection fixtures in `tests/knowledge/test_kernel_bridge.py` were migrated after their predicted failures were confirmed: progressive component retrieval now scripts `knowledge.operation_select/get_component_context`; automatic semantic retrieval explicitly enables embeddings and advertises semantic readiness, then chooses `find_similar_decisions` in semantic mode. Explicit hybrid compatibility remains separately tested with zero operation-selection calls. No legacy heuristic was retained solely to satisfy an obsolete fixture.

## Independent final verification

On the coder's final source freeze:

```text
AC_ENFORCE_STRICT=1
python -m pytest tests/kernel/entity_context tests/knowledge/test_kernel_bridge.py
  -q --tb=short -p no:cacheprovider
  --basetemp=reports/tmp-graph-select-independent-green
  --junitxml=reports/entity-graph-selection-independent-green.xml
```

**148 passed in 48.12 seconds; zero failures, errors or skips.** This comprises all 51 new selection cases, 84 existing entity-context cases, and 13 bridge cases. Changed tests also pass Ruff. This is controlled offline integration proof; the parent owns subsequent real index refresh and live provider verification.

## Mutation discrimination

`reports/entity-graph-selection-mutations.py` changes imported functions only inside its own Python process. Production files are never modified. Each named mutant runs through pytest with strict AC enforcement and writes a separate XML record.

| Plausible wrong implementation | Outcome |
|---|---|
| Always choose exact `get_entities` instead of the assessed relationship | Killed: actual service asserts `get_related_tests` |
| Ignore entity owner read policy | Killed: denied canonical owner reaches evidence |
| Drop the durable unsupported-population assessment | Killed in both sibling orders: research incorrectly becomes completed |
| Discard paid usage after a rejected backend result | Killed: recorded calls are zero instead of one |
| Ignore returned-source authorization | Killed: denied graph response becomes evidence |

Mutation runs may emit pytest rewrite warnings because application modules are intentionally imported before pytest; these do not mask assertions. All scratch directories created by this test-writing task are cleaned after their processes finish; XML/Markdown/probe evidence is retained.

After all five mutant processes exited, the six affected unmodified controls passed again: **6 passed in 1.64 seconds**, `entity-graph-selection-restored.xml`. No production source edits or commits were made by the test writer/evaluator.

## Follow-up after the live plain-record explanation

The parent reported that live Jev recognized `KM-400a-1` but returned an uncertain operation choice, while the relationship and ADR questions selected their intended operations. Those attempts remain preserved in the parent's live evidence.

After the narrow source freeze of `integrations/graph_offers.py` and `integrations/graph_selection.py`, the existing focused tests were rerun independently. The change distinguishes plain record explanations from relationship requests, separates the original user question from the generated research need, and exposes uncertainty measurements. Confidence thresholds remain unchanged. No tests assert specific prompt wording, and no broader suite or mutation repetition was needed for this follow-up.

```text
AC_ENFORCE_STRICT=1
python -m pytest tests/kernel/entity_context/test_knowledge_operation_selection.py
  tests/knowledge/test_kernel_bridge.py -q --tb=short -p no:cacheprovider
  --basetemp=reports/tmp-graph-select-wording-independent
  --junitxml=reports/entity-graph-selection-wording-independent.xml
```

**64 passed in 9.97 seconds; zero failures, errors or skips.** This confirms the existing offline behavior and refusal boundaries after the guidance adjustment. The parent separately reruns live selection; this controlled result does not establish live classifier accuracy.

## Parent-run live evidence

The evaluator read the saved observation files under `.leafcutter/graph-routing-eval/`; live providers and Neo4j were invoked by the parent, not by this evaluation process.

| Live case | Observed behavior and limit |
|---|---|
| Plain AC explanation, final clarified run `run-ffa97182c775462f` | Recognized `KM-400a-1`; Jev selected `get_entities` with that exact ID. Actual Neo4j discovery and source disclosure took two rounds and returned one graph evidence item (`knowledge_status=ok`). Final run completed with satisfied coverage, 6 Jev calls and no host operation. Native sibling search still reported truncation/candidate cuts. |
| Related executable checks, `run-29326dba3ea94f2b` | Jev selected `get_related_tests` for `KM-400a-1`; one graph source reached the result. Retrieval and coverage remained partial/truncated, although the best-effort run envelope completed. |
| ADR, `run-c112bbfa57944585` | Jev selected `get_entities` for exact native identity `ADR-012-retire-create-ticket-js`. Full source disclosure exceeded the available budget; zero graph items remained in the final result and the run was partial. Correct operation selection does not imply successful complete disclosure. |
| All high/critical-priority tickets, `run-e109104a298c42fa` | Jev selected `unsupported_population`; no graph evidence was claimed. The parent verified the limitation persisted after real host synthesis/resume. The best-effort root envelope completed with partial coverage and an explicit unknown; it did not establish the complete matching population. |
| Earlier AC attempts, retained | Cold run `run-752f2168d74a4e36` exhausted the entity validation deadline (parent measured 2.005 seconds) and had no recognized target. Retry `run-9b3037f0d28a4d84` recognized the AC but operation selection was uncertain, so no graph retrieval executed. Its satisfied coverage came from other evidence and is not proof of graph selection success. |

The successful plain-AC observation is `ac-clarified-observed.json`; its [live trace](https://cloud.langfuse.com/project/cmuojt32z021fad0cdji8b19j/traces/d808eec4dce499a952afa86a55345d3a) records the final attempt. Corresponding `relationship-observed.json`, `adr-observed.json`, `unsupported-observed.json`, `ac-observed.json` and `ac-retry-observed.json` preserve the other outcomes. These are mixed live results with explicit remaining limits, not an all-green live evaluation.
