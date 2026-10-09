"""
MODULE: _notice_render
GOAL: Everything that turns a run verdict into the TEXT of the post-merge-red
    notice: the commit range since the last green run, the machine-readable
    state block, the description and the per-run history comment.
BUSINESS CONTEXT: TQ-600a-13-iii. The description is the CURRENT state, so a
    reader sees the latest run without opening the comments; the same state
    block is what the hold (-vi) and fix declarations (-viii) locate. Node ids
    and commit subjects are untrusted text: they appear only inside code spans,
    so a mention or markup in a test name notifies nobody and renders nothing.
ARCHITECTURE: ``collect_commits`` is the only function here that touches the
    outside (one ``git rev-list`` subprocess, all parents followed, in a
    full-history checkout); the rest is pure. ``build_state`` produces the
    ``<!-- post-merge-suite-state v2 {json} -->`` fields; ``render_description``
    and ``render_history_comment`` take that state plus the ``CommitRange``.
    The wording of did-not-complete is TQ-600a-13-v's: it is isolated in
    ``_headline`` so that record changes one function. The anchor sha is shown
    only inside the state block, except when it cannot be resolved, where it is
    named so a reader can find out why the list is empty.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger("post_merge_notice")

LABEL = "post-merge-red"
# The real block is always a line of its own and the LAST line of a description or comment, and
# untrusted text is flattened to one line inside a code span, so it can never start such a line.
STATE_LINE_RE = re.compile(r"^<!-- post-merge-suite-state v2 (\{.*\}) -->[ \t]*$", re.MULTILINE)
SHA_RE = re.compile(r"[0-9a-f]{40}")
ZERO_WIDTH_SPACE = chr(0x200B)  # defuses HTML comment markers; the same character, shown literally: "​"
RUNS_PAGE_SIZE = 100
MAX_COMMITS = 50
MAX_FAILING_SHOWN = 100
GIT_TIMEOUT_SECONDS = 30

# Plain-words cause per stage, shown outside code spans so a reader can tell "the tests never ran" from
# "the tests failed". A stage absent here is still named, in a code span, by the headline.
STAGE_CAUSES = {
    "setup": "a setup step failed before the tests ran",
    "collection": "test collection failed, so part of the lane never ran",
    "empty_selection": "the lane selected no tests at all",
    "retry_failed": "the retry job failed, so the first-run failures were not confirmed",
    "cancelled_or_timed_out": "the run was cancelled or timed out",
    "startup_failure": "the run could not start",
    "result_unreadable": "the run's test result could not be read",
}

RANGE_LISTED = "listed"
RANGE_NO_GREEN = "no_green_run"
RANGE_PAGE_FULL = "green_run_beyond_page"
RANGE_ANCHOR_MISSING = "anchor_unresolvable"
RANGE_HEAD_MISSING = "head_unresolvable"


@dataclass(frozen=True)
class LaneSpec:
    """What differs between the lanes' notices (TQ-600a-13-xii): label, run history, wording, commit sections.

    ``lists_commits`` is False for the timing lane: its notice names commits only as lane entrants (the commit
    that touched a newly marked test's file), so any sha on it means exactly that.
    """

    name: str
    label: str
    workflow: str
    suite: str
    titles: dict
    lists_commits: bool = True


CORRECTNESS = LaneSpec(
    "correctness",
    LABEL,
    "post-merge-suite.yml",
    "post-merge suite",
    {"red": "Post-merge suite is red", "did_not_complete": "Post-merge suite did not complete"},
)
TIMING = LaneSpec(
    "timing",
    "post-merge-timing",
    "post-merge-timing.yml",
    "post-merge timing suite",
    {"red": "Post-merge timing suite is red", "did_not_complete": "Post-merge timing suite did not complete"},
    lists_commits=False,
)
LANES = {spec.name: spec for spec in (CORRECTNESS, TIMING)}


@dataclass(frozen=True)
class CommitRange:
    """The commits merged since the last green run, as far as the checkout could tell."""

    status: str
    anchor_sha: str | None = None
    commits: list = field(default_factory=list)  # (sha, subject) pairs, newest first, at most MAX_COMMITS
    omitted: int = 0


# --------------------------------------------------------------------------- the state block
def encode_state(state: dict) -> str:
    """Return the one-line state block; ``<`` and ``>`` are escaped so no id can close the comment."""
    payload = json.dumps(state, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- post-merge-suite-state v2 {payload} -->"


def parse_state(text: str | None) -> dict | None:
    """Return the state block carried by a description or comment (the LAST one), or None when it has none."""
    matches = STATE_LINE_RE.findall(text or "")
    if not matches:
        return None
    try:
        parsed = json.loads(matches[-1])
    except ValueError:
        logger.warning("a %s notice carries a state block that is not JSON; treating it as absent", LABEL)
        return None
    return parsed if isinstance(parsed, dict) else None


def build_state(verdict: dict, commit_range: CommitRange, red_since: str, lane: LaneSpec = CORRECTNESS) -> dict:
    """Return the state-block fields (delivers_to of TQ-600a-13-iii) for this run.

    A lane that does not list commits (timing) carries ``head_sha: None``: the run link names the head.
    """
    return {
        "run_id": verdict["run_id"],
        "verdict": verdict["verdict"],
        "stage": verdict.get("stage"),
        "failing": sorted(verdict.get("failing") or []),
        "run_url": verdict["run_url"],
        "head_sha": verdict["head_sha"] if lane.lists_commits else None,
        "anchor_sha": commit_range.anchor_sha,
        "commits": [sha for sha, _ in commit_range.commits],
        "commits_omitted": commit_range.omitted,
        "red_since": red_since,
    }


# --------------------------------------------------------------------------- the commit walk
def collect_commits(repo_dir: str, head_sha: str, anchor_sha: str | None, page_full: bool = False) -> CommitRange:
    """List every commit reachable from ``head_sha`` and not from ``anchor_sha`` (all parents).

    ``page_full`` says the run page that held no green run was full, so a green run may exist beyond it.
    """
    if anchor_sha is None:
        return CommitRange(RANGE_PAGE_FULL if page_full else RANGE_NO_GREEN)
    if not SHA_RE.fullmatch(anchor_sha) or not _has_commit(repo_dir, anchor_sha):
        return CommitRange(RANGE_ANCHOR_MISSING, anchor_sha)
    if not SHA_RE.fullmatch(head_sha) or not _has_commit(repo_dir, head_sha):
        return CommitRange(RANGE_HEAD_MISSING, anchor_sha)
    lines = _git(repo_dir, "rev-list", "--format=%s", head_sha, f"^{anchor_sha}")
    if lines is None:
        return CommitRange(RANGE_HEAD_MISSING, anchor_sha)
    pairs = _pair_commits(lines.splitlines())
    return CommitRange(RANGE_LISTED, anchor_sha, pairs[:MAX_COMMITS], max(0, len(pairs) - MAX_COMMITS))


def _pair_commits(lines: list[str]) -> list[tuple[str, str]]:
    """Pair each ``commit <sha>`` header of ``rev-list --format=%s`` output with the subject line after it."""
    pairs = []
    for index in range(0, len(lines) - 1, 2):
        header, subject = lines[index], lines[index + 1]
        if header.startswith("commit ") and SHA_RE.fullmatch(header[7:]):
            pairs.append((header[7:], subject))
    return pairs


def _has_commit(repo_dir: str, sha: str) -> bool:
    """Return True when ``sha`` names a commit object in the checkout."""
    return _git(repo_dir, "cat-file", "-e", f"{sha}^{{commit}}") is not None


def _git(repo_dir: str, *args: str) -> str | None:
    """Run ``git -C repo_dir <args>``; return stdout, or None when git failed or could not run."""
    argv = ["git", "-C", repo_dir, *args]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git %s failed for the %s notice: %s", args[0], LABEL, exc)
        return None
    return done.stdout if done.returncode == 0 else None


# --------------------------------------------------------------------------- rendering
def code(text: str) -> str:
    """Render untrusted ``text`` as one inline code span.

    Backticks and line breaks cannot escape it, and an HTML comment opener or closer is defused so the
    text can neither forge a state block nor swallow the real one.
    """
    flat = " ".join(str(text).replace("`", "'").split())
    flat = flat.replace("<!--", f"<!{ZERO_WIDTH_SPACE}--").replace("-->", f"-{ZERO_WIDTH_SPACE}->")
    return f"`{flat}`"


def _headline(state: dict, lane: LaneSpec = CORRECTNESS) -> str:
    """The one-line statement of what happened.

    A run that did not complete is worded differently from a failure (TQ-600a-13-v): never "red", never a
    claim that tests failed, always the stage at which it stopped (when one is known) and, for the stages
    whose cause is known, a plain-words cause outside the code span.
    """
    subject = f"The {lane.suite}"
    if state["verdict"] != "did_not_complete":
        return f"{subject} is red."
    stage = state.get("stage")
    cause = STAGE_CAUSES.get(stage or "")
    if cause:
        return f"{subject} did not complete: {cause}. Stage: {code(stage)}."
    return f"{subject} did not complete{f' at stage {code(stage)}' if stage else ''}."


def _failing_lines(failing: list[str]) -> list[str]:
    """Bullet lines naming each failing node id, capped; the state block keeps the full list."""
    if not failing:
        return []
    lines = [f"Failing tests ({len(failing)}):", ""]
    lines += [f"- {code(node_id)}" for node_id in failing[:MAX_FAILING_SHOWN]]
    if len(failing) > MAX_FAILING_SHOWN:
        lines.append(f"- ... and {len(failing) - MAX_FAILING_SHOWN} more, listed in the run's log")
    return [*lines, ""]


def _commit_lines(commit_range: CommitRange) -> list[str]:
    """The suspect-commit section: a list, or words when there is no list to show."""
    if commit_range.status == RANGE_NO_GREEN:
        return ["No green run is on record, so the commits merged since one cannot be listed.", ""]
    if commit_range.status == RANGE_PAGE_FULL:
        return [f"The last green run is not within the last {RUNS_PAGE_SIZE} runs, so the commits since it cannot be listed.", ""]
    if commit_range.status == RANGE_ANCHOR_MISSING:
        return [f"The last green run tested {code(commit_range.anchor_sha)}, which is not in this checkout, so the commits since it cannot be listed.", ""]
    if commit_range.status == RANGE_HEAD_MISSING:
        return ["The run's head commit could not be read from this checkout, so the commits since the last green run cannot be listed.", ""]
    if not commit_range.commits:
        return ["No commits were merged since the last green run.", ""]
    lines = ["Commits merged since the last green run:", ""]
    lines += [f"- {code(sha[:7])} {code(subject)}" for sha, subject in commit_range.commits]
    if commit_range.omitted:
        lines.append(f"- ... and {commit_range.omitted} more")
    return [*lines, ""]


def render_description(state: dict, commit_range: CommitRange, lane: LaneSpec = CORRECTNESS, entrants: list[str] | None = None) -> str:
    """Return the notice description: the CURRENT state, ending in the state block.

    ``entrants`` are ready-made bullet lines naming new lane entrants (see ``_notice_entrants``).
    """
    since = "Not green since" if state["verdict"] == "did_not_complete" else "Red since"
    lines = [_headline(state, lane), "", f"Run: {state['run_url']}"]
    if lane.lists_commits:
        lines.append(f"Head commit: {code(state['head_sha'])}")
    lines += [f"{since}: {code(state['red_since'])}", ""]
    lines += _failing_lines(state["failing"])
    lines += _commit_lines(commit_range) if lane.lists_commits else []
    lines += [*entrants, ""] if entrants else []
    lines += ["This notice is for people. It does not decide whether a pull request is held.", "", encode_state(state)]
    return "\n".join(lines) + "\n"


def render_history_comment(state: dict, lane: LaneSpec = CORRECTNESS) -> str:
    """Return the comment that records one run in the streak's history."""
    lines = [f"{_headline(state, lane)} Run: {state['run_url']}", ""]
    lines += _failing_lines(state["failing"])
    lines += [encode_state(state)]
    return "\n".join(lines) + "\n"


def render_green_comment(verdict: dict, lane: LaneSpec = CORRECTNESS) -> str:
    """Return the comment that closes a notice when the suite is green again."""
    return f"The {lane.suite} is green again: {verdict['run_url']}. Closing this notice."


def render_duplicate_comment(canonical: int, lane: LaneSpec = CORRECTNESS) -> str:
    """Return the comment that closes a duplicate notice in favour of the canonical one."""
    return f"Duplicate of #{canonical}, the canonical {lane.label} notice. Closing in its favour."
