"""
MODULE: kernel.capabilities.decision.option_context
GOAL: Build the `option_context` a research request carries once options exist: each usable
    option with its title, description and the references it cites.
BUSINESS CONTEXT: Research that knows which options the decision weighs, and which files or
    symbols those options name, can look for evidence about the options instead of only about the
    question (Rev 3 section 10.5); an option is a design proposal that points at concrete code.
ARCHITECTURE: Pure functions over Working. `cited_refs` holds the option's evidence ids
    (source_refs, verbatim) plus file paths and symbol names mentioned in its description or its
    source_refs, extracted by fixed patterns, deduplicated in first-seen order and capped.
"""

from __future__ import annotations

import re

from kernel.capabilities.decision.state import ADDED_OPTION_PREFIX, Working
from kernel.contracts.decision import Option
from kernel.contracts.payloads import OptionContext

MAX_CITED_REFS = 16
_FILE_EXTENSIONS = "py|md|json|yaml|yml|toml|sql|ts|js|txt|cfg|ini|sh"
_PATTERNS = (
    # a path with at least one folder, an optional #anchor is not part of the path
    re.compile(r"(?<![\w/.-])(?:[\w.-]+/)+[\w.-]*\w\.\w+"),
    # a bare file name with a known extension
    re.compile(rf"(?<![\w/.-])[\w-]+\.(?:{_FILE_EXTENSIONS})\b"),
    # a backtick-quoted symbol or path
    re.compile(r"`([^`\n]{1,80})`"),
    # CamelCase class names (two or more humps)
    re.compile(r"\b(?:[A-Z][a-z0-9]+){2,}\b"),
    # snake_case identifiers and calls such as parse_record or parse()
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\b[a-z_][a-z0-9_]*\(\)"),
)


def extract_refs(text: str) -> list[str]:
    """Return the file paths and symbol names mentioned in text, in order of appearance."""
    found: list[tuple[int, str]] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            found.append((match.start(), (match.group(1) if pattern.groups else match.group(0))
                          .strip().rstrip(".,;:")))
    return [ref for _, ref in sorted(found, key=lambda pair: pair[0]) if ref]


def cited_refs(option: Option) -> list[str]:
    """Return an option's evidence ids and the paths and symbols its texts mention."""
    refs = [*option.source_refs, *extract_refs(option.description),
            *(r for ref in option.source_refs for r in extract_refs(ref))]
    return list(dict.fromkeys(refs))[:MAX_CITED_REFS]


def option_context(work: Working) -> list[OptionContext]:
    """Return the research context of every usable option (empty while no option exists)."""
    return [OptionContext(option_id=o.id, title=o.title,
                          description=o.description or None, cited_refs=cited_refs(o),
                          human_added=o.id.startswith(ADDED_OPTION_PREFIX))
            for o in work.usable_options]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: option_context is built from the decision's usable options with
#   pattern-based extraction of paths and symbols. (#KernelV01/A)
# - 2026-10-01 [python-coder]: Research consumes it; an option a human added is flagged
#   `human_added` so its claims are checked. (#KernelV01/D)
# ====================================================================
