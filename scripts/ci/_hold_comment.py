"""
MODULE: _hold_comment
GOAL: The one comment the per-PR check `Post-merge suite status` keeps on a held
    pull request: what it says for each held state, how the check finds its own
    comment among the pull request's others, and the create / edit / lift
    decision around it.
BUSINESS CONTEXT: TQ-600a-13-vii. A failing status alone tells an author their pull
    request is blocked, not that the cause is outside their change; an author (here
    usually an agent) who cannot see that starts debugging their own diff. The comment
    says so, once, and is edited in place on every later evaluation so the thread
    never fills with copies and is never left claiming a hold that has lifted.
ARCHITECTURE: ``render_comment(verdict, now, previous, head_sha=)`` is pure: the
    body for a verdict. ``sync_comment(client, repo, pr, verdict, now, head_sha)`` is
    the only I/O: it lists the pull request's comments (every page, never leaving the
    API's origin), finds the check's own (first line is the marker AND author is the
    Actions bot), then creates, edits or leaves it alone. A held verdict creates once
    and edits on EVERY evaluation; a pass or exemption edits an own held comment to
    "lifted" once (details of the last hold kept collapsed) and otherwise writes
    nothing; nothing is ever deleted and no foreign comment is ever edited.
    A comment that cannot be listed in full means no write at all (a create could
    duplicate one that cannot be seen). The verdict is computed before this runs and
    nothing here changes it.
    TRUST: node ids, streak dates, stages and commit entries come from a notice a
    pull request may influence; each is rendered through ``_notice_render.code``
    (one inline span, no backtick, no line break, comment markers defused). Only the
    pull request number and a validated head SHA ever come from the event payload.
    Every shown string is cut to 300 characters and the body stays under 60,000 (the
    service refuses 65,536); a previous body is folded on a lift only while it still
    has the shape this check renders, else a one-line summary is folded; a comment is
    "own" only with a positive int ``id`` and an ``issue_url`` ending ``/issues/{pr}``.
    Extension points: -viii adds the ``exempt`` state (``LIFT_STATES``); -ix and -xiv
    own the wording of their states (``HELD_HEADLINES``).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from scripts.ci._github_rest import GitHubClient, GitHubError
from scripts.ci._notice_render import MAX_FAILING_SHOWN, code

logger = logging.getLogger("post_merge_hold")

MARKER = "<!-- post-merge-suite-status v1 -->"
BOT_LOGIN, BOT_TYPE = "github-actions[bot]", "Bot"
PAGE_SIZE, MAX_PAGES = 100, 100
SHORT_LIMIT = 300  # characters of any one untrusted string shown
BODY_LIMIT = 60_000  # GitHub refuses a comment past 65,536 characters
CODE_SPAN_RE = re.compile(r"`[^`]*`")
EDITED_SUMMARY = "The earlier held details were changed after the check wrote them and are not shown."
LIFT_STATES = frozenset({"pass", "exempt"})
RED, DID_NOT_COMPLETE = "red", "did_not_complete"
SHA_RE = re.compile(r"[0-9a-f]{40}")
URL_RE = re.compile(r"https?://[^\s<>`@]+")
LINK_RE = re.compile(r"<([^<>]*)>([^<]*)")
NEXT_RE = re.compile(r'rel\s*=\s*"?next"?(?:[;,\s]|$)')
HELD_PREFIX = "This pull request is held:"
HELD_HEADLINES = {
    RED: f"{HELD_PREFIX} the post-merge suite on main is red.",
    DID_NOT_COMPLETE: f"{HELD_PREFIX} the latest post-merge suite run on main did not complete.",
    "stale": f"{HELD_PREFIX} the post-merge suite has no fresh verdict.",
    "disabled": f"{HELD_PREFIX} the post-merge suite workflow is not active.",
    "never_run": f"{HELD_PREFIX} the post-merge suite has never run on main.",
    "could_not_read": f"{HELD_PREFIX} the post-merge suite status could not be read.",
}
GENERIC_HEADLINE = f"{HELD_PREFIX} the post-merge suite is not green."
LIFTED_HEADLINE = "The hold on this pull request is lifted."
OUTSIDE_NOTE = "This hold comes from the state of main, not from the changes in this pull request. The check re-evaluates on every push."
STATE_SENTENCES = {
    "stale": "The latest settled run is too old to count as a verdict.",
    "disabled": "No verdict can be given while the workflow is not active.",
    "never_run": "There is no run on record to give a verdict.",
    "could_not_read": "The run history could not be read, so the check holds rather than guess.",
}


class EventError(ValueError):
    """The event payload does not carry a usable pull request number."""


# --------------------------------------------------------------------------- the event
def valid_sha(value: object) -> str | None:
    """Return ``value`` when it is exactly 40 lowercase hex characters, else None."""
    return value if isinstance(value, str) and SHA_RE.fullmatch(value) else None


def read_event(path: str | None) -> tuple[int, str | None]:
    """Read ``(pull request number, validated head sha or None)`` from the event file, in Python.

    Nothing else of the payload is read. Raises ``EventError`` when there is no usable positive int number.
    """
    if not path:
        message = "GITHUB_EVENT_PATH is not set"
        raise EventError(message)
    try:
        with open(path, encoding="utf-8") as handle:  # noqa: PTH123 -- the interpreter itself reads the event
            payload = json.load(handle)
    except (OSError, ValueError, RecursionError) as exc:
        message = f"the event file cannot be read: {exc}"
        raise EventError(message) from exc
    pull = payload.get("pull_request") if isinstance(payload, dict) else None
    number = pull.get("number") if isinstance(pull, dict) else None
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        message = "the event has no pull_request.number that is a positive integer"
        raise EventError(message)
    head = pull.get("head")
    return number, valid_sha(head.get("sha") if isinstance(head, dict) else None)


# --------------------------------------------------------------------------- the body
def _stamp(now: datetime) -> str:
    """The evaluation time as ``%Y-%m-%dT%H:%M:%SZ`` (UTC)."""
    aware = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _link(url: object) -> str:
    """A link from the API as plain text when it is a clean URL, as inert code otherwise."""
    if isinstance(url, str) and URL_RE.fullmatch(url):
        return url
    return code(url)


def _short_code(text: object, limit: int = SHORT_LIMIT) -> str:
    """Untrusted ``text`` as one inline code span of at most ``limit`` characters inside it."""
    return code(str(text)[:limit])


def _head_text(head_sha: str | None) -> str:
    """The head commit, as code, or the words that it is unknown."""
    sha = valid_sha(head_sha)
    return f"head commit {code(sha)}" if sha else "head commit unknown"


def _commit_lines(block: dict) -> list[str]:
    """The commit range the notice carries: the anchor and each commit as short code, and how many more."""
    commits = [c for c in block.get("commits") or [] if isinstance(c, str)] if isinstance(block.get("commits"), list) else []
    anchor, omitted = block.get("anchor_sha"), block.get("commits_omitted")
    lines = []
    if isinstance(anchor, str) and anchor:
        lines.append(f"Commits merged since the last green run, which tested {code(anchor[:7])}:")
    elif commits:
        lines.append("Commits merged since the last green run:")
    lines += [f"- {code(sha[:7])}" for sha in commits]
    if isinstance(omitted, int) and not isinstance(omitted, bool) and omitted > 0:
        lines.append(f"- ... and {omitted} more")
    return [*lines, ""] if lines else []


def _failing_lines(block: dict) -> list[str]:
    """The failing node ids the notice carries, each as one code span, capped."""
    raw = block.get("failing")
    failing = [i for i in raw if isinstance(i, str)] if isinstance(raw, list) else []
    if not failing:
        return []
    lines = [f"Failing tests ({len(failing)}):", ""] + [f"- {_short_code(i)}" for i in failing[:MAX_FAILING_SHOWN]]
    if len(failing) > MAX_FAILING_SHOWN:
        lines.append(f"- ... and {len(failing) - MAX_FAILING_SHOWN} more")
    return [*lines, ""]


def _run_lines(verdict: dict) -> list[str]:
    """Run, notice and (red or did-not-complete) the evidence the notice carries, or that it was not found."""
    state, run, notice = verdict["state"], verdict.get("run") or {}, verdict.get("notice")
    lines = [f"Run: {_link(run['html_url'])}"] if run.get("html_url") else []
    if state not in (RED, DID_NOT_COMPLETE):
        return lines
    if not isinstance(notice, dict):
        lines += ["", "The notice for this run was not found."]
        if state == RED:
            lines.append("The fix route is unavailable until the notice exists; re-running the notice job of the run above creates it.")
        return lines
    block = notice.get("state_block") if isinstance(notice.get("state_block"), dict) else {}
    since = "Red since" if state == RED else "Not green since"
    lines.append(f"Notice: {_link(notice.get('html_url'))}")
    lines.append(f"{since}: {_short_code(block.get('red_since'), 64)}")
    if state == DID_NOT_COMPLETE:
        lines.append(f"Stopped at stage: {_short_code(block.get('stage'), 64)}")
    return [*lines, ""] + (_failing_lines(block) if state == RED else []) + _commit_lines(block)


def _held_body(verdict: dict, now: datetime, head_sha: str | None) -> list[str]:
    """The lines (after the marker) of a held comment."""
    state = verdict["state"]
    lines = [HELD_HEADLINES.get(state, GENERIC_HEADLINE), "", OUTSIDE_NOTE, ""]
    if state in STATE_SENTENCES:
        lines += [STATE_SENTENCES[state], ""]
    if state == "could_not_read" and verdict.get("reason"):
        lines += [f"Detail: {code(str(verdict['reason'])[:300])}", ""]
    lines += [*_run_lines(verdict), "", f"Evaluated at {_stamp(now)}; {_head_text(head_sha)}."]
    return lines


def _headline(body: str) -> str:
    """The first non-blank line after the marker."""
    lines = [line.strip() for line in body.splitlines()[1:] if line.strip()]
    return lines[0] if lines else ""


def is_lifted(body: str | None) -> bool:
    """True when ``body`` is a comment that already says the hold lifted."""
    return isinstance(body, str) and _headline(body) == LIFTED_HEADLINE


def _is_rendered_held(body: str) -> bool:
    """True when ``body`` still has the shape this check renders for a held state (a human may have edited it).

    Our marker first, one of our own held headlines, and no ``<``, ``@`` or ``](`` outside a code span: nothing
    this check writes puts markup, a mention or a link anywhere but in code.
    """
    if body.splitlines()[:1] != [MARKER] or _headline(body) not in {*HELD_HEADLINES.values(), GENERIC_HEADLINE}:
        return False
    prose = CODE_SPAN_RE.sub("", "\n".join(body.splitlines()[1:]))
    return not any(token in prose for token in ("<", "@", "]("))


def _folded(previous: str | None, budget: int) -> list[str]:
    """The last held details, collapsed and cut to ``budget`` characters on a line boundary.

    Only a previous body that still has the shape this check renders is folded; anything else is replaced by a
    one-line summary built from the check's own words.
    """
    if not previous:
        return []
    if _is_rendered_held(previous):
        kept, used = [], 0
        for line in previous.splitlines()[1:]:
            if used + len(line) + 1 > budget:
                kept.append("... (cut: the earlier details were too long to keep)")
                break
            kept.append(line)
            used += len(line) + 1
        text = "\n".join(kept).strip()
    else:
        text = _headline(previous) if previous.splitlines()[:1] == [MARKER] and _headline(previous) in HELD_HEADLINES.values() else EDITED_SUMMARY
    return ["", "<details>", "<summary>Last held details</summary>", "", text, "", "</details>"]


def _lifted_body(verdict: dict, now: datetime, previous: str | None, head_sha: str | None) -> list[str]:
    """The lines (after the marker) of a lifted comment."""
    run = verdict.get("run") or {}
    if verdict["state"] == "pass":
        why = f"the latest post-merge suite run on main is green: {_link(run.get('html_url'))}"
    else:
        why = _short_code(verdict.get("reason"))
    lines = [LIFTED_HEADLINE, "", f"Lifted at {_stamp(now)}; {_head_text(head_sha)}.", f"Why: {why}"]
    room = BODY_LIMIT - len(MARKER) - len("\n".join(lines)) - 200  # 200: the details wrapper and slack
    return lines + _folded(previous, max(room, 0))


def render_comment(verdict: dict, now: datetime, previous: str | None = None, *, head_sha: str | None = None) -> str:
    """Return the check's comment body for ``verdict``.

    ``previous`` is the check's earlier body, from which a lifted body takes its collapsed details.
    ``head_sha`` is the pull request's head commit (invalid or absent: the body says it is unknown).
    """
    if verdict["state"] in LIFT_STATES:
        lines = _lifted_body(verdict, now, previous, head_sha)
    else:
        lines = _held_body(verdict, now, head_sha)
    return "\n".join([MARKER, "", *lines]) + "\n"


# --------------------------------------------------------------------------- the service
def next_link(header: str | None) -> str | None:
    """The ``rel="next"`` target of a ``Link`` header, or None."""
    for url, params in LINK_RE.findall(header or ""):
        if NEXT_RE.search(params):
            return url
    return None


def list_comments(client: GitHubClient, repo: str, pr_number: int) -> list[dict]:
    """Every comment on the pull request, following ``Link: rel="next"`` through every page.

    Raises ``GitHubError`` when a page cannot be read or a ``next`` link leaves the API's origin (it is never
    requested: the request would carry the token).
    """
    path, query, seen, comments = f"/repos/{repo}/issues/{pr_number}/comments", {"per_page": PAGE_SIZE}, set(), []
    for _ in range(MAX_PAGES):
        payload, headers = client.get_with_headers(path, query)
        if not isinstance(payload, list):
            message = "the comment list is not a JSON array"
            raise GitHubError(message)
        comments += [c for c in payload if isinstance(c, dict)]
        target = next_link(headers.get("link"))
        if target is None:
            return comments
        path, query = client.same_origin_path(target), None
        if path is None or path in seen:
            message = "the comment list's next link leaves the API origin or repeats"
            raise GitHubError(message)
        seen.add(path)
    message = f"the comment list runs past {MAX_PAGES} pages"
    raise GitHubError(message)


def _plausible_id(comment: dict, pr_number: int) -> bool:
    """True when the comment's ``id`` is a positive int (never a bool) and its ``issue_url`` ends ``/issues/{pr_number}``."""
    comment_id, issue_url = comment.get("id"), comment.get("issue_url")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id < 1:
        return False
    return isinstance(issue_url, str) and issue_url.endswith(f"/issues/{pr_number}")


def find_own(comments: list[dict], pr_number: int) -> dict | None:
    """The check's own comment on ``pr_number``: first line exactly the marker AND authored by the Actions bot.

    Both together, plus a sane ``id`` and this pull request's ``issue_url``; anything else is not ours.
    """
    for comment in comments:
        user, body = comment.get("user"), comment.get("body")
        if not (isinstance(user, dict) and isinstance(body, str) and _plausible_id(comment, pr_number)):
            continue
        if user.get("login") == BOT_LOGIN and user.get("type") == BOT_TYPE and body.splitlines()[:1] == [MARKER]:
            return comment
    return None


def sync_comment(client: GitHubClient, repo: str, pr_number: int, verdict: dict, now: datetime, head_sha: str | None = None) -> None:
    """Create, edit or leave alone the check's one comment.

    A failed list or write (``GitHubError``) is logged and never raised; any other exception is a defect and propagates.
    """
    try:
        own = find_own(list_comments(client, repo, pr_number), pr_number)
    except GitHubError as exc:
        logger.warning("post-merge hold: comments of #%s unreadable, writing none: %s", pr_number, exc)
        return
    previous = own.get("body") if own else None
    if verdict["state"] in LIFT_STATES and (own is None or is_lifted(previous)):
        return
    body = {"body": render_comment(verdict, now, previous, head_sha=head_sha)}
    try:
        if own is None:
            client.post(f"/repos/{repo}/issues/{pr_number}/comments", body)
        else:
            client.patch(f"/repos/{repo}/issues/comments/{own['id']}", body)
    except GitHubError as exc:
        logger.warning("post-merge hold: the comment write on #%s was refused: %s", pr_number, exc)
