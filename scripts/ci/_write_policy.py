"""
MODULE: _write_policy
GOAL: Decide, for one request, whether the shared REST client may send it. The allowed-write
    list of TQ-600a-13-xi lives here and nowhere else.
BUSINESS CONTEXT: TQ-600a-13-xi. The post-merge family must never change the repository's
    code. Every write passes through ``GitHubClient.request``; this module is the one place
    that says which writes exist, so a reviewer audits one file, not every caller.
ARCHITECTURE: ``WritePolicy`` is a frozen, explicit grant per caller, bound to ONE repository
    (``repo``; none means no repository write at all). The default grants nothing, so a client
    built without a policy is read-only. ``WriteGuard`` holds a policy, a ``read`` callable for
    the checks that depend on the service's own state (an issue's labels and whether it is a
    pull request, a run's workflow path, event and head repository, a comment's pull request,
    first line and author; ``read`` returns None when the target cannot be read, and an
    unverifiable write is refused), and the issue numbers and check-run ids THIS client
    created. ``refusal`` returns None for an allowed write, else the reason; it never sends
    anything. Reads are not checked, except that ``path_refusal`` rejects a malformed path
    for every method. Pure logic apart from the injected ``read``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FAMILY_LABELS = frozenset({"post-merge-red", "post-merge-timing", "post-merge-flaky"})
CHECK_NAME = "Post-merge suite status"
MARKER = "<!-- post-merge-suite-status v1 -->"
HOLD_WORKFLOW_PATH = ".github/workflows/post-merge-hold.yml"
HOLD_EVENT = "pull_request_target"
BOT_LOGIN, BOT_TYPE = "github-actions[bot]", "Bot"  # the same pair _hold_comment.find_own matches
ISSUE_PATCH_KEYS = frozenset({"body", "state", "state_reason"})
ISSUE_CREATE_KEYS = frozenset({"title", "body", "labels"})
CHECK_CREATE_KEYS = frozenset({"name", "head_sha", "status"})
CHECK_PATCH_KEYS = frozenset({"status", "conclusion", "output"})
CHECK_CONCLUSIONS = frozenset({"success", "failure"})  # what _hold_publish.conclusion_for can return
TOKEN_KINDS = frozenset({"github", "app_jwt", "app_install"})

_SEG = r"[A-Za-z0-9._-]+"
_REPO_PATH = re.compile(rf"/repos/({_SEG})/({_SEG})(/.*)", re.ASCII)
_EXCHANGE = re.compile(r"/app/installations/[0-9]+/access_tokens", re.ASCII)
_ISSUE = re.compile(r"/issues/([0-9]+)", re.ASCII)
_ISSUE_COMMENTS = re.compile(r"/issues/([0-9]+)/comments", re.ASCII)
_ISSUE_LABELS = re.compile(r"/issues/([0-9]+)/labels", re.ASCII)
_ONE_COMMENT = re.compile(r"/issues/comments/([0-9]+)", re.ASCII)
_RERUN = re.compile(r"/actions/runs/([0-9]+)/rerun", re.ASCII)
_CHECK_RUN = re.compile(r"/check-runs/([0-9]+)", re.ASCII)
_GOOD_PATH = re.compile(r"/[^/@\\][^@\\]*|/", re.ASCII)


@dataclass(frozen=True)
class WritePolicy:
    """What one client may write, on one repository. The default grants nothing: reads only."""

    token_kind: str = "github"  # github | app_jwt | app_install
    repo: str | None = None  # "owner/name": every repository write must be under exactly this
    notices: bool = False  # create, edit, comment on and label the family's notice issues
    notice_comments: bool = False  # comment on a family notice, nothing else (the hold's exemption record)
    pr_comment: int | None = None  # the evaluated pull request, for the hold's marked comment
    rerun_hold: bool = False  # re-run a run of the hold workflow
    check_run_head: str | None = None  # the evaluated head sha, app_install only


def path_refusal(path: str) -> str | None:
    """Why ``path`` is not a plain API path (one leading slash, no ``@``, no backslash), or None."""
    return None if isinstance(path, str) and _GOOD_PATH.fullmatch(path.split("?", 1)[0]) else "a malformed request path"


def _single_family_label(labels) -> bool:
    return isinstance(labels, list) and len(labels) == 1 and isinstance(labels[0], str) and labels[0] in FAMILY_LABELS


def _marked(body) -> bool:
    text = body.get("body") if isinstance(body, dict) else None
    return isinstance(text, str) and text.splitlines()[:1] == [MARKER]


def _keys_within(body, allowed: frozenset) -> bool:
    return isinstance(body, dict) and set(body) <= allowed


class WriteGuard:
    """Applies one ``WritePolicy``; remembers the issues and check runs its client created."""

    def __init__(self, policy: WritePolicy, read) -> None:
        self._policy = policy
        self._read = read
        self._issues: set[int] = set()
        self._checks: set[int] = set()

    def refusal(self, method: str, path: str, body: dict | None) -> str | None:
        """None when ``method path`` is on the list for this policy; otherwise why it is not."""
        if method == "GET":
            return None
        kind, text = self._policy.token_kind, f"{method} {path}"
        if kind not in TOKEN_KINDS:
            return f"{text}: unknown token kind {kind!r}"
        if kind == "app_jwt":
            return None if method == "POST" and _EXCHANGE.fullmatch(path) else f"{text}: the App JWT only exchanges for an installation token"
        found = _REPO_PATH.fullmatch(path)
        if found is None or not self._bound(found.group(1), found.group(2)):
            return f"{text}: not a path under the repository this client is bound to"
        prefix, rest = f"/repos/{found.group(1)}/{found.group(2)}", found.group(3)
        verdict = self._check_run(method, rest, body) if kind == "app_install" else self._github(method, prefix, rest, body)
        return None if verdict is True else f"{text}: {verdict}"

    def record(self, method: str, path: str, response) -> None:
        """Remember an issue number or check-run id the service returned for a write this client made."""
        number = response.get("number" if path.endswith("/issues") else "id") if isinstance(response, dict) else None
        if method != "POST" or not isinstance(number, int):
            return
        if path.endswith("/issues"):
            self._issues.add(number)
        elif path.endswith("/check-runs"):
            self._checks.add(number)

    def _bound(self, owner: str, name: str) -> bool:
        """True when the path's repository is exactly the policy's (and neither segment is ``.`` or ``..``)."""
        if {owner, name} & {".", ".."}:
            return False
        return self._policy.repo is not None and self._policy.repo == f"{owner}/{name}"

    def _check_run(self, method: str, rest: str, body: dict | None):
        policy = self._policy
        if method == "POST" and rest == "/check-runs":
            ok = policy.check_run_head is not None and _keys_within(body, CHECK_CREATE_KEYS) and (body.get("name"), body.get("head_sha")) == (CHECK_NAME, policy.check_run_head)
            return True if ok else "a check run must be named exactly the hold's and sit on the evaluated head"
        found = _CHECK_RUN.fullmatch(rest)
        if method == "PATCH" and found and int(found.group(1)) in self._checks:
            ok = _keys_within(body, CHECK_PATCH_KEYS) and body.get("conclusion", "success") in CHECK_CONCLUSIONS
            return True if ok else "a check run's own completion may carry only status, conclusion (success or failure) and output"
        return "the installation token may only write the hold's own check run"

    def _github(self, method: str, prefix: str, rest: str, body: dict | None):  # noqa: PLR0911 -- one return per rule of the list
        policy = self._policy
        if method == "POST" and rest == "/issues":
            ok = policy.notices and _keys_within(body, ISSUE_CREATE_KEYS) and _single_family_label(body.get("labels"))
            return True if ok else "an issue needs the notices grant, only title, body and labels, and exactly one family label"
        found = _ISSUE.fullmatch(rest)
        if method == "PATCH" and found:
            ok = policy.notices and _keys_within(body, ISSUE_PATCH_KEYS) and self._is_notice(prefix, int(found.group(1)))
            return True if ok else "not an edit (body, state, state_reason) of a family notice"
        found = _ISSUE_COMMENTS.fullmatch(rest)
        if method == "POST" and found:
            return True if self._may_comment(prefix, int(found.group(1)), body) else "not a comment on a notice or the hold's marked comment"
        found = _ISSUE_LABELS.fullmatch(rest)
        if method == "POST" and found:
            ok = policy.notices and int(found.group(1)) in self._issues and _keys_within(body, frozenset({"labels"})) and _single_family_label(body.get("labels"))
            return True if ok else "a label goes only on an issue this client created, and only a family label"
        found = _ONE_COMMENT.fullmatch(rest)
        if method == "PATCH" and found:
            return True if self._is_own_comment(prefix, int(found.group(1)), body) else "not an edit of the hold's own marked comment"
        found = _RERUN.fullmatch(rest)
        if method == "POST" and found:
            return True if policy.rerun_hold and self._is_hold_run(prefix, int(found.group(1))) else "not a re-run of a hold workflow run"
        return "not on the allowed-write list"

    def _may_comment(self, prefix: str, number: int, body) -> bool:
        policy = self._policy
        if not _keys_within(body, frozenset({"body"})):
            return False
        if policy.pr_comment == number and _marked(body):
            return True
        return (policy.notices or policy.notice_comments) and self._is_notice(prefix, number)

    def _is_notice(self, prefix: str, number: int) -> bool:
        """True for an issue this client created, or an issue (never a pull request) whose labels, read first, include a family label."""
        if number in self._issues:
            return True
        issue = self._read(f"{prefix}/issues/{number}")
        if not isinstance(issue, dict) or "pull_request" in issue:
            return False
        names = {item.get("name") if isinstance(item, dict) else item for item in issue.get("labels") or [] if isinstance(item, (dict, str))}
        return any(isinstance(name, str) and name in FAMILY_LABELS for name in names)

    def _is_own_comment(self, prefix: str, comment_id: int, body) -> bool:
        """The hold's comment on the evaluated pull request: marked body, and the comment as it stands (read first) is marked, on that pull request, by the Actions bot."""
        policy = self._policy
        if policy.pr_comment is None or not _keys_within(body, frozenset({"body"})) or not _marked(body):
            return False
        current = self._read(f"{prefix}/issues/comments/{comment_id}")
        if not isinstance(current, dict):
            return False
        user, text, issue_url = current.get("user"), current.get("body"), current.get("issue_url")
        return (
            isinstance(user, dict)
            and (user.get("login"), user.get("type")) == (BOT_LOGIN, BOT_TYPE)
            and isinstance(text, str)
            and text.splitlines()[:1] == [MARKER]
            and isinstance(issue_url, str)
            and issue_url.endswith(f"/issues/{policy.pr_comment}")
        )

    def _is_hold_run(self, prefix: str, run_id: int) -> bool:
        run = self._read(f"{prefix}/actions/runs/{run_id}")
        if not isinstance(run, dict) or run.get("path") != HOLD_WORKFLOW_PATH or run.get("event") != HOLD_EVENT:
            return False
        head = run.get("head_repository")
        return isinstance(head, dict) and head.get("full_name") == self._policy.repo
