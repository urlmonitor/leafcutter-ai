"""
epic_errors.py — Exception types for the goal-to-epic pipeline.

MODULE: epic_errors
GOAL: Define the three domain exceptions the goal-to-epic pipeline raises, in a
      module with no sibling dependencies so every other pipeline module can
      import them without creating a cycle.
BUSINESS CONTEXT: Extracted verbatim from goal_to_epic.py so that file can meet
      the 400-line check_file_size limit. These types are part of the public
      surface: goal_to_epic.py re-exports all three, tests import
      ZeroLeafError and CyclicDependencyError by name, and main() catches both
      to map them onto CLI exit code 1.
ARCHITECTURE: Bottom of the goal-to-epic dependency graph — imports nothing from
      any sibling module. Deployed flat beside goal_to_epic.py in
      <output_root>/scripts/ac_store/ (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-3-i: Zero-leaf condition exits non-zero, no files written
                   (ZeroLeafError is the carrier).
    ACD-1200c-1-i: Cycle detection fires before any ticket files are written
                   (CyclicDependencyError is the carrier).
"""

from __future__ import annotations


class ZeroLeafError(ValueError):
    """Raised when the target AC tree has no leaf-level ACs beneath it.

    This condition means the goal AC has only composite L1 children and none
    have been decomposed to L2/L3 leaves. The caller must decompose the L1s
    before running goal_to_epic.
    """


class EpicFolderConflictError(FileExistsError):
    """Raised when the EPIC folder already exists and would be overwritten."""


class CyclicDependencyError(ValueError):
    """Raised when a circular dependency is detected among leaf ACs.

    The error message contains the full cycle path in the format:
        "Circular dependency detected: <id1> -> <id2> -> ... -> <id1>"
    """


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Extracted verbatim from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  Class bodies and docstrings are byte-identical to the originals; only their
  file location changed. goal_to_epic.py re-exports all three names so every
  existing import site keeps resolving. Pre-split history for these types lives
  in goal_to_epic.py's DECISION HISTORY block (entries dated 2026-06-05 and
  2026-06-22). (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
