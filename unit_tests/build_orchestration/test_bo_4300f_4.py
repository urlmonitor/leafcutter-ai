"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_4.py
AC: BO-4300f-4 -- "The proof runs the copy of the maker that a project
    actually receives" (L2).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    02_TICKET-20260928-BO-4300-deployed-maker-test-support.md

WHAT THIS PROVES
====================================================================
The shared test-support locator in unit_tests/build_orchestration/
_workspace_maker_fixtures.py resolves the DEPLOYED workspace maker (never
a tracked source copy under scripts/ or templates/scripts/) and every
later BO-4300 maker proof runs THAT copy, as a real separate process, from
every BO-4300b-1 starting point. Four tests:

- test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour_MANUAL
  (angle: deployed) -- copy the real deployed maker, inject a fault ONLY
  into the copy (source left correct), run a proof subset against the
  faulted copy via the override seam, and require it fails naming the
  broken behaviour.
- test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL
  (angle: seam) -- pipes the REAL producer (starting_points' six real
  cwds) into the REAL consumer (a separate `python <maker>` subprocess per
  cwd) and asserts every one resolves the same real answer.
- test_locator_fails_when_deployed_copy_is_absent (angle: failure) --
  pointing the locator at a layout without the maker raises, never skips.
- test_locator_never_resolves_a_tracked_source_copy (angle: boundary) --
  pointing the locator's override seam at the package repository's
  scripts/ or templates/scripts/ copy raises, naming that path.

CONTRACT ASSUMPTIONS this file is written against (python-coder's job to
satisfy; see the Source-of-Truth Discipline in this file's own governing
skill before narrowing any of these):
- ensure_deployed_layout() -> Path: builds the shared deployed layout
  EXACTLY ONCE per interpreter session (module-level cache; a real
  `scripts/build.py --target-dir <tmp>` spawn, justified by this ticket's
  own Implementation Notes -- the same "one new spawn site" precedent
  `_bo_4300a_1_fixtures.DeployedMakerBuild` already established), and
  returns the layout root.
- deployed_maker_path(override=None) -> Path: with no argument, resolves
  the maker from ensure_deployed_layout()'s cached build and raises
  DeployedMakerNotFoundError (never returns None, never skips) when
  absent. With `override` given, validates it is NOT under this package
  repository's scripts/ or templates/scripts/ (raises
  TrackedSourceCopyError, naming the path, if it is), then returns it
  unchanged if it names a real file, else raises
  DeployedMakerNotFoundError.
- make_project(tmp, layout='dev'|'consumer') -> {'project': ..., 'hub':
  ..., 'landing_place': ...}.
- run_maker(args, cwd, maker_path=None, env=None, timeout=60) -> {answer:
  dict, exit_code: int, stdout: str, stderr: str}; maker_path defaults to
  deployed_maker_path() and is the override seam's ONLY other consumption
  point (the Delivers-To summary's terse `run_maker(args, cwd, env=None,
  timeout=...)` omits this kwarg because it is meta-test-only -- see this
  ticket's own Implementation Notes, "Override seam used only by the
  meta-test").
- starting_points(project) -> dict[str, Path] naming exactly the six
  BO-4300b-1 cwds.

DEPENDS ON (not yet built -- expected RED state):
- unit_tests/build_orchestration/_workspace_maker_fixtures.py (this ticket)

DECISION HISTORY
====================================================================
- 2026-09-28 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
  BO-4300f-4]: Initial red test stubs written against the locator/fixture
  contract this ticket's own Implementation Notes, "Delivers To" contract
  text, and BO-4300f-4's AC store test_spec all specify.
  ModuleNotFoundError is the expected RED state until python-coder builds
  _workspace_maker_fixtures.py.
====================================================================
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    DeployedMakerNotFoundError,
    TrackedSourceCopyError,
    deployed_maker_path,
    ensure_deployed_layout,
    make_project,
    run_maker,
    starting_points,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestFaultOnlyInDeployedCopyFailsSuite(unittest.TestCase):
    """angle: deployed -- meta-test: inject a fault ONLY into a copy of
    the deployed maker (source left correct), run a proof subset against
    the faulted copy via the override seam, and require it fails naming
    the broken behaviour."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.layout_root = ensure_deployed_layout()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300f4-fault-")
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_fault_only_in_deployed_copy_fails_the_suite_naming_the_behaviour_MANUAL(self):
        # covers: BO-4300f-4
        # angle: deployed
        """MUST BE IMPLEMENTED: deployed_maker_path() resolves the real
        deployed maker; copy it to a scratch dir (source untouched),
        corrupt exactly one documented behaviour -- `ensure` must answer
        `"status": "ok"`; the fault flips that sentinel string to
        `"status": "broken"` -- point the override seam at the faulted
        COPY (never the source), run `ensure` against a real fixture
        project via run_maker(maker_path=faulted_copy), and require the
        proof subset fails, naming the broken `status` behaviour."""
        source_maker = deployed_maker_path()
        self.assertTrue(source_maker.is_file(), msg=f"deployed maker missing at {source_maker}")
        source_text = source_maker.read_text(encoding="utf-8")

        faulted_dir = self.tmp_path / "faulted-copy"
        faulted_dir.mkdir()
        faulted_copy = faulted_dir / source_maker.name
        faulted_text = source_text.replace('"status": "ok"', '"status": "broken"')
        self.assertNotEqual(
            source_text, faulted_text,
            msg=(
                "fault injection did not change anything -- update this test's "
                "sentinel string once the real deployed maker's status literal is known"
            ),
        )
        faulted_copy.write_text(faulted_text, encoding="utf-8")

        # Source is provably untouched by the fault injection above.
        self.assertEqual(source_maker.read_text(encoding="utf-8"), source_text)

        made = make_project(self.tmp_path, layout="dev")
        project = Path(made["project"])

        resolved_faulted = deployed_maker_path(override=faulted_copy)
        self.assertEqual(resolved_faulted, faulted_copy)

        result = run_maker(
            ["ensure", "--kind", "scratch", "--slug", "fault-probe"],
            cwd=project,
            maker_path=faulted_copy,
        )
        self.assertNotEqual(
            result["answer"].get("status"), "ok",
            msg=f"faulted copy did not fail the probed behaviour: {result}",
        )


class TestSuiteRunsDeployedMakerFromEveryStartingPoint(unittest.TestCase):
    """angle: seam -- pipes the REAL producer (starting_points' six real
    cwds) into the REAL consumer (the deployed maker spawned as a separate
    process) and asserts the consumer's observable behaviour: the resolved
    maker path is under the install layout (never templates/), and every
    starting point's real subprocess run answers the same real location."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.layout_root = ensure_deployed_layout()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300f4-seam-")
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_suite_runs_deployed_maker_as_separate_process_from_every_starting_point_MANUAL(self):
        # covers: BO-4300f-4
        # angle: seam
        """MUST BE IMPLEMENTED: deployed_maker_path() resolves to a path
        under the install layout, never under templates/; starting_points
        (project) names all six BO-4300b-1 cwds (project's top folder,
        three levels down inside it, the parent folder above it, a sibling
        folder beside it, inside W1, and inside the new workspace itself);
        a genuinely separate `python <maker>` subprocess spawned from each
        cwd against the real project answers the SAME resolved location."""
        maker_path = deployed_maker_path()
        self.assertNotIn(
            "templates", maker_path.parts,
            msg=f"locator resolved a templates/ path, not the install copy: {maker_path}",
        )

        made = make_project(self.tmp_path, layout="dev")
        project = Path(made["project"])

        w1 = run_maker(["ensure", "--kind", "scratch", "--slug", "alpha"], cwd=project)
        self.assertEqual(w1["answer"].get("status"), "ok", msg=f"W1 ensure failed: {w1}")

        points = starting_points(project)
        six_names = {
            "project_top", "three_levels_down", "parent_above",
            "sibling_beside", "inside_w1", "inside_new_workspace",
        }
        self.assertTrue(
            six_names.issubset(points.keys()),
            msg=f"starting_points is missing expected keys: {sorted(points.keys())}",
        )
        self.assertEqual(len(points), 6, msg=f"expected exactly six starting points: {points}")

        locations: set[str] = set()
        for name, cwd in points.items():
            with self.subTest(starting_point=name):
                result = subprocess.run(
                    [sys.executable, str(maker_path), "ensure", "--kind", "scratch", "--slug", "beta"],
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 0, msg=f"{name}: {result.stdout} {result.stderr}")
                answer = json.loads(result.stdout.strip().splitlines()[-1])
                self.assertEqual(answer.get("status"), "ok", msg=f"{name}: {answer}")
                locations.add(answer.get("workspace_path") or answer.get("worktree_path"))

        self.assertEqual(
            len(locations), 1,
            msg=f"every starting point must resolve the SAME beta location: {locations}",
        )


class TestLocatorFailsWhenDeployedCopyAbsent(unittest.TestCase):
    """angle: failure -- pointing the locator at a layout without the
    maker raises a failure, never a skip."""

    def test_locator_fails_when_deployed_copy_is_absent(self):
        # covers: BO-4300f-4
        # angle: failure
        """MUST BE IMPLEMENTED: deployed_maker_path(override=<path to a
        real, empty install-shaped layout with no maker file>) raises
        DeployedMakerNotFoundError -- never returns None, never raises
        unittest.SkipTest, never silently falls back to templates/."""
        with tempfile.TemporaryDirectory(prefix="bo4300f4-empty-layout-") as tmp:
            empty_layout = Path(tmp) / ".leafcutter" / "scripts"
            empty_layout.mkdir(parents=True)
            missing_maker = empty_layout / "worktree.py"

            with self.assertRaises(DeployedMakerNotFoundError):
                deployed_maker_path(override=missing_maker)


class TestLocatorNeverResolvesTrackedSourceCopy(unittest.TestCase):
    """angle: boundary -- the install-vs-tracked-source edge: pointing the
    locator's override seam at the package repository's scripts/ or
    templates/scripts/ copy raises, naming that path; only an
    install-layout path is ever accepted."""

    def test_locator_never_resolves_a_tracked_source_copy(self):
        # covers: BO-4300f-4
        # angle: boundary
        """MUST BE IMPLEMENTED: TrackedSourceCopyError, naming the path,
        for BOTH real tracked locations this repository actually carries
        today -- scripts/build.py (a long-standing
        tracked script under scripts/) and templates/scripts/worktree.py (the maker's own
        tracked source, built under BO-4300a-1) -- exercised through the
        override seam, since that is the only caller-facing way to force
        the locator's search at an arbitrary path in a unit test."""
        tracked_scripts_copy = REPO_ROOT / "scripts" / "build.py"
        tracked_templates_copy = REPO_ROOT / "templates" / "scripts" / "worktree.py"
        self.assertTrue(tracked_scripts_copy.is_file(), msg=f"fixture assumption broken: {tracked_scripts_copy}")
        self.assertTrue(tracked_templates_copy.is_file(), msg=f"fixture assumption broken: {tracked_templates_copy}")

        for tracked_path in (tracked_scripts_copy, tracked_templates_copy):
            with self.subTest(tracked_path=str(tracked_path)):
                with self.assertRaises(TrackedSourceCopyError) as ctx:
                    deployed_maker_path(override=tracked_path)
                self.assertIn(
                    str(tracked_path), str(ctx.exception),
                    msg=f"error does not name the rejected tracked path: {ctx.exception}",
                )


# ---------------------------------------------------------------------------
# EPIC-WorkspaceMakerHardening/03 (M15, M14): the harness itself is the unit.
# ---------------------------------------------------------------------------
import os  # noqa: E402
import re  # noqa: E402
from unittest import mock  # noqa: E402

import yaml  # noqa: E402

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout  # noqa: E402
from unit_tests.build_orchestration import _bo_4300f_2_fixtures as census_fx  # noqa: E402
from unit_tests.build_orchestration import _workspace_maker_fixtures as maker_fx  # noqa: E402

_PROBE_MAKER = """\
import json, os, sys
try:
    stdin_data = sys.stdin.read()
    stdin_state = "eof" if stdin_data == "" else "data"
except (OSError, ValueError):
    stdin_state = "closed"
keys = ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "GIT_CEILING_DIRECTORIES", "HOME", "USERPROFILE", "PROBE_CALLER")
print(json.dumps({"stdin": stdin_state, "env": {k: os.environ.get(k) for k in keys}}))
"""


class TestDeployedLayoutIsTheSharedLayout(unittest.TestCase):
    """M15 / BO-4300c-2: no mkdtemp build.py spawn; the shared layout is THE layout."""

    def test_deployed_layout_is_the_shared_layout_and_spawns_no_build(self):
        # covers: BO-4300f-4
        # covers: BO-4300c-2
        # angle: criterion
        """MUST BE IMPLEMENTED: ensure_deployed_layout() returns exactly
        get_or_produce_shared_layout(); deployed_maker_path() lies under it;
        neither the first nor a second resolution spawns scripts/build.py."""
        shared = Path(get_or_produce_shared_layout()).resolve()
        saved = getattr(maker_fx, "_deployed_layout_cache", None)
        self.addCleanup(setattr, maker_fx, "_deployed_layout_cache", saved)
        maker_fx._deployed_layout_cache = None

        spawned: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            spawned.append([str(c) for c in cmd])
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            first = maker_fx.ensure_deployed_layout()
            second = maker_fx.ensure_deployed_layout()

        builds = [c for c in spawned if any(part.endswith("build.py") for part in c)]
        self.assertEqual([], builds, msg=f"ensure_deployed_layout spawned build.py: {builds}")
        self.assertEqual(shared, Path(first).resolve())
        self.assertEqual(Path(first).resolve(), Path(second).resolve())
        maker = maker_fx.deployed_maker_path().resolve()
        self.assertIn(shared, maker.parents, msg=f"maker {maker} is not under the shared layout {shared}")


class TestRunMakerBoundedEnvironment(unittest.TestCase):
    """M15 / BO-4300c-2 + f-4-i: the maker runs with closed stdin and an isolated git config."""

    def test_run_maker_closes_stdin_and_isolates_git_config(self):
        # covers: BO-4300c-2
        # covers: BO-4300f-4-i
        # angle: criterion
        """MUST BE IMPLEMENTED: run_maker passes stdin=DEVNULL and an env built
        from _isolated_git_env() plus GIT_CEILING_DIRECTORIES, caller env on top."""
        with tempfile.TemporaryDirectory(prefix="bo4300f4-probe-") as d:
            root = Path(d)
            probe = root / "probe_maker.py"
            probe.write_text(_PROBE_MAKER, encoding="utf-8")
            cwd = root / "fixture" / "project"
            cwd.mkdir(parents=True)
            real_global = str(root / "REAL-USER-gitconfig")
            real_home = str(root / "REAL-USER-home")
            with mock.patch.dict(
                os.environ,
                {"GIT_CONFIG_GLOBAL": real_global, "HOME": real_home, "USERPROFILE": real_home},
            ):
                result = maker_fx.run_maker(
                    ["x"], cwd=cwd, maker_path=probe, env={"PROBE_CALLER": "kept"}, timeout=20,
                )
            env = result["answer"]["env"]
            self.assertEqual("eof", result["answer"]["stdin"], msg=f"stdin was not closed: {result}")
            self.assertEqual("1", env["GIT_CONFIG_NOSYSTEM"])
            self.assertNotIn(env["GIT_CONFIG_GLOBAL"], (None, "", real_global))
            self.assertNotEqual(real_home, env["HOME"])
            self.assertNotEqual(real_home, env["USERPROFILE"])
            self.assertTrue(env["GIT_CEILING_DIRECTORIES"], msg="GIT_CEILING_DIRECTORIES not set")
            self.assertEqual("kept", env["PROBE_CALLER"], msg="caller env must merge on top")

    def test_caller_env_overrides_the_bounded_defaults(self):
        # covers: BO-4300c-2
        # angle: boundary
        """Control row: the caller's env wins over the bounded defaults."""
        with tempfile.TemporaryDirectory(prefix="bo4300f4-probe2-") as d:
            root = Path(d)
            probe = root / "probe_maker.py"
            probe.write_text(_PROBE_MAKER, encoding="utf-8")
            result = maker_fx.run_maker(
                ["x"], cwd=root, maker_path=probe,
                env={"GIT_CEILING_DIRECTORIES": "caller-wins"}, timeout=20,
            )
            self.assertEqual("caller-wins", result["answer"]["env"]["GIT_CEILING_DIRECTORIES"])
            self.assertEqual("1", result["answer"]["env"]["GIT_CONFIG_NOSYSTEM"])


class TestLinkCheckoutExemptionIsDeclared(unittest.TestCase):
    """M15: the census exemption for link_checkout is declared, not hidden by a split string."""

    def test_link_checkout_exemption_is_declared_with_a_reason(self):
        # covers: BO-4300f-4-i
        # angle: failure
        """MUST BE IMPLEMENTED: no split command string in the builders; the
        EXEMPTIONS reason names link_checkout; the census over the repo is []."""
        builders_rel = "unit_tests/build_orchestration/_workspace_maker_builders.py"
        text = (REPO_ROOT / builders_rel).read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(r"""["']work["']\s*\+\s*["']tree["']""", text),
            msg="the raw command is still spelled as a split string",
        )
        self.assertNotIn("_LINK", text)
        # with exemptions OFF the literal command must now be visible to the census
        unexempted = census_fx.census(REPO_ROOT, [builders_rel], apply_exemptions=False)
        self.assertTrue(unexempted, msg="the builders do not spell the command literally for the census")
        entry = next(e for e in census_fx.EXEMPTIONS if e["path"] == builders_rel)
        self.assertIn("link_checkout", entry["reason"])
        self.assertEqual([], census_fx.census(REPO_ROOT, census_fx.tracked_files()))


class TestCiHasDedicatedDeployedMakerJob(unittest.TestCase):
    """M14 / A11 option 2: a dedicated CI job runs the manual-marked deployed-maker tests."""

    FILTER_PATHS = (
        "templates/scripts/worktree",
        "templates/scripts/workspace_root.py",
        "scripts/build_phases_script_deploy_standalone.py",
        "scripts/build_deploy_manifest_helpers.py",
        "unit_tests/build_orchestration/",
    )
    FAMILY_TESTS = (
        "test_bo_4300a_1_deployed.py",
        "test_bo_4300f_4.py",
        "test_bo_4300a_1_budgets.py",
    )

    def test_ci_has_a_dedicated_deployed_maker_job_with_path_filter(self):
        # covers: BO-4300f-4
        # angle: criterion
        """MUST BE IMPLEMENTED: a job (not test-shard) on pull_request whose
        pytest run selects the three family files with -m including manual,
        path-filtered, reporting skips (-r s/a)."""
        doc = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
        triggers = doc.get("on", doc.get(True))
        self.assertIn("pull_request", triggers)
        candidates = []
        for name, job in doc["jobs"].items():
            if name == "test-shard":
                continue
            runs = "\n".join(str(s.get("run", "")) for s in job.get("steps", []))
            if all(t in runs for t in self.FAMILY_TESTS) and "pytest" in runs:
                candidates.append((name, job, runs))
        self.assertTrue(candidates, msg="no dedicated job runs the three family test files")
        name, job, runs = candidates[0]
        m_expr = re.search(r"""-m\s+(?:"([^"]*)"|'([^']*)'|(\S+))""", runs)
        self.assertIsNotNone(m_expr, msg=f"{name}: pytest has no -m selection")
        expr = next(g for g in m_expr.groups() if g is not None)
        self.assertRegex(expr, r"(?<!not )\bmanual\b", msg=f"{name}: -m {expr!r} does not include manual tests")
        self.assertRegex(runs, r"\s-r[a-zA-Z]*[sa]", msg=f"{name}: skipped/deselected tests are not reported")
        whole = yaml.safe_dump(job)
        for path in self.FILTER_PATHS:
            self.assertIn(path, whole, msg=f"{name}: path filter lacks {path}")
        self.assertIn("pull_request", whole, msg=f"{name}: job is not conditioned on pull_request")


if __name__ == "__main__":
    unittest.main()
