"""
MODULE: unit_tests/portability/test_bp_900h6i.py
GOAL: RED test-first stubs for AC BP-900h-6-i — "The use-the-install step
    mutates only a target it is entitled to destroy, and refuses anything
    else untouched".
AC: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-6-i.yaml

CONTRACT UNDER TEST (fixed here because no entitlement check exists yet in
scripts/ci/_use_install_step.py — confirmed by Read: run_use_install_step()
unconditionally calls _init_git_repo, _isolate_precommit_registry_for_scratch_fixture
(which opens the on-disk .pre-commit-config.yaml path and calls write_text on
it directly — following a symlink if that path is one), _install_precommit_hook,
_stage_adopter_change, and _attempt_commit, with no test anywhere of what the
target directory is):

    1. Against an UNENTITLED target — a directory already inside a git
       working tree holding a commit the step did not create — the step must
       refuse BEFORE any mutation: no git-repo state change, no
       skills_config.json rewrite, no registry rewrite, no new commit, and
       every path present beforehand must be byte-identical afterwards. It
       must exit non-zero and name the target path and the failed
       entitlement condition.
    2. Even against an ENTITLED target, if the deployed .pre-commit-config.yaml
       is a symlink resolving to a shared file outside the target root, that
       shared file must be byte-identical after the run — the narrowing must
       never write through the link.
    3. Against an ENTITLED, disposable target (freshly built, no prior git
       history), the step must still run to completion and produce
       BP-900h-6's result — the positive control that stops "refuse
       everything" from being accepted as a fix.
    4. The whole guarded behaviour must be reached by the EXACT command
       .github/workflows/ci.yml parses for the consumer-simulation step — not
       just present in the module. At AC-authoring time that command carries
       no --use-install flag (ci.yml line ~389), so this entry is RED BY
       DESIGN and must stay red until a separate ticket adds the flag.

Every entry below is invoked through the real subprocess entry point
(``scripts/ci/check_consumer_install.py``) — never by importing
``_use_install_step`` and calling a helper directly — per this AC's
REACHABILITY clause and the repository's documented history of grep/helper-only
tests passing on dead code.

RED AT AUTHORING TIME: none of the entitlement, symlink-safety, or reporting
behaviour described above exists. Entries 1, 2, and 4 are expected to fail;
entry 3 is a positive control that already passes today (nothing currently
refuses an entitled target) and is expected to keep passing once entitlement
checks are added — see the DECISION HISTORY note at the bottom for why it is
deliberately not included in this ticket's red_baseline.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"
_CI_YML_PATH = _WORKTREE_ROOT / ".github" / "workflows" / "ci.yml"

_HOOK_ID_PATTERN = re.compile(r"      - id: (\S+)")

# Mirrors the run consumer install simulation step's "- name:" anchor in
# ci.yml, tolerant of the comment lines between the name and the run: line.
_CI_STEP_PATTERN = re.compile(
    r"- name: Run consumer install simulation\n(?:\s*#.*\n)*\s*run:\s*(?P<cmd>.+)"
)


def _run_check_consumer_install(
    target_dir: Path, extra_args: list[str]
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(_SCRIPT_PATH),
        "--package-dir",
        str(_WORKTREE_ROOT),
        "--target-dir",
        str(target_dir),
        *extra_args,
    ]
    return subprocess.run(argv, capture_output=True, text=True, timeout=180, check=False)


def _census(target_dir: Path) -> dict[str, bytes]:
    """Full path-set + byte-content census of ``target_dir``, excluding ``.git``
    internals (whose object encoding is not what BP-900h-6-i's "byte-identical
    content" clause is about — the working-tree files are).
    """
    census: dict[str, bytes] = {}
    for path in sorted(target_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(target_dir)
        if ".git" in rel.parts:
            continue
        census[str(rel)] = path.read_bytes()
    return census


def _commit_count(target_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _extract_ci_command() -> str:
    text = _CI_YML_PATH.read_text(encoding="utf-8")
    match = _CI_STEP_PATTERN.search(text)
    if not match:
        raise AssertionError(
            "Could not locate the 'Run consumer install simulation' step's run: "
            f"line in {_CI_YML_PATH}"
        )
    return match.group("cmd").strip()


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


class TestBp900h6iEntitlement(unittest.TestCase):
    """Entries 1-3: entitlement, symlink safety, and the positive control.

    A single golden build is produced once in setUpClass and copied fresh
    into each test's own scratch directory, since scripts/build.py takes
    several real seconds per invocation and none of these three entries need
    a fresh build of their own — only a fresh, isolated COPY of one.
    """

    _golden_tmp: tempfile.TemporaryDirectory[str]
    _golden_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._golden_tmp = tempfile.TemporaryDirectory()
        cls._golden_dir = Path(cls._golden_tmp.name) / "golden_install"
        build_result = subprocess.run(
            [sys.executable, str(_WORKTREE_ROOT / "scripts" / "build.py"),
             "--target-dir", str(cls._golden_dir)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if build_result.returncode != 0:
            raise RuntimeError(
                "Precondition failed: could not build the golden install fixture.\n"
                f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._golden_tmp.cleanup()

    def _fresh_copy(self, dest: Path) -> None:
        shutil.copytree(self._golden_dir, dest)

    def test_bp900h6i_step_refuses_an_unentitled_target_and_leaves_it_byte_identical(self) -> None:
        # covers: BP-900h-6-i
        # angle: criterion
        """A directory already inside a git working tree holding a commit it
        did not create (a stand-in for a developer's real working tree) must
        be refused before ANY mutation: no new commit, no changed bytes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "developer_tree"
            self._fresh_copy(target_dir)

            _git(["init"], target_dir)
            _git(["config", "user.email", "dev@example.invalid"], target_dir)
            _git(["config", "user.name", "Developer"], target_dir)
            _git(["add", "-A"], target_dir)
            pre_commit = _git(["commit", "-m", "developer's pre-existing commit"], target_dir)
            self.assertEqual(
                0,
                pre_commit.returncode,
                msg=(
                    "Precondition failed: the developer's pre-existing commit must itself "
                    f"succeed.\nstdout:\n{pre_commit.stdout}\nstderr:\n{pre_commit.stderr}"
                ),
            )

            pre_census = _census(target_dir)
            pre_commit_count = _commit_count(target_dir)

            result = _run_check_consumer_install(target_dir, ["--skip-build", "--use-install"])

            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    "Expected the use-install step to REFUSE an unentitled target (already "
                    "inside a git working tree holding a commit the step did not create), "
                    "naming the target path and the failed entitlement condition, before any "
                    "mutation. Today run_use_install_step() performs no entitlement check at "
                    "all and unconditionally git-inits, rewrites the registry, and commits.\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                str(target_dir),
                combined,
                msg=f"Refusal must name the target path {target_dir}.\nOutput:\n{combined}",
            )

            post_census = _census(target_dir)
            post_commit_count = _commit_count(target_dir)

            self.assertEqual(
                pre_commit_count,
                post_commit_count,
                msg="No new commit may exist that did not exist before the refused run.",
            )
            self.assertEqual(
                pre_census,
                post_census,
                msg="Every path present beforehand must be byte-identical afterwards.",
            )

    def test_bp900h6i_shared_artifact_behind_a_symlinked_registry_is_never_written_through(
        self,
    ) -> None:
        # covers: BP-900h-6-i
        # angle: failure
        """In an ENTITLED target whose deployed .pre-commit-config.yaml is a
        symlink to a shared file several installs read, that shared file must
        be byte-identical after the run, whichever branch the step took.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target_dir = tmp_path / "entitled_install"
            self._fresh_copy(target_dir)

            shared_dir = tmp_path / "shared_build_artifact"
            shared_dir.mkdir()
            shared_config = shared_dir / ".pre-commit-config.yaml"
            registry_path = target_dir / ".pre-commit-config.yaml"
            shared_config.write_text(registry_path.read_text(encoding="utf-8"), encoding="utf-8")
            shared_bytes_before = shared_config.read_bytes()

            registry_path.unlink()
            registry_path.symlink_to(shared_config)

            result = _run_check_consumer_install(target_dir, ["--skip-build", "--use-install"])

            shared_bytes_after = shared_config.read_bytes()
            self.assertEqual(
                shared_bytes_before,
                shared_bytes_after,
                msg=(
                    "The shared artifact a symlinked registry resolves to must be "
                    "byte-identical after the run, regardless of which branch the step "
                    "took. Today _isolate_precommit_registry_for_scratch_fixture opens "
                    "target_dir/.pre-commit-config.yaml and calls write_text on it "
                    "directly, which follows the symlink and rewrites the shared file "
                    f"in place.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )

    def test_bp900h6i_an_entitled_disposable_target_still_completes(self) -> None:
        # covers: BP-900h-6-i
        # angle: deployed
        """The did-not-turn-the-step-off control: a freshly built, disposable
        target with no prior git history must still run to completion, so the
        entitlement fix above is not satisfied by refusing everything.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "disposable_install"
            self._fresh_copy(target_dir)

            result = _run_check_consumer_install(target_dir, ["--skip-build", "--use-install"])

            self.assertEqual(
                0,
                result.returncode,
                msg=(
                    "An entitled disposable target (freshly built, no prior git history) "
                    "must still complete BP-900h-6's use-install result — the cheapest "
                    "passing fix for the must-refuse entries above is to refuse everything, "
                    f"which would fail here.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )
            self.assertIn("EXECUTED GUARDS", result.stdout + result.stderr)


class TestBp900h6iReachability(unittest.TestCase):
    def test_bp900h6i_the_refusal_is_reached_by_the_command_the_workflow_actually_runs(
        self,
    ) -> None:
        # covers: BP-900h-6-i
        # angle: reachability
        """Run the EXACT command ci.yml parses for the consumer-simulation
        step against an unentitled target. RED BY DESIGN: that command
        carries no --use-install flag today, so the entitlement guard (and
        the whole use-install step) is entirely unreachable from CI.
        """
        ci_command = _extract_ci_command()
        self.assertIn(
            "check_consumer_install.py",
            ci_command,
            msg=f"Could not locate the consumer-simulation command in ci.yml: {ci_command!r}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            workspace_dir = Path(tmp) / "ci_workspace"
            workspace_dir.mkdir()
            (workspace_dir / "leafcutter-ai").symlink_to(_WORKTREE_ROOT)

            _git(["init"], workspace_dir)
            _git(["config", "user.email", "dev@example.invalid"], workspace_dir)
            _git(["config", "user.name", "Developer"], workspace_dir)
            (workspace_dir / "README.md").write_text("pre-existing developer content\n",
                                                       encoding="utf-8")
            _git(["add", "README.md"], workspace_dir)
            pre_commit = _git(["commit", "-m", "developer's pre-existing commit"], workspace_dir)
            self.assertEqual(
                0,
                pre_commit.returncode,
                msg=(
                    "Precondition failed: the developer's pre-existing commit must itself "
                    f"succeed.\nstdout:\n{pre_commit.stdout}\nstderr:\n{pre_commit.stderr}"
                ),
            )

            pre_readme_bytes = (workspace_dir / "README.md").read_bytes()
            pre_commit_count = _commit_count(workspace_dir)

            argv = shlex.split(ci_command)
            argv[0] = sys.executable  # adapt the interpreter binary only; arguments unchanged
            result = subprocess.run(
                argv, cwd=str(workspace_dir), capture_output=True, text=True, timeout=180,
                check=False,
            )

            readme_path = workspace_dir / "README.md"
            post_readme_bytes = readme_path.read_bytes() if readme_path.exists() else None
            post_commit_count = _commit_count(workspace_dir)

            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    "Running the EXACT command ci.yml parses for the consumer-simulation "
                    "step against an unentitled target (a directory already inside a git "
                    "working tree holding a commit it did not create) must fail. RED TODAY "
                    "BY DESIGN: ci.yml carries no --use-install flag, so the "
                    "entitlement-guarded step — and the guard itself — is entirely "
                    f"unreachable from CI. Parsed command: {ci_command!r}\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )
            self.assertEqual(
                pre_readme_bytes,
                post_readme_bytes,
                msg="Pre-existing developer content must be unmutated.",
            )
            self.assertEqual(
                pre_commit_count,
                post_commit_count,
                msg="No new commit may exist that did not exist before.",
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/BP-900h-6-i]: Initial RED test-first stubs for
#   all four test_spec descriptors. Entries 1, 2, and 4 fail today (confirmed
#   by running this file — see the red_baseline in this ticket's sign-off
#   comment). Entry 3 (test_bp900h6i_an_entitled_disposable_target_still_completes)
#   is a deliberate positive control per the AC's own test_rationale ("without
#   this entry the cheapest passing fix is to refuse everything") and is
#   EXPECTED to already pass today, since no entitlement check exists yet to
#   wrongly refuse an entitled target — it is not included in the ticket's
#   red_baseline for that reason, and must be re-verified still green once
#   entitlement checks are added by the coder phase.
# ====================================================================
