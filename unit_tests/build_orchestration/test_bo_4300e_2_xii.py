"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_xii.py
AC: BO-4300e-2-xii -- A record-less folder whose leftover repository file names this project's shared
project is identified as half-cleared (refused with a token); every other record-less folder stays
NOT_FOUND and untouched.

Real-subprocess proof against the DEPLOYED maker. The evidence bytes are real: a workspace is made
by `ensure`, `git fetch origin` writes its real .git/FETCH_HEAD, and its real .git/config is read;
the leftover folder is then built from those bytes (with the shared project's URL swapped for
blog's, or spelled differently, where a case needs it). Folders sit at <landing>/feature/<slug>
(the shared KIND constant stands in for ac/omega). Helpers come from test_bo_4300e_2.py and _2_ix.py.

DECISION HISTORY
====================================================================
- 2026-11-03 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-xii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project
from unit_tests.build_orchestration.test_bo_4300e_2 import KIND
from unit_tests.build_orchestration.test_bo_4300e_2_ix import StopCase

FILES = ["CLAUDE.md", "README.md"]


def fetch_form(url: str) -> bytes:
    """*url* as git writes it into FETCH_HEAD: without a trailing slash or .git suffix."""
    return url.rstrip("/").removesuffix(".git").encode()


def config_form(url: str) -> str:
    """*url* as git writes it into .git/config: backslashes escaped (Windows paths)."""
    return url.replace("\\", "\\\\")


class OmegaCase(StopCase):
    def setUp(self) -> None:
        super().setUp()
        self.hub_url = self.git(["remote", "get-url", "origin"], self.project)
        source = self.ensure("source")
        self.git(["fetch", "origin"], source)
        self.fetch_head = (source / ".git" / "FETCH_HEAD").read_bytes()
        self.config = (source / ".git" / "config").read_text(encoding="utf-8")
        self.assertIn(fetch_form(self.hub_url), self.fetch_head, msg="fixture: FETCH_HEAD does not name the hub")
        self.assertIn(config_form(self.hub_url), self.config, msg="fixture: config does not name the hub")
        self.assertEqual(self.remove(source)["answer"].get("status"), "ok", msg="fixture: source not cleared")
        blog = make_project(self.tmp / "blog-world")
        self.blog_url = self.git(["remote", "get-url", "origin"], blog["project"])

    def folder(self, slug: str, git: dict[str, bytes] | None = None, parent: Path | None = None,
               git_is_file: bool = False) -> Path:
        """A record-less folder holding CLAUDE.md and README.md, with *git* files inside a .git folder."""
        folder = (parent or self.landing / KIND) / slug
        folder.mkdir(parents=True)
        for name in FILES:
            (folder / name).write_text(f"{name}\n", encoding="utf-8", newline="\n")
        if git_is_file:
            (folder / ".git").write_text("gitdir: nowhere\n", encoding="utf-8", newline="\n")
        elif git is not None:
            (folder / ".git").mkdir()
            for name, data in git.items():
                (folder / ".git" / name).write_bytes(data)
        return folder

    def config_naming(self, url: str) -> bytes:
        text = re.sub(r"(url\s*=\s*)\S+", lambda m: m.group(1) + url, self.config, count=1)
        self.assertIn(url, text, msg="fixture: the url was not swapped")
        return text.encode("utf-8")

    def omega(self, slug: str = "omega") -> Path:
        return self.folder(slug, {"FETCH_HEAD": self.fetch_head})

    def blog_fetch_head(self) -> bytes:
        data = self.fetch_head.replace(fetch_form(self.hub_url), fetch_form(self.blog_url))
        self.assertNotEqual(data, self.fetch_head, msg="fixture: the url was not swapped")
        return data

    def request(self, folder: Path, token: str | None = None) -> dict[str, Any]:
        return self.repeat(folder, token=token)

    def identified(self, folder: Path) -> dict[str, Any]:
        """The refusal of an identified folder (UNSENT_WORK, exit 2, files, token); the folder unchanged."""
        before = self.snap(folder, with_git=True)
        res = self.request(folder)
        answer = res["answer"]
        self.assertNotEqual(answer.get("code"), "NOT_FOUND", msg=f"{folder.name}: {res}")
        self.assertEqual((answer.get("status"), answer.get("code")), ("refused", "UNSENT_WORK"), msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        self.assertEqual(self.snap(folder, with_git=True), before, msg=f"{folder.name}: the folder changed")
        return answer

    def not_found(self, folder: Path, token: str | None = None, files: bool = False) -> None:
        before = self.snap(folder, with_git=True)
        res = self.request(folder, token)
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code")), ("refused", "NOT_FOUND"),
                         msg=f"{folder}: {res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{folder}: {res}")
        self.assertNotIn("discard_token", answer, msg=f"{folder}: {answer}")
        if files:
            self.assertEqual(answer.get("files"), FILES, msg=f"{folder}: {answer}")
        self.assertTrue(folder.is_dir(), msg=f"{folder} was deleted")
        self.assertEqual(self.snap(folder, with_git=True), before, msg=f"{folder}: the folder changed")


class TestRecordLessFolderIdentification(OmegaCase):
    def test_record_less_folder_with_hub_named_leftover_is_half_cleared_not_not_found(self):
        # covers: BO-4300e-2-xii
        # angle: discrimination
        """AC-1: a record-less folder at a workspace position of shop's landing place, holding CLAUDE.md,
        README.md and a .git folder whose only file is FETCH_HEAD ending in shop's hub URL, is refused
        UNSENT_WORK (exit 2), never NOT_FOUND, saying the workspace was half-cleared and its remaining
        files cannot be checked against the shared project. unsent.files is exactly [CLAUDE.md, README.md]
        (nothing under .git), unsent.commits is empty, a 32-hex token is returned and the folder is
        identical. Variants take the URL from .git/config (remote origin) with a trailing slash, a
        file:// spelling, or the .git suffix toggled: not a difference."""
        folders = [self.omega()]
        hub_path = Path(self.hub_url)
        spellings = {"slash": self.hub_url + "/",
                     "suffix": self.hub_url[:-4] if self.hub_url.endswith(".git") else self.hub_url + ".git"}
        if hub_path.is_absolute():
            spellings["uri"] = hub_path.as_uri()
        for name, url in spellings.items():
            folders.append(self.folder(f"omega-{name}", {"config": self.config_naming(url)}))
        for folder in folders:
            answer = self.identified(folder)
            low = str(answer.get("message", "")).lower()
            self.assertTrue("half-cleared" in low or "half cleared" in low, msg=f"{folder.name}: {answer}")
            self.assertIn("cannot be checked", low, msg=f"{folder.name}: {answer}")
            self.assertEqual((answer.get("unsent") or {}).get("files"), FILES, msg=f"{folder.name}: {answer}")
            self.assertEqual((answer.get("unsent") or {}).get("commits"), [], msg=f"{folder.name}: {answer}")
            token = answer.get("discard_token")
            self.assertTrue(isinstance(token, str) and len(token) == 32, msg=f"{folder.name}: {answer}")
            self.assertEqual(set(token) - set("0123456789abcdef"), set(), msg=f"{token!r}")

    def test_remove_cli_reaches_the_record_less_identification(self):
        # covers: BO-4300e-2-xii
        # angle: reachability
        """AC-1: the real CLI (worktree.py remove --path --repo-root) on the first-run folder, with the
        shared project folder moved away, answers exit 2 with UNSENT_WORK. No network is needed to
        identify the folder, and git is never run in it (its .git has no HEAD, so a git call would
        fail or climb to a parent repository)."""
        folder = self.omega()
        self.assertFalse((folder / ".git" / "HEAD").exists())
        self.hub_moved_away()
        try:
            res = self.request(folder)
        finally:
            self.hub_back()
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "UNSENT_WORK"),
                         msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")

    def test_token_finishes_the_identified_folder_including_its_repository_leftover(self):
        # covers: BO-4300e-2-xii
        # angle: real_artifact
        """AC-1: the request repeated with the returned token is ok, discarded.files is
        [CLAUDE.md, README.md], and nothing of the folder remains at its location, the leftover
        .git/FETCH_HEAD included (read back from disk with lexists on the folder and on the file)."""
        folder = self.omega()
        token = self.identified(folder).get("discard_token")
        self.assertTrue(token, msg="no token to present")
        res = self.request(folder, token)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        self.assertEqual((res["answer"].get("discarded") or {}).get("files"), FILES, msg=f"{res['answer']}")
        self.assertFalse(os.path.lexists(folder / ".git" / "FETCH_HEAD"), msg="the leftover FETCH_HEAD remains")
        self.assertFalse(os.path.lexists(folder), msg="something of the folder remains")

    def test_other_hub_and_no_repository_folders_stay_not_found_and_untouched(self):
        # covers: BO-4300e-2-xii
        # angle: discrimination
        """AC-1: a leftover naming another shared project (blog) and a folder with no repository folder
        are refused NOT_FOUND with files [CLAUDE.md, README.md], no discard_token, and are identical
        afterwards. Further cases, each identical afterwards: mixed evidence (one URL equal and one
        different), no URL at all, an unparsable FETCH_HEAD, a .git that is a file, a folder outside
        shop's landing place, and one at a depth other than kind/slug. Control, in the same test: the
        hub-named leftover IS identified, so 'not found' is not a maker that identifies nothing."""
        self.identified(self.omega())
        self.not_found(self.folder("omega-blog", {"FETCH_HEAD": self.blog_fetch_head()}), files=True)
        self.not_found(self.folder("omega-bare"), files=True)
        mixed = self.fetch_head + self.blog_fetch_head()
        cases = [
            self.folder("omega-mixed", {"FETCH_HEAD": mixed}),
            self.folder("omega-nourl", {"FETCH_HEAD": b"nothing to see here\n"}),
            self.folder("omega-garbage", {"FETCH_HEAD": b"\xff\xfe\x00\x01 not text \x80\x81"}),
            self.folder("omega-gitfile", git_is_file=True),
            self.folder("omega", {"FETCH_HEAD": self.fetch_head}, parent=self.tmp / "elsewhere" / KIND),
            self.folder("omega", {"FETCH_HEAD": self.fetch_head}, parent=self.landing / KIND / "group"),
        ]
        for folder in cases:
            self.not_found(folder)

    def test_token_from_the_first_run_is_never_honoured_on_the_not_found_path(self):
        # covers: BO-4300e-2-xii
        # angle: discrimination
        """AC-1: the token returned for the identified first-run folder is presented on the other-hub and
        the no-repository folders (same file names, so the same set could match). Each request is refused
        NOT_FOUND again with the files listed and no new token, and the folder is identical. The same token presented on a second
        identified folder with the same file names and contents is refused with a different token and
        leaves that folder alone. Catches a NOT_FOUND path that honours any token and a token bound to
        the file names only (not to the folder)."""
        token = self.identified(self.omega()).get("discard_token")
        self.assertTrue(token, msg="no token to present")
        blog = self.folder("omega-blog", {"FETCH_HEAD": self.blog_fetch_head()})
        bare = self.folder("omega-bare")
        for folder in (blog, bare):
            self.not_found(folder, token, files=True)
            self.assertEqual(sorted(p.name for p in folder.iterdir() if p.is_file()), FILES)
        # The token is bound to the folder too: a second IDENTIFIED folder with the same file names and the
        # same contents is a different folder, so the first one's token must not clear it.
        twin = self.omega("omega-twin")
        before = self.snap(twin, with_git=True)
        res = self.request(twin, token)
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "UNSENT_WORK"),
                         msg=f"the token of another folder cleared this one: {res}")
        self.assertNotEqual(res["answer"].get("discard_token"), token, msg=f"{res['answer']}")
        self.assertTrue(twin.is_dir(), msg="the twin was deleted with another folder's token")
        self.assertEqual(self.snap(twin, with_git=True), before)


if __name__ == "__main__":
    unittest.main()
