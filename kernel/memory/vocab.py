"""
MODULE: kernel.memory.vocab
GOAL: Load the existing vocabularies a record's filters must be drawn from: component ids
    (docs/components.json), the `change_target` and `risk_surface` enums (config/ac_store_schema.json),
    roadmap phase ids (docs/roadmap.json) and the file-type globs of the rule files
    (templates/rules/*.md front matter).
BUSINESS CONTEXT: A decision filed under a filter nobody else uses can never be found again. The
    store introduces no vocabulary of its own: every filter value must already mean something to
    the rest of the repository (ADR-061 reuses the existing identity vocabularies).
ARCHITECTURE: Pure reads (UTF-8, bounded) of four small files, returned as frozen sets. A missing
    or unreadable source raises VocabularyError naming the file, so a validation run says which
    vocabulary it could not check instead of silently accepting any value.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

COMPONENTS_FILE = "docs/components.json"
AC_SCHEMA_FILE = "config/ac_store_schema.json"
ROADMAP_FILE = "docs/roadmap.json"
RULES_DIR = "templates/rules"
_GLOBS_LINE = re.compile(r"^globs:[ \t]*(.*)$((?:\n[ \t]+-[ \t]+.*)*)", re.MULTILINE)


class VocabularyError(Exception):
    """A vocabulary source is missing or malformed."""

    def __init__(self, source: str, detail: str) -> None:
        """Build the message from the source file and the problem."""
        super().__init__(f"vocabulary source {source}: {detail}")
        self.source = source
        self.detail = detail


@dataclass(frozen=True)
class Vocabulary:
    """The values a record's filters may use."""

    components: frozenset[str] = field(default_factory=frozenset)
    change_target: frozenset[str] = field(default_factory=frozenset)
    risk_surface: frozenset[str] = field(default_factory=frozenset)
    roadmap_phase: frozenset[str] = field(default_factory=frozenset)
    file_globs: frozenset[str] = field(default_factory=frozenset)

    def unknown(self, filters: dict[str, list[str]]) -> list[str]:
        """Return one message per filter value that is not in its vocabulary."""
        out: list[str] = []
        for name, values in filters.items():
            allowed = getattr(self, name)
            out += [f"{name} value {v!r} is not in the existing vocabulary" for v in values
                    if v not in allowed]
        return out


def _read_json(root: Path, relative: str) -> dict:
    """Read a JSON object below `root`, raising VocabularyError on any problem."""
    try:
        data = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VocabularyError(relative, f"{type(exc).__name__}: cannot read it") from exc
    if not isinstance(data, dict):
        raise VocabularyError(relative, "top level must be a JSON object")
    return data


def _enum_values(schema: dict, field_name: str) -> frozenset[str]:
    """Return the string enum of a schema property (a bare enum or one inside anyOf)."""
    prop = schema.get("properties", {}).get(field_name, {})
    found: set[str] = set(prop.get("enum", []))
    for branch in prop.get("anyOf", []):
        found |= set(branch.get("enum", []))
    if not found:
        raise VocabularyError(AC_SCHEMA_FILE, f"no enum found for {field_name}")
    return frozenset(found)


def rule_globs(root: Path) -> frozenset[str]:
    """Return every glob named in a rule file's `globs:` front matter line."""
    folder = root / RULES_DIR
    found: set[str] = set()
    try:
        files = sorted(folder.glob("*.md"))
    except OSError as exc:
        raise VocabularyError(RULES_DIR, f"{type(exc).__name__}: cannot list it") from exc
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.warning("rule file %s unreadable; its globs are not in the vocabulary", path)
            continue
        match = _GLOBS_LINE.search(text.split("\n---", 1)[0])
        if match:
            inline = match.group(1).split(",") if match.group(1) else []
            listed = [line.strip()[1:] for line in match.group(2).splitlines() if line.strip()]
            found |= {g.strip().strip("\"'") for g in [*inline, *listed] if g.strip()}
    found.discard("")
    return frozenset(found)


def load_vocabulary(root: Path) -> Vocabulary:
    """Load all five vocabularies from the repository at `root`.

    Raises:
        VocabularyError: A source is missing, unreadable or has no usable values.
    """
    components = _read_json(root, COMPONENTS_FILE).get("components", {})
    phases = _read_json(root, ROADMAP_FILE).get("phases", [])
    schema = _read_json(root, AC_SCHEMA_FILE)
    if not components:
        raise VocabularyError(COMPONENTS_FILE, "no components found")
    if not phases:
        raise VocabularyError(ROADMAP_FILE, "no phases found")
    return Vocabulary(
        components=frozenset(components), change_target=_enum_values(schema, "change_target"),
        risk_surface=_enum_values(schema, "risk_surface"),
        roadmap_phase=frozenset(p["id"] for p in phases if isinstance(p, dict) and "id" in p),
        file_globs=rule_globs(root))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The vocabularies are read from the files that define them, never
#   copied into the kernel, so a new component or roadmap phase is usable as a filter the day it
#   is declared. (#KernelDecisionStore)
# ====================================================================
