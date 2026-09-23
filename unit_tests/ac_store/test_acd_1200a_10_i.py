"""
MODULE: unit_tests/ac_store/test_acd_1200a_10_i.py
GOAL: Tests for ACD-1200a-10-i — a goal whose every leaf is done or superseded
      must yield an empty leaf set and route into the zero-leaf error path with
      a message that says WHY (all leaves excluded as done/superseded), rather
      than assembling an empty epic or reusing the generic
      "decompose the L1s first" wording that belongs to ACD-1200a-3-i.
COVERS: ACD-1200a-10-i

Tree fixtures used below (mirror the Gherkin exactly):

    ACD-080          L0  covered_by: [ACD-080a]
    ACD-080a         L1  covered_by: [ACD-080a-1, ACD-080a-2, ACD-080a-3]
    ACD-080a-1       L2  status: active,         work_status: done
    ACD-080a-2       L2  status: superseded_by,  superseded_by: [ACD-080a-3]
    ACD-080a-3       L2  status: active,         work_status: done

    ACD-081          L0  covered_by: [ACD-081a]        <- the CONTRAST goal
    ACD-081a         L1  covered_by: []                   (structurally leaf-less,
                                                            i.e. the ACD-1200a-3-i case)

Both goals produce an empty leaf set, but for different reasons, and the AC
requires the user-visible message to tell them apart.

RED expectation at authoring time (2026-09-14): the leaf-collection half is
already implemented (traverse_ac_tree's default exclusion flags land ACD-1200a-10),
so the empty-list and no-folder tests pass. The message half is NOT: the guard in
epic_ac_phases._collect_leaf_ids prints one unconditional string,
"No leaf-level ACs found beneath {ac_id}. Decompose the L1s into L2/L3 ACs first.",
for both shapes — so the message and discriminating tests fail.

NOTE ON PATCHING: these tests patch nothing. They build a real AC store on disk
and invoke the real epic_pipeline.run(). Per the 2026-09-14 decomposition, the
owning sibling module is epic_pipeline / epic_ac_phases — patching
"goal_to_epic.<name>" would not intercept anything, because each name is defined
and called inside its own sibling and resolved through that module's globals.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from epic_pipeline import run as epic_pipeline_run  # noqa: E402
from scan_ac_store import traverse_ac_tree  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    level: str,
    *,
    status: str = "active",
    work_status: str = "todo",
    covered_by: list[str] | None = None,
    superseded_by: list[str] | None = None,
) -> Path:
    """Write one AC YAML file into *ac_root* via the real serializer.

    The bytes on disk are produced by ``yaml.dump`` — the same serializer the
    store itself is written with — never a hand-typed literal, so the loader
    under test sees the real on-disk format.

    Args:
        ac_root: Root directory of the throwaway AC store.
        ac_id: The AC id, also used to derive the component subdirectory.
        level: AC flight level (``L0``/``L1``/``L2``/``L3``).
        status: The ``status`` field value.
        work_status: The ``work_status`` field value.
        covered_by: Child AC ids, or ``None`` for an empty list.
        superseded_by: Replacement AC ids, omitted from the record when ``None``.

    Returns:
        Path: The written YAML file.
    """
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "level": level,
        "status": status,
        "work_status": work_status,
        "covered_by": covered_by if covered_by is not None else [],
    }
    if superseded_by is not None:
        data["superseded_by"] = superseded_by
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_all_done_or_superseded_goal(ac_root: Path) -> None:
    """Populate *ac_root* with the ACD-080 goal whose every leaf is filtered out.

    Args:
        ac_root: Root directory of the throwaway AC store.
    """
    _write_ac(ac_root, "ACD-080", "L0", covered_by=["ACD-080a"])
    _write_ac(
        ac_root,
        "ACD-080a",
        "L1",
        covered_by=["ACD-080a-1", "ACD-080a-2", "ACD-080a-3"],
    )
    _write_ac(ac_root, "ACD-080a-1", "L2", status="active", work_status="done")
    _write_ac(
        ac_root,
        "ACD-080a-2",
        "L2",
        status="superseded_by",
        work_status="todo",
        superseded_by=["ACD-080a-3"],
    )
    _write_ac(ac_root, "ACD-080a-3", "L2", status="active", work_status="done")


def _build_structurally_leafless_goal(ac_root: Path) -> None:
    """Populate *ac_root* with the ACD-081 goal that has no L2/L3 leaves at all.

    This is the ACD-1200a-3-i shape — an undecomposed goal — and exists here
    only so the two zero-leaf causes can be compared.

    Args:
        ac_root: Root directory of the throwaway AC store.
    """
    _write_ac(ac_root, "ACD-081", "L0", covered_by=["ACD-081a"])
    _write_ac(ac_root, "ACD-081a", "L1", covered_by=[])


def _make_inbox(tmp_path: Path, name: str = "00_inbox") -> Path:
    """Create and return a throwaway tickets-inbox directory.

    Args:
        tmp_path: pytest-provided temporary directory.
        name: Leaf directory name for the inbox.

    Returns:
        Path: The created inbox directory.
    """
    inbox_dir = tmp_path / "tickets" / name
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def _run_goal_expecting_exit(goal_id: str, ac_root: Path, inbox_dir: Path) -> SystemExit:
    """Invoke the real goal-mode pipeline and return the SystemExit it raised.

    Args:
        goal_id: The goal AC id to build an epic from.
        ac_root: Root directory of the throwaway AC store.
        inbox_dir: Throwaway tickets inbox root.

    Returns:
        SystemExit: The exception the zero-leaf guard raised.
    """
    with pytest.raises(SystemExit) as exc_info:
        epic_pipeline_run(ac_id=goal_id, ac_store_root=ac_root, inbox_dir=inbox_dir)
    return exc_info.value


# ---------------------------------------------------------------------------
# ACD-1200a-10-i
# ---------------------------------------------------------------------------


class TestAllDoneOrSupersededGoalYieldsZeroLeafError:
    """ACD-1200a-10-i: leaves exist but are all excluded — the goal is complete."""

    def test_acd_1200a_10_i_all_done_or_superseded_yields_empty_leaf_set(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-10-i
        # angle: criterion
        """Leaf collection with the DEFAULT exclusion flags returns an empty list.

        Every L2 beneath ACD-080 is either ``work_status: done`` (a-1, a-3) or
        ``status: superseded_by`` (a-2), so the default
        ``exclude_done``/``exclude_superseded`` filters remove all three.
        """
        ac_root = tmp_path / "acs"
        _build_all_done_or_superseded_goal(ac_root)

        result = traverse_ac_tree("ACD-080", ac_root)

        assert result == [], (
            "Every leaf beneath ACD-080 is done or superseded, so the "
            f"default-filtered leaf set must be empty. Got: {result}"
        )

    def test_acd_1200a_10_i_zero_leaf_error_fires_with_all_done_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # covers: ACD-1200a-10-i
        # angle: criterion
        """The zero-leaf path fires and its message states WHY no leaves remain.

        The run must exit non-zero, name the goal, and say that the buildable
        leaves were excluded because they are done or superseded. Asserting only
        "some error was raised" is not enough — the wording is what tells the
        user the goal is complete/retired rather than undecomposed.
        """
        ac_root = tmp_path / "acs"
        _build_all_done_or_superseded_goal(ac_root)
        inbox_dir = _make_inbox(tmp_path)

        exit_exc = _run_goal_expecting_exit("ACD-080", ac_root, inbox_dir)
        message = capsys.readouterr().err.lower()

        assert exit_exc.code != 0, (
            "A fully-completed goal must exit non-zero so it never silently "
            f"produces an empty epic. Got exit code: {exit_exc.code!r}"
        )
        assert "acd-080" in message, (
            f"The zero-leaf message must name the goal AC. Got: {message!r}"
        )
        assert "done" in message, (
            "The message must state that leaves were excluded because they are "
            f"done. Got: {message!r}"
        )
        assert "superseded" in message, (
            "The message must state that leaves were excluded because they are "
            f"superseded. Got: {message!r}"
        )

    def test_acd_1200a_10_i_no_epic_folder_is_created(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10-i
        # angle: criterion
        """No epic folder exists on disk after the run.

        The guard must fire before ANY directory is created, so this asserts
        absence of the folder (and of the ``epics/`` parent), not emptiness —
        an implementation that mkdirs first and bails afterwards fails here.
        """
        ac_root = tmp_path / "acs"
        _build_all_done_or_superseded_goal(ac_root)
        inbox_dir = _make_inbox(tmp_path)

        _run_goal_expecting_exit("ACD-080", ac_root, inbox_dir)

        epics_dir = inbox_dir / "epics"
        assert not epics_dir.exists(), (
            "The zero-leaf guard must fire before any filesystem write, so the "
            f"epics/ directory must not exist. Found: {sorted(epics_dir.rglob('*'))}"
        )
        created = sorted(p.name for p in inbox_dir.iterdir())
        assert created == [], (
            f"No files or folders may be written to the inbox. Found: {created}"
        )

    def test_acd_1200a_10_i_differs_from_structurally_leafless_goal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # covers: ACD-1200a-10-i
        # angle: boundary
        """The all-excluded message must differ from the undecomposed-goal message.

        ACD-080's leaves exist but are all filtered out (the goal is finished);
        ACD-081 has no L2/L3 descendants at all (the goal is undecomposed —
        ACD-1200a-3-i). Both exit non-zero, but an implementation that collapses
        them into one generic string leaves the user unable to tell "already
        built" from "not yet specified". That implementation passes the other
        three tests in this file and fails this one.
        """
        ac_root = tmp_path / "acs"
        _build_all_done_or_superseded_goal(ac_root)
        _build_structurally_leafless_goal(ac_root)

        _run_goal_expecting_exit("ACD-080", ac_root, _make_inbox(tmp_path, "inbox_done"))
        all_done_message = capsys.readouterr().err.strip()

        _run_goal_expecting_exit("ACD-081", ac_root, _make_inbox(tmp_path, "inbox_leafless"))
        leafless_message = capsys.readouterr().err.strip()

        assert all_done_message, "The all-done goal must emit a diagnostic message"
        assert leafless_message, "The leaf-less goal must emit a diagnostic message"
        assert all_done_message != leafless_message, (
            "A goal whose leaves are all done/superseded must be distinguishable "
            "from a structurally leaf-less goal, but both printed the identical "
            f"message: {all_done_message!r}"
        )
        assert "decompose" not in all_done_message.lower(), (
            "ACD-080's leaves are already decomposed — telling the user to "
            "decompose the L1s is the wrong remedy and is ACD-1200a-3-i's "
            f"wording, not this one's. Got: {all_done_message!r}"
        )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [ACD-1200a-10-i/test-writer]: Initial tests, authored from the AC's
  four test_spec descriptors. Two of the four are green on arrival because
  ACD-1200a-10's default exclusion flags already make the leaf set empty and the
  existing guard already exits before any write; the message and discriminating
  tests are RED because epic_ac_phases._collect_leaf_ids prints a single
  unconditional "Decompose the L1s into L2/L3 ACs first." for both zero-leaf
  causes. Nothing is patched: the tests build a real AC store with yaml.dump and
  invoke the real epic_pipeline.run(), so the post-decomposition patch hazard
  (patching the goal_to_epic facade intercepts nothing) does not apply.
====================================================================
"""
