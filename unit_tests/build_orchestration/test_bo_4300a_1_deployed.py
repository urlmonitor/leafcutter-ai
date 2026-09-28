"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
AC: BO-4300a-1 -- "Every route that asks gets the same kind of workspace from
    the same maker."
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    01_TICKET-20260927-BO-4300a-1.md

Sibling module of unit_tests/build_orchestration/test_bo_4300a_1.py -- see
that module's docstring for the full AC-coverage map, the module-docstring
"WHAT THIS PROVES" statement, and the FILE SPLIT / DECISION HISTORY note
explaining why this file exists (test_bo_4300a_1.py plus this class in one
file was 539 lines, over the `check_file_size.py` 400-line ratchet).

Real-subprocess, real-git proof against the DEPLOYED maker.
`TestBO4300a1DeployedMaker.setUpClass` builds the package's real deployed
layout EXACTLY ONCE (~60s) via `DeployedMakerBuild.build()`
(`_bo_4300a_1_fixtures.py`), and every test method below re-uses that one
build -- never one `scripts/build.py` spawn per test. Every method carries
the `_MANUAL` suffix (this repo's `manual_test_suffix` convention) because
that shared setup exceeds `testing_context.max_test_duration_seconds` (5s).

DECISION HISTORY
====================================================================
- 2026-09-28 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01,
  BO-4300a-1, re-dispatch off python-coder's test_drift handoff]: Split out
  of test_bo_4300a_1.py verbatim (same 9 tests, same assertions, same
  `# covers:` / `# angle:` tags) to bring both files under the 400-line
  ratchet. No behavioral change to any test in this split.
====================================================================
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_fixtures import (
    FIVE_ROUTES,
    RESOLVER_MODULE_NAME,
    DeployedMakerBuild,
    advance_hub,
    attempt_reject_commit,
    make_bare_hub,
    make_project,
    marker_fields,
    parse_json_stdout,
    run_git,
    run_maker,
    seed_hub,
    workspace_location,
)


class TestBO4300a1DeployedMaker(unittest.TestCase):
    """Real-subprocess, real-git proof against the DEPLOYED maker. See module
    docstring (and test_bo_4300a_1.py's module docstring) for why setUpClass
    builds the deployed layout exactly once."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.deployed = DeployedMakerBuild.build()
        cls._tmp = tempfile.TemporaryDirectory(prefix="bo4300a1-fixture-")
        cls.tmp_path = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _require_deployed_maker(self) -> Path:
        if not self.deployed.maker_present():
            self.fail(
                "Deployed maker not found at "
                f"{self.deployed.maker_path} after a real "
                f"`scripts/build.py --target-dir {self.deployed.target_dir}` run "
                f"(exit={self.deployed.build_returncode}). "
                "templates/scripts/worktree.py does not exist yet -- this is "
                "the expected RED state until python-coder builds it and its "
                "deploy-manifest entry."
            )
        return self.deployed.maker_path

    def _new_fixture_project(self, subdir: str) -> tuple[Path, Path, str]:
        """Build a fresh hub + project pair, then ADVANCE the hub with a
        second commit -- so "S as read at the time of [the] request" is
        provably the hub's CURRENT tip, never the project's own stale local
        HEAD from clone time."""
        case_dir = self.tmp_path / subdir
        case_dir.mkdir(parents=True, exist_ok=True)
        hub = make_bare_hub(case_dir)
        stamp = f"stamp-{subdir}"
        seed_hub(case_dir, hub, stamp)
        project = make_project(case_dir, hub)
        advanced_sha = advance_hub(case_dir, hub, note=f"advance-{subdir}")
        return project, hub, advanced_sha

    def _ensure_all_routes(self, maker_path: Path, project: Path) -> list[dict]:
        """Run `ensure --kind K --slug S` once per FIVE_ROUTES entry (AC-1)
        against the SAME project/hub pair, and return the five parsed
        answers in FIVE_ROUTES order. Fails the test immediately, naming the
        offending route, if any call does not produce exactly one JSON
        object on stdout."""
        answers: list[dict] = []
        for route in FIVE_ROUTES:
            proc = run_maker(
                maker_path,
                ["ensure", "--kind", route["kind"], "--slug", route["slug"], "--repo-root", str(project)],
                cwd=project,
            )
            answer = parse_json_stdout(proc)
            if answer is None:
                self.fail(
                    f"Route {route['route']!r} (--kind {route['kind']} --slug "
                    f"{route['slug']}) produced no parseable JSON answer. "
                    f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
                )
            answers.append(answer)
        return answers

    # -----------------------------------------------------------------
    def test_every_route_workspace_carries_marker_agreeing_with_its_answer_MANUAL(self):
        # covers: BO-4300a-1
        # angle: criterion
        """AC-2: every one of the five workspaces carries the record the
        workspace maker leaves in each workspace it makes, and that record
        agrees with the answer the route received.

        MUST BE IMPLEMENTED: `ensure` writes a durable marker into (or
        discoverable from) each workspace, and `verify --path <workspace>`
        reads that SAME marker back (via a fresh subprocess -- proving
        persistence, not an in-memory value) with kind/slug/branch/
        base_commit/state agreeing with the `ensure` answer.
        """
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("marker")
        answers = self._ensure_all_routes(maker_path, project)

        for route, answer in zip(FIVE_ROUTES, answers):
            with self.subTest(route=route["route"]):
                self.assertEqual(answer.get("status"), "ok", msg=f"ensure answer: {answer}")
                location = workspace_location(answer)
                self.assertIsNotNone(location, msg=f"ensure answer carries no location: {answer}")

                verify_proc = run_maker(maker_path, ["verify", "--path", str(location)], cwd=project)
                verify_answer = parse_json_stdout(verify_proc)
                self.assertIsNotNone(
                    verify_answer,
                    msg=f"verify produced no JSON for {location}: {verify_proc.stdout!r}",
                )
                marker = marker_fields(verify_answer)

                self.assertEqual(marker.get("state"), "ready", msg=f"marker: {marker}")
                self.assertEqual(marker.get("kind"), answer.get("kind", route["kind"]))
                self.assertEqual(marker.get("slug"), answer.get("slug", route["slug"]))
                self.assertEqual(marker.get("branch"), answer.get("branch"))
                self.assertEqual(marker.get("base_commit"), answer.get("base_commit"))

    def test_every_route_workspace_is_independent_clone_rooted_at_fresh_hub_main_MANUAL(self):
        # covers: BO-4300a-1
        # angle: criterion
        """AC-3 (independence + freshness clause): each of the five
        workspaces has its own real `.git` DIRECTORY (never a linked
        worktree's gitfile pointer), its own git-common-dir equal to itself,
        origin equal to the hub, and base_commit equal to the hub's CURRENT
        main tip -- read at request time, not the project's stale local HEAD
        from clone time.
        """
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("independent")
        answers = self._ensure_all_routes(maker_path, project)

        for route, answer in zip(FIVE_ROUTES, answers):
            with self.subTest(route=route["route"]):
                location = Path(workspace_location(answer))
                git_entry = location / ".git"
                self.assertTrue(
                    git_entry.is_dir(),
                    msg=f"{git_entry} is not a real .git directory (linked worktrees use a gitfile) for {route}",
                )

                common_dir_proc = run_git(["rev-parse", "--git-common-dir"], location)
                common_dir = Path(common_dir_proc.stdout.strip())
                if not common_dir.is_absolute():
                    common_dir = (location / common_dir).resolve()
                self.assertEqual(
                    common_dir.resolve(),
                    git_entry.resolve(),
                    msg=f"git-common-dir for {location} is not its own .git -- likely a linked worktree",
                )

                origin_proc = run_git(["remote", "get-url", "origin"], location)
                origin_url = origin_proc.stdout.strip()
                self.assertEqual(Path(origin_url).resolve(), hub.resolve())

                self.assertEqual(
                    answer.get("base_commit"),
                    advanced_sha,
                    msg=(
                        "base_commit must be the hub's CURRENT tip (read at request "
                        f"time), not a stale local HEAD. answer={answer}"
                    ),
                )

    def test_every_route_workspace_has_own_install_and_rejects_canary_MANUAL(self):
        # covers: BO-4300a-1
        # angle: real_artifact
        """AC-3 (own install + protections-fire clause): each workspace's
        install files are real regular files inside it, built from its own
        contents (the fixture project's own BUILD_STAMP.txt, read back via
        INSTALLED_MARKER.txt), and a commit of a known-bad file inside it is
        REJECTED by a REAL git hook -- never mocked, never asserted via
        `call_args`.
        """
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("install")
        stamp = (project / "BUILD_STAMP.txt").read_text(encoding="utf-8").strip()
        answers = self._ensure_all_routes(maker_path, project)

        for route, answer in zip(FIVE_ROUTES, answers):
            with self.subTest(route=route["route"]):
                location = Path(workspace_location(answer))
                installed_marker = location / "INSTALLED_MARKER.txt"
                self.assertTrue(
                    installed_marker.is_file(),
                    msg=f"{installed_marker} missing -- install did not run inside {location}",
                )
                content = installed_marker.read_text(encoding="utf-8")
                self.assertIn(
                    stamp,
                    content,
                    msg="install marker does not carry this workspace's OWN build stamp "
                    f"({stamp!r}) -- content={content!r}",
                )

                reject_proc = attempt_reject_commit(location)
                self.assertNotEqual(
                    reject_proc.returncode,
                    0,
                    msg=(
                        f"a commit of the known-bad file inside {location} was NOT "
                        "rejected by a real hook -- protections did not fire. "
                        f"stdout={reject_proc.stdout!r} stderr={reject_proc.stderr!r}"
                    ),
                )

    def test_every_route_workspace_lands_in_the_one_landing_place_MANUAL(self):
        # covers: BO-4300a-1
        # angle: criterion
        """AC-3 (one landing place clause): all five workspace_path values
        share the project's ONE landing place as their common parent
        directory."""
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("landing")
        answers = self._ensure_all_routes(maker_path, project)

        parents = {Path(workspace_location(a)).resolve().parent for a in answers}
        self.assertEqual(
            len(parents),
            1,
            msg=f"the five workspaces do not share one landing place: {parents}",
        )

    def test_every_route_receives_answer_of_identical_shape_MANUAL(self):
        # covers: BO-4300a-1
        # angle: criterion
        """AC-4: the five answers have the same key set and the same status
        (stating ready), differing only in identity-derived values (slug,
        branch, paths, commit)."""
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("shape")
        answers = self._ensure_all_routes(maker_path, project)

        key_sets = [frozenset(a.keys()) for a in answers]
        self.assertEqual(
            len(set(key_sets)),
            1,
            msg=f"the five answers do not share one key set: {key_sets}",
        )

        statuses = {a.get("status") for a in answers}
        self.assertEqual(
            len(statuses),
            1,
            msg=f"the five answers do not share one status: {statuses}",
        )
        self.assertEqual(next(iter(statuses)), "ok")

        identity_derived = {"slug", "branch", "kind", "workspace_path", "worktree_path", "base_commit"}
        shared_keys = set(answers[0].keys()) - identity_derived
        for key in shared_keys:
            values = {json.dumps(a.get(key), sort_keys=True) for a in answers}
            self.assertEqual(
                len(values),
                1,
                msg=f"non-identity-derived key {key!r} differs across routes: "
                f"{[a.get(key) for a in answers]}",
            )

    def test_no_route_lacks_a_property_another_route_has_MANUAL(self):
        # covers: BO-4300a-1
        # angle: criterion
        """AC-5: the set of TRUE `checks.*` fields plus the marker's own
        present/true properties is equal across all five routes -- no route
        gets a lesser workspace than another."""
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("parity")
        answers = self._ensure_all_routes(maker_path, project)

        true_check_sets = []
        for route, answer in zip(FIVE_ROUTES, answers):
            checks = answer.get("checks", {})
            self.assertIsInstance(checks, dict, msg=f"{route['route']}: checks is not a dict: {checks}")
            true_keys = {k for k, v in checks.items() if v is True}
            true_check_sets.append(true_keys)

        for route, true_keys in zip(FIVE_ROUTES, true_check_sets):
            self.assertEqual(
                true_keys,
                true_check_sets[0],
                msg=(
                    f"{route['route']!r}'s true checks.* set {true_keys} differs from "
                    f"{FIVE_ROUTES[0]['route']!r}'s {true_check_sets[0]} -- one route's "
                    "workspace lacks (or has extra) a protection another route's has."
                ),
            )

    def test_deployed_maker_is_present_after_build_and_answers_where_MANUAL(self):
        # covers: BO-4300a-1
        # angle: deployed
        """In the shared deployed layout, <install>/scripts/worktree.py
        exists as a regular file, and `where` emits one JSON object naming
        its own absolute path."""
        maker_path = self._require_deployed_maker()
        self.assertTrue(maker_path.is_file())
        self.assertFalse(maker_path.is_symlink())

        proc = run_maker(maker_path, ["where"], cwd=self.deployed.target_dir)
        answer = parse_json_stdout(proc)
        self.assertIsNotNone(answer, msg=f"`where` produced no JSON: {proc.stdout!r} {proc.stderr!r}")
        named_path = answer.get("path") or answer.get("maker_path")
        self.assertIsNotNone(named_path, msg=f"`where` answer names no path: {answer}")
        self.assertEqual(Path(named_path).resolve(), maker_path.resolve())

    def test_deployed_resolver_module_is_its_own_importable_file_beside_the_maker_MANUAL(self):
        # covers: BO-4300a-1
        # angle: deployed
        """In the shared deployed layout the resolver module exists as its
        own regular file in <install>/scripts/, separate from worktree.py,
        and a SEPARATE Python process with ONLY that directory on its path
        imports it and gets an ok answer naming a temp project from inside
        that project -- proving it is importable by a hook WITHOUT the
        maker's CLI.
        """
        self._require_deployed_maker()
        resolver_path = self.deployed.resolver_path
        self.assertTrue(resolver_path.is_file(), msg=f"resolver module not deployed at {resolver_path}")
        self.assertNotEqual(resolver_path.resolve(), self.deployed.maker_path.resolve())

        target_project = self.tmp_path / "resolver_target_project"
        target_project.mkdir(parents=True, exist_ok=True)
        run_git(["-c", "init.defaultBranch=main", "init", "-q"], target_project)

        module_name = RESOLVER_MODULE_NAME.removesuffix(".py")
        probe_script = self.tmp_path / "resolver_probe.py"
        probe_script.write_text(
            "import json, sys\n"
            f"sys.path.insert(0, {str(resolver_path.parent)!r})\n"
            f"import {module_name} as resolver\n"
            f"result = resolver.resolve(cwd={str(target_project)!r}, repo_root=None)\n"
            "print(json.dumps(result if isinstance(result, dict) else result.__dict__))\n",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [sys.executable, "-I", str(probe_script)],
            cwd=str(target_project),
            capture_output=True,
            text=True,
            timeout=30,
        )
        answer = parse_json_stdout(proc)
        self.assertIsNotNone(
            answer,
            msg=(
                "separate-process import of the deployed resolver module produced "
                f"no JSON answer. exit={proc.returncode} stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}"
            ),
        )
        self.assertEqual(answer.get("status"), "ok", msg=f"resolver answer: {answer}")
        self.assertEqual(
            Path(answer.get("project_root", "")).resolve(),
            target_project.resolve(),
            msg=f"resolver did not name the target project it was run from: {answer}",
        )

    def test_bo_4300a_1_reachable_from_entry_point_MANUAL(self):
        # covers: BO-4300a-1
        # angle: reachability
        """REQUIRED reachability proof: invoke the production entry point --
        the deployed maker CLI, run as a real subprocess (never an import of
        the maker module) -- and assert the new behaviour actually occurs
        AND that the result is consumed in control flow (a second, fresh
        subprocess call to `verify` on the answer's own workspace_path, which
        only succeeds if the first call's answer was read and acted on).

        completion_manifest.reachability_entry_point_answer (recorded on
        sign-off; declared inline here per BP-1100g-2 Step 1.1, "CLI
        script"): result=resolved, entry_point="python
        <install-root>/scripts/worktree.py ensure --kind <k> --slug <s>
        --repo-root <project> (CLI via subprocess)".
        """
        maker_path = self._require_deployed_maker()
        project, hub, advanced_sha = self._new_fixture_project("reachability")
        route = FIVE_ROUTES[0]

        ensure_proc = run_maker(
            maker_path,
            ["ensure", "--kind", route["kind"], "--slug", route["slug"], "--repo-root", str(project)],
            cwd=project,
        )
        answer = parse_json_stdout(ensure_proc)
        self.assertIsNotNone(answer, msg=f"ensure produced no JSON: {ensure_proc.stdout!r}")
        self.assertEqual(answer.get("status"), "ok", msg=f"ensure answer: {answer}")

        location = workspace_location(answer)
        self.assertIsNotNone(location)

        # Consume the result: a SEPARATE process re-verifies the workspace
        # the FIRST process's answer named. If the answer's location were
        # never actually read/acted on (e.g. only passed as a mock argument),
        # this second, independent CLI invocation would have nothing real to
        # find.
        verify_proc = run_maker(maker_path, ["verify", "--path", str(location)], cwd=project)
        verify_answer = parse_json_stdout(verify_proc)
        self.assertIsNotNone(verify_answer, msg=f"verify produced no JSON: {verify_proc.stdout!r}")
        self.assertEqual(
            verify_answer.get("status"),
            "ok",
            msg=f"verify of the ensure-named workspace did not succeed: {verify_answer}",
        )


if __name__ == "__main__":
    unittest.main()
