"""
MODULE: unit_tests/commit_guardian/test_bo2500b5_done_proof_default_scan_root.py
GOAL: RED test stubs for BO-2500b-5 — check_done_proof.py's built-in scan root
    (used whenever a caller omits --test-root) must default to the PROJECT ROOT,
    not the historical "unit_tests" subdirectory.

BUSINESS CONTEXT: The pre-commit hook entry in commit_guardian.json passes
    ``--test-root .`` explicitly.  The CI invocation
    (.github/workflows/ci.yml:163, ``--mode ci-changed --base origin/<base>``)
    passes NO --test-root at all, so it silently falls back to
    ``_DEFAULT_TEST_ROOT = "unit_tests"``.  commit_guardian.json's own comment on
    the pre-commit hook entry documents why that default is wrong: it "contains
    no .ts files, so JS-covered ACs would be reported as unproven (BO-2500e-5);
    this also makes the hook correct in consumer projects whose tests do not
    live under unit_tests/" — yet CI mode is called "the authoritative
    backstop".  Measured on this repo: 21 files under tests/ carry "# covers:"
    tags the CI gate cannot see.

    The fix must change the DEFAULT (not any one caller's command line) so every
    caller that omits --test-root — CI, consumer installs, ad-hoc runs — is
    repaired at once.  An explicit --test-root must continue to override the
    default, and the existing exclusion set (node_modules, .next, dist,
    coverage, .git, __pycache__, .venv) must keep applying even when the
    default widens to the whole project tree.

ARCHITECTURE: These tests drive the REAL check_done_proof.py CLI as a
    subprocess against a synthesized, git-initialised project tree (its own
    docs/acceptance-criteria/ AC store plus several test directories — NOT
    only "unit_tests/"), asserting on the real process exit code and stdout.
    No grepping of check_done_proof.py's source for _DEFAULT_TEST_ROOT — per
    CLAUDE.md ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep"), a
    grep-only test would pass on dead code and cannot distinguish "the default
    is repo-root and the scan actually runs" from "the string is defined but
    unused".

    Precommit mode (the CLI default, no --mode flag needed) is used throughout:
    it calls check_staged_done_proofs(), which is a pure STATIC covers-tag
    presence scan (no pytest/vitest subprocess invocation) — the cleanest,
    fastest, most deterministic way to prove which directory tree was
    actually scanned, for both '# covers:' (Python) and '// covers:' (TS) tags.

    Project-root resolution: check_done_proof.py's main() calls
    _resolve_root.find_project_root(), which prefers
    ``git rev-parse --show-toplevel`` run with the *current process's* cwd.
    Each synthesized project tree is therefore given its own ``git init`` so
    that launching check_done_proof.py with cwd=<synthesized root> makes
    find_project_root() resolve to that synthesized root — not this real repo.

FIXTURE AUTHENTICITY MANDATE (BO-2500c): AC YAML fixtures are written with
    yaml.safe_dump (never a hand-typed YAML literal).  Covers-tagged test
    fixtures are real .py/.ts source files with genuine bodies.  The AC YAML
    is staged into the synthesized repo's git index via a real `git add` so
    that check_done_proof.py's own `git diff --cached` discovers it exactly as
    it would in a real pre-commit invocation — no mocking of git or of the
    pass/fail signal.

RED BASELINE: test_ac1_default_scan_root_is_repo_root_not_unit_tests,
    test_ac1_js_covers_tag_found_under_default_scope, and (the legit-AC half of)
    test_ac1_exclusions_still_apply_under_repo_root_default are RED until
    python-coder changes ``_DEFAULT_TEST_ROOT`` in
    templates/scripts/commit_guardian/check_done_proof.py (and its deployed
    copy at scripts/commit_guardian/check_done_proof.py) from "unit_tests" to
    the project root itself.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2500b_done_proof_hook.py /
# test_done_proof_ci_changed_scope.py.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_CHECK_DONE_PROOF_PY = _COMMIT_GUARDIAN_DIR / "check_done_proof.py"
_PYTHON_EXE = sys.executable
_GIT_TIMEOUT = 10
_GATE_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* and return the completed process.

    Args:
        args: Git subcommand and arguments (without the leading "git").
        cwd: Directory to run the git command in.

    Returns:
        The completed subprocess.CompletedProcess (never raises on nonzero exit).
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
    )


def _init_git_repo(root: Path) -> None:
    """Initialise *root* as its own git repository (no commits required).

    check_done_proof.py's project-root resolution prefers
    ``git rev-parse --show-toplevel``; without a real .git here, that
    resolution would fall back to walking ancestors of check_done_proof.py's
    own __file__ and incorrectly resolve to THIS real repo instead of the
    synthesized fixture tree.

    Args:
        root: Directory to initialise as a git repository.
    """
    proc = _run_git(["init"], cwd=root)
    assert proc.returncode == 0, f"git init failed: {proc.stderr}"


def _write_done_ac(root: Path, ac_id: str) -> Path:
    """Write a minimal, work_status:done AC YAML using yaml.safe_dump and stage it.

    Written under docs/acceptance-criteria/test-component/<ac_id>.yaml so it
    satisfies check_done_proof._is_gated_ac_yaml (suffix .yaml, an
    "acceptance-criteria" path component, no "fixtures" component). Staged via
    a real ``git add`` so check_done_proof.py's own
    ``git diff --cached --name-only`` (the precommit-mode discovery path)
    finds it exactly as it would for a real staged commit.

    Args:
        root: Root of the synthesized, git-initialised project tree.
        ac_id: Identifier for the AC.

    Returns:
        Path to the written (and staged) YAML file.
    """
    subdir = root / "docs" / "acceptance-criteria" / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": "done",
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    # Mandate: use yaml.safe_dump, not a hand-typed YAML literal (BO-2500c).
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    rel = path.relative_to(root)
    add_proc = _run_git(["add", str(rel)], cwd=root)
    assert add_proc.returncode == 0, f"git add failed: {add_proc.stderr}"
    return path


def _write_source_file(root: Path, rel_dir: str, filename: str, content: str) -> Path:
    """Write a real source (test) file under root/rel_dir/filename.

    Args:
        root: Root of the synthesized project tree.
        rel_dir: Directory (relative to root) to place the file in, e.g. "tests".
        filename: Filename, e.g. "test_something.py" or "something.test.ts".
        content: Source text; leading whitespace is dedented automatically.

    Returns:
        Path to the written file.
    """
    target_dir = root / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _run_gate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Invoke the REAL check_done_proof.py CLI against a synthesized project.

    Runs with cwd=root (so find_project_root() resolves the synthesized tree,
    not this real repo) and default mode (precommit — no --mode flag), so the
    exercised code path is check_staged_done_proofs(): a pure static covers-tag
    presence scan requiring no pytest/vitest subprocess.

    Args:
        root: Root of the synthesized, git-initialised project tree.
        extra_args: Additional CLI flags (e.g. ["--test-root", "narrow"]).

    Returns:
        The completed subprocess.CompletedProcess.
    """
    cmd = [_PYTHON_EXE, str(_CHECK_DONE_PROOF_PY)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_GATE_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# TestDefaultScanRootIsProjectRoot
# ---------------------------------------------------------------------------


class TestDefaultScanRootIsProjectRoot(unittest.TestCase):
    """BO-2500b-5: with no --test-root, the scan root is the project root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_git_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_default_scan_root_is_repo_root_not_unit_tests(self) -> None:
        # covers: BO-2500b-5
        """With no --test-root, a '# covers:' tag under tests/ (NOT unit_tests/) is found.

        This is the core regression from the AC: check_done_proof.py's built-in
        default (_DEFAULT_TEST_ROOT) must resolve to the project root, matching
        the --test-root . the pre-commit hook already passes explicitly — not
        to the historical "unit_tests" subdirectory.

        Fixture places the covers tag under tests/ deliberately (NOT
        unit_tests/), and unit_tests/ is never created — so a fixture that put
        the tag in unit_tests/ would reproduce the bug's own assumption and
        pass either way (forbidden by the ticket).

        To make this green: python-coder changes _DEFAULT_TEST_ROOT in
        check_done_proof.py so main() resolves the default test_root to the
        project root itself when --test-root is omitted.
        """
        ac_id = "BO-B5-DEFAULT-ROOT"
        _write_done_ac(self.root, ac_id)
        _write_source_file(
            self.root,
            "tests",
            "test_default_root.py",
            f"""\
            def test_something():
                # covers: {ac_id}
                pass
            """,
        )

        proc = _run_gate(self.root)

        self.assertEqual(
            proc.returncode,
            0,
            "With no --test-root, a '# covers:' tag under tests/ must be found "
            "and the AC must NOT be reported as unproven — the default scan "
            "root must be the project root, not 'unit_tests'. "
            f"Got returncode={proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertNotIn(
            ac_id,
            proc.stdout,
            "The AC must not appear in a violation line when its covers tag "
            f"exists under tests/ and the default scope is repo-root. stdout={proc.stdout!r}",
        )

    def test_ac1_js_covers_tag_found_under_default_scope(self) -> None:
        # covers: BO-2500b-5
        """A '// covers:' tag in a JS/TS test is found under the default scope.

        The old default ("unit_tests") contains no .ts files in this project
        (BO-2500e-5), so a JS-covered AC was always reported unproven purely
        because of directory choice, never because the tag was genuinely
        absent. Widening the default to the project root fixes this for every
        caller that omits --test-root, not just this repo's CI command line.
        """
        ac_id = "BO-B5-JS-TAG"
        _write_done_ac(self.root, ac_id)
        _write_source_file(
            self.root,
            "tests",
            "something.test.ts",
            f"""\
            test('does something', () => {{
                // covers: {ac_id}
                expect(true).toBe(true);
            }});
            """,
        )

        proc = _run_gate(self.root)

        self.assertEqual(
            proc.returncode,
            0,
            "With no --test-root, a '// covers:' tag under tests/*.ts must be "
            "found under the default scope, so a JS-covered AC is not reported "
            "unproven merely because the default directory holds no .ts files. "
            f"Got returncode={proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertNotIn(
            ac_id,
            proc.stdout,
            f"The JS-covered AC must not appear in a violation line. stdout={proc.stdout!r}",
        )

    def test_ac1_exclusions_still_apply_under_repo_root_default(self) -> None:
        # covers: BO-2500b-5
        """Excluded dirs (node_modules, etc.) stay excluded even when the default widens.

        Two ACs are staged as done:
          - one whose covers tag lives under tests/ (a normal, non-excluded
            directory) — must be found under the new repo-root default.
          - one whose covers tag lives ONLY under node_modules/ (an entry of
            _EXCLUDED_SCAN_DIRS) — must still be reported as unproven, proving
            that widening the default scan root to the whole project did not
            also widen it into excluded, non-source subtrees.
        """
        legit_id = "BO-B5-EXCL-LEGIT"
        excluded_id = "BO-B5-EXCL-NODEMODULES"
        _write_done_ac(self.root, legit_id)
        _write_done_ac(self.root, excluded_id)
        _write_source_file(
            self.root,
            "tests",
            "test_legit.py",
            f"""\
            def test_something_legit():
                # covers: {legit_id}
                pass
            """,
        )
        _write_source_file(
            self.root,
            "node_modules/some-pkg",
            "test_excluded.py",
            f"""\
            def test_something_excluded():
                # covers: {excluded_id}
                pass
            """,
        )

        proc = _run_gate(self.root)

        self.assertNotIn(
            legit_id,
            proc.stdout,
            "The AC covered under tests/ (a normal, non-excluded directory) must "
            f"NOT be reported as a violation under the repo-root default. stdout={proc.stdout!r}",
        )
        self.assertIn(
            excluded_id,
            proc.stdout,
            "The AC whose only covers tag lives under node_modules/ must STILL be "
            "reported as a violation — node_modules must remain excluded from the "
            f"scan even when the default widens to the project root. stdout={proc.stdout!r}",
        )


# ---------------------------------------------------------------------------
# TestExplicitTestRootOverridesDefault
# ---------------------------------------------------------------------------


class TestExplicitTestRootOverridesDefault(unittest.TestCase):
    """BO-2500b-5: an explicit --test-root must still narrow the scan."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_git_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_explicit_test_root_still_overrides_default(self) -> None:
        # covers: BO-2500b-5
        """--test-root <narrow dir> still narrows the scan, proving the default
        change did not remove the override.

        A covers tag exists under tests/ (which the new, widened default WOULD
        find), but the CLI is invoked with an explicit --test-root pointing at
        an empty sibling directory. The AC must still be reported as a
        violation: the explicit flag must win over the default, exactly as it
        already does today when the flag is passed to check_all_done_acs /
        check_changed_done_acs.
        """
        ac_id = "BO-B5-OVERRIDE"
        _write_done_ac(self.root, ac_id)
        _write_source_file(
            self.root,
            "tests",
            "test_override.py",
            f"""\
            def test_something_override():
                # covers: {ac_id}
                pass
            """,
        )
        narrow_dir = self.root / "narrow_scope"
        narrow_dir.mkdir(parents=True, exist_ok=True)

        proc = _run_gate(self.root, extra_args=["--test-root", str(narrow_dir)])

        self.assertIn(
            ac_id,
            proc.stdout,
            "An explicit --test-root must override the default and narrow the "
            "scan: the covers tag under tests/ must be ignored because "
            "--test-root points at an empty, unrelated directory. "
            f"Got returncode={proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertNotEqual(
            proc.returncode,
            0,
            "--test-root must have narrowed the scan away from the tag, so the "
            f"gate must exit non-zero (violation). Got returncode={proc.returncode}.",
        )


# ---------------------------------------------------------------------------
# TestRealRepoDefaultScopeSanityCheck (bonus — real-artifact spot-check)
# ---------------------------------------------------------------------------
#
# Not part of the AC's core red-baseline: this class exercises
# _collect_all_covered_ids directly against the REAL tests/ directory of this
# repository (never a synthesized fixture) to substantiate the AC's own
# motivating claim — "21 files under tests/ carry '# covers:' tags the CI gate
# cannot see" — per the CLAUDE.md "Real-artifact behavioral spot-check"
# convention. It does not assert anything about check_done_proof.py's CLI
# default (that is Test 1 above); it only proves the real tests/ tree genuinely
# holds discoverable proof material that a repo-root default would surface.

sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
from check_done_proof import _collect_all_covered_ids  # noqa: E402


class TestRealRepoDefaultScopeSanityCheck(unittest.TestCase):
    """Bonus: the real tests/ tree holds covers tags a repo-root default would find."""

    def test_ac1_real_tests_directory_has_discoverable_covers_tags(self) -> None:
        # covers: BO-2500b-5
        """The real tests/ directory of this repo contains '# covers:' tags.

        Calls the REAL, on-disk _collect_all_covered_ids against the REAL
        tests/ directory of this repository (not a synthesized fixture) —
        substantiating the AC's motivating measurement that a whole class of
        genuine proof-of-done evidence sits outside "unit_tests/" and is
        invisible to the CI gate's current default.
        """
        real_tests_dir = _REPO_ROOT / "tests"
        if not real_tests_dir.is_dir():
            self.skipTest("This repo has no top-level tests/ directory to spot-check.")

        covered_ids = _collect_all_covered_ids(real_tests_dir)

        self.assertTrue(
            len(covered_ids) > 0,
            "Expected the real tests/ directory to contain at least one "
            "'# covers:' tag (the AC's own measurement found 21 such files). "
            "If this now fails, the motivating premise for BO-2500b-5 may have "
            "changed and the AC should be re-verified.",
        )


if __name__ == "__main__":
    unittest.main()
