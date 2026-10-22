"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_2.py
AC: BO-4300a-2 -- The same piece of work is always recognised as the same workspace
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: templates/scripts/worktree_identity.py (one naming table, legacy aliases, hub-line
resolution) does not exist yet; today EPIC-X, epic/x and "X" give three different workspaces.

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300a-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    TICKET_CONTENT,
    TICKET_REL,
    git,
    hub_heads,
    hub_refs,
    is_ancestor,
    landing_entries,
    maker,
    new_project,
    push_hub_line,
    push_ticket_to_hub,
    same,
)

ALIASES = [  # (kind, legacy spelling, canonical slug) -- the table's declared per-kind aliases
    ("epic", "EPIC-Xray", "xray"),
    ("ac", "ac-authoring/xray", "xray"),
    ("fastlane", "fast-lane/xray", "xray"),
    ("ticket", "feature/xray", "xray"),
]


class TestBO4300a2(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300a2-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        fx = new_project(Path(self._tmp.name))
        self.project, self.hub, self.landing = fx["project"], fx["hub"], fx["landing_place"]

    def ensure(self, slug: str, kind: str = "epic", extra: list[str] | None = None) -> dict:
        return maker(["ensure", "--kind", kind, "--slug", slug, *(extra or [])], self.project)

    def ready_workable_with_two_commits(self) -> tuple[Path, list[str]]:
        ans = self.ensure("files-stay-workable")["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        ws = Path(ans["workspace_path"])
        shas = []
        for i in range(2):
            (ws / f"work-{i}.txt").write_text(f"work {i}\n", encoding="utf-8", newline="\n")
            git(["add", "-A"], ws)
            git(["commit", "-q", "-m", f"work {i}"], ws)
            shas.append(git(["rev-parse", "HEAD"], ws))
        return ws, shas

    def test_same_epic_requested_via_other_spelling_returns_existing_location(self):
        # covers: BO-4300a-2
        # angle: criterion
        """Feature-skill spelling, display title and build spelling all answer ok with the one location."""
        ws, _ = self.ready_workable_with_two_commits()
        for spelling in ("EPIC-FilesStayWorkable", "files-stay-workable", "Files Stay Workable"):
            ans = self.ensure(spelling)["answer"]
            self.assertEqual(ans.get("status"), "ok", (spelling, ans))
            self.assertTrue(same(ans["workspace_path"], ws), (spelling, ans))

    def test_one_workspace_and_one_line_of_work_exist_after_rerequests(self):
        # covers: BO-4300a-2
        # angle: criterion
        """Exactly one folder at the landing place and exactly one branch in the workspace."""
        ws, _ = self.ready_workable_with_two_commits()
        self.ensure("EPIC-FilesStayWorkable")
        self.ensure("files-stay-workable")
        entries = [Path(e).as_posix() for e in landing_entries(self.landing)
                   if len(Path(e).parts) <= 2 and (self.landing / e).is_dir()]  # folders only: the workspace holds files
        self.assertEqual(entries, ["epic", "epic/files-stay-workable"])
        lines = [b for b in git(["branch", "--format=%(refname:short)"], ws).split() if b != "main"]  # clone's base branch is not a line of work
        self.assertEqual(lines, ["epic/files-stay-workable"])
        self.assertEqual(hub_heads(self.hub), ["main"])

    def test_existing_commits_survive_rerequests(self):
        # covers: BO-4300a-2
        # angle: criterion
        """Both commits stay on the workspace's line, shas unchanged, after both re-requests."""
        ws, shas = self.ready_workable_with_two_commits()
        for spelling in ("EPIC-FilesStayWorkable", "files-stay-workable"):
            ans = self.ensure(spelling)["answer"]
            self.assertTrue(same(ans.get("workspace_path", "?"), ws), ans)  # answered from THE workspace, not a twin
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], ws), "epic/files-stay-workable")
        self.assertEqual(git(["rev-list", "--reverse", "origin/main..HEAD"], ws).split(), shas)

    def test_distinct_epic_gets_its_own_location(self):
        # covers: BO-4300a-2
        # angle: boundary
        """Files Stay Portable is its own workspace at the exact canonical location; Workable is untouched."""
        ws, _ = self.ready_workable_with_two_commits()
        ans = self.ensure("Files Stay Portable")["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertFalse(same(ans["workspace_path"], ws), ans)
        self.assertTrue(same(ans["workspace_path"], self.landing / "epic" / "files-stay-portable"), ans)
        self.assertTrue(ws.is_dir())

    def test_legacy_epic_spelling_lands_on_the_canonical_epic_workspace(self):
        # covers: BO-4300a-2
        # angle: criterion
        """EPIC-FilesStayPortable -> kind epic, slug files-stay-portable, branch epic/files-stay-portable."""
        ans = self.ensure("EPIC-FilesStayPortable")["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual((ans["kind"], ans["slug"], ans["branch"]), ("epic", "files-stay-portable", "epic/files-stay-portable"))
        self.assertTrue(same(ans["workspace_path"], self.landing / "epic" / "files-stay-portable"), ans)
        again = self.ensure("epic/files-stay-portable")["answer"]
        self.assertEqual(again.get("status"), "ok", again)
        self.assertTrue(same(again["workspace_path"], ans["workspace_path"]), again)

    def test_every_declared_legacy_alias_resolves_to_its_canonical_identity(self):
        # covers: BO-4300a-2
        # angle: boundary
        """Each legacy spelling answers the canonical <kind>/<slug> and the canonical spelling's location."""
        for kind, legacy, slug in ALIASES:
            with self.subTest(kind=kind, legacy=legacy):
                canon = self.ensure(slug, kind=kind)["answer"]
                self.assertEqual(canon.get("status"), "ok", canon)
                self.assertEqual((canon["kind"], canon["slug"], canon["branch"]), (kind, slug, f"{kind}/{slug}"))
                ans = self.ensure(legacy, kind=kind)["answer"]
                self.assertEqual(ans.get("status"), "ok", ans)
                self.assertEqual((ans["kind"], ans["slug"], ans["branch"]), (kind, slug, f"{kind}/{slug}"))
                self.assertTrue(same(ans["workspace_path"], canon["workspace_path"]), (canon, ans))

    def test_legacy_line_on_the_hub_is_resumed_never_twinned(self):
        # covers: BO-4300a-2
        # angle: failure
        """A hub line held only as EPIC-FilesStayPortable is resumed on that branch, not twinned."""
        shas = push_hub_line(self.project, "EPIC-FilesStayPortable", commits=2)
        legacy_before = git(["rev-parse", "refs/heads/EPIC-FilesStayPortable"], self.hub)
        ans = self.ensure("files-stay-portable")["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(ans.get("line_of_work"), "resumed", ans)
        self.assertEqual(ans.get("branch"), "EPIC-FilesStayPortable", ans)
        self.assertEqual((ans["kind"], ans["slug"]), ("epic", "files-stay-portable"))
        ws = Path(ans["workspace_path"])
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], ws), "EPIC-FilesStayPortable")
        for sha in shas:
            self.assertTrue(is_ancestor(sha, "HEAD", ws), sha)
        self.assertEqual(hub_heads(self.hub), ["EPIC-FilesStayPortable", "main"])
        self.assertEqual(git(["rev-parse", "refs/heads/EPIC-FilesStayPortable"], self.hub), legacy_before)

    def test_two_spellings_with_lines_on_the_hub_are_refused_ambiguous_line(self):
        # covers: BO-4300a-2
        # angle: failure
        """Both spellings carry commits on the hub: AMBIGUOUS_LINE names both, nothing is created or moved."""
        push_hub_line(self.project, "EPIC-FilesStayPortable", commits=1)
        push_hub_line(self.project, "epic/files-stay-portable", commits=1)
        before = hub_refs(self.hub)
        res = self.ensure("files-stay-portable")
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "AMBIGUOUS_LINE", 2), ans)
        self.assertEqual(sorted(ans.get("lines") or []), ["EPIC-FilesStayPortable", "epic/files-stay-portable"], ans)
        self.assertNotIn("workspace_path", ans)
        self.assertEqual(landing_entries(self.landing), [])
        self.assertEqual(hub_refs(self.hub), before)

    def test_ticket_06_reachable_from_entry_point(self):
        # covers: BO-4300a-2
        # angle: reachability
        """CLI via subprocess: ensure --kind ticket --slug <s> --ticket <path> --repo-root <project>."""
        push_ticket_to_hub(self.project)
        res = maker(["ensure", "--kind", "ticket", "--slug", "feature/Demo-Reach", "--ticket",
                     str(self.project / TICKET_REL), "--repo-root", str(self.project)], self.project.parent)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), ans)
        self.assertEqual((ans["kind"], ans["slug"]), ("ticket", "demo-reach"), ans)  # identity step consumed the alias
        stated = Path(ans["ticket_path_in_worktree"])
        self.assertEqual(stated.read_text(encoding="utf-8"), TICKET_CONTENT)
        self.assertTrue(same(stated, Path(ans["workspace_path"]) / TICKET_REL))


if __name__ == "__main__":
    unittest.main()
