"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_ix.py
AC: BO-4300e-2-ix -- A clearing that stops part-way is never answered cleared, and asking again
finishes it without a token, a fetch or a second unsent-work check.

Real-subprocess proof against the DEPLOYED maker. A `sitecustomize.py` on the maker process's
PYTHONPATH (the `extra_env` of `cli()`, modelled on the locked.bin hook of test_bo_4300e_2_viii.py)
makes the deletion STOP: at the chosen point it raises OSError "directory not empty" and from then
on every further delete of an item of the workspace fails the same way (a program holding the
folder), so the request that stopped really stops. The items are matched by NAME (a spec file lists
the names of the workspace's items, taken by the test before the request) because on POSIX
`shutil.rmtree` deletes by name relative to a directory descriptor. Stop points:
  first   -- the very first item the maker deletes
  repo10  -- an item inside the repository, after 10 repository items were deleted
  record  -- the workspace record
  last    -- the last item it would delete (the workspace folder itself)
Workspaces use KIND "feature" (the shared helper's kind). Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-11-03 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-ix]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND
from unit_tests.build_orchestration.test_bo_4300e_2_iv import HolderCase

POINTS = ("first", "repo10", "record", "last")

STOP_SITECUSTOMIZE = '''\
import errno
import json
import os

_real_unlink, _real_rmdir = os.unlink, os.rmdir
_spec = json.load(open(os.environ["STOP_SPEC"], encoding="utf-8"))
_all, _repo = set(_spec["all"]), set(_spec["repo"])
_state = {"count": 0, "stopped": False}


def _name(path):
    return os.path.basename(os.fspath(path).rstrip("/\\\\"))


def _must_stop(path):
    name = _name(path)
    if name not in _all:
        return False
    if _state["stopped"]:
        return True
    mode = _spec["mode"]
    if mode == "first":
        _state["count"] += 1
        hit = _state["count"] == 1
    elif mode == "repo10":
        if name in _repo:
            _state["count"] += 1
        hit = _state["count"] == 11 and name in _repo
    elif mode == "record":
        hit = name == _spec["record"]
    else:
        _state["count"] += 1
        hit = _state["count"] == _spec["total"]
    if hit:
        _state["stopped"] = True
        with open(os.environ["FIRED_FLAG"], "w") as flag:
            flag.write("stopped")
    return hit


def unlink(path, *args, **kwargs):
    if _must_stop(path):
        raise OSError(errno.ENOTEMPTY, "Directory not empty", os.fspath(path))
    return _real_unlink(path, *args, **kwargs)


def rmdir(path, *args, **kwargs):
    if _must_stop(path):
        raise OSError(errno.ENOTEMPTY, "Directory not empty", os.fspath(path))
    return _real_rmdir(path, *args, **kwargs)


os.unlink = unlink
os.remove = unlink
os.rmdir = rmdir
'''


def part_way(text: str) -> bool:
    """True when *text* says a clearing stopped part-way and that asking again finishes it."""
    low = text.lower()
    return any(w in low for w in ("part-way", "part way", "partway")) and "again" in low


class StopCase(HolderCase):
    """A workspace with 300 files in 40 folders, and the means to stop its clearing at a chosen item."""

    def bulk_alpha(self, slug: str) -> Path:
        ws = self.ensure(slug)
        for i in range(300):
            folder = ws / "bulk" / f"d{i % 40:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"f{i:03d}.dat").write_text("x\n", encoding="utf-8", newline="\n")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("bulk/\n")
        return ws

    def stop_env(self, ws: Path, point: str) -> dict[str, str]:
        everything, outside_repo, repo = [ws.name], set(), set()
        for root, dirs, files in os.walk(ws):
            inside = ".git" in Path(root).relative_to(ws).parts or Path(root).name == ".git"
            for name in (*dirs, *files):
                everything.append(name)
                (repo if inside or name == ".git" else outside_repo).add(name)
        repo_only = sorted((repo - outside_repo) - {"workspace.json"})
        spec = {"mode": point, "all": sorted(set(everything)), "repo": repo_only,
                "record": "workspace.json", "total": len(everything)}
        folder = self.tmp / f"stop-{ws.name}"
        folder.mkdir(exist_ok=True)
        (folder / "sitecustomize.py").write_text(STOP_SITECUSTOMIZE, encoding="utf-8", newline="\n")
        spec_file = folder / "spec.json"
        spec_file.write_text(json.dumps(spec), encoding="utf-8", newline="\n")
        self.fired = folder / "fired.flag"
        return {"PYTHONPATH": str(folder), "STOP_SPEC": str(spec_file), "FIRED_FLAG": str(self.fired)}

    def stopped_request(self, ws: Path, point: str) -> dict[str, Any]:
        """The remove request that stops at *point*; fails when the stop never happened."""
        res = self.cli(["remove", "--path", str(ws), "--repo-root", str(self.project)],
                       extra_env=self.stop_env(ws, point))
        self.assertTrue(self.fired.exists(), msg=f"fixture: the clearing never reached the {point!r} stop: {res}")
        return res

    def repeat(self, ws: Path, by: str = "path", token: str | None = None,
               extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        where = ["--path", str(ws)] if by == "path" else ["--kind", KIND, "--slug", ws.name]
        extra = ["--discard-token", token] if token else []
        return self.cli(["remove", *where, "--repo-root", str(self.project), *extra], extra_env=extra_env)

    def git_trace(self, label: str) -> tuple[dict[str, str], Path]:
        """An environment that makes every git the maker starts write its command line to a fresh file, and that file."""
        trace = self.tmp / f"git-trace-{label}.txt"
        trace.unlink(missing_ok=True)
        return {"GIT_TRACE": str(trace)}, trace

    @staticmethod
    def fetches_in(trace: Path) -> list[str]:
        """The traced git command lines that run ``git fetch`` (none when git was never started)."""
        lines = trace.read_text(encoding="utf-8", errors="replace").splitlines() if trace.is_file() else []
        return [line for line in lines if re.search(r"\bgit(\.exe)?\b.* fetch\b", line)]

    def landing_entries_named(self, slug: str) -> list[str]:
        return [str(p) for p in self.landing.rglob("*") if p.name == slug]

    def stopped_leftover(self, slug: str, point: str = "repo10") -> Path:
        ws = self.bulk_alpha(slug)
        self.stopped_request(ws, point)
        self.assertTrue(os.path.lexists(ws), msg="fixture: nothing is left of the stopped clearing")
        return ws

    def hub_moved_away(self) -> Path:
        moved = self.hub.with_name(self.hub.name + "-moved")
        os.rename(self.hub, moved)

        def _back() -> None:
            if moved.exists() and not self.hub.exists():
                os.rename(moved, self.hub)

        self.addCleanup(_back)
        self.moved_hub = moved
        return moved

    def hub_back(self) -> None:
        os.rename(self.moved_hub, self.hub)


class TestStoppedClearing(StopCase):
    def test_stopped_clearing_is_refused_not_cleared_and_says_ask_again(self):
        # covers: BO-4300e-2-ix
        # angle: criterion
        """AC-1: at each of the four stop points the request that stopped is refused PROCESS_HOLDS_FILES
        (exit 2), never ok, and its message says the clearing stopped part-way and that making the
        same request again finishes it. Must be implemented: the stopped-clearing message."""
        for index, point in enumerate(POINTS):
            with self.subTest(point=point):
                ws = self.bulk_alpha(f"alpha-{index}")
                res = self.stopped_request(ws, point)
                answer = res["answer"]
                self.assertNotEqual(answer.get("status"), "ok", msg=f"{point}: {res}")
                self.assertEqual(answer.get("code"), "PROCESS_HOLDS_FILES", msg=f"{point}: {res}")
                self.assertEqual(res["exit_code"], 2, msg=f"{point}: {res}")
                self.assertTrue(part_way(str(answer.get("message", ""))), msg=f"{point}: {answer}")
                self.assertTrue(os.path.lexists(ws), msg=f"{point}: the location is gone yet not cleared")

    def test_remove_cli_stops_and_the_repeat_finishes_it_end_to_end(self):
        # covers: BO-4300e-2-ix
        # angle: reachability
        """AC-1: the real CLI (worktree.py remove --path) run twice, the stop hook on the first run only:
        the first answer is refused with the part-way wording, the second is ok with exit 0 and
        nothing of the workspace remains at its location or anywhere in the landing place."""
        ws = self.bulk_alpha("alpha")
        first = self.stopped_request(ws, "repo10")
        self.assertEqual(first["answer"].get("status"), "refused", msg=f"{first}")
        self.assertTrue(part_way(str(first["answer"].get("message", ""))), msg=f"{first['answer']}")
        second = self.repeat(ws)
        self.assertEqual(second["answer"].get("status"), "ok", msg=f"{second}")
        self.assertEqual(second["exit_code"], 0, msg=f"{second}")
        self.assertFalse(os.path.lexists(ws), msg="something of alpha remains")
        self.assertEqual(self.landing_entries_named("alpha"), [])

    def test_repeat_finishes_from_every_stop_point_by_location_and_by_name(self):
        # covers: BO-4300e-2-ix
        # angle: criterion
        """AC-1: for all four stop points, once addressed by --path and once by --kind/--slug, the repeat
        carries no token and is ok; a walk of the landing place finds no entry of that name. The
        record-gone stop point covers the by-name arm when no record exists."""
        for point in POINTS:
            for by in ("path", "name"):
                with self.subTest(point=point, by=by):
                    ws = self.bulk_alpha(f"alpha-{point}-{by}")
                    self.stopped_request(ws, point)
                    res = self.repeat(ws, by)
                    self.assertEqual(res["answer"].get("status"), "ok", msg=f"{point}/{by}: {res}")
                    self.assertEqual(res["exit_code"], 0, msg=f"{point}/{by}: {res}")
                    self.assertFalse(os.path.lexists(ws), msg=f"{point}/{by}: something remains")
                    self.assertEqual(self.landing_entries_named(ws.name), [], msg=f"{point}/{by}")

    def test_repeat_is_never_not_found_unsent_or_fetch_failed(self):
        # covers: BO-4300e-2-ix
        # angle: discrimination
        """AC-1: after each stop point the shared project is moved away (any fetch fails) and the repeat
        carries no token: it is ok, never NOT_FOUND (record deleted first), FETCH_FAILED (fetch
        repeated) or UNSENT_WORK (tracked files already gone read as uncommitted); the shared
        project's refs are identical afterwards, and git is never asked to fetch (a repeated fetch
        whose failure is ignored would answer the same, so the commands git was started with are read
        back through GIT_TRACE). Control: a record that carries the clearing commit but not the
        clearing state is checked normally (UNSENT_WORK for a new file), so the state, not the commit
        alone, marks a started clearing. Problems are collected (not sub-tests) so that every failing
        point is an ordinary failure of this test. Wrong versions caught: the record deleted before the
        repository files, a repeated fetch, a repeated unsent-work check over the remaining files, no
        clearing-started marker."""
        refs_before = self.refs(self.hub)
        self.assertTrue(refs_before)
        problems: list[str] = []
        for index, point in enumerate(POINTS):
            ws = self.bulk_alpha(f"alpha-{index}")
            self.stopped_request(ws, point)
            env, trace = self.git_trace(point)
            self.hub_moved_away()
            try:
                res = self.repeat(ws, extra_env=env)
            finally:
                self.hub_back()
            answer = res["answer"]
            code = answer.get("code")
            if code in ("NOT_FOUND", "UNSENT_WORK", "FETCH_FAILED", "GIT_FAILED"):
                problems.append(f"{point}: answered {code}: {res}")
            if answer.get("status") != "ok":
                problems.append(f"{point}: not ok: {res}")
            if os.path.lexists(ws):
                problems.append(f"{point}: something remains")
            if self.refs(self.hub) != refs_before:
                problems.append(f"{point}: the shared project changed")
            if self.fetches_in(trace):
                problems.append(f"{point}: git was asked to fetch: {self.fetches_in(trace)}")
        self.assertEqual(problems, [])

        control = self.bulk_alpha("alpha-ready")
        self.stopped_request(control, "first")
        record = control / ".leafcutter" / "workspace.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(data.get("state"), "clearing", msg=f"fixture: {data}")
        self.assertTrue(data.get("clearing_commit"), msg=f"fixture: {data}")
        record.write_text(json.dumps({**data, "state": "ready"}), encoding="utf-8", newline="\n")
        (control / "late.txt").write_text("not on the shared project\n", encoding="utf-8", newline="\n")
        res = self.repeat(control)
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"a ready record was finished unchecked: {res}")
        self.assertTrue((control / "late.txt").is_file(), msg="the new file was discarded without a check")

    def test_clearing_marker_is_written_atomically_before_any_deletion(self):
        # covers: BO-4300e-2-ix
        # angle: real_artifact
        """AC-1: with the stop at the very first item, the record read back from disk parses as JSON,
        carries state "clearing", names this project and the workspace location, records the line-of-work
        commit equal to the HEAD taken before the request, and no .workspace-*.json.tmp is left."""
        ws = self.bulk_alpha("alpha")
        head = self.git(["rev-parse", "HEAD"], ws)
        self.stopped_request(ws, "first")
        record = ws / ".leafcutter" / "workspace.json"
        self.assertTrue(record.is_file(), msg="the record is gone: nothing marked the clearing as started")
        data = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(data.get("state"), "clearing", msg=f"{data}")
        values = [os.path.normcase(os.path.normpath(v)) if isinstance(v, str) else v for v in data.values()]
        self.assertIn(os.path.normcase(os.path.normpath(str(ws))), values, msg=f"location not named: {data}")
        self.assertIn(os.path.normcase(os.path.normpath(str(self.project))), values, msg=f"project not named: {data}")
        self.assertIn(head, [v for v in data.values() if isinstance(v, str)], msg=f"commit not recorded: {data}")
        self.assertEqual(list(record.parent.glob(".workspace-*.json.tmp")), [])

    def test_nothing_is_deleted_or_marked_before_the_unsent_work_check_passes(self):
        # covers: BO-4300e-2-ix
        # angle: discrimination
        """AC-1: a workspace with an unpushed commit and an uncommitted file is refused UNSENT_WORK, and one
        with a program running inside it PROCESS_HOLDS_FILES; in both the folder, repository and record
        are byte-identical before and after (the record was not rewritten to the clearing state). The
        control, a clean workspace whose clearing is stopped, has been marked "clearing", so identical
        does not mean nothing ran."""
        unsent, _sha = self.make_unsent("beta", "b")
        before = self.snap(unsent, with_git=True)
        self.assertEqual(self.remove(unsent)["answer"].get("code"), "UNSENT_WORK")
        self.assertEqual(self.snap(unsent, with_git=True), before)

        held = self.ensure("gamma")
        proc = self.start_holder(held)
        self.addCleanup(self.stop, proc)
        held_before = self.snap(held, with_git=True)
        res = self.remove(held)
        self.assertEqual(res["answer"].get("code"), "PROCESS_HOLDS_FILES", msg=f"{res}")
        self.assertEqual(self.snap(held, with_git=True), held_before)

        clean = self.bulk_alpha("alpha")
        self.stopped_request(clean, "first")
        marked = json.loads((clean / ".leafcutter" / "workspace.json").read_text(encoding="utf-8"))
        self.assertEqual(marked.get("state"), "clearing", msg="the control was not marked once its checks passed")

    def test_started_clearing_whose_line_of_work_moved_is_checked_normally(self):
        # covers: BO-4300e-2-ix
        # angle: boundary
        """AC-1: after a stop (the repository untouched, so still readable) a new commit is made on the
        line of work, so it differs from the commit recorded in the marker. The repeat without a token
        does not honour the marker: the normal check applies and the answer is UNSENT_WORK naming the
        full 40-character identifier of the new commit, with the folder unchanged."""
        ws = self.bulk_alpha("alpha")
        self.stopped_request(ws, "first")
        marker = json.loads((ws / ".leafcutter" / "workspace.json").read_text(encoding="utf-8"))
        self.assertEqual(marker.get("state"), "clearing", msg=f"nothing for the guard to guard: {marker}")
        sha = self.commit_unsent(ws, "after-the-stop.txt", "committed after the stop\n")
        before = self.snap(ws, with_git=True)
        res = self.repeat(ws)
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        self.assertIn(sha, (res["answer"].get("unsent") or {}).get("commits", []), msg=f"{res['answer']}")
        self.assertEqual(self.snap(ws, with_git=True), before)


if __name__ == "__main__":
    unittest.main()
