"""
MODULE: unit_tests/commit_guardian/test_ge_122e_3_protected_diagrams.py
GOAL: AC-4 of GE-122e-3 -- the eleven unnumbered diagrams stay unchanged by
    NAME, LOCATION and CONTENT -- pinned by an explicit name set rather than
    derived from the tree. Split out of test_ge_122e_3.py (file-size ratchet).

BUSINESS CONTEXT: docs/acceptance-criteria/guardrail-engine/
    GE-122-numbers-mean-one-thing/GE-122e-3.yaml notes: "THE UNNUMBERED-
    ARTIFACTS CLAUSE IS A NEGATIVE ASSERTION PROTECTING THE USER'S SCOPE
    DECISION. Repair scope was trimmed at the PO gate to the ambiguous cases
    only, and the 11 unnumbered diagrams were explicitly excluded." Its
    it_requirements: "asserted by NAME AND LOCATION over the eleven unnumbered
    diagrams, not by count."

SAFETY / ORACLE INDEPENDENCE (same stance as test_ge_122e_3.py):
  - Real-collection test runs the real pass over a shutil.copytree COPY of the
    repository's docs/tickets trees, never the live tree; tearDownModule proves
    via ``git status --porcelain`` (scoped to the copied-from trees) that
    nothing wrote to the real tree.
  - Oracles (name set, hashes, filename regex) are local; nothing calls into
    check_identifier_uniqueness except the one ``run_uniqueness_pass`` the
    test is about. Fixtures are verbatim copies of real files.

DECISION HISTORY
- 2026-10-02 [test-writer, direct fix -- no ticket]: the old AC-4 test
  (formerly in test_ge_122e_3.py) had two defects. (1) It built the protected
  set DYNAMICALLY from whatever unnumbered ``*.md`` files existed in the
  copied tree and pinned ``len(...) == 11``, so any unrelated new unnumbered
  diagram broke it -- it already broke twice (PR #635, a folder README,
  patched by excluding it; PR #981, new docs). (2) Because the set was derived
  from today's tree, the per-file loop could not see a repository-level rename
  of a protected diagram: a renamed file just dropped out of the set, only the
  count noticed, and adding one new unnumbered file at the same time would
  have hidden the rename. Fix: the eleven are pinned by name in
  ``_PROTECTED_UNNUMBERED_DIAGRAMS`` (the set present on 2026-08-26 when the
  test was written, verified unchanged since); the count assertion is gone;
  the check is the helper ``_missing_or_changed_protected_diagrams``, proven
  load-bearing by TestProtectedDiagramHelperIsLoadBearing (reports a rename
  even when a new unnumbered file keeps the count at 11; reports nothing for
  an unrelated new diagram). Moved to its own module because
  test_ge_122e_3.py was already over its line limit and the ratchet refuses
  growth.
"""

from __future__ import annotations

import hashlib
import importlib.util as _ilu
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_identifier_uniqueness.py"

_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_REAL_ADR_ROOT = _REPO_ROOT / "docs" / "architecture" / "adrs"
_REAL_DIAGRAMS_ROOT = _REPO_ROOT / "docs" / "architecture" / "diagrams"
_REAL_TICKETS_ROOT = _REPO_ROOT / "tickets"

# Independently-authored copy of the production diagram filename pattern.
_DIAGRAM_FILENAME_RE = re.compile(r"^(c\d+-\d+)-.*\.md$", re.IGNORECASE)

# The protected set, pinned BY NAME (see module docstring for the AC citation).
# A literal, NOT derived from the tree: a derived set cannot notice a renamed member.
_PROTECTED_UNNUMBERED_DIAGRAMS = frozenset(
    {
        "c2-fast-lane-build-path-components.md",
        "c2-fast-vs-heavy-lane-phases.md",
        "c3-done-proof-evaluation-sequence.md",
        "c3-fast-lane-build-loop-sequence.md",
        "df-001-dual-engine-workflow-build-transform.md",
        "finalize-progress-narration-sequence.md",
        "finalize-progress-relay-sequence.md",
        "gates-sequence.md",
        "probe-sequence.md",
        "self-heal-component.md",
        "self-heal-sequence.md",
    }
)


def _load_module():
    """Load check_identifier_uniqueness by file path; None if the file is missing."""
    if not _CANONICAL.exists():
        return None
    spec = _ilu.spec_from_file_location("check_identifier_uniqueness", _CANONICAL)
    mod = _ilu.module_from_spec(spec)
    sys.modules["check_identifier_uniqueness"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()

_GUARDED_PATHS = ("docs/acceptance-criteria", "docs/architecture", "tickets")


def _git_status_porcelain() -> str:
    """Return `git status --porcelain` scoped to the trees this module copies from."""
    try:
        result = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "status", "--porcelain", "--", *_GUARDED_PATHS],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


_GIT_STATUS_BEFORE_MODULE = _git_status_porcelain()


def tearDownModule() -> None:
    """Prove this module never wrote to the real tree."""
    status_after = _git_status_porcelain()
    if status_after != _GIT_STATUS_BEFORE_MODULE:
        raise RuntimeError(
            "The real working tree changed during this module's run; every test must operate "
            f"on a tempdir copy.\nBEFORE:\n{_GIT_STATUS_BEFORE_MODULE!r}\nAFTER:\n{status_after!r}"
        )


def _diagrams_dir(collection_root: Path) -> Path:
    """Return the diagrams folder inside a collection root."""
    return collection_root / "docs" / "architecture" / "diagrams"


def _protected_diagram_hashes(collection_root: Path) -> dict[str, str]:
    """Hash every protected diagram that exists in the collection (absent names omitted).

    Args:
        collection_root: Root containing ``docs/architecture/diagrams/``.

    Returns:
        Mapping of protected file name to the sha256 of its bytes.
    """
    diagrams_dir = _diagrams_dir(collection_root)
    return {
        name: hashlib.sha256((diagrams_dir / name).read_bytes()).hexdigest()
        for name in sorted(_PROTECTED_UNNUMBERED_DIAGRAMS)
        if (diagrams_dir / name).is_file()
    }


def _missing_or_changed_protected_diagrams(collection_root: Path, before_hashes: dict[str, str]) -> list[str]:
    """Report every protected diagram that is missing, misnamed or changed.

    Iterates ``_PROTECTED_UNNUMBERED_DIAGRAMS`` (never a tree-derived set):
    each must exist at ``docs/architecture/diagrams/<name>``, must not match
    ``_DIAGRAM_FILENAME_RE``, and must hash equal to ``before_hashes``. Other
    files in the folder are ignored, so unrelated new diagrams report nothing.

    Args:
        collection_root: Root containing ``docs/architecture/diagrams/``.
        before_hashes: Protected-name -> sha256 captured before the pass.

    Returns:
        Human-readable problem strings; empty when all eleven are intact.
    """
    diagrams_dir = _diagrams_dir(collection_root)
    problems: list[str] = []
    for name in sorted(_PROTECTED_UNNUMBERED_DIAGRAMS):
        path = diagrams_dir / name
        if _DIAGRAM_FILENAME_RE.match(name):
            problems.append(f"{name}: protected name matches the numbered-diagram pattern (test constant is wrong)")
            continue
        if not path.is_file():
            problems.append(f"{name}: missing from its original location {path}")
            continue
        if name not in before_hashes:
            problems.append(f"{name}: no before-hash recorded (it was already missing before the pass)")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != before_hashes[name]:
            problems.append(f"{name}: content changed at {path}")
    return problems


class TestUnnumberedArtifactsUnchangedByNameAndLocation(unittest.TestCase):
    def setUp(self) -> None:
        if _mod is None:
            self.fail(f"check_identifier_uniqueness.py not found at {_CANONICAL}.")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(_REAL_AC_ROOT, self.root / "docs" / "acceptance-criteria")
        shutil.copytree(_REAL_ADR_ROOT, self.root / "docs" / "architecture" / "adrs")
        shutil.copytree(_REAL_DIAGRAMS_ROOT, _diagrams_dir(self.root))
        shutil.copytree(_REAL_TICKETS_ROOT, self.root / "tickets")

    def test_unnumbered_artifacts_unchanged_by_name_and_location(self):
        # covers: GE-122e-3
        """AC-4: each pinned protected diagram exists at
        ``docs/architecture/diagrams/<name>`` in the copied collection, does
        not match the numbered pattern, and keeps its content hash after
        ``run_uniqueness_pass`` (the pass must not touch anything). No
        folder-wide count is asserted: a new unnumbered or numbered diagram
        must not fail this test; renaming/moving/deleting/editing a protected
        one must.
        """
        self.assertEqual(11, len(_PROTECTED_UNNUMBERED_DIAGRAMS), msg="the pinned set must hold exactly eleven names.")
        before_hashes = _protected_diagram_hashes(self.root)
        self.assertEqual(
            _PROTECTED_UNNUMBERED_DIAGRAMS,
            frozenset(before_hashes),
            msg="a protected unnumbered diagram is not present at docs/architecture/diagrams/<name> before the pass ran.",
        )

        _mod.run_uniqueness_pass(self.root)  # read-only; must not touch anything

        problems = _missing_or_changed_protected_diagrams(self.root, before_hashes)
        self.assertEqual([], problems, msg=f"protected unnumbered diagrams are not unchanged: {problems}")


class TestProtectedDiagramHelperIsLoadBearing(unittest.TestCase):
    """Proves ``_missing_or_changed_protected_diagrams`` can actually fail.

    Temp collections are verbatim shutil.copy2 copies of the real protected
    diagrams; nothing here calls into the code under test.
    """

    def _build_collection(self) -> tuple[Path, dict[str, str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        diagrams_dir = _diagrams_dir(root)
        diagrams_dir.mkdir(parents=True)
        for name in _PROTECTED_UNNUMBERED_DIAGRAMS:
            shutil.copy2(_REAL_DIAGRAMS_ROOT / name, diagrams_dir / name)
        before_hashes = _protected_diagram_hashes(root)
        self.assertEqual(_PROTECTED_UNNUMBERED_DIAGRAMS, frozenset(before_hashes), msg="fixture sanity: all eleven copied.")
        return root, before_hashes

    def test_renamed_protected_diagram_reported_even_when_count_stays_eleven(self):
        # covers: GE-122e-3
        root, before_hashes = self._build_collection()
        diagrams_dir = _diagrams_dir(root)
        victim = "gates-sequence.md"
        # Rename to a numbered name AND add a new unnumbered diagram so the
        # unnumbered count is still eleven -- the masking scenario.
        (diagrams_dir / victim).rename(diagrams_dir / "c3-099-gates-sequence.md")
        shutil.copy2(_REAL_DIAGRAMS_ROOT / "probe-sequence.md", diagrams_dir / "brand-new-unrelated-diagram.md")
        unnumbered_count = sum(1 for p in diagrams_dir.glob("*.md") if not _DIAGRAM_FILENAME_RE.match(p.name))
        self.assertEqual(11, unnumbered_count, msg="fixture sanity: the old count-based check would still see eleven.")

        problems = _missing_or_changed_protected_diagrams(root, before_hashes)

        self.assertEqual(1, len(problems), msg=f"exactly the renamed diagram must be reported: {problems}")
        self.assertIn(victim, problems[0])
        self.assertIn("missing", problems[0])

    def test_extra_unrelated_unnumbered_diagram_reports_nothing(self):
        # covers: GE-122e-3
        root, before_hashes = self._build_collection()
        diagrams_dir = _diagrams_dir(root)
        shutil.copy2(_REAL_DIAGRAMS_ROOT / "probe-sequence.md", diagrams_dir / "brand-new-unrelated-diagram.md")
        shutil.copy2(_REAL_DIAGRAMS_ROOT / "c1-001-command-map.md", diagrams_dir / "c1-001-command-map.md")

        self.assertEqual([], _missing_or_changed_protected_diagrams(root, before_hashes))

    def test_changed_protected_diagram_reported(self):
        # covers: GE-122e-3
        root, before_hashes = self._build_collection()
        target = _diagrams_dir(root) / "self-heal-sequence.md"
        target.write_bytes(target.read_bytes() + b"\n<!-- tidy-up edit -->\n")

        problems = _missing_or_changed_protected_diagrams(root, before_hashes)

        self.assertEqual(1, len(problems), msg=f"{problems}")
        self.assertIn("self-heal-sequence.md", problems[0])
        self.assertIn("changed", problems[0])


if __name__ == "__main__":
    unittest.main()
