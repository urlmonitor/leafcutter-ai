"""
MODULE: _hold_publish
GOAL: Publish the hold's verdict as the check run `Post-merge suite status`, created by
    the dedicated hold GitHub App on the pull request's head commit.
BUSINESS CONTEXT: TQ-600a-13-vi (App publication clauses). A required check that the
    workflow's own GITHUB_TOKEN can write is a check any workflow in the repository can
    also write; the App's installation token is the one credential only this job holds.
    The run is created in progress BEFORE the verdict is computed and completed after
    it, so a crash or a refused completion leaves the required check pending (not
    green) instead of absent or stale. Every failure fails the job and names its stage.
ARCHITECTURE: ``publish(read_client, api_url, repo, pr_number, head_sha, evaluate)`` is the
    whole flow; each stage raises ``PublishError`` carrying the line to print.
    1. A prior App verdict on the head (a check run of that exact name whose ``app.id``
       equals the configured ``HOLD_APP_ID``) is looked up first, with the GITHUB_TOKEN,
       so a failed refresh can say it left that earlier verdict standing.
    2. The workflow step signs the App's RS256 JWT with openssl (the key lives only in an
       unexported shell variable and is read through a process substitution, never a
       file) and pipes the JWT on stdin (``main`` reads it once and passes ``jwt=``); the
       environment carries only ``HOLD_APP_KEY_SET``. The JWT authorises only
       ``GET /repos/{repo}/installation`` and the ``access_tokens`` exchange, which asks
       for ``checks: write`` on this repository alone.
    3. The installation token authorises only ``POST /repos/{repo}/check-runs`` and
       ``PATCH /repos/{repo}/check-runs/{id}``. Every read and the pull request comment
       use ``read_client`` (the GITHUB_TOKEN). The key, the JWT and the token are never
       printed, logged or put in an exception message.
    ``conclusion_for(verdict)`` is ``success`` only for ``pass`` or ``exempt``.
    TRUST: only the pull request number and a validated head sha reach this module.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Mapping

from scripts.ci._github_rest import GitHubClient, GitHubError

logger = logging.getLogger("post_merge_hold")

CHECK_NAME = "Post-merge suite status"
EXIT_OK, EXIT_HELD = 0, 1
GREEN_STATES = frozenset({"pass", "exempt"})
SUMMARY_LIMIT = 60_000  # GitHub refuses an output summary past 65,535 characters
DIGITS_RE = re.compile(r"[0-9]+")


class PublishError(RuntimeError):
    """One stage of publication failed; the message is the line the job prints."""


def conclusion_for(verdict: object) -> str:
    """``success`` only when the verdict's state is ``pass`` or ``exempt``; every other input is ``failure``."""
    state = verdict.get("state") if isinstance(verdict, dict) else None
    return "success" if state in GREEN_STATES else "failure"


# --------------------------------------------------------------------------- a prior verdict
def has_prior_verdict(client: GitHubClient, repo: str, head_sha: str, app_id: str) -> bool:
    """True when the head already carries a check run of this name created by the App ``app_id`` (read with the GITHUB_TOKEN)."""
    if not DIGITS_RE.fullmatch(app_id):
        return False
    try:
        found = client.get(f"/repos/{repo}/commits/{head_sha}/check-runs", {"check_name": CHECK_NAME, "per_page": 100})
    except GitHubError as exc:
        logger.warning("post-merge hold: could not look for an earlier App verdict on %s: %s", head_sha, exc)
        return False
    runs = found.get("check_runs") if isinstance(found, dict) else None
    return any(isinstance(r, dict) and r.get("name") == CHECK_NAME and isinstance(r.get("app"), dict) and r["app"].get("id") == int(app_id) for r in runs or [])


# --------------------------------------------------------------------------- stages
def _refused(exc: GitHubError, what: str) -> PublishError:
    """The failure line for a refused credential step: 404 is an uninstalled App, 401 or 403 a rejected credential."""
    if exc.status == 404:
        return PublishError(f"The hold App is not installed on this repository; no check run was published ({what}).")
    if exc.status in (401, 403):
        return PublishError(f"The hold App credential was rejected by the service ({_status_text(exc.status)}) while trying to {what}; no check run was published.")
    return PublishError(f"The hold App could not {what} ({_status_text(exc.status)}); no check run was published.")


def _status_text(status: int) -> str:
    """``HTTP <status>``, or ``no response`` when the request got none (``GitHubError.status`` 0)."""
    return f"HTTP {status}" if status else "no response"


def _require_credentials(environ: Mapping[str, str], head_sha: str | None, jwt: str) -> str:
    """Return the JWT, or raise ``PublishError`` naming what is missing (a missing secret never means 'nothing to publish')."""
    if not environ.get("HOLD_APP_ID"):
        message = "HOLD_APP_ID is missing or empty; no check run was published."
        raise PublishError(message)
    if environ.get("HOLD_APP_KEY_SET") != "1":
        message = "HOLD_APP_PRIVATE_KEY is missing or empty; no check run was published."
        raise PublishError(message)
    if not head_sha:
        message = "The pull request's head commit is unknown (the event carries no valid sha); no check run was published."
        raise PublishError(message)
    if not jwt:
        message = "The hold App could not sign its token (HOLD_APP_ID or HOLD_APP_PRIVATE_KEY is malformed, or openssl produced nothing); nothing was sent and no check run was published."
        raise PublishError(message)
    return jwt


def _mint_token(api_url: str, repo: str, jwt: str) -> str:
    """Exchange the App JWT for an installation token (lookup, then ``access_tokens``)."""
    step = "look up the installation"
    try:
        app = GitHubClient(api_url, jwt)
        installation = app.get(f"/repos/{repo}/installation")
        installation_id = installation.get("id") if isinstance(installation, dict) else None
        if not isinstance(installation_id, int) or isinstance(installation_id, bool):
            message = "the installation lookup returned no installation id"
            raise PublishError(message)
        step = "obtain an installation token"
        # least privilege: the check-run write permission, on this repository only
        scope = {"permissions": {"checks": "write"}, "repositories": [repo.split("/", 1)[1]]}
        granted = app.post(f"/app/installations/{installation_id}/access_tokens", scope)
    except GitHubError as exc:
        raise _refused(exc, step) from None
    token = granted.get("token") if isinstance(granted, dict) else None
    if not isinstance(token, str) or not token:
        message = "The hold App's token exchange returned no token; no check run was published."
        raise PublishError(message)
    return token


def _create_check(api_url: str, token: str, repo: str, head_sha: str) -> tuple[GitHubClient, int]:
    """Create the check run in progress on the head; return the installation client and the run's id."""
    try:
        installed = GitHubClient(api_url, token)
        created = installed.post(f"/repos/{repo}/check-runs", {"name": CHECK_NAME, "head_sha": head_sha, "status": "in_progress"})
    except GitHubError as exc:
        message = f"The hold App could not create the check run ({_status_text(exc.status)}); nothing was published."
        raise PublishError(message) from None
    run_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        message = "The hold App could not create the check run (the service returned no run id); nothing was published."
        raise PublishError(message)
    return installed, run_id


def _compute(evaluate: Callable[[], dict]) -> dict:
    """Run the verdict computation; any failure leaves the created run in progress and is named without its message."""
    try:
        verdict = evaluate()
    except Exception as exc:  # noqa: BLE001 -- the created run must be left pending and the job must name the stage
        logger.warning("post-merge hold: the verdict computation raised %s", type(exc).__name__)
        message = f"Verdict computation failed ({type(exc).__name__}); the check run is left in progress."
        raise PublishError(message) from None
    if not isinstance(verdict, dict) or not isinstance(verdict.get("reason"), str):
        message = "Verdict computation failed (no verdict was returned); the check run is left in progress."
        raise PublishError(message)
    return verdict


def _complete_check(installed: GitHubClient, repo: str, run_id: int, verdict: dict) -> str:
    """Complete the run with the verdict's conclusion and reason; return the conclusion."""
    conclusion = conclusion_for(verdict)
    output = {"title": f"{CHECK_NAME}: {verdict.get('state')}", "summary": verdict["reason"][:SUMMARY_LIMIT]}
    try:
        installed.patch(f"/repos/{repo}/check-runs/{run_id}", {"status": "completed", "conclusion": conclusion, "output": output})
    except GitHubError as exc:
        message = f"The hold App could not complete the check run ({_status_text(exc.status)}); it is left in progress."
        raise PublishError(message) from None
    return conclusion


# --------------------------------------------------------------------------- the flow
def publish(
    read_client: GitHubClient,
    api_url: str,
    repo: str,
    pr_number: int,
    head_sha: str | None,
    evaluate: Callable[..., dict],
    environ: Mapping[str, str] | None = None,
    jwt: str = "",
) -> int:
    """Create the check run, compute the verdict, complete the run; return the exit code (0 only on a green conclusion).

    ``evaluate(read_client, repo, pr_number, head_sha=...)`` is the verdict computation (it also keeps the pull
    request's comment). ``jwt`` is the App's signed token, read by the caller from stdin (never from the environment).
    A failure at any stage is printed, fails the job and, when the head already carries an
    App verdict, says that verdict could not be refreshed.
    """
    env = os.environ if environ is None else environ
    prior = bool(head_sha) and has_prior_verdict(read_client, repo, str(head_sha), env.get("HOLD_APP_ID", ""))
    try:
        jwt = _require_credentials(env, head_sha, jwt)
        token = _mint_token(api_url, repo, jwt)
        installed, run_id = _create_check(api_url, token, repo, str(head_sha))
        verdict = _compute(lambda: evaluate(read_client, repo, pr_number, head_sha=head_sha))
        print(verdict["reason"])
        conclusion = _complete_check(installed, repo, run_id, verdict)
    except PublishError as exc:
        print(exc)
        if prior:
            print(f"The verdict already published on {head_sha} could not be refreshed.")
        return EXIT_HELD
    return EXIT_OK if conclusion == "success" else EXIT_HELD
