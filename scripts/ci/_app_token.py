"""
MODULE: _app_token
GOAL: Exchange the dedicated hold App's signed JWT for a short-lived installation token that
    carries ONE permission on THIS repository only.
BUSINESS CONTEXT: TQ-600a-13-vi (the hold's ``checks: write`` token) and TQ-600a-13-xv (the
    re-evaluation's ``actions: write`` token, owner decision 2026-10-12). Both mint the same way,
    so the lookup and the exchange live here once; each caller names the permission it needs and
    nothing else. The token is the only credential allowed to write a check run or to re-run a
    hold run, so it is asked for with the least scope its one caller needs.
ARCHITECTURE: ``mint_installation_token(api_url, repo, jwt, permission, timeout=...)`` looks the
    installation up with the JWT (``GET /repos/{repo}/installation``) and posts the exchange
    (``POST /app/installations/{id}/access_tokens`` with ``{permission: write}`` and a
    ``repositories`` list of this repository's name). The client that carries the JWT is built with
    ``WritePolicy(token_kind="app_jwt", repo=repo, exchange_permission=permission)``, whose write
    guard refuses any exchange body but that one permission for this repository, so the hold's
    minter can never obtain an ``actions`` token nor the re-run minter a ``checks`` one. The
    answer is verified (permissions exactly as asked plus the implicit read-only metadata;
    repositories, if named, exactly this one) and a wider grant fails closed. The accepted token
    is registered with ``::add-mask::`` on stdout before it is returned. A failure raises ``AppTokenError``
    carrying the stage (``step``), the HTTP status (None when the service answered in an
    unexpected shape) and a ``kind``; its text never contains the JWT or the token.
"""

from __future__ import annotations

from scripts.ci._github_rest import DEFAULT_TIMEOUT_SECONDS, GitHubClient, GitHubError, WritePolicy

STEP_LOOKUP, STEP_EXCHANGE = "look up the installation", "obtain an installation token"
KIND_NO_INSTALLATION, KIND_NO_TOKEN, KIND_REFUSED, KIND_WIDER_GRANT = "no_installation", "no_token", "refused", "wider_grant"
IMPLICIT_METADATA = ("metadata", "read")  # every installation token also carries read-only metadata; nothing else may ride along


class AppTokenError(RuntimeError):
    """The token could not be minted at ``step``. ``status`` is the HTTP status (0: no response; None: an unexpected answer)."""

    def __init__(self, message: str, *, step: str, kind: str, status: int | None = None) -> None:
        super().__init__(message)
        self.step = step
        self.kind = kind
        self.status = status


def _grant_matches(granted: dict, permissions: dict[str, str], repo: str) -> bool:
    """True when the service's answer grants exactly ``permissions`` (plus the implicit read-only ``metadata``) and, if it names
    repositories, exactly the one ``repo``. A missing or differently-shaped ``permissions`` is a mismatch (fail closed)."""
    got = granted.get("permissions")
    if got != permissions and got != {**permissions, IMPLICIT_METADATA[0]: IMPLICIT_METADATA[1]}:
        return False
    if "repositories" not in granted:
        return True
    names = granted["repositories"]
    only = names[0] if isinstance(names, list) and len(names) == 1 else None
    return isinstance(only, dict) and only.get("name") == repo.split("/", 1)[1] and only.get("full_name", repo) == repo


def mint_installation_token(api_url: str, repo: str, jwt: str, permission: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Exchange ``jwt`` for an installation token holding exactly ``{permission: write}`` on ``repo`` (``owner/name``) only.

    The answer is checked against what was asked; a wider grant raises. The token is registered with the runner's masking command
    (``::add-mask::<token>`` on stdout, flushed) before it is returned, so it is hidden from every later log line.
    Raises ``AppTokenError`` when the installation cannot be found, the service refuses the exchange, answers without a token, or
    grants more (or other) than was asked.
    """
    step = STEP_LOOKUP
    permissions = {permission: "write"}
    try:
        app = GitHubClient(api_url, jwt, timeout=timeout, policy=WritePolicy(token_kind="app_jwt", repo=repo, exchange_permission=permission))
        installation = app.get(f"/repos/{repo}/installation")
        installation_id = installation.get("id") if isinstance(installation, dict) else None
        if not isinstance(installation_id, int) or isinstance(installation_id, bool):
            message = "the installation lookup returned no installation id"
            raise AppTokenError(message, step=step, kind=KIND_NO_INSTALLATION)
        step = STEP_EXCHANGE
        granted = app.post(f"/app/installations/{installation_id}/access_tokens", {"permissions": permissions, "repositories": [repo.split("/", 1)[1]]})
    except GitHubError as exc:
        outcome = f"HTTP {exc.status}" if exc.status else ("refused by the write policy" if exc.kind == "refused" else "no response")
        message = f"the App could not {step} ({outcome})"
        raise AppTokenError(message, step=step, kind=KIND_REFUSED, status=exc.status) from None
    token = granted.get("token") if isinstance(granted, dict) else None
    if not isinstance(token, str) or not token:
        message = "the token exchange returned no token"
        raise AppTokenError(message, step=step, kind=KIND_NO_TOKEN)
    if not _grant_matches(granted, permissions, repo):
        message = "the token exchange granted more or other than was asked; the token is discarded"  # never names the grant's contents or the token
        raise AppTokenError(message, step=step, kind=KIND_WIDER_GRANT)
    print(f"::add-mask::{token}", flush=True)  # noqa: T201 -- the runner's masking command: it must be on stdout, before the token is used
    return token
