"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_iv.py
AC: BO-4300f-3-iv (A9b, option R) -- retiring an old workspace reports the ignored files it deletes.
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

An old-style workspace holding nothing unsent, whose folder also holds files version control is told to
ignore (`.env.local` and a folder `build/`). The retired entry carries `ignored_removed`, listed from git's own
ignored-file listing with a wholly ignored folder named as that folder (`build/`), and `--preview` lists
the same paths before anything is deleted. A control workspace with nothing ignored reports none.

The `.gitignore` is committed to the project and pushed to the hub BEFORE the workspaces are made, so it is
not itself unsent work (an untracked or unpushed .gitignore would make the workspace "unsent", not retired).

Real subprocess against the DEPLOYED maker; no mock of git; no raw linked-checkout command spelled here.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3-iv]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    legacy_worktree,
)
from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase, norm

_IGNORED = [".env.local", "build/"]


class TestRetireReportsIgnored(MigrateCase):
    def ignore_rules_on_the_hub(self) -> None:
        with open(self.project / ".gitignore", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(".env.local\nbuild/\n")
        self.git(["add", ".gitignore"])
        self.git(["commit", "-q", "-m", "ignore local files"])
        self.git(["push", "-q", "origin", "main"])

    def fill_ignored(self, folder: Path) -> None:
        (folder / ".env.local").write_bytes(b"SECRET=1\n")
        (folder / "build" / "sub").mkdir(parents=True)
        (folder / "build" / "out.o").write_bytes(b"object\n")
        (folder / "build" / "sub" / "deep.o").write_bytes(b"deeper\n")

    def retired_entry(self, answer: dict[str, Any], legacy: Path) -> dict[str, Any]:
        entry = next((e for e in answer["retired"] if norm(e["path"]) == norm(legacy)), None)
        self.assertIsNotNone(entry, msg=f"{legacy} was not retired: {answer}")
        return entry

    def test_retiring_reports_the_ignored_files_it_deletes(self):
        # covers: BO-4300f-3-iv
        # angle: deployed
        """AC-4 (A9b): a legacy workspace with nothing unsent but ignored `.env.local` and `build/` (two
        files below it): `--preview` first lists ignored_removed ['.env.local', 'build/'] on the retired entry
        and deletes nothing; the real run removes the folder and its retired entry lists the same paths. A
        control workspace with nothing ignored is retired with no ignored_removed paths.
        Must implement: list the ignored content from `git status --ignored --porcelain=v1 -z` before the
        deletion, a wholly ignored folder named as that folder, on the entry and in the preview.
        WRONG VERSIONS caught: no field; every file below build/ listed instead of the folder; the preview
        omitting the field or deleting; a plain workspace reporting invented paths."""
        self.ignore_rules_on_the_hub()
        legacy = legacy_worktree(self.project, "feature/ig")
        plain = legacy_worktree(self.project, "feature/plain")
        self.fill_ignored(legacy)

        preview = self.migrate_ok(preview=True)
        self.assertEqual(sorted(self.retired_entry(preview, legacy).get("ignored_removed", [])), _IGNORED,
                         msg=f"{preview}")
        self.assertTrue(legacy.exists(), msg="the preview deleted the folder")
        self.assertTrue((legacy / "build" / "out.o").exists(), msg="the preview deleted ignored content")

        answer = self.migrate_ok()
        self.assertFalse(legacy.exists(), msg="the retired folder is still there")
        self.assertEqual(sorted(self.retired_entry(answer, legacy).get("ignored_removed", [])), _IGNORED,
                         msg=f"{answer}")
        self.assertEqual(self.retired_entry(answer, plain).get("ignored_removed", []), [], msg=f"{answer}")
        self.assertFalse(plain.exists())
