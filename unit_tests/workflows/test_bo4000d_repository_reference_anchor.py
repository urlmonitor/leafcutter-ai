"""
MODULE: unit_tests/workflows/test_bo4000d_repository_reference_anchor.py
GOAL: Behavioral tests for BO-4000d — the worktree step asks about the
    repository using a reference it derives from the target it resolved, so
    its answer does not depend on the directory the run was launched from.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_4d8a1c41-0b9. Every
    worktree_repo_facts.py subcommand defaults its repository reference to
    the process cwd. A phase agent's cwd in the dev self-hosting layout is
    the workspace parent, which is NOT a git checkout, so `facts` answered
    same_repository: null for a present, healthy, correctly-branched linked
    worktree and `base` answered all-null. The reuse guard fell through, the
    base lookup then failed, and the run aborted worktree-base-unavailable
    with zero phase agents spawned. See BO-4000d.yaml.
ARCHITECTURE: The cwd-sensitivity is proven by EXECUTING the real
    templates/scripts/worktree_repo_facts.py as a subprocess against a
    temporary REAL git repository with a real linked worktree, with cwd set
    to a directory that is not a git checkout — the exact condition that
    broke. The real answers are then fed through
    unit_tests/_workflow_engine_harness.py so the abort and the reuse are
    observed as dispatch facts. The driver half is closed by parsing every
    worktree_repo_facts.py invocation out of build-feature.js and requiring
    each to carry an explicit reference; the invocations are derived, never
    counted in advance, so a new unanchored call site fails immediately.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_FACTS_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "worktree_repo_facts.py"
_SCRIPT_NAME = "worktree_repo_facts.py"
_QUOTE_CHARS = "`\"'"

TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"
EPIC_FOLDER_PARTS = ("tickets", "00_inbox", "epics", "EPIC-AnchoredWorktree")
TEMP_BRANCH = "epic/anchored-worktree"

# Labels belonging to the Resolve-Target phase itself; anything else dispatched
# is a phase agent, which the incident proved were never reached.
_FACTS_LABELS = frozenset({
    "resolve-target", "worktree-facts-resolved", "worktree-base",
    "worktree-facts-location", "branch-standing", "worktree-setup",
})


def _phase_calls(result):
    """Every dispatch that is not one of the Resolve-Target-phase facts calls."""
    return [c for c in result.agent_calls if c.label not in _FACTS_LABELS]


def _git(cwd: Path, args: list[str]) -> None:
    """Run a git command in *cwd*, raising on failure."""
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )


def _invocations(source: str) -> list[str]:
    """Every worktree_repo_facts.py command the driver *source* constructs.

    Derived by locating the script name in non-comment lines and reading out
    to the end of the enclosing string literal (whichever of ` " ' opened
    it), so the set of call sites comes from the driver rather than from a
    number written down here. A newly added call site is therefore checked
    the moment it appears.

    Args:
        source: The full text of build-feature.js.

    Returns:
        One command string per invocation, each beginning at the script name.
    """
    commands: list[str] = []
    for line in source.splitlines():
        if line.lstrip().startswith(("//", "*", "/*")):
            continue
        cursor = 0
        while True:
            start = line.find(_SCRIPT_NAME, cursor)
            if start == -1:
                break
            opener = next(
                (ch for ch in reversed(line[:start]) if ch in _QUOTE_CHARS), None
            )
            end = line.find(opener, start) if opener else -1
            commands.append(line[start:end] if end != -1 else line[start:])
            cursor = start + len(_SCRIPT_NAME)
    return commands


def _flag_value(tokens: list[str], flag: str) -> str | None:
    """The value following *flag* in *tokens*, or None when absent/valueless."""
    if flag not in tokens:
        return None
    index = tokens.index(flag)
    if index + 1 >= len(tokens):
        return None
    return tokens[index + 1]


def _reference_argument(tokens: list[str]) -> tuple[str, str | None]:
    """The subcommand and the repository reference it was given.

    Each subcommand of worktree_repo_facts.py spells its reference
    differently, and each of them defaults to the process cwd when it is
    omitted — which is precisely the defect.

    Args:
        tokens: The shell-split invocation, starting at the script name.

    Returns:
        ``(subcommand, reference)``; *reference* is None when the invocation
        left the subcommand's reference to its cwd default.

    Raises:
        AssertionError: The invocation uses a subcommand this test has not
            been taught to check. Failing closed is deliberate: a new
            subcommand must state where its reference goes.
    """
    subcommand = tokens[1] if len(tokens) > 1 else ""
    if subcommand == "facts":
        return subcommand, _flag_value(tokens, "--reference")
    if subcommand == "base":
        positional = [t for t in tokens[2:] if not t.startswith("-")]
        return subcommand, positional[0] if positional else None
    if subcommand == "branch-standing":
        return subcommand, _flag_value(tokens, "--repo")
    raise AssertionError(
        f"unrecognised worktree_repo_facts.py subcommand {subcommand!r}; teach "
        "this test where that subcommand's repository reference goes before "
        "adding a call site for it"
    )


class _RealRepositoryFixture(unittest.TestCase):
    """A temporary REAL repository, a real linked worktree, and a non-git cwd."""

    # Declared because setUpClass assigns them on `cls`, which mypy does not
    # infer as class attributes. Bare annotations are never evaluated, so this
    # has no runtime effect.
    _tmp: ClassVar[tempfile.TemporaryDirectory]
    main_checkout: ClassVar[Path]
    worktree_base: ClassVar[Path]
    linked: ClassVar[Path]
    epic_target: ClassVar[Path]
    not_a_repo: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="bo4000d_anchor_")
        root = Path(cls._tmp.name)

        cls.main_checkout = root / "main-repo"
        cls.main_checkout.mkdir()
        _git(cls.main_checkout, ["init", "-q"])
        _git(cls.main_checkout, ["config", "user.email", "t@example.com"])
        _git(cls.main_checkout, ["config", "user.name", "t"])
        epic_folder = cls.main_checkout.joinpath(*EPIC_FOLDER_PARTS)
        epic_folder.mkdir(parents=True)
        (epic_folder / "01_TICKET-x.md").write_text("# x\n", encoding="utf-8")
        _git(cls.main_checkout, ["add", "."])
        _git(cls.main_checkout, ["commit", "-q", "-m", "init"])

        cls.worktree_base = root / "worktrees"
        cls.linked = cls.worktree_base / "EPIC-AnchoredWorktree"
        cls.worktree_base.mkdir()
        _git(
            cls.main_checkout,
            ["worktree", "add", "-q", "-b", TEMP_BRANCH, str(cls.linked)],
        )
        # The anchor the fix derives: the absolute epic folder of the target,
        # by construction inside the repository.
        cls.epic_target = cls.linked.joinpath(*EPIC_FOLDER_PARTS)

        cls.not_a_repo = root / "launched-from-here"
        cls.not_a_repo.mkdir()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            _git(cls.main_checkout, ["worktree", "remove", "-f", str(cls.linked)])
        except subprocess.CalledProcessError:
            pass
        cls._tmp.cleanup()

    def setUp(self) -> None:
        probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(self.not_a_repo), capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(
            probe.returncode, 0,
            "the launched-from directory must NOT be a git checkout, or this "
            "suite is not testing the condition that broke",
        )

    def _facts_script(self, *args: str) -> dict:
        """Run the REAL facts script from the non-git directory."""
        proc = subprocess.run(
            [sys.executable, str(_FACTS_SCRIPT), *args],
            cwd=str(self.not_a_repo), capture_output=True, text=True, check=True,
        )
        return json.loads(proc.stdout)


class TestUnanchoredCallsAreCwdSensitive(_RealRepositoryFixture):
    def test_facts_without_a_reference_cannot_tell_it_is_the_same_repository(self) -> None:
        # covers: BO-4000d
        # angle: failure
        """Run from a directory that is not a checkout, `facts` reports a real
        linked worktree correctly in every respect EXCEPT same_repository,
        which is null — the degenerate answer that made the reuse guard fall
        through. Pinning it documents why the anchor is necessary and fails
        loudly if the script's cwd default ever changes.
        """
        answer = self._facts_script("facts", str(self.linked))
        self.assertIsNone(answer["same_repository"])
        self.assertTrue(answer["exists"])
        self.assertTrue(answer["is_linked_worktree"])
        self.assertFalse(answer["is_main_checkout"])

    def test_base_without_a_reference_resolves_nothing_outside_a_checkout(self) -> None:
        # covers: BO-4000d
        # angle: failure
        """Run from the same directory, `base` answers all-null — the second
        degenerate answer, the one the run aborted on.
        """
        answer = self._facts_script("base")
        self.assertIsNone(answer["main_checkout"])
        self.assertIsNone(answer["worktree_base"])
        self.assertIsNone(answer["layout"])


class TestAnchoredCallsAnswerIndependentlyOfCwd(_RealRepositoryFixture):
    def test_facts_anchored_on_the_target_reports_the_same_repository(self) -> None:
        # covers: BO-4000d
        # angle: criterion
        """With a reference derived from the target, `facts` answers
        same_repository true from the very same non-git directory, so the
        whole reuse predicate holds for a healthy worktree.
        """
        answer = self._facts_script(
            "facts", str(self.linked), "--reference", str(self.epic_target)
        )
        self.assertTrue(answer["same_repository"])
        self.assertTrue(answer["exists"])
        self.assertTrue(answer["is_linked_worktree"])
        self.assertFalse(answer["is_main_checkout"])

    def test_base_anchored_on_the_target_resolves_the_worktree_base(self) -> None:
        # covers: BO-4000d
        # angle: criterion
        """With the same reference, `base` resolves a non-null main checkout
        and worktree base from outside any checkout.
        """
        answer = self._facts_script("base", str(self.epic_target))
        self.assertIsNotNone(answer["main_checkout"])
        self.assertIsNotNone(answer["worktree_base"])
        self.assertEqual(Path(answer["main_checkout"]).resolve(), self.main_checkout.resolve())
        self.assertEqual(Path(answer["worktree_base"]).resolve(), self.worktree_base.resolve())


class TestRealAnswersDecideTheRun(_RealRepositoryFixture):
    def test_unanchored_answers_abort_the_run_and_anchored_answers_do_not(self) -> None:
        # covers: BO-4000d
        # angle: real_artifact
        """The two real answers above, fed to build-feature.js's own top-level
        body, reproduce the incident and its absence: the cwd-defaulted pair
        aborts worktree-base-unavailable with no phase agent spawned, while
        the anchored pair reuses the healthy worktree and the run goes on.
        """
        unanchored_facts = self._facts_script("facts", str(self.linked))
        unanchored_base = self._facts_script("base")
        responses = bfx.success_label_responses(
            ticket_paths=[TICKET],
            resolved_worktree_path=str(self.linked),
            resolved_worktree_facts=unanchored_facts,
        )
        responses["worktree-base"] = bfx.envelope(unanchored_base)
        aborted = run_workflow_under_e2(
            _BUILD_FEATURE_JS, label_responses=responses, args={"target": bfx.EPIC_NAME}
        )
        payload = aborted.result or {}
        self.assertEqual(payload.get("abort_reason"), "worktree-base-unavailable")
        self.assertTrue(payload.get("worktree_undetermined"))
        self.assertEqual(_phase_calls(aborted), [])

        anchored_facts = self._facts_script(
            "facts", str(self.linked), "--reference", str(self.epic_target)
        )
        anchored_base = self._facts_script("base", str(self.epic_target))
        responses = bfx.success_label_responses(
            ticket_paths=[TICKET],
            resolved_worktree_path=str(self.linked),
            resolved_worktree_facts=anchored_facts,
        )
        responses["worktree-base"] = bfx.envelope(anchored_base)
        proceeded = run_workflow_under_e2(
            _BUILD_FEATURE_JS, label_responses=responses, args={"target": bfx.EPIC_NAME}
        )
        self.assertNotEqual(
            (proceeded.result or {}).get("abort_reason"), "worktree-base-unavailable"
        )
        self.assertTrue(_phase_calls(proceeded), f"stderr={proceeded.stderr!r}")


class TestDriverAnchorsEveryInvocation(unittest.TestCase):
    def test_every_worktree_repo_facts_invocation_in_the_driver_is_anchored(self) -> None:
        # covers: BO-4000d
        # angle: reachability
        """Closes the loop on the driver: the executable behaviour proven
        above is the one build-feature.js really gets. Every
        worktree_repo_facts.py command the driver constructs is parsed out of
        it and must carry an explicit reference that is interpolated from the
        run's own resolved target — not omitted, and not a fixed literal,
        either of which is the cwd default that broke the run.
        """
        source = _BUILD_FEATURE_JS.read_text(encoding="utf-8")
        commands = _invocations(source)
        self.assertTrue(
            commands, "no worktree_repo_facts.py invocation found in the driver"
        )
        seen = set()
        for command in commands:
            with self.subTest(command=command):
                subcommand, reference = _reference_argument(shlex.split(command))
                seen.add(subcommand)
                if reference is None:
                    # self.fail is typed NoReturn, so this also narrows
                    # `reference` to str for the interpolation check below.
                    self.fail(
                        f"the {subcommand!r} invocation leaves its repository "
                        "reference to the process cwd"
                    )
                self.assertIn(
                    "${", reference,
                    f"the {subcommand!r} invocation's reference {reference!r} is a "
                    "fixed literal, not one derived from the resolved target",
                )
        self.assertLessEqual(
            {"facts", "base", "branch-standing"}, seen,
            "the driver's worktree step no longer reaches every subcommand this "
            "record covers; the parse above is not seeing the real call sites",
        )


if __name__ == "__main__":
    unittest.main()
