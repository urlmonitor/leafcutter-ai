"""
MODULE: _notice_entrants
GOAL: Name the tests that newly entered the timing lane since the previous timing
    run, each with the newest commit that touched its test file in the range
    between the two runs' head commits.
BUSINESS CONTEXT: TQ-600a-13-xii. A correctness test that is marked ``timing_ratio``
    silently stops holding pull requests. The marker change arrives by a reviewed
    pull request, so naming the entrant and the commit that touched its file puts
    the move in front of a person instead of leaving it silent. Only a red timing
    notice carries the section (a green run opens no notice).
ARCHITECTURE: ``find_entrants`` compares the ``collected_ids`` of two verdict files
    (current minus previous, sorted) and resolves each entrant's commit with one
    ``git log -n 1 <previous head>..<head> -- <file>`` in the full-history
    checkout. ``render_entrant_lines`` turns that into bullet lines whose node id
    sits in a code span (untrusted text). No previous verdict, or an unchanged
    membership, yields no entrant and no line. An entrant whose commit cannot be
    found says so in words and names no sha. The only outside touch is ``git``.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from scripts.ci._notice_render import MAX_FAILING_SHOWN, SHA_RE, code
from scripts.ci._notice_render import _git as run_git

logger = logging.getLogger("post_merge_notice")

SHORT_SHA = 7


class Entrant(NamedTuple):
    """A test id new to the lane, with the full sha of the commit that touched its file (None when unknown)."""

    node_id: str
    commit: str | None


def _usable_ids(verdict: dict) -> list[str] | None:
    """Return a verdict's ``collected_ids``, or None unless it is a list of strings (an empty list is usable)."""
    ids = verdict.get("collected_ids")
    return ids if isinstance(ids, list) and all(isinstance(i, str) for i in ids) else None


def _newest_touching(repo_dir: str, previous_head: str, head: str, node_id: str) -> str | None:
    """Return the newest commit in ``(previous_head, head]`` that touched the file of ``node_id``, else None."""
    path = node_id.split("::", 1)[0]
    if not (SHA_RE.fullmatch(previous_head) and SHA_RE.fullmatch(head)) or path.startswith("-") or not path:
        return None
    out = run_git(repo_dir, "log", "-n", "1", "--format=%H", f"{previous_head}..{head}", "--", path)
    sha = (out or "").strip()
    return sha if SHA_RE.fullmatch(sha) else None


def find_entrants(current: dict, previous: dict | None, repo_dir: str) -> list[Entrant]:
    """Return the ids in ``current`` but not in ``previous``, sorted, each with its marker commit.

    ``previous`` None (no earlier settled timing run, or its artifact is gone) means no entrants: with
    nothing to compare against, every test would otherwise read as new. A previous run that did not
    complete (other than by selecting nothing) did not establish the lane's membership either: its
    ``collected_ids`` would be a partial list, and every test it missed would read as new.
    """
    if previous is None or (previous.get("verdict") == "did_not_complete" and previous.get("stage") != "empty_selection"):
        return []
    previous_ids, current_ids = _usable_ids(previous), _usable_ids(current)
    if previous_ids is None or current_ids is None:
        logger.warning("a verdict has no usable collected_ids list (old schema or hand-edited?); naming no lane entrants")
        return []
    new_ids = sorted(set(current_ids) - set(previous_ids))
    previous_head, head = str(previous.get("head_sha") or ""), str(current.get("head_sha") or "")
    return [Entrant(node_id, _newest_touching(repo_dir, previous_head, head, node_id)) for node_id in new_ids]


def render_entrant_lines(entrants: list[Entrant]) -> list[str]:
    """Return the section naming each entrant (one bullet each), or no lines when there are none."""
    if not entrants:
        return []
    lines = [f"New in the timing lane since the previous run ({len(entrants)}), with the commit that touched the test's file:", ""]
    for entrant in entrants[:MAX_FAILING_SHOWN]:
        if entrant.commit:
            lines.append(f"- {code(entrant.node_id)} entered the lane; commit {code(entrant.commit[:SHORT_SHA])}")
        else:
            lines.append(f"- {code(entrant.node_id)} entered the lane; the commit that touched its file could not be determined")
    if len(entrants) > MAX_FAILING_SHOWN:
        lines.append(f"- ... and {len(entrants) - MAX_FAILING_SHOWN} more")
    return lines
