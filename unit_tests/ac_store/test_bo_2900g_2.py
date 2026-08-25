"""
MODULE: unit_tests/ac_store/test_bo_2900g_2.py
COVERS: BO-2900g-2

GOAL: ``declares_side_effect`` must be DERIVED by code from an AC record's own
criteria text (a durable, observable effect asserted in a Then clause), not
authored by opinion and not left unset. As of 2026-08-18 no such derivation
function exists anywhere in the reference module named by this AC's
it_requirements (scripts/commit_guardian/_ac_schema_validators.py) — these
tests are RED with ImportError until it is added.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "commit_guardian"))


def _import_derivation():
    """Import the (not-yet-existing) derivation function.

    Import is deferred into a helper so every test gets a clear ImportError
    rather than a collection-time failure that hides the point of each test.
    """
    from _ac_schema_validators import derive_declares_side_effect  # noqa: PLC0415

    return derive_declares_side_effect


class TestDurableEffectCriteriaYieldTheDeclaration:
    def test_bo_2900g_2_durable_effect_criteria_yield_the_declaration(self) -> None:
        # covers: BO-2900g-2
        """A record whose Then clause asserts a file/record/state-change is
        marked True; one that asserts only a returned value is marked False."""
        derive = _import_derivation()

        durable = {
            "id": "ZZ-2900g-2-a",
            "criteria": (
                "Given a change,\nWhen the tool runs,\n"
                "Then a file is written to disk and can be read back.\n"
            ),
        }
        non_durable = {
            "id": "ZZ-2900g-2-b",
            "criteria": (
                "Given an input,\nWhen the function is called,\n"
                "Then it returns the computed value to its caller.\n"
            ),
        }
        assert derive(durable) is True, (
            f"a Then clause asserting a written file must derive True, got "
            f"{derive(durable)!r}"
        )
        assert derive(non_durable) is False, (
            f"a Then clause asserting only a returned value must derive "
            f"False, got {derive(non_durable)!r}"
        )


class TestDerivationOverRealStoreMarksStrictSubset:
    def test_bo_2900g_2_derivation_over_the_real_on_disk_store_marks_a_strict_subset(
        self,
    ) -> None:
        # covers: BO-2900g-2
        """Load every real AC record with yaml.safe_load (never hand-built
        dicts) and assert the derivation marks a strict, non-empty subset:
        neither zero nor all records, and the same split on a second run."""
        derive = _import_derivation()

        # Assert, never skip. This test's whole value is that it reads the REAL
        # store; if the store is absent the test has proved nothing, and a skip
        # would report that as a pass. An absent store is a broken checkout, not
        # a reason to stay quiet.
        assert _REAL_AC_ROOT.is_dir(), (
            f"real AC store root absent: {_REAL_AC_ROOT} — this test derives its "
            f"subset from the real corpus and cannot be satisfied without it"
        )

        records: list[dict] = []
        for path in sorted(_REAL_AC_ROOT.rglob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(data, dict) and data.get("id") and data.get("criteria"):
                records.append(data)

        assert len(records) > 100, f"expected a large real store, found {len(records)}"

        run1 = [bool(derive(r)) for r in records]
        run2 = [bool(derive(r)) for r in records]
        assert run1 == run2, "derivation must be deterministic across two runs"

        marked = sum(run1)
        assert 0 < marked < len(records), (
            f"derivation must mark a STRICT subset of the real store: "
            f"marked={marked}, total={len(records)}. Marking everything or "
            f"nothing makes the downstream gate noise (see BO-2900g-2 "
            f"constraints)."
        )


class TestCriteriaWithoutThenClauseDoNotSilentlyMark:
    def test_bo_2900g_2_criteria_without_a_then_clause_do_not_silently_mark(self) -> None:
        # covers: BO-2900g-2
        """Empty criteria, criteria with no Then clause, and a written-file
        mention inside a Given only, each resolve to unmarked (False/None) —
        never guessed True."""
        derive = _import_derivation()

        empty = {"id": "ZZ-2900g-2-c", "criteria": ""}
        no_then = {"id": "ZZ-2900g-2-d", "criteria": "Given a file exists\nWhen nothing happens\n"}
        given_only_mentions_file = {
            "id": "ZZ-2900g-2-e",
            "criteria": (
                "Given a file was already written to disk,\n"
                "When the reader runs,\n"
                "Then the returned value matches the file's content.\n"
            ),
        }

        assert not derive(empty), derive(empty)
        assert not derive(no_then), derive(no_then)
        assert not derive(given_only_mentions_file), derive(given_only_mentions_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
