"""
MODULE: unit_tests/ac_store/test_bo_2600a_5_cycle_policy.py
GOAL: Epic ordering uses depends_on plus expects_from, except that a child's
      depends_on on its own structural parent yields when the parent's
      expects_from names that child. Any remaining cycle fails generation with
      a report naming every AC and every edge (field + parent-link flag).
COVERS: BO-2600a-5

Decision Kernel dec-46476988badbd5e6 (run run-e02f770927304a29, 2026-10-07).
Sibling of test_bo_2600a_5_expects_from_edges.py (kept separate so neither file
passes the 400-line ratchet). Every test drives the real ``goal_to_epic --ids``
generator as a subprocess against a temporary AC store, except the one seam
test that calls ``_build_depends_on_index`` directly.

Edge report contract the tests pin (owner requires prerequisite):
    ``<owner> -> <prerequisite> (<depends_on|expects_from>, parent-link: <true|false>)``
Titles are colon-free on purpose (a colon breaks the epic folder name on Windows).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GOAL_TO_EPIC = _REPO_ROOT / "scripts" / "goal_to_epic.py"
for _p in (str(_REPO_ROOT / "scripts" / "ac_store"), str(_REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _record(ac_id: str, **extra: object) -> dict:
    rec = {
        "id": ac_id,
        "title": f"Fixture {ac_id} for the cycle policy test",
        "component": "ticket-creation",
        "components": ["ticket_creation_pipeline"],
        "level": "L2",
        "status": "active",
        "req_status": "draft",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "criteria": "Given a fixture AC\nWhen a ticket is generated\nThen it exists\n",
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "change_target": "pipeline",
        "risk_surface": "internal",
        "origin_agent": "human user",
        "doc_links": [],
        "covered_by": [],
        "implemented_by": [],
        "amended_by": [],
        "superseded_by": None,
    }
    rec.update(extra)
    return rec


def _expects(producer: str) -> list[dict]:
    return [{"ac_id": producer, "contract": "fixture contract"}]


def _write_store(root: Path, records: list[dict]) -> Path:
    store = root / "docs" / "acceptance-criteria"
    folder = store / "ticket-creation"
    folder.mkdir(parents=True)
    for rec in records:
        (folder / f"{rec['id']}.yaml").write_text(
            yaml.safe_dump(rec, sort_keys=False), encoding="utf-8"
        )
    return store


def _run_ids(root: Path, records: list[dict], ids: list[str]):
    """Run the real generator. Returns (returncode, output, inbox)."""
    store = _write_store(root, records)
    inbox = root / "tickets" / "00_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable, str(_GOAL_TO_EPIC), "--ids", ",".join(ids),
            "--store-root", str(store), "--inbox-dir", str(inbox),
            "--approved-only",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300, cwd=str(root), env={**os.environ, "PYTHONUTF8": "1"},
    )
    return proc.returncode, proc.stdout + proc.stderr, inbox


def _generate_ok(root: Path, records: list[dict], ids: list[str]):
    code, out, inbox = _run_ids(root, records, ids)
    assert code == 0, f"generation failed\n{out}"
    epics = sorted((inbox / "epics").glob("EPIC-*"))
    assert len(epics) == 1, f"expected one epic folder, got {epics}"
    return epics[0], out


def _frontmatter(ticket: Path) -> dict:
    text = ticket.read_text(encoding="utf-8")
    return yaml.safe_load(text[3:text.find("\n---", 3)]) or {}


def _ticket_for(epic: Path, ac_id: str) -> Path:
    for ticket in sorted(epic.glob("[0-9][0-9]_*.md")):
        if _frontmatter(ticket).get("source_ac") == ac_id:
            return ticket
    raise AssertionError(f"no ticket for {ac_id} in {sorted(p.name for p in epic.iterdir())}")


class TestCyclePolicy(unittest.TestCase):
    """BO-2600a-5 - parent link yields; other cycles fail with a full report."""

    def assert_edge(self, msg: str, owner: str, prereq: str, field: str,
                    parent_link: bool) -> None:
        pattern = rf"{re.escape(owner)}\s*->\s*{re.escape(prereq)}\s*\(([^)]*)\)"
        found = re.search(pattern, msg)
        self.assertIsNotNone(found, f"edge {owner} -> {prereq} not reported\n{msg}")
        inner = found.group(1)
        other = "expects_from" if field == "depends_on" else "depends_on"
        self.assertIn(field, inner, msg)
        self.assertNotIn(other, inner, msg)
        flag = re.search(r"parent[-_ ]?link\W*(true|false)", inner, re.IGNORECASE)
        self.assertIsNotNone(flag, f"no parent-link flag on edge\n{msg}")
        self.assertEqual(str(parent_link).lower(), flag.group(1).lower(), msg)

    def assert_no_epic_written(self, inbox: Path) -> None:
        self.assertEqual([], sorted((inbox / "epics").glob("EPIC-*")))
        self.assertEqual([], sorted(inbox.rglob("*.md")))

    def test_ac7_parent_link_yields_child_built_first(self) -> None:
        # covers: BO-2600a-5
        # angle: reachability
        """AC-7: child depends_on parent + parent expects_from child -> child first."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [
                _record("ZZCP-610a", covered_by=["ZZCP-610a-1"],
                        expects_from=_expects("ZZCP-610a-1")),
                _record("ZZCP-610a-1", depends_on=["ZZCP-610a"]),
            ]
            epic, out = _generate_ok(root, records, ["ZZCP-610a", "ZZCP-610a-1"])
            child = _ticket_for(epic, "ZZCP-610a-1")
            parent = _ticket_for(epic, "ZZCP-610a")
            self.assertLess(child.name[:2], parent.name[:2], out)
            self.assertEqual([child.name], _frontmatter(parent).get("depends_on"))
            self.assertEqual([], _frontmatter(child).get("depends_on"))

    def test_ac7_yield_keeps_parent_link_when_parent_does_not_expect_child(self) -> None:
        # covers: BO-2600a-5
        # angle: discrimination
        """AC-7 narrowness (KI-ACD-021): no expects_from on the child -> parent first.

        P waits on a later-sorting producer W, so dropping the parent link in
        general would let C jump ahead of P.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [
                _record("ZZCP-620a", covered_by=["ZZCP-620a-1"],
                        expects_from=_expects("ZZCP-620z-1")),
                _record("ZZCP-620a-1", depends_on=["ZZCP-620a"]),
                _record("ZZCP-620z-1"),
            ]
            ids = ["ZZCP-620a", "ZZCP-620a-1", "ZZCP-620z-1"]
            epic, out = _generate_ok(root, records, ids)
            parent = _ticket_for(epic, "ZZCP-620a")
            child = _ticket_for(epic, "ZZCP-620a-1")
            self.assertLess(parent.name[:2], child.name[:2], out)

    def test_ac7_index_drops_yielded_parent_edge_only(self) -> None:
        # covers: BO-2600a-5
        # angle: seam
        """AC-7: _build_depends_on_index drops the yielded edge, keeps the rest."""
        from epic_dependencies import _build_depends_on_index

        with tempfile.TemporaryDirectory() as tmp:
            records = [
                _record("ZZCP-630a", expects_from=_expects("ZZCP-630a-1")),
                _record("ZZCP-630a-1", depends_on=["ZZCP-630a"]),
                _record("ZZCP-630b"),
                _record("ZZCP-630b-1", depends_on=["ZZCP-630b"]),
            ]
            index = _build_depends_on_index(_write_store(Path(tmp), records))
            self.assertNotIn("ZZCP-630a", index["ZZCP-630a-1"])
            self.assertIn("ZZCP-630a-1", index["ZZCP-630a"])  # expects_from kept
            self.assertIn("ZZCP-630b", index["ZZCP-630b-1"])  # parent link kept

    def test_ac8_sibling_cycle_fails_naming_both_edges(self) -> None:
        # covers: BO-2600a-5
        # angle: failure
        """AC-8: A depends_on B, B expects_from A (not parent/child) fails, full report."""
        a, b = "ZZCP-640a-1", "ZZCP-640b-1"
        with tempfile.TemporaryDirectory() as tmp:
            records = [_record(a, depends_on=[b]), _record(b, expects_from=_expects(a))]
            code, out, inbox = _run_ids(Path(tmp), records, [a, b])
            self.assertNotEqual(0, code, out)
            self.assert_edge(out, a, b, "depends_on", False)
            self.assert_edge(out, b, a, "expects_from", False)
            self.assert_no_epic_written(inbox)

    def test_ac8_cycle_through_out_of_set_ac_names_it(self) -> None:
        # covers: BO-2600a-5
        # angle: boundary
        """AC-8: X -> Z -> Y -> X where Z is not requested; Z and all edges named."""
        x, z, y = "ZZCP-650a-1", "ZZCP-650b-1", "ZZCP-650c-1"
        with tempfile.TemporaryDirectory() as tmp:
            records = [
                _record(x, depends_on=[z]),
                _record(z, depends_on=[y]),
                _record(y, expects_from=_expects(x)),
            ]
            code, out, inbox = _run_ids(Path(tmp), records, [x, y])
            self.assertNotEqual(0, code, out)
            self.assertIn(z, out)
            self.assert_edge(out, x, z, "depends_on", False)
            self.assert_edge(out, z, y, "depends_on", False)
            self.assert_edge(out, y, x, "expects_from", False)
            self.assert_no_epic_written(inbox)

    def test_ac8_expects_from_only_cycle_names_both_edges(self) -> None:
        # covers: BO-2600a-5
        # angle: failure
        """AC-8: A expects_from B and B expects_from A fails; both edges expects_from."""
        a, b = "ZZCP-660a-1", "ZZCP-660b-1"
        with tempfile.TemporaryDirectory() as tmp:
            records = [_record(a, expects_from=_expects(b)),
                       _record(b, expects_from=_expects(a))]
            code, out, inbox = _run_ids(Path(tmp), records, [a, b])
            self.assertNotEqual(0, code, out)
            self.assert_edge(out, a, b, "expects_from", False)
            self.assert_edge(out, b, a, "expects_from", False)
            self.assert_no_epic_written(inbox)


if __name__ == "__main__":
    unittest.main()
