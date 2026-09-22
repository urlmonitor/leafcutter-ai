"""
MODULE: unit_tests/ac_store/test_tkt_600b_5.py
GOAL: RED tests for TKT-600b-5 — an acceptance criterion whose ``assigned_agent``
      is null must be REFUSED by name, never generated into a ticket carrying a
      literal ``null`` phase and never crashed on with an undiagnosed TypeError.
BUSINESS CONTEXT: 355 records in the real store carry ``assigned_agent: null``.
      Today 317 of them silently produce ``null: needed`` in the agents map and a
      ``- [ ] None`` row in the Sign-offs checklist, and the other 38 die inside
      ``sorted()`` with ``'<' not supported between instances of 'str' and
      'NoneType'``. Both outcomes are wrong in the same direction: the generator
      must say which record is unauthored rather than emit a ticket nobody is
      assigned to build.
COVERS: TKT-600b-5
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

_GENERATOR = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"

#: Real store records, both shapes of the defect. ACD-1000a exercises the SILENT
#: path (one non-canonical agent, so sorted() never compares and None flows
#: straight through into the map); ACD-1100d exercises the CRASH path (a second
#: non-canonical agent joins None in the same sorted() call).
_REAL_NULL_AGENT_ACS = ("ACD-1000a", "ACD-1100d")


def _diagnosed_error():
    """Return the refusal exception type the fix must raise.

    Imported lazily so the RED run fails on the missing name with a readable
    message rather than at module import, which would take every test in the
    file down with it including the ones that must stay green.
    """
    import _gtfa_agents_map

    return _gtfa_agents_map.UnassignedWorkAgentError


class TestNullAssignedAgentIsRefused:
    def test_null_assigned_agent_is_refused_with_a_diagnosed_error(self) -> None:
        # covers: TKT-600b-5
        # angle: criterion
        """A null work agent on the computed path raises a diagnosed refusal.

        RED today: with change_targets/risk_surface supplied the computed path
        reaches ``_order_agents_map``, where ``sorted()`` either lets None
        through (one non-canonical agent) or raises an undiagnosed TypeError
        (two or more). Neither names the field that is unauthored.
        """
        with pytest.raises(_diagnosed_error()) as excinfo:
            _build_agents_map(
                None,
                change_targets=["code"],
                risk_surface="contract_boundary",
            )

        assert "assigned_agent" in str(excinfo.value), (
            "the refusal must name the offending FIELD so the author knows what "
            f"to fill in; got {str(excinfo.value)!r}"
        )

    def test_null_assigned_agent_is_refused_on_the_legacy_path_too(self) -> None:
        # covers: TKT-600b-5
        # angle: boundary
        """The legacy path (no change_targets, no risk_surface) refuses as well.

        This is the entry that goes red against a guard placed inside
        ``_order_agents_map`` instead of at the ``_build_agents_map`` entry
        point: the legacy path never calls the orderer, so such a guard would
        leave ``{None: 'needed'}`` reachable through the very branch that is
        documented as unable to refuse.
        """
        with pytest.raises(_diagnosed_error()) as excinfo:
            _build_agents_map(None)

        assert "assigned_agent" in str(excinfo.value)

    def test_named_assigned_agent_still_generates(self) -> None:
        # covers: TKT-600b-5
        # angle: boundary
        """A real agent name is unaffected — the guard must not refuse widely.

        Covers both the computed and the legacy path, and asserts no None key
        appears in either map.
        """
        computed = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
        )
        assert computed["python-coder"] == "needed"
        assert None not in computed

        legacy = _build_agents_map("python-coder")
        assert legacy["python-coder"] == "needed"
        assert None not in legacy

    @pytest.mark.parametrize("ac_id", _REAL_NULL_AGENT_ACS)
    def test_real_store_null_agent_record_refuses_through_the_cli(
        self, ac_id: str
    ) -> None:
        # covers: TKT-600b-5
        # angle: seam
        """Behavioural proof on the REAL store, in a fresh process.

        Runs the actual generator CLI over an actual on-disk record carrying
        ``assigned_agent: null`` — no synthetic fixture — and asserts a
        diagnosed, non-zero refusal that names the AC id and the field, with
        neither a ``null:`` agents entry nor a ``None`` sign-off row on stdout.
        """
        proc = subprocess.run(  # noqa: S603
            [sys.executable, str(_GENERATOR), "--ac", ac_id, "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(_REPO_ROOT),
        )

        assert proc.returncode != 0, (
            f"{ac_id} carries assigned_agent: null and must be refused; "
            f"the generator exited 0.\nstdout:\n{proc.stdout[:2000]}"
        )
        assert ac_id in proc.stderr, (
            f"the refusal must name the offending AC id; stderr was:\n{proc.stderr}"
        )
        assert "assigned_agent" in proc.stderr, (
            f"the refusal must name the offending field; stderr was:\n{proc.stderr}"
        )
        assert "Traceback" not in proc.stderr, (
            "a traceback is a crash, not a diagnosed refusal; stderr was:\n"
            f"{proc.stderr}"
        )
        assert "null: " not in proc.stdout, (
            "a literal null phase must never reach the generated agents map"
        )
        assert "- [ ] None" not in proc.stdout, (
            "a None sign-off row must never reach the generated ticket body"
        )
