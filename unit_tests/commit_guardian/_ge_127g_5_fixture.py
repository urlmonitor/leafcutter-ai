"""
MODULE: unit_tests/commit_guardian/_ge_127g_5_fixture.py
GOAL: Shared fixture for the GE-127g-2 / GE-127g-5 tests. Builds on the
    GE-127g-1 fixture (real throwaway git repo, real ``git add``, the REAL
    check_doc_length.py run as a subprocess) and adds: a private guardian copy
    whose set-aside declaration the test writes (with a ground and, optionally,
    a ``report_above_lines`` ceiling per entry), and readers that pull the
    reported figures out of a gate run's own output.

    No figure from either AC is pinned. Every size and ceiling is derived from
    the shipped ``doc_length.max_lines`` read at test time, and every expected
    value is computed by the test from the tree it constructed.

OUTPUT-SHAPE CONTRACT the readers assume (the ACs fix words, not layout):
    * the two populations are stated as a number next to the words "judged"
      and "set aside" (either order: "3 documents were judged", "judged: 3");
    * the over-ceiling statement is a blank-line-separated paragraph that
      contains the word "ceiling";
    * headroom is stated as the word "headroom" followed by a SIGNED integer,
      ``ceiling - measured size`` (negative when the document is above it).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import _ge_127g_1_fixture as base

GUARDIAN_DIR = base.GUARDIAN_DIR
CONFIG_NAME = base.CONFIG_NAME
CLEAN_EXIT = base.CLEAN_EXIT
run_gate = base.run_gate
output_of = base.output_of
shipped_limit = base.shipped_limit

CEILING_KEY = "report_above_lines"
SOURCE_A = "fixture-src/alpha-templates/"
SOURCE_B = "fixture-src/beta-roadmap.json"
GROUND_A = f"FIXTUREGROUNDALPHA regenerated whole from {SOURCE_A} by the alpha generator, nobody authors it."
GROUND_B = f"FIXTUREGROUNDBETA regenerated whole from {SOURCE_B} by the beta generator, nobody authors it."
LOC_A = "docs/gen-alpha/"
LOC_B = "docs/gen-beta/"


def measured(body_lines: int) -> int:
    """Measured length of a ``base.doc_text(body_lines, ...)`` document (verified: body_lines + 1)."""
    return body_lines + 1


def entry(path: str, ground: str, ceiling: int | None = None) -> dict:
    out: dict = {"path": path, "ground": ground}
    if ceiling is not None:
        out[CEILING_KEY] = ceiling
    return out


def make_guardian(dest: Path, entries: list[dict]) -> Path:
    """A private copy of the source guardian dir whose declaration is exactly *entries*."""
    guardian = base.copy_guardian(dest)
    config_path = guardian / CONFIG_NAME
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["doc_length"]["set_aside_locations"] = entries
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return guardian


def build_repo(root: Path, committed: dict[str, int], staged: dict[str, int]) -> Path:
    """Commit *committed* (rel path -> body lines) as the parent, then stage *staged*."""
    base.init_repo(root)
    base.write_doc(root, "docs/seed.md", 5)  # so HEAD is never empty history
    for rel, lines in committed.items():
        base.write_doc(root, rel, lines)
    base.commit_baseline(root)
    for rel, lines in staged.items():
        base.write_doc(root, rel, lines)
    base.stage_all(root)
    return root


def count_of(output: str, word: str) -> int | None:
    """The integer the run states for *word* ("judged" / "set aside"), or None if it states none."""
    before = re.search(rf"(\d+)[^\n\d]{{0,40}}?\b{re.escape(word)}\b", output, re.IGNORECASE)
    if before:
        return int(before.group(1))
    after = re.search(rf"\b{re.escape(word)}\b\s*[:=]\s*(\d+)", output, re.IGNORECASE)
    return int(after.group(1)) if after else None


def paragraphs(output: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", output) if p.strip()]


def ceiling_paragraphs(output: str) -> list[str]:
    """Every blank-line-separated paragraph of the run that mentions a ceiling."""
    return [p for p in paragraphs(output) if "ceiling" in p.lower()]


def ceiling_statement_for(output: str, rel: str) -> str:
    """The joined ceiling paragraph(s) that name *rel*; empty string when none does."""
    return "\n".join(p for p in ceiling_paragraphs(output) if rel in p)


def stated_headroom(statement: str) -> int | None:
    found = re.search(r"headroom[^\d\-\n]{0,40}(-?\d+)", statement, re.IGNORECASE)
    return int(found.group(1)) if found else None
