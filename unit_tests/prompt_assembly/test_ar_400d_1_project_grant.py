"""AR-400d-1 / AR-400d-1-i -- a grant marked ``provided_by: project`` reaches the specialist when the
project has the ability, is never rescued by a project copy when UNmarked, survives rebuilds, and
sql-coder declares postgres / sql-test this way (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400d-1.yaml and AR-400d-1-i.yaml (AR-400d-1-ii is already done, with its own tests).
Every e2e test is a real ``build.py --target-dir <project>`` over a copied package inside a scratch
consumer project (see ``_ar400_3b_fixtures``); builds are cached per scenario, and the tests that
rebuild take a private ``fresh`` copy, declared ``shared_layout_mutator``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402

SCRIPTS = F.REPO_ROOT / "scripts"
HOOK_DIR = F.REPO_ROOT / "templates" / "scripts" / "commit_guardian"
SIGNOFF_CONDITION = "When invoked with a ticket_path, load signoff to record your phase sign-off on the ticket."


def _load_hook_sync():
    """The commit hook's own copy of the declaration parser (deployed alone; never imports scripts/)."""
    spec = importlib.util.spec_from_file_location("_agent_ability_sync_under_test", HOOK_DIR / "_agent_ability_sync.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMarkedGrantDelivery(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_marked_grant_present_in_project_area_is_delivered_and_passes(self):
        # covers: AR-400d-1
        # angle: deployed
        """The project's .leafcutter/skills holds postgres; probe-coder grants it ``provided_by:
        project`` and says 'Apply the `postgres` skill'. The build passes with no finding about
        postgres, and probe-coder's compiled abilities row for postgres is the PROJECT's copy and is
        marked as supplied by the project (in every platform root)."""
        b = G.built("marked_present")
        self.assertEqual(G.finding_lines(b.out, "probe-coder", "postgres"), [], b.out[-1500:])
        self.assertEqual(b.rc, 0, b.out[-1500:])
        for root, text in G.compiled(b.sc.project, "probe-coder").items():
            rows = G.ability_rows(text, "postgres")
            self.assertEqual(len(rows), 1, f"{root}: postgres rows {rows}")
            self.assertIn(G.PROJECT_MARK, rows[0], "row must carry the project copy's description")
            self.assertRegex(rows[0].lower(), r"project", f"{root}: row not marked as project-supplied: {rows[0]}")

    @pytest.mark.shared_layout_mutator
    def test_unmarked_grant_to_unshipped_ability_fails_as_nonexistent(self):
        # covers: AR-400d-1
        # angle: discrimination
        # must_catch: unmarked grants still resolve in the project-local area (today's _resolve fallback)
        """Same project (it HAS .leafcutter/skills/postgres), marking removed: the build fails with
        'ability does not exist' for probe-coder / postgres, because the package does not ship it."""
        b = G.built("unmarked_present")
        self.assertEqual(len(F.of_kind(b.out, F.NONEXIST, "postgres", "probe-coder")), 1, b.out[-1500:])
        self.assertNotEqual(b.rc, 0, "an unmarked grant to an unshipped ability must stop the build")

    def test_transform_hook_keeps_provided_by_on_skills_invoked(self):
        # covers: AR-400d-1
        # angle: seam
        # must_catch: the hook's copy of normalize_declared drops provided_by
        """The real transform hook over a package copy regenerates probe-coder's skills_invoked from
        its frontmatter (the registry copy starts EMPTY) and the entry carries ``provided_by:
        project``; and the hook's normalised entries equal ``agent_ability_verdict.normalize_entries``
        for the same frontmatter (the scripts/ parser every other surface uses)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = H.make_slice(tmp)
            F.plant(root, "probe-coder", [G.POSTGRES_BODY], grants=(G.marked("postgres"),), registry_grants=())
            cp = subprocess.run([sys.executable, str(HOOK_DIR / "transform_agent_registry.py"), "--package-root", str(root)],
                                capture_output=True, text=True, timeout=300, check=False)
            self.assertEqual(cp.returncode, 0, cp.stderr[-600:])
            reg = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))
            entry = next(a for a in reg["agents"] if a["id"] == "probe-coder")
            granted = [e for e in entry["skills_invoked"] if e["skill_id"] == "postgres"]
            self.assertEqual(len(granted), 1, entry["skills_invoked"])
            self.assertEqual(granted[0].get("provided_by"), "project")
        raw = yaml.safe_load(yaml.safe_dump([G.marked("postgres"), "signoff", G.marked("sql-test", "conditional") | {"condition": "x"}]))
        sys.path.insert(0, str(SCRIPTS))
        from agent_ability_verdict import normalize_entries  # noqa: PLC0415

        self.assertEqual(_load_hook_sync().normalize_declared(raw), normalize_entries(raw),
                         "the hook's parser and the scripts/ parser disagree")
        self.assertEqual(normalize_entries(raw)[0].get("provided_by"), "project", "the shared parser dropped the marking")

    @pytest.mark.shared_layout_mutator
    def test_project_ability_survives_an_ordinary_rebuild(self):
        # covers: AR-400d-1
        # angle: failure
        # must_catch: --clean removes the marked project ability as a stale artifact (KI-BP-009)
        """Build the scratch project, rebuild without --clean, then WITH --clean: after each,
        .leafcutter/skills/postgres/SKILL.md is present and byte-identical."""
        sc = G.fresh("marked_present")
        rc, out = G.build(sc)
        self.assertEqual(rc, 0, out[-1200:])
        original = G.project_bytes(sc.project, "postgres")
        for extra in ((), ("--clean",)):
            rc, out = G.build(sc, *extra)
            self.assertEqual(rc, 0, f"build {extra} failed: {out[-1200:]}")
            self.assertEqual(G.project_bytes(sc.project, "postgres"), original, f"build {extra} changed the project ability")


class TestSqlCoderDeclaration(unittest.TestCase):
    def test_sql_coder_declares_postgres_and_sql_test_as_project_supplied(self):
        # covers: AR-400d-1-i
        # angle: real_artifact
        """The real templates/agents/sql-coder.md frontmatter grants postgres and sql-test, each
        ``provided_by: project``, and still grants signoff with its prior condition."""
        text = (F.REPO_ROOT / "templates" / "agents" / "sql-coder.md").read_text(encoding="utf-8")
        skills = {e["skill_id"]: e for e in yaml.safe_load(text[3:text.find("\n---", 3)])["skills"]}
        for sid in ("postgres", "sql-test"):
            self.assertEqual(skills.get(sid, {}).get("provided_by"), "project", f"{sid} is not marked project-supplied")
        self.assertEqual(skills["signoff"].get("condition"), SIGNOFF_CONDITION)
        self.assertEqual(skills["signoff"].get("mode"), "conditional")

    @pytest.mark.shared_layout_mutator
    def test_scratch_consumer_without_them_builds_and_reports_each_once(self):
        # covers: AR-400d-1-i
        # angle: deployed
        """Build the real package into a scratch consumer with an empty .leafcutter/skills: the build
        passes, the informational 'project-supplied ... not found' line appears exactly once for
        postgres and once for sql-test, and no 'does not exist' / 'not granted' finding names sql-coder."""
        b = G.built("real_empty")
        self.assertEqual(b.rc, 0, b.out[-1500:])
        for sid in ("postgres", "sql-test"):
            lines = G.info_lines(b.out, "sql-coder", sid, r"not found")
            self.assertEqual(len(lines), 1, f"{sid}: expected one informational line, got {lines}")
        self.assertEqual(F.about(b.out, "sql-coder"), [], "no refusing finding may name sql-coder")


if __name__ == "__main__":
    unittest.main()
