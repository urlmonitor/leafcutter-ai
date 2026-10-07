"""
MODULE: unit_tests/ac_store/test_bo_2600a_5_expects_from_edges.py
GOAL: A prerequisite declared only through ``expects_from`` becomes a real edge
      in the epic's dependency graph and is written as the producer's
      ``NN_``-prefixed epic ticket filename.
COVERS: BO-2600a-5

Every test drives the real ``goal_to_epic --ids`` generator against a temporary
AC store (never the repo's own store or tickets/) and asserts on the real
generated ticket files. The fixtures mirror DK-400a-1 / DK-400a-3: a consumer
whose ``depends_on`` holds only its structural parent (outside the id set) and
whose real prerequisite is named only in ``expects_from``.

Titles are colon-free on purpose: a colon in an AC title breaks the epic folder
name on Windows (a separate, known defect).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GOAL_TO_EPIC = _REPO_ROOT / "scripts" / "goal_to_epic.py"
_GUARD_DIR = _REPO_ROOT / "templates" / "hooks"
_AC_STORE_SCRIPTS = _REPO_ROOT / "scripts" / "ac_store"
for _p in (str(_GUARD_DIR), str(_AC_STORE_SCRIPTS), str(_REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ticket_frontmatter_guard as guard  # noqa: E402


def _record(ac_id: str, **extra: object) -> dict:
    rec = {
        "id": ac_id,
        "title": f"Fixture {ac_id} for the expects_from edge test",
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


def _dk400a_shape(prefix: str, producer_n: int, consumer_n: int) -> list[dict]:
    """Parent L2 plus a producer and a consumer shaped like DK-400a-1 / -3."""
    parent = f"{prefix}a"
    producer = f"{parent}-{producer_n}"
    consumer = f"{parent}-{consumer_n}"
    return [
        _record(parent, level="L2", covered_by=[producer, consumer]),
        _record(producer),
        _record(consumer, depends_on=[parent], expects_from=_expects(producer)),
    ]


def _generate(root: Path, records: list[dict], ids: list[str]) -> tuple[Path, str]:
    """Run the real generator. Returns (epic folder, stdout + stderr)."""
    store = _write_store(root, records)
    inbox = root / "tickets" / "00_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable, str(_GOAL_TO_EPIC),
            "--ids", ",".join(ids),
            "--store-root", str(store),
            "--inbox-dir", str(inbox),
            "--approved-only",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300, cwd=str(root),
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"generation failed (vacuity guard)\n{out}"
    epics = sorted((inbox / "epics").glob("EPIC-*"))
    assert len(epics) == 1, f"expected one epic folder, got {epics}"
    return epics[0], out


def _frontmatter(ticket: Path) -> dict:
    text = ticket.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    return yaml.safe_load(text[3:end]) or {}


def _ticket_for(epic: Path, ac_id: str) -> Path:
    for ticket in sorted(epic.glob("[0-9][0-9]_*.md")):
        if _frontmatter(ticket).get("source_ac") == ac_id:
            return ticket
    names = sorted(p.name for p in epic.iterdir())
    raise AssertionError(f"no ticket for {ac_id} in {names}")


class TestExpectsFromEdges(unittest.TestCase):
    """BO-2600a-5 - expects_from edges get epic-prefixed depends_on."""

    def test_expects_from_edge_gets_epic_prefixed_depends_on(self) -> None:
        # covers: BO-2600a-5
        # angle: criterion
        """AC-2: consumer depends_on == [producer NN_ filename]; real guard accepts it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = _dk400a_shape("ZZEF-100", 1, 3)
            epic, out = _generate(root, records, ["ZZEF-100a-1", "ZZEF-100a-3"])
            producer = _ticket_for(epic, "ZZEF-100a-1")
            consumer = _ticket_for(epic, "ZZEF-100a-3")
            fm = _frontmatter(consumer)

            self.assertRegex(producer.name, r"^\d{2}_")
            self.assertEqual([producer.name], fm.get("depends_on"), out)
            for entry in fm["depends_on"]:
                self.assertRegex(entry, r"^\d{2}_")
                self.assertTrue((epic / entry).is_file(), entry)
            errors = [e for e in guard.validate(fm, consumer) if "depends_on" in e]
            self.assertEqual([], errors)

    def test_producer_sorting_after_consumer_is_built_first(self) -> None:
        # covers: BO-2600a-5
        # angle: boundary
        """AC-3: edge only via expects_from, producer id sorts after consumer."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = _dk400a_shape("ZZEF-200", 2, 1)  # consumer -1 sorts first
            epic, out = _generate(root, records, ["ZZEF-200a-1", "ZZEF-200a-2"])
            producer = _ticket_for(epic, "ZZEF-200a-2")
            consumer = _ticket_for(epic, "ZZEF-200a-1")

            self.assertLess(producer.name[:2], consumer.name[:2])
            self.assertEqual([producer.name], _frontmatter(consumer).get("depends_on"))
            self.assertNotIn("from depends_on or expects_from", out)

    def test_stale_depends_on_replaced_with_epic_list_or_empty(self) -> None:
        # covers: BO-2600a-5
        # angle: failure
        """AC-4: a loose inbox name never survives; no in-set prereq gives []."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [
                _record("ZZEF-300a", covered_by=["ZZEF-300a-1", "ZZEF-300a-2"]),
                _record("ZZEF-300a-1", depends_on=["ZZEF-300a"],
                        expects_from=_expects("ZZEF-300b-9")),  # out of set
                _record("ZZEF-300a-2"),
            ]
            # A loose ticket for the out-of-set producer, which the generator
            # would translate to its unprefixed, unresolvable name.
            loose = root / "tickets" / "00_inbox" / "TICKET-LOOSE-300b-9.md"
            loose.parent.mkdir(parents=True)
            loose.write_text(
                "---\n"
                + yaml.safe_dump({"title": "loose", "source_ac": "ZZEF-300b-9"})
                + "---\n\n# loose\n",
                encoding="utf-8",
            )
            epic, out = _generate(root, records, ["ZZEF-300a-1", "ZZEF-300a-2"])
            for ac_id in ("ZZEF-300a-1", "ZZEF-300a-2"):
                ticket = _ticket_for(epic, ac_id)
                deps = _frontmatter(ticket).get("depends_on")
                self.assertEqual([], deps, f"{ac_id}\n{out}")
                self.assertNotIn("TICKET-LOOSE", ticket.read_text(encoding="utf-8"))

    def test_master_plan_table_shows_prefixed_name(self) -> None:
        # covers: BO-2600a-5
        # angle: real_artifact
        """AC-5: Master_Plan Depends On column names the producer NN_ file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = _dk400a_shape("ZZEF-400", 1, 3)
            epic, _ = _generate(root, records, ["ZZEF-400a-1", "ZZEF-400a-3"])
            producer = _ticket_for(epic, "ZZEF-400a-1")
            consumer = _ticket_for(epic, "ZZEF-400a-3")
            plan = (epic / "Master_Plan.md").read_text(encoding="utf-8")
            rows = [ln for ln in plan.splitlines() if consumer.name in ln]
            self.assertTrue(rows, plan)
            self.assertIn(producer.name, rows[0])

    def test_epic_index_and_generator_agree_on_prerequisites(self) -> None:
        # covers: BO-2600a-5
        # angle: seam
        """AC-1 / AC-6: epic index and generator resolve the same in-set prereqs."""
        from _gtfa_store import _build_ticket_depends_on
        from epic_dependencies import _build_depends_on_index

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = _dk400a_shape("ZZEF-500", 1, 3)
            records.append(_record("ZZEF-500a-4", depends_on=["ZZEF-500a"],
                                   expects_from=_expects("ZZEF-500a-1")))
            store = _write_store(root, records)
            leaves = ["ZZEF-500a-1", "ZZEF-500a-3", "ZZEF-500a-4"]
            tickets = root / "tickets"
            tickets.mkdir()
            for ac_id in leaves:  # one real ticket file per in-set AC
                (tickets / f"TICKET-{ac_id}.md").write_text(
                    "---\n"
                    + yaml.safe_dump({"title": ac_id, "source_ac": ac_id})
                    + "---\n",
                    encoding="utf-8",
                )
            name_to_ac = {f"TICKET-{a}.md": a for a in leaves}
            index = _build_depends_on_index(store)
            by_id = {r["id"]: r for r in records}

            for ac_id in leaves:
                from_index = {d for d in index.get(ac_id, []) if d in leaves}
                names = _build_ticket_depends_on(by_id[ac_id], ac_id, tickets)
                from_generator = {name_to_ac[n] for n in names}
                self.assertEqual(from_generator, from_index, ac_id)
            self.assertEqual(
                {"ZZEF-500a-1"}, {d for d in index["ZZEF-500a-3"] if d in leaves}
            )


if __name__ == "__main__":
    unittest.main()
