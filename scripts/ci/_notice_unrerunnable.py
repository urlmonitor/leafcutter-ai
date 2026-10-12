"""
MODULE: _notice_unrerunnable
GOAL: Turn the ``reevaluate`` job's ``unrerunnable`` output into the lines a
    ``post-merge-red`` notice description carries: one line per pull request whose
    hold could not be re-run, naming ``#<pr>`` and the reason.
BUSINESS CONTEXT: TQ-600a-13-xv. The re-run job holds no ``issues`` scope, so it
    hands its list to the notice job as text. That hand-over is data from another
    job: a broken one must degrade to "nothing named", never to "no notice".
ARCHITECTURE: Pure and stdlib-only. ``parse_unrerunnable`` accepts the JSON text
    and returns only well-formed entries (an int ``pr``, a ``reason`` made of
    lower-case letters, digits and underscores); anything else is dropped.
    ``unrerunnable_lines`` renders the entries as bullet lines through the notice's
    own ``code`` span so untrusted text cannot forge the state block.
"""

from __future__ import annotations

import json
import re

from scripts.ci._notice_render import code

REASON_RE = re.compile(r"[a-z0-9_]{1,64}")


def parse_unrerunnable(text: str | None) -> list[dict]:
    """The well-formed ``{pr, reason}`` entries of the JSON ``text``; empty for absent, empty or unusable text."""
    if not text or not text.strip():
        return []
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return []
    if not isinstance(data, list):
        return []
    entries = [e for e in data if isinstance(e, dict) and isinstance(e.get("pr"), int) and not isinstance(e.get("pr"), bool)]
    return [e for e in entries if isinstance(e.get("reason"), str) and REASON_RE.fullmatch(e["reason"])]


def unrerunnable_lines(text: str | None) -> list[str]:
    """One bullet line per usable entry, ``- #<pr>: the hold was not re-run: <reason>``, with a short heading."""
    entries = parse_unrerunnable(text)
    if not entries:
        return []
    lines = ["Pull requests whose hold could not be re-run after the verdict changed (push, re-run by hand, or close):"]
    lines += [f"- #{e['pr']}: {code(e['reason'])}" for e in entries]
    return lines
