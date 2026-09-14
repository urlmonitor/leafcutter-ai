"""
MODULE: test_inf_400c_5_h1_deployed_layout
GOAL: Regression test for the H-1 fast-lane pr-review finding on AC
    INF-400c-5: ``scripts/knowledge/emit_knowledge.py``,
    ``scripts/knowledge/entry_kind_vocabulary.py``, and
    ``config/entry_kind_vocabulary.json`` were authored but never added to
    any ``build.py`` deploy manifest, so a real build silently omitted all
    three from the deployed layout.
AC: INF-400c-5 (source_ac), H-1 fix

WHY THIS TEST EXISTS (fast-lane pr-review finding, 2026-09-14): the
INF-400c-5/-i/-iii fast-lane build passed 120/120 green tests while shipping
this exact gap. Every pre-existing test in this suite resolves
``scripts/knowledge/emit_knowledge.py``, ``entry_kind_vocabulary.py``, and
``config/entry_kind_vocabulary.json`` via ``_REPO_ROOT`` (the SOURCE tree,
e.g. ``test_inf_400c_5.py``'s ``_EMIT_SCRIPT = _REPO_ROOT / "scripts" /
"knowledge" / "emit_knowledge.py"``) -- never through a deployed
``target_root``. So 120 green tests proved nothing about a deployed install:
after any real ``python scripts/build.py --target-dir <project>`` run, the
moment a shipped emit surface invoked ``emit_knowledge.py`` it would fail on
a missing file; deploying the script without its sibling module would
ImportError; deploying both without the JSON config would make
``load_vocabulary()`` return ``{}`` and reject every ``entry_kind``.

This test closes that blind spot by running a REAL ``build.py`` subprocess
against a temp copy of the package (never the source tree in place -- see
``_copy_package_tree``'s docstring) and asserting the deployed files exist
on disk AND that the DEPLOYED ``emit_knowledge.py`` (invoked from its
deployed path, not ``_REPO_ROOT``) actually runs and writes a valid event.
A manifest grep would have passed on a manifest nothing consulted; only a
real build proves the fix.
"""
# @ac-tag: INF-400c-5

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_COPY_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".next"
)

_TIMEOUT_SECONDS = 180


def _copy_package_tree(dest: Path) -> Path:
    """Copy the whole package tree into *dest*, excluding ``.git``.

    Mirrors ``unit_tests/test_bp_900g_8_ii.py``'s TEMP-COPY DISCIPLINE:
    excluding ``.git`` makes the copy a non-git directory, so
    ``build.py``'s ``_check_tracked_source_guard`` gracefully no-ops (its
    documented "not a git repository" skip) instead of blocking on these
    still-uncommitted fast-lane-build artefacts -- exactly the behaviour a
    genuine non-git consumer install (tarball/pip/vendored, per ADR-001)
    already exercises, so nothing about the deploy phases under test is
    weakened by copying this way. Never mutates ``_REPO_ROOT`` itself.
    """
    shutil.copytree(_REPO_ROOT, dest, ignore=_COPY_IGNORE, symlinks=True)
    return dest


def test_build_deploys_all_three_h1_knowledge_artefacts_and_emit_knowledge_runs(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5
    # angle: reachability (H-1 fast-lane pr-review fix)
    """A real ``build.py --target-dir <tmp>`` run must deploy
    ``scripts/knowledge/emit_knowledge.py``,
    ``scripts/knowledge/entry_kind_vocabulary.py``, AND
    ``config/entry_kind_vocabulary.json`` -- not merely list them in a
    manifest a grep could pass on a manifest never consulted. Then the
    DEPLOYED ``emit_knowledge.py`` (invoked from its deployed location, not
    the source tree) must actually run and accept a valid ``entry_kind``,
    proving its sibling-module import and its vocabulary-config read both
    resolve correctly against the deployed layout.

    Pre-H-1-fix, this test is RED three ways: the two deploy assertions on
    ``deployed_emit`` / ``deployed_vocab_module`` fail outright (files never
    copied), and even if only the manifest were partially fixed, the
    subprocess invocation would fail (missing sibling import, or an empty
    vocabulary rejecting the ``"adr"`` entry_kind).
    """
    copy_root = tmp_path / "pkg_copy"
    _copy_package_tree(copy_root)

    target_dir = tmp_path / "deployed_install"
    result = subprocess.run(
        [sys.executable, str(copy_root / "scripts" / "build.py"), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        cwd=str(copy_root),
        check=False,
    )
    assert result.returncode == 0, (
        f"build.py exited non-zero.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    output_root = target_dir / ".leafcutter"
    deployed_emit = output_root / "scripts" / "knowledge" / "emit_knowledge.py"
    deployed_vocab_module = output_root / "scripts" / "knowledge" / "entry_kind_vocabulary.py"
    deployed_vocab_config = output_root / "config" / "entry_kind_vocabulary.json"

    assert deployed_emit.is_file(), (
        "build.py did not deploy scripts/knowledge/emit_knowledge.py -- this "
        "is the exact H-1 gap: a shipped emit surface invoking this script "
        "would fail with 'No such file or directory'."
    )
    assert deployed_vocab_module.is_file(), (
        "build.py did not deploy scripts/knowledge/entry_kind_vocabulary.py "
        "-- the exact H-1 gap: emit_knowledge.py would ImportError on this "
        "missing sibling module."
    )
    assert deployed_vocab_config.is_file(), (
        "build.py did not deploy config/entry_kind_vocabulary.json -- the "
        "exact H-1 gap: load_vocabulary() would return {} and reject every "
        "entry_kind."
    )

    # Real invocation from the DEPLOYED location, not _REPO_ROOT -- the
    # whole point of this test per the fast-lane pr-review: every
    # pre-existing test resolved these scripts via the source tree, so 120
    # green tests proved nothing about a deployed install.
    dest_path = tmp_path / "captured_learning.md"
    sink_path = tmp_path / "knowledge_emissions.jsonl"
    emit_result = subprocess.run(
        [
            sys.executable, str(deployed_emit),
            "--agent", "test-writer",
            "--component", "infrastructure",
            "--destination", str(dest_path),
            "--entry-kind", "adr",
            "--text", "Deployed-layout real-invocation smoke test.",
            "--sink", str(sink_path),
        ],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )
    assert emit_result.returncode == 0, (
        "emit_knowledge.py, run from its DEPLOYED location, must exit 0 and "
        f"accept a valid entry_kind. stdout={emit_result.stdout!r} "
        f"stderr={emit_result.stderr!r}"
    )
    assert sink_path.exists(), (
        "the deployed emit_knowledge.py did not write to the sink -- it "
        "either could not import its sibling entry_kind_vocabulary module, "
        "or could not load config/entry_kind_vocabulary.json, and silently "
        "rejected a genuinely valid entry_kind."
    )
    lines = [ln for ln in sink_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"expected exactly one accepted event in the sink; got {lines!r}"
    )
