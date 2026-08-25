"""
MODULE: unit_tests/ac_store/test_bo_2900g_1.py
COVERS: BO-2900g-1

GOAL: The reachability-request floor must be attached at the ONE place a test
plan is finalised for a piece of work (``_build_test_requirements_section``),
not only on the criteria-derived fallback route. An AC that authors its own
``test_spec`` (the ~394-record population) must ALSO gain exactly one
``angle: reachability`` descriptor, with its authored entries preserved
unaltered and in order.

CURRENT STATE (2026-08-18): ``_build_test_requirements_section`` returns
``_test_descriptors_from_spec(...)`` verbatim whenever it is non-empty and
never calls ``_reachability_descriptor`` on that route — see
generate_ticket_from_ac.py, the early-return right after the spec-derived
descriptors are computed. These tests are RED against that behaviour.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"

sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from generate_ticket_from_ac import _build_test_requirements_section  # noqa: E402

TEST_ANGLE_REACHABILITY = "reachability"

# Same regex the production ticket guard uses to extract the fenced YAML block
# from ## Test Requirements — _build_test_requirements_section returns the
# FULL markdown section (heading + ```yaml fence), not raw YAML.
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_AUTHORED_SPEC_AC: dict = {
    "id": "ZZ-2900g-1-a",
    "assigned_agent": "python-coder",
    "criteria": "Given a thing\nWhen it happens\nThen the thing is recorded\n",
    "test_spec": [
        {"name": "test_alpha_first", "target_dir": "unit_tests/zz/", "description": "alpha"},
        {"name": "test_beta_second", "target_dir": "unit_tests/zz/", "description": "beta"},
        {"name": "test_gamma_third", "target_dir": "unit_tests/zz/", "description": "gamma"},
    ],
}


def _parse_tests(section_markdown: str) -> list[dict]:
    """Extract the ``tests:`` list from a ## Test Requirements section.

    Args:
        section_markdown: Full section text as returned by
            ``_build_test_requirements_section`` (heading + fenced YAML).

    Returns:
        The parsed list of test entry dicts.
    """
    match = _TESTS_BLOCK_RE.search(section_markdown)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{section_markdown[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list), (
        f"section did not parse to a tests list: {parsed!r}"
    )
    return [e for e in parsed["tests"] if isinstance(e, dict)]


class TestAuthoredSpecPlanGainsReachabilityRequest:
    def test_bo_2900g_1_authored_spec_plan_gains_reachability_request(self) -> None:
        # covers: BO-2900g-1
        """An authored 3-entry test_spec (none reachability) yields exactly one
        angle: reachability descriptor alongside the three authored ones."""
        ac = dict(_AUTHORED_SPEC_AC)
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)

        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]
        assert len(reach) == 1, (
            f"expected exactly one reachability descriptor appended to an "
            f"authored plan of 3 non-reachability entries, got {len(reach)}: "
            f"{entries}"
        )
        assert len(entries) == 4, entries

    def test_bo_2900g_1_authored_entries_survive_unaltered_and_in_order(self) -> None:
        # covers: BO-2900g-1
        """The three authored descriptors keep their authored order and fields;
        only the appended reachability entry is new."""
        ac = dict(_AUTHORED_SPEC_AC)
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)

        # Non-vacuous guard: without this, a route that appends NOTHING (the
        # current behaviour) trivially satisfies "authored order preserved"
        # simply because nothing was added. The floor must actually be
        # present for order-preservation to mean anything.
        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]
        assert len(reach) == 1, (
            f"order-preservation is only meaningful once the reachability "
            f"floor is actually appended; got {len(reach)} reachability "
            f"entries: {entries}"
        )

        authored_order = [item["name"] for item in ac["test_spec"]]
        non_reach_names = [
            e["name"] for e in entries if e.get("angle") != TEST_ANGLE_REACHABILITY
        ]
        assert non_reach_names == authored_order, (
            f"authored entries must survive unaltered and in order: "
            f"expected {authored_order}, got {non_reach_names}"
        )


class TestReachabilityFloorReachableViaGeneratorCli:
    def test_bo_2900g_1_reachability_floor_present_via_generator_cli(self) -> None:
        # covers: BO-2900g-1
        """PRODUCTION ENTRY POINT: run generate_ticket_from_ac.py as a
        subprocess against a real on-disk AC YAML that authors its own
        test_spec, then read the ticket file the CLI wrote and assert its
        ## Test Requirements block carries the reachability entry."""
        ac_id = _AUTHORED_SPEC_AC["id"]
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir) / "docs" / "acceptance-criteria"
            component_dir = ac_root / "fixture-component"
            component_dir.mkdir(parents=True)
            record = dict(_AUTHORED_SPEC_AC)
            record["title"] = "Fixture"
            record["component"] = "build-pipeline"
            record["components"] = ["build_pipeline"]
            record["status"] = "active"
            record["readiness"] = "approved"
            record["priority"] = "medium"
            record["level"] = "L2"
            record["work_status"] = "todo"
            (component_dir / f"{ac_id}.yaml").write_text(
                yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            tickets_root = Path(tmpdir) / "tickets"
            tickets_root.mkdir(parents=True)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_GEN_SCRIPT),
                    "--ac",
                    ac_id,
                    "--ac-root",
                    str(ac_root),
                    "--tickets-root",
                    str(tickets_root),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(_REPO_ROOT),
            )
            assert proc.returncode == 0, (
                f"generator CLI failed (exit {proc.returncode})\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
            written = list(tickets_root.rglob(f"*{ac_id.lower()}*.md")) or list(
                tickets_root.rglob("*.md")
            )
            assert written, f"generator CLI did not write a ticket file under {tickets_root}"
            ticket_text = written[0].read_text(encoding="utf-8")

        assert "reachability" in ticket_text, (
            "the ticket the CLI actually wrote must carry a reachability "
            f"descriptor in its ## Test Requirements block:\n{ticket_text[:2000]}"
        )


class TestNewPlanRouteInheritsFloorUnmodified:
    def test_bo_2900g_1_new_plan_route_inherits_floor_unmodified(self) -> None:
        # covers: BO-2900g-1
        """A THIRD descriptor-producing route (neither the criteria-derived
        fallback nor an authored test_spec) must still receive the floor when
        its output is piped through the real finalisation path, without that
        route being given any special-case knowledge of this rule.

        This models "introduce a third route" by handing
        _build_test_requirements_section an AC record that only the ROUTE
        itself would recognise (a hypothetical 'imported_spec' key) — since no
        such route exists in production today, we assert the general
        contract instead: ANY non-empty descriptor list returned ahead of the
        floor-adding step must still end up carrying exactly one reachability
        entry. Today _build_test_requirements_section has exactly two routes
        and neither the second (test_spec) inherits the floor, so this must
        fail identically to the authored-spec test above.
        """
        ac = {
            "id": "ZZ-2900g-1-b",
            "assigned_agent": "python-coder",
            "criteria": "Given a thing\nWhen it happens\nThen it is done\n",
            "test_spec": [
                {"name": "test_single_authored_entry", "target_dir": "unit_tests/zz/"},
            ],
        }
        section = _build_test_requirements_section(ac, ac["id"])
        entries = _parse_tests(section)
        reach = [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]
        assert len(reach) == 1, (
            "a plan-producing route other than the criteria-derived fallback "
            f"must still inherit the reachability floor: {entries}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
