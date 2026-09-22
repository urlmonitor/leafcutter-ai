"""
MODULE: unit_tests/build_orchestration/test_bo_4100d_4.py
GOAL: RED test stubs for BO-4100d-4 — ``_git_toplevel()`` in
      scripts/setup_ticket_worktree.py (and its parity copy in
      templates/scripts/setup_ticket_worktree.py) must resolve the
      repository from the SUBJECT of the operation, never from the
      location of the running file.

=== The defect ===

``_git_toplevel(anchor=None)`` defaults to
``anchor = Path(__file__).resolve().parent`` — i.e. it assumes "the script
always lives physically inside the repository it operates on" (its own
docstring). That assumption is true only of the checked-out source copy.
Every copy build.py *deploys* violates it:

  - Dev/self-hosting layout: the deployed copy at ``.leafcutter/scripts/``
    sits in the untracked workspace PARENT, so ``git -C <that dir>
    rev-parse --show-toplevel`` fails outright (exit 128) — LOUD.
  - Consumer layout: the deployed copy sits INSIDE the adopter's git
    repository, so the same call SUCCEEDS and silently returns the
    adopter's repo instead of the repo the tool actually belongs to —
    SILENT, and per the AC's own test_rationale this is the more
    important half to pin down: a test written only against the loud
    dev-layout case can be "fixed" by catching the exception and
    re-raising it with a nicer message, leaving the silent case exactly
    as wrong as it was.

=== What varies in each test (and only this) ===

Per AC BO-4100d-4 it_requirements: "Correctness must be demonstrated with
the tool invoked from a copy placed OUTSIDE the repository... location is
the entire defect." Every test below copies the real, unmodified script to
a fresh temporary location (via ``importlib.util.spec_from_file_location``
so the copy's own ``__file__`` genuinely reflects where it now sits — this
is not a mock, it is the actual production module executing from a real
relocated file) and varies ONLY where that copy sits and what the calling
process's current working directory is at call time. Nothing else about
the module is touched.

Both the ``scripts/`` copy and the ``templates/scripts/`` deploy-source
copy are exercised in every test (AC it_requirement 5: "Both copies must
carry the corrected resolution behaviour... do NOT resync the files
wholesale").

=== Red baseline (today, unmodified code) ===

- test_a_copy_outside_the_repository_still_creates_the_workspace_in_the_tools_own_repository:
  RED — raises subprocess.SubprocessError (bare git exit-128 style message)
  because the copy's own directory is outside any repo and CWD is ignored.

- test_a_copy_deployed_inside_a_different_repository_does_not_resolve_that_repository:
  RED — the resolved path silently equals the unrelated repo containing the
  copy, not the repo named by the calling context. This is the load-bearing
  test: it fails today for the *wrong* reason a mock or an in-repo-only test
  cannot detect (no exception is raised at all).

- test_an_unresolvable_location_is_refused_with_the_path_it_tried:
  RED — the raised message names the anchor path (already true today) but
  does not say the copy is deployed outside the repository (not true today).

- test_the_in_repository_copy_keeps_working_unchanged:
  Expected to PASS today (over-trigger control per the AC's test_rationale —
  it must keep passing under any correct fix too) and is therefore excluded
  from the red_baseline per the test-writer protocol (passing tests have no
  place in a red baseline).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_SCRIPT_COPIES = {
    "scripts": _REPO_ROOT / "scripts" / "setup_ticket_worktree.py",
    "templates": _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py",
}


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command anchored at *cwd*, raising on failure.

    Args:
        args: Arguments after ``git`` (e.g. ``["init", "-q"]``).
        cwd: Directory to run the command in.

    Returns:
        The completed subprocess.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path: Path) -> Path:
    """Create a real, minimal git repository at *path* via ``git init``.

    No commits are made — an initialised working tree with a ``.git``
    directory is sufficient for ``git rev-parse --show-toplevel`` to
    resolve. Configures a throwaway identity so any accidental commit in
    future test evolution does not fail on missing user.name/user.email.

    Args:
        path: Directory to initialise as a git repo (created if absent).

    Returns:
        The same *path*, for chaining.
    """
    path.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-q"], cwd=path)
    _run_git(["config", "user.email", "bo4100d4-test@example.com"], cwd=path)
    _run_git(["config", "user.name", "BO-4100d-4 Test"], cwd=path)
    return path


def _load_relocated_copy(real_source: Path, dest_dir: Path):
    """Copy *real_source* to *dest_dir* and import it so its ``__file__`` is the copy.

    Uses ``importlib.util.spec_from_file_location`` with a unique module
    name per call: this is what makes the loaded module's own ``__file__``
    genuinely equal to the relocated path, so ``_git_toplevel()``'s
    ``Path(__file__).resolve().parent`` default anchors from wherever the
    copy actually sits — exactly the production code path a real deployed
    copy exercises, not a mock or a monkeypatched constant.

    Args:
        real_source: Path to the real, unmodified script (never edited).
        dest_dir: Directory the copy should be written into.

    Returns:
        The freshly imported module object.
    """
    import shutil

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "setup_ticket_worktree.py"
    shutil.copy2(real_source, dest_path)
    module_name = f"_bo4100d4_copy_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, dest_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestGitToplevelAnchorDefect(unittest.TestCase):
    """BO-4100d-4 — ``_git_toplevel()`` must anchor on the operation's
    subject, never on the running file's own location."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_root = Path(self._tmp.name)
        self._original_cwd = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._original_cwd)
        self._tmp.cleanup()

    def test_a_copy_outside_the_repository_still_creates_the_workspace_in_the_tools_own_repository(
        self,
    ) -> None:
        # covers: BO-4100d-4
        # angle: criterion
        """AC criteria: a copy deployed outside the repo it manages must still
        resolve the repository the tool belongs to.

        Simulates the dev/self-hosting symptom: the copy is placed in a plain
        temp directory that is NOT inside any git repository (mirrors
        ``.leafcutter/scripts/`` sitting in the untracked workspace parent).
        The calling context (process CWD) IS inside a real repository — the
        subject of the operation. A correct fix resolves the anchor from that
        subject, not from the copy's own (repo-less) directory, so the call
        must succeed and return the calling context's repository.

        DEFECT (unmodified code): ``anchor = Path(__file__).resolve().parent``
        is the copy's directory, which is outside any repo, so
        ``git -C <that dir> rev-parse --show-toplevel`` exits 128 and the
        call raises instead of succeeding. RED via unhandled exception.
        """
        for label, real_source in _SCRIPT_COPIES.items():
            with self.subTest(copy=label):
                copy_dir = self._tmp_root / f"outside_repo_{label}"
                tool_repo = _init_repo(self._tmp_root / f"tool_repo_{label}")

                module = _load_relocated_copy(real_source, copy_dir)

                os.chdir(tool_repo)
                try:
                    resolved = module._git_toplevel()  # noqa: SLF001
                except (subprocess.SubprocessError, OSError) as exc:
                    self.fail(
                        f"[{label}] _git_toplevel() raised {exc!r} when invoked "
                        f"from a copy outside any repo while CWD was a real "
                        f"repository ({tool_repo}). A copy placed outside the "
                        "repository it manages must still resolve the "
                        "repository the tool belongs to (BO-4100d-4 criteria)."
                    )
                    continue

                self.assertEqual(
                    Path(resolved).resolve(),
                    tool_repo.resolve(),
                    f"[{label}] _git_toplevel() must resolve the repository "
                    f"the tool belongs to ({tool_repo}), not fail or resolve "
                    "some other location, when the running copy sits outside "
                    "any repository.",
                )

    def test_a_copy_deployed_inside_a_different_repository_does_not_resolve_that_repository(
        self,
    ) -> None:
        # covers: BO-4100d-4
        # angle: failure
        """AC it_requirement #3 (the silent, load-bearing half): a copy
        deployed INSIDE an unrelated adopter repository must not resolve
        that adopter repository.

        Simulates the consumer-layout symptom exactly: the copy sits inside
        a real, unrelated git repository (the "adopter"), so
        ``git -C <copy dir> rev-parse --show-toplevel`` SUCCEEDS today and
        returns the adopter's repo — no exception anywhere. The calling
        context (process CWD) is a second, distinct repository representing
        the one the tool actually belongs to.

        The assertion is on the RESOLVED PATH, never merely "did not raise" —
        per the AC's own rationale, an assertion that only checks for the
        absence of an exception passes against this exact defect.

        DEFECT (unmodified code): resolves to the adopter's repo (silently
        wrong) instead of the calling context's repo. RED via AssertionError.
        """
        for label, real_source in _SCRIPT_COPIES.items():
            with self.subTest(copy=label):
                adopter_repo = _init_repo(self._tmp_root / f"adopter_repo_{label}")
                copy_dir = adopter_repo / ".leafcutter" / "scripts"
                tool_repo = _init_repo(self._tmp_root / f"tool_repo2_{label}")

                module = _load_relocated_copy(real_source, copy_dir)

                os.chdir(tool_repo)
                resolved = Path(module._git_toplevel()).resolve()  # noqa: SLF001

                self.assertNotEqual(
                    resolved,
                    adopter_repo.resolve(),
                    f"[{label}] _git_toplevel() must NOT silently resolve the "
                    f"unrelated adopter repository ({adopter_repo}) just "
                    "because the deployed copy happens to sit inside it — "
                    "this is the silent consumer-layout half of BO-4100d-4 "
                    "and it raises no exception, so only comparing the "
                    "resolved path (not merely checking for 'no exception') "
                    "can catch it.",
                )
                self.assertEqual(
                    resolved,
                    tool_repo.resolve(),
                    f"[{label}] _git_toplevel() must resolve the repository "
                    f"the tool actually belongs to ({tool_repo}) — the "
                    "subject of the operation — regardless of which "
                    "unrelated repository physically contains the deployed "
                    "copy.",
                )

    def test_an_unresolvable_location_is_refused_with_the_path_it_tried(self) -> None:
        # covers: BO-4100d-4
        # angle: boundary
        """AC it_requirement #4: when NO repository is reachable at all, the
        refusal must name the anchor path it resolved from AND state that
        the copy is deployed outside the repository — a bare
        ``CalledProcessError``/"exit status 128" is not sufficient.

        Both the copy's own directory and the calling context (process CWD)
        are outside any git repository, so resolution can genuinely never
        succeed no matter which of the two a fix chooses to anchor on.

        DEFECT (unmodified code): raises
        ``subprocess.SubprocessError("Failed to resolve git toplevel from "
        "<anchor>: <exc>")`` — it does name the anchor path, but nowhere
        does it say the copy is deployed outside the repository. RED via
        the missing-phrase assertions below.
        """
        for label, real_source in _SCRIPT_COPIES.items():
            with self.subTest(copy=label):
                copy_dir = self._tmp_root / f"unresolvable_copy_{label}"
                no_repo_cwd = self._tmp_root / f"unresolvable_cwd_{label}"
                no_repo_cwd.mkdir(parents=True, exist_ok=True)

                module = _load_relocated_copy(real_source, copy_dir)

                os.chdir(no_repo_cwd)
                with self.assertRaises(
                    Exception,
                    msg=(
                        f"[{label}] _git_toplevel() must refuse (raise) when "
                        "no repository is reachable from either the copy's "
                        "location or the calling context."
                    ),
                ) as cm:
                    module._git_toplevel()  # noqa: SLF001

                message = str(cm.exception)
                lowered = message.lower()
                self.assertTrue(
                    str(copy_dir) in message or str(no_repo_cwd) in message,
                    f"[{label}] refusal message {message!r} must name the "
                    f"anchor path it resolved from (either {copy_dir} or "
                    f"{no_repo_cwd}), per AC it_requirement #4.",
                )
                self.assertIn(
                    "outside",
                    lowered,
                    f"[{label}] refusal message {message!r} must state that "
                    "the copy is deployed OUTSIDE the repository, per AC "
                    "it_requirement #4 — a bare exit-128 message is not "
                    "sufficient.",
                )
                self.assertIn(
                    "repository",
                    lowered,
                    f"[{label}] refusal message {message!r} must refer to "
                    "the repository explicitly, per AC it_requirement #4.",
                )

    def test_the_in_repository_copy_keeps_working_unchanged(self) -> None:
        # covers: BO-4100d-4
        # angle: failure
        """Over-trigger control (per AC test_rationale): invoked from its
        normal in-repo location, the tool must keep resolving exactly as
        before. Without this control, an implementation that refuses every
        location (satisfying the other three tests by always erroring)
        would otherwise look correct.

        This is expected to PASS today and under any correct fix alike — it
        is intentionally NOT evidence of the fix, only a guard against an
        over-broad one. Per the test-writer protocol, a passing test is
        written but excluded from the red_baseline.
        """
        for label, real_source in _SCRIPT_COPIES.items():
            with self.subTest(copy=label):
                # Load the REAL script from its true, unmodified, in-repo
                # location — no copying, no relocation.
                module_name = f"_bo4100d4_inplace_{uuid.uuid4().hex}"
                spec = importlib.util.spec_from_file_location(module_name, real_source)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # The calling context is genuinely inside this repository too,
                # matching real-world invocation of the checked-out source.
                os.chdir(_REPO_ROOT)

                resolved = Path(module._git_toplevel()).resolve()  # noqa: SLF001

                self.assertEqual(
                    resolved,
                    _REPO_ROOT.resolve(),
                    f"[{label}] The in-repository copy at {real_source} must "
                    f"keep resolving its own repository ({_REPO_ROOT}) "
                    "unchanged.",
                )


    def test_an_explicit_anchor_that_does_not_resolve_is_refused_not_silently_replaced(
        self,
    ) -> None:
        # covers: BO-4100d-4
        # angle: boundary
        """An explicit anchor is authoritative: when the caller names a
        subject that is not inside a repository, resolution must FAIL rather
        than quietly fall through to the process working directory.

        This closes the last silent-wrong-repository path in the ordered
        candidate list. `cmd_setup_ticket` passes `ticket_path.parent`; if
        that path were outside the repository and the function fell through,
        it would resolve whatever repository the caller happened to be
        standing in and report success for a workspace in the wrong place --
        the exact defect BO-4100d-4 exists to remove, re-entering through the
        one door the other four tests leave open.

        The cwd is deliberately set to a VALID repository here, so a
        fall-through implementation resolves happily and returns it. Only
        asserting that the call raises can distinguish the two.
        """
        for label, real_source in _SCRIPT_COPIES.items():
            with self.subTest(copy=label):
                copy_dir = self._tmp_root / f"explicit_anchor_copy_{label}"
                not_a_repo = self._tmp_root / f"explicit_anchor_subject_{label}"
                not_a_repo.mkdir(parents=True, exist_ok=True)
                fallback_repo = _init_repo(self._tmp_root / f"fallback_repo_{label}")

                module = _load_relocated_copy(real_source, copy_dir)

                # A perfectly good repository sits at the cwd. A fall-through
                # implementation returns it and passes everything else.
                os.chdir(fallback_repo)

                with self.assertRaises(subprocess.SubprocessError) as caught:
                    module._git_toplevel(not_a_repo)  # noqa: SLF001

                self.assertIn(
                    str(not_a_repo),
                    str(caught.exception),
                    f"[{label}] The refusal must name the anchor the caller "
                    "actually supplied.",
                )


if __name__ == "__main__":
    unittest.main()
