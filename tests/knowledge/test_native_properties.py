"""Behavioral field-fidelity controls for KM-400a-3-i."""

from datetime import date, datetime, timezone
import json

import pytest


def test_nested_metadata_round_trips_without_json_value_blobs():
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_properties import encode, decode, restore_types

    source = {
        "priority": "high",
        "created": date(2026, 10, 2),
        "observed": datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc),
        "components": ["finalize", "other", "finalize"],
        "test_spec": [{"name": "first", "required": True}, {"name": "second", "required": False}],
        "nested": {"a/b~c": {"": 3}, "empty": {}, "null": None},
        "empty_list": [],
        "mixed": [1, "1", None, []],
        "amended_by": [
            {date(2026, 6, 5): "Authored date key", "@date:2026-06-05": "Distinct string key"}
        ],
        "typed_keys": {17: "integer key", None: "null key", "17": "string key"},
    }
    props = encode(source)
    assert props["priority"] == "high"
    assert props["/test_spec/1/name"] == "second"
    assert props["/test_spec/1/required"] is False
    assert props["/nested/a~1b~0c/"] == 3
    assert decode(props) == source
    serialized = json.loads(json.dumps(props, default=lambda x: x.isoformat()))
    assert decode(restore_types(serialized)) == source


def test_authored_reserved_names_cannot_replace_graph_bookkeeping():
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_properties import encode, decode

    source = {
        "current": "historical",
        "key": "authored",
        "payload": {"x": 1},
        "/key": 4,
        "_native_shape": "authored-shape",
        "id": "native-id",
    }
    props = encode(source)
    assert "current" not in props and "key" not in props and "id" not in props
    assert props["/current"] == "historical"
    assert props["/~1key"] == 4
    assert decode(props) == source


def test_missing_null_empty_and_scalar_union_stay_distinct() -> None:
    # covers: KM-400a-3-i
    # angle: criterion
    from knowledge.native_properties import encode, decode

    cases: list[dict[str, object]] = [
        {},
        {"superseded_by": None},
        {"superseded_by": []},
        {"superseded_by": "AC-1"},
        {"superseded_by": ["AC-1"]},
    ]
    for source in cases:
        assert decode(encode(source)) == source


def test_unsupported_values_fail_instead_of_silently_disappearing():
    # covers: KM-400a-3-i
    # angle: failure
    from knowledge.native_properties import encode

    for source in ({"x": float("nan")}, {"x": {1, 2}}, {(1, 2): "invalid-key"}):
        with pytest.raises(ValueError):
            encode(source)


def test_large_integer_values_and_keys_remain_driver_safe_and_lossless():
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_properties import encode, decode, restore_types

    source = {"large": 2**63, "negative": -(2**63) - 1, "items": [2**64], 2**80: "key"}
    props = restore_types(json.loads(json.dumps(encode(source))))
    assert props["large"] == str(2**63)
    assert props["negative"] == str(-(2**63) - 1)
    assert props["/items/0"] == str(2**64)
    assert decode(props) == source
