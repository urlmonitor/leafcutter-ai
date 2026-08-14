"""
MODULE: test_artifact_graph_trust_ratings
GOAL: Verify that every edge's `enforcement` rating in
docs/reference/artifact-knowledge-graph.graph.json is derived from the
active hooks registered in
templates/scripts/commit_guardian/commit_guardian.json — not from the mere
existence of a script file on disk, and not from prose.

Nature: TDD test stubs — MUST be RED until the coder corrects the two
inverted ratings the KM-ADM-001 bug describes:
  - `ac-tested` is currently rated "warn" although its named backing script
    (check_ac_coverage.py) is absent from commit_guardian.json's hook
    registry (i.e. unregistered, dead code that never runs).
  - `ticket-touches` is currently rated "none" although its actual backing
    hook (check-predone-scope / check_files_touched_reconciliation.py) IS
    registered and active (files_touched_reconciliation.enabled: true).

Both must be corrected so the rating tracks registry activity, not prose or
file-existence. Do NOT hardcode the two corrected literal enforcement
values as the sole check — see test_ac1_enforcement_matches_registry_activity_
for_every_named_hook below, which derives its expectation from the registry
itself so it keeps catching drift after this specific bug is fixed.

AC: KM-ADM-001
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GRAPH_PATH = (
    _REPO_ROOT / "docs" / "reference" / "artifact-knowledge-graph.graph.json"
)
_REGISTRY_PATH = (
    _REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "commit_guardian.json"
)

# Matches registered hook ids as they appear in a `note` field, e.g.
# "check-ac-parent-covered-by" or "check-predone-scope".
_HOOK_ID_RE = re.compile(r"\bcheck-[a-z0-9-]+\b")

# Matches a python script filename referenced in a `note` field, e.g.
# "check_ac_coverage.py" or "validate_product_truth.py".
_SCRIPT_RE = re.compile(r"\b[a-z0-9_]+\.py\b")

# The wrapper every hook entry is invoked through — never itself the
# hook's identity, so it must be excluded when extracting script basenames
# from an `entry` command string.
_WRAPPER_SCRIPT = "run_hook.py"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_graph() -> dict:
    return _load_json(_GRAPH_PATH)


def _load_registry() -> dict:
    return _load_json(_REGISTRY_PATH)


def _active_hook_identifiers(registry: dict) -> tuple[set[str], set[str]]:
    """Return (active_hook_ids, active_script_basenames).

    A hook counts as active only when it is present in the
    `hooks_manifest.hooks` array AND not explicitly disabled
    (`"enabled": false`). Absence of the `enabled` key defaults to active,
    matching commit_guardian's own runtime default.
    """
    hooks = registry["hooks_manifest"]["hooks"]
    active_ids: set[str] = set()
    active_scripts: set[str] = set()
    for hook in hooks:
        if hook.get("enabled", True) is False:
            continue
        active_ids.add(hook["id"])
        entry = hook.get("entry", "")
        for script in _SCRIPT_RE.findall(entry):
            if script == _WRAPPER_SCRIPT:
                continue
            active_scripts.add(script)
    return active_ids, active_scripts


def _hooks_named_in_note(note: str) -> tuple[set[str], set[str]]:
    """Return (hook_ids, script_basenames) that a graph edge's `note` field
    names — regardless of whether they are actually registered. This lets
    us detect edges naming a hook that is dead/unregistered (e.g.
    check_ac_coverage.py), not just edges naming a live one.
    """
    return set(_HOOK_ID_RE.findall(note)), set(_SCRIPT_RE.findall(note))


def test_ac1_enforcement_matches_registry_activity_for_every_named_hook():
    # covers: KM-ADM-001
    """KM-ADM-001: for every edge whose `note` names a guardian hook (by hook
    id or by backing script filename), the edge's `enforcement` rating must
    track whether that hook is actually active in
    templates/scripts/commit_guardian/commit_guardian.json:
      - if NONE of the named hooks are active -> enforcement must be "none".
      - if AT LEAST ONE named hook is active -> enforcement must NOT be "none".

    This assertion is derived from the registry at test time, not hardcoded,
    so it keeps catching drift even after the two currently-inverted ratings
    (ac-tested, ticket-touches) are fixed.
    """
    graph = _load_graph()
    registry = _load_registry()
    active_ids, active_scripts = _active_hook_identifiers(registry)

    violations: list[str] = []
    for edge in graph["edges"]:
        note = edge.get("note", "")
        named_ids, named_scripts = _hooks_named_in_note(note)
        named = named_ids | named_scripts
        if not named:
            # This edge's note does not name a specific guardian hook by id
            # or script filename — out of scope for this registry cross-check.
            continue

        any_active = bool(named_ids & active_ids) or bool(
            named_scripts & active_scripts
        )
        enforcement = edge.get("enforcement")

        if not any_active and enforcement != "none":
            violations.append(
                f"edge '{edge.get('id')}': named hook(s) {sorted(named)} are "
                f"NOT active in commit_guardian.json, but enforcement="
                f"{enforcement!r} (expected 'none')"
            )
        if any_active and enforcement == "none":
            violations.append(
                f"edge '{edge.get('id')}': named hook(s) {sorted(named)} ARE "
                f"active in commit_guardian.json, but enforcement='none' "
                f"(expected a non-'none' rating)"
            )

    assert not violations, (
        "artifact-knowledge-graph.graph.json edge enforcement ratings do not "
        "match commit_guardian.json hook registry activity:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_ac1_ac_tested_and_ticket_touches_ratings_are_not_inverted():
    # covers: KM-ADM-001
    """KM-ADM-001 regression pin: the specific inverted pair from the bug
    report. Both conditions are derived from the registry — not from
    hardcoding the expected enforcement string alone — so this test would
    also fail (correctly) if the registry itself changed such that either
    hook's actual active/inactive state flipped.

      - check_ac_coverage.py (backing 'ac-tested') must remain ABSENT from
        the registry's active scripts for 'warn' to be wrong; if it is
        absent, 'ac-tested' must not be rated 'warn'.
      - check-predone-scope (backing 'ticket-touches') must be an ACTIVE
        registered hook id for 'none' to be wrong; if it is active,
        'ticket-touches' must not be rated 'none'.
    """
    graph = _load_graph()
    registry = _load_registry()
    active_ids, active_scripts = _active_hook_identifiers(registry)

    edges_by_id = {edge["id"]: edge for edge in graph["edges"]}
    ac_tested = edges_by_id["ac-tested"]
    ticket_touches = edges_by_id["ticket-touches"]

    # Root cause precondition: check_ac_coverage.py is dead/unregistered.
    assert "check_ac_coverage.py" not in active_scripts, (
        "check_ac_coverage.py is now registered/active in commit_guardian.json — "
        "the 'ac-tested' rating must be re-derived, this pinned regression test "
        "is stale."
    )
    assert ac_tested["enforcement"] != "warn", (
        "'ac-tested' is rated 'warn' but its named backing script "
        "check_ac_coverage.py is absent from commit_guardian.json's hook "
        "registry (unregistered, dead code that never runs at commit time). "
        "This is the exact inverted-rating bug described in KM-ADM-001 — an "
        "unregistered hook must never earn a rating above 'none'."
    )

    # Root cause precondition: check-predone-scope is registered and active.
    assert "check-predone-scope" in active_ids, (
        "check-predone-scope is no longer active in commit_guardian.json — "
        "the 'ticket-touches' rating must be re-derived, this pinned "
        "regression test is stale."
    )
    assert ticket_touches["enforcement"] != "none", (
        "'ticket-touches' is rated 'none' but its actual backing hook "
        "check-predone-scope (check_files_touched_reconciliation.py) IS "
        "registered and active in commit_guardian.json "
        "(files_touched_reconciliation.enabled: true), reporting advisory "
        "scope violations at every ticket commit. This is the exact "
        "inverted-rating bug described in KM-ADM-001 — an active hook must "
        "never be rated 'none'."
    )
