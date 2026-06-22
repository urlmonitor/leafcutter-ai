"""
MODULE: test_scan_ac_store_cycle
GOAL: Unit tests for ACD-1200c-3: dependency cycle in one subtree degrades
      the store-wide scan to a WARNING (exit 0), while a genuine intra-scope
      cycle in a scoped build still hard-fails via CyclicDependencyError.
TICKET: EPIC-GoalToEpicLeafFilter/02_TICKET-20260622-ACD-1200c-3.md
COVERS: ACD-1200c-3
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup — import from the worktree's scripts/ directories
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_AC_STORE_SCRIPTS_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import main as scan_main  # noqa: E402
from goal_to_epic import CyclicDependencyError, topological_sort  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str = "L2",
    depends_on: list[str] | None = None,
    covered_by: list[str] | None = None,
    work_status: str = "todo",
    status: str = "active",
    readiness: str = "approved",
) -> Path:
    """Write a minimal AC YAML file into *ac_root* and return its path.

    Files are written into a subdirectory derived from the first two dash-
    separated components of *ac_id* (e.g. BO-1100a-3 → ac_root/BO-1100/).
    """
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, Any] = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": level,
        "status": status,
        "readiness": readiness,
        "work_status": work_status,
        "covered_by": covered_by if covered_by is not None else [],
        "estimated_complexity": "M",
        "priority": "medium",
        "assigned_agent": "python-coder",
    }
    if depends_on is not None:
        data["depends_on"] = depends_on
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ACD-1200c-3: store-wide cycle degrades to warning (exit 0)
# ---------------------------------------------------------------------------


class TestScanAcStoreCycleDegradesToWarning:
    """ACD-1200c-3: When a dependency cycle is confined to one component
    subtree, the store-wide scan must NOT hard-abort. It must surface the
    cycle as a WARNING and continue, exiting with status 0.
    """

    def test_scan_ac_store_cycle_degrades_to_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # covers: ACD-1200c-3
        """ACD-1200c-3: Store-wide scan with a subtree cycle must exit 0 (not 2).

        Set up a store where:
        - BO-1100a-3 depends_on BO-1100d-1 (creating a cycle with BO-1100d-1)
        - BO-1100d-1 depends_on BO-1100a-3
        - BO-1100x-1 is an isolated, acyclic, ready AC

        The scan must NOT raise or return exit code 2.
        It must surface the cycle as a WARNING (not ERROR) to stderr.
        It must exit 0.

        This test will FAIL (exit 2) until ACD-1200c-3 is implemented because
        the current scan_ac_store.main() hard-aborts with exit code 2 on any cycle.
        """
        # Set up: two ACs forming a cycle
        _write_ac(tmp_path, "BO-1100a-3", depends_on=["BO-1100d-1"])
        _write_ac(tmp_path, "BO-1100d-1", depends_on=["BO-1100a-3"])
        # One isolated acyclic AC
        _write_ac(tmp_path, "BO-1100x-1", depends_on=[])

        exit_code = scan_main(["--ac-root", str(tmp_path), "--json"])

        captured = capsys.readouterr()

        # The scan MUST exit 0 (not 2) when cycle is outside requested scope
        assert exit_code == 0, (
            f"scan_ac_store should exit 0 when cycle is a warning, got: {exit_code}. "
            f"stderr: {captured.err!r}"
        )

        # The cycle must be surfaced as a WARNING on stderr (not ERROR)
        assert "WARNING" in captured.err or "warning" in captured.err.lower(), (
            f"Expected WARNING on stderr for cyclic ACs, got: {captured.err!r}"
        )

        # The warning must name the cyclic AC IDs
        assert "BO-1100a-3" in captured.err or "BO-1100d-1" in captured.err, (
            f"WARNING must name the cyclic AC IDs, got: {captured.err!r}"
        )

    def test_scan_ac_store_acyclic_remainder_ranked_after_cycle(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # covers: ACD-1200c-3
        """ACD-1200c-3: Acyclic ACs still appear in the ranked output despite a cycle.

        Even when a subtree cycle exists, the non-cyclic ACs must be ranked
        and emitted in the JSON output (the "ready" list must be non-empty).

        This test will FAIL until ACD-1200c-3 is implemented because the current
        implementation hard-aborts (exit 2) before any ACs are ranked.
        """
        # Cyclic pair
        _write_ac(tmp_path, "BO-1100a-3", depends_on=["BO-1100d-1"])
        _write_ac(tmp_path, "BO-1100d-1", depends_on=["BO-1100a-3"])
        # Acyclic AC that should appear in ready output
        _write_ac(tmp_path, "BO-1100x-1", depends_on=[])

        exit_code = scan_main(["--ac-root", str(tmp_path), "--json"])

        captured = capsys.readouterr()

        # Exit 0 is required
        assert exit_code == 0, (
            f"Expected exit 0 but got {exit_code}. stderr: {captured.err!r}"
        )

        # The JSON output must be non-empty and contain the acyclic AC
        import json
        output = json.loads(captured.out)
        ready_ids = [item["ac_id"] for item in output.get("ready", [])]
        assert "BO-1100x-1" in ready_ids, (
            f"Acyclic AC BO-1100x-1 must appear in ready output. "
            f"Got ready: {ready_ids!r}. stdout: {captured.out!r}"
        )


# ---------------------------------------------------------------------------
# ACD-1200c-3 (scoped build): intra-scope cycle still hard-fails
# ---------------------------------------------------------------------------


class TestTopologicalSortIntraScopeCycleHardFails:
    """ACD-1200c-3 (scoped build guard): When a goal-scoped run's OWN leaf set
    contains an intra-epic dependency cycle, topological_sort() in
    goal_to_epic.py must STILL raise CyclicDependencyError.

    The ACD-1200c-1-i pre-write guard must NOT be weakened by the cycle-
    degrades-to-warning change.
    """

    def test_topological_sort_raises_on_intra_scope_cycle(self) -> None:
        # covers: ACD-1200c-3
        """ACD-1200c-3 (scoped): intra-scope cycle must still raise CyclicDependencyError.

        A cycle within the scoped leaf set (the ACs being built in the current
        epic) must still be a hard failure. topological_sort() must raise
        CyclicDependencyError when its dep_graph contains a cycle.

        This test verifies that the scoped pre-write guard (ACD-1200c-1-i) is
        NOT weakened by the ACD-1200c-3 store-wide warning behaviour.

        This test is expected to be GREEN immediately (topological_sort already
        raises CyclicDependencyError). It is here to ensure no regression occurs
        when ACD-1200c-3 is implemented — i.e., the scoped guard must remain intact.
        """
        # Two ACs forming a cycle within the scoped build's leaf set
        dep_graph = {
            "ACD-050a-1": ["ACD-050a-2"],
            "ACD-050a-2": ["ACD-050a-1"],
        }
        with pytest.raises(CyclicDependencyError) as exc_info:
            topological_sort(dep_graph)

        exc_str = str(exc_info.value)
        # Error message must name the cyclic ACs
        assert "ACD-050a-1" in exc_str or "ACD-050a-2" in exc_str, (
            f"CyclicDependencyError must name the involved ACs. Got: {exc_str!r}"
        )
        # Error message must use clear language
        assert any(kw in exc_str for kw in ["Circular", "cycle", "circular"]), (
            f"CyclicDependencyError must say 'Circular dependency' or 'cycle'. Got: {exc_str!r}"
        )


# ---------------------------------------------------------------------------
# ACD-1200c-3: live fixture — real store cycle is a warning, not abort
# ---------------------------------------------------------------------------


class TestRealStoreCycleIsWarning:
    """ACD-1200c-3: Uses the real AC store to confirm that the pre-existing
    BO-1100a-3 <-> BO-1100d-1 cycle is surfaced as a WARNING (not a hard abort).
    """

    _REAL_AC_STORE = (
        Path(__file__).resolve().parent.parent.parent
        / "docs"
        / "acceptance-criteria"
    )

    def test_real_store_cycle_bo1100_is_warning_not_abort(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # covers: ACD-1200c-3
        """ACD-1200c-3: Real store — BO-1100a-3 <-> BO-1100d-1 cycle must be a WARNING.

        The real AC store contains a pre-existing dependency cycle:
          BO-1100a-3  depends_on  BO-1100d-1
          BO-1100d-1  depends_on  BO-1100a-3

        The store-wide scan must:
        1. NOT hard-abort (exit 0, not 2).
        2. Emit a WARNING to stderr naming the cyclic IDs.
        3. Still rank and return at least some non-cyclic ACs.

        This test will FAIL until ACD-1200c-3 is implemented (currently exits 2).

        MANUAL note: requires docs/acceptance-criteria/ to be populated with real
        AC YAMLs. Runs against the live store on disk.
        """
        if not self._REAL_AC_STORE.exists():
            pytest.xfail(f"Real AC store not found at {self._REAL_AC_STORE} — live fixture unavailable")

        exit_code = scan_main(["--ac-root", str(self._REAL_AC_STORE), "--json"])

        captured = capsys.readouterr()

        # Must exit 0 — cycle degrades to warning, not fatal error
        assert exit_code == 0, (
            f"scan_ac_store should exit 0 for a store with a subtree cycle. "
            f"Got exit code: {exit_code}. stderr: {captured.err!r}"
        )

        # Must emit a WARNING (not ERROR) to stderr
        assert "WARNING" in captured.err or "warning" in captured.err.lower(), (
            f"Expected WARNING on stderr for the BO-1100 cycle. "
            f"stderr: {captured.err!r}"
        )

        # The warning must name at least one of the cyclic AC IDs
        assert "BO-1100" in captured.err, (
            f"WARNING must mention the BO-1100 cyclic ACs. stderr: {captured.err!r}"
        )

        # At least some ACs must be ranked (output is non-empty)
        import json
        try:
            output = json.loads(captured.out)
        except json.JSONDecodeError:
            pytest.fail(
                f"Expected valid JSON output after graceful cycle handling. "
                f"stdout: {captured.out!r}"
            )

        total_acs = len(output.get("ready", [])) + len(output.get("blocked", []))
        assert total_acs > 0, (
            f"Expected at least some ACs ranked in the output after graceful cycle handling. "
            f"Output: {output!r}"
        )
