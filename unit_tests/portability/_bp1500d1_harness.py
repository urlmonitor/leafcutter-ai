"""
MODULE: _bp1500d1_harness
AC: BP-1500d-1 -- "The record of what was installed is written into the
    project that received it, and accounts for that project"

GOAL: Test-only out-of-package consumer-simulation harness. THIS AC BUILDS
    THE HARNESS (see its own it_requirements): BP-900h-1 specifies an
    out-of-package install but is work_status not_started with zero
    implementation anywhere in the workspace, so nothing exists to reuse.
    This module is deliberately parameterisable (package-directory name,
    deployed output root) so BP-900h-4 / BP-900h-4-i can later adopt it
    rather than build a second one, per this AC's delivers_to contracts.

LAYOUT CHOICE -- RECORDED, NOT SILENTLY PICKED (per this AC's own
    it_requirements #3, which flags the ambiguity explicitly), AND REVISED
    ONCE AFTER BEING MEASURED AGAINST THE REAL BUILD (see DECISION HISTORY):
    the harness places a COMPLETE copy of the producing package at
    ``<scratch>/leafcutter-ai/`` and a SEPARATE, SIBLING directory
    ``<scratch>/receiving_project/`` as the build's ``--target-dir``. The
    package copy is NOT nested inside the target -- test_spec entry 1's own
    wording ("the target contains nothing but a minimal skills_config.json")
    already rules out nesting, since a nested package copy would itself be
    a file under the target. This also matches KI-BP-011's own measured
    evidence, which used the real package root directly against an
    unrelated target directory, not a target containing a package copy.
    ``<scratch>/receiving_project/`` holds nothing else before the build
    runs except a minimal ``skills_config.json`` -- BP-900h-1's "built from
    an empty directory, NOT a copy of this repository" constrains the
    TARGET, not the package (which must be present as a copy somewhere for
    the build to run at all, just not inside the target).

WHY A SYSTEM TEMP ROOT AND NOT A SIBLING PATH (it_requirements #2, measured
    2026-08-25): a scratch target at a path that is still reachable via
    ``package_root.parent`` (e.g. a sibling directory under the same
    workspace the producing package lives in) exercises a code path that
    looks portable but is not exercising an out-of-package install at all.
    ``tempfile`` is used throughout and every harness build asserts, as a
    load-bearing fixture precondition, that the target's real path is NOT
    under the real producing package's own parent directory.

WHAT THIS MODULE DOES NOT DO: it never imports ``build_helpers`` or calls
``write_build_manifest`` directly. Every build below is the real
``python <scratch>/leafcutter-ai/scripts/build.py --target-dir <scratch>``
command line, run as a subprocess with a cwd outside the producing
package's own tree and no producing-package path on ``PYTHONPATH`` -- the
only way to prove the ENTRY POINT routes the target, not merely that the
already-parameterised writer function is capable of it (this AC's own
test_rationale, entry 3).

DECISION HISTORY
====================================================================
- 2026-09-01 [test-writer/BP-1500d-1]: Initial implementation used a NESTED
  layout (package copy AT ``<scratch>/leafcutter-ai/`` with ``<scratch>``
  itself as ``--target-dir``). All six tests passed immediately against the
  current, unmodified build.py -- because that nested-package-under-target
  shape is exactly the "consumer-install" layout the BP-100k-3-i fix
  (2026-08-18, ``package_root`` nested one level below ``target_root``)
  already handles correctly: ``_compute_output_mappings`` uses
  ``target_root`` directly as its relativization base, and a nested package
  is trivially relative to it. Verified live: a real build into that layout
  produced 471 non-empty ``output_mappings`` entries with
  ``output_mappings_error: ""``. Revised to a SIBLING layout (package and
  target as independent directories under the same scratch root, neither
  nested in the other) after confirming live that THIS is the shape that
  still reproduces the defect: the same real build against a sibling target
  produces ``output_mappings: {}``, a non-empty ``output_mappings_error``
  (``ValueError: '.../templates/agents/README.md' is not in the subpath of
  '.../receiving_project'`` -- raised by ``_add()``'s unguarded
  ``template_path.relative_to(repo_root)`` at build_helpers.py, propagated
  out of the per-file loop that has no try/except of its own), while the
  process still exits 0. This is the exact fail-open shape KI-BP-011 and
  this AC's own "VERIFIED EVIDENCE" describe, and matches test_spec entry
  1's literal wording ("the target contains nothing but a minimal
  skills_config.json") over the initial nested reading.
- 2026-09-07 [python-coder/BP-1500d-1-i]: RECORDED, NOT CHANGED, per this
  AC's own it_requirements #9: ``build_out_of_package_harness()`` archives
  ``HEAD`` (see ``git archive HEAD`` above), which is COMMITTED content
  only -- deliberately, so gitignored cruft from a real developer checkout
  never leaks into the simulated fresh clone. The consequence is that every
  test in this module (and in BP-1500d-1-i's own test file, once authored)
  reads RED against an uncommitted production fix in this same worktree, no
  matter how correct that fix is: the package copy this harness builds and
  the ``build.py`` it invokes are both frozen at the last commit. This is a
  property of THIS FIXTURE, not a defect in an uncommitted implementation --
  do not diagnose a correct fix as broken on the strength of a run against
  this harness alone; independently exercise the real build against a
  package copy that reflects the working tree first (see this AC's own
  "Verify behaviourally" instruction).
  EVALUATED AND DELIBERATELY NOT ADOPTED: ``git archive $(git stash create)``
  would archive tracked uncommitted changes (not untracked new files) without
  altering the working tree or the stash list, and was confirmed live in this
  worktree to see an uncommitted fix to ``scripts/build_helpers.py`` and
  ``templates/scripts/commit_guardian/check_build_drift.py`` correctly. It
  was not adopted here because (a) it still cannot see brand-new untracked
  files -- a fix that ADDS a file rather than editing an existing one would
  still read red, trading one visibility gap for a narrower, easy-to-miss
  one -- and (b) changing what a shared test fixture archives is a
  test-authoring decision outside this AC's assigned implementer's role (see
  the project's test-writer/python-coder division of labour). The
  commit-first path is therefore the one this harness keeps: commit the
  production fix, then re-run.
====================================================================
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# The real producing package root: unit_tests/portability/_bp1500d1_harness.py
# -> parents[2] is the repository root (scripts/, templates/, docs/ live here).
REAL_PACKAGE_ROOT = Path(__file__).resolve().parents[2]

_MANIFEST_NAME = ".build_manifest.json"
_DEFAULT_PACKAGE_DIR_NAME = "leafcutter-ai"


@dataclass
class HarnessBuild:
    """Result of standing up one out-of-package harness and building it."""

    scratch_root: Path  # tempdir root; NOT the same as target_root necessarily
    target_root: Path  # the build's --target-dir (the "receiving project")
    package_dir: Path  # <target_root's sibling-or-parent>/<package_dir_name>/
    pre_build_target_files: list[str]
    proc: subprocess.CompletedProcess
    manifest_path: Path
    real_package_manifest_hash_before: str | None
    real_package_manifest_path: Path
    _tmp: tempfile.TemporaryDirectory = field(repr=False)

    def cleanup(self) -> None:
        self._tmp.cleanup()

    @property
    def manifest_exists(self) -> bool:
        return self.manifest_path.is_file()

    def load_manifest(self) -> dict:
        raw = self.manifest_path.read_text(encoding="utf-8")
        return json.loads(raw)


def is_under_package_parent(path: Path, *, package_root: Path = REAL_PACKAGE_ROOT) -> bool:
    """True iff *path* is (or is nested under) the real producing package's
    own parent directory -- the placement rule it_requirements #2 demands be
    demonstrably discriminating, not merely holding by construction."""
    real_path = Path(path).resolve()
    real_package_parent = package_root.resolve().parent
    return real_path == real_package_parent or real_package_parent in real_path.parents


def probe_child_sys_path(cwd: Path, env: dict) -> list[str]:
    """Spawn a throwaway child process with the EXACT (cwd, env) launch
    conditions used for the real build subprocess, and return ITS ACTUAL
    ``sys.path`` -- verifying, as a property of a real child process rather
    than an assumption about our own env-construction, that no path under
    the real producing package checkout is reachable."""
    proc = subprocess.run(
        [sys.executable, "-c", "import json, sys; print(json.dumps(sys.path))"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(proc.stdout)


def _scrubbed_env() -> dict:
    """A subprocess environment with no producing-package path reachable via
    PYTHONPATH, so a defect that only works because the real package is
    importable from the child's path cannot hide behind that accident."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def build_out_of_package_harness(
    *,
    package_dir_name: str = _DEFAULT_PACKAGE_DIR_NAME,
    output_root_name: str = ".leafcutter",
    timeout: int = 300,
) -> HarnessBuild:
    """Stand up a REAL out-of-package consumer-simulation install and build it
    via the REAL ``build.py`` command line (subprocess, not an import).

    Returns a :class:`HarnessBuild` capturing everything the six BP-1500d-1
    test cases need. Caller owns calling ``.cleanup()`` (or use it as part of
    a ``unittest.TestCase`` fixture with ``addClassCleanup``/``tearDownClass``).
    """
    tmp = tempfile.TemporaryDirectory(prefix="bp1500d1_")
    scratch_root = Path(tmp.name)
    # Package and target are SIBLINGS under scratch_root, neither nested in
    # the other -- see module docstring DECISION HISTORY for why a nested
    # layout does not reproduce the defect this AC targets.
    package_dir = scratch_root / package_dir_name
    target_root = scratch_root / "receiving_project"

    # Load-bearing fixture precondition (it_requirements #2): the target must
    # NOT be reachable via the real producing package's own parent directory.
    # tempfile guarantees this under a correctly configured pytest.ini (no
    # --basetemp, no conftest tmp_path_factory override -- verified for this
    # repo 2026-08-25), but this assertion makes the guarantee load-bearing
    # rather than assumed.
    real_target = target_root.resolve()
    real_package_parent = REAL_PACKAGE_ROOT.parent.resolve()
    if real_target == real_package_parent or real_package_parent in real_target.parents:
        tmp.cleanup()
        raise AssertionError(
            f"harness target {real_target} is under the producing package's "
            f"own parent {real_package_parent} -- this is exactly the "
            "false-green placement this harness exists to avoid."
        )

    # A COMPLETE, CLEAN copy of the producing package -- git archive rather
    # than a raw filesystem copy, so gitignored cruft (an existing
    # .build_manifest.json, __pycache__, venvs) from THIS checkout never
    # leaks into the "fresh consumer clone" the harness is simulating.
    package_dir.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    archive_path = scratch_root / "_package_archive.tar"
    try:
        subprocess.run(
            ["git", "-C", str(REAL_PACKAGE_ROOT), "archive", "HEAD", "-o", str(archive_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        tmp.cleanup()
        raise RuntimeError(f"git archive failed while building harness: {exc}") from exc

    try:
        shutil.unpack_archive(str(archive_path), extract_dir=str(package_dir), format="tar")
    finally:
        archive_path.unlink(missing_ok=True)

    # Target itself is empty apart from a minimal skills_config.json, per
    # this AC's it_requirements #3.
    skills_config_path = target_root / "skills_config.json"
    skills_config_path.write_text(
        json.dumps({"output_root": output_root_name}) + "\n", encoding="utf-8",
    )

    pre_build_target_files = sorted(
        str(p.relative_to(target_root)) for p in target_root.iterdir()
    )

    # Capture the REAL producing package's own record hash BEFORE the build,
    # so the negative half of the (b)-does-not-clobber criterion (this AC's
    # test_rationale entry 2) can prove byte-unchanged-ness rather than
    # merely absence-before/absence-after.
    real_package_manifest_path = REAL_PACKAGE_ROOT / _MANIFEST_NAME
    real_package_manifest_hash_before = hash_file(real_package_manifest_path)

    build_script = package_dir / "scripts" / "build.py"
    argv = [sys.executable, str(build_script), "--target-dir", str(target_root)]
    proc = subprocess.run(
        argv,
        cwd=str(target_root),  # cwd is the receiving project, never the package tree
        env=_scrubbed_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    manifest_path = target_root / _MANIFEST_NAME
    return HarnessBuild(
        scratch_root=scratch_root,
        target_root=target_root,
        package_dir=package_dir,
        pre_build_target_files=pre_build_target_files,
        proc=proc,
        manifest_path=manifest_path,
        real_package_manifest_hash_before=real_package_manifest_hash_before,
        real_package_manifest_path=real_package_manifest_path,
        _tmp=tmp,
    )


def hash_file(path: Path) -> str | None:
    """SHA-256 of a file's bytes, or None if it does not exist -- used to
    assert byte-identity (idempotency) and byte-unchanged-ness (no clobber
    of the producing package's own record)."""
    import hashlib

    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
