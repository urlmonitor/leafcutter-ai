"""
MODULE: unit_tests/ac_store/test_tkt_017_epic_depends_on_resolves.py
GOAL: Every dependency a generated epic's ticket declares must name a file that
      exists in the epic folder — on BOTH generation routes.
COVERS: TKT-017

WHY THE ASSERTION IS "THE FILE EXISTS" RATHER THAN "THE NAME HAS A PREFIX"

Checking for an `NN_` prefix would pass on a ticket that names
`99_TICKET-does-not-exist.md`, and would fail if the numbering scheme ever
changes. What actually has to be true is that the dependency resolves — that is
also precisely what check-doc-frontmatter enforces at commit time, so the test
and the gate agree on the same fact rather than on two proxies for it.

BOTH ROUTES ARE COVERED because the defect was a fix applied to one of them and
not back-ported to the other. A test that exercised only the route that happens
to work would have reported this whole class of bug as absent.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GOAL_TO_EPIC = _REPO_ROOT / "scripts" / "goal_to_epic.py"

_GOAL_ID = "ZZDEP-900"
_LEAF_IDS = ("ZZDEP-900a", "ZZDEP-900b", "ZZDEP-900c")


def _record(ac_id: str) -> dict:
    return {
        "id": ac_id,
        "title": f"Fixture {ac_id} for the depends_on resolution test",
        "component": "ticket-creation",
        "components": ["ticket_creation_pipeline"],
        "level": "L2",
        "status": "active",
        "req_status": "draft",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "criteria": (
            "Given a fixture AC\nWhen a ticket is generated\nThen it exists\n"
        ),
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


def _seed_store(root: Path) -> Path:
    """Write a goal plus a 3-long dependency chain. Returns the store root."""
    store = root / "docs" / "acceptance-criteria" / "ticket-creation"
    store.mkdir(parents=True)

    goal = _record(_GOAL_ID)
    goal.update(level="L1", covered_by=list(_LEAF_IDS))
    (store / f"{_GOAL_ID}.yaml").write_text(
        yaml.safe_dump(goal, sort_keys=False), encoding="utf-8"
    )

    # a <- b <- c, so at least two tickets carry a dependency and one carries two.
    chain = {
        _LEAF_IDS[0]: [_GOAL_ID],
        _LEAF_IDS[1]: [_GOAL_ID, _LEAF_IDS[0]],
        _LEAF_IDS[2]: [_GOAL_ID, _LEAF_IDS[0], _LEAF_IDS[1]],
    }
    for leaf_id, deps in chain.items():
        rec = _record(leaf_id)
        rec["depends_on"] = deps
        (store / f"{leaf_id}.yaml").write_text(
            yaml.safe_dump(rec, sort_keys=False), encoding="utf-8"
        )
    return root / "docs" / "acceptance-criteria"


def _epic_folder(inbox: Path) -> Path:
    epics = sorted((inbox / "epics").glob("EPIC-*"))
    assert len(epics) == 1, f"expected exactly one epic folder, got {epics}"
    return epics[0]


def _declared_dependencies(ticket: Path) -> list[str]:
    """Read a ticket's depends_on entries out of its YAML frontmatter."""
    text = ticket.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    fm = yaml.safe_load(text[3:end]) if end != -1 else {}
    raw = (fm or {}).get("depends_on") or []
    return [str(entry) for entry in raw]


class TestEpicDependsOnResolves(unittest.TestCase):
    """TKT-017 — declared dependencies must name files that exist."""

    def _assert_every_dependency_resolves(self, epic: Path) -> None:
        unresolved: list[str] = []
        checked = 0
        for ticket in sorted(epic.glob("*.md")):
            if ticket.name == "Master_Plan.md":
                continue
            for dep in _declared_dependencies(ticket):
                checked += 1
                if not (epic / dep).is_file():
                    unresolved.append(f"{ticket.name} -> {dep}")

        self.assertGreater(
            checked,
            0,
            "no dependencies were examined at all — the fixture chain should "
            "produce at least three. A pass here would be vacuous.",
        )
        self.assertEqual(
            [],
            unresolved,
            "Ticket dependencies name files that do not exist in the epic "
            "folder. Assembly renames each ticket with an NN_ prefix; these "
            "references were left pointing at the pre-move names, so "
            "check-doc-frontmatter refuses the commit.\n"
            + "\n".join(unresolved)
            + f"\n\nfiles present: {sorted(p.name for p in epic.glob('*.md'))}",
        )

    def test_ac_route_dependencies_resolve(self) -> None:
        # covers: TKT-017
        # angle: real_artifact
        """The --ac route (the default, and what /build-ac drives).

        RED before the fix: run() never calls _translate_ticket_depends_on().
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_root = _seed_store(root)
            inbox = root / "tickets" / "00_inbox"
            inbox.mkdir(parents=True)

            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable, str(_GOAL_TO_EPIC),
                    "--ac", _GOAL_ID,
                    "--store-root", str(store_root),
                    "--inbox-dir", str(inbox),
                    "--approved-only",
                ],
                capture_output=True, text=True, timeout=300,
            )
            self.assertEqual(
                0, proc.returncode,
                f"generation failed, so the assertion below would be vacuous.\n"
                f"stdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self._assert_every_dependency_resolves(_epic_folder(inbox))

    def test_ids_route_dependencies_resolve(self) -> None:
        # covers: TKT-017
        # angle: criterion
        """The --ids route. Expected GREEN before the fix — it already calls the
        translation — and it is here so the pair proves the defect was
        route-specific rather than universal, and so a future change cannot fix
        one route by breaking the other."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_root = _seed_store(root)
            inbox = root / "tickets" / "00_inbox"
            inbox.mkdir(parents=True)

            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable, str(_GOAL_TO_EPIC),
                    "--ids", ",".join(_LEAF_IDS),
                    "--store-root", str(store_root),
                    "--inbox-dir", str(inbox),
                    "--approved-only",
                ],
                capture_output=True, text=True, timeout=300,
            )
            self.assertEqual(
                0, proc.returncode,
                f"generation failed, so the assertion below would be vacuous.\n"
                f"stdout={proc.stdout}\nstderr={proc.stderr}",
            )
            self._assert_every_dependency_resolves(_epic_folder(inbox))

    def tearDown(self) -> None:
        """Remove fixture tickets the assembly may have written outside tmp."""
        stray = _REPO_ROOT / "tickets" / "00_inbox"
        if not stray.is_dir():
            return
        for path in stray.glob(f"*{_GOAL_ID}*"):
            path.unlink(missing_ok=True)
        for leaf in _LEAF_IDS:
            for path in stray.glob(f"*{leaf}*"):
                path.unlink(missing_ok=True)
        for epic in stray.glob("epics/*ZZDEP*"):
            shutil.rmtree(epic, ignore_errors=True)
        for epic in stray.glob("epics/*Fixture*"):
            if re.search(r"ZZDEP|Fixture", epic.name):
                shutil.rmtree(epic, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
