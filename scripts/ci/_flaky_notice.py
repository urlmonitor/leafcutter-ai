"""
MODULE: _flaky_notice
GOAL: Decide and word the writes to the single open ``post-merge-flaky`` issue, the
    non-holding notice of correctness-lane tests that passed only on retry, and
    name the ids a repeated pass-on-retry made red.
BUSINESS CONTEXT: TQ-600a-13-xiii. A pass on retry may be the shared-layout
    corruption itself, so a green run that records it only in a log loses the
    signal. The notice lists every test that passed on retry in the window with
    how many runs it did so in, links the run on the lines of this run's ids, and
    names a red that did not reproduce at the same commit as a candidate for the
    timing lane. It never affects a verdict or the hold: the verdict file already
    carries the window, so this module reads no history.
ARCHITECTURE: Pure. ``plan_flaky_writes`` takes the verdict file, the open flaky
    notices (ascending by number) and the window size and returns ``(kind, number,
    body)`` tuples that ``post_merge_notice`` turns into its ``Write`` list: a run
    with no passed-on-retry id and no candidate writes nothing, except that a window
    that is empty too closes every open notice; otherwise the canonical notice is
    edited (or created, labels exactly ``["post-merge-flaky"]``) and duplicates are
    closed. A candidate alone creates or edits the notice and never closes it. A run
    that did not complete, or whose window was only partly read, never closes it (its
    window is unknown); only a whole, clean window does. Node ids and run
    links come from artifacts and appear only inside code spans.
"""

from __future__ import annotations

from scripts.ci._notice_render import CORRECTNESS, MAX_FAILING_SHOWN, LaneSpec, code, render_duplicate_comment

FLAKY_LABEL = "post-merge-flaky"
TITLE = "Correctness tests that passed only on retry"
FLAKY = LaneSpec("flaky", FLAKY_LABEL, CORRECTNESS.workflow, "post-merge flaky-test window", {"red": TITLE, "did_not_complete": TITLE})


def not_reproduced(verdict: dict, previous: dict | None) -> list[str]:
    """Ids of the previous run's failures when it was red and this run is green at the same head commit."""
    if not previous or previous.get("verdict") != "red" or verdict.get("verdict") != "green":
        return []
    head = verdict.get("head_sha")
    if not head or previous.get("head_sha") != head:
        return []
    ids = previous.get("failing")
    return sorted(i for i in ids if isinstance(i, str)) if isinstance(ids, list) else []


def repeated_lines(verdict: dict, tunables: dict) -> list[str]:
    """The red notice's section naming the ids that made the run red by repeating a pass on retry; none when empty."""
    ids = verdict.get("repeated_pass_on_retry") or []
    if not ids:
        return []
    heading = (
        f"Repeated pass-on-retry ({len(ids)}): passed on retry in {tunables['flaky_red_threshold']} or more of the "
        f"last {tunables['flaky_window_runs']} settled runs, so this run is red:"
    )
    return [heading, "", *(f"- {code(i)}" for i in ids[:MAX_FAILING_SHOWN])]


def _window_lines(verdict: dict, size: int) -> list[str]:
    """One line per id of the window: its count, and this run's link on the ids that passed on retry in it."""
    window, retried = verdict.get("pass_on_retry_window") or {}, set(verdict.get("passed_on_retry") or [])
    repeated = set(verdict.get("repeated_pass_on_retry") or [])
    lines = []
    for node_id in sorted(window)[:MAX_FAILING_SHOWN]:
        line = f"- {code(node_id)}: {window[node_id]} of {size} runs"
        if node_id in retried:
            line += f"; passed on retry in this run: {verdict['run_url']}"
        if node_id in repeated:
            line += "; repeated, so this run is red"
        lines.append(line)
    if len(window) > MAX_FAILING_SHOWN:
        lines.append(f"- ... and {len(window) - MAX_FAILING_SHOWN} more")
    return lines


def render_flaky_description(verdict: dict, size: int, candidates: list[str], previous: dict | None) -> str:
    """The notice description: the CURRENT window, then the timing candidates, rewritten every time."""
    window = verdict.get("pass_on_retry_window") or {}
    read = verdict.get("window_runs_read", 1)
    lines = [f"Correctness-lane tests that passed only on retry in the last {size} settled runs (window read: {read} of {size} runs)."]
    lines += ["", *_window_lines(verdict, size)] if window else ["", f"No test passed on retry in the last {size} settled runs."]
    if candidates:
        url = (previous or {}).get("run_url") or ""
        lines += ["", f"Not reproduced at the same commit ({len(candidates)}): red, then green with the same head commit. Candidates for the timing lane:", ""]
        red_in = f"red in {code(url)}" if url else "red"
        lines += [f"- {code(i)}: {red_in}, green on the next run at the same commit; candidate for the timing lane" for i in candidates[:MAX_FAILING_SHOWN]]
    lines += ["", "This notice is for people. It never decides the verdict of the post-merge suite or whether a pull request is held."]
    return "\n".join(lines) + "\n"


def wants_write(verdict: dict, candidates: list[str]) -> bool:
    """True when this run may create or edit the notice: it has a passed-on-retry id or a timing candidate."""
    return bool(verdict.get("passed_on_retry") or candidates)


def may_close(verdict: dict, size: int) -> bool:
    """True when the run completed and the WHOLE window (``size`` runs) was read and is clean.

    A short read (an unreadable earlier artifact, a missing one) says nothing about the runs it did not see,
    so it never closes the notice.
    """
    whole = verdict.get("window_runs_read") == size
    return whole and not verdict.get("pass_on_retry_window") and verdict.get("verdict") != "did_not_complete"


def plan_flaky_writes(verdict: dict, notices: list[dict], size: int, candidates: list[str], previous: dict | None) -> list[tuple[str, int | None, dict]]:
    """Return the ordered ``(kind, number, body)`` writes for this run, given the open flaky notices (ascending)."""
    if not wants_write(verdict, candidates):
        return _close_all(verdict, notices, size) if may_close(verdict, size) else []
    body = render_flaky_description(verdict, size, candidates, previous)
    if not notices:
        return [("create", None, {"title": TITLE, "body": body, "labels": [FLAKY_LABEL]})]
    canonical, duplicates = notices[0], notices[1:]
    writes: list[tuple[str, int | None, dict]] = [] if canonical.get("body") == body else [("edit", canonical["number"], {"body": body})]
    for duplicate in duplicates:
        writes.append(("comment", duplicate["number"], {"body": render_duplicate_comment(canonical["number"], FLAKY)}))
        writes.append(("close", duplicate["number"], {"state": "closed", "state_reason": "duplicate"}))
    return writes


def _close_all(verdict: dict, notices: list[dict], size: int) -> list[tuple[str, int | None, dict]]:
    """A clean window: a comment linking this run, then a close, for every open flaky notice."""
    reason = f"No test passed on retry in the last {size} settled runs: {verdict['run_url']}. Closing this notice."
    writes: list[tuple[str, int | None, dict]] = []
    for notice in notices:
        writes.append(("comment", notice["number"], {"body": reason}))
        writes.append(("close", notice["number"], {"state": "closed", "state_reason": "completed"}))
    return writes
