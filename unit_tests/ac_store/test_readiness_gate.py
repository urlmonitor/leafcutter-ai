"""
MODULE: test_readiness_gate
GOAL: Unit and integration tests for the readiness gate in goal_to_epic.py.
      Covers classify_readiness() (ACD-1200b-1, ACD-1200b-1-i) and the
      three-choice prompt routing (ACD-1200b-2) in the build-ac agent template.
TICKET: EPIC-GoalToEpic/02_readiness-gate.md
COVERS: ACD-1200b-1, ACD-1200b-1-i, ACD-1200b-2
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# These imports will fail (ImportError) until python-coder implements
# classify_readiness() in goal_to_epic.py — that is the intended red state.
from goal_to_epic import classify_readiness  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    readiness: str = "approved",
    covered_by: list[str] | None = None,
) -> Path:
    """Write a minimal AC YAML file with a readiness field and return its path."""
    subdir = ac_root / "ac-driven-dev" / "ACD-1200-goal-to-epic"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "readiness": readiness,
        "covered_by": covered_by if covered_by else [],
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests for classify_readiness() — ACD-1200b-1 (readiness report)
# ---------------------------------------------------------------------------


class TestClassifyReadiness:
    """Tests for the classify_readiness() function (ACD-1200b-1).

    classify_readiness(leaf_ids, store_root) -> dict must:
    - Accept a list of leaf AC IDs and the path to the AC store.
    - Read the 'readiness' field from each AC YAML (read-only).
    - Return a dict with keys:
        approved: list[str]          — IDs where readiness == "approved"
        unapproved: list[dict]       — IDs where readiness != "approved",
                                       each entry has {id: str, readiness: str}
    - Complete in <500ms for up to 100 leaves.
    - Not modify any files.
    """

    def test_ac1_classifies_mixed_leaf_set(self) -> None:
        # covers: ACD-1200b-1
        """AC-1: classify_readiness reads readiness field and classifies correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac(store_root, "ACD-050a-1", readiness="approved")
            _write_ac(store_root, "ACD-050a-2", readiness="approved")
            _write_ac(store_root, "ACD-050a-2-i", readiness="draft")
            _write_ac(store_root, "ACD-050b-1", readiness="reviewed")
            _write_ac(store_root, "ACD-050b-2", readiness="approved")

            leaf_ids = [
                "ACD-050a-1",
                "ACD-050a-2",
                "ACD-050a-2-i",
                "ACD-050b-1",
                "ACD-050b-2",
            ]

            result = classify_readiness(leaf_ids, store_root)

            assert "approved" in result, "Result must have 'approved' key"
            assert "unapproved" in result, "Result must have 'unapproved' key"
            assert sorted(result["approved"]) == sorted(
                ["ACD-050a-1", "ACD-050a-2", "ACD-050b-2"]
            ), "Three approved ACs expected"
            unapproved_ids = [entry["id"] for entry in result["unapproved"]]
            assert sorted(unapproved_ids) == sorted(
                ["ACD-050a-2-i", "ACD-050b-1"]
            ), "Two unapproved ACs expected"

    def test_ac1_unapproved_entry_has_readiness_field(self) -> None:
        # covers: ACD-1200b-1
        """Each unapproved entry must include the readiness value, not just the ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac(store_root, "ACD-050a-2-i", readiness="draft")
            _write_ac(store_root, "ACD-050b-1", readiness="reviewed")

            result = classify_readiness(["ACD-050a-2-i", "ACD-050b-1"], store_root)

            unapproved_map = {entry["id"]: entry["readiness"] for entry in result["unapproved"]}
            assert unapproved_map.get("ACD-050a-2-i") == "draft", (
                "Unapproved entry must carry its readiness value"
            )
            assert unapproved_map.get("ACD-050b-1") == "reviewed", (
                "Unapproved entry must carry its readiness value"
            )

    def test_ac1_performance_under_100_leaves(self) -> None:
        # covers: ACD-1200b-1
        """classify_readiness must complete in <500ms for up to 100 leaves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            leaf_ids = []
            for i in range(100):
                ac_id = f"ACD-PERF-{i:03d}"
                readiness = "approved" if i % 3 != 0 else "draft"
                _write_ac(store_root, ac_id, readiness=readiness)
                leaf_ids.append(ac_id)

            start = time.monotonic()
            classify_readiness(leaf_ids, store_root)
            elapsed_ms = (time.monotonic() - start) * 1000

            assert elapsed_ms < 500, (
                f"classify_readiness took {elapsed_ms:.1f}ms — must complete in <500ms"
            )

    def test_ac1_does_not_modify_any_files(self) -> None:
        # covers: ACD-1200b-1
        """classify_readiness must be read-only — no file modifications."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = _write_ac(store_root, "ACD-050a-1", readiness="approved")
            mtime_before = ac_path.stat().st_mtime

            classify_readiness(["ACD-050a-1"], store_root)

            mtime_after = ac_path.stat().st_mtime
            assert mtime_before == mtime_after, (
                "classify_readiness must not modify AC YAML files"
            )

    # --- All-approved fast-path (ACD-1200b-1-i) ---

    def test_ac2_all_approved_returns_empty_unapproved(self) -> None:
        # covers: ACD-1200b-1-i
        """AC-2: When all leaves are approved, unapproved list must be empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac(store_root, "ACD-050a-1", readiness="approved")
            _write_ac(store_root, "ACD-050a-2", readiness="approved")
            _write_ac(store_root, "ACD-050b-1", readiness="approved")

            result = classify_readiness(
                ["ACD-050a-1", "ACD-050a-2", "ACD-050b-1"], store_root
            )

            assert result["unapproved"] == [], (
                "When all leaves are approved, unapproved must be empty"
            )
            assert sorted(result["approved"]) == sorted(
                ["ACD-050a-1", "ACD-050a-2", "ACD-050b-1"]
            ), "All three ACs should be in approved"

    def test_ac2_all_approved_no_prompt_fast_path(self, capsys) -> None:
        # covers: ACD-1200b-1-i
        """AC-2: When all leaves are approved, no readiness report is displayed,
        and the system prints the fast-path confirmation message."""
        # This test verifies that goal_to_epic.run() or classify_readiness() outputs
        # the correct fast-path message when all ACs are approved and no prompt fires.
        # The production code must call classify_readiness() and, when unapproved is [],
        # print "All N leaf ACs are approved. Generating epic..." without a prompt.
        #
        # Since the function classify_readiness() is pure dict logic, this test
        # verifies that the all-approved fast-path branching logic in goal_to_epic.py
        # produces the correct output message. The integration point is tested via
        # the print-output assertion.
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            _write_ac(store_root, "ACD-050a-1", readiness="approved")
            _write_ac(store_root, "ACD-050a-2", readiness="approved")

            result = classify_readiness(["ACD-050a-1", "ACD-050a-2"], store_root)

            # When unapproved is empty, goal_to_epic.py should print the fast-path msg.
            # We test the trigger condition here; the output assertion is covered by the
            # integration test below (test_fast_path_prints_confirmation_message).
            assert result["unapproved"] == [], (
                "Caller must be able to detect all-approved condition from empty unapproved list"
            )


class TestFastPathOutput:
    """Tests for the all-approved fast-path print message (ACD-1200b-1-i).

    When all leaf ACs are approved, goal_to_epic.py must:
    - NOT display a readiness report
    - NOT show the approval prompt
    - Print: "All N leaf ACs are approved. Generating epic..."
    - Proceed directly to ticket generation
    """

    def test_fast_path_prints_confirmation_message(self, capsys) -> None:
        # covers: ACD-1200b-1-i
        """Fast-path: prints 'All N leaf ACs are approved. Generating epic...' """
        # Import the fast-path print helper — will fail until python-coder
        # implements it in goal_to_epic.py.
        from goal_to_epic import print_fast_path_message  # noqa: PLC0415

        print_fast_path_message(n=3)
        captured = capsys.readouterr()
        assert "All 3 leaf ACs are approved" in captured.out
        assert "Generating epic" in captured.out


# ---------------------------------------------------------------------------
# Integration tests for the three-choice prompt (ACD-1200b-2)
# ---------------------------------------------------------------------------


class TestThreeChoicePromptRouting:
    """Integration tests for the three-choice approval prompt (ACD-1200b-2).

    The readiness_gate_prompt() function in goal_to_epic.py must:
    - Present "Proceed with M approved ACs only? (yes / review-all / cancel)"
    - "yes" path: return only approved IDs
    - "review-all" path: dispatch IT PO v3 for unapproved ACs, re-read readiness,
      re-evaluate gate (re-present once if some remain unapproved after review)
    - "cancel" path: return None or raise a cancellation signal; no file writes
    """

    def test_ac3_yes_path_returns_only_approved_ids(self) -> None:
        # covers: ACD-1200b-2
        """AC-3 yes path: readiness_gate_prompt() returns only approved IDs."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        readiness_dict = {
            "approved": ["ACD-050a-1", "ACD-050a-2", "ACD-050b-2"],
            "unapproved": [
                {"id": "ACD-050a-2-i", "readiness": "draft"},
                {"id": "ACD-050b-1", "readiness": "reviewed"},
            ],
        }

        with patch("builtins.input", return_value="yes"):
            result = readiness_gate_prompt(readiness_dict, store_root=Path("."))

        assert result == ["ACD-050a-1", "ACD-050a-2", "ACD-050b-2"], (
            "'yes' path must return only the approved IDs"
        )

    def test_ac3_cancel_path_returns_no_ids(self) -> None:
        # covers: ACD-1200b-2
        """AC-3 cancel path: readiness_gate_prompt() returns None or empty (no writes)."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        readiness_dict = {
            "approved": ["ACD-050a-1"],
            "unapproved": [{"id": "ACD-050a-2-i", "readiness": "draft"}],
        }

        with patch("builtins.input", return_value="cancel"):
            result = readiness_gate_prompt(readiness_dict, store_root=Path("."))

        assert result is None or result == [], (
            "'cancel' path must return None or empty list — no epic generated"
        )

    def test_ac3_cancel_path_no_file_writes(self, tmp_path) -> None:
        # covers: ACD-1200b-2
        """AC-3 cancel path: no AC YAML files are modified on cancel."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        store_root = tmp_path / "ac-store"
        store_root.mkdir()
        ac_path = store_root / "ACD-050a-2-i.yaml"
        ac_path.write_text(yaml.dump({"id": "ACD-050a-2-i", "readiness": "draft"}))
        mtime_before = ac_path.stat().st_mtime

        readiness_dict = {
            "approved": [],
            "unapproved": [{"id": "ACD-050a-2-i", "readiness": "draft"}],
        }

        with patch("builtins.input", return_value="cancel"):
            readiness_gate_prompt(readiness_dict, store_root=store_root)

        mtime_after = ac_path.stat().st_mtime
        assert mtime_before == mtime_after, (
            "'cancel' path must not modify any AC YAML files"
        )

    def test_ac3_review_all_dispatches_it_po_v3(self) -> None:
        # covers: ACD-1200b-2
        """AC-3 review-all path: dispatches IT PO v3 for the unapproved ACs."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        readiness_dict = {
            "approved": ["ACD-050a-1"],
            "unapproved": [{"id": "ACD-050a-2-i", "readiness": "draft"}],
        }

        # After IT PO v3 runs, we simulate that it promoted ACD-050a-2-i to approved.
        # The re-read from disk shows it approved; gate re-evaluates and all are approved.
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            # Write ACD-050a-1 as approved
            subdir = store_root / "ac-driven-dev"
            subdir.mkdir(parents=True)
            (subdir / "ACD-050a-1.yaml").write_text(
                yaml.dump({"id": "ACD-050a-1", "readiness": "approved"})
            )
            # Write ACD-050a-2-i as draft initially; will be updated by mock IT PO v3
            (subdir / "ACD-050a-2-i.yaml").write_text(
                yaml.dump({"id": "ACD-050a-2-i", "readiness": "draft"})
            )

            def mock_it_po_v3_dispatch(unapproved_ids, store_root):
                """Simulate IT PO v3 promoting all unapproved ACs."""
                for ac_id in unapproved_ids:
                    for yaml_path in store_root.rglob(f"{ac_id}.yaml"):
                        data = yaml.safe_load(yaml_path.read_text())
                        data["readiness"] = "approved"
                        yaml_path.write_text(yaml.dump(data))

            # Simulate: user types "review-all", then IT PO v3 promotes all, then
            # the gate sees all approved and proceeds.
            with patch("builtins.input", side_effect=["review-all"]):
                with patch(
                    "goal_to_epic.dispatch_it_po_v3",
                    side_effect=mock_it_po_v3_dispatch,
                ) as mock_dispatch:
                    result = readiness_gate_prompt(
                        readiness_dict, store_root=store_root
                    )

            mock_dispatch.assert_called_once_with(
                ["ACD-050a-2-i"], store_root
            )
            # After promotion, all should be approved → result contains both IDs
            assert result is not None, (
                "review-all path must return a non-None result after promotion"
            )

    def test_ac3_review_all_re_reads_from_disk(self) -> None:
        # covers: ACD-1200b-2
        """AC-3 review-all path: re-reads readiness from disk (not cached state)."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        readiness_dict = {
            "approved": [],
            "unapproved": [{"id": "ACD-TEST-001", "readiness": "draft"}],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            ac_path = store_root / "ACD-TEST-001.yaml"
            ac_path.write_text(yaml.dump({"id": "ACD-TEST-001", "readiness": "draft"}))

            def promote_on_dispatch(unapproved_ids, sr):
                # Simulate IT PO v3 updating the file on disk
                ac_path.write_text(
                    yaml.dump({"id": "ACD-TEST-001", "readiness": "approved"})
                )

            with patch("builtins.input", side_effect=["review-all"]):
                with patch(
                    "goal_to_epic.dispatch_it_po_v3",
                    side_effect=promote_on_dispatch,
                ):
                    result = readiness_gate_prompt(readiness_dict, store_root=store_root)

            # After promotion and re-read from disk, ACD-TEST-001 is now approved
            # so the result should include it (or all-approved fast-path applies)
            assert result is not None, (
                "After review-all promotes ACs on disk, gate must proceed (not cancel)"
            )

    def test_ac3_review_all_re_presents_if_not_all_promoted(self) -> None:
        # covers: ACD-1200b-2
        """AC-3 review-all: if IT PO v3 does not promote all, re-presents report once."""
        from goal_to_epic import readiness_gate_prompt  # noqa: PLC0415

        readiness_dict = {
            "approved": ["ACD-050a-1"],
            "unapproved": [
                {"id": "ACD-050a-2-i", "readiness": "draft"},
                {"id": "ACD-050b-1", "readiness": "reviewed"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir)
            subdir = store_root / "ac-driven-dev"
            subdir.mkdir()
            # ACD-050a-1: approved
            (subdir / "ACD-050a-1.yaml").write_text(
                yaml.dump({"id": "ACD-050a-1", "readiness": "approved"})
            )
            # ACD-050a-2-i: will be promoted by IT PO v3
            (subdir / "ACD-050a-2-i.yaml").write_text(
                yaml.dump({"id": "ACD-050a-2-i", "readiness": "draft"})
            )
            # ACD-050b-1: will NOT be promoted (stays reviewed)
            (subdir / "ACD-050b-1.yaml").write_text(
                yaml.dump({"id": "ACD-050b-1", "readiness": "reviewed"})
            )

            def partial_promote(unapproved_ids, sr):
                # Only promote ACD-050a-2-i, leave ACD-050b-1 as reviewed
                for ac_id in unapproved_ids:
                    if ac_id == "ACD-050a-2-i":
                        for yaml_path in sr.rglob(f"{ac_id}.yaml"):
                            data = yaml.safe_load(yaml_path.read_text())
                            data["readiness"] = "approved"
                            yaml_path.write_text(yaml.dump(data))

            # User types "review-all" first, then after re-presentation types "yes"
            with patch("builtins.input", side_effect=["review-all", "yes"]):
                with patch(
                    "goal_to_epic.dispatch_it_po_v3",
                    side_effect=partial_promote,
                ):
                    result = readiness_gate_prompt(readiness_dict, store_root=store_root)

            # After re-presentation, user chose "yes" → only approved ACs returned
            # ACD-050a-1 and ACD-050a-2-i are approved; ACD-050b-1 stays unapproved
            assert result is not None, "After re-presentation and 'yes', must return approved IDs"
            assert "ACD-050b-1" not in (result or []), (
                "ACD-050b-1 was not promoted — must not be in the final approved set"
            )
