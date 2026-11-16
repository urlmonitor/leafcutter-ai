"""
MODULE: unit_tests/portability/ge_120e_1/test_ge_120e_1_criterion.py
AC: GE-120e-1 — "A check that works out its own change set works out the
    author's change, not everything the staged tree happens to hold"
GOAL: The two criterion-angle tests of the GE-120e-1 suite: carried-in
    mainline work is absent from the inspected change set (test A), and the
    verdict on the author's own content is the same whether it is committed
    ordinarily or alongside carried-in noise in a merge (test B).
CONTRACT: see the module docstring of ``_support.py`` in this package
    ("CONTRACT ASSUMED") for the shape of the shared module under test and
    why every fixture is a real linked checkout of this repository.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Moved here unchanged from
  unit_tests/portability/test_ge_120e_1.py when that file was split; the
  classes now declare their setUpClass attributes for the type checker.
"""
# @ac-tag: GE-120e-1

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from typing import ClassVar

from unit_tests.build_orchestration._workspace_maker_fixtures import unlink_checkout
from unit_tests.portability.ge_120e_1._support import (
    _CHECK_CONTRACT_SHRINKING,
    _CHECK_DOC_FRONTMATTER,
    _REPO_ROOT,
    _SHARED_MODULE_MISSING_MSG,
    _SHARED_MODULE_OK,
    NoAuthorMergeTestCase,
    _AuthorAndCarriedInMergeFixture,
    _run,
    get_authored_change,
)


# ---------------------------------------------------------------------------
# Test A — angle: criterion
# ---------------------------------------------------------------------------
class TestCarriedInWorkAbsentFromInspectedChangeSet(NoAuthorMergeTestCase):
    """AC-2/AC-4: the change set inspected holds only content differing from
    every state the commit is built on; carried-in mainline work is absent
    from it, and the check's verdict raises no objection to it."""

    def test_ge120e1_carried_in_work_absent_from_inspected_change_set(self) -> None:
        # covers: GE-120e-1
        # angle: criterion
        """RED today via the shared-module import: even though both checks
        already pass this exact fixture individually (GE-120e-1-i landed
        per-check merge-scoping), GE-120e-1's own deliverable is that BOTH
        derive that scoped set from ONE shared module. This test asserts
        both the process-level behavior (subprocess exit + output) AND that
        the shared derivation itself, run against this same fixture,
        produces a path set excluding every carried-in path.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        contract_shrinking = _run(["python3", str(_CHECK_CONTRACT_SHRINKING)], cwd=self.fixture.root)
        self.assertEqual(
            0, contract_shrinking.returncode,
            f"check_contract_shrinking.py must exit clean. stdout={contract_shrinking.stdout!r} "
            f"stderr={contract_shrinking.stderr!r}",
        )
        doc_frontmatter = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root)
        self.assertEqual(
            0, doc_frontmatter.returncode,
            f"check_doc_frontmatter.py must exit clean. stdout={doc_frontmatter.stdout!r} "
            f"stderr={doc_frontmatter.stderr!r}",
        )
        combined = (
            contract_shrinking.stdout + contract_shrinking.stderr
            + doc_frontmatter.stdout + doc_frontmatter.stderr
        )
        for carried in (self.fixture.baddoc_rel, self.fixture.deleted_test_rel):
            self.assertNotIn(
                carried, combined,
                f"Carried-in path {carried!r} must never appear in either check's "
                f"output. Combined output: {combined!r}",
            )

        authored = get_authored_change(cwd=self.fixture.root)
        self.assertFalse(
            authored.could_not_check,
            "get_authored_change() reported could_not_check on a fixture "
            f"with a valid, resolvable merge — the derivation itself failed "
            f"(error={authored.error!r}).",
        )
        self.assertNotIn(
            self.fixture.baddoc_rel, authored.paths,
            f"The shared derivation's own .paths must exclude the carried-in "
            f"doc. Got: {authored.paths!r}",
        )
        self.assertNotIn(
            self.fixture.deleted_test_rel, authored.paths,
            f"The shared derivation's own .paths must exclude the carried-in "
            f"deletion. Got: {authored.paths!r}",
        )


# ---------------------------------------------------------------------------
# Test B — angle: criterion
# ---------------------------------------------------------------------------
class TestVerdictOnAuthorsOwnContentIsUnchanged(unittest.TestCase):
    """AC-4 (second clause): the check's verdict on the SAME author content
    is unchanged whether it is committed ordinarily or alongside carried-in
    mainline noise via a merge."""

    fixture: ClassVar[_AuthorAndCarriedInMergeFixture]
    ordinary_root: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = _AuthorAndCarriedInMergeFixture()
        cls.fixture.build()
        cls.ordinary_root = Path(tempfile.gettempdir()) / f"ge120e1-ordinary-{uuid.uuid4().hex[:10]}"
        cls.fixture.build_ordinary_comparison(cls.ordinary_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.teardown()
        unlink_checkout(_REPO_ROOT, ["--force", str(cls.ordinary_root)], check=False)

    def test_ge120e1_verdict_on_the_authors_own_content_is_unchanged(self) -> None:
        # covers: GE-120e-1
        # angle: criterion
        """RED via the shared-module import gate. Once implemented: the same
        author-authored bad-frontmatter doc must produce the SAME
        pass/fail status and name the SAME file whether committed alone
        (ordinary commit) or alongside a merge's unrelated carried-in
        content.
        """
        if not _SHARED_MODULE_OK:
            self.fail(_SHARED_MODULE_MISSING_MSG)

        ordinary_result = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.ordinary_root)
        merged_result = _run(["python3", str(_CHECK_DOC_FRONTMATTER)], cwd=self.fixture.root)

        self.assertEqual(
            ordinary_result.returncode, merged_result.returncode,
            "check_doc_frontmatter.py's exit code for the author's own bad "
            f"doc must be identical whether ordinary ({ordinary_result.returncode}) "
            f"or merged alongside carried-in noise ({merged_result.returncode}). "
            f"ordinary stdout={ordinary_result.stdout!r} "
            f"merged stdout={merged_result.stdout!r}",
        )
        self.assertNotEqual(
            0, ordinary_result.returncode,
            "Sanity check on the fixture itself: the author's own "
            f"bad-frontmatter doc must be flagged when committed alone. "
            f"stdout={ordinary_result.stdout!r}",
        )
        ordinary_combined = ordinary_result.stdout + ordinary_result.stderr
        merged_combined = merged_result.stdout + merged_result.stderr
        self.assertIn(
            self.fixture.author_baddoc_rel, ordinary_combined,
            f"Ordinary-commit output must name the author's own bad doc. Got: {ordinary_combined!r}",
        )
        self.assertIn(
            self.fixture.author_baddoc_rel, merged_combined,
            f"Merged-commit output must ALSO name the author's own bad doc — "
            f"the verdict on the author's own content must be unchanged by "
            f"the presence of unrelated carried-in content. Got: {merged_combined!r}",
        )
        self.assertNotIn(
            self.fixture.carried_baddoc_rel, merged_combined,
            f"Merged-commit output must NOT name the carried-in doc — only "
            f"the author's own content is in scope. Got: {merged_combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
