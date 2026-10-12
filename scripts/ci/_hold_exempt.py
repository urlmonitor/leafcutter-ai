"""
MODULE: _hold_exempt
GOAL: The one way past the hold `Post-merge suite status`: a pull request whose
    description declares a fix for an open ``post-merge-red`` issue AND whose fix
    proof passed on its head commit, against the current red run, is exempt.
BUSINESS CONTEXT: TQ-600a-13-viii. Without an exception the pull request that repairs
    a red run is itself held by it, so nothing merges and the run cannot go green.
    Every pull request here is opened by the one account every agent uses, so anything
    a pull request can apply to itself (a label, a phrase) is a declaration and not a
    control; the exemption therefore needs evidence (the proof run), and the proof is
    tied to the event's head commit, so a new push needs a new proof.
ARCHITECTURE: ``match_declaration(body, repo_full_name, notice_numbers)`` is pure,
    stdlib only and linear in the text (one regex whose every quantifier ends at a
    character the next token cannot start with, the tail checked in Python; digits
    are ASCII only and capped in length). ``apply_claim`` is the I/O: called by the
    hold only on the held path (red or did_not_complete, reads succeeded), it
    returns the verdict unchanged when the description declares nothing (no extra
    read), says the fix route waits for the notice when none describes the run,
    otherwise reads exactly two things for the evidence, on the declared path only:
    (a) the ``post-merge-fix-proof.yml`` runs on the head (event
    ``pull_request_target``, at most 5, highest run number) and (b) that run's jobs
    (``filter=latest``; the job named exactly ``Post-merge fix proof`` must be
    ``success``). The proof must have started strictly after the verdict run's
    ``updated_at``. Never an artifact. A granted exemption is recorded once per
    pull request per red run as one comment on the declared notice, carrying a hidden
    marker ``pr=N red_run=R proof_run=P head=<sha>``; only a comment authored by
    ``github-actions[bot]`` (type Bot) carrying EXACTLY that four-part marker counts as
    already recorded, so a forgery has to name a proof run that does not exist yet when a
    pull request's workflows start. RESIDUAL: a workflow of the pull request that runs
    after the proof can still post a bot-authored marker (every pull request here is a
    same-repository branch whose own workflow's token posts as that bot) and so hide the
    duplicate record; it can never hide the exemption itself, whose reason stays in the
    check output and the pull request's comment.
    The match sees only what a reader sees: HTML comments, fenced blocks, inline code and
    blockquote lines are removed first (each pass linear), and a number with a leading
    zero is not a reference.
    A refused record write is noted in the output and never changes the verdict.
    TRUST: the description is attacker text. It is read in Python only, is never
    printed, never reaches a shell or a URL, and only the matched issue number (an
    int, checked against the open notices) is used. Titles, labels and commit
    messages are never read.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import NamedTuple

from scripts.ci._github_rest import GitHubClient, GitHubError
from scripts.ci._hold_comment import BOT_LOGIN, BOT_TYPE, list_comments, valid_sha

logger = logging.getLogger("post_merge_hold")

PROOF_WORKFLOW = "post-merge-fix-proof.yml"
FOLLOWUP_WORKFLOW = "post-merge-followup.yml"
FOLLOWUP_JOB = "notice"
PROOF_JOB = "Post-merge fix proof"
PROOF_EVENT = "pull_request_target"
PROOF_PAGE = 5
MAX_DIGITS = 9
SLUG = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
DECLARATION_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)(?![A-Za-z0-9_])(?::[ \t]*|[ \t]+)"
    rf"(?:https://github\.com/(?P<url>{SLUG})/issues/(?P<url_n>[0-9]+)|(?P<slug>{SLUG})#(?P<slug_n>[0-9]+)|#(?P<n>[0-9]+))",
    re.IGNORECASE | re.ASCII,
)


class Claim(NamedTuple):
    """What the event says about the pull request being judged: its description, head commit and number."""

    body: str | None
    head_sha: str | None
    pr_number: int


# --------------------------------------------------------------------------- what a reader sees
HIDDEN = "\0"  # stands in for removed text, so the pieces around it are never joined into a keyword or a reference
FENCE_RE = re.compile(r" {0,3}(`{3,}|~{3,})")
BACKTICKS_RE = re.compile(r"`+")


def _strip_fences(text: str) -> str:
    """Remove fenced code blocks line by line (an unterminated fence hides the rest, as a renderer does)."""
    kept, fence = [], None
    for line in text.split("\n"):
        if fence is None:
            opened = FENCE_RE.match(line)
            if opened and not (opened.group(1)[0] == "`" and "`" in line[opened.end() :]):
                fence = opened.group(1)
                kept.append(HIDDEN)
            else:
                kept.append(line)
            continue
        closer = line.strip()
        if closer and set(closer) == {fence[0]} and len(closer) >= len(fence):
            fence = None
    return "\n".join(kept)


def _strip_comments(text: str) -> str:
    """Remove ``<!-- ... -->`` (an unterminated comment hides the rest)."""
    parts, pos = [], 0
    while True:
        start = text.find("<!--", pos)
        if start < 0:
            parts.append(text[pos:])
            return "".join(parts)
        parts += [text[pos:start], HIDDEN]
        end = text.find("-->", start + 4)
        if end < 0:
            return "".join(parts)
        pos = end + 3


def _strip_inline_code(text: str) -> str:
    """Remove code spans: a backtick run closed by the next run of exactly the same length (an unmatched run stays literal).

    Linear: the next run of each length is found once, from the end, never by rescanning.
    """
    runs = [(m.start(), m.end()) for m in BACKTICKS_RE.finditer(text)]
    nxt, after = {}, [None] * len(runs)
    for i in range(len(runs) - 1, -1, -1):
        length = runs[i][1] - runs[i][0]
        after[i], nxt[length] = nxt.get(length), i
    parts, pos, i = [], 0, 0
    while i < len(runs):
        j = after[i]
        if j is None:
            i += 1
            continue
        parts += [text[pos : runs[i][0]], HIDDEN]
        pos, i = runs[j][1], j + 1
    parts.append(text[pos:])
    return "".join(parts)


def visible_text(body: str) -> str:
    """``body`` without what a reader does not see as prose: fenced blocks, HTML comments, blockquote lines, inline code."""
    unfenced = _strip_comments(_strip_fences(body))
    unquoted = "\n".join(line for line in unfenced.split("\n") if not line.lstrip().startswith(">"))
    return _strip_inline_code(unquoted)


# --------------------------------------------------------------------------- the match
def declared_numbers(body: object, repo_full_name: str):
    """Yield, in order, every issue number of this repository that ``body`` declares a fix for (closing keyword + reference)."""
    if not isinstance(body, str):
        return
    wanted, text = repo_full_name.lower(), visible_text(body)
    for found in DECLARATION_RE.finditer(text):
        digits = found.group("url_n") or found.group("slug_n") or found.group("n")
        slug = found.group("url") or found.group("slug")
        tail = text[found.end() : found.end() + 1]
        if len(digits) > MAX_DIGITS or digits[0] == "0" or tail.isalnum() or tail == "_":
            continue  # a longer word or number, not this reference (isalnum also refuses non-ASCII digits)
        if slug is None or slug.lower() == wanted:
            yield int(digits)


def _first_open(declared, notice_numbers: set[int]) -> int | None:
    """The first declared number that is one of the open notices."""
    return next((number for number in declared if number in notice_numbers), None)


def match_declaration(body: str | None, repo_full_name: str, notice_numbers: set[int]) -> int | None:
    """The open ``post-merge-red`` issue number ``body`` declares a fix for, or None.

    Closing keywords close/closes/closed, fix/fixes/fixed, resolve/resolves/resolved (any case, whole word, optional
    colon) directly followed by ``#N``, ``owner/repo#N`` (this repository, any case) or this repository's issue URL.
    Pure, stdlib only, linear time; the proof workflow's prepare job calls this same function.
    """
    return _first_open(declared_numbers(body, repo_full_name), notice_numbers)


def open_notice_numbers(issues: list[dict]) -> set[int]:
    """The numbers of the open, non-pull-request issues among the ``post-merge-red`` issues listed."""
    return {
        item["number"]
        for item in issues
        if isinstance(item, dict) and not item.get("pull_request") and item.get("state") == "open" and isinstance(item.get("number"), int)
    }


# --------------------------------------------------------------------------- the event
def read_body(path: str | None) -> str | None:
    """The pull request description from the event file, read in Python; None when absent, null or unreadable."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as handle:  # noqa: PTH123 -- the interpreter itself reads the event
            payload = json.load(handle)
    except (OSError, ValueError, RecursionError) as exc:
        logger.warning("post-merge hold: the description could not be read from the event: %s", exc)
        return None
    pull = payload.get("pull_request") if isinstance(payload, dict) else None
    body = pull.get("body") if isinstance(pull, dict) else None
    return body if isinstance(body, str) else None


# --------------------------------------------------------------------------- reads
def _parse_time(text: object) -> datetime | None:
    """An API timestamp as an aware UTC datetime, or None."""
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        logger.warning("post-merge hold: unparseable timestamp %r (%s); the exemption is not granted", text[:40], exc)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _runs_newest_first(client: GitHubClient, repo: str, workflow: str, query: dict, accept) -> list[dict]:
    """Read one page of ``workflow``'s runs; the ones ``accept`` allows, highest ``run_number`` first."""
    payload = client.get(f"/repos/{repo}/actions/workflows/{workflow}/runs", query)
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    usable = [r for r in runs or [] if isinstance(r, dict) and isinstance(r.get("run_number"), int) and isinstance(r.get("id"), int) and accept(r)]
    return sorted(usable, key=lambda r: r["run_number"], reverse=True)


def _notice_job_ran(client: GitHubClient, repo: str, run_id: int) -> bool | None:
    """True when the run's ``notice`` job was not skipped, False when it was, None when that cannot be told."""
    try:
        payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/jobs", {"filter": "latest"})
    except GitHubError as exc:
        logger.warning("post-merge hold: the jobs of follow-up run %s could not be read: %s", run_id, exc)
        return None
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    states = [j.get("conclusion") for j in jobs or [] if isinstance(j, dict) and j.get("name") == FOLLOWUP_JOB]
    return None if not states else any(state != "skipped" for state in states)


def _named(found: dict) -> str:
    """A run by link (its id when it has no link)."""
    link = found.get("html_url")
    return link if isinstance(link, str) else f"run {found['id']}"


def _followup_text(client: GitHubClient, repo: str, run: dict) -> str:
    """The sentence for a red run with no notice: the fix route waits for it; link the follow-up run whose notice job can be re-run."""
    text = "No exemption: no post-merge-red notice describes this run, so the fix route is unavailable until the notice exists."
    sha = valid_sha(run.get("head_sha"))
    if sha is None:
        return text
    try:
        found = _runs_newest_first(client, repo, FOLLOWUP_WORKFLOW, {"head_sha": sha, "per_page": PROOF_PAGE}, lambda r: r.get("head_sha") == sha)
    except GitHubError as exc:
        logger.warning("post-merge hold: the follow-up runs could not be read: %s", exc)
        return f"{text} The follow-up run that can create it could not be read ({exc})."
    unknown = None
    for candidate in found:
        ran = _notice_job_ran(client, repo, candidate["id"])
        if ran:
            return f"{text} Re-run the notice job of the follow-up run {_named(candidate)} to create it."
        if ran is None and unknown is None:
            unknown = candidate
    if unknown is not None:
        return f"{text} The state of the notice job of the follow-up run {_named(unknown)} is unknown; re-run that job if it did not run."
    return f"{text} The follow-up runs on this commit skipped their notice job, so none can be re-run to create it." if found else text


def _proof_failure(client: GitHubClient, repo: str, head: str, run: dict) -> tuple[dict | None, str]:
    """``(proof run, "")`` when the fix proof passed on ``head`` against ``run``; else ``(None, why not)``."""
    try:
        proof = next(iter(_runs_newest_first(client, repo, PROOF_WORKFLOW, {"head_sha": head, "event": PROOF_EVENT, "per_page": PROOF_PAGE}, lambda r: r.get("head_sha") == head and r.get("event") == PROOF_EVENT)), None)
    except GitHubError as exc:
        logger.warning("post-merge hold: the fix proof runs could not be read, holding: %s", exc)
        return None, f"No exemption: the fix proof runs could not be read ({exc})."
    if proof is None:
        return None, f"No exemption: there is no run of the fix proof ({PROOF_WORKFLOW}) on head commit {head[:7]}."
    if proof.get("status") != "completed":
        return None, f"No exemption: the fix proof (run {proof['id']}) is still running or not yet finished; the check re-evaluates when it completes."
    started, settled = _parse_time(proof.get("run_started_at")), _parse_time(run.get("updated_at"))
    if started is None or settled is None:
        return None, "No exemption: the start of the fix proof or the settle time of the red run could not be read."
    if started <= settled:
        return None, "No exemption: the fix proof started before the red run settled, so it proved an earlier red run, not the current one."
    try:
        payload = client.get(f"/repos/{repo}/actions/runs/{proof['id']}/jobs", {"filter": "latest"})
    except GitHubError as exc:
        logger.warning("post-merge hold: the jobs of fix proof run %s could not be read, holding: %s", proof["id"], exc)
        return None, f"No exemption: the jobs of the fix proof could not be read ({exc})."
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    results = [j.get("conclusion") for j in jobs or [] if isinstance(j, dict) and j.get("name") == PROOF_JOB]
    if not results:
        return None, f"No exemption: the fix proof run has no job named '{PROOF_JOB}'."
    if results == ["skipped"]:
        return None, "No exemption: the fix proof job was skipped, which is not a pass."
    if any(result != "success" for result in results):
        return None, "No exemption: the fix proof failed, so the tests that failed on main do not yet pass on this head."
    return proof, ""


# --------------------------------------------------------------------------- the record
def marker_for(pr_number: int, red_run_id: object, proof_run_id: object, head_sha: str) -> str:
    """The hidden marker line of one exemption: this pull request, this red run, this proof run on this head (all four must match)."""
    return f"<!-- post-merge-fix-exemption pr={pr_number} red_run={red_run_id} proof_run={proof_run_id} head={head_sha} -->"


def _recorded(client: GitHubClient, repo: str, issues: list[int], marker: str) -> bool:
    """True when a comment authored by the Actions bot on any of ``issues`` carries ``marker`` as one of its lines."""
    for number in issues:
        for comment in list_comments(client, repo, number):
            user, body = comment.get("user"), comment.get("body")
            if isinstance(user, dict) and user.get("login") == BOT_LOGIN and user.get("type") == BOT_TYPE and isinstance(body, str) and marker in body.splitlines():
                return True
    return False


def _record(client: GitHubClient, repo: str, target: int, others: list[int], claim: Claim, head: str, proof: dict, run: dict) -> str:
    """Record the exemption once on ``target``; return the sentence for the output (the verdict is never changed by it)."""
    marker = marker_for(claim.pr_number, run.get("id"), proof["id"], head)
    try:
        if _recorded(client, repo, [target, *others], marker):
            return f" Already recorded on #{target}."
        text = f"{marker}\nExemption: pull request #{claim.pr_number} (head commit {head}) declares and proves a fix for the red post-merge run {run.get('id')}, so the hold does not apply to it.\nProof run id: {proof['id']}\n"
        client.post(f"/repos/{repo}/issues/{target}/comments", {"body": text})
    except GitHubError as exc:
        logger.warning("post-merge hold: the exemption could not be recorded on #%s: %s", target, exc)
        return f" The exemption could not be recorded on #{target} ({exc})."
    return f" Recorded on #{target}."


# --------------------------------------------------------------------------- the decision
def _held(verdict: dict, note: str) -> dict:
    """The held verdict with ``note`` (why no exemption) after its reason."""
    return {**verdict, "reason": f"{verdict['reason']} {note}"}


def apply_claim(client: GitHubClient, repo: str, verdict: dict, issues: list[dict] | None, issues_error: str | None, claim: Claim) -> dict:
    """Return ``verdict`` (a held red or did_not_complete one) or its ``exempt`` form when the description declares and proves a fix.

    ``issues`` is the ``post-merge-red`` issue list already read for the verdict (None with ``issues_error`` when that read
    failed). Nothing is read here unless the description declares a fix; raises ``GitHubError`` never (each failure holds).
    """
    declared = list(declared_numbers(claim.body, repo))
    if not declared:
        return verdict
    run, notice = verdict["run"], verdict["notice"]
    if issues is None:
        return _held(verdict, f"No exemption: the post-merge-red issues could not be read ({issues_error}).")
    if notice is None:
        return _held(verdict, _followup_text(client, repo, run))
    chosen = _first_open(declared, open_notice_numbers(issues))
    if chosen is None:
        return _held(verdict, f"No exemption: this pull request declares #{declared[0]}, which is not an open post-merge-red notice.")
    head = valid_sha(claim.head_sha)
    if head is None:
        return _held(verdict, "No exemption: the head commit is unknown, so no fix proof can be matched to it.")
    proof, why = _proof_failure(client, repo, head, run)
    if proof is None:
        return _held(verdict, why)
    others = [n for n in {notice.get("number")} if isinstance(n, int) and n != chosen]
    recorded = _record(client, repo, chosen, others, claim, head, proof, run)
    reason = f"Post-merge suite status passes: this pull request declares and proves a fix for #{chosen} (red run {run.get('html_url')}; fix proof run {proof.get('html_url')}).{recorded}"
    return {**verdict, "state": "exempt", "reason": reason, "cause": None}
