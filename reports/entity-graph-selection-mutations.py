"""In-process plausible-defect probes; never edit production source files."""

import os
from pathlib import Path
import sys
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["AC_ENFORCE_STRICT"] = "1"

import pytest
import integrations.knowledge_execution as execution
import integrations.graph_offers as offers

mutant = sys.argv[1]
test_file = "tests/kernel/entity_context/test_knowledge_operation_selection.py"
if mutant == "first_operation":
    original = execution.assess_graph_operation

    async def select_first(*args, **kwargs):
        choice, usage = await original(*args, **kwargs)
        if choice.retrieve:
            choice = replace(choice, operation="get_entities", mode="exact",
                             arguments={"entity_ids": ["EC-1100a-1-i"]})
        return choice, usage

    execution.assess_graph_operation = select_first
    selected = "test_entity_question_selects_bound_graph_operation_and_yields_evidence[relationship-paraphrase]"
elif mutant == "ignore_owner_policy":
    offers._permitted = lambda ctx, card: True
    selected = "test_scope_revision_source_policy_rechecked_before_execution[owner_glob_denied]"
elif mutant == "erase_population_guard":
    original = execution.selection_result

    async def unguarded(ctx, invocation, payload, choice, usage, *args, **kwargs):
        if choice.operation == "unsupported_population":
            choice = replace(choice, operation="unsupported")
        return await original(ctx, invocation, payload, choice, usage, *args, **kwargs)

    execution.selection_result = unguarded
    selected = "test_ticket_completeness_limitation_survives_sibling_merge_and_resume"
elif mutant == "discard_paid_failure":
    original = execution._kernel_result

    def drop_usage(*args, **kwargs):
        result = original(*args, **kwargs)
        return result.model_copy(update={"usage": []}) if result.status.value == "failed" else result

    execution._kernel_result = drop_usage
    selected = "test_selector_usage_is_preserved_on_execution_failure[foreign_result]"
elif mutant == "ignore_returned_scope":
    execution._authorized = lambda *args, **kwargs: True
    selected = "test_scope_revision_source_policy_rechecked_before_execution[graph_response_denied]"
else:
    raise SystemExit("Unknown mutation probe")

raise SystemExit(pytest.main([
    test_file + "::" + selected, "-q", "--tb=short", "-p", "no:cacheprovider",
    "--basetemp=reports/tmp-graph-select-mutant-" + mutant,
    "--junitxml=reports/entity-graph-selection-mutant-" + mutant + ".xml",
]))
