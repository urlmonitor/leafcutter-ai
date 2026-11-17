"""
MODULE: unit_tests/commit_guardian/test_ge_127g_2_i.py
COVERS: GE-127g-2-i -- a set-aside declaration that cannot be read (absent) or
    interpreted (malformed, or an entry with a blank ground) is SAID SO, and every
    staged document is JUDGED; an empty-but-readable declaration is reported
    differently from an unreadable one.

GOAL: RED test-first stubs, one per declared test_spec descriptor. Each drives the
    REAL check_doc_length.py as a subprocess against a real throwaway git repo
    with a real ``git add``. The absent case is built by really DELETING the
    declaring file from a private guardian copy (a patched loader would be
    entered and could not reproduce the existence-test miss). The malformed case
    is written by the fixture; the entry-granularity case uses the fixture's own
    entry() builder.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.1): CLI script --
    ``python check_doc_length.py`` run with cwd at the staged repo.

Wrong versions the descriptors catch: silent fallback to a built-in set-aside list;
    quiet set-aside of every document on an unreadable declaration; an existence
    test guarding the read; an empty declaration reported as unreadable; an entry
    with a blank ground honoured because only the file's JSON shape was checked.

DECISION HISTORY
- 2026-10-14 [GE-127g-2-i/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_5_fixture as fx  # noqa: E402

BIG_BODY = 2808  # measured 2,809 lines, the AC's generated document
SMALL = 20  # well inside any authored limit
GENERATED = f"{fx.base.CARDS_DIR}generated-card.md"
CONTROL = "docs/hand-small.md"
NAMES_DECLARATION = re.compile(r"commit_guardian\.json|set_aside_locations")
COULD_NOT_READ = re.compile(r"could not be read|cannot be read|unreadable", re.IGNORECASE)
COULD_NOT_INTERPRET = re.compile(r"could not be interpreted|cannot be interpreted|uninterpretable", re.IGNORECASE)


def _stage(tmp_path: Path):
    return fx.build_repo(tmp_path / "repo", committed={}, staged={GENERATED: BIG_BODY, CONTROL: SMALL})


def _guardian_with(tmp_path: Path, mutate) -> Path:
    guardian = fx.base.copy_guardian(tmp_path / "guardian")
    mutate(guardian / fx.CONFIG_NAME)
    return guardian


def _edit_declaration(value):
    def apply(config_path: Path) -> None:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["doc_length"]["set_aside_locations"] = value
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return apply


def _lines_naming(output: str, rel: str) -> list[str]:
    return [line for line in output.splitlines() if rel in line]


def _assert_judged_not_set_aside_not_compliant(out: str) -> None:
    """The generated document is among the JUDGED, over its limit, and neither set aside nor compliant."""
    assert GENERATED in out, f"generated document not reported at all: {out!r}"
    assert fx.count_of(out, "judged") == 2, f"both staged documents must be reported judged: {out!r}"
    assert fx.count_of(out, "set aside") in (None, 0), f"a document was reported set aside: {out!r}"
    for line in _lines_naming(out, GENERATED):
        assert not re.search(r"set aside|within|PASSED|compliant", line, re.IGNORECASE), (
            f"generated document reported as set aside / compliant: {line!r}"
        )
    assert re.search(r"exceed|over|refus|BLOCK", out, re.IGNORECASE), f"document not reported over its limit: {out!r}"
    assert "PASSED" not in out, f"run reports a pass: {out!r}"


def test_absent_declaration_refuses_names_it_and_judges_the_document(tmp_path: Path) -> None:
    # covers: GE-127g-2-i
    # angle: failure
    """Arm 1. The declaring file is really removed. The commit is refused; the run
    says the declaration could not be read and names it; the 2,809-line generated
    document is reported among those judged and over its limit -- neither set aside
    nor within its permitted length. Four assertions kept separate.

    Must implement: attempt the read and handle its failure (no existence test),
    no built-in set-aside list, and judge every staged document.
    """
    guardian = _guardian_with(tmp_path, lambda config_path: config_path.unlink())
    assert not (guardian / fx.CONFIG_NAME).exists()
    result = fx.run_gate(_stage(tmp_path), guardian)
    out = fx.output_of(result)

    assert result.returncode != fx.CLEAN_EXIT, f"commit completed on an unreadable declaration: {out!r}"
    assert COULD_NOT_READ.search(out), f"run does not say the declaration could not be read: {out!r}"
    assert NAMES_DECLARATION.search(out), f"run does not name the declaration: {out!r}"
    _assert_judged_not_set_aside_not_compliant(out)


def test_malformed_declaration_refuses_names_it_and_judges_the_document(tmp_path: Path) -> None:
    # covers: GE-127g-2-i
    # angle: failure
    """Arm 2. The declaration is present but its entries cannot be interpreted
    (wrong shape). Refused; the run says the declaration could not be INTERPRETED
    and names it; the document is again reported among those judged.
    """
    guardian = _guardian_with(tmp_path, _edit_declaration(["not-an-entry", 7]))
    result = fx.run_gate(_stage(tmp_path), guardian)
    out = fx.output_of(result)

    assert result.returncode != fx.CLEAN_EXIT, f"commit completed on an uninterpretable declaration: {out!r}"
    assert COULD_NOT_INTERPRET.search(out), f"run does not say the declaration could not be interpreted: {out!r}"
    assert NAMES_DECLARATION.search(out), f"run does not name the declaration: {out!r}"
    _assert_judged_not_set_aside_not_compliant(out)


def test_empty_declaration_judges_without_claiming_an_unreadable_declaration(tmp_path: Path) -> None:
    # covers: GE-127g-2-i
    # angle: discrimination
    """Arm 3. Readable declaration with zero entries. Refused for the document's
    length; the document is reported among those judged; and the output does NOT
    say the declaration could not be read (or interpreted). The empty declaration
    is a decision that nothing is set aside, so the run states 0 set aside rather
    than a fault.

    Wrong version caught: reporting an empty declared set with the unreadable text.
    """
    guardian = _guardian_with(tmp_path, _edit_declaration([]))
    result = fx.run_gate(_stage(tmp_path), guardian)
    out = fx.output_of(result)

    assert result.returncode != fx.CLEAN_EXIT, f"commit completed over a 2,809-line document: {out!r}"
    assert not COULD_NOT_READ.search(out), f"empty declaration reported as unreadable: {out!r}"
    assert not COULD_NOT_INTERPRET.search(out), f"empty declaration reported as uninterpretable: {out!r}"
    assert fx.count_of(out, "set aside") == 0, f"empty declaration must state 0 set aside: {out!r}"
    _assert_judged_not_set_aside_not_compliant(out)


def test_declaration_entry_with_a_blank_ground_is_rejected_not_honoured(tmp_path: Path) -> None:
    # covers: GE-127g-2-i
    # angle: boundary
    """Entry granularity. The cards directory is declared with a whitespace-only
    ground (a second entry is well formed, as control). The over-limit generated
    document is JUDGED, not set aside, and the output names the offending entry.

    Wrong versions caught: honouring an entry with a blank ground; validating only
    that the file parses.
    """
    entries = [
        fx.entry(fx.base.CARDS_DIR, "   ", 100000),
        fx.entry(fx.LOC_B, fx.GROUND_B, 100000),
    ]
    guardian = _guardian_with(tmp_path, _edit_declaration(entries))
    result = fx.run_gate(_stage(tmp_path), guardian)
    out = fx.output_of(result)

    assert result.returncode != fx.CLEAN_EXIT, f"blank-ground entry was honoured, commit completed: {out!r}"
    assert any(
        fx.base.CARDS_DIR in line and "ground" in line.lower() and GENERATED not in line for line in out.splitlines()
    ), f"output does not name the offending entry and its missing ground: {out!r}"
    _assert_judged_not_set_aside_not_compliant(out)
