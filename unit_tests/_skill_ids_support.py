"""Grant-list readers shared by tests: skill ids from bare strings or {skill_id, mode[, condition]} dicts."""

from __future__ import annotations

from typing import Any


def skill_ids(entries: Any) -> set[str]:
    return {e["skill_id"] if isinstance(e, dict) else e for e in (entries or [])}


def assert_grants_agree(entry: dict, fm: dict, expected: set[str]) -> None:
    """The derived registry copy (``skills_invoked``) and the template frontmatter
    (``skills``, the source of truth) must both grant exactly ``expected``."""
    assert skill_ids(entry.get("skills_invoked")) == expected
    assert skill_ids(fm.get("skills")) == expected
