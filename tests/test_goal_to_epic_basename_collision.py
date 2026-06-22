"""
MODULE: test_goal_to_epic_basename_collision
GOAL: Verify ACD-1200a-9-i — basename collision resolution inside the EPIC
    folder. When a generated ticket's computed basename already exists at the
    epic-folder path, the system must overwrite the existing file in place,
    emit a WARNING, and leave exactly one file with that basename at the
    epic-folder path.

BUSINESS CONTEXT: Implements the test coverage required by ticket
    02_basename_collision_resolution.md (EPIC-GoalToEpicBugfixes). Ensures
    re-runs converge on exactly one ticket file per leaf AC and never create a
    renamed sibling or a second copy at the inbox root.

ARCHITECTURE: Pure unit tests using unittest.TestCase + unittest.mock.
    No database. No network. Uses tempfile.TemporaryDirectory for all
    filesystem writes. Must complete in < 5 seconds.

Tests in this file:
  - test_acd_1200a_9i_in_place_overwrite_on_collision
  - test_acd_1200a_9i_no_second_location_copy
  - test_acd_1200a_9i_single_file_after_run
  - test_acd_1200a_9i_warning_emitted_on_overwrite
  - test_acd_1200a_9i_implemented_by_after_collision
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load goal_to_epic from the worktree scripts/ directory.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_GOAL_TO_EPIC_PATH = _SCRIPTS_DIR / "goal_to_epic.py"


def _load_goal_to_epic():
    """Load goal_to_epic from scripts/ into sys.modules (idempotent)."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))

    module_name = "goal_to_epic"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, _GOAL_TO_EPIC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(path: Path, content: str = "ticket content") -> Path:
    """Write a minimal ticket file at *path* and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBasenameCollisionResolution(unittest.TestCase):
    """ACD-1200a-9-i: in-place overwrite when a basename collides inside the epic folder.

    The epic_name passed to assemble_epic_folder() uses hyphen-separated words
    (e.g. "validate-input-schema") so that _to_pascal_case() produces a
    deterministic PascalCase result ("ValidateInputSchema") that we can match
    against the pre-created test fixture.  Passing already-PascalCase strings
    (e.g. "ValidateInputSchema") through _to_pascal_case() collapses interior
    capitals via str.capitalize(), producing "Validateinputschema" — a mismatch.
    """

    #: Hyphen-separated epic name passed to assemble_epic_folder().
    #: _to_pascal_case("validate-input-schema") → "ValidateInputSchema".
    EPIC_NAME_HYPHEN = "validate-input-schema"
    #: The PascalCase result expected by _to_pascal_case().
    EPIC_NAME_PASCAL = "ValidateInputSchema"

    def setUp(self) -> None:
        self._goal_to_epic = _load_goal_to_epic()
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self._inbox_dir = self._tmp_path / "tickets" / "00_inbox"
        self._inbox_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_source_ticket(self, filename: str, content: str = "original") -> Path:
        """Create a source ticket file in the inbox root."""
        source_path = self._inbox_dir / filename
        return _make_ticket(source_path, content)

    def _pre_create_epic_folder_with_file(
        self, pascal_name: str, prefixed_filename: str, content: str = "prior content"
    ) -> Path:
        """Pre-create the epic folder with a file that will collide on the next run.

        Args:
            pascal_name: The PascalCase folder name (e.g. "ValidateInputSchema").
            prefixed_filename: The numbered filename inside the folder (e.g.
                "01_validate-input-schema.md").
            content: Content to write into the pre-existing file.

        Returns:
            Path to the created epic folder.
        """
        epics_dir = self._inbox_dir / "epics"
        epic_folder = epics_dir / f"EPIC-{pascal_name}"
        epic_folder.mkdir(parents=True, exist_ok=True)
        prior_file = epic_folder / prefixed_filename
        _make_ticket(prior_file, content)
        return epic_folder

    # -----------------------------------------------------------------------
    # Test 1: In-place overwrite on collision
    # -----------------------------------------------------------------------

    def test_acd_1200a_9i_in_place_overwrite_on_collision(self) -> None:
        """ACD-1200a-9-i: existing epic-folder file is overwritten in place.

        Given the epic folder already contains 01_validate-input-schema.md
        with prior content, and the new source ticket has updated content,
        When assemble_epic_folder() is called with epic_name="validate-input-schema",
        Then the destination file contains the updated content (not the prior),
        confirming in-place overwrite occurred.
        """
        # covers: ACD-1200a-9-i (in-place overwrite)
        goal_to_epic = self._goal_to_epic
        source_filename = "validate-input-schema.md"
        prefixed_filename = f"01_{source_filename}"
        prior_content = "prior run content"
        new_content = "updated content from new run"

        # Pre-create the epic folder with a prior-run file (use PascalCase folder name)
        self._pre_create_epic_folder_with_file(
            self.EPIC_NAME_PASCAL, prefixed_filename, content=prior_content
        )

        # Create the new source ticket (with updated content)
        source_ticket = self._make_source_ticket(source_filename, content=new_content)

        # Act: assemble using the hyphen-separated name — _to_pascal_case() will
        # produce EPIC_NAME_PASCAL which matches the pre-created folder.
        epic_folder = goal_to_epic.assemble_epic_folder(
            [str(source_ticket)],
            self.EPIC_NAME_HYPHEN,
            self._inbox_dir,
        )

        dest_file = epic_folder / prefixed_filename
        self.assertTrue(
            dest_file.exists(),
            msg=f"Destination file {dest_file} must exist after assembly.",
        )
        actual_content = dest_file.read_text(encoding="utf-8")
        self.assertEqual(
            actual_content,
            new_content,
            msg=(
                "Destination file must contain the updated content (in-place overwrite). "
                f"Got: {actual_content!r}, expected: {new_content!r}"
            ),
        )

    # -----------------------------------------------------------------------
    # Test 2: No second-location copy
    # -----------------------------------------------------------------------

    def test_acd_1200a_9i_no_second_location_copy(self) -> None:
        """ACD-1200a-9-i: no renamed sibling and no second copy is created anywhere.

        After assemble_epic_folder() resolves a collision by overwriting in place,
        only one file with the source basename must exist inside the epic folder,
        and no file with a mangled/renamed variant of that basename must exist.
        """
        # covers: ACD-1200a-9-i (no second copy, no renamed sibling)
        goal_to_epic = self._goal_to_epic
        source_filename = "validate-input-schema.md"
        prefixed_filename = f"01_{source_filename}"

        # Pre-create the epic folder with a prior-run file
        self._pre_create_epic_folder_with_file(
            self.EPIC_NAME_PASCAL, prefixed_filename, content="prior content"
        )

        source_ticket = self._make_source_ticket(source_filename, content="new content")

        epic_folder = goal_to_epic.assemble_epic_folder(
            [str(source_ticket)],
            self.EPIC_NAME_HYPHEN,
            self._inbox_dir,
        )

        # Collect all .md files in the epic folder (excluding Master_Plan.md)
        all_md_files = [
            f.name for f in epic_folder.iterdir()
            if f.suffix == ".md" and f.name != "Master_Plan.md"
        ]

        # Must have exactly one ticket file
        self.assertEqual(
            len(all_md_files),
            1,
            msg=(
                f"Expected exactly 1 ticket .md file in epic folder, found: {all_md_files}. "
                "No renamed sibling or extra copy must be created."
            ),
        )
        self.assertIn(
            prefixed_filename,
            all_md_files,
            msg=(
                f"The single file must be {prefixed_filename!r}, not a renamed variant. "
                f"Found: {all_md_files}"
            ),
        )

    # -----------------------------------------------------------------------
    # Test 3: Single resulting file after run
    # -----------------------------------------------------------------------

    def test_acd_1200a_9i_single_file_after_run(self) -> None:
        """ACD-1200a-9-i: exactly one ticket file with the computed basename exists
        at the epic-folder path after the run.

        Verifies the post-condition across the entire folder, not just the specific
        destination: the epic folder contains exactly the expected set of numbered
        ticket files (one per source ticket).
        """
        # covers: ACD-1200a-9-i (single file invariant after run)
        goal_to_epic = self._goal_to_epic

        # Set up two source tickets
        source_a = self._make_source_ticket("validate-input-a.md", content="content-a")
        source_b = self._make_source_ticket("validate-input-b.md", content="content-b")

        # Pre-create the epic folder with a collision on the first ticket slot.
        # The epic folder name must match what assemble_epic_folder will create:
        # _to_pascal_case(self.EPIC_NAME_HYPHEN) → self.EPIC_NAME_PASCAL.
        self._pre_create_epic_folder_with_file(
            self.EPIC_NAME_PASCAL, "01_validate-input-a.md", content="stale content"
        )

        epic_folder = goal_to_epic.assemble_epic_folder(
            [str(source_a), str(source_b)],
            self.EPIC_NAME_HYPHEN,
            self._inbox_dir,
        )

        md_files = sorted(
            f.name for f in epic_folder.iterdir()
            if f.suffix == ".md" and f.name != "Master_Plan.md"
        )

        self.assertEqual(
            md_files,
            ["01_validate-input-a.md", "02_validate-input-b.md"],
            msg=(
                "After the run, exactly the expected numbered ticket files must "
                "exist in the epic folder — no duplicates, no renamed siblings. "
                f"Found: {md_files}"
            ),
        )

        # Verify content of the overwritten file is the new version
        overwritten = (epic_folder / "01_validate-input-a.md").read_text(encoding="utf-8")
        self.assertEqual(overwritten, "content-a")

    # -----------------------------------------------------------------------
    # Test 4: WARNING is emitted on overwrite
    # -----------------------------------------------------------------------

    def test_acd_1200a_9i_warning_emitted_on_overwrite(self) -> None:
        """ACD-1200a-9-i: a WARNING-level log line is emitted when a file is replaced.

        The overwrite must not be silent — the caller must be able to observe
        that an existing file was replaced.
        """
        # covers: ACD-1200a-9-i (observable WARNING on overwrite)
        goal_to_epic = self._goal_to_epic
        source_filename = "validate-input-schema.md"
        prefixed_filename = f"01_{source_filename}"

        self._pre_create_epic_folder_with_file(
            self.EPIC_NAME_PASCAL, prefixed_filename, content="prior"
        )
        source_ticket = self._make_source_ticket(source_filename, content="new")

        with self.assertLogs("goal_to_epic", level=logging.WARNING) as log_ctx:
            goal_to_epic.assemble_epic_folder(
                [str(source_ticket)],
                self.EPIC_NAME_HYPHEN,
                self._inbox_dir,
            )

        # At least one WARNING message must mention the collision/overwrite
        collision_warnings = [
            msg for msg in log_ctx.output
            if "WARNING" in msg and "collision" in msg.lower()
        ]
        self.assertGreater(
            len(collision_warnings),
            0,
            msg=(
                "Expected at least one WARNING log line mentioning 'collision' "
                "when a basename collision is resolved by overwriting. "
                f"All log messages captured: {log_ctx.output}"
            ),
        )

    # -----------------------------------------------------------------------
    # Test 5: Correct implemented_by after collision
    # -----------------------------------------------------------------------

    def test_acd_1200a_9i_implemented_by_after_collision(self) -> None:
        """ACD-1200a-9-i: _replace_implemented_by_entry updates implemented_by to
        the single epic-folder path after a collision overwrite.

        Verifies that after assemble_epic_folder resolves a collision and
        _replace_implemented_by_entry is called, the AC YAML's implemented_by
        field names only the epic-folder path (not a loose path or a sibling path).
        """
        # covers: ACD-1200a-9-i (implemented_by names single epic-folder path)
        import yaml  # noqa: PLC0415

        goal_to_epic = self._goal_to_epic

        # Set up an AC YAML store with a leaf AC that has an implemented_by entry
        # pointing to the loose inbox path.
        ac_store = self._tmp_path / "docs" / "acceptance-criteria"
        ac_store.mkdir(parents=True, exist_ok=True)
        loose_ticket_rel_path = "tickets/00_inbox/validate-input-schema.md"
        ac_yaml_content = (
            "id: ACD-TEST-1\n"
            "title: Test leaf AC\n"
            "readiness: approved\n"
            "implemented_by:\n"
            f"- {loose_ticket_rel_path}\n"
        )
        ac_yaml_path = ac_store / "test_ac.yaml"
        ac_yaml_path.write_text(ac_yaml_content, encoding="utf-8")

        # Simulate the epic-folder path that should replace the loose path
        epic_folder_path = str(
            self._inbox_dir
            / "epics"
            / f"EPIC-{self.EPIC_NAME_PASCAL}"
            / "01_validate-input-schema.md"
        )

        # Act: call _replace_implemented_by_entry directly (same helper that
        # run() calls after assemble_epic_folder succeeds, per ACD-1200a-9)
        goal_to_epic._replace_implemented_by_entry(
            ac_store_root=ac_store,
            old_path=loose_ticket_rel_path,
            new_path=epic_folder_path,
        )

        # Assert: the AC YAML must now list only the epic-folder path
        updated_content = ac_yaml_path.read_text(encoding="utf-8")

        self.assertIn(
            epic_folder_path,
            updated_content,
            msg=(
                "implemented_by must contain the epic-folder path after collision resolution. "
                f"AC YAML content:\n{updated_content}"
            ),
        )
        self.assertNotIn(
            loose_ticket_rel_path,
            updated_content,
            msg=(
                "implemented_by must NOT contain the loose inbox path after collision resolution. "
                f"AC YAML content:\n{updated_content}"
            ),
        )

        # Verify there is no second-location sibling in implemented_by
        data = yaml.safe_load(updated_content)
        implemented_by: list = data.get("implemented_by", [])
        self.assertEqual(
            len(implemented_by),
            1,
            msg=(
                "implemented_by must contain exactly one entry (the epic-folder path) "
                f"after collision resolution. Got: {implemented_by}"
            ),
        )
        self.assertEqual(
            implemented_by[0],
            epic_folder_path,
            msg=(
                "implemented_by[0] must be the epic-folder path. "
                f"Got: {implemented_by[0]!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
