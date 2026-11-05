"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
AC: BO-4300a-1 -- "Every route that asks gets the same kind of workspace from
    the same maker." (AC-4: identical answer shape across the five routes)
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md

Split out of test_bo_4300a_1_deployed.py (verbatim apart from the
bootstrap.config_path change below) so that file does not grow past the
check-file-size ratchet. Same real-subprocess, real-git proof against the
DEPLOYED maker; setUpClass builds the deployed layout once.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/05]
  (classification: test_drift): bootstrap.config_path is
  <workspace>/.claude/skills_config.json (BO-4300c-2), per-workspace by
  contract, so it is treated as identity-derived like workspace_path and
  asserted to sit inside each route's workspace_path. All other keys stay
  strictly compared.
====================================================================
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_fixtures import (
    FIVE_ROUTES,
    DeployedMakerBuild,
    advance_hub,
    make_bare_hub,
    make_project,
    parse_json_stdout,
    run_maker,
    seed_hub,
)


def _split_canary_checks(answer: dict) -> tuple[dict, dict]:
    """Split an answer's `checks` into (everything else, the canary-proof keys
    `hooks_*_fired` and `hooks_canary_rejected`)."""
    rest: dict = {}
    canary: dict = {}
    for key, value in (answer.get("checks") or {}).items():
        is_canary = key == "hooks_canary_rejected" or (key.startswith("hooks_") and key.endswith("_fired"))
        (canary if is_canary else rest)[key] = value
    return rest, canary


class TestBO4300a1RouteShape(unittest.TestCase):
    """AC-4 shape proof against the DEPLOYED maker."""

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

        identity_derived = {"slug", "branch", "kind", "workspace_path", "workspace_path_posix", "worktree_path", "base_commit"}
        shared_keys = set(answers[0].keys()) - identity_derived - {"checks"}
        def _comparable(answer, key):
            # BO-4300c-2: bootstrap.config_path is <workspace>/.claude/skills_config.json,
            # per-workspace by contract, so it is identity-derived like workspace_path.
            # Every other bootstrap field stays in the strict comparison.
            value = answer.get(key)
            if key == "bootstrap" and isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != "config_path"}
            return value

        for key in shared_keys:
            values = {json.dumps(_comparable(a, key), sort_keys=True) for a in answers}
            self.assertEqual(
                len(values),
                1,
                msg=f"non-identity-derived key {key!r} differs across routes: "
                f"{[_comparable(a, key) for a in answers]}",
            )
        for a in answers:
            config_path = (a.get("bootstrap") or {}).get("config_path")
            self.assertTrue(config_path, msg=f"bootstrap.config_path missing: {a.get('bootstrap')}")
            self.assertIn(
                Path(str(a["workspace_path"])),
                Path(str(config_path)).parents,
                msg=f"bootstrap.config_path {config_path!r} is not inside workspace_path {a['workspace_path']!r}",
            )

        # The non-canary `checks` (dropped when this test was split out) are equal across the five routes.
        # The canary-proof keys are excluded: a scratch route reports them 'n/a' by BO-4300c-1's design.
        rests = [json.dumps(_split_canary_checks(a)[0], sort_keys=True) for a in answers]
        self.assertEqual(len(set(rests)), 1, msg=f"non-canary checks differ across routes: {rests}")
