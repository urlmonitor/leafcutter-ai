"""
MODULE: unit_tests/commit_guardian/test_ge_127g_1.py
COVERS: GE-127g-1 -- which documents the size standard sets aside is a DECLARED
    CLASS OF LOCATIONS (doc_length.set_aside_locations), so a newly generated
    document joins it with no edit to any list.

GOAL: RED test-first stubs, one per declared test_spec descriptor. Each drives
    the REAL check_doc_length.py as a subprocess against a real throwaway git
    repo with a real ``git add`` -- never a grep of the config. No figure from
    the AC criteria (65 / 2,809 / 276 ...) is pinned: lengths are derived from
    the shipped ``max_lines`` and every assertion is against the set THIS
    FIXTURE constructed.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.1): CLI script --
    ``python check_doc_length.py`` run with cwd at the staged repo (source copy
    for three descriptors, the DEPLOYED copy for the fourth).

Named mutations the descriptors catch: (1) the 65-filename list -> arm 2 red;
    (2) exclude everything under docs/ -> arm 3 red; (3) hardcode the directory
    in the gate ignoring the declaration -> arm 3 red only.

DECISION HISTORY
- 2026-10-12 [GE-127g-1/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_1_fixture as fx  # noqa: E402

LIMIT = fx.shipped_limit()

# name -> (committed body lines, regenerated body lines). Derived from the
# shipped limit; the three "over" cards start above it, "crossing" starts
# under it and ends above, the rest stay under.
OVER_CARDS = {
    "agent-a.card.md": (LIMIT + 500, LIMIT + 580),
    "agent-b.card.md": (LIMIT + 200, LIMIT + 250),
    "agent-c.card.md": (LIMIT + 120, LIMIT + 130),
}
CROSSING_CARDS = {"agent-d.card.md": (LIMIT - 24, LIMIT + 40)}
UNDER_CARDS = {
    "agent-e.card.md": (LIMIT - 60, LIMIT - 55),
    "agent-f.card.md": (LIMIT - 90, LIMIT - 90),
    "agent-g.card.md": (20, 25),
}
ALL_CARDS = {**OVER_CARDS, **CROSSING_CARDS, **UNDER_CARDS}
# What the standard WOULD refuse if no declaration set the directory aside.
EXPECTED_REFUSED = {f"{fx.CARDS_DIR}{name}" for name in {**OVER_CARDS, **CROSSING_CARDS}}


def _cards_repo(root: Path, extra_after: dict[str, int] | None = None) -> Path:
    """Repo with the cards directory committed at HEAD, then restaged as a regeneration leaves it."""
    fx.init_repo(root)
    fx.write_doc(root, "docs/guide.md", 10)  # a hand-authored checked doc, so HEAD is not empty-history
    for name, (before, _after) in ALL_CARDS.items():
        fx.write_doc(root, f"{fx.CARDS_DIR}{name}", before)
    fx.commit_baseline(root)
    for name, (_before, after) in ALL_CARDS.items():
        fx.write_doc(root, f"{fx.CARDS_DIR}{name}", after)
    for name, lines in (extra_after or {}).items():
        fx.write_doc(root, f"{fx.CARDS_DIR}{name}", lines)
    fx.stage_all(root)
    return root


def test_regenerated_cards_directory_commits_cleanly(tmp_path: Path) -> None:
    # covers: GE-127g-1
    # angle: criterion
    """Arm 1. The whole cards directory, restaged as a regeneration leaves it
    (documents already over the limit grew, one document crossed it), passes
    the gate with exit 0.

    Must implement: ``doc_length.set_aside_locations`` declaring docs/agents/cards/
    and a membership test that treats the directory by LOCATION. Wrong version
    caught: leaving the basename-matched ``excluded_files`` as the only mechanism
    (cards named *.card.md are not README.md, so they are still judged).
    """
    repo = _cards_repo(tmp_path / "arm1")
    result = fx.run_gate(repo, fx.GUARDIAN_DIR)
    assert result.returncode == fx.CLEAN_EXIT, (
        f"regenerated cards directory was refused (exit {result.returncode}): {fx.output_of(result)!r}"
    )


def test_newly_generated_document_needs_no_declaration_edit(tmp_path: Path) -> None:
    # covers: GE-127g-1
    # angle: discrimination
    """Arm 2, the whole record. A new generated document (longer than the
    limit, named in no declared entry) is staged with the rest of the
    directory: the gate completes AND the declaration file is byte-identical
    before and after, AND the declaration names the directory (a location),
    not the individual documents.

    Wrong versions caught: expressing the exclusion as the current filenames
    (the new name matches nothing -> refused); appending the newly seen
    document to the declaration at run time (bytes differ).
    """
    guardian = fx.copy_guardian(tmp_path / "guardian")
    declared = fx.set_aside_paths(guardian)
    assert fx.CARDS_DIR in declared, f"cards directory is not a declared location: {declared!r}"
    assert not any(".card.md" in p for p in declared), (
        f"the declaration lists individual card documents instead of a location: {declared!r}"
    )

    new_name = "agent-brand-new.card.md"
    assert not any(new_name in p for p in declared)
    repo = _cards_repo(tmp_path / "arm2", extra_after={new_name: LIMIT + 120})
    config = guardian / fx.CONFIG_NAME
    before = config.read_bytes()

    result = fx.run_gate(repo, guardian)

    assert result.returncode == fx.CLEAN_EXIT, (
        f"a new generated document was refused (exit {result.returncode}): {fx.output_of(result)!r}"
    )
    assert config.read_bytes() == before, "the declaration was edited during the run"


def test_emptied_declaration_names_the_three_over_limit_documents(tmp_path: Path) -> None:
    # covers: GE-127g-1
    # angle: discrimination
    """Arm 3, the negative control. With the declaration's cards entry
    removed, the same regenerated directory is refused and the documents the
    gate names are EXACTLY the ones this fixture constructed as refusable
    (never a pinned count). The intact declaration over the same index
    completes, so the arms differ only by the declaration.

    Wrong versions caught: excluding every document under docs/ (the emptied
    run would complete); hardcoding the directory in the gate and ignoring the
    declaration (the emptied run would complete).
    """
    intact = fx.copy_guardian(tmp_path / "guardian_intact")
    emptied = fx.copy_guardian(tmp_path / "guardian_emptied")
    assert fx.CARDS_DIR in fx.set_aside_paths(emptied), "precondition: the shipped declaration names the cards directory"

    config_path = emptied / fx.CONFIG_NAME
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["doc_length"]["set_aside_locations"] = [
        e for e in config["doc_length"]["set_aside_locations"] if e["path"] != fx.CARDS_DIR
    ]
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    repo = _cards_repo(tmp_path / "arm3")

    control = fx.run_gate(repo, intact)
    assert control.returncode == fx.CLEAN_EXIT, f"control (declaration intact) was refused: {fx.output_of(control)!r}"

    refused = fx.run_gate(repo, emptied)
    assert refused.returncode == fx.REFUSED_EXIT, (
        f"gate completed (exit {refused.returncode}) with the declaration emptied: {fx.output_of(refused)!r}"
    )
    named = {p for p in fx.named_docs(fx.output_of(refused)) if p.startswith(fx.CARDS_DIR)}
    assert named == EXPECTED_REFUSED, f"named {sorted(named)!r}, fixture constructed {sorted(EXPECTED_REFUSED)!r}"


@pytest.mark.shared_layout_reader
def test_deployed_doc_length_gate_honours_the_declared_locations(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-127g-1
    # angle: deployed
    """The DEPLOYED check_doc_length.py, run cold from the shared build layout
    against a staged over-limit generated document, reaches a clean verdict --
    not a ModuleNotFoundError and not a refusal -- and the DEPLOYED declaration
    carries the set-aside locations (so the deployed copy of the declaration is
    the one in effect). Only READS the layout; no private build.py.

    Wrong version caught: a membership helper module the build does not deploy
    (deployed hook crashes while source-tree tests stay green).
    """
    deployed = None
    for candidate in (
        shared_reference_layout / "scripts" / "commit_guardian",
        shared_reference_layout / ".leafcutter" / "scripts" / "commit_guardian",
    ):
        if (candidate / "check_doc_length.py").exists():
            deployed = candidate
            break
    assert deployed is not None, f"check_doc_length.py not deployed under {shared_reference_layout}"
    assert fx.CARDS_DIR in fx.set_aside_paths(deployed), "deployed declaration does not name the cards directory"

    repo = _cards_repo(tmp_path / "deployed")
    result = fx.run_gate(repo, deployed)
    combined = fx.output_of(result)
    assert "ModuleNotFoundError" not in combined, f"deployed gate crashed importing a dependency: {combined!r}"
    assert result.returncode == fx.CLEAN_EXIT, (
        f"deployed gate refused a set-aside directory (exit {result.returncode}): {combined!r}"
    )
