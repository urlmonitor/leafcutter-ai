"""
MODULE: unit_tests/commit_guardian/test_ge_132a_1_excused_list.py
COVERS: GE-132a-1 -- the excused list (hook_parity.undeclared_remedy_baseline)
    only shrinks: it cannot gain an entry, the ratchet compares every merge
    parent, it cannot be deleted then re-added, and the seeding commit passes.

GOAL, REACHABILITY ENTRY POINT, LOADER CONTRACT and MARKERS: see the shared
    harness _ge_132a_1_harness.py, which every GE-132a-1 test file imports.

DECISION HISTORY
- 2026-10-12 [GE-132a-1/test-writer]: Initial RED authoring (in test_ge_132a_1.py).
- 2026-10-12 [GE-132a-1/restructuring-specialist]: Split out of test_ge_132a_1.py
  (file-size limit); tests moved verbatim.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    DECL,
    MANIFEST_RELS,
    SEED_RELS,
    _accepted,
    _all_declared_seed,
    _clean_seed,
    _commit,
    _dump,
    _git,
    _head,
    _hooks,
    _lines_naming,
    _real_manifest,
    _refused,
    _scratch,
    _stage,
    _undeclared,
    _widget_hook,
    _with_parity,
    _write_tables,
)


# ---------------------------------------------------------------------------
# Arm 3 -- the excused list only shrinks
# ---------------------------------------------------------------------------
@pytest.mark.shared_layout_reader
def test_ge132a1_excused_list_cannot_gain_an_entry(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: discrimination
    """Arm 3. Arm 2's change also adds check-widget-names to the excused list:
    still refused, and the refusal names the excused list. Control: removing an
    entry (while declaring it) commits, so the refusal is caused by the addition.

    Wrong version caught: THE OPEN DOOR -- accepting additions to the excused list.
    """
    manifest = _real_manifest()
    seed = _clean_seed(manifest)
    undeclared = _undeclared(manifest, seed)
    base = _with_parity(manifest, undeclared)

    shrunk_seed = copy.deepcopy(seed)
    shrunk_seed["rules"].append({"hook_id": "check-folder-density", "category": "structural", **DECL})
    ctl_manifest = _with_parity(manifest, undeclared - {"check-folder-density"})
    ctl, ctl_stanza = _scratch(shared_reference_layout, tmp_path / "control", base, seed)
    before = _head(ctl)
    _write_tables(ctl, ctl_manifest, shrunk_seed)
    _stage(ctl, *MANIFEST_RELS, *SEED_RELS)
    _accepted(ctl, before, _commit(ctl), ctl_stanza)

    added = _with_parity(manifest, undeclared | {"check-widget-names"})
    _hooks(added).append(_widget_hook("check-widget-names"))
    repo, _ = _scratch(shared_reference_layout, tmp_path / "arm3", base, seed)
    before = _head(repo)
    _write_tables(repo, added, seed)
    _stage(repo, *MANIFEST_RELS)
    output = _refused(repo, before, _commit(repo))
    named = _lines_naming(output, "check-widget-names").lower()
    assert named, f"check-widget-names not named: {output!r}"
    assert "excused" in output.lower(), f"refusal never mentions the excused list: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge132a1_excused_ratchet_compares_every_merge_parent(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: discrimination
    """Constraint: the ratchet compares against HEAD and each MERGE_HEAD. An id
    in MERGE_HEAD's list but not HEAD's is not an addition (merge commits);
    an id in neither parent's list still refuses.

    Wrong version caught: a ratchet that reads HEAD only (refuses the first merge).
    """
    manifest = _real_manifest()
    seed = _clean_seed(manifest)
    undeclared = _undeclared(manifest, seed)
    base = _with_parity(manifest, undeclared)
    theirs = _with_parity(manifest, undeclared | {"check-widget-names"})
    _hooks(theirs).append(_widget_hook("check-widget-names"))
    theirs["_comment"] = "other side comment"
    ours = copy.deepcopy(base)
    ours["_comment"] = "main side comment"

    def merge_state(name: str) -> tuple[Path, dict, str]:
        """Both sides edit the manifest's _comment line, so the merge CONFLICTS on
        the manifest: pre-commit hands a merge commit only its conflicted files,
        so the trigger-gated hook runs only when the manifest is among them."""
        repo, stanza = _scratch(shared_reference_layout, tmp_path / name, base, seed)
        _git(["checkout", "-q", "-b", "other"], repo)
        _write_tables(repo, theirs, seed)
        _stage(repo, *MANIFEST_RELS)
        _git(["commit", "-q", "--no-verify", "-m", "other adds the excused id"], repo)
        _git(["checkout", "-q", "main"], repo)
        _write_tables(repo, ours, seed)
        _stage(repo, *MANIFEST_RELS)
        _git(["commit", "-q", "--no-verify", "-m", "main moves"], repo)
        before = _head(repo)
        merged = _git(["merge", "-q", "--no-commit", "--no-ff", "other"], repo, check=False)
        assert merged.returncode != 0, "fixture merge was expected to conflict on the manifest"
        return repo, stanza, before

    repo, stanza, before = merge_state("merge_ok")
    resolved = copy.deepcopy(theirs)
    resolved["_comment"] = "resolved comment"
    _write_tables(repo, resolved, seed)
    _stage(repo, *MANIFEST_RELS)
    _accepted(repo, before, _commit(repo, "merge other"), stanza)

    repo, stanza, before = merge_state("merge_bad")
    gained = _with_parity(manifest, undeclared | {"check-widget-names", "check-gadget-names"})
    _hooks(gained).extend([_widget_hook("check-widget-names"), _widget_hook("check-gadget-names")])
    gained["_comment"] = "resolved comment"
    _write_tables(repo, gained, seed)
    _stage(repo, *MANIFEST_RELS)
    output = _refused(repo, before, _commit(repo, "merge other"))
    assert _lines_naming(output, "check-gadget-names"), f"id in no parent's list not named: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge132a1_excused_list_cannot_be_deleted_then_readded(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: discrimination
    """Loophole. Every gating check is declared, so the HEAD list is empty. A commit
    that DELETES hook_parity.undeclared_remedy_baseline is refused, naming the list
    as removed (otherwise the next commit re-adds it with entries nobody judged).
    Control: the same commit keeping the empty list is accepted.

    Wrong version caught: a ratchet skipped whenever the staged manifest has no list.
    """
    manifest = _real_manifest()
    seed, _ = _all_declared_seed(manifest)
    base = _with_parity(manifest, set())
    assert base["hook_parity"]["undeclared_remedy_baseline"] == []

    kept = copy.deepcopy(base)
    kept["_comment"] = "touched, list kept"
    ctl, ctl_stanza = _scratch(shared_reference_layout, tmp_path / "control", base, seed)
    before = _head(ctl)
    _write_tables(ctl, kept, seed)
    _stage(ctl, *MANIFEST_RELS)
    _accepted(ctl, before, _commit(ctl), ctl_stanza)

    deleted = copy.deepcopy(base)
    del deleted["hook_parity"]["undeclared_remedy_baseline"]
    repo, _ = _scratch(shared_reference_layout, tmp_path / "deleted", base, seed)
    before = _head(repo)
    _dump(repo / MANIFEST_RELS[0], deleted)
    _stage(repo, MANIFEST_RELS[0])
    output = _refused(repo, before, _commit(repo))
    lowered = output.lower()
    # presence-only: asserts on the refusal text of a real git commit that _refused() already proved was refused, not on source text
    assert "undeclared_remedy_baseline" in output and "removed" in lowered, f"deletion not named: {output!r}"
    assert "excused" in lowered, f"refusal never mentions the excused list: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge132a1_seeding_commit_without_any_parent_list_still_passes(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: boundary
    """Seeding. No parent has ever carried the list, so the commit that first adds
    it (with entries) is not an addition and is accepted.

    Wrong version caught: a deletion rule over-applied so the seeding commit refuses.
    """
    manifest = _real_manifest()
    seed, declared = _all_declared_seed(manifest)
    unseeded = _with_parity(manifest, set())
    del unseeded["hook_parity"]["undeclared_remedy_baseline"]
    repo, stanza = _scratch(shared_reference_layout, tmp_path / "seeding", unseeded, seed)
    before = _head(repo)
    seeded = _with_parity(manifest, declared)
    _write_tables(repo, seeded, seed)
    _stage(repo, *MANIFEST_RELS)
    _accepted(repo, before, _commit(repo, "seed the excused list"), stanza)
