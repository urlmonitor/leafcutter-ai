"""
MODULE: unit_tests/prompt_assembly/test_tq_500f_1_i_three_way_lockstep.py
COVERS: TQ-500f-1-i

GOAL (from the AC criteria): today's lockstep check
(unit_tests/prompt_assembly/test_bp_1100g_1.py's `_compare_angle_sets`)
compares only two of the three permitted-kind lists — R (the requirement
side, config/ac_store_schema.json test_spec[].angle) and T (the taught set,
templates/agents/test-writer.md's TAUGHT-TEST-ANGLES anchor) — so a kind
dropped from G alone (config/test_requirements.schema.json tests[].angle)
goes unnoticed. This ticket widens that SAME check (not a second one beside
it, per the AC's own it_requirements) to full three-way set equality.

THE TARGET CONTRACT (for python-coder, editing test_bp_1100g_1.py in place —
never this file, and never adding a parallel checker): that module must
additionally define

    def _load_generated_angles(schema_path: Path) -> set[str]:
        '''Read config/test_requirements.schema.json's
        $defs.test_entry.properties.angle.enum.'''

    def _compare_three_way_angle_sets(
        emittable: set[str], generated: set[str], taught: dict
    ) -> list[str]:
        '''Full set-equality across R (emittable), G (generated), T (taught).
        One message per differing angle name, naming BY FILE PATH which
        list(s) lack it and which list(s) carry it:
          - R: config/ac_store_schema.json (test_spec[].angle)
          - G: config/test_requirements.schema.json (tests[].angle)
          - T: templates/agents/test-writer.md (taught set)
        Replaces `_compare_angle_sets` (the existing two-way comparator) as
        the ONE comparator both the live-file test and every existing
        R-vs-T test in that module now call — see the AC's it_requirement
        "Replace today's R-vs-T comparison ... rather than adding a second
        check beside it, so two lockstep checks cannot disagree."'''

RED BASELINE (2026-09-25): neither `_load_generated_angles` nor
`_compare_three_way_angle_sets` exists in test_bp_1100g_1.py at HEAD
(confirmed: that module only defines the two-way `_compare_angle_sets` and
`_load_emittable_angles`, with no G-side reader at all). Both names are
therefore imported LAZILY, inside each test, via `_import_target_symbols()`
below — never at module scope — so a missing deliverable produces a real
per-test FAILURE (`pytest.fail`, a collected, counted, individually-reported
red test) rather than a single module-level collection ERROR that swallows
every test in the file into one uncounted red (BO-... verify_red_baseline
counts collection errors as INCONCLUSIVE, not as N counted red tests). Once
the comparator exists, each test proves a distinct half of the widened
contract, exactly as before.

The V1-V4 and stray-kind sets are PREPARED VARIANTS (plain Python literals),
never edits to the real config/template files, per the AC's own
it_requirement. Only the reachability test below reads the real three files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AC_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"
_TEST_REQ_SCHEMA_PATH = _REPO_ROOT / "config" / "test_requirements.schema.json"
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "agents" / "test-writer.md"

# Bare sibling import within the same test directory — same mechanism
# unit_tests/ac_store/*.py already relies on for its `_tkt_500f_*` support
# modules; confirmed to require an explicit sys.path insert of this file's
# own directory (unlike unit_tests/ac_store, plain `pythonpath = .` alone
# does not put unit_tests/prompt_assembly on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Safe at module scope: both names already exist in test_bp_1100g_1.py at
# HEAD (confirmed live), so importing them here cannot itself produce a
# collection error.
from test_bp_1100g_1 import (  # noqa: E402
    _load_emittable_angles,
    _load_taught_angles,
)


def _import_target_symbols():
    """Lazily import the two symbols this AC adds to test_bp_1100g_1.py.

    THE TARGET CONTRACT (for python-coder, editing test_bp_1100g_1.py in
    place — see the module docstring above for the full signatures):
    `_load_generated_angles(schema_path) -> set[str]` and
    `_compare_three_way_angle_sets(emittable, generated, taught) -> list[str]`.

    Called at the TOP of every test below, never at module import time, so a
    missing deliverable fails that ONE test individually (a real, counted
    red) instead of erroring out collection for the whole module. Every
    caller re-runs this import fresh (no caching) so a partial edit made
    mid-run is still picked up by whichever test executes next.

    Returns:
        tuple: (_compare_three_way_angle_sets, _load_generated_angles).

    Raises:
        Nothing directly — `pytest.fail` itself raises `Failed`, which
        pytest reports as a normal test failure, not a collection error.
    """
    try:
        from test_bp_1100g_1 import (
            _compare_three_way_angle_sets,
            _load_generated_angles,
        )
    except ImportError as exc:
        pytest.fail(
            "test_bp_1100g_1.py does not yet define _compare_three_way_angle_sets "
            "and/or _load_generated_angles (see THE TARGET CONTRACT in this "
            f"module's docstring). ImportError: {exc}",
            pytrace=False,
        )
    return _compare_three_way_angle_sets, _load_generated_angles

# ---------------------------------------------------------------------------
# Prepared variants (V1-V4 + stray-kind) — literal sets, no file edits.
# ---------------------------------------------------------------------------

_BASE_EIGHT = {
    "criterion",
    "reachability",
    "seam",
    "real_artifact",
    "deployed",
    "boundary",
    "failure",
    "discrimination",
}

_SEVEN_NO_DISCRIMINATION = _BASE_EIGHT - {"discrimination"}


def _taught_dict(names: set[str]) -> dict:
    return {name: f"rule for {name}" for name in names}


# V1: present in R, G and T.
_V1 = {"R": _BASE_EIGHT, "G": _BASE_EIGHT, "T": _taught_dict(_BASE_EIGHT)}
# V2: present in R and T, absent from G — the case today's R-vs-T check misses.
_V2 = {
    "R": _BASE_EIGHT,
    "G": _SEVEN_NO_DISCRIMINATION,
    "T": _taught_dict(_BASE_EIGHT),
}
# V3: present in R and G, absent from T.
_V3 = {
    "R": _BASE_EIGHT,
    "G": _BASE_EIGHT,
    "T": _taught_dict(_SEVEN_NO_DISCRIMINATION),
}
# V4: present in G and T, absent from R.
_V4 = {
    "R": _SEVEN_NO_DISCRIMINATION,
    "G": _BASE_EIGHT,
    "T": _taught_dict(_BASE_EIGHT),
}
# Stray: "discriminating" present ONLY in G; neither R nor T has it or the
# correctly-spelled "discrimination" either.
_STRAY = {
    "R": _SEVEN_NO_DISCRIMINATION,
    "G": _SEVEN_NO_DISCRIMINATION | {"discriminating"},
    "T": _taught_dict(_SEVEN_NO_DISCRIMINATION),
}


class TestLiveLockstepCheckPassesOverRealThreeSources:
    """angle: reachability — surface_invoked (per the AC's test_spec):
    'the lockstep test collected by pytest, reading the real
    config/ac_store_schema.json, config/test_requirements.schema.json and
    templates/agents/test-writer.md'. No subprocess is spawned (and no
    build.py — see CLAUDE.md's spawn-prohibition); pytest collecting and
    running this test function against the three real on-disk files IS the
    production entry point this angle proves, exactly as the AC's own
    surface_invoked field states."""

    def test_live_lockstep_check_passes_over_real_three_sources(self) -> None:
        # covers: TQ-500f-1-i
        # angle: reachability
        """WRONG VERSION THIS CATCHES: TQ-500f-1's three files (both JSON
        schemas and the taught-set anchor) landing only partially applied —
        e.g. both schemas widened but the taught-set anchor left at 7 keys.
        Reading all three real sources and demanding empty mismatches is the
        only way to catch a partial rollout that a single-file test would
        miss."""
        _compare_three_way_angle_sets, _load_generated_angles = _import_target_symbols()

        for path in (_AC_SCHEMA_PATH, _TEST_REQ_SCHEMA_PATH, _TEMPLATE_PATH):
            assert path.is_file(), f"real source missing: {path}"

        emittable = _load_emittable_angles(_AC_SCHEMA_PATH)
        generated = _load_generated_angles(_TEST_REQ_SCHEMA_PATH)
        taught = _load_taught_angles(_TEMPLATE_PATH)

        mismatches = _compare_three_way_angle_sets(emittable, generated, taught)
        assert mismatches == [], (
            "R, G and T must fully agree on the live files:\n"
            + "\n".join(mismatches)
        )


class TestLockstepComparatorPassesWhenAllThreeListsAgree:
    """angle: criterion — V1: the positive control paired with the
    adversarial V2-V4/stray cases below (a control alone proves nothing per
    the TQ-500 rule cited in the AC's notes)."""

    def test_lockstep_comparator_passes_when_all_three_lists_agree(self) -> None:
        # covers: TQ-500f-1-i
        # angle: criterion
        """WRONG VERSION THIS CATCHES: a comparator that always returns a
        non-empty list regardless of input (e.g. a stub raising
        NotImplementedError or hard-failing) — caught in combination with
        the adversarial tests below, which require an ACTUALLY EMPTY result
        specifically on agreement and a non-empty one specifically on
        disagreement; a constant-fail stub would fail this test."""
        _compare_three_way_angle_sets, _load_generated_angles = _import_target_symbols()
        mismatches = _compare_three_way_angle_sets(_V1["R"], _V1["G"], _V1["T"])
        assert mismatches == [], f"V1 (all three agree) must report no mismatches: {mismatches}"


class TestLockstepComparatorFailsNamingListThatLacksDiscrimination:
    """angle: failure — V2, V3, V4: each must fail, and the failure must
    name the lacking list. V2 is the AC's own named must_catch case."""

    @pytest.mark.parametrize(
        "variant,label,missing_list_marker,carrying_markers",
        [
            (
                _V2,
                "V2 (missing from G only)",
                "config/test_requirements.schema.json",
                ("config/ac_store_schema.json", "test-writer.md"),
            ),
            (
                _V3,
                "V3 (missing from T only)",
                "test-writer.md",
                ("config/ac_store_schema.json", "config/test_requirements.schema.json"),
            ),
            (
                _V4,
                "V4 (missing from R only)",
                "config/ac_store_schema.json",
                ("config/test_requirements.schema.json", "test-writer.md"),
            ),
        ],
        ids=["V2_missing_from_G", "V3_missing_from_T", "V4_missing_from_R"],
    )
    def test_lockstep_comparator_fails_naming_list_that_lacks_discrimination(
        self, variant: dict, label: str, missing_list_marker: str, carrying_markers: tuple
    ) -> None:
        # covers: TQ-500f-1-i
        # angle: failure
        """WRONG VERSION THIS CATCHES (V2 specifically): 'compare only R
        with T (today's check)' — the AC's own named must_catch. Under that
        wrong version, R and T fully agree in V2 (G is never consulted), so
        the comparator would wrongly report zero mismatches for V2 — this
        assertion (non-empty result, naming G) is exactly the case today's
        check cannot make. V3/V4 are the sibling single-list-missing cases,
        completing full pairwise coverage of which list can go missing."""
        _compare_three_way_angle_sets, _load_generated_angles = _import_target_symbols()
        mismatches = _compare_three_way_angle_sets(
            variant["R"], variant["G"], variant["T"]
        )
        joined = "\n".join(mismatches)
        assert mismatches, f"{label}: comparator must report a mismatch, got none"
        assert "discrimination" in joined, (
            f"{label}: mismatch must name the specific angle 'discrimination':\n{joined}"
        )
        assert missing_list_marker in joined, (
            f"{label}: mismatch must name the list that LACKS the angle, by "
            f"file path ({missing_list_marker}):\n{joined}"
        )
        for carrier in carrying_markers:
            assert carrier in joined, (
                f"{label}: mismatch must also name the list(s) that CARRY the "
                f"angle, by file path ({carrier}):\n{joined}"
            )


class TestLockstepComparatorFailsOnStrayKindInGeneratedSideOnly:
    """angle: boundary — a kind present ONLY in G (never in R or T) must
    still fail, proving full-set equality rather than a subset check."""

    def test_lockstep_comparator_fails_on_stray_kind_in_generated_side_only(self) -> None:
        # covers: TQ-500f-1-i
        # angle: boundary
        """WRONG VERSION THIS CATCHES: 'subset instead of equality' (the
        AC's own named must_catch) — a comparator checking only "is
        everything in R/T also in G?" (subset) would silently accept a
        stray value that exists in G but nowhere else, because a superset
        of the required kinds still satisfies a subset check. Only full
        set-equality catches an extra, unrecognised value like
        'discriminating' leaking into G alone."""
        _compare_three_way_angle_sets, _load_generated_angles = _import_target_symbols()
        mismatches = _compare_three_way_angle_sets(
            _STRAY["R"], _STRAY["G"], _STRAY["T"]
        )
        joined = "\n".join(mismatches)
        assert mismatches, "a stray kind present only in G must be reported"
        assert "discriminating" in joined, (
            f"mismatch must name the specific stray value 'discriminating':\n{joined}"
        )
        assert "config/test_requirements.schema.json" in joined, (
            f"mismatch must name G (the list that carries the stray value) by "
            f"file path:\n{joined}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
