"""ADR metadata extraction preserves native source truth and legacy documents."""

from datetime import date
from importlib import import_module
from pathlib import Path

import yaml


def _write(root, name, metadata, body):
    path = root / "docs/architecture/adrs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "" if metadata is None else "---\n" + yaml.safe_dump(metadata) + "---\n"
    path.write_text(front + body, encoding="utf-8")
    return path


def _extract(root):
    return import_module("knowledge.native_types.adr").extract(root)


def test_native_adr_preserves_all_frontmatter_types_without_defaults(tmp_path):
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: criterion
    metadata = {
        "title": "ADR-999: Complete metadata",
        "description": "Exact description",
        "type": "adr",
        "status": "active",
        "created": date(2026, 8, 1),
        "last_updated": "2026-08-03",
        "components": ["finalize", "testing", "finalize"],
        "deciders": ["Ada"],
        "related_docs": [{"design / rationale": "docs/design.md"}, "docs/other.md"],
        "related_code": ["scripts/finalize.py"],
        "affects_diagrams": [],
        "amended": "2026-08-04",
        "requires_ac": "KM-400a-3-i",
        "tags": ["history"],
        "extension": {"null": None, "false": False, "zero": 0, "empty": "", "map": {}},
        "current": "source-current",
        "payload": {"source": True},
    }
    body = "# ADR\n\n## Status\n\n| Field | Value |\n|---|---|\n| Status | Accepted |\n| Date | 2026-08-02 |\n| Author | Ada |\n| Supersedes | None |\n\n## Context\nNative body.\n"
    _write(tmp_path, "ADR-999-complete-metadata.md", metadata, body)
    (record,) = _extract(tmp_path)
    assert record.kind == "ADR"
    assert record.native_id == "ADR-999-complete-metadata"
    assert record.metadata == metadata
    assert isinstance(record.metadata["created"], date)
    assert isinstance(record.metadata["last_updated"], str)
    assert record.derived["body"] == body
    assert record.derived["adr_status"] == "Accepted"
    assert record.derived["adr_date"] == "2026-08-02"
    assert record.derived["adr_author"] == "Ada"
    assert record.derived["adr_supersedes"] == "None"
    assert record.metadata["status"] == "active"
    assert "id" not in record.metadata
    assert record.locator == "frontmatter"


def test_native_adr_legacy_missing_frontmatter_remains_a_record(tmp_path):
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: boundary
    body = "# Legacy title\n\n## Decision status\n\nAccepted long ago.\n\n## Context\nContext.\n"
    _write(tmp_path, "ADR-003-legacy-body.md", None, body)
    (record,) = _extract(tmp_path)
    assert record.native_id == "ADR-003-legacy-body"
    assert record.title == "ADR-003-legacy-body"
    assert record.description == "Accepted long ago."
    assert record.metadata == {}
    assert record.derived["body"] == body
    assert record.derived["status_section"] == "\nAccepted long ago.\n\n"
    assert record.derived["frontmatter_present"] is False
    diagnostics = record.derived["diagnostics"]
    assert any(d["code"] == "missing_frontmatter" for d in diagnostics)
    assert {d["field"] for d in diagnostics if d["code"] == "missing_required_field"} == {
        "title",
        "type",
        "status",
        "created",
        "last_updated",
        "components",
    }
    assert "adr_status" not in record.derived
    assert "adr_date" not in record.derived


def test_native_adr_distinguishes_document_status_and_guide_disagreements(tmp_path):
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: boundary
    _write(tmp_path, "ADR-001-historical-type.md", {"type": "tutorial", "status": None}, "Body.\n")
    (record,) = _extract(tmp_path)
    assert record.metadata == {"type": "tutorial", "status": None}
    diagnostics = record.derived["diagnostics"]
    assert any(
        d["code"] == "unexpected_document_type" and d["observed"] == "tutorial" for d in diagnostics
    )
    assert any(
        d["code"] == "missing_required_field" and d["field"] == "status" and d["state"] == "null"
        for d in diagnostics
    )
    assert {d["field"] for d in diagnostics if d["code"] == "schema_requirement_disagreement"} == {
        "description",
        "affects_diagrams",
    }


def test_native_adr_only_reads_first_direct_status_table_and_keeps_unknown_rows(tmp_path):
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: boundary
    body = """# ADR

```markdown
## Status
| Field | Value |
|---|---|
| Status | Fake |
```

## 1. Status

| Field | Value |
|---|---|
| Status | Accepted, amended twice |
| Context ADRs | ADR-005 |
| Date | first date |
| Date | second date |

Later explanation and unrelated table:

| Field | Value |
|---|---|
| Author | Wrong later author |

## Context
Context.
"""
    _write(tmp_path, "ADR-999-table-scope.md", {}, body)
    (record,) = _extract(tmp_path)
    rows = record.derived["status_metadata"]
    assert [(r["label"], r["value"]) for r in rows] == [
        ("Status", "Accepted, amended twice"),
        ("Context ADRs", "ADR-005"),
        ("Date", "first date"),
        ("Date", "second date"),
    ]
    assert all(r["source_locator"].startswith("body:line:") for r in rows)
    assert record.derived["adr_status"] == "Accepted, amended twice"
    assert "adr_author" not in record.derived
    assert "adr_date" not in record.derived
    assert any(
        d["code"] == "ambiguous_status_row" and d["field"] == "Date"
        for d in record.derived["diagnostics"]
    )


def test_native_adr_respects_configured_surface_and_existing_id_override(tmp_path):
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: seam
    import json

    (tmp_path / "config").mkdir()
    (tmp_path / "config/paths.json").write_text(
        json.dumps({"surfaces": {"adrs": {"path": "decisions/"}}}), encoding="utf-8"
    )
    path = _write(
        tmp_path,
        "ADR-777-moved.md",
        {"id": "original-override", "title": "Source title"},
        "Body.\n",
    )
    (tmp_path / "decisions").mkdir()
    path.rename(tmp_path / "decisions/ADR-777-moved.md")
    (tmp_path / "decisions/README.md").write_text("# Directory index\n", encoding="utf-8")
    (tmp_path / "decisions/Master_Plan.md").write_text("# Planning index\n", encoding="utf-8")
    (record,) = _extract(tmp_path)
    assert record.native_id == "original-override"
    assert record.source_path == "decisions/ADR-777-moved.md"
    assert record.metadata == {"id": "original-override", "title": "Source title"}


def test_native_adr_real_sources_retain_complete_fields_and_legacy_body():
    # covers: KM-400a-1-ii
    # covers: KM-400a-3-i
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    records = {record.native_id: record for record in _extract(root)}
    from knowledge.native_types.common import frontmatter

    name = "ADR-056-colony-memory-evidence-reinforcement"
    metadata, body = frontmatter(root / "docs/architecture/adrs" / f"{name}.md")
    record = records[name]
    assert len(metadata) >= 10
    assert record.metadata == metadata
    assert record.metadata["status"] == "active"
    assert record.derived["adr_status"] == "Accepted"
    assert record.derived["body"] == body
    legacy = records["ADR-003-test-source-of-truth-discipline"]
    assert legacy.metadata == {}
    assert len(legacy.derived["body"]) > 100
    assert legacy.derived["frontmatter_present"] is False
