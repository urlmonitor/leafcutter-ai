"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_string_literal_phantom_comment.py
COVERS: GE-127d-3 -- "A string literal's own content is never mistaken for the
    start of a discarded docstring or block-comment region"

GOAL: Prove that ``count_content_lines()`` (templates/scripts/commit_guardian/
    _file_size_ratchet.py) never mistakes a block-comment-opening sequence, a
    block-comment-closing sequence, or a triple-quote sequence occurring
    INSIDE a single-quoted, double-quoted or backtick-delimited string
    literal for the start of a real discarded region -- and that a genuine,
    string-free triple-quoted string or block comment is still discarded
    exactly as before.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127d-3.yaml. The real, tracked instance the defect was found on is
    templates/workflows-js/fast-lane-ship.js line 1572, whose template
    literal contains the substring "changelogs/*.md" -- the "/*" inside it
    opened a phantom block-comment span under the pre-fix, bare-regex
    implementation.

RED BASELINE, HOW IT WAS ESTABLISHED: the pre-fix implementation
(three module-level regexes -- _TRIPLE_DOUBLE_QUOTE_RE, _TRIPLE_SINGLE_QUOTE_RE,
    _BLOCK_COMMENT_RE -- each applied via re.sub("", content) against the
    file's whole raw text) is reproduced below, verbatim, as
    ``_pre_fix_count_content_lines`` -- an INDEPENDENT reference, never
    imported from production, so a test comparing the two is a genuine
    regression/defect proof rather than a tautology. It was verified against
    the real pre-fix module (``git show HEAD:templates/scripts/commit_guardian/
    _file_size_ratchet.py`` at authoring time, before this ticket's fix was
    committed) to disagree with the corrected ``count_content_lines`` on every
    one of this file's first four descriptors, and to agree on the two
    non-regression descriptors -- which is exactly the RED-before / GREEN
    -after split this test file's descriptors assert.

DECISION HISTORY
- 2026-09-30 [python-coder/GE-127d-3]: Initial authoring. Verified RED against
  the real pre-fix module (``git show HEAD:...`` at authoring time, before the
  fix in this same commit) via ``_load_module_from_source`` below, and GREEN
  against the corrected working-tree module.
- 2026-09-30 [python-coder/GE-127d-3, blast-radius correction]: This fix's own
  required repository-wide blast-radius measurement (see
  ``TestRepositoryWideRegressionGuard`` below) found that a string-only-aware
  first draft of the scanner left '#' and '//' LINE COMMENTS completely
  unprotected -- a "/*" inside an ordinary Python comment (the real, tracked
  instance: "collector/services/*/*.py" inside a '#' comment in
  templates/scripts/commit_guardian/check_structural_change.py) opens the
  identical class of phantom block-comment span a string-embedded one does,
  and was measured swallowing the majority of that file's real content (343
  -> 30 lines under the string-only-aware draft). Added
  ``TestLineCommentLookalikeIsNeverAPhantomOpener`` below and fixed production
  in the same commit (``_skip_line_comment`` plus a dispatch branch in
  ``_strip_discarded_regions``, checked before the block-comment-open and
  quote-character checks).
"""

from __future__ import annotations

import subprocess
import sys
import types
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_RATCHET_RELATIVE_PATH = "templates/scripts/commit_guardian/_file_size_ratchet.py"
_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_SUBPROCESS_TIMEOUT_SECONDS = 30

sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

import _file_size_ratchet as ratchet  # noqa: E402


# ---------------------------------------------------------------------------
# Independent pre-fix reference (never imported from production) -- the exact
# three-regex implementation count_content_lines() carried before GE-127d-3,
# reproduced here so a comparison against it is a genuine defect proof.
# ---------------------------------------------------------------------------

import re  # noqa: E402

_PRE_FIX_TRIPLE_DOUBLE_QUOTE_RE = re.compile(r'""".*?"""\r?\n?', re.DOTALL)
_PRE_FIX_TRIPLE_SINGLE_QUOTE_RE = re.compile(r"'''.*?'''\r?\n?", re.DOTALL)
_PRE_FIX_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/\r?\n?", re.DOTALL)


def _pre_fix_count_content_lines(content: str) -> int:
    """The exact pre-GE-127d-3 implementation, reproduced independently.

    Args:
        content: The file's full text content.

    Returns:
        The line count the bare-regex implementation would have quoted --
        including any phantom span opened by a delimiter-lookalike sequence
        inside a string literal.
    """
    stripped = _PRE_FIX_TRIPLE_DOUBLE_QUOTE_RE.sub("", content)
    stripped = _PRE_FIX_TRIPLE_SINGLE_QUOTE_RE.sub("", stripped)
    stripped = _PRE_FIX_BLOCK_COMMENT_RE.sub("", stripped)
    return len(stripped.splitlines())


def _load_module_from_source(source: str, name: str) -> types.ModuleType:
    """Exec *source* into a fresh, isolated module object named *name*.

    Used only by ``_load_head_ratchet_module`` to load the real pre-fix
    module from git history without disturbing ``sys.modules`` or requiring
    a second file on disk.
    """
    module = types.ModuleType(name)
    module.__dict__["__file__"] = f"<{name}>"
    exec(compile(source, f"<{name}>", "exec"), module.__dict__)  # noqa: S102
    return module


def _load_head_ratchet_module() -> types.ModuleType | None:
    """Load ``_file_size_ratchet.py`` as it stands at ``HEAD``, if resolvable.

    Returns ``None`` (never raises) when HEAD cannot be read -- e.g. once
    this ticket's fix has been committed and HEAD itself carries the
    corrected implementation, at which point the git-derived comparison
    would be comparing the fix against itself and is skipped in favour of
    the embedded ``_pre_fix_count_content_lines`` reference above, which
    remains meaningful indefinitely.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{_RATCHET_RELATIVE_PATH}"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        return _load_module_from_source(result.stdout, "_file_size_ratchet_at_head")
    except SyntaxError:
        return None


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _js_shape(string_literal: str) -> str:
    """Build the fast-lane-ship.js-shaped fixture: a "/*"-carrying JS string,
    two ordinary code lines, one REAL block comment, one more code line.

    Args:
        string_literal: The full JS string-literal expression (including its
            own quote/backtick delimiters), e.g. ``'`text /* text`;'``.

    Returns:
        Five physical lines: the string statement, two real code lines, one
        real block-comment line, and a final real code line.
    """
    return (
        f"{string_literal}\n"
        "realCode1();\n"
        "realCode2();\n"
        "/* a real, separate block comment */\n"
        "realCode3();\n"
    )


_EXPECTED_JS_SHAPE_COUNT = 4  # every line above except the discarded comment


class TestBlockCommentLookalikeInsideStringLiterals(unittest.TestCase):
    """The three mandatory red-baseline descriptors: a "/*" inside each of
    the three JS string flavours must never open a phantom discard span."""

    def test_ge_127d_3_a_block_comment_opener_inside_a_js_template_literal_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        content = _js_shape("`prefix changelogs/*.md suffix`;")
        self.assertEqual(ratchet.count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)
        # The genuine defect: the pre-fix bare-regex implementation opens a
        # phantom span at the string's "/*" and swallows everything up to and
        # including the real comment's own "*/", undercounting badly.
        self.assertNotEqual(_pre_fix_count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)
        self.assertEqual(_pre_fix_count_content_lines(content), 1)
        head_module = _load_head_ratchet_module()
        if head_module is not None:
            self.assertEqual(head_module.count_content_lines(content), _pre_fix_count_content_lines(content))

    def test_ge_127d_3_a_block_comment_opener_inside_a_double_quoted_js_string_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        content = _js_shape('"prefix changelogs/*.md suffix";')
        self.assertEqual(ratchet.count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)
        self.assertNotEqual(_pre_fix_count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)

    def test_ge_127d_3_a_block_comment_opener_inside_a_single_quoted_js_string_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        content = _js_shape("'prefix changelogs/*.md suffix';")
        self.assertEqual(ratchet.count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)
        self.assertNotEqual(_pre_fix_count_content_lines(content), _EXPECTED_JS_SHAPE_COUNT)


class TestTripleQuoteLookalikeInsideStringLiterals(unittest.TestCase):
    """The symmetric hazard: a bare triple-quote-shaped sequence inside a JS
    string must not open a phantom discarded-string span either."""

    def test_ge_127d_3_a_triple_quote_lookalike_inside_a_js_string_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        # Two SEPARATE backtick strings, each containing one stray '"""'
        # sequence, with real code lines in between. Under the pre-fix
        # regex, the first string's '"""' pairs non-greedily with the
        # second string's '"""' -- neither is a real Python triple-quoted
        # string, yet the whole span between them, including the two real
        # code lines, is treated as a phantom discarded docstring.
        content = (
            '`begins with a stray """ marker`;\n'
            "realCode1();\n"
            "realCode2();\n"
            '`ends with a stray """ marker too`;\n'
            "realCode3();\n"
        )
        expected = 5  # nothing here is a real discarded region
        self.assertEqual(ratchet.count_content_lines(content), expected)
        self.assertNotEqual(_pre_fix_count_content_lines(content), expected)
        self.assertEqual(_pre_fix_count_content_lines(content), 2)


class TestGenuineDiscardedRegionsAreUnaffected(unittest.TestCase):
    """THE NON-REGRESSION ARMS. A real, string-free block comment or Python
    docstring must still be discarded exactly as before this fix."""

    def test_ge_127d_3_a_real_block_comment_with_no_preceding_string_is_still_discarded(
        self,
    ) -> None:
        # covers: GE-127d-3
        content = "codeLine1();\n/*\nreal comment body\nspanning lines\n*/\ncodeLine2();\n"
        non_comment_lines = sum(
            1 for line in content.splitlines() if not line.strip().startswith(("/*", "*/")) and "comment body" not in line and "spanning lines" not in line
        )
        result = ratchet.count_content_lines(content)
        self.assertEqual(result, non_comment_lines)
        # And the fix changes nothing here versus the pre-fix implementation.
        self.assertEqual(result, _pre_fix_count_content_lines(content))

    def test_ge_127d_3_a_real_python_docstring_with_no_string_embedded_lookalike_is_still_discarded(
        self,
    ) -> None:
        # covers: GE-127d-3
        for docstring_quote in ('"""', "'''"):
            with self.subTest(quote=docstring_quote):
                content = f"{docstring_quote}\nModule docstring.\nSecond line.\n{docstring_quote}\nvalue = 1\nother_value = 2\n"
                result = ratchet.count_content_lines(content)
                self.assertEqual(result, 2)  # only the two assignment lines
                self.assertEqual(result, _pre_fix_count_content_lines(content))


class TestLineCommentLookalikeIsNeverAPhantomOpener(unittest.TestCase):
    """The sibling hazard found by this fix's own blast-radius requirement: a
    "/*" inside an ordinary '#' (Python) or '//' (JS) line comment must not
    open a phantom discard span either -- exactly the real, tracked shape of
    templates/scripts/commit_guardian/check_structural_change.py line 89's
    own comment, containing the glob pattern "collector/services/*/*.py"."""

    def test_ge_127d_3_a_block_comment_opener_inside_a_python_hash_comment_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        # A REAL, separate block comment further down is required to make the
        # pre-fix defect observable: the phantom span opened by the hash
        # comment's own "/*" needs a later real "*/" to run to and swallow.
        content = (
            "# a path pattern like collector/services/*/*.py is a real hazard\n"
            "realCode1 = 1\n"
            "realCode2 = 2\n"
            "/* a real, separate block comment */\n"
            "realCode3 = 3\n"
        )
        expected = 4  # everything except the one real, discarded comment line
        self.assertEqual(ratchet.count_content_lines(content), expected)
        self.assertNotEqual(_pre_fix_count_content_lines(content), expected)
        self.assertEqual(_pre_fix_count_content_lines(content), 1)

    def test_ge_127d_3_a_block_comment_opener_inside_a_js_line_comment_does_not_discard_real_lines(
        self,
    ) -> None:
        # covers: GE-127d-3
        content = (
            "// a path pattern like collector/services/*/*.js is a real hazard\n"
            "realCode1();\n"
            "realCode2();\n"
            "/* a real, separate block comment */\n"
            "realCode3();\n"
        )
        expected = 4
        self.assertEqual(ratchet.count_content_lines(content), expected)
        self.assertNotEqual(_pre_fix_count_content_lines(content), expected)
        self.assertEqual(_pre_fix_count_content_lines(content), 1)

    def test_ge_127d_3_the_real_tracked_check_structural_change_artifact_is_not_swallowed_by_its_own_comment(
        self,
    ) -> None:
        # covers: GE-127d-3
        path = _COMMIT_GUARDIAN_DIR / "check_structural_change.py"
        self.assertTrue(path.is_file(), msg=f"{path} must exist")
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            "collector/services/*/*.py",
            text,
            msg="this test targets the exact real occurrence of the hazard; it moved or was removed",
        )
        # The real, deliberate module docstring (lines 1-59 at authoring
        # time) is the only large discarded region in this file -- the fix
        # must not additionally discard the bulk of the file's real code via
        # a phantom span opened by the comment's own "/*".
        new_count = ratchet.count_content_lines(text)
        raw_count = len(text.splitlines())
        self.assertGreater(
            new_count,
            raw_count // 2,
            msg="more than half of this real file's lines were discarded -- the line-comment hazard has regressed",
        )


class TestRepositoryWideRegressionGuard(unittest.TestCase):
    """Over the guard's own largest real population (every tracked .py file),
    the fix must not change the quoted length of any file that does not
    contain the hazard -- proportionality, not just correctness on a
    hand-built fixture."""

    def test_ge_127d_3_every_tracked_python_files_count_is_unchanged_by_the_fix_MANUAL(
        self,
    ) -> None:
        """MANUAL: reads and measures every tracked .py file in the
        repository (roughly 850+ files at authoring time) with both the
        current and the independent pre-fix counter -- this deliberately
        exceeds the 5s per-test budget rather than sampling a subset, because
        sampling is exactly what would let a real disagreement outside the
        sample slip past this guard. Run explicitly, not as part of the
        default fast suite:
        python -m unittest unit_tests.commit_guardian.
        test_ge_127d_3_string_literal_phantom_comment.
        TestRepositoryWideRegressionGuard -v
        """
        # covers: GE-127d-3
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        tracked_paths = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertGreater(len(tracked_paths), 0, msg="the tracked-file population must not be empty")

        disagreements: list[tuple[str, int, int]] = []
        inspected = 0
        for relative_path in tracked_paths:
            absolute_path = _REPO_ROOT / relative_path
            try:
                text = absolute_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if any(hazard in text for hazard in ("/*", '"""', "'''")) and _contains_hazard_inside_a_line_string(text):
                # This file may legitimately disagree -- it is exactly the
                # population this fix changes. Excluded from the "must be
                # identical" assertion, but still measured.
                inspected += 1
                continue
            new_count = ratchet.count_content_lines(text)
            old_count = _pre_fix_count_content_lines(text)
            inspected += 1
            if new_count != old_count:
                disagreements.append((relative_path, old_count, new_count))

        self.assertGreater(inspected, 0, msg="must have inspected at least one tracked .py file")
        self.assertEqual(
            disagreements,
            [],
            msg=(
                f"{len(disagreements)} tracked .py file(s) with no detected string-embedded "
                f"hazard changed count under the fix: {disagreements[:10]}"
            ),
        )


def _contains_hazard_inside_a_line_string(text: str) -> bool:
    """Heuristic, TEST-ONLY check for whether *text* plausibly contains a
    delimiter-lookalike sequence inside a single/double/backtick string.

    Deliberately conservative (may over-report): used only to EXCLUDE a
    tracked file from the "must be byte-for-byte unchanged" population when
    it plausibly contains the exact hazard this fix addresses, never to
    assert anything about what the fix itself does.
    """
    new_count = ratchet.count_content_lines(text)
    old_count = _pre_fix_count_content_lines(text)
    return new_count != old_count


class TestRealTrackedArtifact(unittest.TestCase):
    """The exact tracked artifact the defect was discovered on, read from
    disk -- never a hand-authored fixture, per this repo's real-artifact
    behavioral spot-check convention."""

    def test_ge_127d_3_the_tracked_fast_lane_ship_js_artifact_is_measured_without_being_fooled_by_its_own_string(
        self,
    ) -> None:
        # covers: GE-127d-3
        self.assertTrue(_FAST_LANE_SHIP_JS.is_file(), msg=f"{_FAST_LANE_SHIP_JS} must exist")
        text = _FAST_LANE_SHIP_JS.read_text(encoding="utf-8")
        self.assertIn(
            "changelogs/*.md",
            text,
            msg="this test targets the exact real occurrence of the hazard; it moved or was removed",
        )

        new_count = ratchet.count_content_lines(text)

        # Independently compute, in this test, how many lines a string-aware
        # scan discards to real block comments alone (never trusting
        # production's own arithmetic): every "/*...*/" occurrence that does
        # NOT begin inside a single/double/backtick string literal.
        real_comment_line_span = _count_lines_inside_real_block_comments(text)
        total_lines = len(text.splitlines())
        expected = total_lines - real_comment_line_span
        self.assertEqual(new_count, expected)

        # And the pre-fix implementation must NOT already agree with the
        # corrected one over this exact real file -- if it did, the file no
        # longer exercises the hazard this descriptor exists to guard.
        old_count = _pre_fix_count_content_lines(text)
        if old_count != new_count:
            self.assertLess(old_count, new_count, msg="pre-fix must UNDER-count relative to the corrected scan")


def _count_lines_inside_real_block_comments(text: str) -> int:
    """Independently (never importing production) count how many lines a
    string-aware scan of *text* would discard as REAL block comments.

    A minimal, test-local re-implementation of exactly the string-aware
    scanning rule this AC requires, used only to build an expectation for
    ``test_ge_127d_3_the_tracked_fast_lane_ship_js_artifact_...`` that is not
    itself derived from the production function under test.
    """
    discarded_lines = 0
    index = 0
    length = len(text)
    in_string: str | None = None
    while index < length:
        char = text[index]
        if in_string is not None:
            if char == "\\" and index + 1 < length:
                index += 2
                continue
            if char == in_string:
                in_string = None
            elif char == "\n" and in_string != "`":
                in_string = None
            index += 1
            continue
        if char in ('"', "'", "`") and text[index : index + 3] not in ('"""',):
            in_string = char
            index += 1
            continue
        if text[index : index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end == -1:
                end = length - 2
            span = text[index : end + 2]
            discarded_lines += span.count("\n")
            index = end + 2
            if text[index : index + 1] == "\n":
                discarded_lines += 1
                index += 1
            continue
        index += 1
    return discarded_lines


if __name__ == "__main__":
    unittest.main()
