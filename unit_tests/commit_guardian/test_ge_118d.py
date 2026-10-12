"""
MODULE: unit_tests/commit_guardian/test_ge_118d.py
COVERS: GE-118d -- "A document's path-bearing frontmatter entries are
    resolved whichever of the two accepted shapes they use"

GOAL: RED test-first stubs for all 5 test_spec entries on ticket GE-118d.
    The defect site is `validate_paths()` in
    templates/scripts/commit_guardian/frontmatter_validators.py (~lines
    226-250), which does `project_root_path / p` on each element of
    related_docs / related_code / architecture_diagrams with no per-element
    shape check -- a labelled (single-key mapping) entry raises
    `TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'`
    (see docs/known-issues/commit-guardian/resolved/resolved-blocker-ki-cg-008.md,
    moved there from open-blocker-ki-cg-008.md once GE-118d resolved it).

    The fix's producer does not exist yet: a new top-level module
    scripts/frontmatter_path_resolver.py (VERBATIM-COPY tier, alongside
    scripts/knowledge_query.py), deployed via TWO manifest locations
    (`deploy_scripts` in build_workflow_tools(), scripts/build_phases_workflows.py;
    and the tuple inside _manifest_workflow_tool_scripts(),
    scripts/build_phases_knowledge.py -- corrected by architect-review from the
    ticket's original wrong guess of build_phases_workflows.py for the second
    location). validate_paths() must obtain its path strings by calling this
    resolver, never by testing element types inline.

FILE LAYOUT (the suite is two files, not one). Tests 1 (angle: deployed) and
    5 (angle: reachability) now live in the sibling module
    unit_tests/commit_guardian/test_ge_118d_deployed.py, and the fixture
    helpers both files share live in unit_tests/commit_guardian/
    _ge_118d_fixtures.py. The split is mechanical -- it keeps each file inside
    the 400-content-line file-size ratchet (check-file-size) -- and changed no
    test, no assertion and no `# covers:` tag. This file keeps tests 2, 3 and
    4 (angles: failure, criterion, real_artifact).

INTERFACE THIS SUITE ESTABLISHES (the ticket's Delivers-To section describes
    the resolver's CONTRACT -- "a single element ... returning either the one
    path string it denotes or a named refusal carrying the field, the entry
    as parsed, and the accepted-shape set. Three outcomes only" -- but names
    no concrete Python API). Test 3 below is the explicit target python-coder
    must satisfy:

        scripts/frontmatter_path_resolver.py
            ACCEPTED_SHAPES: tuple[str, ...]        # declared once
            class PathEntryRefusal:                  # frozen dataclass or equivalent
                field: str
                entry: Any
                accepted_shapes: tuple[str, ...]
            def resolve_frontmatter_path_entry(entry: Any, field: str) -> str | PathEntryRefusal:
                ...   # never raises -- returns a refusal for an unsupported shape
                      # (CLAUDE.md Error Handling Policy Rule 4: pure classification
                      # must be total, not protected by a try/except wrapper)

    Order is proven by calling this per-element function across a list in
    Python's own iteration order (test 3) -- no second "resolve a whole list"
    function is required by this suite; validate_paths()'s existing per-field
    loop already iterates in declared order, so calling the per-element
    resolver from inside that unchanged loop is sufficient to satisfy
    GE-118f's ordering dependency.

EXERCISE STRATEGY (mirrors the established sibling patterns in this same
    directory -- test_ge_118c_doc_types_deployed_resolution.py for the
    same guard, and test_ge_127c_1_deployed_reachability.py for the
    deployed-vs-reachability split):
    - Test 1 (angle: deployed), in test_ge_118d_deployed.py, builds a REAL,
      FRESH `python scripts/build.py --target-dir <tmp>` into a temp directory
      OUTSIDE this repository, then invokes the DEPLOYED run_hook.py/
      check_doc_frontmatter.py as a subprocess there. A source-tree import is
      blind to the two-place deploy-manifest gap that reopened GE-118c; this
      is the test that would catch python-coder forgetting either manifest
      location.
    - Test 2 (angle: failure), here, and Test 5 (angle: reachability), in
      test_ge_118d_deployed.py, invoke the SOURCE-tree run_hook.py/
      check_doc_frontmatter.py (templates/scripts/commit_guardian/) as a
      subprocess against an isolated, real throwaway git repository -- a real
      production entry point (mirrors pre-commit's own invocation), just not
      the one exercising the deploy-manifest gap (that division of labour is
      deliberate; see the module docstring of
      test_ge_127c_1_deployed_reachability.py for the same split rationale).
    - Test 3 (angle: criterion) is a direct unit test against the new
      resolver module.
    - Test 4 (angle: real_artifact) runs the REAL validate_doc_file() against
      (a) docs/known-issues/commit-guardian/resolved/resolved-blocker-ki-cg-008.md
      (moved there from open-blocker-ki-cg-008.md once GE-118d resolved it), a
      document already tracked in this repository using the bare form, and
      (b) a document whose frontmatter bytes are produced by yaml.safe_dump
      (never a hand-indented literal), per CLAUDE.md's "Real-artifact
      behavioral spot-check" and docs/how-to/real-artifact-fixtures.md.

RED BASELINE -- see the test-writer sign-off comment on ticket GE-118d for
    the exact captured subprocess/assertion output from the verification run.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from ._ge_118d_fixtures import (
    _KI_CG_008_REL,
    _REPO_ROOT,
    _SCRIPTS_DIR,
    _TEMPLATES_CG_DIR,
    _four_entry_doc_frontmatter,
    _init_repo,
    _run_hook_against_source,
    _write,
    _write_four_entry_targets,
)


# ---------------------------------------------------------------------------
# Test 2 -- angle: failure
# ---------------------------------------------------------------------------


class TestGe118dAbsentPathReportsOneError(unittest.TestCase):
    """AC GE-118d's negative arm: a labelled entry naming an absent path must
    report exactly one error, naming the field and the path string -- never
    the parsed mapping's repr."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ge118d_failure_")
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        _init_repo(self.repo)

    def test_ge_118d_labelled_entry_naming_an_absent_path_reports_exactly_one_error_naming_the_path(
        self,
    ) -> None:
        # covers: GE-118d
        # angle: failure
        """THE NEGATIVE ARM, which is what separates the fix from unwrapping
        an element and never checking it. Change one labelled entry to name
        docs/explanation/absent.md and assert exactly one error, that it
        names the field and the literal string docs/explanation/absent.md,
        and that the message does NOT contain the mapping's repr.

        FAILS TODAY: the hook crashes with an uncaught TypeError on the
        labelled entry before ever reaching a per-path existence check, so no
        'Broken path' message is ever produced -- there is no message to
        assert content on. What must be implemented to make this green: the
        resolver returns the labelled entry's path string, validate_paths()
        finds it does not exist, and reports exactly one error naming
        'related_docs' and 'docs/explanation/absent.md' -- never the dict
        `{'explanation_labelled': 'docs/explanation/absent.md'}` the parser
        produced.
        """
        _write_four_entry_targets(self.repo)
        doc_rel = "docs/ge118d_temp_absent_doc.md"
        _write(
            self.repo / doc_rel,
            _four_entry_doc_frontmatter(
                title="GE-118d absent-path fixture",
                absent_target="docs/explanation/absent.md",
            ),
        )

        result = _run_hook_against_source(self.repo, [doc_rel])
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "GE-118d: expected the guard to refuse a labelled entry "
                f"naming an absent path.\n{combined}"
            ),
        )

        error_lines = [line for line in combined.splitlines() if "Broken path" in line]
        self.assertEqual(
            1,
            len(error_lines),
            msg=(
                "GE-118d RED: expected exactly one broken-path error, got "
                f"{len(error_lines)}: {error_lines!r}\nfull output:\n{combined}"
            ),
        )
        (error_line,) = error_lines
        self.assertIn(
            "related_docs",
            error_line,
            msg=f"the error must name the field 'related_docs'. Got: {error_line!r}",
        )
        self.assertIn(
            "docs/explanation/absent.md",
            error_line,
            msg=(
                "the error must name the literal path string "
                f"'docs/explanation/absent.md'. Got: {error_line!r}"
            ),
        )
        self.assertNotIn(
            "explanation_labelled",
            error_line,
            msg=(
                "the error must NOT contain the mapping's key/repr as the "
                f"parser rendered it. Got: {error_line!r}"
            ),
        )
        self.assertNotIn(
            "{",
            error_line,
            msg=f"the error must not contain a dict-repr brace. Got: {error_line!r}",
        )


# ---------------------------------------------------------------------------
# Test 3 -- angle: criterion
# ---------------------------------------------------------------------------


class TestGe118dResolverReturnsOneOrderedPathPerAcceptedEntry(unittest.TestCase):
    """AC GE-118d direct-on-the-resolver test: bare -> itself, labelled ->
    its value, and order is preserved across a mixed sequence."""

    def setUp(self) -> None:
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))

    def test_ge_118d_resolver_returns_one_ordered_path_per_accepted_entry(self) -> None:
        # covers: GE-118d
        # angle: criterion
        """Direct on the resolver: a bare string yields that string; a
        single-key mapping yields its value; a mixed list yields both, in the
        order declared. Order is asserted because GE-118f compares the two
        consumers' ordered lists and an unordered resolver makes that
        comparison vacuous.

        FAILS TODAY: scripts/frontmatter_path_resolver.py does not exist.
        What must be implemented to make this green: the module described in
        this file's own top-of-module docstring, exporting
        `resolve_frontmatter_path_entry(entry, field)`, `ACCEPTED_SHAPES`,
        and `PathEntryRefusal`.
        """
        try:
            import frontmatter_path_resolver as resolver
        except ImportError as exc:
            self.fail(
                "GE-118d RED: scripts/frontmatter_path_resolver.py does not "
                f"exist yet ({exc}). Implement "
                "resolve_frontmatter_path_entry(entry, field) there, per the "
                "ticket's Delivers-To contract and this test file's module "
                "docstring."
            )
            return

        entries = ["docs/a.md", {"explanation": "docs/b.md"}, "docs/c.md"]
        resolved = [
            resolver.resolve_frontmatter_path_entry(entry, "related_docs")
            for entry in entries
        ]
        self.assertEqual(
            ["docs/a.md", "docs/b.md", "docs/c.md"],
            resolved,
            msg=(
                "expected one ordered path string per accepted entry "
                f"(bare, labelled, bare, in declared order), got {resolved!r}"
            ),
        )

        # "Three outcomes only" (Delivers-To contract): an unsupported shape
        # must be refused BY NAME, never silently accepted or coerced.
        multi_key_entry = {"explanation": "docs/b.md", "extra": "docs/d.md"}
        refusal = resolver.resolve_frontmatter_path_entry(multi_key_entry, "related_docs")
        self.assertIsInstance(
            refusal,
            resolver.PathEntryRefusal,
            msg=(
                "a multi-key mapping must be refused by name, not silently "
                f"accepted or coerced into a path string; got {refusal!r}"
            ),
        )
        self.assertEqual(refusal.field, "related_docs")
        self.assertEqual(refusal.entry, multi_key_entry)
        self.assertEqual(
            tuple(refusal.accepted_shapes),
            tuple(resolver.ACCEPTED_SHAPES),
            msg=(
                "the refusal must carry the SAME accepted-shape set declared "
                "once at module level -- a second, inline copy is what this "
                "AC's 'ONE ROUTINE, ONE DECLARED ACCEPTED-SHAPE SET, IN "
                "EXACTLY ONE PLACE' Implementation Note forbids."
            ),
        )


# ---------------------------------------------------------------------------
# Test 4 -- angle: real_artifact
# ---------------------------------------------------------------------------


class TestGe118dRealArtifactVerdict(unittest.TestCase):
    """AC GE-118d real-artifact requirement: the guard's verdict on a real
    tracked bare-form document must be unchanged, and a labelled-form
    document produced by yaml.safe_dump must also reach a verdict without
    raising."""

    def setUp(self) -> None:
        if str(_TEMPLATES_CG_DIR) not in sys.path:
            sys.path.insert(0, str(_TEMPLATES_CG_DIR))

    def test_ge_118d_verdict_is_unchanged_on_a_real_tracked_document_and_on_a_pyyaml_serialised_one(
        self,
    ) -> None:
        # covers: GE-118d
        # angle: real_artifact
        """Run the guard against a document tracked in this repository that
        uses the bare form (docs/known-issues/commit-guardian/resolved/
        resolved-blocker-ki-cg-008.md, moved there from
        open-blocker-ki-cg-008.md once GE-118d resolved it) and against a
        labelled-form document
        written with yaml.safe_dump rather than as an indented string
        literal. Assert a verdict is reached on both and that the bare-form
        document's verdict is unchanged from today's.

        Part A (bare form) is expected to ALREADY PASS today -- bare-string
        related_docs entries never exercised the defect. This stands as a
        regression guard, per test-writer convention for a must-stay-green
        arm alongside a RED arm in the same AC.

        Part B (yaml.safe_dump labelled form) FAILS TODAY: validate_doc_file
        raises TypeError uncaught for the labelled entry, which this test
        converts into a readable AssertionError. What must be implemented to
        make this green: validate_paths() must resolve the labelled entry via
        the new resolver and report a clean verdict when its target exists.
        """
        from frontmatter_validators import validate_doc_file

        # --- Part A: a REAL tracked document using the bare form. ---
        self.assertTrue(
            (_REPO_ROOT / _KI_CG_008_REL).exists(),
            msg=f"expected a real tracked doc at {_KI_CG_008_REL}",
        )
        try:
            bare_errors, _bare_warnings = validate_doc_file(_KI_CG_008_REL, set(), _REPO_ROOT)
        except Exception as exc:  # noqa: BLE001 -- test intentionally converts ANY crash into a readable assertion failure; see AC's "reaches a verdict ... without raising"
            self.fail(
                f"validate_doc_file raised {exc!r} against the real tracked "
                f"bare-form document {_KI_CG_008_REL} -- the guard must reach "
                "a verdict without raising."
            )
            return
        self.assertEqual(
            [],
            bare_errors,
            msg=(
                "GE-118d: the bare-form document's verdict must be unchanged "
                f"from today's clean pass. Got errors: {bare_errors!r}"
            ),
        )

        # --- Part B: a labelled-form document written with yaml.safe_dump. ---
        tmp_ctx = tempfile.TemporaryDirectory(prefix="ge118d_real_artifact_")
        self.addCleanup(tmp_ctx.cleanup)
        tmp_root = Path(tmp_ctx.name)
        _write(tmp_root / "docs" / "explanation" / "architecture.md", "# Architecture\n")

        fm = {
            "title": "GE-118d temp yaml.safe_dump fixture",
            "type": "reference",
            "status": "active",
            "created": "2026-09-28",
            "last_updated": "2026-09-28",
            "components": ["commit_guardian"],
            "related_docs": [{"explanation": "docs/explanation/architecture.md"}],
        }
        # Fixture Authenticity Rule (docs/how-to/real-artifact-fixtures.md):
        # produce the bytes with the REAL serializer, write to a real temp
        # file, and let validate_doc_file re-read it from disk -- never
        # assert on the in-memory dict or string.
        frontmatter_yaml = yaml.safe_dump(fm, sort_keys=False)
        doc_text = f"---\n{frontmatter_yaml}---\n\nBody text for the yaml.safe_dump fixture.\n"
        doc_rel = "docs/ge118d_temp_yaml_safe_dump_doc.md"
        _write(tmp_root / doc_rel, doc_text)

        try:
            labelled_errors, _labelled_warnings = validate_doc_file(doc_rel, set(), tmp_root)
        except Exception as exc:  # noqa: BLE001 -- see Part A's comment
            self.fail(
                f"validate_doc_file raised {exc!r} against a labelled-form "
                "document produced by yaml.safe_dump -- GE-118d requires the "
                "guard to reach a verdict for every accepted-shape entry "
                "without raising."
            )
            return
        self.assertEqual(
            [],
            labelled_errors,
            msg=(
                "expected the labelled-form entry (produced by yaml.safe_dump) "
                f"to resolve cleanly since its target exists. Got: {labelled_errors!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
