"""Shared oracle and git snapshot for TQ-600a-13-xi (the allowed-write list). Not a test: underscore-named.

* ``Write`` / ``collect_writes`` -- every write the server SAW, whichever fake of the family recorded it (the comment-aware
  fakes keep PR and notice comments in ``comment_writes``, the App plane in ``log``, the rest in ``write_attempts``).
* ``verdict_on`` -- the TEST'S OWN reading of the AC's list (it does not import the client's allowlist, so a client that
  widens the list cannot widen the oracle with it). ``None`` means allowed; a string names why a write is outside the list.
* ``snapshot`` / ``make_origin`` -- branches, tags, index and working tree of a repository and the refs of its bare origin.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ._notice_fakes import REPO

FAMILY_LABELS = ("post-merge-red", "post-merge-timing", "post-merge-flaky")
CHECK_NAME = "Post-merge suite status"
MARKER = "<!-- post-merge-suite-status v1 -->"
HOLD_RUN_PATH = ".github/workflows/post-merge-hold.yml"
PREFIX = f"/repos/{REPO}"
_ISSUE = re.compile(r"/issues/(\d+)")
_ISSUE_COMMENTS = re.compile(r"/issues/(\d+)/comments")
_ONE_COMMENT = re.compile(r"/issues/comments/(\d+)")
_RERUN = re.compile(r"/actions/runs/(\d+)/rerun")
_CHECK = re.compile(r"/check-runs(?:/(\d+))?")
_EXCHANGE = re.compile(r"/app/installations/\d+/access_tokens")
ISSUE_PATCH_KEYS = {"body", "state", "state_reason"}  # the description, state and reason of AC -xi (no caller edits a title, so a title edit is outside the list)
ISSUE_CREATE_KEYS = {"title", "body", "labels"}  # no assignees, milestone or other field on a created notice
CHECK_PATCH_KEYS = {"status", "conclusion", "output"}  # a check run's completion; never a rename or a new head
COMMENT_KEYS = {"body"}
EXCHANGE_PERMISSIONS = ({"checks": "write"}, {"actions": "write"})  # the only two scopes a token may be minted with: the hold's and the re-evaluation's


@dataclass(frozen=True)
class Write:
    method: str
    path: str
    body: dict | None = None
    auth: str | None = None  # install | jwt | github_token | none | other; None when the fake does not record who authorised it


@dataclass
class World:
    """The context the AC's list is stated against: the issue labels, the evaluated pull request and its head, the hold's runs."""

    labels: dict
    pr: int | None = None
    head: str | None = None
    hold_runs: frozenset = frozenset()


def collect_writes(svc):
    """Every non-GET request the fake recorded, as ``Write`` values."""
    if hasattr(svc, "comment_writes"):  # the comment-aware fakes answer comment paths before ``log``
        verbs = {"create": "POST", "edit": "PATCH", "delete": "DELETE"}
        found = [Write(e["method"], e["path"], e["body"], svc.auth_kind(e)) for e in svc.log if e["method"] != "GET"]
        return found + [Write(verbs.get(w["kind"], w["kind"]), w["path"], {"body": w["body"]}) for w in svc.comment_writes]
    return [Write(a["method"], a["path"], a["body"], a.get("auth")) for a in svc.write_attempts]


def world_of(svc, *, pr=None, head=None, hold_runs=()):
    """The world as the fake holds it after a path ran (issue labels are read from the fake's own state)."""
    issues = {n: i for n, i in getattr(svc, "issues", {}).items() if not i.get("pull_request")}  # a pull request is never a notice
    return World({n: list(i["labels"]) for n, i in issues.items()}, pr, head, frozenset(hold_runs))


def _single_family_label(labels):
    return isinstance(labels, list) and len(labels) == 1 and labels[0] in FAMILY_LABELS


def _marked(body):
    return isinstance(body, dict) and isinstance(body.get("body"), str) and body["body"].splitlines()[:1] == [MARKER]


_NOT_THIS_RULE = object()  # a rule's "this write is not mine": the next rule of the list is tried


def _rule_issue_create(write, rest, body, world):
    if not (write.method == "POST" and rest == "/issues"):
        return _NOT_THIS_RULE
    if not set(body) <= ISSUE_CREATE_KEYS:
        return f"issue created with fields {sorted(set(body) - ISSUE_CREATE_KEYS)} beyond title, body and labels"
    return None if _single_family_label(body.get("labels")) else f"issue created with labels {body.get('labels')!r}"


def _rule_issue_edit(write, rest, body, world):
    match = _ISSUE.fullmatch(rest)
    if not (write.method == "PATCH" and match):
        return _NOT_THIS_RULE
    labelled = bool(set(world.labels.get(int(match.group(1)), [])) & set(FAMILY_LABELS))
    return None if labelled and set(body) <= ISSUE_PATCH_KEYS else f"PATCH #{match.group(1)} (labelled: {labelled}, keys {sorted(body)})"


def _rule_comment_create(write, rest, body, world):
    match = _ISSUE_COMMENTS.fullmatch(rest)
    if not (write.method == "POST" and match):
        return _NOT_THIS_RULE
    number = int(match.group(1))
    if not set(body) <= COMMENT_KEYS:
        return f"comment on #{number} carrying fields {sorted(set(body) - COMMENT_KEYS)}"
    if world.labels.get(number) and set(world.labels[number]) & set(FAMILY_LABELS):
        return None
    return None if number == world.pr and _marked(body) else f"comment on #{number}, which is neither a notice nor the evaluated pull request's marked comment"


def _rule_comment_edit(write, rest, body, world):
    if not (write.method == "PATCH" and _ONE_COMMENT.fullmatch(rest)):
        return _NOT_THIS_RULE
    # whether the comment is the hold's OWN (its pull request, its author) is a read the client makes; a write cannot show it
    return None if world.pr is not None and _marked(body) and set(body) <= COMMENT_KEYS else "comment edit that is not the hold's marked comment"


def _rule_rerun(write, rest, body, world):
    match = _RERUN.fullmatch(rest)
    if not (write.method == "POST" and match):
        return _NOT_THIS_RULE
    # AMENDED 2026-10-12: a re-run is the App installation token's alone (the GITHUB_TOKEN requests none), of a pull_request_target run of the hold
    if write.auth != "install":
        return f"re-run of run {match.group(1)} requested with the {write.auth or 'unrecorded'} credential, not the App's installation token"
    return None if int(match.group(1)) in world.hold_runs else f"re-run of run {match.group(1)}, which is not a pull_request_target run of the hold workflow"


def _rule_check_run(write, rest, body, world):
    if not (write.method in ("POST", "PATCH") and _CHECK.fullmatch(rest)):
        return _NOT_THIS_RULE
    if write.auth != "install":
        return f"check run written with the {write.auth or 'unrecorded'} credential"
    if write.method == "POST" and (body.get("name"), body.get("head_sha")) != (CHECK_NAME, world.head):
        return f"check run {body.get('name')!r} on {body.get('head_sha')!r}"
    if write.method == "PATCH" and (not set(body) <= CHECK_PATCH_KEYS or body.get("conclusion", "success") not in ("success", "failure")):
        return f"check run completion with {sorted(body)} / conclusion {body.get('conclusion')!r}"
    return None


def _rule_exchange(write, rest, body, world):
    if not (write.method == "POST" and _EXCHANGE.fullmatch(rest)):
        return _NOT_THIS_RULE
    if write.auth != "jwt":
        return "the App credential exchange without the App's JWT"
    # the token is asked for one permission only (the hold's check runs, the re-evaluation's re-runs), on this repository only
    asked = (body.get("permissions"), body.get("repositories"), sorted(set(body) - {"permissions", "repositories"}))
    return None if asked[0] in EXCHANGE_PERMISSIONS and asked[1] == [REPO.split("/", 1)[1]] and not asked[2] else f"the exchange asks for {body!r}"


_RULES = (_rule_issue_create, _rule_issue_edit, _rule_comment_create, _rule_comment_edit, _rule_rerun, _rule_check_run, _rule_exchange)


def verdict_on(write, world):
    """None when ``write`` is on the AC's list for ``world``; otherwise the reason it is not."""
    if not write.path.startswith(PREFIX) and not _EXCHANGE.fullmatch(write.path):
        return f"{write.method} {write.path}: not under this repository"
    rest, body = write.path[len(PREFIX) :] if write.path.startswith(PREFIX) else write.path, write.body or {}
    for rule in _RULES:
        verdict = rule(write, rest, body, world)
        if verdict is not _NOT_THIS_RULE:
            return verdict
    return f"{write.method} {rest}"


def category_of(write):
    """A short name for an allowed write, so a test can show that every kind of allowed write was exercised."""
    rest = write.path[len(PREFIX) :] if write.path.startswith(PREFIX) else write.path
    if rest == "/issues":
        return "issue-create"
    if _ISSUE.fullmatch(rest):
        return "issue-edit"
    if _ISSUE_COMMENTS.fullmatch(rest):
        return "comment-create"
    if _ONE_COMMENT.fullmatch(rest):
        return "comment-edit"
    if _RERUN.fullmatch(rest):
        return "hold-rerun"
    if _CHECK.fullmatch(rest):
        return "check-create" if write.method == "POST" else "check-complete"
    return "exchange" if _EXCHANGE.fullmatch(rest) else "other"


# --------------------------------------------------------------------------- git
def git(path, *args):
    """Run git in ``path``; a failure is a broken test, never a silent pass."""
    argv = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args]
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=30).stdout  # noqa: S603
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        message = f"git {args} failed in {path}: {exc}"
        raise AssertionError(message) from exc


def make_origin(repo_path, bare_path):
    """Give the scratch repository a LOCAL BARE origin (a clone of itself) and fetch it, so ``origin/*`` exist."""
    git(repo_path, "clone", "-q", "--bare", str(repo_path), str(bare_path))
    git(repo_path, "remote", "add", "origin", str(bare_path))
    git(repo_path, "fetch", "-q", "origin")
    return Path(bare_path)


def snapshot(repo_path, origin_path, *, untracked=True):
    """Branches, tags (every ref), HEAD, index, working tree status and the origin's refs, as comparable text.

    ``untracked=False`` leaves files git does not track out of the status: a job workspace legitimately gains the downloaded
    artifact, which is not "a file tracked by the repository".
    """
    refs = "%(refname) %(objectname)"
    return {
        "refs": git(repo_path, "for-each-ref", f"--format={refs}"),
        "head": git(repo_path, "rev-parse", "HEAD"),
        "index": git(repo_path, "ls-files", "-s"),
        "status": git(repo_path, "status", "--porcelain", f"--untracked-files={'all' if untracked else 'no'}"),
        "origin_refs": git(origin_path, "for-each-ref", f"--format={refs}"),
    }


def changed(before, after):
    """The snapshot parts that differ, named."""
    return sorted(name for name in before if before[name] != after[name])
