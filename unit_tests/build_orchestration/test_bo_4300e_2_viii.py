"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_viii.py
AC: BO-4300e-2-viii -- Clearing ignores files that vanish while it deletes, and still names a file
that cannot be deleted.

Real-subprocess proof against the DEPLOYED maker. A `sitecustomize.py` on the maker process's
PYTHONPATH (the `extra_env` of `cli()`) wraps `os.unlink` / `os.rmdir`. It is deterministic (no
timing) and unprivileged on both platforms. The trigger is keyed on file NAMES (vanish_NNN.dat,
locked.bin) because on POSIX `shutil.rmtree` deletes by name relative to a directory descriptor, so
a full-path match would never fire. Workspaces use KIND "feature" (the shared helper's kind).
Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-26 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-viii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase

SITECUSTOMIZE = '''\
import os
import shutil
import sys

_real_unlink, _real_rmdir, _real_lstat, _real_chmod = os.unlink, os.rmdir, os.lstat, os.chmod
_whole = os.environ.get("VANISH_WORKSPACE", "")
_flaky = os.environ.get("FLAKY_NAME", "")
_vanish_dir = os.environ.get("VANISH_DIR", "")
_state = {"fired": False}


def _vanish_everything():
    """The program outside: delete every file, then the folder itself, with the real calls."""
    _state["fired"] = True
    with open(os.environ["FIRED_FLAG"], "w") as flag:
        flag.write("fired")
    for root, dirs, files in os.walk(_vanish_dir, topdown=False):
        for name in files:
            _real_unlink(os.path.join(root, name))
        for name in dirs:
            _real_rmdir(os.path.join(root, name))
    _real_rmdir(_vanish_dir)


def _name(path):
    return os.path.basename(os.fspath(path).rstrip("/\\\\"))


def _plain(path):
    text = os.fspath(path)
    long_prefix = chr(92) * 2 + "?" + chr(92)
    return os.path.normcase(os.path.normpath(text[4:] if text.startswith(long_prefix) else text))


def lstat(path, *args, **kwargs):
    """The folder vanishes at the moment rmtree first looks at it (rmtree's own call, not the maker's)."""
    from_rmtree = sys._getframe(1).f_code.co_filename.endswith("shutil.py")
    if _whole and not _state["fired"] and from_rmtree and _plain(path) == _plain(_whole):
        _state["fired"] = True
        with open(os.environ["FIRED_FLAG"], "w") as flag:
            flag.write("fired")
        shutil.rmtree(_whole, ignore_errors=True)
    return _real_lstat(path, *args, **kwargs)


def chmod(path, *args, **kwargs):
    """The file named FLAKY_NAME vanishes between the delete error and the read-only retry."""
    if _flaky and _name(path) == _flaky and os.path.lexists(path):
        _state["fired"] = True
        with open(os.environ["FIRED_FLAG"], "w") as flag:
            flag.write("fired")
        _real_unlink(path)
    return _real_chmod(path, *args, **kwargs)


def unlink(path, *args, **kwargs):
    name = _name(path)
    if _flaky and name == _flaky and not _state["fired"]:
        raise PermissionError(13, "read-only", os.fspath(path))
    if name == "locked.bin":
        raise PermissionError(13, "locked", os.fspath(path))
    if _vanish_dir and not _state["fired"] and name.startswith("vanish_") and os.path.isdir(_vanish_dir):
        _vanish_everything()
    return _real_unlink(path, *args, **kwargs)


def rmdir(path, *args, **kwargs):
    if _vanish_dir and not _state["fired"] and _name(path) == "tmp" and os.path.isdir(_vanish_dir):
        _vanish_everything()
    return _real_rmdir(path, *args, **kwargs)


os.lstat = lstat
os.chmod = chmod
os.unlink = unlink
os.remove = unlink
os.rmdir = rmdir
'''


class VanishCase(WorkspaceCase):
    def vanishing_alpha(self) -> tuple[Path, dict[str, str]]:
        """alpha with 200 files in build/tmp (excluded from git, so nothing is unsent) and the env that
        makes the maker's own deletion race a program removing them first."""
        ws = self.ensure("alpha")
        tmp_dir = ws / "build" / "tmp"
        tmp_dir.mkdir(parents=True)
        for i in range(200):
            (tmp_dir / f"vanish_{i:03d}.dat").write_text("x\n", encoding="utf-8", newline="\n")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("build/\n")
        self.fired = self.tmp / "vanish.fired"
        return ws, self.sitecustomize_env({"VANISH_DIR": str(tmp_dir), "FIRED_FLAG": str(self.fired)})

    def sitecustomize_env(self, extra: dict[str, str]) -> dict[str, str]:
        folder = self.tmp / "site"
        folder.mkdir(exist_ok=True)
        (folder / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8", newline="\n")
        return {"PYTHONPATH": str(folder), **extra}

    @staticmethod
    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [s for v in value.values() for s in VanishCase.strings(v)]
        if isinstance(value, list):
            return [s for v in value for s in VanishCase.strings(v)]
        return []


class TestVanishingAndLockedItems(VanishCase):
    def test_alpha_clears_when_items_vanish_during_deletion(self):
        # covers: BO-4300e-2-viii
        # angle: reachability
        """AC-1: the real CLI, with 200 files and then build/tmp itself vanishing under it mid-deletion
        (the real call then raises FileNotFoundError), still answers ok and nothing remains at the
        location. Catches a deletion that counts an item that no longer exists as a failure."""
        ws, extra_env = self.vanishing_alpha()
        res = self.remove(ws, extra_env=extra_env)
        self.assertTrue(self.fired.exists(), msg="fixture: the outside program never removed build/tmp")
        self.assertFalse((ws / "build" / "tmp").exists(), msg="fixture: build/tmp survived")
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        self.assertFalse(os.path.lexists(ws), msg="something of alpha remains")

    def test_workspace_vanishing_as_deletion_starts_still_answers_ok(self):
        # covers: BO-4300e-2-viii
        # angle: discrimination
        """AC-1: the whole workspace folder is removed by another program at the moment the maker's own
        deletion first looks at it (rmtree's lstat raises FileNotFoundError). The answer is ok and nothing
        remains. Control for the whole-folder case; the retry branch of the error handler is held by
        the next test."""
        ws = self.ensure("alpha")
        self.fired = self.tmp / "vanish.fired"
        env = self.sitecustomize_env({"VANISH_WORKSPACE": str(ws), "FIRED_FLAG": str(self.fired)})
        res = self.remove(ws, extra_env=env)
        self.assertTrue(self.fired.exists(), msg="fixture: the workspace never vanished under the deleter")
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        self.assertFalse(os.path.lexists(ws), msg="something of alpha remains")

    def test_item_vanishing_between_delete_error_and_retry_still_answers_ok(self):
        # covers: BO-4300e-2-viii
        # angle: discrimination
        """AC-1: flaky.bin first fails to delete (PermissionError), then vanishes before the maker's
        read-only retry reaches it (the retry's chmod raises FileNotFoundError). The answer is ok and
        nothing remains. Catches a retry that lets a vanished item escape as a failure."""
        ws = self.ensure("alpha")
        (ws / "flaky.bin").write_bytes(b"flaky\n")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("flaky.bin\n")
        self.fired = self.tmp / "vanish.fired"
        env = self.sitecustomize_env({"FLAKY_NAME": "flaky.bin", "FIRED_FLAG": str(self.fired)})
        res = self.remove(ws, extra_env=env)
        self.assertTrue(self.fired.exists(), msg="fixture: flaky.bin never reached the retry")
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        self.assertFalse(os.path.lexists(ws), msg="something of alpha remains")

    def test_vanished_build_tmp_items_are_not_named_as_failures(self):
        # covers: BO-4300e-2-viii
        # angle: criterion
        """AC-1: in the same race, no string in the answer names a path under build/tmp."""
        ws, extra_env = self.vanishing_alpha()
        res = self.remove(ws, extra_env=extra_env)
        self.assertTrue(res["answer"], msg=f"the maker gave no answer: {res}")
        self.assertTrue(self.fired.exists(), msg="fixture: the outside program never removed build/tmp")
        for text in self.strings(res["answer"]):
            self.assertNotIn("build/tmp", text.replace("\\", "/"), msg=f"{res['answer']}")
            self.assertNotIn("vanish_", text, msg=f"{res['answer']}")
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")

    def test_locked_item_still_fails_and_is_named(self):
        # covers: BO-4300e-2-viii
        # angle: discrimination
        """AC-1: beta holds locked.bin, which exists and raises PermissionError on every delete (so it
        cannot be a vanished item). The answer is not ok, names locked.bin, and the folder remains
        (the post-check still arbitrates). Bounded by the cli timeout, which catches an unbounded
        retry; the other wrong versions are one that ignores every error (answers cleared while
        locked.bin remains) and one that names no item."""
        ws = self.ensure("beta")
        (ws / "locked.bin").write_bytes(b"locked\n")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("locked.bin\n")
        res = self.remove(ws, extra_env=self.sitecustomize_env({}), timeout=60)
        self.assertNotEqual(res["answer"].get("status"), "ok", msg=f"a locked file was answered cleared: {res}")
        self.assertTrue((ws / "locked.bin").exists(), msg="fixture: locked.bin was deleted")
        self.assertTrue(any("locked.bin" in s for s in self.strings(res["answer"])),
                        msg=f"the answer does not name locked.bin: {res['answer']}")


if __name__ == "__main__":
    unittest.main()
