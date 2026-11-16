"""
MODULE: unit_tests/evals/tq200d1ii/test_tq200d1ii_kinds.py
GOAL: RED drift test for TQ-200d-1-ii: the entries ("### `<kind>`") over the four family pages are
    exactly the kinds of produced_tests_scoring.KINDS, each on the page of its registering module,
    none on two pages.
Target: docs/reference/produced-tests-eval-assertion-kinds-*.md, scripts/evals/produced_tests_scoring.py
"""

from __future__ import annotations

import unit_tests.evals.tq200d1ii._helpers as h
import unit_tests.evals.tq200d1ii._pageset as ps


def test_every_registered_kind_has_exactly_one_entry():
    # covers: TQ-200d-1-ii
    # angle: real_artifact
    # must_catch: kind registered with no entry on any page; entry left on a page for a kind no longer registered; one kind given entries on two family pages
    """The REAL pages carry one entry per registered kind; bad copies (one swap each) are caught by name."""
    assert h.check_kinds(h.read_real_pages()) == set(), "the real pages must hold exactly one entry per registered kind"
    gold = ps.gold_pages()
    fam = h.family_of()
    assert h.check_kinds(gold) == set()
    assert len(h.all_entries(gold)) == len(fam) > 0, "exactly one entry per kind, counted across the pages"
    kind = sorted(k for k, f in fam.items() if f == "test-designer")[0]
    own, other = h.FAMILY_PAGE["test-designer"], h.FAMILY_PAGE["test-writer"]
    # a kind registered with no entry on any page
    assert h.check_kinds(ps.drop_entry(gold, kind)) == {("missing", kind)}
    # an entry left for a kind no longer registered
    assert h.check_kinds(ps.add_entry(gold, own, "retired_kind_xyz", like=kind)) == {("stale", "retired_kind_xyz")}
    # one kind given entries on two family pages
    twice = ps.add_entry(gold, other, kind, like=kind)
    assert h.check_kinds(twice) == {("on_two_pages", kind)}
    # the entry sits on the family page of a module that does not register it
    moved = {**twice, own: ps.drop_entry(gold, kind)[own]}
    assert h.check_kinds(moved) == {("wrong_page", kind)}
    # the hub holds no entries: an entry there is on the wrong page
    on_hub = ps.add_entry(ps.drop_entry(gold, kind), h.HUB, kind, like=next(k for k in fam if k != kind))
    assert h.check_kinds(on_hub) == {("wrong_page", kind)}
    # a whole family page missing
    gone = {n: t for n, t in gold.items() if n != own}
    assert h.check_kinds(gone) == {("missing_page", own)} | {("missing", k) for k, f in fam.items() if f == "test-designer"}
    # controls: a heading in a fenced example and a level-4 heading are not entries
    fenced = dict(gold)
    fenced[other] += "\n```\n### `ghost_kind`\n```\n\n#### `ghost_two`\n"
    assert h.check_kinds(fenced) == set()
    # the module that registers a kind decides its page (derived, not listed): four families, all used
    assert fam["wrong_version_run"] == "test-writer" and len(set(fam.values())) == 4
