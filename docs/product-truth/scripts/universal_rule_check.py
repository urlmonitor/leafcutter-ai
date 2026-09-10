"""
MODULE: universal_rule_check
GOAL: Provide a generic checker for rules phrased as "every record of some kind must
    satisfy a predicate," returning a verdict that distinguishes "not exercised" (zero
    records) from a real "holds" or "violated" outcome over a populated set.
BUSINESS CONTEXT: UXP-700b establishes that a universal-rule check ("every X must
    satisfy P") is vacuously true over an empty set, and that a trustworthy check must
    report that it examined nothing rather than silently pass. UXP-700b-3-i pins the
    other half of that contract: a population of exactly one record must yield a real,
    populated verdict (holds or violated) — never a fallback to not_exercised — so the
    not-exercised outcome cannot be used to mask either a real pass or a real failure.
ARCHITECTURE: A small, dependency-free module in docs/product-truth/scripts, callable
    both as a library (check_universal_rule) and as a standalone CLI
    (`python universal_rule_check.py --records <file.json> --rule <name> --kind <name>`)
    whose exit code (0 for holds/not_exercised, 1 for violated) makes the verdict
    consumable in control flow, not just in printed output. It has no consumer yet — the
    wiring into validate_product_truth.py's D1-D4 checks belongs to a later ticket.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("universal_rule_check")

#: Canned predicates selectable via the CLI's --rule flag. Each takes a record dict and
#: returns True when the record satisfies the rule.
_CLI_RULES: dict[str, Callable[[dict], bool]] = {
    "positive": lambda record: record.get("value", 0) > 0,
}


@dataclass(frozen=True)
class RuleCheckResult:
    """The verdict of running a universal rule over a population of records.

    outcome is one of "not_exercised" (zero records — the rule was never exercised),
    "holds" (one or more records, all satisfy the predicate), or "violated" (one or
    more records, at least one fails the predicate).
    """

    outcome: str
    examined: int
    kind: str
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of this result."""
        return {
            "outcome": self.outcome,
            "examined": self.examined,
            "kind": self.kind,
            "violations": self.violations,
        }


def check_universal_rule(
    records: list[dict],
    predicate: Callable[[dict], bool],
    kind: str,
    name_of: Callable[[dict], str] | None = None,
) -> RuleCheckResult:
    """Check that every record in `records` satisfies `predicate`.

    Returns a RuleCheckResult whose outcome is "not_exercised" when `records` is empty,
    "holds" when every record satisfies `predicate`, or "violated" when at least one
    record fails it. `name_of` extracts a display name for a violating record (defaults
    to its "id" field, falling back to str(record) when absent).
    """
    if not records:
        return RuleCheckResult(outcome="not_exercised", examined=0, kind=kind)

    resolve_name = name_of or (lambda record: str(record.get("id", record)))
    violations = [resolve_name(record) for record in records if not predicate(record)]

    outcome = "violated" if violations else "holds"
    return RuleCheckResult(
        outcome=outcome,
        examined=len(records),
        kind=kind,
        violations=violations,
    )


def _load_records(path: str) -> list[dict]:
    """Read a JSON list of record objects from `path`."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except OSError:
        logger.exception("cannot read %s", path)
        raise
    except json.JSONDecodeError:
        logger.exception("invalid JSON in %s", path)
        raise


class UnknownRuleError(SystemExit):
    """Raised when --rule names a predicate that is not registered in _CLI_RULES."""


def _resolve_rule(rule_name: str) -> Callable[[dict], bool]:
    """Resolve a --rule CLI argument to its predicate, raising on an unknown name."""
    try:
        return _CLI_RULES[rule_name]
    except KeyError as exc:
        raise UnknownRuleError(_unknown_rule_message(rule_name)) from exc


def _unknown_rule_message(rule_name: str) -> str:
    """Build the error text for an unrecognized --rule value."""
    known = ", ".join(sorted(_CLI_RULES))
    return f"unknown --rule {rule_name!r}; known rules: {known}"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: check a JSON records file against a named rule and print the
    verdict as JSON. Exits 0 for "holds"/"not_exercised", 1 for "violated"."""
    parser = argparse.ArgumentParser(
        description="Check that every record of a kind satisfies a universal rule."
    )
    parser.add_argument("--records", required=True, help="Path to a JSON list of record objects.")
    parser.add_argument("--rule", required=True, help="Name of the canned rule predicate to apply.")
    parser.add_argument("--kind", required=True, help="The kind of record being checked (for reporting).")
    args = parser.parse_args(argv)

    predicate = _resolve_rule(args.rule)
    records = _load_records(args.records)
    result = check_universal_rule(records, predicate=predicate, kind=args.kind)

    print(json.dumps(result.to_dict()))
    return 1 if result.outcome == "violated" else 0


if __name__ == "__main__":
    sys.exit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-09-09 16:05 [python-coder]: Created universal_rule_check module and CLI to
#   pin the population-of-one boundary for the every-record rule checker. (#EPIC-TruthfulProjectRecord/17)
# - 2026-09-10 09:00 [commit]: Wrapped _load_records' open()/json.load() in a
#   try/except (OSError, json.JSONDecodeError) with logger.exception + re-raise,
#   matching the established _load_json pattern in apply_flow_backlinks.py and
#   generate_product_truth.py, to satisfy the check-exception-handling I/O
#   boundary guard (IO-001). (#TICKETLESS reason=precommit-hook-mechanical-fix)
