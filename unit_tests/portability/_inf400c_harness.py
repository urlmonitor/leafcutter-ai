"""
MODULE: Golden consumer-install harness for the INF-400c test family.
GOAL: Produce ONE real consumer-install build per process and hand every
    test a cheap, content-identical COPY of it, instead of each test paying
    its own ~60s build.py subprocess.
BUSINESS CONTEXT: Extracted from test_inf_400c_4_i.py under TQ-600a-9. It
    lives here rather than inline for two reasons: test_inf_400c_4_i.py is
    already over the 400-line file-size limit and this mechanism is what
    pushed it further over, and test_inf_400c_4_v.py needs the identical
    "one build, many copies" pattern, so a sibling harness is the shape this
    directory already uses for shared test machinery (see
    _bp1500g1_harness.py and _bp1500g2_harness.py).
ARCHITECTURE: _run_consumer_build() is the single call site every INF-400c
    test funnels its real deploy through, and the one place
    emit_execution_signal() is called -- so TQ-600a-9's build-subprocess
    counter sees every genuine build and nothing else.
    _golden_consumer_tree() memoises exactly one such build per process.
    _consumer_install_copy() hands out shutil.copytree copies of it.

WHY COPYING IS SAFE HERE, and the one exception. Every deployed file except
config/knowledge_sink.json is byte-identical regardless of which absolute
path the package was built into. knowledge_sink.json is the sole exception:
its content is a pure, deterministic function of target_dir's own absolute
path (see scripts/build_phases_knowledge.build_knowledge_sink_declaration).
So a copy is indistinguishable from an independent build for every test
except one -- the test asserting that two installs declare DIFFERENT sinks.
That test uses _consumer_install_copy_with_fresh_sink(), which re-derives
only that one file by calling the SAME real, unmocked production function
build.py itself calls, in-process. It does not run a second build.py.

Copies, never shared references (TQ-600a-9-i copy-on-write isolation): a
write through one test's tree can never reach the golden tree or a sibling
test's copy. Symlinks are preserved as symlinks, because .claude/skills is
a real deploy symlink and a copy that flattened it would be structurally
distinguishable from a genuine build.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.suite_performance._shared_layout_coordination import (
    emit_execution_signal,
)

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_CHECK_CONSUMER_INSTALL = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"
_BUILD_TIMEOUT_SECONDS = 180

_GOLDEN_CONSUMER_INSTALL: dict[str, Path] = {}


def deployed_root(target_dir: Path) -> Path:
    """Return the deployed-layout root inside a consumer install.

    Args:
        target_dir: The consumer project root a build was targeted at.

    Returns:
        The .leafcutter directory beneath it.
    """
    return target_dir / ".leafcutter"


def run_consumer_build(
    target_dir: Path,
    package_dir: Path = _WORKTREE_ROOT,
) -> subprocess.CompletedProcess[str]:
    """Run the REAL scripts/ci/check_consumer_install.py as a REAL subprocess.

    Shells out to the REAL scripts/build.py underneath -- no mocking of the
    build, the filesystem, or any of the four surfaces this AC repoints.
    Emits TQ-600a-9's build-subprocess signal (a no-op unless a test has
    pointed LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG at a scratch file), so
    the counter sees every genuine build. A mocked build is not a build.

    Args:
        target_dir: Consumer project root to install into.
        package_dir: Package checkout to install FROM.

    Returns:
        The completed subprocess, uninspected -- callers assert on it.
    """
    argv = [
        sys.executable,
        str(_CHECK_CONSUMER_INSTALL),
        "--package-dir", str(package_dir),
        "--target-dir", str(target_dir),
    ]
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
        check=False,
    )
    emit_execution_signal(target_dir)
    return result


def golden_consumer_tree() -> Path:
    """Produce, at most once per process, the ONE real consumer-install
    build this family's tests share.

    Returns:
        Path to the golden tree. Never hand this out directly to a test --
        use copy_consumer_install() so writes cannot reach it.

    Raises:
        AssertionError: If the one real build did not succeed, since every
            later test would otherwise fail against a broken fixture for
            reasons that have nothing to do with what they assert.
    """
    if "root" not in _GOLDEN_CONSUMER_INSTALL:
        golden_dir = Path(tempfile.mkdtemp(prefix="tq600a9_golden_consumer_install_")) / "project"
        golden_dir.mkdir()
        build_result = run_consumer_build(golden_dir)
        assert build_result.returncode == 0, (
            "Fixture setup failed: the one real golden consumer-install "
            f"build did not succeed.\nstdout:\n{build_result.stdout}\n"
            f"stderr:\n{build_result.stderr}"
        )
        _GOLDEN_CONSUMER_INSTALL["root"] = golden_dir
    return _GOLDEN_CONSUMER_INSTALL["root"]


def copy_consumer_install(target_dir: Path) -> None:
    """Materialize *target_dir* as a content-identical COPY of the golden
    tree -- never a shared reference.

    Args:
        target_dir: Destination, which must not already exist.
    """
    shutil.copytree(golden_consumer_tree(), target_dir, symlinks=True)


def copy_consumer_install_with_fresh_sink(target_dir: Path) -> None:
    """As copy_consumer_install(), plus re-deriving the ONE deployed file
    whose correct content depends on *target_dir*'s own absolute location.

    Used only by the test comparing two installs' declared sinks. See this
    module's docstring for why no second build.py run is needed.

    Args:
        target_dir: Destination, which must not already exist.
    """
    copy_consumer_install(target_dir)
    scripts_dir = str(_WORKTREE_ROOT / "scripts")
    inserted = scripts_dir not in sys.path
    if inserted:
        sys.path.insert(0, scripts_dir)
    try:
        from build_phases_knowledge import build_knowledge_sink_declaration

        build_knowledge_sink_declaration(
            deployed_root(target_dir), {}, dry_run=False, force=True
        )
    finally:
        if inserted:
            sys.path.remove(scripts_dir)
