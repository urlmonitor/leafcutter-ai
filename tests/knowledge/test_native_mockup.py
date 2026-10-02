"""Mockup source fidelity and supporting-source safety (KM-400a-3-i)."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from knowledge.native_properties import decode, encode


def _extract(root):
    return importlib.import_module("knowledge.native_types.mockup").extract(root)


def _source(root, metadata=None, name="plant/cart", text=None):
    path = root / "docs/product-truth/mockups" / (name + ".mockup.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        text if text is not None else json.dumps(metadata or _metadata()),
        encoding="utf-8-sig",
    )
    return path


def _metadata():
    return {
        "id": "plant/cart",
        "component": "ux-prototyping",
        "screen": "cart",
        "title": "Exact title",
        "summary": "Exact summary",
        "entities": ["Order"],
        "source": "mock",
        "example_product": "plant",
        "realization": "spec",
        "renders": None,
        "status": "deprecated",
        "superseded_by": "plant/cart-new",
        "readiness": "approved",
        "version": 2,
        "shape_version": 3,
        "tags": [],
        "mock_data_ref": "plant/data",
        "provenance": [],
    }


def _manifest(root, entries):
    path = root / "docs/product-truth/index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"artifacts": entries}), encoding="utf-8")
    return path


def _entry(**changes):
    return {
        "id": "plant/cart",
        "type": "mockup",
        "path": "mockups/plant/cart.mockup.json",
        **changes,
    }


def test_mockup_all_fields_unknown_extensions_and_shape_are_preserved(tmp_path):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: integration
    # angle: criterion
    metadata = _metadata()
    metadata["future"] = {"x/y~z": [None, True, {}, [], ""]}
    _source(tmp_path, metadata)
    (record,) = _extract(tmp_path)
    assert record.kind == "Mockup" and record.native_id == "plant/cart"
    assert record.source_path == "docs/product-truth/mockups/plant/cart.mockup.json"
    assert record.title == metadata["title"] and record.description == metadata["summary"]
    assert record.locator == ""
    assert record.metadata == metadata
    assert decode(encode(record.metadata)) == metadata
    assert record.derived == {"manifest_registered": False}


def test_mockup_manifest_and_render_remain_separate_exact_supporting_sources(tmp_path):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: integration
    # angle: seam
    metadata = _metadata()
    metadata["renders"] = "cart.html"
    metadata["provenance"] = [
        {"action": "authored", "by": "A", "date": "2026-01-01", "note": "First"},
        {},
        {"by": "B", "note": "Second"},
    ]
    path = _source(tmp_path, metadata)
    html = '<html>\r\n<script>throw "Never execute";</script>Exact â‚¬ screen\r\n</html>'
    render = path.parent / "cart.html"
    render.write_bytes(html.encode("utf-8"))
    entry = _entry(summary="Stale summary", tags=["stale"])
    _manifest(tmp_path, [{"type": "flow", "id": "plant/flow"}, entry])
    (record,) = _extract(tmp_path)
    assert record.metadata == metadata
    assert record.derived["manifest_record"] == entry
    assert record.derived["manifest_registered"] is True
    assert record.derived["manifest_locator"] == "/artifacts/1"
    assert record.derived["manifest_source_path"] == "docs/product-truth/index.json"
    assert record.derived["manifest_differing_fields"] == ["summary", "tags"]
    assert record.derived["render_source_path"].endswith("/plant/cart.html")
    assert record.derived["render_body"] == html
    assert record.derived["render_content_hash"] == hashlib.sha256(render.read_bytes()).hexdigest()
    assert decode(encode(record.derived)) == record.derived
    assert decode(encode(record.metadata))["provenance"] == metadata["provenance"]


def test_mockup_real_canonical_population_includes_unregistered_and_null_renders():
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    records = _extract(root)
    paths = list((root / "docs/product-truth/mockups").rglob("*.mockup.json"))
    assert len(records) == len(paths) == 15
    assert {record.source_path for record in records} == {p.relative_to(root).as_posix() for p in paths}
    manifest = json.loads((root / "docs/product-truth/index.json").read_text(encoding="utf-8-sig"))
    registered = {entry["id"]: entry for entry in manifest["artifacts"] if entry["type"] == "mockup"}
    assert sum(record.derived["manifest_registered"] for record in records) == 14
    assert sum("render_body" in record.derived for record in records) == 10
    assert sum("shape_version" in record.metadata for record in records) == 5
    assert sum("realization" in record.metadata for record in records) == 5
    for record in records:
        original = json.loads((root / record.source_path).read_text(encoding="utf-8-sig"))
        assert record.metadata == original
        assert decode(encode(record.metadata)) == original
        for field in ("realization", "shape_version"):
            assert (field in record.metadata) == (field in original)
        assert record.derived["manifest_registered"] == (record.native_id in registered)
        if record.native_id in registered:
            assert record.derived["manifest_record"] == registered[record.native_id]
        if original["renders"] is None:
            assert not any(key.startswith("render_") for key in record.derived)
        else:
            render = (root / record.source_path).parent / original["renders"]
            assert ("render_body" in record.derived) == render.is_file()
            if render.is_file():
                assert record.derived["render_body"] == render.read_bytes().decode("utf-8-sig")
    sign_in = next(record for record in records if record.native_id == "fern-and-fig/sign-in")
    assert sign_in.derived["manifest_registered"] is False
    cart = next(record for record in records if record.native_id == "fern-and-fig/cart")
    assert cart.metadata["summary"] != cart.derived["manifest_record"]["summary"]


def test_mockup_missing_store_and_absent_optional_fields_are_not_manufactured(tmp_path):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    fixture = tmp_path / "leafcutter-web/fixtures/cart.mockup.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(json.dumps(_metadata()), encoding="utf-8")
    assert _extract(tmp_path) == []
    metadata = _metadata()
    for key in ["realization", "shape_version", "superseded_by", "tags"]:
        metadata.pop(key)
    _source(tmp_path, metadata)
    (record,) = _extract(tmp_path)
    assert record.metadata == metadata
    assert record.derived == {"manifest_registered": False}


def test_mockup_safe_missing_render_is_reported_without_losing_record(tmp_path):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    metadata = _metadata()
    metadata["renders"] = "not-yet-drawn.html"
    _source(tmp_path, metadata)
    (record,) = _extract(tmp_path)
    assert record.metadata == metadata
    assert record.derived["render_missing"] is True
    assert record.derived["render_source_path"].endswith("/not-yet-drawn.html")
    assert "render_body" not in record.derived


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "[]",
        "{}",
        '{"id":"plant/cart","title":null}',
        '{"id":"other/cart","title":"T","summary":"S","renders":null}',
    ],
)
def test_mockup_malformed_records_fail_explicitly(tmp_path, text):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _source(tmp_path, text=text)
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_mockup_duplicate_records_and_manifest_ids_fail_explicitly(tmp_path):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _source(tmp_path)
    duplicate = _source(tmp_path, name="plant/second")
    with pytest.raises(ValueError, match="duplicate"):
        _extract(tmp_path)
    duplicate.unlink()
    _manifest(tmp_path, [_entry(), _entry()])
    with pytest.raises(ValueError, match="duplicate"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "unsafe",
    [
        "../../../../../../outside.html",
        "C:/outside.html",
        "C:\\outside.html",
        "/outside.html",
        "//server/share/a.html",
        "https://example.com/a.html",
        "file:outside.html",
    ],
)
def test_mockup_render_paths_cannot_escape_or_fetch_urls(tmp_path, unsafe):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    metadata = _metadata()
    metadata["renders"] = unsafe
    _source(tmp_path, metadata)
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "entry",
    [
        _entry(path="../outside.json"),
        _entry(path="mockups/plant/other.mockup.json"),
        _entry(id="plant/missing"),
        _entry(path="https://example.com/mockup.json"),
    ],
)
def test_mockup_manifest_path_and_identity_conflicts_fail(tmp_path, entry):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _source(tmp_path)
    _manifest(tmp_path, [entry])
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_mockup_resolved_escape_is_rejected_before_read(tmp_path, monkeypatch):
    # covers: KM-400a-1-xi
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    source = _source(tmp_path)
    original_resolve = Path.resolve

    def escaped_resolve(path, *args, **kwargs):
        if path == source:
            return tmp_path.parent / "outside.mockup.json"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", escaped_resolve)
    with pytest.raises(ValueError):
        _extract(tmp_path)
