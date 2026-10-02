"""Authored Documents retain fields and remain distinct from specialized records."""

from datetime import date
import importlib
import json
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return importlib.import_module("knowledge.native_types.document").extract(root)


def _write(root, name, metadata=None, body="# Heading\n\nExact body.\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if metadata is None else "---\n" + yaml.safe_dump(metadata) + "---\n"
    path.write_text(prefix + body, encoding="utf-8")
    return path


def _config(root, surfaces):
    path = root / "config/paths.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"surfaces": surfaces}), encoding="utf-8")


def test_document_preserves_complete_frontmatter_and_body(tmp_path):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    from knowledge.native_properties import decode, encode

    metadata = {
        "id": "authored-id",
        "title": "Source title",
        "type": "how-to",
        "status": "active",
        "created": date(2026, 9, 1),
        "last_updated": "2026-09-02",
        "description": "Contains --- here",
        "current": "authored",
        "components": [],
        "source_ticket": None,
        "related_docs": ["docs/a.md", {"Label": "docs/b.md"}],
        "stack": {"framework": "native", "css": "none"},
        "data_layer": {"mock_toggle": {"production_lock": True}, "future": [{"x": 7}]},
    }
    body = "\n# Another title\n\n**Status:** open\n\n```yaml\nx: 1\n```\n"
    _write(tmp_path, "docs/known-issues/a.md", metadata, body)
    (record,) = _extract(tmp_path)
    assert record.kind == "Document"
    assert record.native_id == record.source_path == "docs/known-issues/a.md"
    assert record.locator == ""
    assert record.metadata == metadata
    assert decode(encode(record.metadata)) == metadata
    assert record.title == "Source title"
    assert record.description == "Contains --- here"
    assert record.derived == {"body": body, "document_family": "known_issue"}
    assert record.metadata["status"] == "active"
    assert "children" not in record.metadata


def test_document_legacy_memory_identity_and_safe_display_fallback(tmp_path):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    body = "```md\n# Example title\n```\n\n# Real title\ntext\n"
    _write(tmp_path, "memory/same.md", None, body)
    _write(tmp_path, "docs/sub/same.md", {"title": None, "description": []}, "plain\n")
    _write(tmp_path, "memory/nested/ignored.md")
    by_id = {r.native_id: r for r in _extract(tmp_path)}
    assert set(by_id) == {"memory/same.md", "docs/sub/same.md"}
    memory = by_id["memory/same.md"]
    assert memory.metadata == {}
    assert memory.title == "Real title"
    assert memory.description == ""
    assert memory.derived == {"body": body, "document_family": "memory"}
    assert by_id["docs/sub/same.md"].title == "same"
    assert by_id["docs/sub/same.md"].metadata == {"title": None, "description": []}


def test_document_excludes_owned_views_without_dropping_authored_guides(tmp_path):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    excluded = [
        "docs/architecture/adrs/ADR-001-a.md",
        "docs/agents/cards/a.md",
        "docs/glossary.md",
        "docs/roadmap.md",
        "docs/changelog/a.md",
        "docs/elsewhere-card.md",
    ]
    included = [
        "docs/architecture/adrs/README.md",
        "docs/architecture/components/a.md",
        "docs/agents/documentation/reference-author.md",
        "docs/agents/README.md",
        "docs/product-truth/README.md",
        "docs/acceptance-criteria/guide.md",
    ]
    for name in excluded + included:
        _write(tmp_path, name, {"type": "card"} if name.endswith("elsewhere-card.md") else {})
    records = _extract(tmp_path)
    assert {r.native_id for r in records} == set(included)
    component = next(r for r in records if r.native_id.endswith("components/a.md"))
    assert component.derived["document_family"] == "component_document"


def test_document_configured_surfaces_and_product_manifest_views(tmp_path):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    _config(
        tmp_path,
        {
            "docs": {"path": "manual/"},
            "adrs": {"path": "manual/decisions/"},
            "glossary": {"path": "manual/words.md"},
            "roadmap": {"path": "manual/plan.json"},
            "components": {"path": "manual/parts/"},
        },
    )
    for name in [
        "manual/decisions/ADR-1.md",
        "manual/words.md",
        "manual/plan.md",
        "manual/parts/one.md",
        "manual/flow-guide.md",
        "docs/ignored.md",
    ]:
        _write(tmp_path, name)
    product = tmp_path / "manual/product-truth"
    (product / "flows").mkdir(parents=True)
    (product / "flows/one.flow.json").write_text("{}", encoding="utf-8")
    (product / "index.json").write_text(
        json.dumps({"artifacts": [{"type": "flow", "path": "flows/one.flow.json"}]}),
        encoding="utf-8",
    )
    _write(tmp_path, "manual/product-truth/flows/one.md")
    _write(tmp_path, "manual/product-truth/flows/authored.md", body="Generated content guide\n")
    records = _extract(tmp_path)
    assert {r.native_id for r in records} == {
        "manual/parts/one.md",
        "manual/flow-guide.md",
        "manual/product-truth/flows/authored.md",
    }
    assert (
        next(r for r in records if r.native_id.endswith("one.md")).derived["document_family"]
        == "component_document"
    )


@pytest.mark.parametrize(
    "contents", ["---\ntitle: missing close\n", "---\n- a\n---\n", "---\ntitle: [\n---\n"]
)
def test_document_malformed_frontmatter_fails_explicitly(tmp_path, contents):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    path = _write(tmp_path, "docs/invalid.md")
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="frontmatter"):
        _extract(tmp_path)


@pytest.mark.parametrize("entry", [{"path": "../outside"}, {"path": 4}, []])
def test_document_refuses_invalid_or_escaping_surface(tmp_path, entry):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _config(tmp_path, {"docs": entry})
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_document_missing_roots_is_empty(tmp_path):
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    assert _extract(tmp_path) == []


def test_document_real_corpus_full_metadata_fidelity():
    # covers: KM-400a-1-vii
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    from knowledge.native_types.common import frontmatter

    root = Path(__file__).resolve().parents[2]
    records = _extract(root)
    assert len(records) >= 700
    assert len({r.native_id for r in records}) == len(records)
    by_id = {r.native_id: r for r in records}
    for record in records:
        metadata, body = frontmatter(root / record.source_path)
        assert record.metadata == metadata
        assert record.derived["body"] == body
    assert "docs/ui-context.md" in by_id
    assert "docs/architecture/components/doc-compliance.md" in by_id
    assert "data_layer" in by_id["docs/ui-context.md"].metadata
    assert "docs/glossary.md" not in by_id
    assert not any("/agents/cards/" in key for key in by_id)
