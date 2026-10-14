"""
Tests for TQ-600a-13-xi (client half) -- the shared REST client refuses, BEFORE sending, every write that is not on the allowed list.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml (it_requirements 1, 6)

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this) -- scripts/ci/_github_rest.py gains:

  ``WritePolicy`` -- a frozen dataclass of keyword-only fields, EXPLICIT per caller:
      token_kind: "github" (default) | "app_jwt" | "app_install"   which credential this client holds
      notices: bool = False            may write the notice issues (POST /issues with exactly one family label; PATCH, comment on an
                                       issue that carries one; POST /issues/{n}/labels with ONE family label on an issue THIS client created)
      pr_comment: int | None = None    the evaluated pull request: POST /issues/{pr}/comments and PATCH /issues/comments/{id}, body first
                                       line ``<!-- post-merge-suite-status v1 -->``
      rerun_hold: bool = False         with token_kind "app_install" ONLY (AMENDED 2026-10-12, owner decision): POST /actions/runs/{id}/rerun,
                                       after GET /actions/runs/{id} shows ``path`` equals ``.github/workflows/post-merge-hold.yml``,
                                       ``event`` equals ``pull_request_target`` and ``head_repository`` is this repository. The
                                       GITHUB_TOKEN ("github") is refused for EVERY re-run, whatever this flag says.
      check_run_head: str | None = None   the evaluated head sha: with token_kind "app_install" only, POST /check-runs named exactly
                                       ``Post-merge suite status`` on that sha, PATCH /check-runs/{id} for an id this client created
  ``GitHubClient(api_url, token, timeout=..., policy=WritePolicy())`` -- the default policy grants nothing: a client built without one
  is READ-ONLY (reads are unrestricted). ``app_jwt`` clients may only POST /app/installations/{id}/access_tokens, for exactly
  ``{checks: write}`` (the hold) or ``{actions: write}`` (the re-evaluation) on this repository only; ``app_install`` clients may write
  a check run (``check_run_head`` set) OR re-run a hold run (``rerun_hold`` set), NEVER both in one client (a client holding both is
  refused everything); ``github`` clients never write check runs and never re-run.
  A write outside the policy raises ``GitHubError`` with ``kind == "refused"`` (``"refused"`` joins ``KINDS``) BEFORE any request is sent.
  Before a write that depends on the service's own state the client reads it: ``GET /repos/{repo}/issues/{n}`` (labels) and
  ``GET /repos/{repo}/actions/runs/{id}`` (``path``); a read that fails refuses the write (an unverifiable write is not on the list).
"""

from __future__ import annotations

import dataclasses
import unittest

from ._ending_harness import CHECK, Cases
from ._notice_fakes import REPO, import_production
from ._xi_service import RecordingService
from ._xi_support import CHECK_NAME, MARKER

PR, HEAD, OTHER_HEAD = 42, "9" * 40, "8" * 40
R = f"/repos/{REPO}"
MARKED = {"body": f"{MARKER}\n\nthe hold's comment"}
ISSUES = {7: ["bug"], 8: ["post-merge-red"], 9: ["post-merge-timing"], 10: ["post-merge-flaky"], 11: ["bug", "post-merge-red"]}
RUNS = {
    300: ".github/workflows/ci.yml",
    301: ".github/workflows/post-merge-suite.yml",
    302: ".github/workflows/post-merge-hold.yml",
    303: ".github/workflows/not-post-merge-hold.yml",
    304: ".github/workflows/post-merge-hold.yml.old",
    305: ".github/workflows/post-merge-hold.yml",  # run of the hold, but of a pull_request event (see RUN_META)
    306: ".github/workflows/post-merge-hold.yml",  # run of the hold, but from a fork (see RUN_META)
}
RUN_META = {305: {"event": "pull_request"}, 306: {"head_repository": {"full_name": "fork/leafcutter-ai"}}}
ISSUES[12] = ["post-merge-red"]  # a PULL REQUEST that carries the label (see PULLS)
PULLS = {12}
BOT = {"login": "github-actions[bot]", "type": "Bot"}
COMMENTS = {  # comment id -> what the service holds: only 9001 is the hold's own comment on the evaluated pull request
    9001: {"issue_url": f"https://api.example/repos/{REPO}/issues/{PR}", "body": f"{MARKER}\n\nheld", "user": BOT},
    9002: {"issue_url": f"https://api.example/repos/{REPO}/issues/{PR + 1}", "body": f"{MARKER}\n\nheld", "user": BOT},
    9003: {"issue_url": f"https://api.example/repos/{REPO}/issues/{PR}", "body": "someone else's words", "user": BOT},
    9004: {"issue_url": f"https://api.example/repos/{REPO}/issues/{PR}", "body": f"{MARKER}\n\nheld", "user": {"login": "mallory", "type": "User"}},
}
MAX = {"notices": True, "pr_comment": PR, "rerun_hold": True, "check_run_head": HEAD}  # every grant on: refusals below are the LIST's, not a missing grant
NAME = REPO.split("/")[1]
EXCHANGE_CHECKS = {"permissions": {"checks": "write"}, "repositories": [NAME]}
EXCHANGE_ACTIONS = {"permissions": {"actions": "write"}, "repositories": [NAME]}


def rest():
    return import_production("scripts.ci._github_rest")


def make_client(url, token_kind="github", **grants):
    """A client with an explicit policy; against a module without ``WritePolicy`` yet, the legacy client (so the rows fail on behaviour)."""
    module = rest()
    policy_cls = getattr(module, "WritePolicy", None)
    if policy_cls is None:
        return module.GitHubClient(url, "fake-token")
    known = {f.name for f in dataclasses.fields(policy_cls)}
    return module.GitHubClient(url, "fake-token", policy=policy_cls(token_kind=token_kind, **{k: v for k, v in {"repo": REPO, **grants}.items() if k in known}))  # an unknown grant is dropped, so its rows fail on behaviour


def accepted_rows():
    """``(client kind, label, call)`` for every write the list allows; each must reach the server."""
    gh, app, jwt = "gh", "app", "jwt"
    rows = []
    for label in ("post-merge-red", "post-merge-timing", "post-merge-flaky"):
        rows.append((gh, f"create a notice labelled {label}", lambda c, label=label: c.post(f"{R}/issues", {"title": "t", "body": "b", "labels": [label]})))
    rows += [
        (gh, "edit a labelled notice (body, state, reason)", lambda c: c.patch(f"{R}/issues/8", {"body": "x", "state": "closed", "state_reason": "duplicate"})),
        (gh, "edit a notice that carries the label among others", lambda c: c.patch(f"{R}/issues/11", {"body": "x"})),
        *((gh, f"comment on notice #{n}", lambda c, n=n: c.post(f"{R}/issues/{n}/comments", {"body": "c"})) for n in (8, 9, 10, 11)),
        (gh, "the hold's marked comment on the evaluated pull request: create", lambda c: c.post(f"{R}/issues/{PR}/comments", MARKED)),
        (gh, "the hold's marked comment: edit", lambda c: c.patch(f"{R}/issues/comments/9001", MARKED)),
        ("rerun", "AMENDED 2026-10-12: the App re-run token re-runs a pull_request_target run of the hold workflow", lambda c: c.post(f"{R}/actions/runs/302/rerun", {})),
        (app, "create `Post-merge suite status` on the evaluated head", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD, "status": "in_progress"})),
        ("jwt_checks", "the hold's credential exchange: checks write, this repository only", lambda c: c.post("/app/installations/777/access_tokens", EXCHANGE_CHECKS)),
        (jwt, "the re-evaluation's credential exchange: actions write, this repository only", lambda c: c.post("/app/installations/777/access_tokens", EXCHANGE_ACTIONS)),
        ("hold", "the hold's exemption record: a comment on a notice", lambda c: c.post(f"{R}/issues/8/comments", {"body": "recorded"})),
    ]
    return rows


def refused_rows():
    """``(client kind, label, call, kind of refusal or None)`` for writes outside the list; none may reach the server."""
    gh, app, jwt = "gh", "app", "jwt"
    unverifiable = None  # the read that would verify the write fails: refused, whatever the error's kind
    return [
        (gh, "create a pull request", lambda c: c.post(f"{R}/pulls", {"title": "fix", "head": "fix", "base": "main"}), "refused"),
        (gh, "update a ref", lambda c: c.patch(f"{R}/git/refs/heads/main", {"sha": HEAD}), "refused"),
        (gh, "create a ref", lambda c: c.post(f"{R}/git/refs", {"ref": "refs/heads/x", "sha": HEAD}), "refused"),
        (gh, "put contents", lambda c: c.request("PUT", f"{R}/contents/README.md", {"message": "m", "content": "eA=="}), "refused"),
        (gh, "merge a pull request", lambda c: c.request("PUT", f"{R}/pulls/5/merge", {}), "refused"),
        (gh, "review a pull request", lambda c: c.post(f"{R}/pulls/5/reviews", {"event": "APPROVE"}), "refused"),
        (gh, "update a pull request", lambda c: c.patch(f"{R}/pulls/5", {"state": "closed"}), "refused"),
        (gh, "delete a tag", lambda c: c.request("DELETE", f"{R}/git/refs/tags/v1", None), "refused"),
        (gh, "comment on an UNLABELLED issue (comments as a class)", lambda c: c.post(f"{R}/issues/7/comments", {"body": "c"}), "refused"),
        (gh, "edit an unlabelled issue", lambda c: c.patch(f"{R}/issues/7", {"state": "closed"}), "refused"),
        (gh, "comment on an issue that does not exist", lambda c: c.post(f"{R}/issues/999/comments", {"body": "c"}), unverifiable),
        (gh, "create a label", lambda c: c.post(f"{R}/labels", {"name": "post-merge-red"}), "refused"),
        (gh, "label ANOTHER issue", lambda c: c.post(f"{R}/issues/7/labels", {"labels": ["post-merge-red"]}), "refused"),
        (gh, "label a notice the client did not create", lambda c: c.post(f"{R}/issues/8/labels", {"labels": ["bug"]}), "refused"),
        (gh, "create an issue with no label", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": []}), "refused"),
        (gh, "create an issue with another label", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["bug"]}), "refused"),
        (gh, "create an issue with two family labels", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red", "post-merge-flaky"]}), "refused"),
        (gh, "comment on another pull request, marker present", lambda c: c.post(f"{R}/issues/{PR + 1}/comments", MARKED), "refused"),
        (gh, "comment on the evaluated pull request WITHOUT the marker", lambda c: c.post(f"{R}/issues/{PR}/comments", {"body": "hello"}), "refused"),
        (gh, "edit a comment WITHOUT the marker", lambda c: c.patch(f"{R}/issues/comments/9001", {"body": "hello"}), "refused"),
        (gh, "re-run a run of ci.yml (re-runs as a class)", lambda c: c.post(f"{R}/actions/runs/300/rerun", {}), "refused"),
        (gh, "re-run a run of the suite workflow", lambda c: c.post(f"{R}/actions/runs/301/rerun", {}), "refused"),
        (gh, "re-run a run whose workflow name merely ENDS like the hold's", lambda c: c.post(f"{R}/actions/runs/303/rerun", {}), "refused"),
        (gh, "re-run a run whose workflow name merely STARTS like the hold's", lambda c: c.post(f"{R}/actions/runs/304/rerun", {}), "refused"),
        (gh, "re-run a run that does not exist", lambda c: c.post(f"{R}/actions/runs/999/rerun", {}), unverifiable),
        (gh, "re-run only the failed jobs of a hold run (a different endpoint)", lambda c: c.post(f"{R}/actions/runs/302/rerun-failed-jobs", {}), "refused"),
        (gh, "dispatch a workflow", lambda c: c.post(f"{R}/actions/workflows/ci.yml/dispatches", {"ref": "main"}), "refused"),
        (gh, "disable a workflow", lambda c: c.request("PUT", f"{R}/actions/workflows/ci.yml/disable", None), "refused"),
        (gh, "enable a workflow", lambda c: c.request("PUT", f"{R}/actions/workflows/ci.yml/enable", None), "refused"),
        (gh, "cancel a run", lambda c: c.post(f"{R}/actions/runs/302/cancel", {}), "refused"),
        (gh, "post a commit status", lambda c: c.post(f"{R}/statuses/{HEAD}", {"state": "success", "context": "x"}), "refused"),
        (gh, "create a release", lambda c: c.post(f"{R}/releases", {"tag_name": "v1"}), "refused"),
        (gh, "post the check run with the GITHUB_TOKEN", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD}), "refused"),
        (app, "check run under another name", lambda c: c.post(f"{R}/check-runs", {"name": "Other check", "head_sha": HEAD}), "refused"),
        (app, "check run on another sha", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": OTHER_HEAD}), "refused"),
        (app, "complete a check run this client did not create", lambda c: c.patch(f"{R}/check-runs/5001", {"status": "completed"}), "refused"),
        (app, "the App token for an issue comment", lambda c: c.post(f"{R}/issues/8/comments", {"body": "c"}), "refused"),
        (app, "the App token for the hold's comment", lambda c: c.post(f"{R}/issues/{PR}/comments", MARKED), "refused"),
        (app, "the App token to create an issue", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}), "refused"),
        (app, "the App token to edit an issue", lambda c: c.patch(f"{R}/issues/8", {"body": "x"}), "refused"),
        (app, "the App token for a re-run", lambda c: c.post(f"{R}/actions/runs/302/rerun", {}), "refused"),
        (app, "the App token for a commit status", lambda c: c.post(f"{R}/statuses/{HEAD}", {"state": "success"}), "refused"),
        (app, "the installation token at the credential exchange", lambda c: c.post("/app/installations/777/access_tokens", {}), "refused"),
        # AMENDED 2026-10-12: the GITHUB_TOKEN requests no re-run at all; the App's installation token requests only one kind
        (gh, "AMENDED: the GITHUB_TOKEN re-runs a pull_request_target run of the hold workflow (rerun_hold is honoured only for app_install)", lambda c: c.post(f"{R}/actions/runs/302/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a run of ci.yml", lambda c: c.post(f"{R}/actions/runs/300/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a run of the suite workflow", lambda c: c.post(f"{R}/actions/runs/301/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a run whose workflow name merely ENDS like the hold's", lambda c: c.post(f"{R}/actions/runs/303/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a run whose workflow name merely STARTS like the hold's", lambda c: c.post(f"{R}/actions/runs/304/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a hold run of a pull_request event", lambda c: c.post(f"{R}/actions/runs/305/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a hold run from a fork", lambda c: c.post(f"{R}/actions/runs/306/rerun", {}), "refused"),
        ("rerun", "the App re-run token re-runs a run that does not exist", lambda c: c.post(f"{R}/actions/runs/999/rerun", {}), unverifiable),
        ("rerun", "the App re-run token re-runs with debug logging switched on", lambda c: c.post(f"{R}/actions/runs/302/rerun", {"enable_debug_logging": True}), "refused"),
        ("rerun", "the App re-run token re-runs only the failed jobs of a hold run", lambda c: c.post(f"{R}/actions/runs/302/rerun-failed-jobs", {}), "refused"),
        ("rerun", "the App re-run token cancels a hold run", lambda c: c.post(f"{R}/actions/runs/302/cancel", {}), "refused"),
        ("rerun", "the App re-run token dispatches a workflow", lambda c: c.post(f"{R}/actions/workflows/post-merge-hold.yml/dispatches", {"ref": "main"}), "refused"),
        ("rerun", "the App re-run token disables a workflow", lambda c: c.request("PUT", f"{R}/actions/workflows/ci.yml/disable", None), "refused"),
        ("rerun", "the App re-run token re-runs a hold run of ANOTHER repository", lambda c: c.post("/repos/evil/other/actions/runs/302/rerun", {}), "refused"),
        ("rerun", "the App re-run token creates the hold's check run", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD, "status": "in_progress"}), "refused"),
        ("rerun", "the App re-run token completes a check run", lambda c: c.patch(f"{R}/check-runs/5001", {"status": "completed", "conclusion": "success"}), "refused"),
        ("rerun", "the App re-run token comments on a notice", lambda c: c.post(f"{R}/issues/8/comments", {"body": "c"}), "refused"),
        ("rerun", "the App re-run token writes an issue", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}), "refused"),
        # a client must not be allowed both: an installation client holding both grants is refused everything, either write
        ("both", "an App client holding BOTH grants: the re-run", lambda c: c.post(f"{R}/actions/runs/302/rerun", {}), "refused"),
        ("both", "an App client holding BOTH grants: the check-run create", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD, "status": "in_progress"}), "refused"),
        # the exchange is bounded to the two permission sets actually requested, on this repository only
        (jwt, "an exchange with no permissions", lambda c: c.post("/app/installations/777/access_tokens", {"repositories": [NAME]}), "refused"),
        (jwt, "an exchange asking for BOTH checks and actions", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"checks": "write", "actions": "write"}, "repositories": [NAME]}), "refused"),
        (jwt, "an exchange asking for actions: read", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "read"}, "repositories": [NAME]}), "refused"),
        (jwt, "an exchange asking for contents: write", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"contents": "write"}, "repositories": [NAME]}), "refused"),
        (jwt, "an exchange asking for actions: write AND contents: write", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "write", "contents": "write"}, "repositories": [NAME]}), "refused"),
        (jwt, "an exchange with no repositories (every repository of the installation)", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "write"}}), "refused"),
        (jwt, "an exchange for ANOTHER repository", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "write"}, "repositories": ["other"]}), "refused"),
        (jwt, "an exchange for this repository AND another", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "write"}, "repositories": [NAME, "other"]}), "refused"),
        (jwt, "an exchange by repository ids", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": {"actions": "write"}, "repository_ids": [1]}), "refused"),
        (jwt, "an exchange by repository ids beside the repository", lambda c: c.post("/app/installations/777/access_tokens", {**EXCHANGE_ACTIONS, "repository_ids": [1]}), "refused"),
        (jwt, "an exchange carrying a field beyond permissions and repositories", lambda c: c.post("/app/installations/777/access_tokens", {**EXCHANGE_ACTIONS, "extra": 1}), "refused"),
        (jwt, "an exchange whose permissions are not a mapping", lambda c: c.post("/app/installations/777/access_tokens", {"permissions": ["actions"], "repositories": [NAME]}), "refused"),
        (jwt, "the App's JWT for an issue comment", lambda c: c.post(f"{R}/issues/8/comments", {"body": "c"}), "refused"),
        (jwt, "the App's JWT for a check run", lambda c: c.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD}), "refused"),
        ("none", "a client built with no policy: a notice create", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}), "refused"),
        ("reeval", "the re-evaluation's grant is not an issue comment", lambda c: c.post(f"{R}/issues/8/comments", {"body": "c"}), "refused"),
        ("notice", "the notice's grant is not a re-run of the hold", lambda c: c.post(f"{R}/actions/runs/302/rerun", {}), "refused"),
        ("notice", "the notice's grant is not the hold's pull request comment", lambda c: c.post(f"{R}/issues/{PR}/comments", MARKED), "refused"),
        # H-2: the hold's comment edit is tied to the hold's OWN comment, read first
        (gh, "edit a marked comment that sits on ANOTHER pull request", lambda c: c.patch(f"{R}/issues/comments/9002", MARKED), "refused"),
        (gh, "edit a comment whose CURRENT first line is not the marker", lambda c: c.patch(f"{R}/issues/comments/9003", MARKED), "refused"),
        (gh, "edit a comment written by another user", lambda c: c.patch(f"{R}/issues/comments/9004", MARKED), "refused"),
        (gh, "edit a comment that cannot be read", lambda c: c.patch(f"{R}/issues/comments/9999", MARKED), unverifiable),
        # H-3: a pull request that carries the label is not a notice
        (gh, "close a pull request that carries the family label", lambda c: c.patch(f"{R}/issues/12", {"state": "closed"}), "refused"),
        (gh, "comment on a pull request that carries the family label", lambda c: c.post(f"{R}/issues/12/comments", {"body": "c"}), "refused"),
        # M-1: the policy is bound to its repository
        # (the hold's marked comment on the evaluated PR number needs no read, so only the repository binding can refuse these)
        (gh, "a write to another repository", lambda c: c.post(f"/repos/evil/other/issues/{PR}/comments", MARKED), "refused"),
        (gh, "a write to an owner named '..'", lambda c: c.post(f"/repos/../{REPO.split('/')[1]}/issues/{PR}/comments", MARKED), "refused"),
        (gh, "a write to a repository named '.'", lambda c: c.post(f"/repos/{REPO.split('/')[0]}/./issues/{PR}/comments", MARKED), "refused"),
        ("norepo", "a client bound to no repository", lambda c: c.post(f"{R}/issues/{PR}/comments", MARKED), "refused"),
        # M-2: the hold's grant is comment-only on notices
        ("hold", "the hold creating a notice", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}), "refused"),
        ("hold", "the hold editing a notice", lambda c: c.patch(f"{R}/issues/8", {"state": "closed"}), "refused"),
        ("hold", "the hold re-running a run", lambda c: c.post(f"{R}/actions/runs/302/rerun", {}), "refused"),
        # M-3: a re-run needs the hold's pull_request_target event, from this repository
        (gh, "re-run a hold run of a pull_request event", lambda c: c.post(f"{R}/actions/runs/305/rerun", {}), "refused"),
        (gh, "re-run a hold run from a fork", lambda c: c.post(f"{R}/actions/runs/306/rerun", {}), "refused"),
        # M-4 and L-3: the bodies are bounded too
        (gh, "create a notice with extra fields (assignees)", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"], "assignees": ["x"]}), "refused"),
        (gh, "create a notice with a milestone", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"], "milestone": 1}), "refused"),
        (gh, "edit a notice's labels", lambda c: c.patch(f"{R}/issues/8", {"labels": ["bug"]}), "refused"),
        (gh, "edit a notice's title", lambda c: c.patch(f"{R}/issues/8", {"title": "renamed"}), "refused"),
        ("weird", "a client with an unknown token kind", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}), "refused"),
        # L-1: a label that is not a string is a refusal, never a TypeError
        (gh, "create a notice whose label is a list", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": [["post-merge-red"]]}), "refused"),
        (gh, "create a notice whose label is a dict", lambda c: c.post(f"{R}/issues", {"title": "t", "labels": [{"a": 1}]}), "refused"),
    ]


class TestTq600a13XiClientAllowlist(unittest.TestCase):
    def setUp(self):
        self.svc = RecordingService()
        self.addCleanup(self.svc.close)
        self.svc.issues, self.svc.runs = dict(ISSUES), dict(RUNS)
        self.svc.pulls, self.svc.run_meta, self.svc.comments = set(PULLS), dict(RUN_META), dict(COMMENTS)
        self.clients = {
            "hold": make_client(self.svc.url, notice_comments=True, pr_comment=PR),
            "norepo": make_client(self.svc.url, repo=None, **MAX),
            "weird": make_client(self.svc.url, "admin", **MAX),
            "gh": make_client(self.svc.url, **MAX),
            "app": make_client(self.svc.url, "app_install", check_run_head=HEAD),  # the hold's: check runs, no re-run grant
            "rerun": make_client(self.svc.url, "app_install", rerun_hold=True),  # the re-evaluation's: re-runs, no check-run grant
            "both": make_client(self.svc.url, "app_install", rerun_hold=True, check_run_head=HEAD),  # never allowed
            "jwt": make_client(self.svc.url, "app_jwt", exchange_permission="actions"),  # the re-evaluation's minting client
            "jwt_checks": make_client(self.svc.url, "app_jwt", exchange_permission="checks"),  # the hold's minting client
            "none": rest().GitHubClient(self.svc.url, "fake-token"),
            "reeval": make_client(self.svc.url, rerun_hold=True),  # the OLD re-evaluation grant on the GITHUB_TOKEN: honoured for nothing now
            "notice": make_client(self.svc.url, notices=True),
        }

    def test_tq600a_13_xi_the_client_refuses_a_write_outside_the_list(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """Ask the client for each write the list forbids and each it allows, against a server that ACCEPTS everything it receives.

        Rows: every forbidden write raises ``GitHubError`` (kind ``refused``) and the server records NONE of them; every allowed
        write reaches the server (the control rows: they pass for the opposite reason, so a client that refuses everything fails);
        the server's recorded writes equal the allowed rows, in order, exactly.

        Wrong versions caught (each needs its own row to stay green): the allowlist checked AFTER the request is sent (the server
        records the write); the allowlist matching by method only (POST /pulls beside POST /issues); a comment on an unlabelled issue
        allowed because comments are; a re-run of ci.yml, of the suite, or of a run whose workflow name merely ends or starts like
        the hold's; a dispatch, disable, enable or cancel allowed because the job holds ``actions: write``; a check run allowed
        because check runs are, for the GITHUB_TOKEN or under another name or on another sha; the App token accepted for an issue
        or a comment, or for a re-run of anything but a pull_request_target hold run of this repository (AMENDED 2026-10-12); the
        GITHUB_TOKEN accepted for ANY re-run, even with ``rerun_hold`` set; an App client holding both a re-run and a check-run grant
        accepted for either; a credential exchange for more than ``{checks: write}`` / ``{actions: write}`` or for more than this
        repository; a client without a policy that writes; a grant wider than its caller needs.
        """
        cases = Cases()
        with cases.case("the policy interface exists"):
            CHECK.assertTrue(hasattr(rest(), "WritePolicy"), "scripts/ci/_github_rest.py has no WritePolicy yet")
        for kind, label, call in accepted_rows():
            with cases.case(f"allowed: {label}"):
                call(self.clients[kind])
        allowed = self.svc.writes()
        with cases.case("every allowed write reached the server once"):
            CHECK.assertEqual(len(accepted_rows()), len(allowed), allowed)
        for kind, label, call, refusal in refused_rows():
            before = self.svc.writes()
            with cases.case(f"refused: {label}"):
                with self.assertRaises(rest().GitHubError) as caught:
                    call(self.clients[kind])
                if refusal:
                    CHECK.assertEqual(refusal, caught.exception.kind)
            with cases.case(f"refused, and never sent: {label}"):
                CHECK.assertEqual(before, self.svc.writes())
        with cases.case("the server recorded exactly the allowed writes, in order, and nothing else"):
            CHECK.assertEqual(allowed, self.svc.writes())
        cases.check()

    def test_tq600a_13_xi_the_completion_of_the_apps_check_run_is_accepted_only_for_its_own_run(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """The App's create of `Post-merge suite status` on the evaluated head and its completion are accepted; a completion of any
        other check run is refused. Wrong version caught: ``PATCH /check-runs/{id}`` allowed for any id once the App token is held."""
        client, cases = make_client(self.svc.url, "app_install", check_run_head=HEAD), Cases()
        created = {}
        with cases.case("create on the evaluated head is accepted"):
            created.update(client.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD, "status": "in_progress"}) or {})
        with cases.case("completing the run this client created is accepted"):
            client.patch(f"{R}/check-runs/{created.get('id')}", {"status": "completed", "conclusion": "success"})
        with cases.case("completing another run is refused and not sent"):
            before = self.svc.writes()
            with self.assertRaises(rest().GitHubError):
                client.patch(f"{R}/check-runs/{(created.get('id') or 0) + 1}", {"status": "completed", "conclusion": "success"})
            CHECK.assertEqual(before, self.svc.writes())
        with cases.case("the server saw one create and one completion"):
            CHECK.assertEqual(["POST", "PATCH"], [m for m, _ in self.svc.writes()])
        cases.check()

    def test_tq600a_13_xi_the_apps_own_check_run_may_only_be_completed_never_rewritten(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """H-1. A PATCH of the client's own check run is checked by its body: only ``status``, ``conclusion`` (what the hold
        publishes: success or failure) and ``output`` may be sent; a rename (to a name another required check owns), a new
        ``head_sha`` or a conclusion the hold never publishes is refused and never sent. Control: the completion the hold sends."""
        client, cases = make_client(self.svc.url, "app_install", check_run_head=HEAD), Cases()
        created = {}
        with cases.case("create on the evaluated head is accepted"):
            created.update(client.post(f"{R}/check-runs", {"name": CHECK_NAME, "head_sha": HEAD, "status": "in_progress"}) or {})
        path = f"{R}/check-runs/{created.get('id')}"
        for label, body in (
            ("a rename to another check's name with conclusion success", {"name": "Lint (ruff)", "conclusion": "success", "status": "completed"}),
            ("a move to another head", {"head_sha": OTHER_HEAD, "status": "completed"}),
            ("a conclusion the hold never publishes", {"status": "completed", "conclusion": "neutral"}),
            ("a create-only field", {"status": "completed", "conclusion": "success", "details_url": "https://evil.example"}),
        ):
            before = self.svc.writes()
            with cases.case(f"refused: {label}"):
                with self.assertRaises(rest().GitHubError) as caught:
                    client.patch(path, body)
                CHECK.assertEqual("refused", caught.exception.kind)
                CHECK.assertEqual(before, self.svc.writes())
        with cases.case("accepted: the completion the hold sends"):
            client.patch(path, {"status": "completed", "conclusion": "failure", "output": {"title": "t", "summary": "s"}})
        with cases.case("the server saw one create and one completion"):
            CHECK.assertEqual(["POST", "PATCH"], [m for m, _ in self.svc.writes()])
        cases.check()

    def test_tq600a_13_xi_a_malformed_path_is_refused_before_it_is_sent(self):
        # covers: TQ-600a-13-xi
        # angle: boundary
        """L-4. A path that does not start with a single slash, or that contains ``@`` or a backslash, is refused for every method
        (a ``//host`` or ``@host`` path can aim the request, and the token, at another origin). Control: a normal read goes through."""
        client, cases = rest().GitHubClient(self.svc.url, "fake-token"), Cases()
        for label, path in (("a double slash", "//evil.example/x"), ("no leading slash", "repos/x"), ("an @", f"{R}/issues/8@evil.example"), ("a backslash", f"{R}\\..\\x")):
            with cases.case(f"refused: {label}"):
                with self.assertRaises(rest().GitHubError) as caught:
                    client.get(path)
                CHECK.assertEqual("refused", caught.exception.kind)
        with cases.case("nothing was sent"):
            CHECK.assertEqual([], self.svc.requests)
        with cases.case("a normal read goes through"):
            client.get(f"{R}/issues/8")
        cases.check()

    def test_tq600a_13_xi_a_notice_created_without_its_label_may_be_labelled_and_closed_by_its_creator(self):
        # covers: TQ-600a-13-xi
        # angle: discrimination
        """The notice job repairs an issue the service created WITHOUT the label (it adds the label, or comments and closes the orphan).

        That is a write to an issue the service does not yet show as a notice, so the list reads "an issue THIS client created". Rows:
        for the number the create returned, adding the family label, commenting and closing are accepted; adding another label is
        refused; adding the label to any other issue is refused. Wrong versions caught: the repair refused (the orphan is invisible to
        every later run); labels allowed on any issue once the client may create notices."""
        self.svc.drop_labels = True
        client, cases = make_client(self.svc.url, notices=True), Cases()
        created = client.post(f"{R}/issues", {"title": "t", "labels": ["post-merge-red"]}) or {}
        number = created.get("number")
        for label, call in (
            ("label the created issue", lambda: client.post(f"{R}/issues/{number}/labels", {"labels": ["post-merge-red"]})),
            ("comment on the created issue", lambda: client.post(f"{R}/issues/{number}/comments", {"body": "orphan"})),
            ("close the created issue", lambda: client.patch(f"{R}/issues/{number}", {"state": "closed", "state_reason": "not_planned"})),
        ):
            with cases.case(f"accepted: {label}"):
                call()
        for label, call in (
            ("add another label to the created issue", lambda: client.post(f"{R}/issues/{number}/labels", {"labels": ["bug"]})),
            ("add the family label to an issue it did not create", lambda: client.post(f"{R}/issues/7/labels", {"labels": ["post-merge-red"]})),
        ):
            before = self.svc.writes()
            with cases.case(f"refused: {label}"):
                with self.assertRaises(rest().GitHubError):
                    call()
                CHECK.assertEqual(before, self.svc.writes())
        with cases.case("the server saw the create and the three accepted repairs"):
            CHECK.assertEqual(4, len(self.svc.writes()), self.svc.writes())
        cases.check()

    def test_tq600a_13_xi_reads_are_unrestricted_for_a_read_only_client(self):
        # covers: TQ-600a-13-xi
        # angle: boundary
        """Reads are not on the list: a client with no grants reads an issue, a run list and a pull request list. Wrong version caught: an
        allowlist that refuses the GETs the whole family depends on (the control for a client that refuses everything)."""
        client, cases = rest().GitHubClient(self.svc.url, "fake-token"), Cases()
        for label, path in (("an issue", f"{R}/issues/8"), ("a run", f"{R}/actions/runs/302"), ("a list", f"{R}/pulls")):
            with cases.case(f"read {label}"):
                client.get(path)
        with cases.case("and no write was recorded"):
            CHECK.assertEqual([], self.svc.writes())
        cases.check()


if __name__ == "__main__":
    unittest.main()
