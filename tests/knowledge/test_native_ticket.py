"""Ticket source metadata stays distinct from derived display and epic information."""

from datetime import date
import importlib
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return importlib.import_module("knowledge.native_types.ticket").extract(root)


def _write(root, path, metadata, body="# Ticket\n\nKeep this body.\n"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\n" + yaml.safe_dump(metadata) + "---\n" + body, encoding="utf-8")
    return target


def test_ticket_preserves_full_metadata_nested_shapes_dates_and_body(tmp_path):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    metadata = {
        "title": "Authored title",
        "status": "invalid",
        "components": ["finalize"],
        "created": date(2026, 9, 1),
        "last_updated": "2026-09-02",
        "depends_on": [],
        "type": "design_decision_ticket",
        "requires_adr": None,
        "requires_diagram": False,
        "agents": {"coder": {"status": "signed_off", "grandfathered": False}},
        "ac_traceability": [{"id": "FIN-10", "path": "docs/a.yaml"}],
        "ac_coverage": ["FIN-10"],
        "change_target": ["code", "docs"],
        "test_requirements": {
            "tests": [{"name": "test_a", "path": "tests/a.py", "coverage": "claim\ntext"}]
        },
        "future~/field": {"empty": {}, "list": [], "null": None},
        "documentation_required": True,
        "requires_documentation": ["reference"],
        "requires_documentation_verification": False,
        "merged_pr": 95,
    }
    body = "\n# Display heading is different\n\n---\nLiteral body\n"
    path = "tickets/99_done/EPIC-One/done/01_child.md"
    _write(tmp_path, path, metadata, body)
    (record,) = _extract(tmp_path)
    assert record.kind == "Ticket"
    assert record.native_id == record.source_path == path
    assert record.locator == ""
    assert record.title == "Authored title"
    assert record.metadata == metadata
    assert record.derived == {"body": body, "subtype": "ticket", "subtype_source": "default"}
    assert record.description == ""


def test_ticket_distinct_paths_and_epic_subtype_provenance(tmp_path):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    sources = {
        "tickets/00_inbox/EPIC-One/Master_Plan.md": {"epic_name": "One"},
        "tickets/00_inbox/EPIC-Two/Master_Plan.md": {"title": "Two", "type": "epic"},
        "tickets/00_inbox/EPIC-One/01_child.md": {"status": "todo"},
        "tickets/00_inbox/EPIC-Two/01_child.md": {"status": "done"},
        "tickets/00_inbox/unusual.md": {"type": "epic"},
    }
    for path, metadata in sources.items():
        _write(tmp_path, path, metadata)
    records = {record.native_id: record for record in _extract(tmp_path)}
    assert set(records) == set(sources)
    for path, metadata in sources.items():
        record = records[path]
        assert record.metadata == metadata
        assert record.derived["subtype"] == ("ticket" if "child" in path else "epic")
    assert records[next(iter(sources))].derived["subtype_source"] == "path_convention"
    assert records["tickets/00_inbox/unusual.md"].derived["subtype_source"] == "frontmatter.type"
    assert records[next(iter(sources))].title == "One"
    assert records[next(iter(sources))].derived["title_source"] == "frontmatter.epic_name"


def test_ticket_excludes_readme_generic_notes_and_missing_frontmatter(tmp_path):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _write(tmp_path, "tickets/README.md", {"type": "reference", "status": "active"})
    _write(tmp_path, "tickets/EPIC-One/readME.md", {"type": "epic", "source_ac": "A"})
    _write(
        tmp_path, "tickets/notes.md", {"title": "Notes", "type": "reference", "status": "active"}
    )
    _write(tmp_path, "docs/TICKET-unrelated.md", {"status": "todo"})
    missing = tmp_path / "tickets/TICKET-no-frontmatter.md"
    missing.write_text("# Just a note\n", encoding="utf-8")
    _write(tmp_path, "tickets/TICKET-valid.md", {"status": "open"})
    records = _extract(tmp_path)
    assert [record.native_id for record in records] == ["tickets/TICKET-valid.md"]
    _write(tmp_path, "tickets/TICKET-valid-two.md", {"status": "todo"})
    assert len(_extract(tmp_path)) == 2


def test_ticket_never_defaults_missing_fields_or_normalizes_historical_values(tmp_path):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    source = {"status": "open", "requires_adr": None, "type": "bugfix", "test_required": False}
    _write(tmp_path, "tickets/99_done/TICKET-old.md", source, "# Legacy heading\n")
    (record,) = _extract(tmp_path)
    assert record.metadata == source
    assert record.title == "Legacy heading"
    assert record.derived["title_source"] == "body.heading"
    assert record.derived["subtype"] == "ticket"


@pytest.mark.parametrize(
    "text", ["---\ntitle: x\n", "---\n[bad, mapping]\n---\n", "---\na: [\n---\n"]
)
def test_ticket_invalid_frontmatter_is_explicit_failure(tmp_path, text):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    path = tmp_path / "tickets/TICKET-bad.md"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        _extract(tmp_path)


def test_ticket_absent_store_returns_no_records(tmp_path):
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    assert _extract(tmp_path) == []


def test_ticket_real_store_preserves_every_frontmatter_field():
    # covers: KM-400a-1-vi
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    candidates = sorted(
        path for path in (root / "tickets").rglob("*.md") if path.name.lower() != "readme.md"
    )
    records = _extract(root)
    assert len(records) == len(candidates) == 1560
    assert len({record.native_id for record in records}) == len(records)
    by_path = {record.source_path: record for record in records}
    fields = set()
    expected_epics = set()
    for path in candidates:
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        assert lines[0].strip() == "---"
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        metadata = yaml.safe_load("".join(lines[1:end]))
        record = by_path[path.relative_to(root).as_posix()]
        assert record.metadata == metadata
        assert record.derived["body"] == "".join(lines[end + 1 :])
        fields.update(metadata)
        if metadata.get("type") == "epic" or (
            path.name.lower() == "master_plan.md"
            and any(part.startswith("EPIC-") for part in path.relative_to(root).parts[:-1])
        ):
            expected_epics.add(record.source_path)
    assert {"title", "status", "components", "source_ac"} <= fields
    assert expected_epics
    assert {r.source_path for r in records if r.derived["subtype"] == "epic"} == expected_epics
    assert len(fields) == 44
    assert sum(record.derived["subtype"] == "epic" for record in records) == 92
