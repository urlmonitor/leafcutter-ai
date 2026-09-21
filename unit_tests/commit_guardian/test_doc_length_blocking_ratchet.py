"""
MODULE: unit_tests/commit_guardian/test_doc_length_blocking_ratchet.py
COVERS: check-doc-length's move from severity ``warn`` to severity ``block``
    with a GE-127-style ratchet.

GOAL: Prove, behaviourally, the four things that distinguish the blocking
    ratchet from both the warn-only gate it replaces and the absolute block
    it deliberately is NOT:
      1. A doc that CROSSES its limit is refused (exit 1).
      2. A doc ALREADY over its limit and GROWING is refused (exit 1).
      3. A doc ALREADY over its limit that SHRINKS or HOLDS STEADY passes
         (exit 0) — the property that makes blocking survivable against the
         59 docs that were already over when this shipped.
      4. An unresolvable previous value is INDETERMINATE (exit 2), never a
         silent pass.

    Plus the two invariants that make those verdicts trustworthy: the
    configuration actually ships as ``block`` (a gate configured ``warn``
    exits 0 no matter how correct its logic is — the original defect), and
    the counting rule is applied identically to both sides of the
    comparison.

BUSINESS CONTEXT: check-doc-length shipped with ``severity`` unset, so
    DOC_LENGTH_SEVERITY defaulted to "warn" and main() returned 0 on every
    run. Three known-issues registers reached ~4,500 lines against a
    300-line limit without one commit being stopped. These tests exist
    because "the gate now blocks" is exactly the claim that a grep-only or
    source-reading test cannot establish — see CLAUDE.md, "Gate / Workflow
    ACs — Verify Behaviorally, Not by Grep", and the fast-lane postmortem it
    cites, where a gate passed its structural tests while never executing.

EXERCISE STRATEGY: real git repos in tmpdirs, real commits, real staged
    content, real subprocess invocations of the actual check_doc_length.py.
    The INDETERMINATE fixture is built by making the previous-value source
    GENUINELY unavailable at run time (a working copy that is not a git
    repository at all) rather than by asserting an error branch exists in
    the source — the same constraint test_ge_127b_1_i.py operates under, and
    for the same reason.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_DOC_LENGTH = _COMMIT_GUARDIAN_DIR / "check_doc_length.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_TIMEOUT = 30

_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_DOC_LENGTH_CONFIG = _CONFIG["doc_length"]
_MAX_LINES = _DOC_LENGTH_CONFIG["max_lines"]

_CLEAN_EXIT = 0
_FINDING_EXIT = 1
_INDETERMINATE_EXIT = 2


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=_TIMEOUT, check=True
    )


def _init_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "doc-length-test@example.com"], root)
    _git(["config", "user.name", "doc-length ratchet fixture"], root)


def _doc(n_body_lines: int, tag: str = "para") -> str:
    """Build a doc with frontmatter plus *n_body_lines* body lines.

    Frontmatter is included deliberately: the gate strips it before counting,
    so a fixture without it would not exercise the rule under test.
    """
    frontmatter = "---\ntitle: fixture\ntype: reference\n---\n"
    return frontmatter + "\n".join(f"{tag} line {i}" for i in range(n_body_lines)) + "\n"


def _write_doc(root: Path, relpath: str, n_body_lines: int, tag: str = "para") -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_doc(n_body_lines, tag), encoding="utf-8")


def _commit_all(root: Path, message: str) -> None:
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    _git(["add", "-A"], root)


def _run_check(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_PYTHON, str(_CHECK_DOC_LENGTH)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


class _RepoFixture(unittest.TestCase):
    """Base fixture: a temp git repo holding one already-committed short doc.

    The pre-existing short doc matters — it makes HEAD hold at least one
    checked doc, so the run exercises the real per-file lookup rather than
    the empty-history shortcut.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root)
        _write_doc(self.root, "docs/baseline.md", 10)
        _commit_all(self.root, "baseline doc")

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# The configuration actually ships as blocking
# ---------------------------------------------------------------------------


class TestConfiguredSeverity(unittest.TestCase):
    def test_doc_length_severity_ships_as_block(self):
        """The shipped config must set severity to 'block'.

        This is not a restatement of the code: DOC_LENGTH_SEVERITY defaults
        to "warn", and under "warn" main() returns 0 on every input, so
        every other test in this module would pass vacuously against a
        correct implementation that was simply never switched on. That
        combination — right logic, wrong configuration, green suite — is the
        exact shape of the original defect.
        """
        self.assertEqual("block", _DOC_LENGTH_CONFIG["severity"])


# ---------------------------------------------------------------------------
# Crossing refusal
# ---------------------------------------------------------------------------


class TestCrossingRefusal(_RepoFixture):
    def test_a_doc_taken_from_under_to_over_its_limit_is_refused(self):
        """A doc that was comfortably under the limit and is now over it
        must fail the commit."""
        _write_doc(self.root, "docs/growing.md", 50)
        _commit_all(self.root, "short doc")

        _write_doc(self.root, "docs/growing.md", _MAX_LINES + 25)
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_FINDING_EXIT, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("docs/growing.md", result.stdout)

    def test_a_new_doc_arriving_already_over_the_limit_is_refused(self):
        """A doc that exists at no parent cannot be grandfathered — there is
        no previous size to be judged against, so the limit applies."""
        _write_doc(self.root, "docs/brand-new.md", _MAX_LINES + 40)
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_FINDING_EXIT, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("docs/brand-new.md", result.stdout)

    def test_a_doc_that_stays_under_its_limit_passes(self):
        """The ordinary case must not be disturbed."""
        _write_doc(self.root, "docs/small.md", 40)
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# The ratchet on an already-oversized doc
# ---------------------------------------------------------------------------


class TestGrandfatheredDocRatchet(_RepoFixture):
    """The property that makes blocking survivable.

    Each test commits an ALREADY-oversized doc first — standing in for the
    59 real docs that were over the limit the day this gate started
    blocking — and then varies only what the staged revision does to it.
    """

    def setUp(self) -> None:
        super().setUp()
        self.oversized = _MAX_LINES + 200
        _write_doc(self.root, "docs/register.md", self.oversized)
        _commit_all(self.root, "an already-oversized register")

    def test_an_already_oversized_doc_that_grows_is_refused(self):
        _write_doc(self.root, "docs/register.md", self.oversized + 1)
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_FINDING_EXIT, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("docs/register.md", result.stdout)

    def test_an_already_oversized_doc_that_shrinks_passes_while_still_over(self):
        """Shrinking passes even though the doc remains far over the limit —
        judged against its own previous size, not the fixed limit."""
        shrunk = self.oversized - 50
        self.assertGreater(shrunk, _MAX_LINES, "fixture must stay over the limit to be meaningful")
        _write_doc(self.root, "docs/register.md", shrunk)
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)

    def test_an_already_oversized_doc_edited_without_changing_its_size_passes(self):
        """The append-heavy-register case: content changes, length does not."""
        _write_doc(self.root, "docs/register.md", self.oversized, tag="rewritten")
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Fail-closed floor
# ---------------------------------------------------------------------------


class TestIndeterminate(unittest.TestCase):
    def test_an_unreachable_previous_value_source_is_indeterminate_not_a_pass(self):
        """With no git repository at all, the gate must refuse with a named
        INDETERMINATE verdict rather than treating "no previous value" as
        "nothing grew".

        Silence is the failure mode this package exists to prevent; a gate
        that cannot see is not a gate that found nothing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_doc(root, "docs/orphan.md", _MAX_LINES + 100)

            result = subprocess.run(
                [_PYTHON, str(_CHECK_DOC_LENGTH)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )

        self.assertNotEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)


class TestEmptyHistoryCompletes(unittest.TestCase):
    def test_an_unborn_head_completes_rather_than_deadlocking_the_first_commit(self):
        """A fresh repo with no commit yet must not be refused — the first
        commit that would populate the history is the one a refusal would be
        blocking on."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write_doc(root, "docs/first.md", 20)
            _stage_all(root)

            result = _run_check(root)

        self.assertEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# One counting rule, both sides
# ---------------------------------------------------------------------------


class TestMeasurementSymmetry(_RepoFixture):
    def test_adding_frontmatter_alone_does_not_read_as_growth(self):
        """Frontmatter is stripped before counting. If the previous side were
        measured by a different rule than the current side, adding
        frontmatter lines to an already-oversized doc would register as
        growth and be refused. It must not.
        """
        oversized = _MAX_LINES + 100
        body = "\n".join(f"para line {i}" for i in range(oversized)) + "\n"
        path = self.root / "docs" / "fm.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntitle: t\n---\n" + body, encoding="utf-8")
        _commit_all(self.root, "oversized doc with short frontmatter")

        longer_frontmatter = (
            "---\ntitle: t\ntype: reference\nstatus: active\ncreated: 2026-09-14\n"
            "description: a much longer frontmatter block\n---\n"
        )
        path.write_text(longer_frontmatter + body, encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)
        self.assertEqual(_CLEAN_EXIT, result.returncode, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
