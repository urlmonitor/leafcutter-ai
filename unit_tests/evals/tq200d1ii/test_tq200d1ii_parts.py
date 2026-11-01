"""
MODULE: unit_tests/evals/tq200d1ii/test_tq200d1ii_parts.py
GOAL: RED drift test for TQ-200d-1-ii: every entry has all seven labelled parts, once, each non-empty.
Target: docs/reference/produced-tests-eval-assertion-kinds-*.md
"""

from __future__ import annotations

import unit_tests.evals.tq200d1ii._helpers as h
import unit_tests.evals.tq200d1ii._pageset as ps


def _reverse(block: str) -> str:
    head, *parts = block.split("\n**")
    return "\n**".join([head, *reversed(parts)])


def test_every_entry_has_all_required_parts():
    # covers: TQ-200d-1-ii
    # angle: real_artifact
    # must_catch: an entry with one of the seven parts missing, empty or repeated
    """The REAL entries carry all seven parts; each part removed, emptied or repeated is caught by its label."""
    real = h.read_real_pages()
    assert len(h.all_entries(real)) == len(h.family_of()), "the real pages must hold one entry per registered kind"
    assert h.check_parts(real) == set()
    gold = ps.gold_pages()
    assert h.check_parts(gold) == set()
    kind = ps.quoted_kind(gold)
    for label in h.PARTS:
        gone = ps.edit_entry(gold, kind, lambda b, lab=label: ps.drop_label(b, lab))
        assert h.check_parts(gone) == {(f"missing_part:{label}", kind)}, label
        empty = ps.edit_entry(gold, kind, lambda b, lab=label: ps.empty_label(b, lab))
        assert h.check_parts(empty) == {(f"empty_part:{label}", kind)}, label
        twice = ps.edit_entry(gold, kind, lambda b, lab=label: b + f"\n**{lab}:** again.\n")
        assert h.check_parts(twice) == {(f"repeated_part:{label}", kind)}, label
    # a label written inside a fenced example does not stand in for the missing part
    no_reads = ps.edit_entry(gold, kind, lambda b: ps.drop_label(b, "Reads"))
    fenced = ps.edit_entry(no_reads, kind, lambda b: b + "\n```\n**Reads:** the report.\n```\n")
    assert h.check_parts(fenced) == {("missing_part:Reads", kind)}
    # control: the same parts in another order are still all there
    assert h.check_parts(ps.edit_entry(gold, kind, _reverse)) == set()
