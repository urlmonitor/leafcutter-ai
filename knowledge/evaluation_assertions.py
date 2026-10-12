"""Safe expected-versus-actual comparisons for reviewed research cases.
MODULE: knowledge.evaluation_assertions
GOAL: Grade serialized actual values without executing oracle code.
BUSINESS CONTEXT: Expected source facts must never repair a deficient tool response.
ARCHITECTURE: Pure dotted-path predicates over JSON data.
"""

from __future__ import annotations

_MISSING = object()


def resolve(actual: object, path: str) -> object:
    """Read a bounded dotted dictionary/list path without reflection or execution.

    Args:
        actual: Actual serialized response.
        path: Dot-separated JSON dictionary keys or list indices.

    Returns:
        Value at the path, or an internal missing sentinel.
    """
    value = actual
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part, _MISSING)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def judge(actual: dict, assertion: dict) -> dict:
    """Evaluate one explicit reviewed predicate; malformed predicates fail closed.

    Args:
        actual: Actual serialized response, never modified.
        assertion: Reviewed expected predicate.

    Returns:
        Verdict, expected predicate and the actual observed value.
    """
    path = assertion.get("path")
    operators = set(assertion) & {"equals", "contains", "set_equals", "absent"}
    if not isinstance(path, str) or not path or len(operators) != 1:
        return {"expected": assertion, "passed": False, "reason": "invalid assertion"}
    operator = next(iter(operators))
    value = resolve(actual, path)
    passed = _matches(value, operator, assertion[operator])
    return {
        "expected": assertion,
        "passed": passed,
        "actual": None if value is _MISSING else value,
        "present": value is not _MISSING,
    }


def _matches(value: object, operator: str, expected: object) -> bool:
    """Apply the small declared predicate vocabulary with strict absent semantics.

    Args:
        value: Actual value or missing sentinel.
        operator: Validated comparison operator.
        expected: Independently reviewed expected value.

    Returns:
        Whether the actual value satisfies the declared comparison.
    """
    if operator == "absent":
        return (value is _MISSING) == expected
    if value is _MISSING:
        return False
    if operator == "equals":
        return value == expected
    if operator == "contains":
        return isinstance(value, (list, dict, str)) and expected in value
    if not isinstance(value, list) or not isinstance(expected, list):
        return False
    return (
        len(value) == len(expected)
        and all(item in expected for item in value)
        and all(item in value for item in expected)
    )


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Keep source-oracle predicates outside actual retrieval. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500d-3)
