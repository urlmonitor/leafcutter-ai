"""
MODULE: unit_tests/workflows/_bo4000_fixtures.py
GOAL: Shared label_responses/fixture helpers for the BO-4000 family
    (BO-4000, BO-4000a, BO-4000b, BO-4000c) — the worktree step that decides
    reuse/open/refuse from repository FACTS rather than an agent's judgement
    or the resolver's own word.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14 (see
    BO-4000.yaml notes). Every fixture here mirrors that incident's own
    literals so a reviewer can compare a test directly against the AC text.
ARCHITECTURE: Builds on unit_tests/workflows/_bo3900_fixtures.py's epic
    scaffolding (epic-planner / signoff-readback / epic-recheck), adding the
    BO-4000 repository-facts labels build-feature.js's worktree step now
    dispatches: worktree-facts-resolved, worktree-base, worktree-facts-
    location, branch-standing, worktree-setup.
"""
from __future__ import annotations

import json
from typing import Any

from unit_tests.workflows import _bo3900_fixtures as fx

MAIN_CHECKOUT = "C:/Users/Hendrik/Code/leafcutter/leafcutter-ai"
WORKTREE_BASE = "C:/Users/Hendrik/Code/leafcutter/worktrees"
UXP_WORKTREE = "C:/Users/Hendrik/Code/leafcutter/worktrees/uxp-700-tranche-2"
EPIC_NAME = "EPIC-TruthfulProjectRecord"
NAMED_LOCATION = WORKTREE_BASE + "/" + EPIC_NAME
INCIDENT_NESTED = UXP_WORKTREE + "/tickets/00_inbox/epics/" + EPIC_NAME
TARGET_BRANCH = "epic/truthful-project-record"


def envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """A repo-facts {output, exit_code} envelope wrapping *payload*."""
    return {"output": json.dumps(payload), "exit_code": 0}


def facts(
    *, exists=True, is_git_toplevel=True, is_linked_worktree=True,
    is_main_checkout=False, same_repository=True, branch="epic/truthful-project-record",
) -> dict[str, Any]:
    """A repository-facts payload matching BO-4000's delivers_to schema."""
    return {
        "exists": exists, "is_git_toplevel": is_git_toplevel,
        "is_linked_worktree": is_linked_worktree, "is_main_checkout": is_main_checkout,
        "same_repository": same_repository, "branch": branch,
    }


def not_a_checkout() -> dict[str, Any]:
    """Facts for a path that is not a git checkout at all (or absent)."""
    return facts(
        exists=False, is_git_toplevel=False, is_linked_worktree=False,
        is_main_checkout=False, same_repository=None, branch=None,
    )


def base_response(worktree_base: str = WORKTREE_BASE, layout: str = "dev") -> dict[str, Any]:
    """label_responses["worktree-base"] envelope value."""
    return envelope({"main_checkout": MAIN_CHECKOUT, "worktree_base": worktree_base, "layout": layout})


def branch_standing(*, exists=True, fetch_ok=True, behind=0, ahead=0) -> dict[str, Any]:
    """label_responses["branch-standing"] envelope value."""
    return envelope({"branch": TARGET_BRANCH, "exists": exists, "fetch_ok": fetch_ok, "behind": behind, "ahead": ahead})


def open_worktree_response(worktree_path: str = NAMED_LOCATION, status: str = "created") -> dict[str, Any]:
    """label_responses["worktree-setup"] value for the OPEN-a-new-worktree path."""
    return {"worktree_path": worktree_path, "status": status}


def success_label_responses(
    *,
    ticket_paths: list[str],
    resolved_worktree_path: str | None = None,
    resolved_worktree_facts: dict[str, Any] | None = None,
    worktree_base: str = WORKTREE_BASE,
    location_facts: dict[str, Any] | None = None,
    standing: dict[str, Any] | None = None,
    opened_worktree_path: str = NAMED_LOCATION,
) -> dict[str, Any]:
    """A full label_responses dict driving build-feature.js all the way to
    per-ticket dispatch, with every BO-4000 repository-facts label controlled.

    When ``resolved_worktree_path`` is None (the default), the run has no
    pre-resolved worktree and must name-and-open a new one — the
    "worktree-base" / "worktree-facts-location" / "branch-standing" /
    "worktree-setup" labels below drive that path. When it is set, the
    "worktree-facts-resolved" label alone decides reuse (BO-4000 scenario 1).
    """
    base = fx.base_epic_label_responses(
        epic_path=EPIC_NAME, worktree_path=opened_worktree_path, ticket_paths=ticket_paths,
    )
    responses: dict[str, Any] = {
        **base,
        "resolve-target": {
            "target_type": "epic", "epic_path": EPIC_NAME, "ticket_path": None,
            "worktree_path": resolved_worktree_path,
        },
        "worktree-base": base_response(worktree_base),
        "worktree-facts-location": envelope(location_facts or {"exists": False}),
        "branch-standing": standing if standing is not None else branch_standing(),
        "worktree-setup": open_worktree_response(opened_worktree_path),
    }
    if resolved_worktree_path is not None:
        responses["worktree-facts-resolved"] = envelope(resolved_worktree_facts or facts())
    return responses
