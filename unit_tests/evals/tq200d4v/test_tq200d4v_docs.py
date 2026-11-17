"""
MODULE: unit_tests/evals/tq200d4v/test_tq200d4v_docs.py
COVERS: TQ-200d-4-v
GOAL: The report_says_not_run entry of the database-setting reference page quotes the test-runner
    template sentence "The database tests were not run." (not the old 'Do NOT attempt to run' line)
    with templates/agents/test-runner.md and uses the relayed block as its passing example, and the
    evals README names the sentence and links #report_says_not_run.
RED STATE: the entry still quotes 'Do NOT attempt to run the SQL suite ...' and the README has no bullet.
"""

from __future__ import annotations

import re

import unit_tests.evals.tq200d1ii._helpers as d1ii
import unit_tests.evals.tq200d4v._helpers as h

PAGE = "produced-tests-eval-assertion-kinds-database-setting.md"
OLD_SENTENCE = "Do NOT attempt to run the SQL suite unless the checker reports `reachable`."
README = h.REPO_ROOT / "scripts" / "evals" / "README.md"
TEMPLATE_PATH = "templates/agents/test-runner.md"


def _entry() -> dict:
    page = (h.REPO_ROOT / d1ii.REF_DIR / PAGE).read_text(encoding="utf-8")
    entries = [e for e in d1ii.parse_page(page) if e["kind"] == h.NOT_RUN]
    assert len(entries) == 1, f"the page must hold exactly one {h.NOT_RUN} entry, got {len(entries)}"
    return entries[0]


def _plain(lines: list[str]) -> str:
    """Entry lines with fences, blockquote markers and quote marks removed, whitespace-normalised."""
    kept = [re.sub(r"^\s*>\s?", "", ln) for ln in lines if not ln.lstrip().startswith("```")]
    return d1ii.norm(" ".join(kept).replace('"', ""))


def test_report_says_not_run_entry_quotes_the_test_runner_sentence():
    # covers: TQ-200d-4-v
    # angle: real_artifact
    # must_catch: the entry still quotes the old 'Do NOT attempt to run' sentence as its template sentence
    """Entry quotes the new sentence, passes with the extracted block, and the README bullet names it."""
    entry = _entry()
    quotes = d1ii.quotes_of(entry)
    assert [q for q, _p in quotes] == [h.SENTENCE], \
        f"the template sentence part must quote exactly {h.SENTENCE!r}, got {[q for q, _p in quotes]}"
    assert all(path == TEMPLATE_PATH for _q, path in quotes), f"the quote must cite {TEMPLATE_PATH}"
    assert OLD_SENTENCE not in "\n".join(sum(entry["parts"].values(), [])), "the old sentence must not remain"
    template_text = d1ii.norm(h.TEMPLATE.read_bytes().decode("utf-8"))
    assert h.SENTENCE in template_text, "the quoted sentence must be in the template"

    passing = _plain(entry["parts"].get("Passing example", []))
    body = d1ii.norm(h.template_block().split("\n", 1)[1].replace('"', ""))
    assert body in passing, "the passing example must be the not_configured block as the template holds it"
    assert passing.rstrip(". ").endswith(h.SENTENCE.rstrip(".")), "the passing example must end with the sentence"

    readme = README.read_text(encoding="utf-8")
    bullets = [b for b in re.split(r"\n(?=- )", readme) if h.SENTENCE.rstrip(".") in b]
    assert bullets, f"scripts/evals/README.md must name {h.SENTENCE!r} in a bullet"
    assert any("#report_says_not_run" in b and "Database Not Configured" in b for b in bullets), \
        "the README bullet must link #report_says_not_run and name the 'Database Not Configured' message"
