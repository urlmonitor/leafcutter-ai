"""
MODULE: unit_tests/evals/tq200d1ii/test_tq200d1ii_quotes.py
GOAL: RED drift test for TQ-200d-1-ii: every blockquoted template sentence on the family pages appears,
    whitespace-normalised, in the template file the entry names.
Target: docs/reference/produced-tests-eval-assertion-kinds-*.md, templates/agents/*.md
"""

from __future__ import annotations

import re

import unit_tests.evals.tq200d1ii._helpers as h
import unit_tests.evals.tq200d1ii._pageset as ps


def _recase(block: str) -> str:
    return re.sub(r"^> (\w)", lambda m: "> " + m.group(1).swapcase(), block, count=1, flags=re.M)


def _pad(block: str) -> str:
    return re.sub(r"^>.*$", lambda m: m.group(0).replace(" ", "   "), block, flags=re.M)


def test_quoted_template_sentences_appear_verbatim():
    # covers: TQ-200d-1-ii
    # angle: real_artifact
    # must_catch: quoted sentence reworded on the page but not in the template; quote attributed to the wrong template
    """The REAL quotes are verbatim in their templates; a reworded quote and a mis-attributed one are caught."""
    root = h.REPO_ROOT
    real = h.read_real_pages()
    assert h.check_quotes(real, root) == set(), "every real quote must be verbatim in its template"
    assert len(h.all_entries(real)) == len(h.family_of()), "the real pages must hold the entries whose quotes are checked"
    gold = ps.gold_pages()
    assert h.check_quotes(gold, root) == set()
    kind = ps.quoted_kind(gold)
    # a quoted sentence reworded on the page (a word added; one letter's case changed)
    added = ps.edit_entry(gold, kind, lambda b: re.sub(r"^> (.*)$", r"> \1 extra", b, count=1, flags=re.M))
    assert h.check_quotes(added, root) == {("not_verbatim", kind)}
    assert h.check_quotes(ps.edit_entry(gold, kind, _recase), root) == {("not_verbatim", kind)}
    # a quote attributed to the wrong template (the real sentence, a template that lacks it)
    entry = next(e for _n, e in h.all_entries(gold) if e["kind"] == kind)
    quote, path = h.quotes_of(entry)[0]
    wrong = ps.template_lacking(quote, path.rsplit("/", 1)[1])
    assert h.check_quotes(ps.edit_entry(gold, kind, lambda b: ps.swap_template_path(b, wrong)), root) == {("not_verbatim", kind)}
    # a template path that does not exist, and a quote with no path line
    nope = ps.edit_entry(gold, kind, lambda b: ps.swap_template_path(b, "no-such-agent.md"))
    assert h.check_quotes(nope, root) == {("no_such_template", kind)}
    nopath = ps.edit_entry(gold, kind, lambda b: re.sub(r"^- templates/agents/[\w.-]+\.md\s*$", "", b, count=1, flags=re.M))
    assert h.check_quotes(nopath, root) == {("no_template_path", kind)}
    # a Template sentence part with neither a quote nor 'none'
    noquote = ps.edit_entry(gold, kind, lambda b: b[: b.index("**Template sentence:**")] + "**Template sentence:** see the template.\n")
    assert h.check_quotes(noquote, root) == {("no_quote", kind)}
    # control: the same sentence padded with spaces still matches (whitespace-normalised)
    assert h.check_quotes(ps.edit_entry(gold, kind, _pad), root) == set()
