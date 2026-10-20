"""
MODULE: scripts/build_orchestration/_wvw_reply.py
GOAL: Read the preparer's raw reply and sort its entries against the owed names.
BUSINESS CONTEXT: TQ-500g-1-ix, contract TQ-500g-1-iv. The reply never defines what is
    owed and its claims (diff, caught, test names, anomalies) are never trusted: only the
    status, reason and replacements of an entry whose name matches an owed name EXACTLY
    are used. A reply that cannot be read stops the step; a malformed entry inside a
    readable reply only fails that one name.
ARCHITECTURE: Pure functions over text and dicts (no I/O). :class:`ReplyError` carries
    the full error sentence the step prints.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

UNREADABLE = "the preparer's reply could not be read"
STATUSES = ("prepared", "could_not_prepare")
NO_ANSWER = "no alteration returned"
TWO_ANSWERS = "more than one alteration returned"
NO_REASON = "no reason given"


class ReplyError(Exception):
    """The reply stops the step; ``str(exc)`` is the error the step prints."""


@dataclass
class Reply:
    """A readable success-shape reply: its entries and its anomalies (log only)."""

    entries: list = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)


@dataclass
class Answer:
    """What the reply says for one owed name: a refusal reason, or replacements to apply."""

    reason: str = ""
    replacements: list[dict] = field(default_factory=list)


def _unreadable(detail: str) -> ReplyError:
    """Build the unreadable-reply error."""
    msg = f"{UNREADABLE}: {detail}"
    return ReplyError(msg)


def parse_reply(text: str, work_key: str) -> Reply:
    """Parse *text* as the preparer's reply for *work_key*.

    Args:
        text: The raw reply text.
        work_key: The work key the step was started for.

    Returns:
        The :class:`Reply`.

    Raises:
        ReplyError: When the reply is unreadable or is the failed shape.
    """
    if not text.strip():
        raise _unreadable("the reply is empty")
    try:
        data = json.loads(text)
        json.dumps(data, ensure_ascii=False).encode("utf-8")  # a lone surrogate cannot be written back
    except (ValueError, RecursionError) as exc:  # UnicodeEncodeError is a ValueError
        raise _unreadable(f"not one usable JSON value ({exc})") from exc
    if not isinstance(data, dict):
        raise _unreadable("not one JSON object")
    anomalies = data.get("anomalies", [])
    if not isinstance(anomalies, list) or not all(isinstance(a, str) for a in anomalies):
        raise _unreadable("anomalies is not a list of strings")
    if data.get("status") == "failed":
        summary = data.get("blocker_summary")
        if not isinstance(summary, str):
            raise _unreadable("the failed shape has no blocker_summary")
        msg = f"the preparer reported failure: {summary}"
        raise ReplyError(msg)
    if not isinstance(data.get("work_key"), str) or not isinstance(data.get("entries"), list):
        raise _unreadable("it matches neither the success nor the failed shape")
    if data["work_key"] != work_key:
        raise _unreadable(f"it is for work key {data['work_key']!r}, not {work_key!r}")
    return Reply(data["entries"], anomalies)


def group_by_name(entries: list, owed: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """Group reply entries by owed name (exact match); return ``(groups, ignored names)``."""
    groups: dict[str, list[dict]] = {name: [] for name in owed}
    ignored: list[str] = []
    for item in entries:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str):
            continue
        if name in groups:
            groups[name].append(item)
        elif name not in ignored:
            ignored.append(name)
    return groups, ignored


def _one_line(reason: object) -> str:
    """Return *reason* on one line, or the fixed wording when there is none."""
    if not isinstance(reason, str) or not reason.strip():
        return NO_REASON
    return re.sub(r"\r\n|\r|\n", " ", reason)


def _bad_replacement_field(repls: object) -> str:
    """Return the name of the first malformed replacement field, or ``""`` when all are fine."""
    if not isinstance(repls, list) or not repls:
        return "replacements"
    for repl in repls:
        if not isinstance(repl, dict):
            return "replacements"
        for key in ("path", "old", "new"):
            if not isinstance(repl.get(key), str):
                return key
    return ""


def answer_for(answers: list[dict]) -> Answer:
    """Turn the reply entries for one owed name into an :class:`Answer`."""
    if not answers:
        return Answer(NO_ANSWER)
    if len(answers) > 1:
        return Answer(TWO_ANSWERS)
    item = answers[0]
    status = item.get("status")
    if status not in STATUSES:
        return Answer("malformed reply entry: status")
    if status == "could_not_prepare":
        return Answer(_one_line(item.get("reason")))
    bad = _bad_replacement_field(item.get("replacements"))
    if bad:
        return Answer(f"malformed reply entry: {bad}")
    return Answer(replacements=item["replacements"])
