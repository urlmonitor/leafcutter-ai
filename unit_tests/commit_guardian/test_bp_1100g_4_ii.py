"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_4_ii.py
COVERS: BP-1100g-4-ii

GOAL: RED test stubs for the promise-versus-claim check's lifecycle-state
    trigger. BP-1100g-4 built the promise-versus-claim comparison itself
    (``check_proof_promise_claim.py``). This AC pins down WHEN that
    comparison is allowed to fire: ``main()`` currently applies it
    identically to every staged ticket regardless of the ticket's own
    ``status:`` frontmatter, so a ticket that has just been generated from an
    approved AC — ``status: todo``, no implementation yet, no test-writer
    phase run yet — is refused for a promise it has not reached the point of
    owing. The fix must exempt ONLY the still-planned state; started,
    offered-for-hand-off, and unreadable states all remain subject to the
    check exactly as before (fail-closed on anything that cannot be read as
    still-planned).

BUSINESS CONTEXT: found 2026-09-07 by the gate refusing a freshly-generated
    ticket (status todo) for a 'reachability' proof whose test is, by this
    repo's own TDD mandate, the NEXT phase's output — making the documented
    ADR-012 /plan-feature -> /build-ac path unusable end to end. See this
    AC's own YAML (``notes`` field) for the full incident.

ARCHITECTURE: Per CLAUDE.md's "Gate / Workflow ACs — Verify Behaviorally, Not
    by Grep": this is a trigger-condition defect, which is invisible to any
    test that reads ``main()``'s source — an implementation that checks
    every staged ticket and one that checks only what is due are source-
    shaped alike, differing solely in a run-time decision against a value in
    the input. Every test below therefore executes the DEPLOYED hook as a
    real subprocess (``run_hook.py`` wrapping ``check_proof_promise_claim.py``,
    exactly as pre-commit invokes it) under an isolated, freshly
    ``git init``-ed temporary project root — never an import of the module,
    never a grep of its text. ``find_project_root()`` resolves via
    ``git rev-parse --show-toplevel`` from the child process's own cwd, so
    each temp root's own ticket + test tree is what gets scanned, never this
    repository's own (mirrors the isolation pattern already used by
    ``unit_tests/commit_guardian/test_bp_1100g_4_i.py``'s reachability test).

    Mutation-proof design (REQUIRED TEST PROPERTIES #4 from the ticket): the
    "still refused" / "still examined" tests (started, offered-for-hand-off,
    unreadable-state) each build their fixture from the exact same
    ``_build_ticket_fixture`` helper used for the planned (status: todo)
    fixture, changing only the status line (or removing/corrupting it for
    the unreadable cases) — never the promise, the ac_id, or the Test
    Requirements block. Each of those tests ALSO runs the byte-identical
    todo sibling as an in-test control and asserts it IS passed over. This
    is not decorative: because today's ``main()`` refuses every staged
    ticket unconditionally, a bare "started/offered/unreadable must be
    refused" assertion would ALREADY pass against the unfixed code (the bug
    is over-refusal, not under-refusal) and would never turn red. Pairing it
    with the todo-control assertion (which fails today, since nothing is
    exempted yet) is what makes each of these tests a true red-baseline
    proof of the fix rather than a test that was already accidentally
    satisfied by the bug itself.

=== Red baseline ===

    RED today for all five tests:
      - test_planned_work_with_an_unclaimed_promise_is_passed_over_and_says_so
        fails directly: main() refuses status:todo work today (exit 1, no
        "passed over" wording exists anywhere), so the exit-0 /
        "passed over" assertions fail outright.
      - test_the_same_work_once_started_is_still_refused_by_name,
        test_the_same_work_once_offered_for_handoff_is_still_refused_by_name,
        and test_work_with_no_readable_state_is_examined_not_passed_over each
        fail on their in-test todo-control assertion (control_result.returncode
        == 0), since main() does not yet exempt ANY status today.
      - test_handed_off_work_whose_promise_is_claimed_is_not_refused fails on
        its in-test todo-control assertion (asserting "passed over" appears
        in the control's output), since that wording does not exist in
        format_refusal() or main() today.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEPLOYED_RUN_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "run_hook.py"
)
_DEPLOYED_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_proof_promise_claim.py"
)

_SUBPROCESS_TIMEOUT_SECONDS = 60

_SHARED_AC_ID = "ZZ-BP1100G4II-LIFECYCLE"
_SHARED_ANGLE = "reachability"
_SHARED_BEHAVIOUR = "the promise-claim lifecycle demo behaviour is reachable end to end"


def _build_test_requirements_block() -> str:
    """Build the ``## Test Requirements`` fenced YAML body via the REAL serializer.

    Mirrors exactly what ``generate_ticket_from_ac.py``'s
    ``_build_test_requirements_section`` emits — ``yaml.dump`` of a
    ``{"tests": [...]}`` dict — per the fixture-authenticity convention
    (never a hand-typed YAML string). Computed ONCE at module load so every
    ticket fixture built below shares the byte-identical block.

    Returns:
        The fenced block's inner YAML text (no ``---``/heading wrapper).
    """
    descriptors = [
        {
            "name": f"test_zz_lifecycle_{_SHARED_ANGLE}",
            "file": "unit_tests/zz/test_lifecycle.py",
            "covers": [_SHARED_AC_ID],
            "asserts": _SHARED_BEHAVIOUR,
            "framework": "unittest",
            "type": "integration",
            "angle": _SHARED_ANGLE,
        }
    ]
    return yaml.dump(
        {"tests": descriptors},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()


_TEST_REQUIREMENTS_BLOCK = _build_test_requirements_block()


def _build_ticket_fixture(state_line: str | None) -> str:
    """Build a real ticket fixture, varying ONLY the frontmatter state line.

    Every other line — the ``---`` delimiters, the title, the
    ``## Test Requirements`` heading, and the fenced YAML block itself — is
    byte-identical across every call. This is the mutation-proof property
    REQUIRED TEST PROPERTIES #4 demands: nothing but *state_line* can explain
    a difference in the check's outcome between two fixtures built from this
    same function.

    Args:
        state_line: The raw frontmatter line encoding the ticket's declared
            state (e.g. ``"status: todo"``, ``"status: {unterminated"`` for
            an unparseable value). ``None`` omits the status line entirely
            — the "no status: key at all" shape.

    Returns:
        The full ticket markdown text.
    """
    lines = ["---", "title: zz-bp-1100g-4-ii fixture ticket"]
    if state_line is not None:
        lines.append(state_line)
    lines.append("---")
    lines.append("")
    lines.append("## Test Requirements")
    lines.append("")
    lines.append("```yaml")
    lines.append(_TEST_REQUIREMENTS_BLOCK)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _init_temp_git_project(project_root: Path) -> None:
    """``git init`` a fresh, disposable project root.

    Required so the deployed hook's ``find_project_root()`` (which prefers
    ``git rev-parse --show-toplevel``) resolves to THIS isolated tree rather
    than to the real repository's own root — meaning the scanned claim tree
    is exactly, and only, whatever this test wrote into it.

    Args:
        project_root: Directory to initialise as a git repository.
    """
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(project_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _write_claim_file(directory: Path, filename: str, ac_id: str, angle: str) -> Path:
    """Write a real on-disk test file carrying a ``# covers:`` + ``# angle:`` claim.

    Tags sit directly above the ``def`` line — one of the three positions the
    shared ``collect_test_tag_records`` scanner recognises — so this is
    scanned exactly as a real contributor's test would be.

    Args:
        directory: Directory to write the file into.
        filename: File name to write.
        ac_id: The ``ac_id`` to claim.
        angle: The ``angle`` to claim.

    Returns:
        Path to the written file.
    """
    path = directory / filename
    path.write_text(
        f"# covers: {ac_id}\n"
        f"# angle: {angle}\n"
        "def test_zz_lifecycle_claim():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return path


def _run_check(project_root: Path, ticket_path: Path) -> subprocess.CompletedProcess:
    """Invoke the DEPLOYED hook via ``run_hook.py`` exactly as pre-commit would.

    Args:
        project_root: Working directory for the subprocess — a fresh,
            git-initialised, disposable project root.
        ticket_path: Path to the staged ticket markdown file, passed as the
            hook's ``argv``.

    Returns:
        The completed subprocess result (stdout/stderr/returncode).
    """
    return subprocess.run(
        [sys.executable, str(_DEPLOYED_RUN_HOOK), str(_DEPLOYED_HOOK), str(ticket_path)],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestPlannedWorkWithAnUnclaimedPromiseIsPassedOverAndSaysSo(unittest.TestCase):
    """test_spec: test_planned_work_with_an_unclaimed_promise_is_passed_over_and_says_so
    (angle: criterion). Direct proof of the AC's primary Then-clause."""

    def test_planned_work_with_an_unclaimed_promise_is_passed_over_and_says_so(
        self,
    ) -> None:
        # covers: BP-1100g-4-ii
        # angle: criterion
        """A ticket declaring itself still planned (status: todo), carrying
        an unclaimed promised kind, is NOT refused: the check exits zero and
        states in its output that the work was passed over for being still
        a plan — distinguishable from having been examined and found
        complete."""
        self.assertTrue(
            _DEPLOYED_HOOK.is_file(),
            f"deployed check_proof_promise_claim.py not found at {_DEPLOYED_HOOK}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _init_temp_git_project(project_root)
            ticket_path = project_root / "TICKET-zz-bp1100g4ii-planned.md"
            ticket_path.write_text(
                _build_ticket_fixture("status: todo"), encoding="utf-8"
            )

            result = _run_check(project_root, ticket_path)

        self.assertEqual(
            result.returncode,
            0,
            "planned (status: todo) work with an unclaimed promise must not "
            f"be refused: stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "passed over",
            combined,
            "the outcome must state the work was passed over for being "
            f"still a plan: stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            _SHARED_AC_ID.lower(),
            combined,
            f"the passed-over outcome must name the piece of work by id: {combined!r}",
        )


class TestTheSameWorkOnceStartedIsStillRefusedByName(unittest.TestCase):
    """test_spec: test_the_same_work_once_started_is_still_refused_by_name
    (angle: boundary). Mutation proof against a fix that disables the check
    rather than narrowing it."""

    def test_the_same_work_once_started_is_still_refused_by_name(self) -> None:
        # covers: BP-1100g-4-ii
        # angle: boundary
        """A fixture byte-identical to the planned (status: todo) ticket
        apart from its status value, moved to status: in_progress, is
        refused by name (AC id + unclaimed angle) with a non-zero exit —
        while its byte-identical todo sibling, run as an isolated control,
        IS passed over. Only the status value differs between the two
        fixtures, so only the declared state can explain the difference in
        outcome."""
        todo_fixture = _build_ticket_fixture("status: todo")
        started_fixture = _build_ticket_fixture("status: in_progress")
        self.assertEqual(
            todo_fixture.replace("status: todo", "status: in_progress"),
            started_fixture,
            "the started fixture must be byte-identical to the todo fixture "
            "apart from the status value",
        )

        with tempfile.TemporaryDirectory() as tmp_control:
            control_root = Path(tmp_control)
            _init_temp_git_project(control_root)
            control_ticket = control_root / "TICKET-zz-bp1100g4ii-control-started.md"
            control_ticket.write_text(todo_fixture, encoding="utf-8")
            control_result = _run_check(control_root, control_ticket)

        with tempfile.TemporaryDirectory() as tmp_target:
            target_root = Path(tmp_target)
            _init_temp_git_project(target_root)
            target_ticket = target_root / "TICKET-zz-bp1100g4ii-started.md"
            target_ticket.write_text(started_fixture, encoding="utf-8")
            target_result = _run_check(target_root, target_ticket)

        self.assertEqual(
            control_result.returncode,
            0,
            "the byte-identical todo control sibling must be passed over, "
            f"not refused: stdout={control_result.stdout!r} "
            f"stderr={control_result.stderr!r}",
        )
        self.assertNotEqual(
            target_result.returncode,
            0,
            "work moved from planned to started must still be refused: "
            f"stdout={target_result.stdout!r} stderr={target_result.stderr!r}",
        )
        combined = (target_result.stdout + target_result.stderr).lower()
        self.assertIn(
            _SHARED_AC_ID.lower(),
            combined,
            f"the refusal must name the piece of work by id: {combined!r}",
        )
        self.assertIn(
            _SHARED_ANGLE.lower(),
            combined,
            f"the refusal must name the unclaimed angle: {combined!r}",
        )


class TestTheSameWorkOnceOfferedForHandoffIsStillRefusedByName(unittest.TestCase):
    """test_spec: test_the_same_work_once_offered_for_handoff_is_still_refused_by_name
    (angle: boundary). Establishes that only the still-planned state is
    exempt, never "anything other than started"."""

    def test_the_same_work_once_offered_for_handoff_is_still_refused_by_name(
        self,
    ) -> None:
        # covers: BP-1100g-4-ii
        # angle: boundary
        """A fixture byte-identical to the planned (status: todo) ticket
        apart from its status value, moved to status: done (offered for
        hand-off) with its promise still unclaimed, is refused by name — while
        its byte-identical todo sibling, run as an isolated control, IS
        passed over. Pairs with the started case to rule out a fix that
        exempts every non-finished state instead of only the planned one."""
        todo_fixture = _build_ticket_fixture("status: todo")
        offered_fixture = _build_ticket_fixture("status: done")
        self.assertEqual(
            todo_fixture.replace("status: todo", "status: done"),
            offered_fixture,
            "the offered-for-hand-off fixture must be byte-identical to the "
            "todo fixture apart from the status value",
        )

        with tempfile.TemporaryDirectory() as tmp_control:
            control_root = Path(tmp_control)
            _init_temp_git_project(control_root)
            control_ticket = control_root / "TICKET-zz-bp1100g4ii-control-offered.md"
            control_ticket.write_text(todo_fixture, encoding="utf-8")
            control_result = _run_check(control_root, control_ticket)

        with tempfile.TemporaryDirectory() as tmp_target:
            target_root = Path(tmp_target)
            _init_temp_git_project(target_root)
            target_ticket = target_root / "TICKET-zz-bp1100g4ii-offered.md"
            target_ticket.write_text(offered_fixture, encoding="utf-8")
            target_result = _run_check(target_root, target_ticket)

        self.assertEqual(
            control_result.returncode,
            0,
            "the byte-identical todo control sibling must be passed over, "
            f"not refused: stdout={control_result.stdout!r} "
            f"stderr={control_result.stderr!r}",
        )
        self.assertNotEqual(
            target_result.returncode,
            0,
            "work offered for hand-off (status: done) with its promise "
            f"still unclaimed must still be refused: stdout={target_result.stdout!r} "
            f"stderr={target_result.stderr!r}",
        )
        combined = (target_result.stdout + target_result.stderr).lower()
        self.assertIn(
            _SHARED_AC_ID.lower(),
            combined,
            f"the refusal must name the piece of work by id: {combined!r}",
        )
        self.assertIn(
            _SHARED_ANGLE.lower(),
            combined,
            f"the refusal must name the unclaimed angle: {combined!r}",
        )


class TestWorkWithNoReadableStateIsExaminedNotPassedOver(unittest.TestCase):
    """test_spec: test_work_with_no_readable_state_is_examined_not_passed_over
    (angle: failure). Fail-closed proof: absent or unparseable state must
    never be treated as evidence of being early."""

    def test_work_with_no_readable_state_is_examined_not_passed_over(self) -> None:
        # covers: BP-1100g-4-ii
        # angle: failure
        """Work carrying no status: key at all, and work whose frontmatter
        cannot be parsed as YAML, are each EXAMINED (never passed over) and
        each refused on the unclaimed promise — while the byte-identical
        readable todo control IS passed over, proving the distinction is
        driven by readability of the state, not by some other difference."""
        todo_fixture = _build_ticket_fixture("status: todo")
        no_status_fixture = _build_ticket_fixture(None)
        unparseable_fixture = _build_ticket_fixture("status: {unterminated")

        with tempfile.TemporaryDirectory() as tmp_control:
            control_root = Path(tmp_control)
            _init_temp_git_project(control_root)
            control_ticket = control_root / "TICKET-zz-bp1100g4ii-control-unreadable.md"
            control_ticket.write_text(todo_fixture, encoding="utf-8")
            control_result = _run_check(control_root, control_ticket)

        with tempfile.TemporaryDirectory() as tmp_no_status:
            no_status_root = Path(tmp_no_status)
            _init_temp_git_project(no_status_root)
            no_status_ticket = no_status_root / "TICKET-zz-bp1100g4ii-nostatus.md"
            no_status_ticket.write_text(no_status_fixture, encoding="utf-8")
            no_status_result = _run_check(no_status_root, no_status_ticket)

        with tempfile.TemporaryDirectory() as tmp_unparseable:
            unparseable_root = Path(tmp_unparseable)
            _init_temp_git_project(unparseable_root)
            unparseable_ticket = unparseable_root / "TICKET-zz-bp1100g4ii-unparseable.md"
            unparseable_ticket.write_text(unparseable_fixture, encoding="utf-8")
            unparseable_result = _run_check(unparseable_root, unparseable_ticket)

        self.assertEqual(
            control_result.returncode,
            0,
            "the readable, byte-identical status: todo control must be "
            f"passed over: stdout={control_result.stdout!r} "
            f"stderr={control_result.stderr!r}",
        )

        for label, result in (
            ("no status key", no_status_result),
            ("unparseable frontmatter", unparseable_result),
        ):
            self.assertNotEqual(
                result.returncode,
                0,
                f"work with {label} must be EXAMINED (never passed over) and "
                f"refused on the unclaimed promise: stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            combined = (result.stdout + result.stderr).lower()
            self.assertIn(
                _SHARED_AC_ID.lower(),
                combined,
                f"the {label} case must name the piece of work by id: {combined!r}",
            )
            self.assertIn(
                _SHARED_ANGLE.lower(),
                combined,
                f"the {label} case must name the unclaimed angle: {combined!r}",
            )
            self.assertNotIn(
                "passed over",
                combined,
                "a state that cannot be read must never be treated as "
                f"evidence of being early ({label}): {combined!r}",
            )


class TestHandedOffWorkWhosePromiseIsClaimedIsNotRefused(unittest.TestCase):
    """test_spec: test_handed_off_work_whose_promise_is_claimed_is_not_refused
    (angle: seam). Real producer (a written, tagged test file scanned by the
    real done_proof.collect_test_tag_records) piped into the real check."""

    def test_handed_off_work_whose_promise_is_claimed_is_not_refused(self) -> None:
        # covers: BP-1100g-4-ii
        # angle: seam
        """Work offered for hand-off (status: done) whose promised angle IS
        claimed by a real, tagged, on-disk test exits zero, worded as
        examined and complete — never as passed over. Control: the
        byte-identical todo/unclaimed sibling IS worded as passed over, so
        the two zero-exit outcomes stay textually distinguishable rather
        than collapsing into one silent "fine" result."""
        todo_fixture = _build_ticket_fixture("status: todo")
        done_fixture = _build_ticket_fixture("status: done")

        with tempfile.TemporaryDirectory() as tmp_control:
            control_root = Path(tmp_control)
            _init_temp_git_project(control_root)
            control_ticket = control_root / "TICKET-zz-bp1100g4ii-control-claimed.md"
            control_ticket.write_text(todo_fixture, encoding="utf-8")
            control_result = _run_check(control_root, control_ticket)

        with tempfile.TemporaryDirectory() as tmp_target:
            target_root = Path(tmp_target)
            _init_temp_git_project(target_root)
            target_ticket = target_root / "TICKET-zz-bp1100g4ii-handedoff.md"
            target_ticket.write_text(done_fixture, encoding="utf-8")
            _write_claim_file(
                target_root,
                "test_zz_lifecycle_claim.py",
                _SHARED_AC_ID,
                _SHARED_ANGLE,
            )
            target_result = _run_check(target_root, target_ticket)

        self.assertEqual(
            control_result.returncode,
            0,
            "the byte-identical todo/unclaimed control sibling must be "
            f"passed over: stdout={control_result.stdout!r} "
            f"stderr={control_result.stderr!r}",
        )
        control_combined = (control_result.stdout + control_result.stderr).lower()
        self.assertIn(
            "passed over",
            control_combined,
            f"the control outcome must be worded as passed over: {control_combined!r}",
        )

        self.assertEqual(
            target_result.returncode,
            0,
            "handed-off work whose promised angle is claimed must not be "
            f"refused: stdout={target_result.stdout!r} stderr={target_result.stderr!r}",
        )
        target_combined = (target_result.stdout + target_result.stderr).lower()
        self.assertNotIn(
            "passed over",
            target_combined,
            "a piece of work that was examined and found complete must "
            f"never be described as passed over: {target_combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
