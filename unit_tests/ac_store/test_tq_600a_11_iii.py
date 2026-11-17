"""
RED test stubs for TQ-600a-11-iii -- "The agreement check is shown to
disagree when the two parsers really differ."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-11-iii.yaml
(test_spec + test_rationale; that record's YAML wins wherever a summary here
differs).

======================================================================
This file imports `_compare_all_records` / `_parse_both` / `_PARSE_FAILED`
directly from test_tq_600a_11_ii.py -- the injection seam TQ-600a-11-iii's
own expects_from names as required ("a way to inject one additional input
into its compared set... the injection seam is part of what TQ-600a-11-ii
must deliver"). Every test below therefore shares the same ASSUMED
PRODUCTION CONTRACT dependency (scripts/ac_store/yaml_safe_loader.py, not
yet implemented) and fails via the identical ModuleNotFoundError path the
sibling file documents.

OBSERVE THE DIVERGENCE BEFORE RELYING ON IT (per this AC's own
it_requirement). PROBE NOTES, observed at test-authoring time (2026-10-05,
this installed PyYAML, yaml.__with_libyaml__ == True) -- the full
duplicate-key -> timestamp -> numeric -> merge-key escalation the AC
prescribes was tried FIRST, in that order, before settling on a different
input:
  - duplicate key ("a: 1\\na: 2"): AGREES ({"a": 2} both sides) -- moved on.
  - timestamp scalar: AGREES -- moved on.
  - ambiguous numeric forms (leading-zero, underscore, sexagesimal, hex):
    AGREE -- moved on.
  - merge key (single-anchor and list-of-anchors forms): AGREE -- moved on.
  - 600 levels of nested empty flow sequences ("[" * 600 + "]" * 600):
    DIVERGES. The pure-Python safe parser raises RecursionError (Python's
    default recursion limit of 1000, exceeded by PyYAML's own recursive
    descent well before 600 nesting levels are reached once the surrounding
    test/interpreter call stack is counted); the C-backed loader (reached
    via the shared accessor) parses the identical text successfully and
    returns an ordinary (deeply-nested, empty) list value. This is the
    chosen input, named here per the it_requirement "if the chosen input
    turns out to produce equal objects under the installed library, a
    different input is found, and the one actually used is named in the
    test."

Per this AC's it_requirement "THE DIVERGENT INPUT NEVER TOUCHES
docs/acceptance-criteria/": `_DIVERGENT_TEXT` below is a Python string
literal held only in this test's own fixture space and injected via
`_compare_all_records(extra_records=...)`; it is never written to the real
AC store.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_DIR))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tq_600a_11_ii import _PARSE_FAILED, _compare_all_records, _parse_both  # noqa: E402

_DIVERGENT_ID = "tq600a_11_iii_fixture_recursion_depth_600"
_DIVERGENT_TEXT = "[" * 600 + "]" * 600


class TestTq600a11iiiDivergentInputMakesComparisonFail(unittest.TestCase):
    def test_tq600a_11_iii_a_genuinely_divergent_input_makes_the_comparison_fail(self):
        # covers: TQ-600a-11-iii
        # angle: failure
        """
        With the divergent input in the compared set, the comparison
        reports it as a disagreement and names both the input id and the
        differing detail (here: which side raised).
        """
        result = _compare_all_records(extra_records=[(_DIVERGENT_ID, _DIVERGENT_TEXT)])
        disagreement = next(
            (d for d in result["disagreements"] if d["id"] == _DIVERGENT_ID),
            None,
        )
        self.assertIsNotNone(
            disagreement,
            f"the divergent input {_DIVERGENT_ID!r} was not reported as a "
            f"disagreement (disagreements found: {result['disagreements']})",
        )
        self.assertIn(
            "raised",
            disagreement["detail"],
            f"disagreement detail does not name which side raised: {disagreement!r}",
        )


class TestTq600a11iiiPairedCleanRunAttributesTheCause(unittest.TestCase):
    def test_tq600a_11_iii_the_same_comparison_without_that_input_is_clean(self):
        # covers: TQ-600a-11-iii
        # angle: criterion
        """
        The paired control: the identical comparison, over the identical
        real store, WITHOUT the divergent input, is clean. Together with
        the test above, this shows the non-zero outcome is attributable to
        the input rather than to the harness -- a single red run alone is
        also what a broken harness looks like.
        """
        result = _compare_all_records()
        self.assertEqual(
            result["disagreements"],
            [],
            f"the comparison over the real store alone (no injected "
            f"divergent input) was not clean: {result['disagreements']}",
        )


class TestTq600a11iiiChosenInputObservedToDiverge(unittest.TestCase):
    def test_tq600a_11_iii_the_chosen_input_is_observed_to_diverge_under_the_installed_library(self):
        # covers: TQ-600a-11-iii
        # angle: boundary
        """
        Parse the chosen input directly with both parsers (bypassing the
        comparison harness entirely) and assert the two outcomes are
        UNEQUAL. This is the guard on the guard: if a future PyYAML upgrade
        makes the two agree on 600 levels of nested empty flow sequences,
        this descriptor goes red and names the problem here, instead of the
        can-fail test above silently becoming a can-not-fail test that is
        green forever for the wrong reason.
        """
        pure, theirs = _parse_both(_DIVERGENT_TEXT)
        self.assertNotEqual(
            pure,
            theirs,
            "the chosen divergent input no longer diverges under the "
            "installed PyYAML -- the can-fail test above would be a "
            "can-not-fail test; choose a different input (see this file's "
            "module docstring PROBE NOTES escalation order) and update "
            "_DIVERGENT_TEXT in both this file and test_tq_600a_11_ii.py.",
        )
        self.assertIs(
            pure,
            _PARSE_FAILED,
            "expected the pure-Python safe parser to raise (RecursionError) "
            "on 600 levels of nested empty flow sequences",
        )
        self.assertIsNot(
            theirs,
            _PARSE_FAILED,
            "expected the accessor (C-backed) parser to succeed on 600 "
            "levels of nested empty flow sequences",
        )


if __name__ == "__main__":
    unittest.main()
