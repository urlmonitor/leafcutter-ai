"""
MODULE: test_selection_criteria_evaluator.py
GOAL: Unit tests for selection_criteria_evaluator.py — the two-tier DSL-first
    evaluation engine for agent_registry.json trigger_conditions.
BUSINESS CONTEXT: The evaluator is the engine that business-analyst uses to
    decide which agents to assign to a new ticket. These tests verify that DSL
    glob matching, contains/equals/matches operators, AND/OR combinators, the
    LLM-type stub, and the schema-validation path all behave correctly. A
    regression in any of these would silently mis-assign agents at ticket
    creation time.
ARCHITECTURE: Tests exercise the public API (evaluate, evaluate_all) and the
    DSL internals (_parse_atom, _evaluate_atom, _evaluate_dsl) directly.
    No LLM calls or external dependencies. All inputs are inline dicts.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import shim: leafcutter uses a hyphenated directory name which
# Python cannot import directly. We load the module from its absolute path.
# ---------------------------------------------------------------------------
_EVALUATOR_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "selection_criteria_evaluator.py"
)
_spec = importlib.util.spec_from_file_location(
    "selection_criteria_evaluator", _EVALUATOR_PATH
)
_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_module)  # type: ignore[union-attr]
sys.modules["selection_criteria_evaluator"] = _module

DSLSyntaxError = _module.DSLSyntaxError
LLMEvaluationRequired = _module.LLMEvaluationRequired
_evaluate_dsl = _module._evaluate_dsl
_parse_atom = _module._parse_atom
evaluate = _module.evaluate
evaluate_all = _module.evaluate_all

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CTX_PY = {
    "files_touched": ["live_trader/foo.py", "unit_tests/test_foo.py"],
    "title": "Add foo module",
    "description": "Implements the foo module for live_trader.",
    "components": ["live_trader", "infrastructure"],
}

_CTX_SQL = {
    "files_touched": ["sql_functions/procedures/update_htf.sql"],
    "title": "Add HTF update procedure",
    "description": "Creates a new SQL procedure.",
    "components": ["database"],
}

_CTX_EMPTY = {
    "files_touched": [],
    "title": "",
    "description": "",
    "components": [],
}


# ---------------------------------------------------------------------------
# DSL parser tests
# ---------------------------------------------------------------------------


class TestParseAtom(unittest.TestCase):
    """_parse_atom splits a DSL atom into (field, op, value)."""

    def test_files_touched_contains(self) -> None:
        """files_touched contains *.py -> (files_touched, contains, *.py)."""
        field, op, value = _parse_atom("files_touched contains *.py")
        self.assertEqual(field, "files_touched")
        self.assertEqual(op, "contains")
        self.assertEqual(value, "*.py")

    def test_title_equals(self) -> None:
        """title equals foo -> (title, equals, foo)."""
        field, op, value = _parse_atom("title equals foo")
        self.assertEqual(field, "title")
        self.assertEqual(op, "equals")
        self.assertEqual(value, "foo")

    def test_description_matches(self) -> None:
        """description matches ^foo -> (description, matches, ^foo)."""
        field, op, value = _parse_atom("description matches ^foo")
        self.assertEqual(field, "description")
        self.assertEqual(op, "matches")
        self.assertEqual(value, "^foo")

    def test_invalid_field_raises(self) -> None:
        """Unknown field raises DSLSyntaxError."""
        with self.assertRaises(DSLSyntaxError):
            _parse_atom("unknown_field contains foo")

    def test_invalid_operator_raises(self) -> None:
        """Unknown operator raises DSLSyntaxError."""
        with self.assertRaises(DSLSyntaxError):
            _parse_atom("title like foo")

    def test_too_few_parts_raises(self) -> None:
        """Too few whitespace tokens raise DSLSyntaxError."""
        with self.assertRaises(DSLSyntaxError):
            _parse_atom("files_touched")


# ---------------------------------------------------------------------------
# DSL evaluation — single atom
# ---------------------------------------------------------------------------


class TestEvaluateDSLAtom(unittest.TestCase):
    """Single-atom DSL expressions against various contexts."""

    def test_files_touched_glob_match(self) -> None:
        """files_touched contains *.py matches a .py file."""
        self.assertTrue(_evaluate_dsl("files_touched contains *.py", _CTX_PY))

    def test_files_touched_glob_no_match(self) -> None:
        """files_touched contains *.sql does not match a .py-only context."""
        self.assertFalse(_evaluate_dsl("files_touched contains *.sql", _CTX_PY))

    def test_files_touched_prefix_glob(self) -> None:
        """files_touched contains sql_functions/ matches an sql_functions path."""
        self.assertTrue(_evaluate_dsl("files_touched contains sql_functions/*", _CTX_SQL))

    def test_files_touched_empty_context_false(self) -> None:
        """files_touched contains *.py returns False when files_touched is empty."""
        self.assertFalse(_evaluate_dsl("files_touched contains *.py", _CTX_EMPTY))

    def test_files_touched_directory_prefix_match(self) -> None:
        """files_touched contains sql_functions/ matches paths starting with that prefix."""
        ctx = {"files_touched": ["sql_functions/procedures/update_htf.sql"]}
        self.assertTrue(_evaluate_dsl("files_touched contains sql_functions/", ctx))

    def test_files_touched_directory_prefix_no_match(self) -> None:
        """files_touched contains sql_functions/ does not match alembic paths."""
        ctx = {"files_touched": ["alembic/versions/abc.py"]}
        self.assertFalse(_evaluate_dsl("files_touched contains sql_functions/", ctx))

    def test_title_contains_substring(self) -> None:
        """title contains foo matches a title containing 'foo'."""
        self.assertTrue(_evaluate_dsl("title contains foo", _CTX_PY))

    def test_title_contains_case_insensitive(self) -> None:
        """title contains FOO matches case-insensitively."""
        self.assertTrue(_evaluate_dsl("title contains FOO", _CTX_PY))

    def test_title_equals_exact(self) -> None:
        """title equals 'add foo module' matches case-insensitively."""
        self.assertTrue(_evaluate_dsl("title equals Add foo module", _CTX_PY))

    def test_description_matches_regex(self) -> None:
        """description matches 'foo.*module' matches with re.search."""
        self.assertTrue(_evaluate_dsl("description matches foo.*module", _CTX_PY))

    def test_description_matches_no_match(self) -> None:
        """description matches xyz returns False when pattern is absent."""
        self.assertFalse(_evaluate_dsl("description matches xyz", _CTX_PY))

    def test_components_contains(self) -> None:
        """components contains live_trader matches."""
        self.assertTrue(_evaluate_dsl("components contains live_trader", _CTX_PY))

    def test_components_contains_case_insensitive(self) -> None:
        """components contains LIVE_TRADER matches case-insensitively."""
        self.assertTrue(_evaluate_dsl("components contains LIVE_TRADER", _CTX_PY))

    def test_components_not_present_false(self) -> None:
        """components contains database returns False for a non-database context."""
        self.assertFalse(_evaluate_dsl("components contains database", _CTX_PY))


# ---------------------------------------------------------------------------
# DSL evaluation — AND / OR combinators
# ---------------------------------------------------------------------------


class TestEvaluateDSLCombinators(unittest.TestCase):
    """AND and OR combinator evaluation."""

    def test_or_first_matches(self) -> None:
        """A OR B returns True when the first clause matches."""
        expr = "files_touched contains *.py OR files_touched contains *.sql"
        self.assertTrue(_evaluate_dsl(expr, _CTX_PY))

    def test_or_second_matches(self) -> None:
        """A OR B returns True when the second clause matches."""
        expr = "files_touched contains *.sql OR files_touched contains *.py"
        self.assertTrue(_evaluate_dsl(expr, _CTX_PY))

    def test_or_neither_matches(self) -> None:
        """A OR B returns False when neither clause matches."""
        expr = "files_touched contains *.sql OR files_touched contains *.go"
        self.assertFalse(_evaluate_dsl(expr, _CTX_PY))

    def test_and_both_match(self) -> None:
        """A AND B returns True when both conditions match."""
        expr = "files_touched contains *.py AND components contains live_trader"
        self.assertTrue(_evaluate_dsl(expr, _CTX_PY))

    def test_and_one_fails(self) -> None:
        """A AND B returns False when one condition does not match."""
        expr = "files_touched contains *.py AND components contains database"
        self.assertFalse(_evaluate_dsl(expr, _CTX_PY))

    def test_and_binds_tighter_than_or(self) -> None:
        """A AND B OR C evaluates as (A AND B) OR C."""
        # (*.sql AND *.py) OR *.py
        # (False AND True) OR True -> True
        expr = "files_touched contains *.sql AND files_touched contains *.py OR files_touched contains *.py"
        self.assertTrue(_evaluate_dsl(expr, _CTX_PY))


# ---------------------------------------------------------------------------
# Public evaluate() API
# ---------------------------------------------------------------------------


class TestEvaluateFunction(unittest.TestCase):
    """Tests for the public evaluate() API."""

    def test_dsl_type_matches(self) -> None:
        """A dsl-type condition with matching expression returns True."""
        cond = {"type": "dsl", "expression": "files_touched contains *.py"}
        self.assertTrue(evaluate(cond, _CTX_PY))

    def test_dsl_type_no_match(self) -> None:
        """A dsl-type condition with non-matching expression returns False."""
        cond = {"type": "dsl", "expression": "files_touched contains *.sql"}
        self.assertFalse(evaluate(cond, _CTX_PY))

    def test_llm_type_raises(self) -> None:
        """A llm-type condition raises LLMEvaluationRequired."""
        cond = {"type": "llm", "expression": "ticket involves Python code"}
        with self.assertRaises(LLMEvaluationRequired):
            evaluate(cond, _CTX_PY)

    def test_unknown_type_raises(self) -> None:
        """An unrecognised type raises ValueError."""
        cond = {"type": "magic", "expression": "files_touched contains *.py"}
        with self.assertRaises(ValueError):
            evaluate(cond, _CTX_PY)

    def test_missing_type_raises(self) -> None:
        """A condition missing the type key raises ValueError."""
        cond = {"expression": "files_touched contains *.py"}
        with self.assertRaises(ValueError):
            evaluate(cond, _CTX_PY)


# ---------------------------------------------------------------------------
# evaluate_all() API
# ---------------------------------------------------------------------------


class TestEvaluateAllFunction(unittest.TestCase):
    """Tests for the public evaluate_all() API."""

    def test_any_dsl_match_returns_true(self) -> None:
        """Returns True when at least one DSL condition matches."""
        conditions = [
            {"type": "dsl", "expression": "files_touched contains *.sql"},
            {"type": "dsl", "expression": "files_touched contains *.py"},
        ]
        self.assertTrue(evaluate_all(conditions, _CTX_PY))

    def test_all_dsl_no_match_returns_false(self) -> None:
        """Returns False when no DSL condition matches."""
        conditions = [
            {"type": "dsl", "expression": "files_touched contains *.sql"},
            {"type": "dsl", "expression": "files_touched contains *.go"},
        ]
        self.assertFalse(evaluate_all(conditions, _CTX_PY))

    def test_llm_skipped_by_default(self) -> None:
        """LLM-type conditions are skipped (return False) when llm_fallback=False."""
        conditions = [
            {"type": "llm", "expression": "ticket involves Python code"},
        ]
        # Should not raise, should return False
        result = evaluate_all(conditions, _CTX_PY, llm_fallback=False)
        self.assertFalse(result)

    def test_llm_raises_when_fallback_enabled(self) -> None:
        """LLM-type condition raises LLMEvaluationRequired when llm_fallback=True."""
        conditions = [
            {"type": "llm", "expression": "ticket involves Python code"},
        ]
        with self.assertRaises(LLMEvaluationRequired):
            evaluate_all(conditions, _CTX_PY, llm_fallback=True)

    def test_dsl_match_before_llm_returns_true_without_raising(self) -> None:
        """True is returned from the first DSL match without reaching the LLM condition."""
        conditions = [
            {"type": "dsl", "expression": "files_touched contains *.py"},
            {"type": "llm", "expression": "ticket involves Python code"},
        ]
        # llm_fallback=True but DSL already matched — should not raise
        result = evaluate_all(conditions, _CTX_PY, llm_fallback=True)
        self.assertTrue(result)

    def test_empty_conditions_returns_false(self) -> None:
        """An empty condition list returns False."""
        self.assertFalse(evaluate_all([], _CTX_PY))


# ---------------------------------------------------------------------------
# Schema validation — agent_registry.json conforms to the updated schema
# ---------------------------------------------------------------------------


class TestAgentRegistrySchemaConformance(unittest.TestCase):
    """Validate that the updated agent_registry.json conforms to the new schema."""

    def _get_registry_path(self) -> Path:
        """Return the absolute path to the registry file in the worktree."""
        # Walk up from this file to find the repo root
        this_file = Path(__file__).resolve()
        # tests/test_...py -> repo root is 2 levels up
        root = this_file.parent.parent
        return root / "config" / "agent_registry.json"

    def test_registry_loads_as_valid_json(self) -> None:
        """agent_registry.json must be parseable as JSON."""
        path = self._get_registry_path()
        if not path.exists():
            self.skipTest(f"agent_registry.json not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("agents", data)

    def test_all_trigger_conditions_have_type_and_expression(self) -> None:
        """Every trigger_condition in agent_registry.json must have type and expression."""
        path = self._get_registry_path()
        if not path.exists():
            self.skipTest(f"agent_registry.json not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        for agent in data["agents"]:
            sc = agent.get("selection_criteria")
            if sc is None:
                continue
            for i, cond in enumerate(sc.get("trigger_conditions", [])):
                agent_id = agent["id"]
                self.assertIsInstance(
                    cond, dict,
                    f"agent '{agent_id}' trigger_condition[{i}] must be a dict, got {type(cond).__name__}"
                )
                self.assertIn(
                    "type", cond,
                    f"agent '{agent_id}' trigger_condition[{i}] missing 'type'"
                )
                self.assertIn(
                    "expression", cond,
                    f"agent '{agent_id}' trigger_condition[{i}] missing 'expression'"
                )
                self.assertIn(
                    cond["type"], ("dsl", "llm"),
                    f"agent '{agent_id}' trigger_condition[{i}] type must be 'dsl' or 'llm'"
                )

    def test_all_dsl_conditions_parse_without_error(self) -> None:
        """All dsl-type trigger_conditions in agent_registry.json must parse cleanly."""
        path = self._get_registry_path()
        if not path.exists():
            self.skipTest(f"agent_registry.json not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        for agent in data["agents"]:
            sc = agent.get("selection_criteria")
            if sc is None:
                continue
            for i, cond in enumerate(sc.get("trigger_conditions", [])):
                if not isinstance(cond, dict) or cond.get("type") != "dsl":
                    continue
                expr = cond.get("expression", "")
                agent_id = agent["id"]
                try:
                    # Attempt to evaluate against an empty context (result doesn't matter)
                    _evaluate_dsl(expr, _CTX_EMPTY)
                except DSLSyntaxError as exc:
                    self.fail(
                        f"agent '{agent_id}' trigger_condition[{i}] DSL parse error: {exc}"
                    )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-13 [Agent/python-coder]: Created for EPIC-PortableWorkflowHardening
  ticket 02. Covers all acceptance criteria: DSL glob match, DSL glob no-match,
  AND/OR combinators, LLM-path stub raise, schema validation pass/fail. The
  schema conformance tests read the actual agent_registry.json to verify every
  trigger_condition uses the new {type, expression} format and every dsl-type
  condition parses without error.
====================================================================
"""
