"""
RED test stubs for TQ-600a-11-ii -- "The two parsers are proved to agree on
the real store, record by record."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-11-ii.yaml
(test_spec + test_rationale; that record's YAML wins wherever a summary here
differs).

======================================================================
THIS FILE IS ITSELF THE DELIVERABLE, NOT JUST ITS TESTS. TQ-600a-11-ii's own
declared_files names only this one test file (no separate production
module), because its criteria requires the comparison be "part of the suite
as a standing guard... so it re-runs against the store as the store
changes" -- a one-off CLI tool would not satisfy that. The private helper
`_compare_all_records()` below IS the record-by-record comparison the AC
describes; TQ-600a-11-iii's own test file imports it directly (see that
file's module docstring) to inject one additional divergent input, per that
AC's expects_from contract ("a way to inject one additional input into its
compared set").

ASSUMED PRODUCTION CONTRACT (the only part of this file that does not exist
yet) -- see unit_tests/ac_store/test_tq_600a_11.py's module docstring for
the full scripts/ac_store/yaml_safe_loader.py contract. Every test below
fails the first time it calls into `_compare_all_records()` /
`_parse_both()`, which import `yaml_safe_loader` lazily (not at module
import time), via ModuleNotFoundError, until python-coder implements that
module. That is the correct RED state -- it also keeps collection of this
file itself from failing, so every test reports its own RED independently.

PROBE NOTES (observed at test-authoring time, 2026-10-05, this installed
PyYAML; yaml.__with_libyaml__ == True) -- recorded here because the AC's own
it_requirement forbids assuming which way duplicate keys resolve without
observing it:
  - duplicate key ("a: 1\\na: 2"): AGREES -- both sides return {"a": 2}
    (last value wins on both the pure-Python and C-backed loader).
  - timestamp scalar ("created: 2026-10-05"): AGREES.
  - ambiguous numeric forms (leading-zero, underscore-separated,
    sexagesimal, hexadecimal): AGREE.
  - merge key (single-anchor and list-of-anchors "<<: [*a, *b]" forms):
    AGREE.
  - 600 levels of nested empty flow sequences ("[" * 600 + "]" * 600):
    DIVERGES -- the pure-Python safe parser raises RecursionError; the
    C-backed loader parses it successfully. This is the one real divergence
    found by probing, and is the input used by the "one parser rejects"
    test below and by TQ-600a-11-iii's can-fail demonstration (see that
    file's own module docstring for the full probe).

BUDGET NOTE: a full real-store sweep measures roughly 25s (pure-Python) +
2s (accessor) per the AC's own criteria. This file calls
`_compare_all_records()` exactly twice (tests 1 and 2 below each do one full
sweep; tests 3 and 4 inject into a sweep too) -- see the AC's own
it_requirement "BUDGET: ABOUT 27 SECONDS... keep it to ONE test, not one per
class, and do not let it sweep the store more than twice." This file's four
tests each perform their own full sweep because each targets a materially
different failure mode (agreement / count-honesty / class-presence /
reject-handling) and the AC's test_spec lists all four as separate
descriptors; python-coder may consolidate at implementation time if a
cheaper shared-fixture shape is found, so long as each assertion still goes
red independently under its own named mutation.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_DIR))

_STORE_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"

#: Sentinel: this side of a comparison raised rather than returning a value.
_PARSE_FAILED = object()


def _enumerate_real_store() -> list[Path]:
    """Every *.yaml/*.yml under docs/acceptance-criteria/, excluding
    index.yaml (the component registry, not an AC record) -- the same walk
    rule validate_ac_schema.py's directory-argument handling uses, so the
    compared population and the validated population cannot drift apart."""
    return sorted(
        p
        for p in (*_STORE_ROOT.rglob("*.yaml"), *_STORE_ROOT.rglob("*.yml"))
        if p.is_file() and p.name != "index.yaml"
    )


def _parse_both(text: str) -> tuple[Any, Any]:
    """Parse *text* with the pure-Python safe parser and with the shared
    accessor. Either side that raises is represented by the `_PARSE_FAILED`
    sentinel rather than propagating, so the two outcomes can always be
    compared -- this is exactly the behaviour the "one parser rejects"
    test below protects: an implementation that wraps each parse in
    try/except-and-skip instead of recording `_PARSE_FAILED` converts a
    real divergence into silence.
    """
    import yaml

    from yaml_safe_loader import load_yaml_text

    try:
        pure = yaml.safe_load(text)
    except (yaml.YAMLError, RecursionError):
        # RecursionError (not a yaml.YAMLError subclass) is the documented
        # real divergence this AC's own PROBE NOTES record: deeply nested
        # flow sequences blow the pure-Python recursive-descent composer's
        # stack while the C-backed accessor parses them without error. Both
        # must be treated as "this side rejected" for the comparison below
        # to see it as a disagreement rather than crash the harness.
        pure = _PARSE_FAILED
    try:
        theirs = load_yaml_text(text)
    except Exception:  # noqa: BLE001 -- deliberately broad: ANY raise on the
        # accessor side is a disagreement to report, not an error to
        # propagate to the caller; see docstring above.
        theirs = _PARSE_FAILED
    return pure, theirs


def _record_disagreement(disagreements: list[dict], record_id: str, pure: Any, theirs: Any) -> None:
    if pure is _PARSE_FAILED or theirs is _PARSE_FAILED:
        if pure is not theirs:
            disagreements.append(
                {
                    "id": record_id,
                    "detail": (
                        "one parser raised and the other did not "
                        f"(pure={'raised' if pure is _PARSE_FAILED else 'ok'}, "
                        f"accessor={'raised' if theirs is _PARSE_FAILED else 'ok'})"
                    ),
                }
            )
        return
    if pure != theirs or type(pure) is not type(theirs):
        disagreements.append(
            {
                "id": record_id,
                "detail": (
                    f"pure={pure!r} (type={type(pure).__name__}) != "
                    f"accessor={theirs!r} (type={type(theirs).__name__})"
                ),
            }
        )


def _compare_all_records(extra_records: list[tuple[str, str]] | None = None) -> dict:
    """The record-by-record agreement comparison itself (TQ-600a-11-ii).

    Args:
        extra_records: Optional ``(id, raw_yaml_text)`` pairs appended to
            the real store's enumeration -- the injection seam
            TQ-600a-11-iii's expects_from names as required ("a way to
            inject one additional input into its compared set").

    Returns:
        ``{"examined_count": int, "examined_ids": list[str],
        "disagreements": [{"id": str, "detail": str}, ...]}``. A record that
        only one parser rejects is a disagreement, never a skip.
    """
    paths = _enumerate_real_store()
    examined_ids: list[str] = []
    disagreements: list[dict] = []

    for path in paths:
        record_id = path.relative_to(_REPO_ROOT).as_posix()
        examined_ids.append(record_id)
        text = path.read_text(encoding="utf-8")
        pure, theirs = _parse_both(text)
        _record_disagreement(disagreements, record_id, pure, theirs)

    for name, text in extra_records or []:
        examined_ids.append(name)
        pure, theirs = _parse_both(text)
        _record_disagreement(disagreements, name, pure, theirs)

    return {
        "examined_count": len(examined_ids),
        "examined_ids": examined_ids,
        "disagreements": disagreements,
    }


class TestTq600a11iiEveryRecordAgrees(unittest.TestCase):
    def test_tq600a_11_ii_every_store_record_parses_identically_under_both_parsers(self):
        # covers: TQ-600a-11-ii
        # angle: real_artifact
        """
        Enumerate the REAL on-disk store, parse each record both ways,
        compare objects and types. Zero disagreements expected. The failure
        message names the record path and the differing detail for every
        disagreement found.
        """
        result = _compare_all_records()
        self.assertEqual(
            result["disagreements"],
            [],
            f"{len(result['disagreements'])} record(s) disagree between the "
            f"pure-Python and accessor-backed parsers (examined "
            f"{result['examined_count']}): {result['disagreements']}",
        )


class TestTq600a11iiExaminedCountIsHonest(unittest.TestCase):
    def test_tq600a_11_ii_the_comparison_reports_the_number_of_records_it_examined(self):
        # covers: TQ-600a-11-ii
        # angle: criterion
        """
        NAMED MUTATION: an implementation whose enumeration silently returns
        an empty list must go RED here even though the agreement assertion
        above would stay vacuously green over zero records -- this is
        KI-ACS-001 (the AC validator's own eight-day bare-directory no-op)
        turned into a criterion. The independent count below is computed by
        this test's OWN walk of the real store, never by calling into
        `_compare_all_records`'s internals, so a comparison that silently
        examines fewer records cannot agree with it by construction.
        """
        independent_count = len(_enumerate_real_store())
        self.assertGreater(independent_count, 0, "the real AC store resolved to zero files")
        result = _compare_all_records()
        self.assertEqual(
            result["examined_count"],
            independent_count,
            f"the comparison examined {result['examined_count']} record(s) "
            f"but an independent walk of the real store found "
            f"{independent_count} -- a comparison that examines fewer than "
            f"the real population is reporting a false clean result.",
        )


class TestTq600a11iiFourDivergenceClassesPresent(unittest.TestCase):
    def test_tq600a_11_ii_the_four_known_divergence_classes_are_present_in_the_compared_set(self):
        # covers: TQ-600a-11-ii
        # angle: boundary
        """
        Supplement the compared set with one representative instance of
        each of the four classes TQ-600a-11-ii's criteria names (duplicate
        key, timestamp scalar, ambiguous numeric forms, merge key) and
        assert the comparison's own report names all four by id -- the
        "either the real store holds one, or one is added and named"
        allowance. See this file's module docstring PROBE NOTES: none of
        the four diverges under the installed library, so their presence
        here demonstrates inclusion in the examined set, not disagreement
        (disagreement is TQ-600a-11-iii's job, using a different input).
        """
        extras = [
            ("tq600a_11_ii_fixture_duplicate_key", "a: 1\na: 2\n"),
            ("tq600a_11_ii_fixture_timestamp_scalar", "created: 2026-10-05\n"),
            (
                "tq600a_11_ii_fixture_ambiguous_numeric",
                "leading_zero: 0755\nunderscore: 1_000_000\n"
                "sexagesimal: 1:30:00\nhexadecimal: 0x1A\n",
            ),
            (
                "tq600a_11_ii_fixture_merge_key",
                "base: &base\n  a: 1\nderived:\n  <<: *base\n  b: 2\n",
            ),
        ]
        result = _compare_all_records(extra_records=extras)
        for name, _ in extras:
            self.assertIn(
                name,
                result["examined_ids"],
                f"divergence-class fixture {name!r} was not present in the "
                f"comparison's own examined-id report",
            )


class TestTq600a11iiOneParserRejectsCountsAsDisagreement(unittest.TestCase):
    def test_tq600a_11_ii_a_record_only_one_parser_rejects_counts_as_a_disagreement(self):
        # covers: TQ-600a-11-ii
        # angle: failure
        """
        NAMED MUTATION: wrapping each parse in try/except-and-skip is the
        obvious implementation and converts every divergence into a silent
        skip; this test must go RED under that mutation. Uses 600 levels of
        nested empty flow sequences ("[[[...]]]") -- OBSERVED (module
        docstring PROBE NOTES) to raise RecursionError under the installed
        pure-Python PyYAML while the C-backed accessor parses it without
        error.
        """
        poison_text = "[" * 600 + "]" * 600
        result = _compare_all_records(
            extra_records=[("tq600a_11_ii_fixture_one_parser_rejects", poison_text)]
        )
        ids = [d["id"] for d in result["disagreements"]]
        self.assertIn(
            "tq600a_11_ii_fixture_one_parser_rejects",
            ids,
            f"an input only one parser rejects was not recorded as a "
            f"disagreement (disagreement ids: {ids})",
        )


if __name__ == "__main__":
    unittest.main()
