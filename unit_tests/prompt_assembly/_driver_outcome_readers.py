"""
MODULE: _driver_outcome_readers
GOAL: Read-only helpers that interpret the result a build driver returns:
      does it claim the epic complete, deny it, or name work as not built.
BUSINESS CONTEXT: The driver tests assert on a workflow's completion wording
    and outcome status; these readers keep that interpretation in one place so
    a success status that contradicts its own message is detected the same way
    everywhere.
ARCHITECTURE: Pure functions over the harness ``result`` object; no node or
    subprocess access. _driver_harness star-imports this module so existing
    ``from _driver_harness import claims_epic_complete`` callers keep working.
    Split out of _driver_harness.py to honour the file-size ratchet.

DECISION HISTORY:
    - 2026-10-12 (BO-4300 ticket 10): moved verbatim out of _driver_harness.py;
      behaviour unchanged.
"""

from __future__ import annotations

import json
import re

# ---------------------------------------------------------------------------
# Completion-output helpers
# ---------------------------------------------------------------------------

_NEGATION = re.compile(
    r"\b(not|never|cannot|unverified|un-verified|incomplete|without|no)\b", re.IGNORECASE
)
_COMPLETE_CLAIM = re.compile(r"\bcomplete[ds]?\b", re.IGNORECASE)


def output_text(result) -> str:
    """The completion output a run emitted, as a single searchable string."""
    if result is None:
        return ""
    return json.dumps(result, sort_keys=True)


def claims_epic_complete(result) -> bool:
    """True when the emitted output asserts, unqualified, that the epic is complete.

    A sentence that carries a negation ("not verified complete", "no ticket
    completed") is not a completion claim. This mirrors what an operator reads.
    """
    if result is None:
        return False
    message = ""
    if isinstance(result, dict):
        message = str(result.get("message") or "")
        for key in ("summary", "completion_output", "epic_status"):
            if result.get(key):
                message += " " + str(result[key])
    else:
        message = str(result)

    for sentence in re.split(r"(?<=[.!?])\s+|\n", message):
        if not sentence.strip():
            continue
        if _COMPLETE_CLAIM.search(sentence) and not _NEGATION.search(sentence):
            return True
    return False


# ---------------------------------------------------------------------------
# The epic-level OUTCOME VALUE (BO-300a-5-ii)
#
# claims_epic_complete() above reads only the message string, so it is
# structurally blind to a payload whose leading outcome value says success
# while its own verdict and prose say the epic is not complete. It is left
# exactly as it was — every existing caller asserts on the prose and must keep
# asserting on the prose. The helpers below add the missing channel: the value
# a machine routes on, the epic's own complete-or-not verdict, and a single
# invariant over the three.
# ---------------------------------------------------------------------------

#: Values of the payload's leading ``status`` field that a caller routing on
#: that field alone would read as "this succeeded".
SUCCESS_OUTCOME_VALUES = frozenset(
    {"ok", "success", "succeeded", "complete", "completed", "done", "pass", "passed"}
)

_DENIES_COMPLETE = re.compile(
    r"\bnot\s+complete\b|\bnever\s+complete\b|\bincomplete\b|\bnot\s+completed\b",
    re.IGNORECASE,
)


def _message_text(result) -> str:
    """The prose an operator reads out of a completion payload."""
    if result is None:
        return ""
    if not isinstance(result, dict):
        return str(result)
    text = str(result.get("message") or "")
    for key in ("summary", "completion_output", "epic_status"):
        if result.get(key):
            text += " " + str(result[key])
    return text


def outcome_status(result):
    """The single overall outcome value the payload leads with, or None."""
    if not isinstance(result, dict):
        return None
    value = result.get("status")
    return None if value is None else str(value)


def is_success_outcome(result) -> bool:
    """True when a caller reading ONLY the outcome value would take it for success."""
    status = outcome_status(result)
    return status is not None and status.strip().lower() in SUCCESS_OUTCOME_VALUES


def epic_complete_verdict(result):
    """The epic's own complete-or-not verdict: True, False, or None if unstated."""
    if not isinstance(result, dict) or "epic_complete" not in result:
        return None
    return bool(result["epic_complete"])


def denies_epic_complete(result) -> bool:
    """True when the payload's own prose states the epic is NOT complete."""
    return bool(_DENIES_COMPLETE.search(_message_text(result)))


# ---------------------------------------------------------------------------
# NOT-BUILT WORDING AND THE PER-PIECE CONTRADICTION (BO-300a-5-iii)
#
# _DENIES_COMPLETE above recognises a contradiction only by the phrases "not
# complete" / "incomplete". The removals branch of epicRecheckReport does not
# use either: it states that a NAMED PIECE OF WORK "was not built", which is the
# same contradiction in different words and slips straight past the check
# written to catch this class. That blind spot is why a payload reporting one
# ticket as completed AND as never built reached a reviewer under a green suite.
#
# Two channels are added, both purely additive:
#
#   * states_work_not_built()  — the missing WORDING, checked alongside the
#     three conditions epic_outcome_disagreement() already checks, and only for
#     payloads that lead with a success value (as those three are).
#
#   * completed_and_unbuilt_conflict() — the missing PER-PIECE fact. Checked
#     unconditionally, because "this payload names one piece of work as both
#     completed and not built" is a contradiction no matter what outcome value
#     the payload leads with. A withheld payload that says it both built and did
#     not build the same ticket is exactly as unusable as a successful one.
# ---------------------------------------------------------------------------

#: The wordings these drivers use to say a named piece of work was NOT built.
#: `epicRecheckReport` emits "were not built" for both additions and removals;
#: the alternatives are listed so a re-wording of the same claim is still seen.
_DENIES_BUILT = re.compile(
    r"\b(?:not|never)\s+(?:built|done|run|executed)\b"
    r"|\bunbuilt\b"
    r"|\b(?:was|were|is|are)\s+(?:not|never)\s+(?:built|completed|done)\b",
    re.IGNORECASE,
)


def states_work_not_built(result) -> bool:
    """True when the payload's prose states that some work was NOT built."""
    return bool(_DENIES_BUILT.search(_message_text(result)))


def completed_work_paths(result) -> list:
    """Every piece of work the payload's OWN record names as completed.

    This is the drive's proof that the work was done: the epic completion
    returns report it under ``completed_batches[*].tickets``. A removal judged
    against this list is a lifecycle move, not unbuilt work.
    """
    if not isinstance(result, dict):
        return []
    out = []

    def _add(value):
        if isinstance(value, str) and value and value not in out:
            out.append(value)

    for batch in result.get("completed_batches") or []:
        if not isinstance(batch, dict):
            continue
        for entry in batch.get("tickets") or []:
            _add(entry if isinstance(entry, str) else (entry or {}).get("path"))
    for key in ("completed_tickets", "completed_work", "completed_ticket_paths"):
        for entry in result.get(key) or []:
            _add(entry if isinstance(entry, str) else (entry or {}).get("path"))
    return out


def _named_work_paths(result) -> list:
    """Every work path the payload names anywhere the checks below care about."""
    out = list(completed_work_paths(result))
    for key in ("no_longer_present", "discovered_after_planning"):
        for entry in (result or {}).get(key) or []:
            if isinstance(entry, str) and entry and entry not in out:
                out.append(entry)
    return out


def paths_described_as_not_built(result) -> list:
    """The pieces of work this payload describes as never built / not done.

    Sentence-scoped: a path counts only when it appears in a sentence that
    makes the not-built claim, so re-wording a removal as "no longer present"
    (with no claim about whether it was built) correctly stops matching.
    ``discovered_after_planning`` is always included — the field's own contract
    is work that arrived after the plan and was therefore never built.
    """
    if not isinstance(result, dict):
        return []
    out = []
    for entry in result.get("discovered_after_planning") or []:
        if isinstance(entry, str) and entry and entry not in out:
            out.append(entry)
    candidates = _named_work_paths(result)
    for sentence in re.split(r"(?<=[.!?])\s+|\n", _message_text(result)):
        if not _DENIES_BUILT.search(sentence):
            continue
        for path in candidates:
            if path in sentence and path not in out:
                out.append(path)
    return out


def completed_and_unbuilt_conflict(result) -> list:
    """Pieces of work this payload names BOTH as completed and as not built.

    The invariant BO-300a-5-iii states directly. Non-empty is always a defect:
    one output cannot assert that the same piece of work was done and not done.
    """
    completed = completed_work_paths(result)
    if not completed:
        return []
    return [p for p in paths_described_as_not_built(result) if p in completed]


def epic_outcome_disagreement(result):
    """Name the self-contradiction in an epic payload, or None if it agrees.

    The invariant BO-300a-5-ii states directly: the leading outcome value, the
    ``epic_complete`` verdict and the sentence the payload states about the
    epic must never contradict each other. Returns a human-readable string
    describing the disagreement so a failing test names what it found.

    BO-300a-5-iii extends it in two additive ways: the per-piece
    completed-and-not-built conflict (checked for every payload, success or
    not), and the not-built WORDING the removals branch actually emits (checked
    for success payloads alongside the three conditions already here).
    """
    if not isinstance(result, dict):
        return None

    conflict = completed_and_unbuilt_conflict(result)
    if conflict:
        return (
            "the payload names the same piece(s) of work BOTH as work the drive "
            f"completed and as work that was not built: {', '.join(conflict)}"
        )

    if not is_success_outcome(result):
        return None
    contradictions = []
    if epic_complete_verdict(result) is False:
        contradictions.append("`epic_complete: false`")
    if result.get("epic_set_verified") is False:
        contradictions.append("`epic_set_verified: false`")
    if denies_epic_complete(result):
        contradictions.append(
            "a message that states the epic is NOT complete "
            f"({_message_text(result)!r})"
        )
    if states_work_not_built(result):
        contradictions.append(
            "a message that states a named piece of work was NOT built "
            f"({_message_text(result)!r})"
        )
    if not contradictions:
        return None
    return (
        f"the payload leads with `status: {outcome_status(result)!r}` (a success "
        f"value) while also carrying " + " and ".join(contradictions)
    )
