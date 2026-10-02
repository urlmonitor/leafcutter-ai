"""
MODULE: shared_layout_integrity
GOAL: Prove -- not merely assume -- that the shared reference layout
    (TQ-600a-1) stays read-only across every ``shared_layout_reader``-marked
    consumer test in a session. Captures a content-digest record of the
    layout the instant the single deploy that produced it finishes, then
    compares that record against the layout's state after each consuming
    test, reporting how many files it compared and how many consuming tests
    ran, so "nothing to check" and "checked and untouched" never read the
    same.
BUSINESS CONTEXT: TQ-600a-3. Sharing one deployed layout across many tests
    (TQ-600a-1) is only safe if read-only is enforced rather than assumed --
    an unnoticed mutation would silently corrupt the layout for every test
    that runs after the offender, presenting as intermittent unrelated
    failures. See docs/acceptance-criteria/testing-quality/
    TQ-600-suite-feedback-latency/TQ-600a-3.yaml for the full Gherkin
    criteria and the two anti-false-green precedents (the AC-store
    validator's eight-day zero-file green streak; the bytecode-churn
    false-positive) this module is built to not repeat.
ARCHITECTURE: The content-digest walk itself (``capture_record`` /
    ``compare_record``) lives in ``_shared_layout_integrity_compare.py``,
    split out to respect this project's 400-line file-size limit (mirroring
    the ``_shared_layout_producer.py`` / ``_shared_layout_coordination.py``
    split), and is re-exported unchanged below. THIS module owns the
    session-level pytest plugin built on those functions.

    Registered via an EXPLICIT ``-p scripts.suite_performance.
    shared_layout_integrity`` override in every test that exercises it
    (this AC's own ``files_touched`` names only the two files above, so
    unlike the routing plugin it was not required to be added to
    pytest.ini's own ``addopts``) AND, additionally, added to pytest.ini's
    ``addopts`` so the guard is not dead code that only ever runs inside
    its own test suite: a comparison mechanism whose only invocation is its
    own tests proves nothing about the real, ever-growing population of
    ``shared_layout_reader``-marked tests it exists to guard. Loading the
    same dotted plugin name twice (once via addopts, once via an explicit
    ``-p``) is idempotent -- pytest de-duplicates by module identity,
    exactly as the existing routing plugin (also both in addopts AND
    explicitly re-passed by its own test helpers) already demonstrates.

    The plugin does NOT eagerly call ``get_or_produce_shared_layout()`` at
    session start -- that would force a deploy even when zero tests ever
    consume the shared layout, contradicting TQ-600a-1-i's laziness
    guarantee. Instead it detects production via the read-only
    ``_shared_layout_coordination.check_published`` probe, run in a
    ``pytest_runtest_setup`` hookwrapper immediately AFTER the wrapped
    setup call returns for the first ``shared_layout_reader``-marked test
    observed: fixture resolution (which is what actually calls
    ``get_or_produce_shared_layout()`` for a reader-routed test) happens
    DURING that wrapped call, so by the time control returns to this
    hookwrapper the deploy has already completed and the record can be
    captured before that test's own body (the ``call`` phase) has had any
    chance to run -- satisfying "the record is captured before any
    consumer runs" even for the very consumer whose own request triggered
    the deploy.

    Per-test attribution -- which test dirtied the layout -- is
    implemented as a ``pytest_runtest_teardown`` hookwrapper that re-walks
    and re-compares once after EACH ``shared_layout_reader``-marked
    consumer completes (the more expensive, explicitly-requested per-test
    attribution mode the AC's Implementation Notes distinguish from the
    cheap default of "digest once at capture and once at comparison"). The
    FIRST consumer whose post-teardown comparison newly reports a
    difference is recorded as ``offending_test``, by pytest node id, and
    announced loudly via ``pytest_terminal_summary`` -- "the layout
    changed" alone is not an acceptable failure message.

    At ``pytest_sessionfinish`` the plugin ALWAYS evaluates the final
    report and fails the run (non-zero exit) when, and only when,
    ``files_ok`` is False -- this happens regardless of whether the
    diagnostic JSON env var below is set, because the guard's job is to
    fail a genuinely dirtied real suite run, not merely to describe one.
    Writing the JSON report to the path named by
    ``LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT`` is a SEPARATE,
    env-var-gated concern (no-op if unset), used by this AC's own tests to
    inspect the report's shape.

    SCOPE, verified against the shipped producer rather than assumed:
    ``_shared_layout_coordination.py`` derives run identity from
    ``PYTEST_XDIST_TESTRUNUID`` and serialises production on a file lock,
    so exactly one layout is produced per RUN and shared across every
    pytest-xdist worker -- this plugin's attribution is therefore across
    the run's consumers as a whole, not scoped to one worker's share of
    them. Like the routing plugin's own documented scope limit, the
    module-global state here (``_captured_record``, ``_consumer_count``,
    ``_offending_test``) is per OS PROCESS: under ``-n`` each xdist worker
    process evaluates and reports its own share independently. No test in
    this AC's own test_spec exercises ``-n`` against this reporting
    surface.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_coordination import (
    PUBLISHED_DIRNAME,
    check_published,
    run_base_dir,
)
from scripts.suite_performance._shared_layout_integrity_compare import (
    capture_record,
    compare_record,
)
from scripts.suite_performance.pytest_shared_reference_layout import READER_MARKER

__all__ = ["capture_record", "compare_record"]

_log = logging.getLogger(__name__)

# Env var naming the JSON file this plugin writes its ONE final report to, at
# pytest_sessionfinish. No-op (report not written to disk) when unset -- the
# session-failure behaviour below is NOT gated by this var; only the file
# write is.
INTEGRITY_REPORT_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT"

# ---------------------------------------------------------------------------
# Session-level state (module globals -- one set per pytest OS process; see
# the SCOPE note above for the xdist caveat).
# ---------------------------------------------------------------------------

_captured_record: dict | None = None
_shared_root: Path | None = None
_consumer_count = 0
_offending_test: str | None = None


def _published_path() -> Path:
    """Return the path the shared layout would be published to, if produced."""
    return run_base_dir() / PUBLISHED_DIRNAME


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    """Capture the baseline record right after the first reader's setup.

    Runs as a hookwrapper so the yielded-to default implementation (which
    resolves the test's fixtures, including ``shared_reference_layout`` for
    a reader-routed test) has already completed by the time this function
    resumes -- meaning any deploy the fixture triggered has already
    returned, and the record is captured before this test's own ``call``
    phase (its body) has run.

    Args:
        item: The pytest test item about to run.

    Yields:
        None (hookwrapper protocol).
    """
    yield
    global _captured_record, _shared_root  # noqa: PLW0603
    if _captured_record is not None:
        return
    if item.get_closest_marker(READER_MARKER) is None:
        return
    published = check_published(_published_path())
    if published is None:
        return
    _shared_root = published
    _captured_record = capture_record(published)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, None, None]:
    """Attribute a dirtying mutation to the first offending reader test.

    Re-compares the layout once after EACH ``shared_layout_reader``-marked
    consumer completes its own teardown, and records the first test whose
    comparison newly reports a difference as ``offending_test`` -- by node
    id, never overwritten once set, so a later clean or later-dirtying test
    cannot obscure the true first offender.

    Args:
        item: The pytest test item that just finished.

    Yields:
        None (hookwrapper protocol).
    """
    yield
    global _consumer_count, _offending_test  # noqa: PLW0603
    if item.get_closest_marker(READER_MARKER) is None:
        return
    _consumer_count += 1
    if _offending_test is not None:
        return
    if _captured_record is None or _shared_root is None:
        return
    report = compare_record(_shared_root, _captured_record)
    if not report["files_ok"]:
        _offending_test = item.nodeid


def _final_report() -> dict:
    """Return this session's final integrity report.

    At zero consumers, states so explicitly rather than reporting a clean
    comparison: ``compared_count`` is None (not 0), distinguishing "nothing
    to check" from "checked a real, unchanged layout" (this AC's
    2026-09-28 clause). This is deliberately NOT a failure -- at zero
    consumers TQ-600a-1-i requires that no layout be produced at all, so
    failing here would contradict that laziness guarantee.

    Returns:
        The report dict, shaped identically to ``compare_record``'s return
        value at consumer_count > 0.
    """
    if _consumer_count == 0:
        return {
            "compared_count": None,
            "added": [],
            "changed": [],
            "missing": [],
            "consumer_count": 0,
            "offending_test": None,
            "files_ok": True,
            "had_consumers": False,
        }
    if _captured_record is None or _shared_root is None:
        # Defensive: consumers ran but no baseline was ever captured (e.g.
        # the deploy never actually published). Fail loudly rather than
        # silently reporting clean over an unknown state.
        return {
            "compared_count": 0,
            "added": [],
            "changed": [],
            "missing": [],
            "consumer_count": _consumer_count,
            "offending_test": _offending_test,
            "files_ok": False,
            "had_consumers": True,
        }
    return compare_record(
        _shared_root,
        _captured_record,
        consumer_count=_consumer_count,
        offending_test=_offending_test,
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write the final report (if requested) and fail the run on a real diff.

    The session is failed (non-zero exit) when, and only when, ``files_ok``
    is False -- ``had_consumers`` being False must never by itself fail the
    session. This failure behaviour is unconditional; writing the JSON
    report to disk is the only part gated by
    ``LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT``.

    Args:
        session: The finishing pytest session.
        exitstatus: The exit status pytest computed before this hook ran
            (unused directly -- ``session.exitstatus`` is mutated instead,
            which is what pytest's process exit code is actually read from).
    """
    del exitstatus  # unused: session.exitstatus is the mutable source of truth
    report = _final_report()

    report_path_str = os.environ.get(INTEGRITY_REPORT_ENV_VAR)
    if report_path_str:
        try:
            Path(report_path_str).write_text(json.dumps(report), encoding="utf-8")
        except OSError as exc:
            _log.warning(
                "shared_layout_integrity: could not write report to %s: %s",
                report_path_str,
                exc,
            )

    if not report["files_ok"]:
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Announce a dirtied layout loudly, naming the offending test by node id.

    "The layout changed" alone is not an acceptable failure message -- this
    line is what lets a human (or a log-scraping tool) find the offender
    without reading the JSON report.

    Args:
        terminalreporter: pytest's terminal reporter plugin instance.
    """
    if _offending_test is not None:
        terminalreporter.write_line(
            f"shared-layout-integrity: DIRTIED by {_offending_test}"
        )
    elif _consumer_count > 0:
        terminalreporter.write_line(
            f"shared-layout-integrity: clean ({_consumer_count} consumer(s) checked)"
        )


# DECISION HISTORY
# ================================================================================
# - 2026-09-30 [python-coder]: Created shared_layout_integrity.py for
#   TQ-600a-3: a session-level pytest plugin built on capture_record/
#   compare_record (split into _shared_layout_integrity_compare.py to
#   respect the 400-line file-size limit and re-exported here).
#   pytest_runtest_setup captures the baseline right after the first
#   reader's fixture setup returns; pytest_runtest_teardown attributes the
#   first dirtying test; pytest_sessionfinish always evaluates files_ok and
#   fails the run independently of whether the diagnostic JSON report path
#   is set. Registered via an explicit -p override in every consuming test
#   AND additionally added to pytest.ini's addopts so the guard is not dead
#   code exercised only by its own test suite -- loading the same plugin
#   twice (addopts + explicit -p) is idempotent, mirroring the existing
#   routing-plugin precedent. (#TQ-600a-3)
