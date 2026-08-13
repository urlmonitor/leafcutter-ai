"""
MODULE: unit_tests/commit_guardian/test_ge_118b_drift_manifest_resolution.py
GOAL: GE-118b — check_output_drift.py and check_build_drift.py must locate
    .build_manifest.json where build_helpers.write_build_manifest() actually
    writes it (``package_root / ".build_manifest.json"``), not at a path
    derived from a hardcoded ``"leafcutter"`` package-directory segment. And
    when the manifest genuinely cannot be found, the hook must say so
    explicitly (naming the path(s) it tried), never pass silently.
BUSINESS CONTEXT: Both hooks compute (identically):

    _REPO_ROOT = Path(__file__).resolve().parents[2]
    _MANIFEST_PATH = _REPO_ROOT / "leafcutter" / ".build_manifest.json"

    Deployed under ``.leafcutter/scripts/commit_guardian/``, ``.resolve()``
    lands on the real (non-symlink) directory that houses the deployed
    scripts. ``parents[2]`` from there is the workspace/consumer-project
    root, and appending the literal segment ``"leafcutter"`` produces a path
    that does not exist whenever the actual package directory is named
    anything else (e.g. ``leafcutter-ai``, or any consumer-chosen name) —
    which is the real production case in THIS workspace. Confirmed by hand:

        >>> from pathlib import Path
        >>> p = Path(
        ...   "/home/henzeh/projects/leafcutter/leafcutter-ai/.leafcutter/"
        ...   "scripts/commit_guardian/check_output_drift.py"
        ... ).resolve()
        >>> p.parents[2]
        PosixPath('/home/henzeh/projects/leafcutter/.leafcutter')
        >>> (p.parents[2] / "leafcutter" / ".build_manifest.json").exists()
        False

    while the real manifest lives at
    ``/home/henzeh/projects/leafcutter/leafcutter-ai/.build_manifest.json``
    (build_helpers.py:184, ``package_root / ".build_manifest.json"``) —
    a SIBLING of ``.leafcutter``, not nested inside it. The gate therefore
    reports success while never comparing anything, in the main checkout as
    well as in worktrees.

EXERCISE STRATEGY (documented per test-writer instructions): both hooks
    compute ``_REPO_ROOT`` / ``_MANIFEST_PATH`` / (for check_build_drift)
    ``_TEMPLATES_DIR`` as MODULE-LEVEL statements evaluated once at import
    time, keyed off ``Path(__file__).resolve()``. There is no importable
    seam that lets a test supply a fake ``__file__`` location to the already-
    imported module, and inventing one (e.g. a
    ``resolve_manifest_path(hook_file)`` free function the coder must then
    implement with that exact name) would presume a specific fix shape the
    ticket explicitly asks us not to presume ("the fix shape should stay
    open").

    Instead, each test COPIES the real hook module (``shutil.copy``, so the
    exact on-disk template source under review is exercised, not a
    paraphrase) into a synthesized fake deployment tree built inside a
    ``tempfile.TemporaryDirectory()``, at the same relative depth the real
    deployed layout uses (``<fake_root>/.leafcutter/scripts/commit_guardian/
    check_*.py``), then invokes it with ``subprocess.run([sys.executable,
    str(hook_path)], cwd=str(fake_root), ...)`` — i.e. runs it exactly the
    way ``run_hook.py`` / pre-commit invokes it in production. This:

      1. Reproduces the EXACT failure mode (a real, non-existent computed
         Path — not a mocked one) rather than a proxy for it.
      2. Does not presume any particular fix shape (a shared root-resolution
         helper, a multi-candidate search, reusing the existing sibling
         ``_resolve_root.py`` module, etc.) — any correct fix makes these
         tests pass, whatever internal shape it takes.
      3. ``_resolve_root.py`` (already a real sibling file in
         ``templates/scripts/commit_guardian/``, used by other hooks in this
         same directory — see ``test_resolve_root_git_preferred.py``) is
         copied alongside every deployed hook copy so that, if the fix
         imports it, the import resolves without extra sys.path plumbing:
         Python auto-inserts a script's own containing directory onto
         ``sys.path`` when it is run as ``__main__``.

    A hand-verified sanity assertion is embedded in every "locates manifest"
    test: the WRONG, hardcoded-``"leafcutter"``-segment path must genuinely
    be absent in the synthesized tree, guarding against a vacuous pass (the
    EPIC-PhantomDoneFilesTouched failure mode — a fixture that accidentally
    satisfies the buggy code path too).

    Two independent package-directory names are exercised
    (``leafcutter-ai/`` — mimicking THIS repo's real deployed name — and
    ``pkg-xyz/`` — an arbitrary consumer name) so that a fix which merely
    swaps the hardcoded literal ``"leafcutter"`` for the literal
    ``"leafcutter-ai"`` (an equally narrow hardcode) is caught red-handed by
    the ``pkg-xyz`` case.

RED BASELINE (captured 2026-08-13, before any production-code change — see
    the ticket sign-off comment for the exact captured subprocess output):
    - The four "locates manifest" tests fail because ``_load_manifest``
      returns ``None`` without ever attempting to open the file (the
      computed ``_MANIFEST_PATH`` under the hardcoded ``"leafcutter"``
      segment does not exist), so the "cannot read manifest" message this
      test looks for is never printed — only the generic "not found"
      message is.
    - The two "missing manifest names the path(s) tried" tests fail because
      today's warning text is a fixed, generic sentence
      (``"... .build_manifest.json not found. Run build.py to generate it.
      Skipping ... check."``) that never interpolates the actual computed
      path — there is no absolute path substring in the message at all.
    - The build-drift round-trip ("actually compares") test fails because
      the manifest is never found, so ``check_drift()`` returns 0 with the
      generic warning instead of detecting the deliberately-introduced
      template drift and exiting 1 with a ``BLOCKED`` message.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# templates/scripts/commit_guardian/ — the canonical template source that
# build.py deploys into consumer projects (ADR-001: edit this copy, never
# the deployed output).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_CG_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_OUTPUT_DRIFT_SRC = _TEMPLATES_CG_DIR / "check_output_drift.py"
_CHECK_BUILD_DRIFT_SRC = _TEMPLATES_CG_DIR / "check_build_drift.py"
_RESOLVE_ROOT_SRC = _TEMPLATES_CG_DIR / "_resolve_root.py"

_SUBPROCESS_TIMEOUT_SECONDS = 10


def _deploy_hook(base: Path, hook_src: Path) -> Path:
    """Copy a hook module into a synthesized deployed layout under ``base``.

    Mirrors the REAL deployed relative depth exactly:
    ``<base>/.leafcutter/scripts/commit_guardian/<hook_name>.py``. Both hooks
    compute ``Path(__file__).resolve().parents[2]`` — from that exact depth
    this lands on ``<base>/.leafcutter``, matching the live workspace
    computation verified by hand in the module docstring.

    ``_resolve_root.py`` (a real sibling file in the source template
    directory) is copied alongside so that a fix which imports it resolves
    without any additional sys.path setup — Python auto-adds a script's own
    directory to ``sys.path`` when run as ``__main__``.

    Args:
        base: Temp directory to build the fake deployment inside.
        hook_src: Absolute path to the real hook module under
            templates/scripts/commit_guardian/ to copy.

    Returns:
        Absolute path to the copied hook module in the fake deployed tree.
    """
    deployed_dir = base / ".leafcutter" / "scripts" / "commit_guardian"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    dest = deployed_dir / hook_src.name
    shutil.copy(hook_src, dest)
    if _RESOLVE_ROOT_SRC.exists():
        shutil.copy(_RESOLVE_ROOT_SRC, deployed_dir / "_resolve_root.py")
    return dest


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed hook copy as a subprocess, exactly as pre-commit does.

    Args:
        hook_path: Absolute path to the (copied) hook module to execute.
        cwd: Working directory to run the subprocess in.

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _write_real_manifest(package_root: Path, content: str) -> Path:
    """Write a ``.build_manifest.json`` at the real location build.py uses.

    Args:
        package_root: The directory build_helpers.write_build_manifest()
            treats as the package root (``package_root / ".build_manifest.json"``).
        content: Raw text to write (deliberately malformed JSON is used by
            the "locates manifest" tests — see module docstring).

    Returns:
        Absolute path to the manifest file written.
    """
    package_root.mkdir(parents=True, exist_ok=True)
    manifest_path = package_root / ".build_manifest.json"
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


class TestDriftHooksLocateRealManifest(unittest.TestCase):
    """AC-1: both hooks must locate the manifest build.py actually wrote,
    regardless of the package directory's name."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def _assert_hook_locates_manifest(self, hook_src: Path, pkg_dir_name: str) -> None:
        """Shared body: deploy `hook_src`, place a real-but-malformed manifest
        under `<base>/<pkg_dir_name>/.build_manifest.json`, and assert the
        hook actually opened it (proven by the "cannot read manifest"
        message, which _load_manifest only emits after `manifest_path.exists()`
        was True) rather than silently failing to find it.
        """
        hook_path = _deploy_hook(self.base, hook_src)
        package_root = self.base / pkg_dir_name
        manifest_path = _write_real_manifest(package_root, "{not valid json")

        # Sanity: guard against a vacuous pass. The path the BUGGY hook
        # computes today (hardcoded "leafcutter" segment under .leafcutter/)
        # must genuinely be absent from this synthesized tree.
        wrong_path = self.base / ".leafcutter" / "leafcutter" / ".build_manifest.json"
        self.assertFalse(
            wrong_path.exists(),
            "Test setup bug: the buggy hardcoded-path location must not "
            "coincidentally exist, or this test cannot distinguish fixed "
            "from unfixed behavior.",
        )

        result = _run_hook(hook_path, self.base)

        self.assertIn(
            "cannot read manifest",
            result.stderr,
            msg=(
                f"GE-118b: {hook_src.name} never attempted to open the real "
                f"manifest at {manifest_path}. It only reaches the "
                "'cannot read manifest' branch after manifest_path.exists() "
                "is True, so this failure means the hook's computed path "
                "does not match where build.py actually wrote the manifest "
                f"(package dir name: {pkg_dir_name!r}). "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            str(manifest_path.resolve()),
            result.stderr,
            msg=(
                "The 'cannot read manifest' message must name the exact "
                f"path it opened ({manifest_path}). stderr:\n{result.stderr}"
            ),
        )

    def test_ac_ge118b_output_drift_locates_manifest_leafcutter_ai_pkgname(self) -> None:
        # covers: GE-118b
        """check_output_drift.py must find the manifest when the package
        directory is named 'leafcutter-ai' (this repo's REAL deployed name).
        """
        self._assert_hook_locates_manifest(_CHECK_OUTPUT_DRIFT_SRC, "leafcutter-ai")

    def test_ac_ge118b_output_drift_locates_manifest_arbitrary_pkgname(self) -> None:
        # covers: GE-118b
        """check_output_drift.py must find the manifest under an arbitrary
        consumer package-directory name ('pkg-xyz'), proving the fix does
        not merely swap one hardcoded literal for another.
        """
        self._assert_hook_locates_manifest(_CHECK_OUTPUT_DRIFT_SRC, "pkg-xyz")

    def test_ac_ge118b_build_drift_locates_manifest_leafcutter_ai_pkgname(self) -> None:
        # covers: GE-118b
        """check_build_drift.py must find the manifest when the package
        directory is named 'leafcutter-ai' (this repo's REAL deployed name).
        """
        self._assert_hook_locates_manifest(_CHECK_BUILD_DRIFT_SRC, "leafcutter-ai")

    def test_ac_ge118b_build_drift_locates_manifest_arbitrary_pkgname(self) -> None:
        # covers: GE-118b
        """check_build_drift.py must find the manifest under an arbitrary
        consumer package-directory name ('pkg-xyz'), proving the fix does
        not merely swap one hardcoded literal for another.
        """
        self._assert_hook_locates_manifest(_CHECK_BUILD_DRIFT_SRC, "pkg-xyz")


class TestDriftHooksMissingManifestNamesPathsTried(unittest.TestCase):
    """AC-2: a genuinely missing manifest must be reported explicitly,
    naming the path(s) tried — never a silent pass."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_ac_ge118b_output_drift_missing_manifest_names_path_tried(self) -> None:
        # covers: GE-118b
        """With no manifest anywhere under the fake root, check_output_drift.py
        must exit 0 (fail-open — a missing manifest is not itself a block)
        but its warning must name a concrete absolute path it tried, not
        just repeat the bare filename ".build_manifest.json" generically.

        FAILS TODAY: the current warning text is a fixed sentence that never
        interpolates the computed _MANIFEST_PATH, so no path-like substring
        (this fake root's own absolute path) appears anywhere in stderr.
        """
        hook_path = _deploy_hook(self.base, _CHECK_OUTPUT_DRIFT_SRC)
        # Deliberately no .build_manifest.json anywhere under self.base.

        result = _run_hook(hook_path, self.base)

        self.assertEqual(
            0,
            result.returncode,
            msg=f"Missing manifest must fail-open (exit 0). stderr:\n{result.stderr}",
        )
        self.assertIn(
            "not found",
            result.stderr.lower(),
            msg=f"Missing manifest must produce a visible warning. stderr:\n{result.stderr}",
        )
        self.assertIn(
            str(self.base.resolve()),
            result.stderr,
            msg=(
                "GE-118b it_requirement: 'A missing manifest must produce a "
                "visible warning naming the paths tried, never a silent "
                "success.' Today's message is a generic fixed sentence with "
                f"no concrete path in it. stderr:\n{result.stderr}"
            ),
        )

    def test_ac_ge118b_build_drift_missing_manifest_names_path_tried(self) -> None:
        # covers: GE-118b
        """Same contract as above for check_build_drift.py: check_build_drift.py:188
        already warns (not a silent pass) but the warning text does not name
        the path it tried — this test requires that it does.

        FAILS TODAY for the same reason as the output_drift test above: the
        warning sentence is fixed text with no interpolated path.
        """
        hook_path = _deploy_hook(self.base, _CHECK_BUILD_DRIFT_SRC)
        # Deliberately no .build_manifest.json anywhere under self.base.

        result = _run_hook(hook_path, self.base)

        self.assertEqual(
            0,
            result.returncode,
            msg=f"Missing manifest must fail-open (exit 0). stderr:\n{result.stderr}",
        )
        self.assertIn(
            "not found",
            result.stderr.lower(),
            msg=f"Missing manifest must produce a visible warning. stderr:\n{result.stderr}",
        )
        self.assertIn(
            str(self.base.resolve()),
            result.stderr,
            msg=(
                "GE-118b it_requirement: 'A missing manifest must produce a "
                "visible warning naming the paths tried, never a silent "
                "success.' Today's message is a generic fixed sentence with "
                f"no concrete path in it. stderr:\n{result.stderr}"
            ),
        )


class TestBuildDriftComparesWithCorrectlyPlacedManifest(unittest.TestCase):
    """AC-3 (check_build_drift specific, per ticket): with a correctly
    placed manifest, the hook must actually perform the comparison and
    detect real drift — not merely avoid crashing."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_ac_ge118b_build_drift_detects_real_violation_with_correct_manifest(self) -> None:
        # covers: GE-118b
        """Full round trip: a template under leafcutter-ai/templates/agents/
        is recorded in the manifest with its ORIGINAL hash, then edited
        (simulating "template edited without re-running build.py"). With the
        manifest correctly located, check_build_drift.py must detect the
        mismatch and exit 1 with a BLOCKED message — proving it genuinely
        compared, not merely that it avoided an exception.

        FAILS TODAY: the manifest is never found (computed path uses the
        hardcoded "leafcutter" segment, which does not exist here), so the
        hook exits 0 with the generic "not found" warning instead of
        detecting the drift.
        """
        hook_path = _deploy_hook(self.base, _CHECK_BUILD_DRIFT_SRC)
        package_root = self.base / "leafcutter-ai"
        templates_agents_dir = package_root / "templates" / "agents"
        templates_agents_dir.mkdir(parents=True, exist_ok=True)

        original_content = "# Example Agent Template\n\nOriginal content.\n"
        tpl_path = templates_agents_dir / "example.md"
        tpl_path.write_text(original_content, encoding="utf-8")
        original_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

        # Manifest key format matches build_helpers.write_build_manifest():
        # relative to repo_root (package_root.parent), forward-slash posix.
        manifest_key = "leafcutter-ai/templates/agents/example.md"
        manifest_content = json.dumps({manifest_key: original_hash, "output_mappings": {}})
        manifest_path = _write_real_manifest(package_root, manifest_content)

        # Simulate drift: template edited without re-running build.py.
        tpl_path.write_text("# Example Agent Template\n\nDRIFTED content.\n", encoding="utf-8")

        result = _run_hook(hook_path, self.base)

        self.assertEqual(
            1,
            result.returncode,
            msg=(
                f"check_build_drift.py must detect the deliberately-introduced "
                f"template drift once the manifest at {manifest_path} is "
                f"correctly located. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            "BLOCKED",
            result.stdout + result.stderr,
            msg=(
                "Exit code was 1 but no BLOCKED message was printed — "
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )
        self.assertIn(manifest_key, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
