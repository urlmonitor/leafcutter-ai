"""
MODULE: pytest_shared_reference_layout
GOAL: Pytest plugin exposing the ``shared_reference_layout`` fixture -- a
    single, real deployed copy of this package produced once for the whole
    run (lazily, on first demand) and shared, cross-process-safely, across
    every READER-DECLARED consumer test. A MUTATOR-declared or UNDECLARED
    consumer instead receives its own fresh, private, unshared copy
    (TQ-600a-5's per-test routing selector).
BUSINESS CONTEXT: TQ-600a-1 built the one shared layout. TQ-600a-5 -- "A
    test that has not said which kind it is gets the safe kind" -- adds the
    routing selector this module now implements. See CLAUDE.md's "Tests
    must not spawn their own build.py" rule for the read-vs-mutate boundary
    this selector enforces mechanically: a test that never declares itself
    must not be trusted with the one shared root, because an undeclared
    test might, in fact, be a mutator.
ARCHITECTURE: Registered as a pytest plugin via pytest.ini's addopts
    ``-p scripts.suite_performance.pytest_shared_reference_layout``,
    mirroring the existing whole-suite-loaded precedent
    ``-p scripts.ac_store.pytest_ac_enforcement``. This is the LOAD-BEARING
    registration: this repo has no root conftest.py and no
    unit_tests/conftest.py, so a per-directory conftest.py is invisible
    outside its own directory -- registering here instead of there is what
    makes the fixture reachable from every test file, not just one
    directory's worth.

    TQ-600a-5's own files_touched names only this plugin file and
    pytest.ini -- no new fixture name, no new module -- so the routing
    selector lives inside the fixture that already exists, and the two
    registered marker names (``shared_layout_reader`` /
    ``shared_layout_mutator``) are registered in pytest.ini's own
    ``[pytest] markers =`` section (never here via
    ``config.addinivalue_line``), because this AC's own marker-registration
    test, and TQ-600a-8's later examination, both read pytest.ini's text
    directly.

    Routing is decided PURELY from the requesting test item's own marker
    metadata (``request.node.get_closest_marker``), at fixture-request
    time, WITHOUT ever importing or executing the test body and WITHOUT
    ever consulting the test's file name or directory -- see
    ``_select_route`` below for the one and only place that decision is
    made. Keying routing on a filename glob (e.g. the historical
    ``test_bp_900g_8*`` mutator proxy documented in the root CLAUDE.md) is
    the specific defect this AC exists to prevent: that glob was only ever
    a proxy for the mutators known at authoring time, never a verified
    complete set.

    A MUTATOR-declared test is always given a fresh, private copy of its
    own -- never the shared root, and never cached or reused across
    requesters, because a mutator is expected to alter the package before
    building (TQ-600a-2's isolation guarantee, not yet built) and sharing
    its copy with any other requester would corrupt that other requester's
    result. An UNDECLARED test takes the identical private-copy path for
    the identical reason: an undeclared test's true nature is unknown, so
    it is treated as though it might mutate -- fail-safe, never fail-fast
    (Implementation Notes point 2): it still runs and still passes, it is
    merely handed the safe (unshared) root instead of the fast (shared)
    one, and is named -- loudly, by node id -- in both the JSONL routing
    log (env var ``LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG``, no-op if unset)
    and the console summary (``pytest_terminal_summary``), alongside a
    running count that gives the 77-site TQ-600 migration a progress
    measure. That count (``undeclared_count``) is reported ALONGSIDE, and
    never merged into, the separately-named ``declared_mutator_count`` --
    TQ-600a-6's amended bound (``reported_deploys <= 1 + declared_mutators``)
    reads only the latter; folding the former in would silently widen that
    bound back to its pre-2026-09-28 shape.

    All production/locking/caching logic for the ONE shared root lives in
    ``_shared_layout_producer.py`` and ``_shared_layout_coordination.py``
    (split out to respect the project's file-size limit); this module adds
    the routing selector, the private-copy production path, and the
    JSONL/console reporting -- all confined to this one file per this AC's
    own files_touched list, deliberately not reaching into
    ``_shared_layout_producer.py``'s private helpers. ``get_or_produce_shared_layout``
    and ``SharedReferenceLayoutError`` are re-exported here so a caller that
    imports this plugin module directly (as the low-level tests in
    unit_tests/suite_performance/test_tq_600a_1.py do) can reach them
    without also importing the private helper modules.

    KNOWN SCOPE LIMIT: the per-session console/JSONL summary counts
    (``declared_mutator_count`` / ``undeclared_count``) are process-local
    module globals, so under pytest-xdist (``-n``) each worker reports only
    its own share -- no test in this AC's own test_spec exercises ``-n``
    against this reporting surface, so this is an accepted, undocumented-
    elsewhere scope limit rather than a defect this ticket is responsible
    for closing.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_coordination import (
    emit_execution_signal,
)
from scripts.suite_performance._shared_layout_producer import (
    SharedReferenceLayoutError,
    get_or_produce_shared_layout,
)

__all__ = [
    "MUTATOR_MARKER",
    "READER_MARKER",
    "ROUTING_LOG_ENV_VAR",
    "SharedReferenceLayoutError",
    "get_or_produce_shared_layout",
    "shared_reference_layout",
]

_log = logging.getLogger(__name__)

# Registered in pytest.ini's own [pytest] markers = section (never via
# config.addinivalue_line here) -- see the ARCHITECTURE note above.
READER_MARKER = "shared_layout_reader"
MUTATOR_MARKER = "shared_layout_mutator"

# Env var naming the JSONL file the routing selector appends one line to,
# per routed test, plus one final "routing_summary" line at session finish.
# No-op when unset, mirroring the existing
# LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG convention from TQ-600a-1.
ROUTING_LOG_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG"

# scripts/suite_performance/pytest_shared_reference_layout.py -> parents[2]
# == worktree root (the same computation _shared_layout_producer.py makes
# for its own _WORKTREE_ROOT; duplicated rather than imported so this AC's
# routing logic stays entirely inside this one file, per its own
# files_touched list).
#
# The same override as the producer's (see its SOURCE_ROOT_ENV_VAR): set only by the post-merge
# fix proof's child session so the code under test, not main's checkout, is what gets deployed;
# unset or empty, this is the computation above, unchanged.
_WORKTREE_ROOT = Path(os.environ.get("LEAFCUTTER_SHARED_LAYOUT_SOURCE_ROOT") or Path(__file__).resolve().parents[2])

# Generous timeout for the real ~60s private-copy deploy subprocess (see
# TQ-600.yaml's measured deploy cost).
_PRIVATE_DEPLOY_SUBPROCESS_TIMEOUT_S = 240

# Excluded when copying this repository into a private staging directory --
# mirrors _shared_layout_producer._EXCLUDED_NAMES (VCS metadata, prior
# build outputs, caches; none are part of the deployable source).
_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        ".claude",
        ".leafcutter",
        ".leafcutter.lock",
        ".agents",
        "debugging",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".env",
        ".gemini",
        ".pre-commit-config.yaml",
        ".build_manifest.json",
        ".venv",
        "venv",
    }
)

# ---------------------------------------------------------------------------
# Session-level state (module globals -- one set per pytest OS process; see
# the KNOWN SCOPE LIMIT note above for the xdist caveat).
# ---------------------------------------------------------------------------

_declared_mutator_count = 0
_undeclared_count = 0
_undeclared_nodeids: list[str] = []


def _select_route(node: pytest.Item) -> str:
    """Return ``"reader"``, ``"mutator"``, or ``"undeclared"`` for *node*.

    Decided purely from the requesting test item's own registered marker
    metadata -- NEVER from its file name or directory (Implementation Notes
    point 5; this is the exact defect the anti-glob NAMED MUTATION test
    exists to catch). A test carrying both markers is routed as a mutator:
    the mutator guarantee (never hand out the shared root) must win over
    the reader declaration's convenience.

    Args:
        node: The requesting test item (``request.node``).

    Returns:
        One of ``"reader"``, ``"mutator"``, ``"undeclared"``.
    """
    if node.get_closest_marker(MUTATOR_MARKER) is not None:
        return "mutator"
    if node.get_closest_marker(READER_MARKER) is not None:
        return "reader"
    return "undeclared"


def _append_jsonl(entry: dict) -> None:
    """Append one JSON line to the routing log, if the env var names a file.

    No-op when ``LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG`` is unset -- the same
    env-var-gated no-op shape as ``emit_execution_signal`` from TQ-600a-1, so
    this instrumentation is invisible to a real (non-instrumented) run. This
    is a SEPARATE log from ``emit_execution_signal``'s: this one records
    routing decisions (which route a test took), while
    ``emit_execution_signal`` -- called directly by ``_produce_private_copy``
    below -- records that a real ``build.py`` deploy subprocess executed.
    Both are appended for every private-copy production.

    Args:
        entry: A JSON-serialisable mapping to append as one line.
    """
    log_path_str = os.environ.get(ROUTING_LOG_ENV_VAR)
    if not log_path_str:
        return
    try:
        with open(log_path_str, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        _log.warning("could not append routing entry to %s: %s", log_path_str, exc)


def _produce_private_copy() -> Path:
    """Produce and return a fresh, private, unshared copy of the package.

    Used for both the MUTATOR and UNDECLARED routes: never the shared root,
    never cached or reused across requesters -- each call produces its own
    independent staging directory and runs its own real
    ``build.py --target-dir`` subprocess against it, mirroring the status
    quo every non-migrated test already pays for itself today (e.g.
    ``unit_tests/test_bp_900g_8*.py``'s own build.py invocation).

    Calls ``emit_execution_signal`` exactly when the subprocess really ran
    (normal completion or timeout-after-launch), never when it could not be
    started at all -- the identical placement and contract
    ``_shared_layout_producer._run_build_subprocess`` uses for the shared
    route, so a real deploy on this (private) route is recorded in the same
    execution log a caller like
    unit_tests/suite_performance/test_tq_600a_1.py already reads, instead of
    being invisible to it.

    Returns:
        The absolute path to the freshly deployed, private package root.

    Raises:
        SharedReferenceLayoutError: on any copy, deploy, or completeness
            failure.
    """
    staging_parent = Path(tempfile.mkdtemp(prefix="leafcutter-unshared-layout-"))
    staging = staging_parent / "layout"
    try:
        shutil.copytree(
            _WORKTREE_ROOT,
            staging,
            symlinks=True,
            ignore=shutil.ignore_patterns(*_EXCLUDED_NAMES),
        )
    except OSError as exc:
        raise SharedReferenceLayoutError(
            "could not copy source tree for a private unshared layout copy "
            f"from {_WORKTREE_ROOT} to {staging}: {exc}"
        ) from exc

    build_script = staging / "scripts" / "build.py"
    cmd = [sys.executable, str(build_script), "--target-dir", str(staging)]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, internal tool
            cmd,
            cwd=str(staging),
            capture_output=True,
            text=True,
            timeout=_PRIVATE_DEPLOY_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        emit_execution_signal(staging)  # the process really ran, just too long
        _log.warning(
            "private unshared layout deploy subprocess timed out: %s", exc
        )
        raise SharedReferenceLayoutError(
            f"private unshared layout deploy subprocess {cmd!r} timed out "
            f"after {_PRIVATE_DEPLOY_SUBPROCESS_TIMEOUT_S}s: {exc}"
        ) from exc
    except (subprocess.SubprocessError, OSError) as exc:
        raise SharedReferenceLayoutError(
            f"private unshared layout deploy subprocess {cmd!r} could not "
            f"be run: {exc}"
        ) from exc

    emit_execution_signal(staging)

    if result.returncode != 0:
        raise SharedReferenceLayoutError(
            f"private unshared layout deploy subprocess {cmd!r} exited "
            f"{result.returncode}:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    manifest = staging / ".build_manifest.json"
    if not manifest.exists():
        raise SharedReferenceLayoutError(
            "private unshared layout deploy subprocess exited 0 but "
            f"{manifest} is missing -- refusing to hand out an incomplete layout"
        )
    return staging


@pytest.fixture
def shared_reference_layout(request: pytest.FixtureRequest) -> Path:
    """Return the path to a deployed package root, routed by declaration.

    Function-scoped (re-evaluated per requesting test) so each test's OWN
    marker can be read and acted on independently -- a session-scoped
    fixture would compute one return value for the whole run and could
    never distinguish a reader's request from a mutator's. This does not
    reintroduce the per-test deploy cost TQ-600a-1 exists to avoid for
    READERS: ``get_or_produce_shared_layout()`` is itself cross-process-
    cached, so every reader-routed call after the first real deploy returns
    the identical cached root immediately.

    Routing (``_select_route``, decided from ``request.node``'s own marker
    metadata only):
      - ``shared_layout_reader`` -> the one real shared reference layout.
      - ``shared_layout_mutator`` -> a fresh private copy, never shared.
      - neither (undeclared) -> the identical private-copy path as a
        mutator (fail-safe default), additionally counted and named by
        node id in the routing log and console summary.

    Args:
        request: The requesting test's fixture request, whose ``node``
            carries any ``shared_layout_reader`` / ``shared_layout_mutator``
            marker.

    Returns:
        The absolute path to a deployed, complete package root -- the
        shared one for a declared reader, a fresh private one otherwise.

    Raises:
        SharedReferenceLayoutError: when the routed production fails.
    """
    global _declared_mutator_count, _undeclared_count  # noqa: PLW0603

    route = _select_route(request.node)
    nodeid = request.node.nodeid

    if route == "reader":
        root = get_or_produce_shared_layout()
        _append_jsonl({"event": "routed_shared_reader", "nodeid": nodeid})
        return root

    if route == "mutator":
        _declared_mutator_count += 1
        _append_jsonl({"event": "routed_unshared_mutator", "nodeid": nodeid})
        return _produce_private_copy()

    # Undeclared: safe default (fail-safe, not fail-fast) -- the test still
    # runs and still passes; it is merely routed unshared and named, loudly.
    _undeclared_count += 1
    _undeclared_nodeids.append(nodeid)
    _append_jsonl({"event": "routed_unshared_undeclared", "nodeid": nodeid})
    return _produce_private_copy()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Announce every undeclared-routed test by node id, loudly, at session
    finish, plus a summary line -- and append the matching JSONL summary.

    ``terminalreporter.write_line`` writes directly to the terminal,
    bypassing pytest's per-test output capture, so an undeclared test that
    PASSES (the fail-safe, not fail-fast, contract) is still visible here:
    a passing test's captured stdout is normally never shown at all.

    Args:
        terminalreporter: pytest's terminal reporter plugin instance,
            injected by the ``pytest_terminal_summary`` hook.
    """
    for nodeid in _undeclared_nodeids:
        terminalreporter.write_line(f"shared-layout-routing: UNDECLARED {nodeid}")
    terminalreporter.write_line(
        f"shared-layout-routing: declared_mutators={_declared_mutator_count} "
        f"undeclared={_undeclared_count}"
    )
    _append_jsonl(
        {
            "event": "routing_summary",
            "declared_mutator_count": _declared_mutator_count,
            "undeclared_count": _undeclared_count,
        }
    )


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 19:14 [python-coder]: Created the shared_reference_layout
#   pytest fixture/plugin for TQ-600a-1 and registered it in pytest.ini's
#   addopts (mirroring the existing
#   `-p scripts.ac_store.pytest_ac_enforcement` precedent) so it is reachable
#   from a plain, un-augmented pytest invocation over any test in the suite
#   -- registering it only in a per-directory conftest.py would have been
#   invisible outside that one directory, since this repo has no root
#   conftest.py and no unit_tests/conftest.py. (#TQ-600a-1)
# - 2026-09-29 [python-coder]: TQ-600a-5 -- added the marker-based routing
#   selector (`_select_route`, read from `request.node.get_closest_marker`
#   only -- never the test's file name or directory), the private-copy
#   production path (`_produce_private_copy`, never cached/reused across
#   requesters) for declared mutators and undeclared tests, and the
#   JSONL/console routing report with its two separately-named counts
#   (`declared_mutator_count` / `undeclared_count`, deliberately never
#   merged -- see TQ-600a-6's amended bound). Changed the fixture from
#   `scope="session"` to function-scoped: routing must be decided per
#   requesting test, which a session-scoped fixture's single cached return
#   value cannot do; `get_or_produce_shared_layout()`'s own cross-process
#   cache keeps the reader path just as cheap as before. KNOWN REGRESSION
#   (flagged, not silently fixed): TQ-600a-1's and
#   TQ-600a-1-multiworker's tests that spawn MULTIPLE unmarked consumer
#   tests in one session and assert they collapse onto one shared deploy /
#   identical root now fail, because those consumers are UNDECLARED under
#   this AC and each correctly receives its own private, uncached copy --
#   see this ticket's sign-off comment for the full list and the
#   recommended test-writer follow-up (add `shared_layout_reader` to each
#   affected consumer_body template). (#TQ-600a-5)
# - 2026-09-29 [python-coder]: Production defect fix -- `_produce_private_copy`
#   ran a real `build.py --target-dir` subprocess for the MUTATOR and
#   UNDECLARED routes but never called `emit_execution_signal`, so every
#   private deploy was invisible to the execution log
#   (`LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG`) that TQ-600a-6's deploy-count
#   emitter and TQ-600a-2's `reported_deploys <= 1 + declared_mutators` bound
#   both read. Imported `emit_execution_signal` from
#   `_shared_layout_coordination` (the same module
#   `_shared_layout_producer.py` reaches it from) and call it after a
#   successful subprocess run, mirroring
#   `_shared_layout_producer._run_build_subprocess`'s placement exactly:
#   once on normal completion (any exit code) and once on
#   `subprocess.TimeoutExpired` (the process really ran, just too long),
#   never when the subprocess could not be started at all. Corrected
#   `_append_jsonl`'s docstring, which described `emit_execution_signal`
#   only as historical precedent for its own no-op shape while the module
#   never actually called it -- it now also documents the two logs as
#   separate and both populated by `_produce_private_copy`. (#TQ-600a-5)
