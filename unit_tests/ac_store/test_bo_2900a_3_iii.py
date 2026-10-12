"""
MODULE: unit_tests/ac_store/test_bo_2900a_3_iii.py
COVERS: BO-2900a-3

=== Rework round two (pr-reviewer 2026-09-28 00:57 blocker) ===

    python-coder's fix for the addopts-plugin regression above (see the
    2026-09-28 00:31 DECISION HISTORY entry in
    scripts/ac_store/_done_proof_phase_helpers.py) added
    ``_directory_declares_pytest_rootdir`` / ``_pytest_ini_section_present``,
    walking upward from the test files' common ancestor and accepting the
    first directory that "declares itself a pytest rootdir" -- ``pytest.ini``
    on sight, or ``pyproject.toml``/``tox.ini``/``setup.cfg`` only when they
    carry the specific section pytest itself reads from that file kind. The
    marker table (``_PYTEST_ROOTDIR_TOML_MARKERS``) pairs
    ``("setup.cfg", "[pytest]")`` -- but real pytest reads ``setup.cfg``
    ONLY via a ``[tool:pytest]`` section, never a bare ``[pytest]`` section
    (that spelling is only valid in ``pytest.ini``/``tox.ini``). Since
    ``"[pytest]"`` is not a substring of ``"[tool:pytest]"``, a genuine
    ``setup.cfg``-rooted project is never recognised as a pytest rootdir by
    this check, so ``_resolve_pytest_run_cwd`` walks straight past it and
    falls back to the test files' own common ancestor -- reproducing the
    EXACT SAME failure mode as the original regression (an ``addopts -p
    <plugin>`` entry beside the config file becomes unimportable from that
    fallback cwd).

    Two new tests below, mirroring
    ``_write_project_with_root_plugin_and_nested_test``'s exact fixture
    shape but swapping the config file:

    1. ``test_setup_cfg_addopts_plugin_is_unimportable_because_the_rootdir_marker_checks_the_wrong_section_name``
       -- a genuine ``setup.cfg`` with ``[tool:pytest]`` (the section pytest
       actually reads) is never recognised as a rootdir; RED today.
       Confirmed empirically before writing this test: with this exact
       fixture, ``_resolve_pytest_run_cwd`` returns
       ``<root>/sub/dir`` (the bare common ancestor, not ``<root>`` where
       ``setup.cfg`` lives), and ``done_proof._run_pytest_and_parse`` returns
       ``{}`` -- the real, passing ``test_x`` is never reported PASSED.
    2. ``test_pyproject_toml_addopts_plugin_is_importable_via_the_correctly_paired_rootdir_marker``
       -- a GUARD test (not part of this round's red baseline): the
       ``pyproject.toml`` marker (``"[tool.pytest.ini_options]"``) is paired
       correctly, so this case already works today. Confirmed empirically
       GREEN before writing this test: ``_resolve_pytest_run_cwd`` returns
       ``<root>`` (the ``pyproject.toml`` directory), and
       ``done_proof._run_pytest_and_parse`` returns
       ``{'sub/dir/test_x.py::test_x': 'PASSED'}``. Kept here so a fix for
       the ``setup.cfg`` bug above cannot silently regress this already-
       correct case.

GOAL: Rework-round RED test for the CI regression PR #925 (Linux) surfaced:
    "Proof-of-done coverage check" failed with
    ``WARNING: done_proof: pytest run unfinished: 2 file(s), returncode 4``
    for BO-2900a-1 and BO-2900a-3.

    The root cause is ``_resolve_pytest_run_cwd()``
    (scripts/ac_store/_done_proof_phase_helpers.py), added by this same
    ticket's earlier round to fix a DIFFERENT bug (a fixture rooted under
    the OS temp directory sharing only a distant ancestor with the caller's
    own cwd, causing pytest's rootdir walk to cross unrelated, transiently
    changing directories). That fix anchors the child pytest subprocess's
    ``cwd=`` (in ``done_proof._run_pytest_and_parse``) to *test_files*' own
    common-ancestor directory -- e.g. ``unit_tests/ac_store`` for this
    repo's own real test files.

    This repo's own ``pytest.ini`` carries:
        addopts = --continue-on-collection-errors -p scripts.ac_store.pytest_ac_enforcement
        pythonpath = .
    ``python -m pytest`` inserts the SUBPROCESS's cwd onto ``sys.path``, not
    the ini file's own directory. When the subprocess's cwd is anchored to
    the linked test files' own directory (e.g. ``unit_tests/ac_store``)
    rather than the ini's directory (the repo root), the dotted ``-p``
    plugin argument ``scripts.ac_store.pytest_ac_enforcement`` can no longer
    be imported by that name -- ``scripts`` is not importable as a top-level
    package from that cwd. Confirmed empirically before writing this test
    (see the two manual reproductions below): on this checkout's pytest
    version, the failure to import a plugin named in ``addopts`` surfaces as
    an UNHANDLED exception during pytest's own argument-parsing phase,
    printed to stderr as a raw traceback, before any test result line is
    ever written to stdout -- so ``_parse_pytest_verbose_output`` finds
    nothing to match and returns an EMPTY dict, silently reading as "no
    tests ran" rather than raising or reporting the incomplete-run sentinel.
    On the CI (Linux) pytest version this same failure instead exits with
    return code 4 (usage error), which does trip the
    ``_PYTEST_RUN_INCOMPLETE_SENTINEL`` path (``proc.returncode not in (0,
    1)``) -- a different downstream symptom of the exact same root cause.
    Both are wrong: the linked test genuinely ran and passed, and the
    caller's own answer (whether "no result at all" or "run incomplete")
    must not depend on which pytest version happens to be installed.

    This test avoids depending on either version-specific returncode by
    building an isolated fixture project (own ``pytest.ini``, own root-level
    plugin module, own nested test file) that reproduces the SAME structural
    shape -- an ``addopts -p <plugin>`` naming a plugin that lives beside the
    ini file, not beside the linked test file -- deterministically, on any
    pytest version: whatever numeric returncode that version assigns to a
    plugin-import failure, the practical, user-visible symptom is identical
    -- the real test is never reported PASSED. That is the single, version-
    independent assertion this test makes.

=== Manual reproduction (recorded before writing this test) ===

    Fixture: tmp/pytest.ini with ``addopts = -p rootplugin`` (no
    ``pythonpath`` line), tmp/rootplugin.py (a trivial plugin module), and
    tmp/sub/dir/test_x.py with one passing ``test_x()``.

    - ``cwd=<tmp>/sub/dir`` (today's ``_resolve_pytest_run_cwd`` answer for
      this single-file input -- the file's own parent directory): pytest
      exits with returncode 1 (NOT 4, on this checkout's pytest/Python
      version) after an unhandled ``ModuleNotFoundError: No module named
      'rootplugin'`` during plugin loading -- stdout is empty (no result
      line ever printed), so ``done_proof._run_pytest_and_parse`` returns
      ``{}``. The real ``test_x`` is never reported PASSED.
    - ``cwd=<tmp>`` (the ini's own directory): pytest exits 0, stdout
      contains ``sub/dir/test_x.py::test_x PASSED``, and
      ``done_proof._run_pytest_and_parse`` returns
      ``{'sub/dir/test_x.py::test_x': 'PASSED'}``.

    This confirms the regression is real, is caused by the cwd anchor
    exactly as the ticket describes, and is independent of the specific
    returncode pytest happens to assign to a plugin-import failure.

=== Red baseline (this round) ===

    ``test_addopts_plugin_beside_the_ini_is_unimportable_when_cwd_is_anchored_to_the_test_files_own_directory``
    is RED today: ``done_proof._run_pytest_and_parse`` returns a dict with
    no PASSED entry for the fixture's own passing test (today: ``{}``,
    empty, because stdout was never populated) instead of reporting it
    PASSED, and no ``_PYTEST_RUN_INCOMPLETE_SENTINEL`` entry either -- the
    run simply produces no usable signal at all.

    ``test_project_with_no_ini_ancestor_in_the_fixture_still_runs_and_passes``
    is a GUARD test, not part of this round's red baseline: it protects the
    ORIGINAL motivation ``_resolve_pytest_run_cwd`` was added for (a fixture
    with no ini ancestor of its own, rooted deep under the OS temp
    directory, must still run and pass without the subprocess's rootdir
    walk crossing into unrelated directories). Confirmed GREEN today by
    manual reproduction before writing this test -- kept here so a fix for
    the RED test above cannot silently regress this original case.

    Shared fixture helpers are NOT reused from ``_bo_2900a_1_fixtures.py``
    here (unlike this file's siblings): that module's helpers build AC-store
    + covers-tag fixtures for ``verify_done_eligible``, a layer above the
    one this file targets. This file calls
    ``done_proof._run_pytest_and_parse`` directly, one level below that
    seam, so its fixtures are a plain pytest.ini + plugin module + test file
    on disk -- no AC YAML, no covers tags, no git init required.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "ac_store"))

import done_proof  # noqa: E402


def _write_project_with_root_plugin_and_nested_test(root: Path) -> Path:
    """Build a fixture project whose ``pytest.ini`` names a plugin that
    lives BESIDE the ini file, while the only linked test file lives several
    directories below it -- the same structural shape as this repo's own
    ``pytest.ini`` (``-p scripts.ac_store.pytest_ac_enforcement``) versus a
    linked test under ``unit_tests/ac_store/``.

    No ``pythonpath = .`` line is written: this is deliberate -- the whole
    point of the fixture is that the plugin is importable ONLY when the
    pytest subprocess's cwd is the ini's own directory (which puts that
    directory on ``sys.path`` via ``python -m pytest``'s own cwd-insertion
    behaviour), not when the subprocess's cwd is anchored to the nested test
    file's own directory.

    Returns the nested test file's path.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text(
        "[pytest]\naddopts = -p rootplugin\n", encoding="utf-8"
    )
    (root / "rootplugin.py").write_text(
        '"""Trivial pytest plugin used only as an import probe -- it defines '
        'no hooks; its only job is to exist beside pytest.ini so a '
        '``-p rootplugin`` addopts entry can (or cannot) find it depending '
        'on the subprocess cwd."""\n',
        encoding="utf-8",
    )
    sub = root / "sub" / "dir"
    sub.mkdir(parents=True, exist_ok=True)
    test_file = sub / "test_x.py"
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    return test_file


def _write_project_with_setup_cfg_and_nested_test(root: Path) -> Path:
    """Same fixture shape as
    :func:`_write_project_with_root_plugin_and_nested_test`, but the config
    file is ``setup.cfg`` with a genuine ``[tool:pytest]`` section -- the
    ONLY section name real pytest reads from ``setup.cfg`` (a bare
    ``[pytest]`` section, valid in ``pytest.ini``/``tox.ini``, is never
    recognised by pytest itself when it appears in ``setup.cfg``).

    Returns the nested test file's path.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "setup.cfg").write_text(
        "[tool:pytest]\naddopts = -p rootplugin\n", encoding="utf-8"
    )
    (root / "rootplugin.py").write_text(
        '"""Trivial pytest plugin used only as an import probe."""\n',
        encoding="utf-8",
    )
    sub = root / "sub" / "dir"
    sub.mkdir(parents=True, exist_ok=True)
    test_file = sub / "test_x.py"
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    return test_file


def _write_project_with_pyproject_toml_and_nested_test(root: Path) -> Path:
    """Same fixture shape as
    :func:`_write_project_with_root_plugin_and_nested_test`, but the config
    file is ``pyproject.toml`` with a genuine ``[tool.pytest.ini_options]``
    section -- the section real pytest reads addopts from in that file kind.

    Returns the nested test file's path.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-p rootplugin"\n',
        encoding="utf-8",
    )
    (root / "rootplugin.py").write_text(
        '"""Trivial pytest plugin used only as an import probe."""\n',
        encoding="utf-8",
    )
    sub = root / "sub" / "dir"
    sub.mkdir(parents=True, exist_ok=True)
    test_file = sub / "test_x.py"
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    return test_file


class TestPytestRunCwdAnchorBreaksARootLevelAddoptsPlugin(unittest.TestCase):
    """CI regression (PR #925, Linux): anchoring the pytest subprocess's cwd
    to the linked test files' own directory (``_resolve_pytest_run_cwd``)
    makes an ``addopts -p <plugin>`` entry naming a plugin that lives beside
    ``pytest.ini`` -- not beside the test file -- unimportable, so a
    genuinely passing test is never reported PASSED."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_addopts_plugin_beside_the_ini_is_unimportable_when_cwd_is_anchored_to_the_test_files_own_directory(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: discrimination
        test_file = _write_project_with_root_plugin_and_nested_test(self.root)

        result = done_proof._run_pytest_and_parse([test_file])

        self.assertNotIn(
            done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL,
            result,
            f"expected the real pytest subprocess to run to completion (not "
            f"time out / be killed), got an incomplete-run sentinel: {result}",
        )
        passed_entries = {
            nodeid: outcome
            for nodeid, outcome in result.items()
            if nodeid.endswith("test_x.py::test_x")
        }
        self.assertTrue(
            passed_entries and all(o == "PASSED" for o in passed_entries.values()),
            f"expected test_x (a genuinely passing test) to be reported "
            f"PASSED even though pytest.ini's 'addopts -p rootplugin' names "
            f"a plugin module that lives beside pytest.ini, not beside the "
            f"test file itself -- the pytest subprocess's cwd must be "
            f"anchored so that plugin remains importable, got: {result}",
        )


class TestPytestRunCwdAnchorMissesAGenuineSetupCfgRootdir(unittest.TestCase):
    """pr-reviewer (2026-09-28 00:57 blocker):
    ``_PYTEST_ROOTDIR_TOML_MARKERS`` pairs ``("setup.cfg", "[pytest]")``, but
    real pytest reads ``setup.cfg`` only via a ``[tool:pytest]`` section --
    never a bare ``[pytest]`` section (that spelling is only valid in
    ``pytest.ini``/``tox.ini``). A genuine ``setup.cfg``-rooted project is
    therefore never recognised as a pytest rootdir by
    ``_directory_declares_pytest_rootdir``, so ``_resolve_pytest_run_cwd``
    walks past it and falls back to the test files' own common ancestor --
    reproducing the exact same addopts-plugin-unimportable failure as the
    original CI regression."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_setup_cfg_addopts_plugin_is_unimportable_because_the_rootdir_marker_checks_the_wrong_section_name(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: discrimination
        test_file = _write_project_with_setup_cfg_and_nested_test(self.root)

        result = done_proof._run_pytest_and_parse([test_file])

        self.assertNotIn(
            done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL,
            result,
            f"expected the real pytest subprocess to run to completion (not "
            f"time out / be killed), got an incomplete-run sentinel: {result}",
        )
        passed_entries = {
            nodeid: outcome
            for nodeid, outcome in result.items()
            if nodeid.endswith("test_x.py::test_x")
        }
        self.assertTrue(
            passed_entries and all(o == "PASSED" for o in passed_entries.values()),
            f"expected test_x (a genuinely passing test) to be reported "
            f"PASSED even though setup.cfg's genuine '[tool:pytest]' "
            f"section names an 'addopts -p rootplugin' plugin that lives "
            f"beside setup.cfg, not beside the test file itself -- "
            f"_directory_declares_pytest_rootdir must recognise setup.cfg's "
            f"'[tool:pytest]' section (the one real pytest reads from that "
            f"file kind), not a bare '[pytest]' section, got: {result}",
        )


class TestPytestRunCwdAnchorRecognisesAPyprojectTomlRootdir(unittest.TestCase):
    """Guard test (not part of this round's red baseline): the
    ``pyproject.toml`` marker (``"[tool.pytest.ini_options]"``) IS paired
    correctly in ``_PYTEST_ROOTDIR_TOML_MARKERS``, so a genuine
    ``pyproject.toml``-rooted project is already recognised as a pytest
    rootdir today. Kept here so a fix for the ``setup.cfg`` bug above cannot
    silently regress this already-correct case."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pyproject_toml_addopts_plugin_is_importable_via_the_correctly_paired_rootdir_marker(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        test_file = _write_project_with_pyproject_toml_and_nested_test(self.root)

        result = done_proof._run_pytest_and_parse([test_file])

        self.assertNotIn(
            done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL,
            result,
            f"expected the real pytest subprocess to run to completion (not "
            f"time out / be killed), got an incomplete-run sentinel: {result}",
        )
        passed_entries = {
            nodeid: outcome
            for nodeid, outcome in result.items()
            if nodeid.endswith("test_x.py::test_x")
        }
        self.assertTrue(
            passed_entries and all(o == "PASSED" for o in passed_entries.values()),
            f"expected test_x to be reported PASSED when pyproject.toml's "
            f"genuine '[tool.pytest.ini_options]' section names an "
            f"'addopts -p rootplugin' plugin that lives beside "
            f"pyproject.toml, got: {result}",
        )


class TestPytestRunCwdAnchorStillHandlesAFixtureWithNoIniAncestor(unittest.TestCase):
    """Guard test (not part of this round's red baseline): protects the
    ORIGINAL motivation ``_resolve_pytest_run_cwd`` was added for -- a
    fixture rooted under the OS temp directory with no ``pytest.ini``
    ancestor of its own must still run its linked test and report it
    PASSED, without the subprocess's rootdir walk crossing into unrelated,
    transiently changing directories on the way up from an unset cwd."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_project_with_no_ini_ancestor_in_the_fixture_still_runs_and_passes(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        sub = self.root / "sub"
        sub.mkdir(parents=True, exist_ok=True)
        test_file = sub / "test_y.py"
        test_file.write_text("def test_y():\n    assert True\n", encoding="utf-8")

        result = done_proof._run_pytest_and_parse([test_file])

        self.assertNotIn(
            done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL,
            result,
            f"expected a plain fixture with no pytest.ini ancestor of its "
            f"own to run to completion, got an incomplete-run sentinel: "
            f"{result}",
        )
        passed_entries = {
            nodeid: outcome
            for nodeid, outcome in result.items()
            if nodeid.endswith("test_y.py::test_y")
        }
        self.assertTrue(
            passed_entries and all(o == "PASSED" for o in passed_entries.values()),
            f"expected test_y to be reported PASSED for a fixture with no "
            f"ini ancestor of its own, got: {result}",
        )


if __name__ == "__main__":
    unittest.main()
