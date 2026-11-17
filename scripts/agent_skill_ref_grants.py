"""
MODULE: agent_skill_ref_grants
GOAL: Turn the ability references recognised in one document into the gate's
    finding lines: does not exist, exists but is not granted, differs only in
    case, names an agent rather than an ability.
BUSINESS CONTEXT: An instruction to use an ability the specialist's OWN definition
    does not grant is a setup fault the build must stop on (AR-400b-1), and the
    grant side is only ever the definition's own ``skills:`` declaration -- the
    derived central registry copy must never satisfy (or excuse) the check
    (AR-400b-1-i). A wrong-letter-case spelling and a specialist named as if it
    were an ability each get a diagnostic of their own instead of a misleading
    "does not exist" (AR-400b-2-v / -vi).
ARCHITECTURE: ``reference_findings`` is a pure function over the recognised
    references (``skill_ref_recognition.recognise``) and data the caller read: the
    subject, the file, the own grant ids (None when the document is a shared guide,
    or when the declaration was malformed and the comparison was skipped), the
    specialist's hand-off ids (None for a guide) and a ``bundle_gap`` probe for a
    path that names a file inside an ability's bundle. Precedence per reference:
    names an agent, then does not exist, then letter case, then a missing bundled
    file (reported as "does not exist"), then -- instructions only, never citations
    -- the grant comparison. A citation is exempt from the grant comparison but
    never from the existence check (AR-400b-2-iii). ``check_skill_refs`` reads the
    files and calls this; ``registry_validator`` reaches it only through there, so
    the validator, the build and the commit hook share one computation (AR-400b-4).
    Pure: no I/O of its own.

DECISION HISTORY
- 2026-10-16 [python-coder/AR-400b-1]: Created. The 'does not exist' line keeps the
  AR-400a-1 wording; the three new kinds follow the same subject / ability /
  file:line shape. (#TICKETLESS reason=ar-400b-1-grant-comparison)
- 2026-10-16 [python-coder/AR-400d-3]: No change here: a grant marked ``provided_by: project``
  reaches this module as an ordinary known, granted id because ``check_skill_refs`` adds the
  definition's own project-supplied ids to the known set it recognises against.
  (#TICKETLESS reason=ar-400d-3-project-supplied-marking)
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


def _where(ref: dict[str, Any], rel: str) -> str:
    """The ``'<text>' referenced at <file>:<line>`` part every finding shares."""
    return f"'{ref['ability_text']}' referenced at {rel}:{ref['line']}"


def _agent_finding(subject: str, rel: str, ref: dict[str, Any], hand_off: Iterable[str] | None) -> str:
    """One 'names an agent, not an ability' line, stating the hand-off relationship."""
    text = ref["ability_text"]
    if hand_off is None:
        tail = f"'{text}' is a specialist, not an ability"
    elif text in set(hand_off):
        tail = f"'{text}' is a specialist {subject} may hand work to"
    else:
        tail = f"'{text}' is a specialist, but is not in {subject}'s hand-off list"
    return f"{subject}: names an agent, not an ability: {_where(ref, rel)} ({tail})"


def _existence_finding(subject: str, rel: str, ref: dict[str, Any], reason: str) -> str:
    """One 'ability does not exist' line (the AR-400a-1 wording)."""
    return f"{subject}: ability does not exist: {_where(ref, rel)} ({reason})"


def _kind_finding(subject: str, rel: str, ref: dict[str, Any], grants: list[str] | None,
                  hand_off: Iterable[str] | None, bundle_gap: Callable[[str, str], str | None]) -> str | None:
    """The finding for one recognised reference, or None when it is clean."""
    canonical = ref["canonical_id"]
    if ref["names_agent"]:
        return _agent_finding(subject, rel, ref, hand_off)
    if canonical is None:
        return _existence_finding(subject, rel, ref, f"no skill directory templates/skills/{ref['ability_text']}/")
    if ref["ability_text"] != canonical:
        return (f"{subject}: ability name differs only in case: {_where(ref, rel)} "
                f"(did you mean '{canonical}'?)")
    gap = bundle_gap(canonical, ref["inner"])
    if gap is not None:
        return _existence_finding(subject, rel, ref, gap)
    if ref["citation"] or grants is None or canonical in grants:
        return None
    granted = ", ".join(grants) if grants else "nothing"
    return (f"{subject}: ability exists but is not granted: {_where(ref, rel)} "
            f"({subject} grants: {granted})")


def reference_findings(
    refs: list[dict[str, Any]],
    *,
    subject: str,
    rel: str,
    grants: list[str] | None,
    hand_off: Iterable[str] | None,
    bundle_gap: Callable[[str, str], str | None],
) -> list[str]:
    """Return one finding line per faulty reference, in the order the references were found.

    Args:
        refs: The recognised references of one document (``recognise`` output).
        subject: The specialist id, or the guide's repo-relative path.
        rel: The document's repo-relative path (reported with the line).
        grants: The ability ids the document's OWN declaration grants; None when no grant
            comparison applies (a shared guide, or a declaration that could not be read).
        hand_off: The ids the specialist may hand work to; None for a guide.
        bundle_gap: ``(canonical_id, inner_path)`` -> why a bundled file is missing, else None.

    Returns:
        Finding lines, empty when every reference is clean.
    """
    findings = (_kind_finding(subject, rel, ref, grants, hand_off, bundle_gap) for ref in refs)
    return [line for line in findings if line is not None]
