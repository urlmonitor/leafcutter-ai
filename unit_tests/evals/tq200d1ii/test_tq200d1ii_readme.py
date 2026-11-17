"""
MODULE: unit_tests/evals/tq200d1ii/test_tq200d1ii_readme.py
GOAL: RED test for TQ-200d-1-ii: scripts/evals/README.md links the hub page (the link resolves) and its
    produced-tests section names no registered kind outside a per-rule line that links an entry.
Target: scripts/evals/README.md, docs/reference/produced-tests-eval-assertion-kinds.md
"""

from __future__ import annotations

import re

import unit_tests.evals.tq200d1ii._helpers as h
import unit_tests.evals.tq200d1ii._pageset as ps

README = h.REPO_ROOT / "scripts" / "evals" / "README.md"
BASE = "scripts/evals"
HUB_LINK = "../../docs/reference/" + h.HUB
INLINE = re.compile(r"Kinds: `fixture_seeds_moved_input`.*?`wrong_version_run`\.", re.S)
HUB_TARGET = re.compile(r"\]\([^)\s]*" + re.escape(h.HUB) + r"[^)\s]*\)")
KINDS3 = ["fixture_seeds_moved_input", "counts_rows_and_non_null", "wrong_version_run"]


def gold_readme() -> str:
    """The real README with its inline kind list (when it still has one) swapped for the hub link."""
    text = README.read_text(encoding="utf-8")
    return INLINE.sub(f"Each kind is described, with examples, in the [assertion-kinds reference]({HUB_LINK}).", text)


def test_evals_readme_links_the_hub_and_lists_no_kind_names(tmp_path):
    # covers: TQ-200d-1-ii
    # angle: real_artifact
    # must_catch: README still lists the kind names inline
    """The REAL README links the hub and lists no kind name; the inline list brought back, or the link lost, is caught."""
    real = README.read_text(encoding="utf-8")
    assert h.check_readme(real, BASE, h.REPO_ROOT) == set(), "the real README must link the hub and list no kind names"
    ps.write_pages(tmp_path, ps.gold_pages())
    gold = gold_readme()
    assert h.check_readme(gold, BASE, tmp_path) == set()
    # the kind names listed inline again (the state before this AC), in the produced-tests section
    listed = gold.replace("- **Offline.**", "- **Kinds.** " + ", ".join(f"`{k}`" for k in KINDS3) + ".\n- **Offline.**", 1)
    assert h.check_readme(listed, BASE, tmp_path) == {("kind_name", k) for k in KINDS3}
    # the link lost
    assert h.check_readme(HUB_TARGET.sub("](#scoring)", gold), BASE, tmp_path) == {("no_hub_link", "")}
    # the link kept but the page is not there
    assert h.check_readme(gold, BASE, tmp_path / "empty") == {("broken_hub_link", "")}
    # a per-rule line that links ONE entry may name its kind; a link line naming three may not
    entry_link = f"../../docs/reference/{h.FAMILY_PAGE['test-writer']}#wrong_version_run"
    one = gold.replace("- **Offline.**", f"- **Rule.** `wrong_version_run` is described in [its entry]({entry_link}).\n- **Offline.**", 1)
    assert h.check_readme(one, BASE, tmp_path) == set()
    three = one.replace("`wrong_version_run` is", "`wrong_version_run`, `fixture_seeds_moved_input` and `counts_rows_and_non_null` are")
    assert h.check_readme(three, BASE, tmp_path) == {("kind_name", k) for k in KINDS3}
    # control: a kind name in another section of the README is not this AC's business
    other = gold + "\n## Elsewhere\n\nThe `fixture_seeds_moved_input` kind is mentioned here.\n"
    assert h.check_readme(other, BASE, tmp_path) == set()
