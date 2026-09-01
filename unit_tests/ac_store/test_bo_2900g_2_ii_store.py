"""
MODULE: unit_tests/ac_store/test_bo_2900g_2_ii_store.py
COVERS: BO-2900g-2-ii

GOAL: the two store-level guarantees of the narrowed durable-effect derivation.

  1. Narrowing must not push any NEW record into disagreement with its authored
     declares_side_effect. Nine records already disagreed beforehand and are
     pinned in an allowlist rather than edited — they are a separate defect in
     the opposite direction (probable false NEGATIVES), and rewriting them to
     quiet the gate is what BO-2900g-2-ii explicitly forbids.

  2. A genuine durable effect must still force user-surface-smoker into the
     generated ticket. Narrowing a detector is one edit away from disabling the
     guard it feeds, so that floor is asserted against the real router.

Both run against the REAL store and the REAL config, not fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"

sys.path.insert(0, str(_REPO_ROOT / "scripts" / "commit_guardian"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from _ac_schema_validators import validate_declares_side_effect  # noqa: E402
from generate_ticket_from_ac import _build_agents_map  # noqa: E402

# Records whose authored declares_side_effect disagreed with the derivation
# BEFORE BO-2900g-2-ii narrowed it, and still do for the same reason. They are
# NOT this change's doing and are left for their owners to decide.
#
# BO-2900g-2 was in this set and is no longer: adding BO-2900g-2-ii as its child
# meant staging the parent, and the forward ratchet then refused the commit until
# the disagreement was resolved. It was resolved to false for CONSISTENCY — its
# Then clause states what a record CARRIES, which is the same shape as
# BO-2600b-2's "that statement appears in the record", and that one was set false
# in the same change. The declaration follows what the Then clause states, not
# what the implementation incidentally writes.
#
# That episode is worth knowing when clearing the rest: several of these will
# resolve the same way once anyone touches them. BO-2400g-4-i is the likeliest
# genuine false NEGATIVE — it requires findings to appear on a pull request,
# which is durable and externally visible, and is asserted in its Then.
#
# Shrinking this set is progress. Growing it is a regression: it means a change
# to the derivation moved a record into contradiction without reconciling it.
#
# BP-1100g-4 was in this set and is no longer: it was reconciled on main while this
# branch was open, and the staleness test below caught it in CI on the merge ref
# before a human did. That is the set shrinking on its own, which is the intent.
#
# BP-1100g-5-i removed 2026-08-31, reconciled rather than aged out. It declared
# declares_side_effect: true while every Then clause in it reports a shortfall and
# writes nothing; the derivation excludes transient destinations, so false is the
# honest value. Two mechanisms disagreed about whether this was visible, and both
# were right about their own scope: the commit-time AC hooks read only the staged
# index, so they had never been handed the file and never fired — while this
# store-wide test walks the real store, which is exactly why it exists. The hook's
# silence was not a pass. This test's allowlist was the only record that the
# disagreement was known at all.
_KNOWN_PRE_EXISTING_DISAGREEMENTS = frozenset({
    "BO-2400g-4",
    "BO-2400g-4-i",
    "BO-2900g-1",
    "BO-2900g-2-i",
    "BO-2900g-4",
    "BP-1100g-4-i",
})


def _iter_store_records():
    """Yield (path, parsed dict) for every AC record in the real store."""
    for path in sorted(_REAL_AC_ROOT.rglob("*.yaml")):
        if path.name == "index.yaml":
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and data.get("id"):
            yield path, data


class TestNarrowingAddsNoNewDisagreement:
    def test_bo_2900g_2_ii_narrowing_adds_no_new_disagreement(self) -> None:
        # covers: BO-2900g-2-ii
        """No record outside the pinned allowlist may disagree with the derivation."""
        unexpected = sorted(
            data["id"]
            for path, data in _iter_store_records()
            if data.get("declares_side_effect") is not None
            and validate_declares_side_effect(path, data)
            and data["id"] not in _KNOWN_PRE_EXISTING_DISAGREEMENTS
        )
        assert unexpected == [], (
            "These records' authored declares_side_effect disagrees with the "
            f"derivation and is not a known pre-existing case: {unexpected}. "
            "Either the derivation changed without reconciling them, or they were "
            "authored against a different reading. Do not add them to the "
            "allowlist to make this pass — decide each one."
        )

    def test_bo_2900g_2_ii_allowlist_has_not_gone_stale(self) -> None:
        # covers: BO-2900g-2-ii
        """Every pinned id must still exist and still disagree.

        Without this, the allowlist silently keeps excusing records that were
        fixed or deleted, and stops describing the store.
        """
        still_disagreeing = {
            data["id"]
            for path, data in _iter_store_records()
            if data.get("declares_side_effect") is not None
            and validate_declares_side_effect(path, data)
        }
        resolved = sorted(_KNOWN_PRE_EXISTING_DISAGREEMENTS - still_disagreeing)
        assert resolved == [], (
            f"These ids no longer disagree (fixed or removed): {resolved}. "
            "Delete them from _KNOWN_PRE_EXISTING_DISAGREEMENTS — shrinking that "
            "set is the point."
        )


class TestDurableEffectsStillRouteTheSmoker:
    def test_bo_2900g_2_ii_durable_effects_still_route_the_smoker(self) -> None:
        # covers: BO-2900g-2-ii
        """A true declaration must still place user-surface-smoker as needed.

        The regression floor for the narrowing: a detector that marks nothing is
        indistinguishable from a guard that was switched off.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            files_touched=[],
            declares_side_effect=True,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )
        assert agents.get("user-surface-smoker") == "needed", agents

    def test_bo_2900g_2_ii_absent_declaration_does_not_route_the_smoker(self) -> None:
        # covers: BO-2900g-2-ii
        """The other half: no declaration means no forced smoker phase.

        Pairing the two is what makes the floor meaningful — a router that
        always adds the smoker would pass the assertion above on its own.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            files_touched=[],
            declares_side_effect=False,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )
        assert agents.get("user-surface-smoker") != "needed", agents
