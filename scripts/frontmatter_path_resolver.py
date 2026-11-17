"""
MODULE: frontmatter_path_resolver
GOAL: Resolve a single element of a path-bearing frontmatter field
    (``related_docs``, ``related_code``, ``architecture_diagrams``, or any
    future field driven by the same list) to the one path string it
    denotes -- whichever of the two accepted shapes the entry uses -- or a
    named refusal when the entry's shape is not one of the two accepted
    ones (AC GE-118d).
BUSINESS CONTEXT: templates/scripts/commit_guardian/frontmatter_validators.py's
    validate_paths() previously assumed every path_fields element was a bare
    string and did ``project_root_path / p`` directly; a labelled entry
    (a single-key mapping, e.g. ``{"explanation": "docs/foo.md"}``) raised
    ``TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'``
    (docs/known-issues/commit-guardian/open-blocker-ki-cg-008.md). This
    module is the ONE place the accepted-shape rule is declared, so
    validate_paths() (and any future second consumer -- see GE-118f) calls
    this resolver rather than re-testing element types inline; admitting a
    further shape is a one-line edit at this single declaration point.
ARCHITECTURE: One declared constant (``ACCEPTED_SHAPES``), one refusal
    dataclass (``PathEntryRefusal``), and one pure classification function
    (``resolve_frontmatter_path_entry``) that never raises -- an
    unsupported shape (e.g. a multi-key mapping) returns a
    ``PathEntryRefusal`` rather than needing a try/except wrapper to
    survive (CLAUDE.md Error Handling Policy Rule 4: a pure classification
    function must be total by construction). THE RESOLVER'S HOME IS
    SETTLED: this is a new top-level module in the VERBATIM-COPY tier
    (deployed by ``build_workflow_tools()`` in
    scripts/build_phases_workflows.py, alongside scripts/knowledge_query.py
    and scripts/knowledge_frontmatter_reader.py), never under
    templates/scripts/commit_guardian/ -- that directory is the COMPILED
    tier (config placeholders are injected into every ``.py`` file there),
    and this resolver has no config-dependent behaviour, so running it
    through ``inject_config()`` would be a category error and a latent
    hazard (any ``{{...}}``-shaped text in a refusal message would be
    silently substituted). See GE-118d's Implementation Notes for the full
    three-reason placement rationale (tier, dependency direction,
    ownership).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The one declared accepted-shape set (GE-118d Delivers-To contract: "Three
# outcomes only"). Extending accepted shapes is a one-line edit here; every
# consumer (validate_paths(), and GE-118f's second consumer) reads this SAME
# tuple via PathEntryRefusal.accepted_shapes rather than declaring its own.
ACCEPTED_SHAPES: tuple[str, ...] = (
    "bare string",
    "single-key mapping ({field_name: path_string})",
)

# Refusal reasons (GE-118d-1 / GE-118d-2). The arity rule lives here, where
# the accepted shape is declared, not in the guard (GE-118d-2).
GENERIC_REASON = "not an accepted shape"
ARITY_REASON = "an entry in the labelled form carries exactly one label and one path"


@dataclass(frozen=True)
class PathEntryRefusal:
    """A frontmatter path-field entry whose shape is not one of the two accepted ones.

    Attributes:
        field: The frontmatter field the entry was found in (e.g.
            ``"related_docs"``).
        entry: The entry exactly as parsed. Callers must never render this
            value's repr into a user-facing message -- report the field
            name and, when applicable, a resolved path string instead.
        accepted_shapes: The same ``ACCEPTED_SHAPES`` tuple declared at
            module level, carried on every refusal so a caller never needs
            a second import to describe what would have been accepted.
    """

    field: str
    entry: Any
    accepted_shapes: tuple[str, ...]
    reason: str = GENERIC_REASON


def resolve_frontmatter_path_entry(entry: Any, field: str) -> str | PathEntryRefusal:
    """Classify one path-bearing frontmatter entry and resolve its path string.

    Total by construction (CLAUDE.md Error Handling Policy Rule 4): every
    input produces one of the three outcomes below, never an exception --
    this function performs no I/O and mutates no shared state, so it must
    not be wrapped in a try/except by any caller.

    Args:
        entry: One element of a path-bearing frontmatter list field, as
            parsed by ``yaml.safe_load`` -- a bare string, a single-key
            mapping, or anything else.
        field: The frontmatter field name *entry* was found in, carried
            through unchanged into a refusal so the caller does not need to
            re-supply it on a separate error path.

    Returns:
        str | PathEntryRefusal: The resolved path string for an
            accepted-bare or accepted-labelled entry, or a
            ``PathEntryRefusal`` naming *field*, *entry*, and
            ``ACCEPTED_SHAPES`` for any other shape -- including a
            single-key mapping whose value is not itself a string, and a
            multi-key mapping (deliberately refused rather than resolved
            to all of its values; see docs/known-issues/commit-guardian/
            open-blocker-ki-cg-008.md's sketch fix, which this AC exists to
            NOT repeat).
    """
    if isinstance(entry, str) and entry:
        return entry
    reason = GENERIC_REASON
    if isinstance(entry, dict) and len(entry) == 1:
        (value,) = entry.values()
        if isinstance(value, str) and value:
            return value
    elif isinstance(entry, dict) and len(entry) > 1:
        reason = ARITY_REASON
    return PathEntryRefusal(
        field=field, entry=entry, accepted_shapes=ACCEPTED_SHAPES, reason=reason
    )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-28 [python-coder/GE-118d]: Created this module. See the module
  docstring for the full placement rationale (settled 2026-09-21 by the
  user on an architect's recommendation) and GE-118d's Implementation
  Notes for the three-reason writeup (tier, dependency direction,
  ownership) this history entry deliberately does not repeat.
====================================================================
"""
