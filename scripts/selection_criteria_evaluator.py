"""
MODULE: selection_criteria_evaluator.py
GOAL: Evaluate agent_registry.json selection_criteria.trigger_conditions
    against a ticket context using the two-tier DSL-first / LLM-fallback
    strategy selected in ADR-018.
BUSINESS CONTEXT: business-analyst builds the agents: map for each new ticket
    by evaluating every agent's trigger_conditions. The previous implicit
    LLM-judgment approach was non-deterministic and expensive. This module
    replaces it with a deterministic DSL evaluator for conditions that can be
    mechanically resolved, while explicitly flagging conditions that require
    LLM judgment via a ``type: llm`` discriminator. The evaluator returns True
    when any DSL condition matches; LLM-type conditions are currently stubbed
    (NotImplementedError) and will be wired in a follow-up ticket.
ARCHITECTURE: Pure Python module, zero external dependencies beyond stdlib
    (fnmatch, re). Entry point is ``evaluate(trigger_condition, ticket_context)``
    which accepts a single condition object and a ticket-context dict. The
    ``evaluate_all`` helper runs the full list and returns True when any
    condition matches. The DSL grammar (v1) supports ``contains``, ``equals``,
    and ``matches`` operators over ``files_touched``, ``title``,
    ``description``, and ``components`` fields. Grammar is defined in ADR-018.

Usage::
    from portable_dev_workflow.scripts.selection_criteria_evaluator import (
        evaluate, evaluate_all
    )
    result = evaluate({"type": "dsl", "expression": "files_touched contains *.py"}, ctx)
    result = evaluate_all(agent["selection_criteria"]["trigger_conditions"], ctx)
"""

import fnmatch
import re
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

TriggerCondition = dict[str, str]  # {"type": "dsl"|"llm", "expression": str}
TicketContext = dict[str, Any]  # {files_touched: list[str], title: str, ...}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMEvaluationRequired(NotImplementedError):
    """Raised when a trigger_condition has type 'llm' and the LLM path is not wired.

    The business-analyst caller should catch this and fall back to the
    agent's default_status for that condition.
    """


class DSLSyntaxError(ValueError):
    """Raised when a DSL expression cannot be parsed."""


# ---------------------------------------------------------------------------
# DSL parser (v1 grammar — see ADR-018)
# ---------------------------------------------------------------------------


def _parse_atom(expression: str) -> tuple[str, str, str]:
    """Parse a single field_expr atom into (field_name, operator, value).

    Supported operators: contains, equals, matches
    Supported fields: files_touched, title, description, components

    Args:
        expression: A trimmed single-atom DSL expression string, e.g.
            ``"files_touched contains *.py"`` or ``"title equals foo"``.

    Returns:
        A (field_name, operator, value) triple.

    Raises:
        DSLSyntaxError: If the expression does not match the expected form.
    """
    _VALID_FIELDS = {"files_touched", "title", "description", "components"}
    _VALID_OPS = {"contains", "equals", "matches"}

    # Greedy split on first two whitespace-separated tokens
    parts = expression.strip().split(None, 2)
    if len(parts) != 3:
        raise DSLSyntaxError(
            f"DSL atom must have form '<field> <op> <value>', got: {expression!r}"
        )
    field, op, value = parts
    if field not in _VALID_FIELDS:
        raise DSLSyntaxError(
            f"Unknown field {field!r}. Valid fields: {', '.join(sorted(_VALID_FIELDS))}"
        )
    if op not in _VALID_OPS:
        raise DSLSyntaxError(
            f"Unknown operator {op!r}. Valid operators: {', '.join(sorted(_VALID_OPS))}"
        )
    return field, op, value


def _file_path_matches(file_path: str, value: str) -> bool:
    """Test a single file path against a DSL contains value.

    Uses fnmatch for glob matching. Additionally, when the value ends with
    ``"/"`` (a directory-prefix pattern), accepts any path that starts with
    the prefix — e.g. ``"sql_functions/"`` matches
    ``"sql_functions/procedures/update_htf.sql"``.

    Args:
        file_path: A single path from the ``files_touched`` list.
        value: The DSL expression value (glob pattern or directory prefix).

    Returns:
        True when the path matches.
    """
    if fnmatch.fnmatch(file_path, value):
        return True
    return bool(value.endswith("/") and file_path.startswith(value))


def _evaluate_files_touched(op: str, value: str, raw: object) -> bool:
    """Evaluate a DSL atom whose field is ``files_touched``.

    Args:
        op: The operator: ``contains``, ``equals``, or ``matches``.
        value: The comparison value or glob pattern.
        raw: The raw value from the ticket context (expected list[str]).

    Returns:
        True when any path in the list satisfies the operator.
    """
    files: list[str] = raw if isinstance(raw, list) else []
    if op == "contains":
        return any(_file_path_matches(f, value) for f in files)
    if op == "equals":
        return any(f == value for f in files)
    # matches
    pattern = re.compile(value)
    return any(pattern.search(f) is not None for f in files)


def _evaluate_list_field(op: str, value: str, raw: object) -> bool:
    """Evaluate a DSL atom whose field is a lowercase-normalised list (``components``).

    Args:
        op: The operator: ``contains``, ``equals``, or ``matches``.
        value: The comparison value.
        raw: The raw value from the ticket context (expected list[str]).

    Returns:
        True when the list satisfies the operator against the value.
    """
    items: list[str] = [c.lower() for c in (raw if isinstance(raw, list) else [])]
    if op in ("contains", "equals"):
        return value.lower() in items
    # matches
    pattern = re.compile(value, re.IGNORECASE)
    return any(pattern.search(c) is not None for c in items)


def _evaluate_string_field(op: str, value: str, raw: object) -> bool:
    """Evaluate a DSL atom whose field is a scalar string (``title``, ``description``).

    Args:
        op: The operator: ``contains``, ``equals``, or ``matches``.
        value: The comparison value or pattern.
        raw: The raw value from the ticket context (expected str or None).

    Returns:
        True when the string field satisfies the operator against the value.
    """
    text: str = str(raw) if raw is not None else ""
    if op == "contains":
        return value.lower() in text.lower()
    if op == "equals":
        return text.lower() == value.lower()
    # matches
    return re.search(value, text, re.IGNORECASE) is not None


def _evaluate_atom(field: str, op: str, value: str, ctx: TicketContext) -> bool:
    """Dispatch a parsed DSL atom to the correct per-field evaluator.

    Args:
        field: Field name (files_touched, title, description, components).
        op: Operator (contains, equals, matches).
        value: The comparison value or pattern.
        ctx: Ticket context dict with keys matching the supported fields.

    Returns:
        True when the atom matches; False otherwise.
    """
    raw = ctx.get(field)
    if field == "files_touched":
        return _evaluate_files_touched(op, value, raw)
    if field == "components":
        return _evaluate_list_field(op, value, raw)
    return _evaluate_string_field(op, value, raw)


def _evaluate_dsl(expression: str, ctx: TicketContext) -> bool:
    """Evaluate a full DSL expression string against the ticket context.

    Supports AND / OR combinators at the top level. Operator precedence:
    AND binds tighter than OR (standard logic). Atoms are evaluated by
    _evaluate_atom.

    Args:
        expression: A DSL expression string (may contain AND/OR).
        ctx: Ticket context dict.

    Returns:
        True when the expression evaluates to True; False otherwise.

    Raises:
        DSLSyntaxError: If any atom cannot be parsed.
    """
    # Split on OR first (lowest precedence)
    or_clauses = re.split(r"\bOR\b", expression)
    for or_clause in or_clauses:
        # Each OR-clause is an AND of atoms
        and_atoms = re.split(r"\bAND\b", or_clause)
        clause_result = True
        for atom_str in and_atoms:
            atom_str = atom_str.strip()
            if not atom_str:
                continue
            field, op, value = _parse_atom(atom_str)
            if not _evaluate_atom(field, op, value, ctx):
                clause_result = False
                break
        if clause_result:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate(trigger_condition: TriggerCondition, ticket_context: TicketContext) -> bool:
    """Evaluate a single trigger_condition against a ticket context.

    For type ``"dsl"``, evaluates the expression deterministically via the
    DSL parser. For type ``"llm"``, raises ``LLMEvaluationRequired`` — the
    caller should catch this and fall back to the agent's ``default_status``.

    Args:
        trigger_condition: A condition dict from agent_registry.json with keys
            ``type`` (``"dsl"`` or ``"llm"``) and ``expression`` (str).
        ticket_context: A dict with ticket fields available for matching. Keys
            used by the DSL evaluator: ``files_touched`` (list[str]),
            ``title`` (str), ``description`` (str), ``components`` (list[str]).

    Returns:
        True when the condition matches, False when it does not.

    Raises:
        LLMEvaluationRequired: When ``type`` is ``"llm"`` (not yet wired).
        DSLSyntaxError: When ``type`` is ``"dsl"`` but the expression is
            syntactically invalid.
        ValueError: When ``type`` is absent or not a recognised value.
    """
    condition_type = trigger_condition.get("type")
    expression = trigger_condition.get("expression", "")

    if condition_type == "dsl":
        return _evaluate_dsl(expression, ticket_context)

    if condition_type == "llm":
        raise LLMEvaluationRequired(
            f"LLM evaluation not yet wired. Condition: {expression!r}. "
            "Caller should fall back to agent default_status."
        )

    raise ValueError(
        f"trigger_condition must have type 'dsl' or 'llm'; got {condition_type!r}. "
        f"Full condition: {trigger_condition!r}"
    )


def evaluate_all(
    trigger_conditions: list[TriggerCondition],
    ticket_context: TicketContext,
    llm_fallback: bool = False,
) -> bool:
    """Evaluate a list of trigger_conditions and return True when any matches.

    DSL conditions are evaluated deterministically. LLM conditions are skipped
    (returning False for that condition) unless ``llm_fallback=True``, in which
    case they raise ``LLMEvaluationRequired`` for the caller to handle.

    Args:
        trigger_conditions: List of condition dicts from agent_registry.json.
        ticket_context: Ticket fields dict (see ``evaluate``).
        llm_fallback: When False (default), LLM-type conditions are skipped
            and do not contribute to the result. When True, they propagate
            ``LLMEvaluationRequired`` so the caller can invoke the LLM path.

    Returns:
        True when any matching condition is found; False when none match.

    Raises:
        LLMEvaluationRequired: Only when ``llm_fallback=True`` and an
            ``llm``-type condition is encountered.
        DSLSyntaxError: When a ``dsl``-type condition has invalid syntax.
    """
    for condition in trigger_conditions:
        condition_type = condition.get("type")
        if condition_type == "llm":
            if llm_fallback:
                raise LLMEvaluationRequired(
                    f"LLM condition encountered: {condition.get('expression', '')!r}"
                )
            # Skip silently when llm_fallback is False
            continue
        if evaluate(condition, ticket_context):
            return True
    return False


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-13 12:45 [Agent/python-coder]: Created for EPIC-PortableWorkflowHardening (#EPIC-LeafcutterMVP/01)
  ticket 02, implementing the two-tier evaluation strategy from ADR-018.
  DSL grammar v1 supports contains/equals/matches over files_touched, title,
  description, and components. AND/OR combinators supported at expression level.
  LLM-type conditions raise LLMEvaluationRequired (stub); actual LLM wiring
  deferred to a follow-up ticket. evaluate_all() is the primary entry point
  for business-analyst.
====================================================================
"""
