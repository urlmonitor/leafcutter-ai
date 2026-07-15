"""
MODULE: pytest_ac_enforcement
GOAL: Pytest plugin that converts failing tests covering not-done ACs to
    informational (xfail) outcomes, preventing them from blocking the run.
BUSINESS CONTEXT: A test that covers an AC whose work_status is not "done"
    must never fail the CI run — the feature is in progress and the test is
    expected to fail until the AC is complete.  The test is still visible in
    the output so the team can track its progress.
ARCHITECTURE: Registered as a pytest plugin via pytest.ini addopts
    ``-p scripts.ac_store.pytest_ac_enforcement``.  This ensures the plugin
    loads for ANY pytest invocation that uses the project pytest.ini,
    regardless of where the test files live — including subprocess invocations
    with ``--config-file=<repo_root>/pytest.ini`` pointing at temp directories.

    The plugin calls :mod:`scripts.ac_store.test_enforcement` for the pure
    classification logic.  The AC store root is read from the environment
    variable ``LEAFCUTTER_AC_STORE_ROOT`` (set by tests that inject a synthetic
    store); if absent, falls back to ``docs/acceptance-criteria/`` relative to
    this file's directory.

    Outcome conversion:
      - A failing ``call``-phase test whose ``# covers: <AC-ID>`` tag points at
        an AC with work_status != "done" has its report ``outcome`` set to
        ``"xfailed"`` with a ``wasxfail`` attribute so pytest shows XFAIL.
      - All other tests are unaffected.

    Safety guarantees (BP-audit stage 5 — anti-silent-masking):
      - A failure covering an AC whose work_status **is** ``"done"`` is NEVER
        masked — it surfaces as a hard failure (a regression in shipped work).
        Unknown / absent ACs are likewise enforced (fail-safe). This partition
        is decided by :func:`scripts.ac_store.test_enforcement.classify_by_work_status`.
      - Masking is **loud, never silent**: every downgrade prints a per-test
        line during the run AND an end-of-session summary
        (:func:`pytest_terminal_summary`) naming the masked-failure count and the
        AC ids, so a masked regression can never hide behind a green suite.
      - Masking is **opt-out**: set the environment variable ``AC_ENFORCE_STRICT``
        to a truthy value (``1``/``true``/``yes``/``on``) to disable masking
        entirely — every AC-tagged failure then surfaces as a real failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Session-level state (module globals — one per pytest process)
# ---------------------------------------------------------------------------

_ac_cache: dict[str, str] | None = None
_cache_built: bool = False

# Records every failure that was downgraded to xfail this session as
# (nodeid, ac_id) tuples, so pytest_terminal_summary can announce them loudly.
_masked_failures: list[tuple[str, str]] = []

# Truthy tokens for the AC_ENFORCE_STRICT opt-out switch.
_STRICT_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _strict_mode_enabled() -> bool:
    """Return True when masking is disabled via ``AC_ENFORCE_STRICT``.

    When enabled, every AC-tagged failure surfaces as a real failure — no
    outcome is ever downgraded to xfail, regardless of the covered AC's
    work_status.

    Returns:
        True when the ``AC_ENFORCE_STRICT`` env var holds a truthy token
        (``1``/``true``/``yes``/``on``, case-insensitive); False otherwise.
    """
    return os.environ.get("AC_ENFORCE_STRICT", "").strip().lower() in _STRICT_TRUTHY


def _emit_terminal_line(config: pytest.Config, message: str) -> None:
    """Write *message* to the terminal, loudly and unconditionally.

    Prefers pytest's terminal reporter so the line lands in the captured
    terminal output; falls back to stderr when the reporter is unavailable
    (e.g. ``-p no:terminal``).

    Args:
        config: The active pytest config (source of the terminal reporter).
        message: The line to emit.
    """
    reporter = None
    try:
        reporter = config.pluginmanager.get_plugin("terminalreporter")
    except (AttributeError, ValueError) as exc:  # pragma: no cover - defensive
        print(
            f"WARNING: pytest_ac_enforcement: cannot access terminalreporter: {exc}",
            file=sys.stderr,
        )
        reporter = None

    if reporter is not None:
        try:
            reporter.write_line(message)
        except (AttributeError, OSError) as exc:  # pragma: no cover - defensive
            print(
                f"WARNING: pytest_ac_enforcement: terminalreporter write failed: {exc}",
                file=sys.stderr,
            )
        else:
            return

    print(message, file=sys.stderr)


def _get_enforcement():
    """Import and return the test_enforcement module.

    Returns:
        The scripts.ac_store.test_enforcement module.

    Raises:
        ImportError: When the module cannot be found on sys.path.
    """
    from scripts.ac_store import test_enforcement  # noqa: PLC0415
    return test_enforcement


def _resolve_ac_store_root() -> Path:
    """Resolve the AC store root directory.

    Checks ``LEAFCUTTER_AC_STORE_ROOT`` environment variable first, then
    falls back to ``docs/acceptance-criteria/`` relative to this module.

    Returns:
        Absolute path to the AC store root.
    """
    env_root = os.environ.get("LEAFCUTTER_AC_STORE_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent.parent / "docs" / "acceptance-criteria"


def _get_ac_cache() -> dict[str, str]:
    """Return the session-scoped AC work_status cache, built on first call.

    Returns:
        Dict mapping AC id → work_status string.
    """
    global _ac_cache, _cache_built  # noqa: PLW0603
    if not _cache_built:
        try:
            enforcement = _get_enforcement()
            ac_root = _resolve_ac_store_root()
            _ac_cache = enforcement.build_ac_work_status_cache(ac_root)
        except ImportError as exc:
            print(
                f"WARNING: pytest_ac_enforcement: cannot import test_enforcement: {exc}",
                file=sys.stderr,
            )
            _ac_cache = {}
        _cache_built = True
    return _ac_cache or {}


# ---------------------------------------------------------------------------
# pytest hook
# ---------------------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, pytest.TestReport, None]:
    """Convert failing tests covering not-done ACs to xfail outcomes.

    For each test that fails during the ``call`` phase:
      1. Extracts the ``# covers: <AC-ID>`` tag from the test function source.
      2. Looks up the AC's work_status in the session cache.
      3. If classified as ``"informational"`` (work_status != ``"done"``),
         rewrites the report ``outcome`` to ``"xfailed"`` so pytest does not
         count the test as a run failure.

    Args:
        item: The pytest test item being reported on.
        call: The call-phase info object (phase: setup / call / teardown).

    Yields:
        None (hookwrapper protocol — delegates to inner hooks, then post-processes).
    """
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    # Only intercept actual test-call failures (not setup/teardown).
    if report.when != "call" or report.outcome != "failed":
        return

    try:
        enforcement = _get_enforcement()
    except ImportError as exc:
        print(
            f"WARNING: pytest_ac_enforcement: cannot import test_enforcement: {exc}",
            file=sys.stderr,
        )
        return

    ac_id = enforcement.extract_covers_tag(item)
    if ac_id is None:
        return

    cache = _get_ac_cache()
    classification = enforcement.classify_by_work_status(ac_id, cache)
    if classification != "informational":
        # AC is done (or absent → fail-safe enforcement): this is a real
        # regression in shipped work. NEVER mask it — let it fail hard.
        return

    # The covered AC is not done. Masking a not-yet-implemented AC's failure is
    # the TDD-convenience default, but it must never be SILENT and it must be
    # possible to turn off entirely.
    if _strict_mode_enabled():
        # Opt-out: surface every AC-tagged failure as a real failure.
        _emit_terminal_line(
            item.config,
            f"AC-ENFORCEMENT [STRICT]: {item.nodeid} covers not-done AC "
            f"{ac_id} — NOT masked (AC_ENFORCE_STRICT=1); reported as a real "
            f"failure.",
        )
        return

    # Downgrade to xfail so pytest does not count this as a run failure — but
    # record it and announce it loudly so a masked regression can never hide.
    report.outcome = "xfailed"
    report.wasxfail = (
        f"AC {ac_id} work_status is not done — test is informational"
    )
    _masked_failures.append((item.nodeid, ac_id))
    _emit_terminal_line(
        item.config,
        f"AC-ENFORCEMENT [MASKED FAILURE]: {item.nodeid} covers AC {ac_id} "
        f"(work_status != done) — downgraded to xfail. Set AC_ENFORCE_STRICT=1 "
        f"to treat this as a real failure.",
    )


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Emit an end-of-session summary naming every masked AC-tagged failure.

    A masked failure (a genuinely-red test downgraded to xfail because its
    covered AC is not done) must be impossible to miss. This hook prints a
    loud, red separator plus one line per masked failure at the very end of
    the run, so the count and the AC ids are surfaced even in a "passing" run.

    Args:
        terminalreporter: pytest's terminal reporter (writes to the terminal).
        exitstatus: The session exit status (unused; part of the hook contract).
        config: The active pytest config (unused; part of the hook contract).
    """
    if not _masked_failures:
        return

    ac_ids = sorted({ac_id for _, ac_id in _masked_failures})
    terminalreporter.write_sep(
        "=", "AC ENFORCEMENT: MASKED FAILURES", red=True, bold=True
    )
    terminalreporter.write_line(
        f"AC-ENFORCEMENT SUMMARY: {len(_masked_failures)} AC-tagged failure(s) "
        f'were masked (downgraded to xfail) because their AC work_status != "done": '
        f"{', '.join(ac_ids)}. "
        f"Set AC_ENFORCE_STRICT=1 to surface them as real failures."
    )
    for nodeid, ac_id in _masked_failures:
        terminalreporter.write_line(f"  - {nodeid}  [AC {ac_id}]")
