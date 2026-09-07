"""
MODULE: unit_tests/ac_store/test_find_nodeid_for_test.py
GOAL: Direct unit coverage for ``done_proof._find_nodeid_for_test``, which has
    ZERO test coverage anywhere in the repo (confirmed by grep across
    scripts/, unit_tests/, and tests/ before this file was written).

=== The defect (blast radius: ACS-200f / ACS-200f-1) ===

``_find_nodeid_for_test`` (scripts/ac_store/done_proof.py:1043) matches a
covering test's bare function name against the pytest nodeid keys of a
``{nodeid: outcome}`` dict via a single ``suffix = f"::{func_name}"`` +
``str.endswith(suffix)`` check, tried first with a file-basename guard and
then without:

    suffix = f"::{func_name}"
    for nodeid in pytest_results:
        if nodeid.endswith(suffix) and file_basename in nodeid:
            return nodeid
    for nodeid in pytest_results:
        if nodeid.endswith(suffix):
            return nodeid
    return None

pytest emits a parametrized test's real nodeid as
``path::test_root_ids_return_true[ACS-100]`` (see the real producer's shape
at ``_PYTEST_RESULT_RE``, done_proof.py:102-105:
``r"^(\\S+::test_\\w+(?:\\[.*?\\])?)\\s+(OUTCOME)"``) -- it ends with ``]``,
never with ``::test_root_ids_return_true``, so BOTH loops above miss and the
function returns ``None``. Its only caller, ``_classify_outcomes``
(done_proof.py:1116), treats ``None`` as fail-closed and reports the test as
"linked test not run" even though it genuinely ran and passed. The same
function is imported and called by
``scripts/build_orchestration/fast_lane.py:1322``, so the fast lane inherits
the same defect.

=== Fixture authenticity ===

Every ``pytest_results`` dict here is shaped exactly like the real
``_parse_pytest_verbose_output`` producer's output (nodeid strings matching
``_PYTEST_RESULT_RE``'s own grammar) rather than an invented shape -- the
point of this file is to prove the matching function's OWN contract in
isolation. The real end-to-end seam (a genuine ``python -m pytest -v``
subprocess run producing these nodeids, piped into this same function via
``verify_done_eligible``) is exercised separately in
``test_acs200f_done_gate_strict_verification.py``, which this file
complements rather than duplicates.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from done_proof import _find_nodeid_for_test  # noqa: E402


class TestFindNodeidForTest(unittest.TestCase):
    """Direct coverage for the nodeid-matching oracle behind the done gate."""

    def test_plain_nodeid_matches(self) -> None:
        # covers: ACS-200f
        # angle: criterion
        """A plain, unparametrized nodeid matching file+function is found."""
        results = {"unit_tests/foo/test_bar.py::test_widget": "PASSED"}

        found = _find_nodeid_for_test("test_widget", "test_bar.py", results)

        self.assertEqual(found, "unit_tests/foo/test_bar.py::test_widget")

    def test_parametrized_nodeid_matches_bracket_suffix(self) -> None:
        # covers: ACS-200f
        # angle: boundary
        """A parametrized nodeid ``::func[PARAM]`` must still be found.

        This is the exact shape of the diagnosed defect: pytest emits
        ``path::test_widget[case1]`` for a parametrized test, which ends
        with ``]`` rather than the function name, so the current
        ``endswith(suffix)`` check misses it entirely and the caller reports
        a genuinely passing test as "linked test not run".
        """
        results = {
            "unit_tests/foo/test_bar.py::test_widget[case1]": "PASSED",
        }

        found = _find_nodeid_for_test("test_widget", "test_bar.py", results)

        self.assertEqual(
            found,
            "unit_tests/foo/test_bar.py::test_widget[case1]",
            "A parametrized nodeid must be located, not silently missed.",
        )

    def test_class_nested_parametrized_matches(self) -> None:
        # covers: ACS-200f
        # angle: boundary
        """A class-nested, parametrized nodeid must also be found."""
        results = {
            "unit_tests/foo/test_bar.py::TestWidget::test_widget[case1]": "PASSED",
        }

        found = _find_nodeid_for_test("test_widget", "test_bar.py", results)

        self.assertEqual(
            found,
            "unit_tests/foo/test_bar.py::TestWidget::test_widget[case1]",
        )

    def test_parametrized_param_id_containing_double_colon_resolves_to_outer_function(
        self,
    ) -> None:
        # covers: ACS-200f
        # angle: boundary
        """A parametrize id that itself contains ``::`` must not be mistaken
        for the file/function delimiter.

        This repository parametrizes tests over nodeid strings (the exact
        shape ``_find_nodeid_for_test`` itself consumes), so a real
        parameter id such as ``"path.py::test_x"`` is a realistic input, not
        a contrived one. A fix that takes the LAST ``::`` segment before
        stripping the bracket suffix would pick ``"test_x]"`` (or, after a
        naive bracket strip, ``"test_x"``) out of the parameter id instead of
        the real outer function name, silently reintroducing a false
        "linked test not run" refusal for exactly the kind of covering test
        this repo actually writes. Stripping the bracket FIRST (splitting on
        the first ``[``) and only then taking the last ``::`` segment avoids
        this, because a parameter suffix can never precede the function name
        in a real pytest nodeid.

        Confirmed via ``_PYTEST_RESULT_RE`` (done_proof.py) that this exact
        nodeid shape is what the regex captures intact from real pytest -v
        output -- this is not an invented fixture.
        """
        results = {
            "unit_tests/foo/test_bar.py::test_nodeid_matches_outer"
            "[path.py::test_x]": "PASSED",
        }

        found = _find_nodeid_for_test(
            "test_nodeid_matches_outer", "test_bar.py", results
        )

        self.assertEqual(
            found,
            "unit_tests/foo/test_bar.py::test_nodeid_matches_outer"
            "[path.py::test_x]",
            "The outer function name must be located even though the "
            "parameter id itself contains '::'.",
        )

    def test_does_not_match_longer_function_name_plain(self) -> None:
        # covers: ACS-200f
        # angle: boundary
        """Searching for ``test_foo`` must not match a longer sibling name.

        This is the trap in the obvious fix: a bare ``in`` check, or a
        ``startswith``/loosened boundary, would let ``test_foo_bar``
        satisfy a lookup for ``test_foo``. The real function name is
        ``test_foo_bar``, not ``test_foo`` -- they must never be confused.
        """
        results = {"unit_tests/foo/test_bar.py::test_foo_bar": "PASSED"}

        found = _find_nodeid_for_test("test_foo", "test_bar.py", results)

        self.assertIsNone(
            found,
            "test_foo must not match the unrelated test_foo_bar nodeid.",
        )

    def test_does_not_match_longer_function_name_parametrized(self) -> None:
        # covers: ACS-200f
        # angle: boundary
        """The same non-match must hold when the sibling is parametrized.

        This is the most important assertion in this file. A correct fix
        for the bracket-suffix defect above must strip exactly one trailing
        ``[...]`` segment and then compare the *whole remaining* name, not
        loosen the match into a substring/prefix check -- otherwise
        ``test_foo_bar[X]`` would satisfy a lookup for ``test_foo``.
        """
        results = {"unit_tests/foo/test_bar.py::test_foo_bar[X]": "PASSED"}

        found = _find_nodeid_for_test("test_foo", "test_bar.py", results)

        self.assertIsNone(
            found,
            "test_foo must not match the unrelated parametrized "
            "test_foo_bar[X] nodeid.",
        )

    def test_returns_none_when_nothing_matches(self) -> None:
        # covers: ACS-200f
        # angle: criterion
        """No candidate at all yields None, not an exception."""
        results = {"unit_tests/foo/test_bar.py::test_other": "PASSED"}

        found = _find_nodeid_for_test("test_widget", "test_bar.py", results)

        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
