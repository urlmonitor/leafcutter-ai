"""
MODULE: unit_tests/ac_store/test_bo_2900g_1_i.py
COVERS: BO-2900g-1-i

GOAL: Once BO-2900g-1 makes the reachability floor universal, the append
must be a DE-DUPE, not a blind append. An authored plan that already
carries one ``angle: reachability`` entry must keep exactly one (its own
text, not the generic sentinel); a plan without one must gain exactly one
sentinel entry; no plan may ever end up with two.

CURRENT STATE (2026-08-18): There is no floor-append logic on the
authored-test_spec route at all (see test_bo_2900g_1.py), so
``_build_test_requirements_section`` cannot yet dedupe anything — these
tests are RED (either 0 reachability entries where 1 is expected, or the
count-across-N-authored-entries boundary check fails).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from generate_ticket_from_ac import _build_test_requirements_section  # noqa: E402

TEST_ANGLE_REACHABILITY = "reachability"

_SENTINEL_MARKER = "not declared"

# Same regex the production ticket guard uses to extract the fenced YAML block
# from ## Test Requirements — _build_test_requirements_section returns the
# FULL markdown section (heading + ```yaml fence), not raw YAML.
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _parse_tests(section_markdown: str) -> list[dict]:
    match = _TESTS_BLOCK_RE.search(section_markdown)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{section_markdown[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list)
    return [e for e in parsed["tests"] if isinstance(e, dict)]


class TestAuthoredReachabilityRequestIsNotDuplicated:
    def test_bo_2900g_1_i_authored_reachability_request_is_not_duplicated(self) -> None:
        # covers: BO-2900g-1-i
        """An AC whose test_spec already contains a reachability entry naming
        an entry point yields exactly one such entry, with the author's text
        preserved — not the generic sentinel."""
        ac = {
            "id": "ZZ-2900g-1-i-a",
            "assigned_agent": "python-coder",
            "criteria": "Given a thing\nWhen it happens\nThen it is recorded\n",
            "test_spec": [
                {
                    "name": "test_reachable_via_named_cli",
                    "target_dir": "unit_tests/zz/",
                    "angle": "reachability",
                    "description": "Run `scripts/zz/run.py --do-thing` as a subprocess.",
                },
            ],
        }
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)
        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]

        assert len(reach) == 1, (
            f"authored reachability entry must not be duplicated: {entries}"
        )
        assert "run.py" in str(reach[0].get("asserts", "")), (
            "the author's own entry-point text must survive verbatim, not be "
            f"overwritten by the not-declared sentinel: {reach[0]!r}"
        )

        # Non-vacuous guard: "no duplicate appended" is trivially true today
        # because NOTHING is ever appended on the authored-spec route (see
        # test_bo_2900g_1.py). Prove the floor-append machinery is actually
        # active by checking its sibling case in the SAME assertion: a
        # twin AC with no authored reachability entry must gain exactly one.
        # Without this, a no-op implementation passes the assertions above
        # for the wrong reason.
        twin_ac = {
            "id": "ZZ-2900g-1-i-a-twin",
            "assigned_agent": "python-coder",
            "criteria": ac["criteria"],
            "test_spec": [{"name": "test_no_reachability_authored", "target_dir": "unit_tests/zz/"}],
        }
        twin_entries = _parse_tests(
            _build_test_requirements_section(twin_ac, twin_ac["id"])
        )
        twin_reach = [e for e in twin_entries if e.get("angle") == TEST_ANGLE_REACHABILITY]
        assert len(twin_reach) == 1, (
            "the floor-append machinery must be active (a plan with NO "
            "authored reachability entry must gain exactly one) — otherwise "
            "'no duplication' above is true only because nothing is ever "
            f"appended: {twin_entries}"
        )


class TestPlanWithoutRequestGainsExactlyOneSentinelEntry:
    def test_bo_2900g_1_i_plan_without_request_gains_exactly_one_sentinel_entry(
        self,
    ) -> None:
        # covers: BO-2900g-1-i
        """An AC whose test_spec has no reachability entry gains exactly one,
        carrying the not-declared sentinel, and no entry of any other angle."""
        ac = {
            "id": "ZZ-2900g-1-i-b",
            "assigned_agent": "python-coder",
            "criteria": "Given a thing\nWhen it happens\nThen it is recorded\n",
            "test_spec": [
                {"name": "test_only_authored_entry", "target_dir": "unit_tests/zz/"},
            ],
        }
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)
        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]

        assert len(reach) == 1, entries
        assert _SENTINEL_MARKER in str(reach[0].get("asserts", "")).lower(), (
            f"gained entry must carry the not-yet-resolved sentinel: {reach[0]!r}"
        )
        angles_seen = {e.get("angle") for e in entries if e.get("angle")}
        assert angles_seen <= {TEST_ANGLE_REACHABILITY} | {None}, entries


class TestReachabilityEntryCountAcrossZeroOneAndTwoAuthored:
    @pytest.mark.parametrize("n_authored_reachability", [0, 1, 2])
    def test_bo_2900g_1_i_reachability_entry_count_is_one_across_zero_one_and_two_authored(
        self, n_authored_reachability: int
    ) -> None:
        # covers: BO-2900g-1-i
        """0 -> gains one; 1 -> stays one; 2 (pathological, hand-authored twice)
        -> stays two-unchanged. The rule adds, never removes, and never adds a
        second."""
        test_spec = [{"name": "test_baseline", "target_dir": "unit_tests/zz/"}]
        for i in range(n_authored_reachability):
            test_spec.append(
                {
                    "name": f"test_reach_{i}",
                    "target_dir": "unit_tests/zz/",
                    "angle": "reachability",
                }
            )
        ac = {
            "id": f"ZZ-2900g-1-i-c{n_authored_reachability}",
            "assigned_agent": "python-coder",
            "criteria": "Given a thing\nWhen it happens\nThen it is recorded\n",
            "test_spec": test_spec,
        }
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)
        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]

        expected = max(n_authored_reachability, 1)
        assert len(reach) == expected, (
            f"with {n_authored_reachability} authored reachability entries, "
            f"expected {expected} after finalisation, got {len(reach)}: {entries}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
