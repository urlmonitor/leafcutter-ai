"""
MODULE: _cross_layer_seam_checks.py
GOAL: The BP-1100g-5-i cross_layer_seam_answer shortfall reader — a
    commit-time reader over a ticket's ``## Comments`` ``completion_manifest:``
    block(s) that reports exactly three named shortfall kinds against the
    BP-1100g-5 shipped record shape (SKILL.md §2b.2, key
    ``cross_layer_seam_answer``, shapes ``{result: covered, producing_side,
    consuming_side}`` and ``{result: not_applicable, reason, remediation}``):
    "reasonless", "absent", and "answered_more_than_once". A reasoned
    negative (``result: not_applicable`` with a non-empty ``reason``) is a
    valid answer and must never be reported, and a ticket that never
    produced a ``completion_manifest:`` at all (halted run, or a pre-epoch
    legacy sign-off per SKILL.md §2b Legacy Compatibility) is a DIFFERENT
    state from "absent" and must also never be reported.
BUSINESS CONTEXT: completion_manifest has ZERO other code readers today.
    This module is extracted (rather than inlined into
    ``_signoff_parity_checks.py``) purely to keep the sibling file under its
    400-line budget — ``check_ticket_signoff_parity.py`` re-exports
    ``check_cross_layer_seam_answer`` from ``_signoff_parity_checks`` so the
    import surface test-writer built against (``from
    _signoff_parity_checks import check_cross_layer_seam_answer``) is
    unaffected.
ARCHITECTURE: Cardinality for the answered-more-than-once case is established
    from the RAW TEXT the run actually emitted — never from a
    ``yaml.safe_load`` of the whole ``completion_manifest:`` block, because
    PyYAML's default loader silently keeps only the last of a duplicate
    mapping key (the exact trap BO-1000b-1-i's own count-guard regex fell
    into, from the other direction — matching only quoted-string call sites
    and missing template-literal ones). Deployed alongside
    ``_signoff_parity_checks.py`` in ``scripts/commit_guardian/`` (wholesale
    directory copy at build time — no separate deploy-manifest entry needed).
"""

import re

import yaml

# ---------------------------------------------------------------------------
# Raw-text block extraction
# ---------------------------------------------------------------------------

_COMPLETION_MANIFEST_KEY_RE = re.compile(r"^completion_manifest:\s*$")
_SEAM_ANSWER_KEY_RE = re.compile(r"^(?P<indent>[ \t]*)cross_layer_seam_answer:\s*$")


def _line_indent(line: str) -> int:
    """Return the number of leading space/tab characters on ``line``."""
    return len(line) - len(line.lstrip(" \t"))


def _collect_indented_block(lines: list[str], start_idx: int) -> list[str]:
    """Collect the child lines belonging to a top-level ``key:`` block.

    A child line is any blank line, or any line indented relative to column
    0. The block ends at the first non-blank, zero-indented line (or end of
    the ticket text).

    Args:
        lines: Full ticket content split into lines.
        start_idx: Index of the ``completion_manifest:`` line itself.

    Returns:
        The block's body lines (excluding the ``completion_manifest:`` line).
    """
    block: list[str] = []
    for line in lines[start_idx + 1 :]:
        if line.strip() == "":
            block.append(line)
            continue
        if _line_indent(line) == 0:
            break
        block.append(line)
    return block


def _find_completion_manifest_blocks(content: str) -> list[list[str]]:
    """Find every ``completion_manifest:`` block anywhere in ``content``.

    Args:
        content: Full ticket text.

    Returns:
        One entry per raw textual ``completion_manifest:`` occurrence, each
        holding that block's child lines, in document order.
    """
    lines = content.splitlines()
    blocks: list[list[str]] = []
    for idx, line in enumerate(lines):
        if _COMPLETION_MANIFEST_KEY_RE.match(line):
            blocks.append(_collect_indented_block(lines, idx))
    return blocks


def _parse_seam_answer_occurrence(
    block_lines: list[str], key_idx: int, key_indent: int
) -> dict:
    """Parse ONE raw ``cross_layer_seam_answer:`` occurrence's nested body.

    Args:
        block_lines: Child lines of the enclosing ``completion_manifest:`` block.
        key_idx: Index into ``block_lines`` of the ``cross_layer_seam_answer:`` line.
        key_indent: Indentation (character count) of that line.

    Returns:
        The parsed answer mapping, or ``{}`` when the occurrence's body is
        missing or fails to parse as YAML. An empty dict is itself a
        non-conforming answer downstream — it is never silently dropped from
        the cardinality count.
    """
    body_lines: list[str] = []
    for line in block_lines[key_idx + 1 :]:
        if line.strip() == "":
            body_lines.append(line)
            continue
        if _line_indent(line) <= key_indent:
            break
        body_lines.append(line)

    text = "cross_layer_seam_answer:\n" + "\n".join(body_lines)
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    answer = parsed.get("cross_layer_seam_answer")
    return answer if isinstance(answer, dict) else {}


def extract_cross_layer_seam_answers(content: str) -> list[dict] | None:
    """Extract every raw ``cross_layer_seam_answer:`` occurrence from ``content``.

    Per BP-1100g-5-i, cardinality is established from the raw text the run
    actually emitted, never from a de-duplicated ``yaml.safe_load`` of the
    whole block (PyYAML silently keeps only the last of a duplicate mapping
    key, which would hide the answered-more-than-once defect).

    Args:
        content: Full ticket text.

    Returns:
        ``None`` when no ``completion_manifest:`` block exists anywhere in
        ``content`` — the no-record / halted-run / legacy state (SKILL.md
        §2b Legacy Compatibility). ``[]`` when at least one
        ``completion_manifest:`` block exists but none carries the key.
        Otherwise one parsed dict per raw textual occurrence, in document
        order.
    """
    blocks = _find_completion_manifest_blocks(content)
    if not blocks:
        return None

    answers: list[dict] = []
    for block_lines in blocks:
        for idx, line in enumerate(block_lines):
            m = _SEAM_ANSWER_KEY_RE.match(line)
            if m is None:
                continue
            key_indent = len(m.group("indent"))
            answers.append(_parse_seam_answer_occurrence(block_lines, idx, key_indent))
    return answers


# ---------------------------------------------------------------------------
# Shortfall classification
# ---------------------------------------------------------------------------


def _classify_seam_answer(answer: dict, ticket_path: str) -> dict | None:
    """Classify a single ``cross_layer_seam_answer`` mapping.

    Args:
        answer: The parsed answer mapping (may be empty or malformed).
        ticket_path: Identifies the work item in the returned report.

    Returns:
        ``None`` for a conforming answer (``result: covered`` naming both
        ``producing_side`` and ``consuming_side``, or ``result:
        not_applicable`` with a non-empty ``reason``). Otherwise a
        ``"reasonless"``-kind shortfall dict — a single answer that is
        neither conforming shape is a malformed or missing reason/side,
        which is the ``reasonless`` case among this AC's three named kinds.
    """
    result = answer.get("result")

    if result == "covered":
        if answer.get("producing_side") and answer.get("consuming_side"):
            return None
        detail = (
            "cross_layer_seam_answer result: covered is missing a non-empty "
            "producing_side and/or consuming_side"
        )
    elif result == "not_applicable":
        if answer.get("reason"):
            return None
        detail = (
            "cross_layer_seam_answer result: not_applicable is missing a "
            "non-empty reason"
        )
    else:
        detail = (
            f"cross_layer_seam_answer has an unrecognised or missing result "
            f"{result!r}; expected 'covered' or 'not_applicable'"
        )

    return {"work_item_id": ticket_path, "kind": "reasonless", "detail": detail}


def check_cross_layer_seam_answer(content: str, ticket_path: str) -> dict | None:
    """Apply the BP-1100g-5-i shortfall rule to one ticket's hand-off record.

    A run that never produced a ``completion_manifest:`` for this work item
    at all (halted before hand-off, or a pre-epoch legacy sign-off with no
    manifest block per SKILL.md §2b Legacy Compatibility) is a DIFFERENT
    state from "absent" and must never be reported.

    Args:
        content: Full ticket text.
        ticket_path: Identifies the work item in the returned report.

    Returns:
        ``None`` when there is no shortfall — either the no-record state
        described above, or exactly one conforming answer. Otherwise
        ``{"work_item_id": ..., "kind": "reasonless" | "absent" |
        "answered_more_than_once", "detail": <non-empty str>}``.
    """
    answers = extract_cross_layer_seam_answers(content)
    if answers is None:
        return None  # no completion_manifest at all — no-record state

    if len(answers) == 0:
        return {
            "work_item_id": ticket_path,
            "kind": "absent",
            "detail": (
                "a completion_manifest: block exists for this work item but "
                "carries no cross_layer_seam_answer key at all"
            ),
        }

    if len(answers) > 1:
        return {
            "work_item_id": ticket_path,
            "kind": "answered_more_than_once",
            "detail": (
                f"cross_layer_seam_answer appears {len(answers)} times in "
                "this work item's hand-off record; exactly one answer is "
                "required"
            ),
        }

    return _classify_seam_answer(answers[0], ticket_path)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [python-coder/BP-1100g-5-i]: Created module. Extracted from an
  initial inline addition to _signoff_parity_checks.py to keep that file
  under its 400-line budget (it was already at 414 stripped lines before
  this ticket). extract_cross_layer_seam_answers() (raw-text occurrence
  scanner over completion_manifest: blocks) and
  check_cross_layer_seam_answer() (classifies one ticket's record into the
  three named shortfall kinds — reasonless, absent, answered_more_than_once —
  or None for a conforming answer or a genuine no-record/halted-run state).
  Re-exported from _signoff_parity_checks.py so `from _signoff_parity_checks
  import check_cross_layer_seam_answer` (the import surface test-writer
  built against) continues to work, and wired into
  check_ticket_signoff_parity.py's _validate_ticket_content().
====================================================================
"""
