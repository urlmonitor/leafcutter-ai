"""
MODULE: unit_tests/commit_guardian/test_ge_132a_1_registration.py
COVERS: GE-132a-1 -- registration side: declared and excused checks pass, a new
    check registered without a remedy declaration is refused, a declaration for
    a check that is not registered is refused, the shipped tables and trigger,
    and the SKILL.md / blocking_hook_ids "five gating hooks" wording.

GOAL, REACHABILITY ENTRY POINT, LOADER CONTRACT and MARKERS: see the shared
    harness _ge_132a_1_harness.py, which every GE-132a-1 test file imports.

DECISION HISTORY
- 2026-10-12 [GE-132a-1/test-writer]: Initial RED authoring (in test_ge_132a_1.py).
- 2026-10-12 [GE-132a-1/restructuring-specialist]: Split out of test_ge_132a_1.py
  (file-size limit). test_ge132a1_template_blocking_hook_ids_are_exactly_the_five
  moved here from test_precommit_safety_net.py; it still reads that file's
  _EXPECTED_BLOCKING_HOOKS so the five ids have one source.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    DECL,
    MANIFEST_RELS,
    SEED_REL,
    SEED_RELS,
    SKILL_PATH,
    _accepted,
    _clean_seed,
    _commit,
    _declared_ids,
    _dump,
    _gating_ids,
    _head,
    _hooks,
    _lines_naming,
    _real_manifest,
    _real_seed,
    _refused,
    _scratch,
    _stage,
    _stanza,
    _undeclared,
    _widget_hook,
    _with_parity,
    _write_tables,
)
from test_precommit_safety_net import _EXPECTED_BLOCKING_HOOKS, _load_template_config  # noqa: E402


# ---------------------------------------------------------------------------
# Arm 1 -- declared and excused checks do not refuse
# ---------------------------------------------------------------------------
@pytest.mark.shared_layout_reader
def test_ge132a1_declared_and_excused_checks_do_not_refuse(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: real_artifact
    """Arm 1. The REAL manifest and REAL routing table: check-complexity is
    declared, check-folder-density is excused (in the list, no declaration). A
    commit touching only the routing table runs the check, which passes and
    names neither.

    Wrong versions caught: a check that refuses everything; a build that left
    check-docstrings behind (arm 4 fires on the real tree) or renamed
    check-ac-limits to check-ac-tree-limits; a trigger not widened to the
    routing table (the check shows Skipped, never Passed).
    """
    manifest, seed = _real_manifest(), _real_seed()
    assert "check-complexity" in _declared_ids(seed), "real seed does not declare check-complexity"
    assert "check-folder-density" in _gating_ids(manifest) - _declared_ids(seed), "check-folder-density must be undeclared"
    baseline = _undeclared(manifest, seed)
    assert "check-complexity" not in baseline
    repo, stanza = _scratch(shared_reference_layout, tmp_path / "arm1", _with_parity(manifest, baseline), seed)
    before = _head(repo)
    touched = copy.deepcopy(seed)
    touched["_comment"] = touched["_comment"] + " (touched)"
    _dump(repo / SEED_REL, touched)
    _stage(repo, SEED_REL)
    output = _accepted(repo, before, _commit(repo, "touch the routing table"), stanza)
    assert not _lines_naming(output, "check-complexity"), output
    assert not _lines_naming(output, "check-folder-density"), output


@pytest.mark.shared_layout_reader
def test_ge132a1_real_table_has_no_stale_rules_and_renames_ac_limits() -> None:
    # covers: GE-132a-1
    # angle: real_artifact
    """The shipped table: no rule for a check that is not registered, no
    check-docstrings or check-ac-limits rule, the rename is check-ticket-ac-limits
    (NOT check-ac-tree-limits), the blocking list keeps only registered ids, and
    the excused list the build ships equals the re-measured undeclared set.
    """
    manifest, seed = _real_manifest(), _real_seed()
    rule_ids = [r["hook_id"] for r in seed["rules"]]
    registered = {h["id"] for h in _hooks(manifest)}
    assert not set(rule_ids) - registered, f"declarations for unregistered checks: {sorted(set(rule_ids) - registered)}"
    assert "check-docstrings" not in rule_ids and "check-ac-limits" not in rule_ids
    assert "check-ticket-ac-limits" in rule_ids and "check-ac-tree-limits" not in rule_ids
    assert "check-ticket-ac-limits" not in seed["blocking_hook_ids"], "check-ticket-ac-limits must NOT be added to blocking_hook_ids"
    ticket_rule = next(r for r in seed["rules"] if r["hook_id"] == "check-ticket-ac-limits")
    assert "AC count" in ticket_rule["description"], "renamed rule must keep the ticket AC-count text"
    shipped = manifest["hook_parity"].get("undeclared_remedy_baseline")
    assert isinstance(shipped, list), "hook_parity.undeclared_remedy_baseline is not seeded"
    assert len(shipped) == len(set(shipped)), "excused list holds duplicates"
    assert set(shipped) == _undeclared(manifest, seed), "excused list != re-measured undeclared gating checks"


@pytest.mark.shared_layout_reader
def test_ge132a1_trigger_reaches_the_remedy_declarations(shared_reference_layout: Path) -> None:
    # covers: GE-132a-1
    # angle: boundary
    """The generated stanza's files trigger matches the routing table AND every
    path it matched before; without it a declarations-only commit runs no check."""
    pattern = _stanza(shared_reference_layout)["files"]
    assert re.search(pattern, SEED_REL), f"trigger {pattern!r} misses {SEED_REL}"
    for old in ("scripts/commit_guardian/x.py", "templates/scripts/commit_guardian/x.py", "templates/commit-guardian/x.py"):
        assert re.search(pattern, old), f"trigger {pattern!r} lost {old}"
    assert not re.search(pattern, "docs/readme.md")


# ---------------------------------------------------------------------------
# Arm 2 -- new check without a declaration
# ---------------------------------------------------------------------------
@pytest.mark.shared_layout_reader
def test_ge132a1_new_check_without_declaration_is_refused(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: failure
    """Arm 2. The manifest gains check-widget-names (judgment, pre-commit), no
    rule: refused, HEAD stays, output names it and says a remedy declaration is
    needed. Control: the same registration WITH a declaration commits.

    Wrong version caught: THE SILENT DEFAULT -- a check with no declaration
    treated as 'author clears it'.
    """
    manifest = _real_manifest()
    seed = _clean_seed(manifest)
    base = _with_parity(manifest, _undeclared(manifest, seed))

    ctl_manifest = copy.deepcopy(base)
    _hooks(ctl_manifest).append(_widget_hook("check-widget-names"))
    ctl_seed = copy.deepcopy(seed)
    ctl_seed["rules"].append({"hook_id": "check-widget-names", "category": "structural", **DECL})
    ctl, ctl_stanza = _scratch(shared_reference_layout, tmp_path / "control", base, seed)
    before = _head(ctl)
    _write_tables(ctl, ctl_manifest, ctl_seed)
    _stage(ctl, *MANIFEST_RELS, *SEED_RELS)
    _accepted(ctl, before, _commit(ctl), ctl_stanza)

    new_manifest = copy.deepcopy(base)
    _hooks(new_manifest).append(_widget_hook("check-widget-names"))
    repo, _ = _scratch(shared_reference_layout, tmp_path / "arm2", base, seed)
    before = _head(repo)
    _write_tables(repo, new_manifest, seed)
    _stage(repo, *MANIFEST_RELS)
    output = _refused(repo, before, _commit(repo))
    named = _lines_naming(output, "check-widget-names").lower()
    assert named, f"check-widget-names not named: {output!r}"
    assert "remedy declaration" in output.lower(), f"reason not stated: {output!r}"
    assert "registered" in output.lower(), f"'before it can be registered' not stated: {output!r}"


# ---------------------------------------------------------------------------
# Arm 4 -- declaration for an unregistered check; reachability
# ---------------------------------------------------------------------------
def _stale_case(layout: Path, root: Path, stage_manifest: bool) -> tuple[Path, str, subprocess.CompletedProcess]:
    manifest = _real_manifest()
    seed = _clean_seed(manifest)
    base = _with_parity(manifest, _undeclared(manifest, seed))
    repo, _ = _scratch(layout, root, base, seed)
    before = _head(repo)
    stale = copy.deepcopy(seed)
    stale["rules"].append({"hook_id": "check-docstrings", "category": "structural", **DECL})
    touched = copy.deepcopy(base)
    touched["_comment"] = touched["_comment"] + " (touched)"
    _write_tables(repo, touched if stage_manifest else base, stale)
    _stage(repo, *SEED_RELS, *(MANIFEST_RELS if stage_manifest else ()))
    return repo, before, _commit(repo)


@pytest.mark.shared_layout_reader
def test_ge132a1_declaration_for_unregistered_check_is_refused(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: failure
    """Arm 4. The routing table holds a check-docstrings declaration; no
    registered check has that id: refused, naming it as a declaration for a
    check that is not registered and the file it came from.

    Wrong version caught: THE LEFTOVER -- accepting a declaration for an
    unregistered check.
    """
    repo, before, commit = _stale_case(shared_reference_layout, tmp_path / "arm4", stage_manifest=True)
    output = _refused(repo, before, commit)
    named = _lines_naming(output, "check-docstrings").lower()
    assert named, f"check-docstrings not named: {output!r}"
    assert "not registered" in output.lower(), f"reason not stated: {output!r}"
    assert "precommit-autofix.json" in output, f"offending file not stated: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge_132a_1_reachable_from_entry_point(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: reachability
    """Entry point: the registered pre-commit hook. A commit staging ONLY the
    routing table (a declarations-only change) must reach the check, which
    refuses the stale declaration through the real commit path."""
    repo, before, commit = _stale_case(shared_reference_layout, tmp_path / "reach", stage_manifest=False)
    output = _refused(repo, before, commit)
    assert "check-docstrings" in output and "not registered" in output.lower(), output
    assert "Skipped" not in output, f"hook was skipped, never reached: {output!r}"


# ---------------------------------------------------------------------------
# The five gating hooks: SKILL.md Step 4 prose and the shipped blocking list
# ---------------------------------------------------------------------------
def test_ge132a1_skill_step4_names_the_five_gating_hooks() -> None:
    # covers: GE-132a-1
    # angle: criterion
    """SKILL.md Step 4 no longer says 'seven' nor lists the two removed ids."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if "gating hooks" in line and "blocking_hook_ids" in line]
    assert lines, "Step 4 gating-hooks sentence not found"
    line = lines[0]
    assert "seven" not in line.lower(), line
    assert "five" in line.lower(), line
    for gone in ("check-docstrings", "check-ac-limits"):
        assert gone not in line, f"{gone} still listed: {line}"


class TestGe132a1BlockingHookIds(unittest.TestCase):
    """Moved from test_precommit_safety_net.TestBlockingHookIdsConfig (GE-132a-1).

    GE-132a-1 (2026-10-09, BrainCandy-approved BO-210a-2 amendment): the list is
    FIVE ids. check-docstrings has no hooks_manifest member (no such gate exists)
    and check-ac-limits was never the gate the hook is named for, so both left.
    check-ticket-ac-limits is deliberately NOT added.
    """

    def test_ge132a1_template_blocking_hook_ids_are_exactly_the_five(self):
        # covers: GE-132a-1
        # angle: discrimination
        """GE-132a-1: the shipped seed lists exactly the five gating ids.

        The subset check in test_precommit_safety_net stays green when stale ids linger, so this pins
        equality on the template (the content build.py deploys). Catches the
        wrong version that removes the stale rules but leaves check-docstrings
        and check-ac-limits in blocking_hook_ids, and the one that adds
        check-ticket-ac-limits.
        """
        actual = set(_load_template_config().get("blocking_hook_ids", []))
        self.assertEqual(
            actual, _EXPECTED_BLOCKING_HOOKS,
            f"blocking_hook_ids must be exactly the five ids; extra={actual - _EXPECTED_BLOCKING_HOOKS} "
            f"missing={_EXPECTED_BLOCKING_HOOKS - actual}."
        )
