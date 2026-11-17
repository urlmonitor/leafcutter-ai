"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
AC: BO-4300a-2 (IT0 as amended by A5) -- a work identity is always a valid, single-segment line-of-work name.
Real-subprocess proof against the DEPLOYED maker (real temp repos and hub, no git mock).

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/06, BO-4300a-2]: Created the red baseline for A5
  (safe slugs; empty result is USAGE exit 64 and writes nothing). (#EPIC-WorkspaceMakerHardening/06)
====================================================================
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project, run_maker
from unit_tests.build_orchestration._bo_4300a_2_probe import deployed_identity_probe
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

SLUG_CASES = [("a..b", "a.b"), (".hidden", "hidden"), ("x.lock", "x"), ("v1.2", "v1.2"), ("-a-", "a"),
              ("a...b", "a.b"), ("x.lock.lock", "x")]

RESERVED = ["con", "NUL", "aux", "com1", "lpt9", "con.txt", "Prn", "COM9.log"]


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def _refs(repo: Path) -> str:
    return subprocess.run(["git", "for-each-ref", "--format=%(refname) %(objectname)"], cwd=str(repo),
                          capture_output=True, text=True, env=_isolated_git_env(), check=True).stdout


class TestSafeSlugs(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300a2s-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.fx = make_project(Path(self._tmp.name))

    def test_dot_only_or_empty_identity_is_usage_and_writes_nothing(self):
        # covers: BO-4300a-2
        # angle: deployed
        """A5: --slug '..', '...' and '' each answer error/USAGE, exit 64, naming the identity; nothing is written."""
        project, hub, landing = self.fx["project"], self.fx["hub"], self.fx["landing_place"]
        hub_before, project_before = _refs(hub), _refs(project)
        for raw in ("..", "...", ""):
            with self.subTest(slug=raw):
                res = run_maker(["ensure", "--kind", "feature", "--slug", raw], project)
                ans = res["answer"]
                self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("error", "USAGE", 64), ans)
                self.assertIn("feature", str(ans.get("message", "")), ans)  # names the identity (kind, raw slug)
                if raw:
                    self.assertIn(raw, str(ans.get("message", "")), ans)
                self.assertNotIn("workspace_path", ans)
                self.assertEqual(_tree(landing), [], "nothing may be written to the landing place")
                self.assertEqual(_refs(hub), hub_before)
                self.assertEqual(_refs(project), project_before)

    def test_slug_rules_give_one_valid_ref_segment(self):
        # covers: BO-4300a-2
        # angle: boundary
        """A5: slugify maps a..b/.hidden/x.lock/v1.2/-a- to a.b/hidden/x/v1.2/a; each is one valid ref segment."""
        raws = [r for r, _ in SLUG_CASES]
        got = deployed_identity_probe(f"import json\nprint(json.dumps([wi_module.slugify(r) for r in {raws!r}]))")
        self.assertEqual(got, [e for _, e in SLUG_CASES])
        for slug in got:
            with self.subTest(slug=slug):
                self.assertNotIn("/", slug)
                proc = subprocess.run(["git", "check-ref-format", "--branch", f"feature/{slug}"], capture_output=True,
                                      text=True, env=_isolated_git_env())
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unsalvageable_input_has_no_default_slug(self):
        # covers: BO-4300a-2
        # angle: failure
        """A5: no 'workspace' fallback -- slugify of an empty-normalising input is empty, never 'workspace'."""
        got = deployed_identity_probe("import json\nprint(json.dumps([wi_module.slugify(r) for r in ['..', '', '.lock']]))")
        self.assertEqual(got, ["", "", ""])

    def test_underscore_maps_to_hyphen_and_alone_is_empty(self):
        # covers: BO-4300a-2
        # angle: boundary
        """`_` becomes '-': a_b gives a-b; '_' alone normalises to empty (USAGE at resolve)."""
        got = deployed_identity_probe("import json\nprint(json.dumps([wi_module.slugify(r) for r in ['a_b', '_', '__x__']]))")
        self.assertEqual(got, ["a-b", "", "x"])

    def test_non_ascii_letters_are_dropped_current_behaviour(self):
        # covers: BO-4300a-2
        # angle: boundary
        """Pinned current behaviour: non-ASCII letters are dropped, cafe-with-accent gives caf."""
        got = deployed_identity_probe("import json\nprint(json.dumps([wi_module.slugify('caf\\u00e9')]))")
        self.assertEqual(got, ["caf"])

    def test_windows_reserved_device_names_are_usage_and_write_nothing(self):
        # covers: BO-4300a-2
        # angle: failure
        """A reserved device name as the slug's name part (any case, with or without extension) is USAGE on every OS."""
        project, hub, landing = self.fx["project"], self.fx["hub"], self.fx["landing_place"]
        hub_before, project_before = _refs(hub), _refs(project)
        for raw in RESERVED:
            with self.subTest(slug=raw):
                res = run_maker(["ensure", "--kind", "feature", "--slug", raw], project)
                ans = res["answer"]
                self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("error", "USAGE", 64), ans)
                self.assertNotIn("workspace_path", ans)
                self.assertEqual(_tree(landing), [])
                self.assertEqual(_refs(hub), hub_before)
                self.assertEqual(_refs(project), project_before)

    def test_reserved_name_lookalikes_are_still_accepted(self):
        # covers: BO-4300a-2
        # angle: boundary
        """Control row: names that merely contain or extend a device name (console, com10, nul-x) stay valid."""
        got = deployed_identity_probe("import json\nprint(json.dumps([wi_module.slugify(r) for r in ['console', 'com10', 'nul-x']]))")
        self.assertEqual(got, ["console", "com10", "nul-x"])

    def test_overlong_slug_is_usage_naming_the_limit_and_not_truncated(self):
        # covers: BO-4300a-2
        # angle: boundary
        """64 characters pass; 65 are USAGE naming the limit (64); nothing is written and no truncation happens."""
        project, hub, landing = self.fx["project"], self.fx["hub"], self.fx["landing_place"]
        hub_before = _refs(hub)
        res = run_maker(["ensure", "--kind", "feature", "--slug", "a" * 65], project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("error", "USAGE", 64), ans)
        self.assertIn("64", str(ans.get("message", "")), ans)
        self.assertNotIn("workspace_path", ans)
        self.assertEqual(_tree(landing), [])
        self.assertEqual(_refs(hub), hub_before)
        # the limit is measured after normalisation: 65 raw chars that normalise to 64 are fine
        got = deployed_identity_probe(
            "import json\nprint(json.dumps(wi_module.resolve('feature', '-' + 'a' * 64 + '-').slug))")
        self.assertEqual(got, "a" * 64)


if __name__ == "__main__":
    unittest.main()
