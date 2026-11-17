"""
MODULE: unit_tests/portability/ge_120e_1/test_ge_120e_1_iii_test_d_isolation.py
AC: GE-120e-1-iii — "The test that poisons the shared change-set source poisons
    a copy, so a killed run never leaves a broken check in the repository"
GOAL: Prove that test D of the GE-120e-1 suite (the seam test in
    ``test_ge_120e_1_boundary_and_seam.py``) never writes into the repository
    tree. Test D replaces the shared ``_authored_change.py`` with a stub that
    always raises. These tests run test D as a separate process and watch the
    REAL ``templates/scripts/commit_guardian/_authored_change.py`` and the git
    status of ``templates/`` before, during and after, including a run killed
    with SIGKILL at the moment the stub is in place. A ``finally`` block cannot
    protect against SIGKILL, so only a real kill proves the tree is safe.

HOW THE STUB IS FOUND: test D is started with a private ``TMPDIR``, so its
    private copy of ``commit_guardian/`` (and its fixture checkout) land under
    a directory this test owns. The poll looks for test D's POISONED_SOURCE in
    the real shared module and in ``<private TMPDIR>/<SEAM_COPY_PREFIX>*/
    scripts/commit_guardian/_authored_change.py``. A third test checks that the
    unpoisoned copy behaves exactly like the repository's own checks, so test
    D's could-not-check evidence can only come from the poison.

SAFETY NET: when test D still wrote into the tree (the defect), the kill test
    restores the original bytes and modification time of the real module after
    asserting, so a red run of this test does not itself leave the hook broken.
    A killed run also leaves a linked checkout and two fixture branches
    registered against the repository; both tests remove them.

DECISION HISTORY:
- 2026-11-17 [isolate-ge120e1-test-d]: Created for GE-120e-1-iii after a
  read-only review on origin/main 1b4a4b859 found test D writing its stub into
  the real templates file and restoring it only in a finally block.
"""
# @ac-tag: GE-120e-1-iii

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import unlink_checkout
from unit_tests.portability.ge_120e_1._support import (
    _COMMIT_GUARDIAN_TEMPLATES,
    _REPO_ROOT,
    NoAuthorMergeTestCase,
    _run_git,
)
from unit_tests.portability.ge_120e_1.test_ge_120e_1_boundary_and_seam import (
    POISONED_SOURCE,
    SEAM_COPY_PREFIX,
    make_private_guardian_copy,
    remove_private_guardian_copy,
    run_both_checks,
)

logger = logging.getLogger(__name__)

_REAL_SHARED_MODULE = _COMMIT_GUARDIAN_TEMPLATES / "_authored_change.py"
_TEST_D_ID = (
    "unit_tests.portability.ge_120e_1.test_ge_120e_1_boundary_and_seam."
    "TestBothSelfDerivingChecksInspectTheSameAuthoredSet"
)
_COPY_GLOB = f"{SEAM_COPY_PREFIX}*/scripts/commit_guardian/_authored_change.py"
_FIXTURE_DIR_PREFIX = "ge120e1-noauthor-"
_RUN_TIMEOUT_S = 300.0
_POLL_INTERVAL_S = 0.01


def _snapshot() -> tuple[str, int, str]:
    """Bytes hash and mtime of the real shared module, plus ``git status`` of templates/."""
    digest = hashlib.sha256(_REAL_SHARED_MODULE.read_bytes()).hexdigest()
    mtime_ns = _REAL_SHARED_MODULE.stat().st_mtime_ns
    status = _run_git(["status", "--porcelain", "--", "templates/"], cwd=_REPO_ROOT).stdout
    return digest, mtime_ns, status


def _holds_stub(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return POISONED_SOURCE in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # The copy is removed by test D's cleanup while we poll; a vanished
        # file is simply "not holding the stub".
        logger.warning("Could not read %s while polling for the stub: %s", path, exc)
        return False


def _stub_in_copy(private_tmp: Path) -> bool:
    return any(_holds_stub(path) for path in private_tmp.glob(_COPY_GLOB))


def _start_test_d(private_tmp: Path, log_path: Path) -> subprocess.Popen:
    """Start test D as its own process group with TMPDIR pointed at *private_tmp*."""
    env = {**os.environ, "TMPDIR": str(private_tmp)}
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            return subprocess.Popen(
                [sys.executable, "-m", "unittest", "-v", _TEST_D_ID],
                cwd=str(_REPO_ROOT),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except OSError as exc:
        logger.warning("Could not start test D as a process: %s", exc)
        raise


def _kill_group(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            logger.warning("Test D process group was already gone: %s", exc)
    proc.wait(timeout=60)


def _remove_leftovers(private_tmp: Path) -> None:
    """Remove the fixture checkout and branches a killed test D left registered."""
    for fixture_dir in private_tmp.glob(f"{_FIXTURE_DIR_PREFIX}*"):
        suffix = fixture_dir.name[len(_FIXTURE_DIR_PREFIX):]
        unlink_checkout(_REPO_ROOT, ["--force", str(fixture_dir)], check=False)
        _run_git(["branch", "-D", f"ge120e1-ours-{suffix}"], cwd=_REPO_ROOT)
        _run_git(["branch", "-D", f"ge120e1-theirs-{suffix}"], cwd=_REPO_ROOT)
    shutil.rmtree(private_tmp, ignore_errors=True)


class TestSeamTestWritesNothingIntoTheRepository(unittest.TestCase):
    """GE-120e-1-iii: test D, run to completion and killed mid-run, leaves the
    real shared module and the git status of templates/ exactly as they were."""

    def setUp(self) -> None:
        self.private_tmp = Path(tempfile.mkdtemp(prefix="ge120e1iii-"))
        self.log_path = self.private_tmp / "test_d.log"
        self.original_bytes = _REAL_SHARED_MODULE.read_bytes()
        original_stat = _REAL_SHARED_MODULE.stat()
        self.original_times = (original_stat.st_atime_ns, original_stat.st_mtime_ns)

    def tearDown(self) -> None:
        if _REAL_SHARED_MODULE.read_bytes() != self.original_bytes:
            # Safety net for the defect only: put the real hook back so a red
            # run of this test does not leave the tree broken.
            _REAL_SHARED_MODULE.write_bytes(self.original_bytes)
            os.utime(_REAL_SHARED_MODULE, ns=self.original_times)
        _remove_leftovers(self.private_tmp)

    def _log_text(self) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read the test D log: %s", exc)
            return f"<no log: {exc}>"

    def test_ge120e1iii_seam_test_poisons_a_copy_and_never_the_real_shared_module(self) -> None:
        # covers: GE-120e-1-iii
        # angle: seam
        before = _snapshot()
        proc = _start_test_d(self.private_tmp, self.log_path)
        seen_in_real = False
        seen_in_copy = False
        deadline = time.monotonic() + _RUN_TIMEOUT_S
        try:
            while proc.poll() is None:
                seen_in_real = seen_in_real or _holds_stub(_REAL_SHARED_MODULE)
                seen_in_copy = seen_in_copy or _stub_in_copy(self.private_tmp)
                if time.monotonic() > deadline:
                    self.fail(f"test D did not finish within {_RUN_TIMEOUT_S}s:\n{self._log_text()}")
                time.sleep(_POLL_INTERVAL_S)
        finally:
            _kill_group(proc)
        after = _snapshot()
        log_text = self._log_text()

        self.assertFalse(
            seen_in_real,
            "test D wrote its always-raising stub into the REAL "
            f"{_REAL_SHARED_MODULE}; a killed run would leave it there.\n{log_text}",
        )
        self.assertEqual(
            before, after,
            "The real shared module (sha256, mtime_ns) or `git status -- templates/` "
            f"changed across a test D run: before={before!r} after={after!r}\n{log_text}",
        )
        self.assertEqual(proc.returncode, 0, f"test D itself must still pass:\n{log_text}")
        self.assertTrue(
            seen_in_copy,
            "test D passed but its stub was never seen in a private copy under "
            f"{self.private_tmp}/{_COPY_GLOB}; the poisoning must happen in a copy.\n{log_text}",
        )

    def test_ge120e1iii_killed_seam_test_leaves_the_repository_tree_unchanged(self) -> None:
        # covers: GE-120e-1-iii
        # angle: failure
        before = _snapshot()
        proc = _start_test_d(self.private_tmp, self.log_path)
        stub_place = None
        deadline = time.monotonic() + _RUN_TIMEOUT_S
        try:
            while stub_place is None:
                if _holds_stub(_REAL_SHARED_MODULE):
                    stub_place = "real"
                elif _stub_in_copy(self.private_tmp):
                    stub_place = "copy"
                elif proc.poll() is not None:
                    self.fail(f"test D finished before its stub was ever in place:\n{self._log_text()}")
                elif time.monotonic() > deadline:
                    self.fail(f"the stub was not in place within {_RUN_TIMEOUT_S}s:\n{self._log_text()}")
                else:
                    time.sleep(_POLL_INTERVAL_S)
        finally:
            # SIGKILL the whole group at the moment the stub is in place: no
            # finally block in test D can run.
            _kill_group(proc)
        after = _snapshot()

        self.assertEqual(proc.returncode, -signal.SIGKILL, "test D must have been killed, not finished")
        self.assertEqual(
            before, after,
            f"A test D run killed while its stub was in place (in the {stub_place}) left "
            "the real shared module (sha256, mtime_ns) or `git status -- templates/` "
            f"changed: before={before!r} after={after!r}",
        )
        self.assertEqual(stub_place, "copy", "the stub must only ever be in a private copy")


class TestUnpoisonedCopyBehavesExactlyLikeTheRepositoryChecks(NoAuthorMergeTestCase):
    """GE-120e-1-iii, third clause: test D's could-not-check evidence must come
    from the poison alone. Unpoisoned, the copied checks must behave exactly
    like the repository's own (same exit status, same output once the copy's
    path is replaced by the real one) and report no could-not-check, so a copy
    that is broken some other way cannot make test D pass."""

    def test_ge120e1iii_unpoisoned_copy_behaves_exactly_like_the_repository_checks(self) -> None:
        # covers: GE-120e-1-iii
        # angle: discrimination
        guardian_copy = make_private_guardian_copy()
        try:
            self.assertNotIn(
                _REPO_ROOT.resolve(), guardian_copy.resolve().parents,
                f"The private copy {guardian_copy} must live outside the repository.",
            )
            symlinks = [str(path) for path in guardian_copy.parents[1].rglob("*") if path.is_symlink()]
            self.assertEqual(symlinks, [], "The copy must be real files: a symlinked check imports the real module.")
            copied = run_both_checks(guardian_copy, self.fixture.root)
            real = run_both_checks(_COMMIT_GUARDIAN_TEMPLATES, self.fixture.root)
        finally:
            remove_private_guardian_copy(guardian_copy)

        for name, from_copy, from_repo in zip(
            ("check_contract_shrinking.py", "check_doc_frontmatter.py"), copied, real, strict=True,
        ):
            copy_text = (from_copy.stdout + from_copy.stderr).replace(
                str(guardian_copy), str(_COMMIT_GUARDIAN_TEMPLATES),
            )
            repo_text = from_repo.stdout + from_repo.stderr
            self.assertEqual(
                (from_copy.returncode, copy_text), (from_repo.returncode, repo_text),
                f"{name} run from the private copy must behave exactly like the repository's own.",
            )
            self.assertNotIn(
                "could_not_check", copy_text.lower(),
                f"Unpoisoned, {name} must not report could-not-check, or test D proves nothing: {copy_text!r}",
            )


if __name__ == "__main__":
    unittest.main()
