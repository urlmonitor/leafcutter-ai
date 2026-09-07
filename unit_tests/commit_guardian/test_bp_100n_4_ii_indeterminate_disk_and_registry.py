"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_ii_indeterminate_disk_and_registry.py
COVERS: BP-100n-4-ii

GOAL: the four INDETERMINATE fail-closed situations BP-100n-4-ii's two new
    populations (the disk-side gate-script listing and the registry read)
    must each be named by their own specific reason and must fail — never
    silently fall through to a clean, zero-invoked-by-nothing verdict. Split
    out of test_bp_100n_4_ii.py purely to keep that NEW file under
    check-file-size's absolute 400-counted-line cap for new files — see that
    module's own "SPLIT NOTE" paragraph for the full rationale and where its
    other test_spec descriptors landed.

DEPENDENCY NOTE — imports, never copy-pastes, from the sibling: this module
    reuses the low-level git/registry/subprocess fixtures that already live
    in test_bp_100n_4_ii.py (``_init_repo``, ``_commit_all``,
    ``_deploy_gate_dir_copy``, ``_run_reachability_hook``,
    ``_write_gate_script``, ``_FixtureRepoTestCase``, ``_RESULT_LINE_RE``,
    ``_INDETERMINATE_LINE_RE``, ``_REACHABILITY_HOOK_NAME``). Per this
    repo's Source-of-Truth Discipline (a duplicated helper is how two
    sibling files drift apart later), those are loaded via ``importlib``
    under a private module name — mirroring this exact directory's own
    established convention for reusing another test file's internals
    read-only (see test_bp_100k_4_ii_registry_shapes.py and
    test_bp_100k_5_i.py / test_bp_100k_5.py's identical use of the same
    pattern) — rather than copy-pasted, so the two files cannot silently
    drift on what the fixture repo, the real gate-directory copy, or a
    reachability-hook invocation looks like.

RED BASELINE (expected): every test below is RED for the same reason
    test_bp_100n_4_ii.py's are — no disk-side INDETERMINATE branch exists
    yet, and HOOK_TEST_GATE_DIR is not yet resolved.

    Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep":
    every indeterminate scenario below is exercised by making the underlying
    lookup GENUINELY unavailable at run time (permission bits removed via
    os.chmod, a nonexistent path, a corrupt file written to disk) — never by
    reading the guard's source for an error branch.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BASE_MODULE_PATH = _THIS_DIR / "test_bp_100n_4_ii.py"


def _load_base_module():
    """Load test_bp_100n_4_ii.py under a private module name via importlib.

    Read-only reuse of that module's git/registry/subprocess fixtures.
    Loading it this way (rather than a package-qualified ``import``) mirrors
    this same directory's own established convention and never collides
    with pytest's own normal collection of test_bp_100n_4_ii.py as its own
    test module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100n4ii_base_indeterminate", _BASE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_module()


# ---------------------------------------------------------------------------
# test_spec 2: an unlistable gate-script directory is named and fails.
# ---------------------------------------------------------------------------


class TestUnlistableGateScriptDirectoryIsNamedAndFails(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _base._init_repo(self.workspace)
        self.gate_dir = _base._deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _base._REACHABILITY_HOOK_NAME
        _base._commit_all(self.workspace, "initial fixture copy")
        self.locked_dir = self.workspace / "locked_gate_dir"
        self.locked_dir.mkdir()
        _base._write_gate_script(self.locked_dir / "check_locked_fixture.py")

    def tearDown(self) -> None:
        os.chmod(str(self.locked_dir), stat.S_IRWXU)
        self._tmp.cleanup()

    def test_bp_100n_4_ii_an_unlistable_gate_script_directory_is_named_as_such_and_fails(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: failure
        """With the gate-script directory made GENUINELY unavailable at run
        time (execute-only permission bits — no read/listing), the check
        states that it could not establish which gate scripts exist, names
        this as the unlistable situation, and exits non-zero.
        """
        os.chmod(str(self.locked_dir), stat.S_IXUSR)
        result = _base._run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={"HOOK_TEST_GATE_DIR": str(self.locked_dir)},
        )
        output = result.stdout + result.stderr
        match = _base._INDETERMINATE_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            "expected an INDETERMINATE: reason=... line for an unlistable "
            f"gate-script directory; got {output!r}",
        )
        self.assertIn(
            "unlistable",
            match.group(1).lower(),
            f"the reason must name the unlistable situation specifically; got {output!r}",
        )
        self.assertNotEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# test_spec 3: a listable-but-empty gate-script directory is the OTHER
# named situation.
# ---------------------------------------------------------------------------


class TestEmptyGateScriptDirectoryIsTheOtherNamedSituation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _base._init_repo(self.workspace)
        self.gate_dir = _base._deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _base._REACHABILITY_HOOK_NAME
        self.empty_dir = self.workspace / "empty_gate_dir"
        self.empty_dir.mkdir()
        _base._commit_all(self.workspace, "initial fixture copy plus empty dir")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bp_100n_4_ii_a_listable_but_empty_gate_script_directory_is_the_other_named_situation(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: boundary
        """A gate-script directory that lists successfully and holds no
        gate scripts at all is a DIFFERENT, separately named situation from
        the unlistable one, and also fails.
        """
        result = _base._run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={"HOOK_TEST_GATE_DIR": str(self.empty_dir)},
        )
        output = result.stdout + result.stderr
        match = _base._INDETERMINATE_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            f"expected an INDETERMINATE: reason=... line for an empty directory; got {output!r}",
        )
        reason = match.group(1).lower()
        self.assertNotIn(
            "unlistable",
            reason,
            "a successfully-empty listing must be named DIFFERENTLY from an "
            f"unlistable one; got {output!r}",
        )
        self.assertTrue(
            "empty" in reason or "no gate scripts" in reason,
            f"expected the empty-directory situation to be named as such; got {output!r}",
        )
        self.assertNotEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# test_spec 4: an unreadable or unparseable registry names its reason.
# ---------------------------------------------------------------------------


class TestUnreadableOrUnparseableRegistryNamesItsReason(_base._FixtureRepoTestCase):
    def test_bp_100n_4_ii_an_unreadable_or_unparseable_registry_names_its_reason_and_fails(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: failure
        """With the registry made genuinely unreadable, and separately made
        present-but-unparseable, the check states it could not establish
        which scripts are invoked, names which reason applies, and exits
        non-zero. The corrupt case must not fall through to a different,
        clean registry copy.
        """
        missing_config = str(self.workspace / "does_not_exist.json")
        unreadable_result = _base._run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={"HOOK_TEST_CONFIG": missing_config},
        )
        unreadable_output = unreadable_result.stdout + unreadable_result.stderr
        unreadable_match = _base._INDETERMINATE_LINE_RE.search(unreadable_output)
        self.assertIsNotNone(
            unreadable_match,
            f"expected INDETERMINATE for an unreadable registry; got {unreadable_output!r}",
        )
        self.assertNotEqual(unreadable_result.returncode, 0)

        corrupt_config_path = self.workspace / "corrupt_registry.json"
        corrupt_config_path.write_text("{not valid json", encoding="utf-8")
        corrupt_result = _base._run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={"HOOK_TEST_CONFIG": str(corrupt_config_path)},
        )
        corrupt_output = corrupt_result.stdout + corrupt_result.stderr
        corrupt_match = _base._INDETERMINATE_LINE_RE.search(corrupt_output)
        self.assertIsNotNone(
            corrupt_match,
            f"expected INDETERMINATE for an unparseable registry; got {corrupt_output!r}",
        )
        self.assertNotEqual(corrupt_result.returncode, 0)
        self.assertNotEqual(
            unreadable_match.group(1),
            corrupt_match.group(1),
            "an absent registry and a present-but-corrupt one are different "
            "facts and must be named with different reasons",
        )


# ---------------------------------------------------------------------------
# test_spec 5: neither indeterminate situation emits a zero-invoked-by-
# nothing clean verdict.
# ---------------------------------------------------------------------------


class TestIndeterminateNeverEmitsCleanVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _base._init_repo(self.workspace)
        self.gate_dir = _base._deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _base._REACHABILITY_HOOK_NAME
        _base._commit_all(self.workspace, "initial fixture copy")
        self.locked_dir = self.workspace / "locked_gate_dir"
        self.locked_dir.mkdir()
        _base._write_gate_script(self.locked_dir / "check_locked_fixture.py")

    def tearDown(self) -> None:
        os.chmod(str(self.locked_dir), stat.S_IRWXU)
        self._tmp.cleanup()

    def test_bp_100n_4_ii_neither_indeterminate_situation_emits_a_zero_invoked_by_nothing_clean_verdict(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: failure
        """With the disk listing made genuinely unavailable, the run must
        never state unreferenced=0 nor exit as though every script had been
        found invoked. This is asserted directly against the fail-closed
        requirement, exercised by a real, unlistable directory — never by a
        source-level mutation toggle.
        """
        os.chmod(str(self.locked_dir), stat.S_IXUSR)
        result = _base._run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={"HOOK_TEST_GATE_DIR": str(self.locked_dir)},
        )
        output = result.stdout + result.stderr
        # First establish that the disk listing was actually made
        # unavailable and consulted (HOOK_TEST_GATE_DIR resolved and
        # reported INDETERMINATE) — without this, an implementation that
        # ignores the override entirely would still coincidentally satisfy
        # the two assertions below via unrelated trigger-reachability
        # findings, exactly the "green on arrival" trap this AC's own
        # rationale warns against.
        match = _base._INDETERMINATE_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            "expected the disk listing to be made genuinely unavailable and "
            f"reported INDETERMINATE; got {output!r}",
        )
        self.assertNotRegex(
            output,
            r"\bunreferenced=0\b",
            "an indeterminate disk listing must never be reported as zero "
            f"scripts invoked by nothing; got {output!r}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "an indeterminate disk listing must never exit as though the "
            "comparison had been performed and found everything invoked",
        )


if __name__ == "__main__":
    unittest.main()
