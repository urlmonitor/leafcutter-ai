"""
Shared helpers for the TQ-600a-3 test file (``test_tq_600a_3.py``). Extracted
purely to keep the main test file under the repo's GE-127a-1 400-line
file-size limit — see ``test_tq_600a_3.py``'s module docstring for the full
"ASSUMED PRODUCTION CONTRACT" this whole test suite is pinned to (the
``shared_layout_integrity`` module's low-level functions, its pytest plugin
hooks, and its JSON report shape).

Builds on ``_test_helpers.py`` (TQ-600a-1's ``_WORKTREE_ROOT``,
``_SUITE_PERF_DIR``, ``_read_jsonl``, ``_write_consumer_test``,
``_rmtree_if_exists``) and ``_test_helpers_tq_600a_5.py`` (``READER_MARKER``),
reused here rather than duplicated.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from ._test_helpers import _SUITE_PERF_DIR, _WORKTREE_ROOT  # noqa: F401 - re-exported
from ._test_helpers_tq_600a_5 import READER_MARKER

# ---------------------------------------------------------------------------
# ASSUMED interface constants (see test_tq_600a_3.py's module docstring for
# the full rationale). python-coder implements against these exact names.
# ---------------------------------------------------------------------------

# Env var naming the JSON file the shared_layout_integrity plugin writes its
# ONE final report to, at pytest_sessionfinish. Mirrors the existing
# LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG / LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG
# env-var-gated convention from TQ-600a-1 / TQ-600a-5 -- the difference here
# is a single JSON object (one report per session), not a JSONL append log,
# because there is exactly one comparison per session, not one event per
# routing decision.
INTEGRITY_REPORT_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT"

# This AC's own files_touched names ONLY shared_layout_integrity.py -- it
# does not touch pytest.ini's addopts. So, unlike the routing plugin (which
# IS in addopts and therefore always active), every child session below
# loads this plugin via an EXPLICIT -p override, mirroring exactly how
# TQ-600a-1's and TQ-600a-5's own tests load plugins explicitly wherever
# addopts registration would be the wrong (or not-yet-true) thing to rely on.
_INTEGRITY_PLUGIN = "scripts.suite_performance.shared_layout_integrity"
_ROUTING_PLUGIN = "scripts.suite_performance.pytest_shared_reference_layout"

CHILD_SESSION_TIMEOUT_S = 300


def run_integrity_child_session(
    children_dir: Path,
    *,
    report_path: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a real child pytest session over *children_dir* with the
    shared_layout_integrity plugin explicitly loaded via -p, in addition to
    the routing plugin (already in pytest.ini's real addopts, but named
    explicitly too for clarity/robustness, mirroring
    run_child_session's force_register_plugin=True default).

    children_dir MUST live inside the worktree (e.g. under
    _SUITE_PERF_DIR), never under a bare tempfile.TemporaryDirectory:
    pytest's rootdir/inifile discovery walks up from the given path's own
    ancestry, not from `cwd` -- a /tmp-rooted child would never find this
    repo's pytest.ini and its real marker registration
    (`shared_layout_reader` / `--strict-markers`), silently defeating the
    real end-to-end routing this AC's integration tests depend on.
    """
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(children_dir),
        "-p",
        _ROUTING_PLUGIN,
        "-p",
        _INTEGRITY_PLUGIN,
        "-q",
    ]
    env = dict(os.environ)
    env[INTEGRITY_REPORT_ENV_VAR] = str(report_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        cwd=str(_WORKTREE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=CHILD_SESSION_TIMEOUT_S,
    )


def reader_consumer_source(test_name: str, body: str) -> str:
    """Source for a single ``shared_layout_reader``-marked test function
    named ``test_<test_name>``, binding ``root`` (a ``Path``) to the
    ``shared_reference_layout`` fixture's return value, followed by the
    dedented statements in *body*.
    """
    indented = textwrap.indent(textwrap.dedent(body).strip("\n") + "\n", "    ")
    return (
        "import pytest\n"
        "from pathlib import Path\n\n\n"
        f"@pytest.mark.{READER_MARKER}\n"
        f"def test_{test_name}(shared_reference_layout):\n"
        "    root = Path(shared_reference_layout)\n"
        f"{indented}"
    )


def read_report(report_path: Path) -> dict | None:
    """Return the parsed JSON integrity report, or None if never written."""
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))
