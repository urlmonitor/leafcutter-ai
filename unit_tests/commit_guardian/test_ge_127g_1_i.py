"""
MODULE: unit_tests/commit_guardian/test_ge_127g_1_i.py
COVERS: GE-127g-1-i -- a set-aside document is set aside on BOTH arms of the
    standard: it may grow once already over its limit (growth ratchet,
    GE-127b) AND may cross the limit for the first time (crossing refusal,
    GE-127a); nothing outside the declared locations is set aside on either arm.

GOAL: RED test-first stubs, one per declared test_spec descriptor. Real git
    repos, real ``git add``, the REAL check_doc_length.py run as a subprocess
    (reachability entry point: CLI script, BP-1100g-2 Step 1.1). No figure
    from the criteria (2,525 / 2,809 / 268 / 340 / 355) is pinned: lengths are
    derived from the shipped ``max_lines`` at test time.

Note on arm mapping (from the AC's test_rationale): classify_dimension routes
    an already-over document to the GROWTH branch and an under-limit document
    to the CROSSING branch, so the first test goes red under a crossing-only
    exemption and the second under a growth-only exemption.

DECISION HISTORY
- 2026-10-12 [GE-127g-1-i/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_1_fixture as fx  # noqa: E402

LIMIT = fx.shipped_limit()

GROWING_CARD = f"{fx.CARDS_DIR}agent-grow.card.md"      # already far over, regenerated longer
CROSSING_CARD = f"{fx.CARDS_DIR}agent-cross.card.md"    # under, regenerated over
HAND_DOC = "docs/guides/hand-authored.md"               # outside every declared location

GROW_FROM, GROW_TO = LIMIT + 700, LIMIT + 800
CROSS_FROM, CROSS_TO = LIMIT - 30, LIMIT + 40
HAND_FROM, HAND_TO = LIMIT + 40, LIMIT + 55


def _repo(root: Path, *, grow: bool = False, cross: bool = False, hand: bool = False) -> Path:
    """Baseline holds all three documents; the staged change touches the selected ones."""
    fx.init_repo(root)
    fx.write_doc(root, "docs/guide.md", 10)
    fx.write_doc(root, GROWING_CARD, GROW_FROM)
    fx.write_doc(root, CROSSING_CARD, CROSS_FROM)
    fx.write_doc(root, HAND_DOC, HAND_FROM)
    fx.commit_baseline(root)
    if grow:
        fx.write_doc(root, GROWING_CARD, GROW_TO)
    if cross:
        fx.write_doc(root, CROSSING_CARD, CROSS_TO)
    if hand:
        fx.write_doc(root, HAND_DOC, HAND_TO)
    fx.stage_all(root)
    return root


def test_set_aside_document_already_over_the_limit_may_grow(tmp_path: Path) -> None:
    # covers: GE-127g-1-i
    # angle: criterion
    """Arm 1 (growth comparison only applies: the document already crossed).
    A set-aside document committed far over the limit and staged LONGER
    completes with exit 0.

    Wrong versions caught: consulting the set-aside membership only before the
    crossing comparison; placing it inside classify_dimension's else branch only.
    """
    assert fx.CARDS_DIR in fx.set_aside_paths(fx.GUARDIAN_DIR), "precondition: cards directory is a declared location"
    repo = _repo(tmp_path / "grow", grow=True)
    result = fx.run_gate(repo, fx.GUARDIAN_DIR)
    assert result.returncode == fx.CLEAN_EXIT, (
        f"a set-aside document already over its limit was refused for growing "
        f"({GROW_FROM + 1} -> {GROW_TO + 1} lines, exit {result.returncode}): {fx.output_of(result)!r}"
    )


def test_set_aside_document_may_cross_the_limit_for_the_first_time(tmp_path: Path) -> None:
    # covers: GE-127g-1-i
    # angle: criterion
    """Arm 2 (crossing comparison only applies: the document was under).
    A set-aside document committed under the limit and staged OVER it
    completes with exit 0.

    Wrong versions caught: consulting the membership only before the growth
    comparison; placing it inside the previous-over-limit branch only.
    """
    assert fx.CARDS_DIR in fx.set_aside_paths(fx.GUARDIAN_DIR), "precondition: cards directory is a declared location"
    repo = _repo(tmp_path / "cross", cross=True)
    result = fx.run_gate(repo, fx.GUARDIAN_DIR)
    assert result.returncode == fx.CLEAN_EXIT, (
        f"a set-aside document was refused for crossing the limit "
        f"({CROSS_FROM + 1} -> {CROSS_TO + 1} lines, exit {result.returncode}): {fx.output_of(result)!r}"
    )


def test_hand_authored_document_outside_every_declared_location_is_still_refused(tmp_path: Path) -> None:
    # covers: GE-127g-1-i
    # angle: discrimination
    """Arm 3, the negative control, staged in the SAME commit as both generated
    documents. The gate refuses, and the only document it names is the
    hand-authored one -- neither generated document is named.

    Wrong versions caught: setting both comparisons aside for every document
    under docs/ (no refusal); refusing without naming which document caused it.
    """
    assert fx.CARDS_DIR in fx.set_aside_paths(fx.GUARDIAN_DIR), "precondition: cards directory is a declared location"
    repo = _repo(tmp_path / "hand", grow=True, cross=True, hand=True)
    result = fx.run_gate(repo, fx.GUARDIAN_DIR)
    output = fx.output_of(result)
    assert result.returncode == fx.REFUSED_EXIT, f"hand-authored growth was not refused (exit {result.returncode}): {output!r}"
    named = fx.named_docs(output)
    assert HAND_DOC in named, f"the refusal does not name the hand-authored document: {output!r}"
    assert GROWING_CARD not in named and CROSSING_CARD not in named, (
        f"a set-aside generated document was named in the refusal: {sorted(named)!r}"
    )
    assert named == {HAND_DOC}, f"refusal names more than the hand-authored document: {sorted(named)!r}"


def test_set_aside_document_absent_from_both_the_staged_and_head_covered_populations(tmp_path: Path) -> None:
    # covers: GE-127g-1-i
    # angle: seam
    """The two is_checked consultation sites (staged filter and HEAD-covered
    predicate) must agree. HEAD holds ONLY set-aside documents (plus a
    non-doc file); a short hand-authored doc is newly staged alongside a
    set-aside document staged SHORTER than committed. If the HEAD-covered set
    excludes the set-aside documents, HEAD holds no covered doc and the run
    reports EMPTY HISTORY; a gate that excludes the document from the staged
    filter only still sees the card at HEAD and reports no EMPTY HISTORY.
    Neither INDETERMINATE nor any finding may appear.
    """
    assert fx.CARDS_DIR in fx.set_aside_paths(fx.GUARDIAN_DIR), "precondition: cards directory is a declared location"
    root = tmp_path / "seam"
    fx.init_repo(root)
    (root / "README.txt").write_text("not a doc under test\n", encoding="utf-8")
    fx.write_doc(root, GROWING_CARD, GROW_FROM)
    fx.commit_baseline(root)
    fx.write_doc(root, GROWING_CARD, GROW_FROM - 50)  # shorter than committed, still over
    fx.write_doc(root, "docs/guides/new-short.md", 12)  # a covered doc, so the staged population is non-empty
    fx.stage_all(root)

    result = fx.run_gate(root, fx.GUARDIAN_DIR)
    output = fx.output_of(result)
    assert "INDETERMINATE" not in output, f"previous-value resolution failed: {output!r}"
    assert result.returncode == fx.CLEAN_EXIT, f"unexpected refusal (exit {result.returncode}): {output!r}"
    assert "EMPTY HISTORY" in output, (
        "HEAD holds only set-aside documents, so the HEAD-covered set must be empty; "
        f"the two consultation sites disagree: {output!r}"
    )
