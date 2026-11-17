"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_x.py
AC: BO-4300e-2-x -- Asking for, or locating, a half-cleared workspace never answers it as ready:
the answer is HALF_CLEARED, the leftover is not touched, and the shared project is not contacted.

Real-subprocess proof against the DEPLOYED maker. Two leftovers of the feature work, one per run
(the slugs differ because both live in the one project of this test):
  stopped    -- the leftover of a REAL clearing that stopped part-way after 10 repository items
                (the BO-4300e-2-ix stop hook), its record in the clearing-started state;
  unreadable -- a record that still says ready beside a repository whose stored objects are deleted
                (the BO-4300e-2-xi fixture).
Workspaces use KIND "feature" (the shared helper's kind). Helpers come from test_bo_4300e_2.py,
_2_ix.py and _2_xi.py.

DECISION HISTORY
====================================================================
- 2026-11-03 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-x]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import hashlib
import os
import stat
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND
from unit_tests.build_orchestration.test_bo_4300e_2_xi import DamagedCase

ABORT = {"LEAFCUTTER_WORKSPACE_ABORT_AT": "after_clone"}


def says_stopped_part_way(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("part-way", "part way", "partway")) and "clear" in low and "again" in low


class LeftoverCase(DamagedCase):
    def leftovers(self) -> dict[str, Path]:
        stopped = self.stopped_leftover("invoice-export")
        unreadable = self.zeta("invoice-export-b")
        return {"stopped": stopped, "unreadable": unreadable}

    def ensure_cli(self, slug: str, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        return self.cli(["ensure", "--kind", KIND, "--slug", slug, "--repo-root", str(self.project)],
                        extra_env=extra_env)

    def locate_cli(self, ws: Path, by: str = "name", extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        where = ["--kind", KIND, "--slug", ws.name] if by == "name" else ["--path", str(ws)]
        return self.cli(["locate", *where, "--repo-root", str(self.project)], extra_env=extra_env)

    @staticmethod
    def full_snap(ws: Path) -> list[tuple[str, bool, int, str]]:
        """Every entry under *ws* (empty folders and file modes included, .git too) with a content digest."""
        out = []
        for p in sorted(ws.rglob("*")):
            info = p.lstat()
            is_dir = stat.S_ISDIR(info.st_mode)
            digest = "" if is_dir or p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()
            out.append((p.relative_to(ws).as_posix(), is_dir, stat.S_IMODE(info.st_mode), digest))
        return out

    def assert_half_cleared(self, res: dict[str, Any], ws: Path, label: str) -> None:
        answer = res["answer"]
        self.assertNotEqual(answer.get("status"), "ok", msg=f"{label}: {res}")
        self.assertEqual(answer.get("code"), "HALF_CLEARED", msg=f"{label}: {res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{label}: {res}")
        self.assertNotIn("workspace_path", answer, msg=f"{label}: {answer}")


class TestHalfClearedLeftovers(LeftoverCase):
    def test_ensure_refuses_both_half_cleared_leftovers_with_half_cleared_code(self):
        # covers: BO-4300e-2-x
        # angle: discrimination
        """AC-1: for each leftover the real ensure answers refused HALF_CLEARED (exit 2) with remnant_path
        naming the leftover, no workspace_path, and a message saying an earlier clearing stopped
        part-way and that asking to clear it again finishes it. Never ok, never INCOMPLETE, never
        resumed or completed."""
        for name, ws in self.leftovers().items():
            res = self.ensure_cli(ws.name)
            self.assert_half_cleared(res, ws, name)
            answer = res["answer"]
            self.assertEqual(os.path.normcase(os.path.normpath(str(answer.get("remnant_path", "")))),
                             os.path.normcase(os.path.normpath(str(ws))), msg=f"{name}: {answer}")
            self.assertTrue(says_stopped_part_way(str(answer.get("message", ""))), msg=f"{name}: {answer}")
        # Control: an ordinary ready workspace (intact repository) is not a leftover, so the same request
        # is answered ok; a decision that took every ready record with a repository folder for a leftover
        # would refuse it too.
        healthy = self.ensure("healthy-export")
        control = self.ensure_cli(healthy.name)
        self.assertEqual(control["answer"].get("status"), "ok", msg=f"{control}")
        self.assertNotEqual(control["answer"].get("code"), "HALF_CLEARED", msg=f"{control}")

    def test_ensure_cli_is_reachable_and_exits_2_on_half_cleared_leftover(self):
        # covers: BO-4300e-2-x
        # angle: reachability
        """AC-1: the real CLI (worktree.py ensure --kind feature --slug invoice-export) prints JSON with
        code HALF_CLEARED, status refused and exit code 2; the code is additive, so schema_version equals
        the one of an ordinary answer of the same maker."""
        ws = self.stopped_leftover("invoice-export")
        res = self.ensure_cli(ws.name)
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "HALF_CLEARED"),
                         msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        ordinary = self.locate_cli(self.landing / KIND / "never-made")["answer"]
        self.assertTrue(ordinary.get("schema_version"), msg=f"fixture: {ordinary}")
        self.assertEqual(res["answer"].get("schema_version"), ordinary.get("schema_version"), msg=f"{res['answer']}")

    def test_half_made_workspace_is_still_completed_not_captured(self):
        # covers: BO-4300e-2-x
        # angle: boundary
        """AC-1: a workspace made half-way with LEAFCUTTER_WORKSPACE_ABORT_AT=after_clone (repository
        readable, record in the creating state, no clearing-started state) is asked for again and is
        completed in place (ok, workspace_action completed), not refused HALF_CLEARED. Control, in the
        same run: the leftover of a stopped clearing IS refused HALF_CLEARED."""
        half = self.ensure("half-made", extra_env=ABORT)
        self.assertTrue(half.is_dir(), msg="fixture: nothing was made")
        res = self.ensure_cli("half-made")
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["answer"].get("workspace_action"), "completed", msg=f"{res}")
        self.assertNotEqual(res["answer"].get("code"), "HALF_CLEARED", msg=f"{res}")
        leftover = self.stopped_leftover("invoice-export")
        self.assertEqual(self.ensure_cli(leftover.name)["answer"].get("code"), "HALF_CLEARED")

    def test_locate_reports_half_cleared_not_ready_for_both_leftovers(self):
        # covers: BO-4300e-2-x
        # angle: discrimination
        """AC-1: the real locate (by --kind/--slug and by --path) over each leftover is never ok and never
        carries the leftover as workspace_path; it answers HALF_CLEARED saying the workspace is
        half-cleared. A ready record with a damaged repository would be located ok, and a
        clearing-started record would read as INCOMPLETE; both are caught. locate stays read-only."""
        for name, ws in self.leftovers().items():
            before = self.full_snap(ws)
            for by in ("name", "path"):
                res = self.locate_cli(ws, by)
                self.assert_half_cleared(res, ws, f"{name}/{by}")
                low = str(res["answer"].get("message", "")).lower()
                self.assertTrue("half-cleared" in low or "half cleared" in low, msg=f"{name}/{by}: {res['answer']}")
            self.assertEqual(self.full_snap(ws), before, msg=f"{name}: locate changed the leftover")
        # Control: an ordinary ready workspace (intact repository) is located ok, not half-cleared.
        healthy = self.ensure("healthy-locate")
        for by in ("name", "path"):
            control = self.locate_cli(healthy, by)
            self.assertEqual(control["answer"].get("status"), "ok", msg=f"{by}: {control}")
            self.assertNotEqual(control["answer"].get("code"), "HALF_CLEARED", msg=f"{by}: {control}")

    def test_list_never_reports_a_half_cleared_leftover_as_ready(self):
        # covers: BO-4300e-2-x
        # angle: criterion
        """AC-1: the real list never carries an entry for either leftover with state ready (a new state
        value is accepted, ready is a failure). The ready record with the damaged repository is the
        case that lists ready today."""
        leftovers = self.leftovers()
        res = self.cli(["list", "--repo-root", str(self.project)])
        self.assertTrue(res["answer"], msg=f"list gave no answer: {res}")
        wanted = {os.path.normcase(os.path.normpath(str(ws))): name for name, ws in leftovers.items()}

        def walk(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, dict):
                return [value] + [d for v in value.values() for d in walk(v)]
            if isinstance(value, list):
                return [d for v in value for d in walk(v)]
            return []

        named = [d for d in walk(res["answer"])
                 if any(isinstance(v, str) and os.path.normcase(os.path.normpath(v)) in wanted
                        for v in d.values())]
        self.assertTrue(named, msg=f"fixture: list names neither leftover: {res['answer']}")
        for entry in named:
            self.assertNotEqual(entry.get("state"), "ready", msg=f"a half-cleared leftover listed ready: {entry}")

    def test_leftover_is_identical_before_and_after_ensure_and_locate(self):
        # covers: BO-4300e-2-x
        # angle: criterion
        """AC-1: a snapshot of the whole leftover (every entry with .git, empty folders and file modes)
        is equal before and after the ensure and the locate request, both of which answer HALF_CLEARED
        (so they ran): no write, rename or delete inside it, no rescue folder, no rewritten record. The
        per-work lock lives outside the leftover and is gone after the answer."""
        for name, ws in self.leftovers().items():
            before = self.full_snap(ws)
            siblings = sorted(p.name for p in ws.parent.iterdir())
            for res in (self.ensure_cli(ws.name), self.locate_cli(ws)):
                self.assert_half_cleared(res, ws, name)
            self.assertEqual(self.full_snap(ws), before, msg=f"{name}: the leftover changed")
            self.assertEqual(sorted(p.name for p in ws.parent.iterdir()), siblings, msg=f"{name}: a rescue or lock appeared")

    def test_neither_request_fetches_or_pushes_on_a_half_cleared_leftover(self):
        # covers: BO-4300e-2-x
        # angle: discrimination
        """AC-1: with the shared project moved away (any fetch fails) both requests still answer
        HALF_CLEARED, never FETCH_FAILED and never a clone, the shared project's refs are identical
        afterwards, the leftover is byte-identical, and git is never asked to fetch: the commands git was
        started with are read back through GIT_TRACE, because a fetch whose failure is ignored would answer
        the same. Catches a half-cleared decision placed after the fetch in ensure or after the
        completion of a half-made workspace."""
        leftovers = self.leftovers()
        refs_before = self.refs(self.hub)
        before = {name: self.full_snap(ws) for name, ws in leftovers.items()}
        traces: list[tuple[str, Path]] = []
        self.hub_moved_away()
        try:
            results = []
            for name, ws in leftovers.items():
                ensure_env, ensure_trace = self.git_trace(f"{name}-ensure")
                locate_env, locate_trace = self.git_trace(f"{name}-locate")
                traces += [(f"{name}/ensure", ensure_trace), (f"{name}/locate", locate_trace)]
                results.append((name, self.ensure_cli(ws.name, ensure_env), self.locate_cli(ws, "name", locate_env)))
        finally:
            self.hub_back()
        for name, ensured, located in results:
            for res in (ensured, located):
                self.assertNotIn(res["answer"].get("code"), ("FETCH_FAILED", "GIT_FAILED"), msg=f"{name}: {res}")
                self.assertEqual(res["answer"].get("code"), "HALF_CLEARED", msg=f"{name}: {res}")
        self.assertEqual(self.refs(self.hub), refs_before, msg="the shared project changed")
        for name, ws in leftovers.items():
            self.assertEqual(self.full_snap(ws), before[name], msg=f"{name}: the leftover changed")
        for label, trace in traces:
            self.assertEqual(self.fetches_in(trace), [], msg=f"{label}: git was asked to fetch")


if __name__ == "__main__":
    unittest.main()
