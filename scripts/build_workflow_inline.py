"""
MODULE: build_workflow_inline
GOAL: Fill the empty ``// WORKSPACE-ANSWER-START`` / ``// WORKSPACE-ANSWER-END``
    marker pair of a workflow template with the one tracked source block, and
    refuse anything that would leave a hand copy or a missing block deployed.
BUSINESS CONTEXT: Every workflow that needs a workspace applies the same
    acceptance predicate to the workspace maker's answer (BO-4300c-3). Hand
    copies drift (KI-BO-20260925-finalize-gate-accepts-agent-answers), so the
    block lives in templates/workflows-js/_shared/workspace-answer.js and is
    inlined at build time; workflow bodies cannot require a shared file
    (ADR-030).
ARCHITECTURE: A pure text transform called by
    ``build_phases_workflows.build_workflow_scripts`` once per template, BEFORE
    config-placeholder injection. It raises ``WorkspaceBlockError`` (a
    ``ValueError``) so the build fails instead of deploying a bad template; it
    never writes a file, so the caller's compare-before-write idempotency is
    untouched.
"""

from __future__ import annotations

import re
from pathlib import Path

START_MARKER = "// WORKSPACE-ANSWER-START"
END_MARKER = "// WORKSPACE-ANSWER-END"
SOURCE_RELATIVE = Path("_shared") / "workspace-answer.js"
_SOURCE_NAME = SOURCE_RELATIVE.as_posix()

_UNBALANCED = f"needs exactly one {START_MARKER} / {END_MARKER} pair"
_REVERSED = f"has {END_MARKER} before {START_MARKER}"
_HAND_FILLED = (
    f"has text between the markers already; the block is inlined from {_SOURCE_NAME} "
    "and must not be hand-filled"
)
_SOURCE_MISSING = f"carries the markers but {_SOURCE_NAME} is missing"
_SOURCE_EMPTY = f"carries the markers but {_SOURCE_NAME} is empty"
_SOURCE_HAS_MARKERS = f"carries the markers but {_SOURCE_NAME} itself spells a marker out"

_PAIR_RE = re.compile(
    re.escape(START_MARKER) + r"(?P<inner>.*?)" + re.escape(END_MARKER), re.DOTALL
)


class WorkspaceBlockError(ValueError):
    """A workflow template's WORKSPACE-ANSWER marker pair cannot be filled."""

    def __init__(self, template_name: str, problem: str) -> None:
        super().__init__(f"{template_name}: {problem}")


def inline_workspace_block(text: str, template_name: str, workflows_src: Path) -> str:
    """Return ``text`` with an empty marker pair filled from the shared source.

    Args:
        text: Template source (already decoded).
        template_name: File name, used in error messages.
        workflows_src: The ``templates/workflows-js`` directory.

    Returns:
        ``text`` unchanged when it carries no marker; otherwise ``text`` with
        the block between the markers.

    Raises:
        WorkspaceBlockError: The pair is unbalanced, already holds text, or the
            source block is missing or empty.
    """
    if START_MARKER not in text and END_MARKER not in text:
        return text
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise WorkspaceBlockError(template_name, _UNBALANCED)
    match = _PAIR_RE.search(text)
    if match is None:
        raise WorkspaceBlockError(template_name, _REVERSED)
    if match.group("inner").strip():
        raise WorkspaceBlockError(template_name, _HAND_FILLED)
    source = workflows_src / SOURCE_RELATIVE
    if not source.is_file():
        raise WorkspaceBlockError(template_name, _SOURCE_MISSING)
    block = source.read_text(encoding="utf-8").strip("\n")
    if not block.strip():
        raise WorkspaceBlockError(template_name, _SOURCE_EMPTY)
    if START_MARKER in block or END_MARKER in block:
        raise WorkspaceBlockError(template_name, _SOURCE_HAS_MARKERS)
    return text[: match.start("inner")] + "\n" + block + "\n" + text[match.end("inner"):]


# DECISION HISTORY
# ================================================================================
# - 2026-10-15 12:00 [python-coder]: Created as its own module (build_phases_workflows.py is
#   over the size limit); pure text transform that raises instead of deploying a hand-filled
#   or sourceless marker pair. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/23)
