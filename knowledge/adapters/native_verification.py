"""Verify physical native fields before a staged generation can be published."""

from __future__ import annotations


def native_value(value):
    """Compare driver temporal values with their source-native equivalents."""
    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, list):
        return ("list", tuple(native_value(item) for item in value))
    return (type(value).__name__, value)


def verify_rows(expected: list[dict], actual: list[dict]) -> None:
    """Reject missing, duplicated or changed fields without logging source contents."""
    observed = {row["key"]: row["props"] for row in actual}
    if len(actual) != len(expected) or len(observed) != len(expected):
        raise ValueError("native property readback count mismatch")
    for row in expected:
        found = observed.get(row["key"])
        if found is None:
            raise ValueError("native property readback identity mismatch")
        for field, value in row.items():
            if native_value(found.get(field)) != native_value(value):
                raise ValueError("native property readback mismatch: " + field)
