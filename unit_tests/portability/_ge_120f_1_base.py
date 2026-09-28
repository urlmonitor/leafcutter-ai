"""
MODULE: _ge_120f_1_base
AC: GE-120f-1 (and its children GE-120f-1-i, -i-b, -ii, -ii-b) -- shared
    TestCase base class for the whole test_ge_120f_1*.py family.
GOAL: Every class in this family (TestGE120f1NegativeControlLiveness,
    TestGE120f1iEntryPointDemonstration, TestGE120f1iNoRegisteredEntryPoint,
    TestGE120f1iiAcceptableInputPairing, TestGE120f1iiFailedInvocationAndSchemaShape)
    used to hand-roll an IDENTICAL setUpClass/tearDownClass pair -- build ONE
    real deployed-only working copy via _deployed_check_harness ONCE per
    class, per this AC family's own RUNTIME BUDGET requirement ("Build the
    copy ONCE per sweep, never once per check") -- differing only in which
    subdirectory of the copy each class parks its own fixture files under.
    None of that setUpClass/tearDownClass body ever declared the class
    attributes it assigned (`_tmp`, `copy_dir`, `harness`, `deployed_cg_dir`,
    `fixtures_dir`) with a type annotation anywhere mypy's
    `--explicit-package-bases` run can see, since a bare
    `cls.copy_dir = ...` inside a classmethod does not itself create an
    attribute mypy considers declared on the class -- every *read* of one of
    those five names anywhere else in the same class (i.e. every `self.`
    read in a test body) then reports `[attr-defined]`. This module exists
    to declare those five names ONCE, with real annotations, and hold the
    ONE shared setUpClass/tearDownClass body so five near-identical copies of
    it are not still living on independently in five files after the fix.

    Extend GE-120c-1's harness by importing it here rather than duplicating
    any of its logic -- this module composes `_deployed_check_harness`, it
    does not re-implement any part of it.

DECISION HISTORY
====================================================================
- 2026-09-27 [test-writer rework, GE-120f-1 family / PR #916]: Extracted
  from the five test_ge_120f_1*.py files' own IDENTICAL setUpClass/
  tearDownClass bodies to clear the "Type-check changed files (mypy,
  informational)" CI job, which reported 196 `[attr-defined]` errors (43 +
  53 + 16 + 52 + 32 across the five files) -- every one traced to these same
  five undeclared class attributes. No assertion, test name, `# covers:` /
  `# angle:` tag, or test behaviour changed: each test class now inherits
  `GE120f1DeployedCopyTestCase` and sets its own `fixtures_subdir` class
  attribute (the one thing that varied file to file) instead of repeating
  the whole setUpClass body. `TestGE120f1iiFailedInvocationAndSchemaShape`
  (test_ge_120f_1_ii_b.py) additionally overrides `setUpClass` to call
  `super().setUpClass()` and then set its own extra `currently_schema` class
  attribute, which no sibling class needs, so that attribute is declared and
  assigned only on that one subclass rather than pushed into this shared
  base for a single caller.
====================================================================
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

import _deployed_check_harness as dch  # type: ignore[import]

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root


class GE120f1DeployedCopyTestCase(unittest.TestCase):
    """Shared, expensive fixture base: build ONE real deployed-only working
    copy via the real scripts/build.py ONCE for the whole class. Subclasses
    set `fixtures_subdir` (the only thing that ever varied between the five
    original hand-rolled copies of this body) before `setUpClass` runs --
    i.e. as a plain class attribute in the subclass body, not inside a
    method."""

    #: Overridden per subclass; the subdirectory of the deployed copy this
    #: class's own fixture manifests and fixture check scripts live under.
    fixtures_subdir: ClassVar[str] = "_ge120f1_fixtures"

    _tmp: ClassVar[tempfile.TemporaryDirectory[str]]
    copy_dir: ClassVar[Path]
    harness: ClassVar[dch.DeployedCheckHarness]
    deployed_cg_dir: ClassVar[Path]
    fixtures_dir: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(cls._tmp.name)
        cls.copy_dir = tmp_root / "copy"
        cls.harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        cls.harness.create_second_copy(cls.copy_dir)
        cls.deployed_cg_dir = cls.copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
        cls.fixtures_dir = cls.copy_dir / cls.fixtures_subdir

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()
