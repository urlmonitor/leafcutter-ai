"""
MODULE: agent_declaration_shape
GOAL: Say, for one agent's frontmatter ``skills`` or ``spawn_allowlist`` value,
    whether it is well-formed -- and when it is not, name the offending value --
    so that no malformed entry is ever silently dropped.
BUSINESS CONTEXT: AR-300c-1 / AR-300c-5 ("none omitted"). A declaration whose
    entry was ignored (a ``skill:`` key where ``skill_id:`` belongs, a mode
    typo, a sub-agent written as a mapping) compiles an agent that holds LESS
    than its header says, with the build green. Every reader of a declaration
    therefore either receives well-formed entries or is told exactly which
    value is wrong; the build gate turns that into a refusal naming the agent.
ARCHITECTURE: Pure functions, no I/O. ``skills_problems`` / ``spawn_problems``
    return one message per defect (an empty list means well-formed; an absent
    value is well-formed). ``MalformedDeclarationError`` (a ``ValueError``)
    carries the messages for callers that cannot continue past a defect
    (``normalize_entries``, ``declared_spawn``). Build-engine module under
    ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300-review]: Created. Replaces the silent
  ``continue`` / ``isinstance`` filters in the declaration readers. (#AR-300c-1, #AR-300c-5)
- 2026-10-16 [python-coder/AR-400d-3]: A ``skills`` entry may carry ``provided_by``; the only accepted
  value is ``project`` and any other is a defect naming the entry and the value (the commit hook's
  ``_agent_ability_sync._skill_problem`` carries the same rule). (#AR-400d-3)
"""

from __future__ import annotations

from typing import Any

VALID_MODES = ("always", "conditional")
PROVIDED_BY_PROJECT = "project"  # the only accepted ``provided_by`` value (AR-400d-3)


class MalformedDeclarationError(ValueError):
    """A declaration value is not well-formed; the message names every offending value."""

    def __init__(self, field: str, problems: list[str]) -> None:
        """Join ``problems`` into one message prefixed with the declaring ``field``."""
        self.field = field
        self.problems = list(problems)
        super().__init__(f"malformed {field} declaration: " + "; ".join(problems))


def _skill_entry_problem(item: Any) -> str | None:
    """Return what is wrong with one ``skills`` entry, or None when it is well-formed."""
    if isinstance(item, str):
        return None
    if not isinstance(item, dict):
        return f"entry {item!r} is neither a skill id string nor a mapping"
    if not isinstance(item.get("skill_id"), str):
        return f"entry {item!r} has no string 'skill_id'"
    mode = item.get("mode")
    if mode is not None and mode not in VALID_MODES:
        return f"entry {item!r} has mode {mode!r} (expected one of: {', '.join(VALID_MODES)})"
    supplier = item.get("provided_by")
    if supplier is not None and supplier != PROVIDED_BY_PROJECT:
        return f"entry {item!r} has provided_by {supplier!r} (expected {PROVIDED_BY_PROJECT})"
    return None


def skills_problems(raw: Any) -> list[str]:
    """Return one message per defect in a ``skills`` value (``[]`` when absent or well-formed)."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [f"skills must be a list of entries, got {type(raw).__name__} {raw!r}"]
    return [p for p in (_skill_entry_problem(item) for item in raw) if p]


def spawn_problems(raw: Any) -> list[str]:
    """Return one message per defect in a ``spawn_allowlist`` value (``[]`` when absent or well-formed)."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [f"spawn_allowlist must be a list of agent ids, got {type(raw).__name__} {raw!r}"]
    return [f"entry {item!r} is not an agent id string" for item in raw if not isinstance(item, str)]


def require_well_formed(field: str, problems: list[str]) -> None:
    """Raise ``MalformedDeclarationError`` for ``field`` when ``problems`` is non-empty."""
    if problems:
        raise MalformedDeclarationError(field, problems)
