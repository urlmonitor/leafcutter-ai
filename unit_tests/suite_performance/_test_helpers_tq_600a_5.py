"""
Shared helpers + constants for the TQ-600a-5 test files:
``test_tq_600a_5.py`` (tests 1-5, the three-way routing cases) and
``test_tq_600a_5_reporting.py`` (tests 6-10, the reporting/registration/
reachability cases). Extracted so each test function stays short and each
file stays well under the repo's GE-127a-1 400-line file-size limit — see
``test_tq_600a_5.py``'s module docstring for the full "ASSUMED PRODUCTION
CONTRACT" both files are pinned to.

Builds on ``_test_helpers.py`` (the TQ-600a-1 helpers: ``_WORKTREE_ROOT``,
``_read_jsonl``, ``_write_consumer_test``, ``_rmtree_if_exists``), reused
here rather than duplicated.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ._test_helpers import _WORKTREE_ROOT, _read_jsonl  # noqa: F401 - re-exported

# ---------------------------------------------------------------------------
# ASSUMED interface constants (see test_tq_600a_5.py's module docstring for
# the full rationale). python-coder implements against these exact names.
# ---------------------------------------------------------------------------

READER_MARKER = "shared_layout_reader"
MUTATOR_MARKER = "shared_layout_mutator"

# Env var naming the JSONL file the routing selector appends one line to per
# routed test, plus one final "routing_summary" line at session finish.
# Mirrors the existing LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG convention
# from TQ-600a-1 (_shared_layout_coordination.EXECUTION_LOG_ENV_VAR).
ROUTING_LOG_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG"

PYTEST_INI_PATH = _WORKTREE_ROOT / "pytest.ini"

# Generous timeout: a child session below may trigger more than one real
# ~60s build.py subprocess (one shared + one or more private copies).
CHILD_SESSION_TIMEOUT_S = 300


def run_child_session(
    children_dir: Path,
    *,
    extra_args: list[str] | None = None,
    env_overrides: dict[str, str] | None = None,
    force_register_plugin: bool = True,
) -> subprocess.CompletedProcess:
    """Run a real child pytest session over *children_dir*.

    force_register_plugin=True (default) passes an explicit ``-p`` override
    for the shared-reference-layout plugin, matching TQ-600a-1's tests 1-6
    convention. Set False only for a reachability test that must rely on
    the real, un-augmented pytest.ini registration surface (mirroring
    TQ-600a-1's test 7 / test_tq_600a_1_reachable_from_entry_point).
    """
    cmd = [sys.executable, "-m", "pytest", str(children_dir)]
    if force_register_plugin:
        cmd += ["-p", "scripts.suite_performance.pytest_shared_reference_layout"]
    cmd += (extra_args or []) + ["-q"]
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd,
        cwd=str(_WORKTREE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=CHILD_SESSION_TIMEOUT_S,
    )


def direct_root_source(out_name: str) -> str:
    """Source for a test that calls the low-level function directly (no
    fixture, no marker) and writes the resulting root path to RESULT_DIR.
    This is the "known-shared" reference point every routing test compares
    a fixture-handed root against."""
    lines = [
        "import os",
        "from pathlib import Path",
        "from scripts.suite_performance._shared_layout_producer import (",
        "    get_or_produce_shared_layout,",
        ")",
        "",
        "def test_direct_shared_root():",
        "    root = get_or_produce_shared_layout()",
        f'    out = Path(os.environ["RESULT_DIR"]) / "{out_name}"',
        "    out.write_text(str(root))",
    ]
    return "\n".join(lines) + "\n"


def consumer_source(
    test_name: str,
    out_name: str,
    marker: str | None = None,
    *,
    also_assert_exists: bool = False,
) -> str:
    """Source for a test that requests the ``shared_reference_layout``
    fixture, optionally declared via *marker* (None = undeclared), and
    writes the handed-back root path to RESULT_DIR.

    also_assert_exists=True additionally asserts the root is a real,
    existing directory containing scripts/build.py -- the "result consumed
    in control flow" shape the reachability angle requires.
    """
    lines = ["import os", "from pathlib import Path"]
    if marker:
        lines += ["import pytest", "", f"@pytest.mark.{marker}"]
    lines.append(f"def test_{test_name}(shared_reference_layout):")
    if also_assert_exists:
        lines.append("    root = Path(shared_reference_layout)")
        lines.append('    assert (root / "scripts" / "build.py").exists()')
    lines.append(f'    out = Path(os.environ["RESULT_DIR"]) / "{out_name}"')
    lines.append("    out.write_text(str(shared_reference_layout))")
    return "\n".join(lines) + "\n"


def read_root(result_dir: Path, out_name: str) -> str:
    return (result_dir / out_name).read_text(encoding="utf-8")


def find_routing_summary(entries: list[dict]) -> dict | None:
    """Return the last "routing_summary" event in *entries*, if any."""
    for entry in reversed(entries):
        if entry.get("event") == "routing_summary":
            return entry
    return None
