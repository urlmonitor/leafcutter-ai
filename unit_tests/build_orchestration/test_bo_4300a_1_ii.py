"""
MODULE: test_bo_4300a_1_ii
GOAL: Red-first behavioural tests for BO-4300a-1-ii -- a ready workspace made
    for a ticket states where that ticket is inside the workspace.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against a real bare hub and a real shared project in a temp directory.
    No mock of git, no import of the maker, no grep of its source.
    Fixture helpers are shared with test_bo_4300a_1 (_bo4300a1_helpers.py).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import build_world, git_ok, run_maker

TICKET_REL = "tickets/TICKET-20260925-demo.md"
TICKET_BYTES = (b"---\nstatus: todo\n---\n# demo ticket\r\nbody line with CRLF\r\n"
                b"unique-marker-4300a1ii\n")
EDITED_BYTES = TICKET_BYTES + b"edited only in the main copy\n"
FORBIDDEN_FIELDS = ("ticket_path_final", "ticket_path_new")
TICKET_FIELDS = ("ticket_path_in_worktree", "ticket_path_in_worktree_posix")

_WORLDS = []


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _new_world():
    world = build_world(_scripts_dir())
    _WORLDS.append(world)
    return world


def tearDownModule():  # noqa: N802
    for world in _WORLDS:
        world.holder.cleanup()


def _push_ticket_to_hub(world, content: bytes) -> None:
    """Commit the ticket on the hub's main from a second clone, then pull it
    into the project so the main copy holds it too."""
    seed2 = world.base / "seed2"
    git_ok(world.base, world.env, "clone", str(world.hub), str(seed2))
    target = seed2 / TICKET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    git_ok(seed2, world.env, "add", "-A")
    git_ok(seed2, world.env, "commit", "-m", "add demo ticket")
    git_ok(seed2, world.env, "push", "origin", "HEAD:main")
    git_ok(world.project, world.env, "pull", "--ff-only", "origin", "main")


def _ensure(world, slug: str, ticket: str | None, cwd: Path | None = None,
            repo_root: bool = True, kind: str = "ticket"):
    argv = ["ensure", "--kind", kind, "--slug", slug]
    if ticket is not None:
        argv += ["--ticket", ticket]
    if repo_root:
        argv += ["--repo-root", str(world.project)]
    return run_maker(world, argv, cwd=cwd)


def _landing(world) -> Path:
    return world.project.parent / "worktrees"


@pytest.mark.shared_layout_reader
class TestBo4300a1ii(unittest.TestCase):
    def test_ready_answer_states_ticket_location_inside_the_workspace(self):
        # covers: BO-4300a-1-ii
        # angle: criterion
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        main_copy = world.project / TICKET_REL
        # absolute path, asked from a folder outside the project
        done, answer = _ensure(world, "demo-abs", str(main_copy), cwd=world.elsewhere)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "ok", answer)
        ws = Path(answer["workspace_path"])
        self.assertEqual(answer["ticket_path_in_worktree"], str(ws / "tickets" / "TICKET-20260925-demo.md"))
        self.assertEqual(answer["ticket_path_in_worktree_posix"],
                         (ws / "tickets" / "TICKET-20260925-demo.md").as_posix())
        # project-relative path, asked from inside the project's tickets folder
        # (relative to the project, never to cwd)
        done2, answer2 = _ensure(world, "demo-rel", TICKET_REL, cwd=world.project / "tickets",
                                 repo_root=False)
        self.assertEqual(done2.returncode, 0, done2.stderr[-1500:])
        ws2 = Path(answer2["workspace_path"])
        self.assertEqual(answer2["ticket_path_in_worktree"],
                         str(ws2 / "tickets" / "TICKET-20260925-demo.md"))
        self.assertEqual(answer2["ticket_path_in_worktree_posix"],
                         (ws2 / "tickets" / "TICKET-20260925-demo.md").as_posix())
        # control: two pieces of work, two distinct stated locations
        self.assertNotEqual(answer["ticket_path_in_worktree"], answer2["ticket_path_in_worktree"])

    def test_stated_ticket_location_holds_the_requested_tickets_content(self):
        # covers: BO-4300a-1-ii
        # angle: real_artifact
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        main_copy = world.project / TICKET_REL
        done, answer = _ensure(world, "demo-content", str(main_copy))
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        stated = Path(answer["ticket_path_in_worktree"])
        self.assertTrue(stated.is_file() and not stated.is_symlink(), stated)
        self.assertEqual(stated.read_bytes(), main_copy.read_bytes())
        self.assertEqual(stated.read_bytes(), TICKET_BYTES)
        # control: the stated file is a real copy, not the main copy itself
        self.assertNotEqual(os.path.realpath(stated), os.path.realpath(main_copy))

    def test_answer_never_presents_a_location_outside_the_workspace_as_the_ticket(self):
        # covers: BO-4300a-1-ii
        # angle: boundary
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        main_copy = world.project / TICKET_REL
        done, answer = _ensure(world, "demo-inside", str(main_copy))
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        ws = os.path.realpath(answer["workspace_path"])
        for key in TICKET_FIELDS:
            value = answer[key]
            self.assertTrue(os.path.realpath(value).startswith(ws + os.sep), (key, value))
            self.assertNotEqual(os.path.realpath(value), os.path.realpath(main_copy), key)
        for key in FORBIDDEN_FIELDS:
            self.assertNotIn(key, answer)

    def test_ticket_absent_from_the_base_never_yields_an_ok_answer(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        world = _new_world()
        local_only = world.project / TICKET_REL
        local_only.parent.mkdir(parents=True, exist_ok=True)
        local_only.write_bytes(TICKET_BYTES)  # present in the main copy only, never pushed
        done, answer = _ensure(world, "demo-absent", str(local_only))
        self.assertEqual(done.returncode, 2, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("code"), "TICKET_NOT_ON_BASE")
        self.assertEqual(answer.get("reason"), "absent")
        self.assertEqual(answer.get("ticket_path"), str(local_only))
        for key in (*TICKET_FIELDS, "workspace_path"):
            self.assertNotIn(key, answer)
        landing = _landing(world)
        leftovers = sorted(p.name for p in landing.iterdir()) if landing.exists() else []
        self.assertEqual(leftovers, [], "refusal left a folder or INCOMPLETE remnant")
        # the stub build never ran: it would have left an install in some workspace
        self.assertEqual(
            [p for p in world.base.rglob("install_marker.txt")], [])
        # control: the refused request left the main copy untouched
        self.assertEqual(local_only.read_bytes(), TICKET_BYTES)

    def test_ticket_that_differs_from_the_base_is_refused_not_on_base(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        main_copy = world.project / TICKET_REL
        main_copy.write_bytes(EDITED_BYTES)  # edited, not pushed
        done, answer = _ensure(world, "demo-differs", str(main_copy))
        self.assertEqual(done.returncode, 2, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("code"), "TICKET_NOT_ON_BASE")
        self.assertEqual(answer.get("reason"), "differs")
        for key in (*TICKET_FIELDS, "workspace_path"):
            self.assertNotIn(key, answer)
        landing = _landing(world)
        leftovers = sorted(p.name for p in landing.iterdir()) if landing.exists() else []
        self.assertEqual(leftovers, [])
        # compare raw bytes (the text-mode git() helper would turn CRLF into LF)
        on_hub = subprocess.run(  # noqa: S603
            ["git", "show", f"main:{TICKET_REL}"], cwd=str(world.hub), env=world.env,
            capture_output=True, check=False)
        self.assertEqual(on_hub.returncode, 0, on_hub.stderr)
        self.assertEqual(on_hub.stdout, TICKET_BYTES)
        self.assertEqual(main_copy.read_bytes(), EDITED_BYTES)

    def test_ticket_fields_absent_without_ticket_request_and_on_every_refusal(self):
        # covers: BO-4300a-1-ii
        # angle: seam
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        # ok ensure without --ticket
        done, plain = _ensure(world, "demo-plain", None)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(plain.get("status"), "ok", plain)
        for key in TICKET_FIELDS:
            self.assertNotIn(key, plain)
        # OCCUPIED refusal with --ticket: a plain folder sits where the workspace goes
        occupied_ws = Path(plain["workspace_path"])
        shutil.rmtree(occupied_ws)
        occupied_ws.mkdir()
        (occupied_ws / "someone-elses-file.txt").write_text("not a workspace\n", encoding="utf-8")
        done2, refused = _ensure(world, "demo-plain", str(world.project / TICKET_REL))
        self.assertNotEqual(done2.returncode, 0)
        self.assertEqual(refused.get("status"), "refused", refused)
        self.assertEqual(refused.get("code"), "OCCUPIED")
        for key in TICKET_FIELDS:
            self.assertNotIn(key, refused)

    def test_resumed_workspace_without_the_ticket_is_refused_and_kept(self):
        # covers: BO-4300a-1-ii
        # angle: failure
        world = _new_world()
        done, plain = _ensure(world, "demo-resume-absent", None)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        ws = Path(plain["workspace_path"])
        _push_ticket_to_hub(world, TICKET_BYTES)  # pushed AFTER the workspace was made
        done2, answer = _ensure(world, "demo-resume-absent", str(world.project / TICKET_REL))
        self.assertEqual(done2.returncode, 2, done2.stderr[-1500:])
        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("code"), "TICKET_NOT_ON_BASE")
        self.assertEqual(answer.get("reason"), "absent")
        for key in (*TICKET_FIELDS, "workspace_path"):
            self.assertNotIn(key, answer)
        # control: the pre-existing workspace is never cleared by the refusal
        self.assertTrue((ws / ".leafcutter-workspace.json").is_file())

    def test_resumed_workspace_ticket_committed_on_the_line_is_ok_with_the_lines_bytes(self):
        # covers: BO-4300a-1-ii
        # angle: boundary
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        main_copy = world.project / TICKET_REL
        done, first = _ensure(world, "demo-resume-line", str(main_copy))
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        ws = Path(first["workspace_path"])
        # a phase agent appends a sign-off and commits it on the resumed line
        (ws / TICKET_REL).write_bytes(EDITED_BYTES)
        git_ok(ws, world.env, "add", TICKET_REL)
        # the workspace's rejecting hook guards agent commits; this is test setup
        git_ok(ws, world.env, "commit", "--no-verify", "-m", "sign-off comment")
        done2, answer = _ensure(world, "demo-resume-line", str(main_copy))
        self.assertEqual(done2.returncode, 0, done2.stderr[-1500:])
        self.assertEqual(answer.get("status"), "ok", answer)
        self.assertEqual(Path(answer["ticket_path_in_worktree"]).read_bytes(), EDITED_BYTES)
        # control: the main copy was never touched or copied over the line's bytes
        self.assertEqual(main_copy.read_bytes(), TICKET_BYTES)

    def test_ticket_with_scratch_kind_is_a_usage_error(self):
        # covers: BO-4300a-1-ii
        # angle: boundary
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        done, answer = _ensure(world, "demo-scratch", str(world.project / TICKET_REL),
                               kind="scratch")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(answer.get("code"), "USAGE", answer)
        for key in (*TICKET_FIELDS, "workspace_path"):
            self.assertNotIn(key, answer)
        # control: the same request without --ticket is not a usage error
        _done, plain = _ensure(world, "demo-scratch", None, kind="scratch")
        self.assertNotEqual(plain.get("code"), "USAGE", plain)

    def test_bo_4300a_1_ii_reachable_from_entry_point(self):
        # covers: BO-4300a-1-ii
        # angle: reachability
        # entry point: `python <install>/scripts/worktree.py ensure --ticket ...` (CLI via subprocess)
        world = _new_world()
        _push_ticket_to_hub(world, TICKET_BYTES)
        done, answer = _ensure(world, "demo-reach", str(world.project / TICKET_REL))
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        stated = Path(answer["ticket_path_in_worktree"])
        # the answer is consumed: the stated location is where a caller reads the ticket
        self.assertEqual(stated.read_bytes(), TICKET_BYTES)
        located, found = run_maker(
            world, ["locate", "--path", answer["workspace_path"], "--repo-root", str(world.project)])
        self.assertEqual(located.returncode, 0, located.stderr[-1500:])
        self.assertTrue(str(stated).startswith(found["workspace_path"] + os.sep))
        # control: the same request without --ticket carries no ticket location
        _done, no_ticket = _ensure(world, "demo-reach", None)
        for key in TICKET_FIELDS:
            self.assertNotIn(key, no_ticket)


if __name__ == "__main__":
    unittest.main()
