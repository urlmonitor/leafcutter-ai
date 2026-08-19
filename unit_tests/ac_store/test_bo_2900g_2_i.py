"""
MODULE: unit_tests/ac_store/test_bo_2900g_2_i.py
COVERS: BO-2900g-2-i

GOAL: The declares_side_effect declaration must be DERIVED per-record, not a
property that only holds right after a one-off sweep. A record authored AFTER
any sweep — by an author with no knowledge of the field — must still carry the
declaration, and the guarantee must hold with the sweep never run at all
(two-run test: sweep-run vs sweep-never-run, identical post-authoring state).

CURRENT STATE (2026-08-18): No derivation function
(_ac_schema_validators.derive_declares_side_effect) and no sweep entry point
exist yet — RED with ImportError.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "commit_guardian"))


def _import_derivation():
    from _ac_schema_validators import derive_declares_side_effect  # noqa: PLC0415

    return derive_declares_side_effect


_NEW_DURABLE_RECORD = {
    "id": "ZZ-2900g-2-i-new",
    "criteria": (
        "Given a change,\nWhen the tool runs,\n"
        "Then a record is persisted to the database.\n"
    ),
}


class TestRecordAuthoredAfterTheSweepCarriesTheDeclaration:
    def test_bo_2900g_2_i_record_authored_after_the_sweep_carries_the_declaration(
        self,
    ) -> None:
        # covers: BO-2900g-2-i
        """Simulate a sweep over a small store, then author a NEW durable-effect
        record with no mention of the field anywhere in the input, and assert
        the derivation (invoked by the ordinary authoring path) marks it True
        with no second sweep run."""
        derive = _import_derivation()

        pre_existing = [
            {
                "id": "ZZ-2900g-2-i-old",
                "criteria": "Given x\nWhen y\nThen a file is written to disk\n",
            },
        ]
        # "sweep": derive once over the pre-existing store.
        for record in pre_existing:
            record["declares_side_effect"] = derive(record)
        assert all(r.get("declares_side_effect") is True for r in pre_existing)

        # A NEW record, authored afterward, with NO declares_side_effect key
        # anywhere in the input — the author never mentions the field.
        new_record = copy.deepcopy(_NEW_DURABLE_RECORD)
        assert "declares_side_effect" not in new_record

        derived_value = derive(new_record)
        assert derived_value is True, (
            f"a new durable-effect record authored after the sweep must "
            f"derive True without any second sweep, got {derived_value!r}"
        )


class TestGuaranteeHoldsWithTheSweepNeverRun:
    def test_bo_2900g_2_i_guarantee_holds_with_the_sweep_never_run(self) -> None:
        # covers: BO-2900g-2-i
        """Two-run discriminator: identical new-record input, one run preceded
        by a simulated sweep and one with no sweep at all. The post-authoring
        derived value for the SAME new record must be identical in both —
        proving the sweep is not in the causal chain."""
        derive = _import_derivation()

        # Run A: sweep executed over an (irrelevant) pre-existing store first.
        pre_existing = [{"id": "ZZ-x", "criteria": "Given x\nWhen y\nThen a file is written\n"}]
        for r in pre_existing:
            derive(r)
        new_record_a = copy.deepcopy(_NEW_DURABLE_RECORD)
        result_a = derive(new_record_a)

        # Run B: sweep never run at all — no pre-existing derivation call.
        new_record_b = copy.deepcopy(_NEW_DURABLE_RECORD)
        result_b = derive(new_record_b)

        assert result_a == result_b, (
            f"derivation must be identical whether or not a sweep preceded it: "
            f"with-sweep={result_a!r}, without-sweep={result_b!r}"
        )
        assert result_a is True, result_a


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
