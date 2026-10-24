"""
MODULE: unit_tests/workflows/_bo4000_fixtures.py
GOAL: Shared label_responses/fixture helpers for the BO-4000 family
    (BO-4000, BO-4000a, BO-4000b, BO-4000c, BO-4000d, BO-4000e, BO-4000f) -- the worktree step that must
    never nest a worktree, name a second location, or trust an agent's word about where it is.
BUSINESS CONTEXT: FIELD EVIDENCE -- run wf_0e0872f9-453, 2026-09-14 (see BO-4000.yaml notes). Every fixture
    here mirrors that incident's own literals so a reviewer can compare a test directly against the AC text.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the workflow no longer reads repository facts, names a location,
    compares branches, or asks a worktree agent to open anything. The location, its reuse, its naming and its
    refusals (occupied, stale, unfetchable) all belong to the workspace maker; the workflow takes the
    maker's ONE accepted answer (handed in as ``args.workspace`` or the reply to one ``workspace-ensure``
    dispatch of the maker command) and nothing else. These fixtures therefore script that one reply -- an
    ok answer, a refusal, or no usable answer -- in the shell-executor shape the real engine delivers.
ARCHITECTURE: Builds on unit_tests/workflows/_bo3900_fixtures.py's epic scaffolding (epic-planner /
    signoff-readback / epic-recheck).
"""
from __future__ import annotations

from typing import Any

from unit_tests._workflow_engine_harness import (
    workspace_ensure_reply,
    workspace_refusal_reply,
)
from unit_tests.workflows import _bo3900_fixtures as fx

MAIN_CHECKOUT = "C:/Users/Hendrik/Code/leafcutter/leafcutter-ai"
WORKTREE_BASE = "C:/Users/Hendrik/Code/leafcutter/worktrees"
UXP_WORKTREE = "C:/Users/Hendrik/Code/leafcutter/worktrees/uxp-700-tranche-2"
EPIC_NAME = "EPIC-TruthfulProjectRecord"
NAMED_LOCATION = WORKTREE_BASE + "/" + EPIC_NAME
INCIDENT_NESTED = UXP_WORKTREE + "/tickets/00_inbox/epics/" + EPIC_NAME
TARGET_BRANCH = "epic/truthful-project-record"

WORKSPACE_LABEL = "workspace-ensure"

# BO-4300a-1-ia: the one probe that resolves the maker's absolute path runs before the workspace step (consumer_drift).
MAKER_PATH_LABEL = "resolve-maker-path"

# Every dispatch the workspace step itself accounts for; anything else is a phase agent.
RESOLVE_PHASE_LABELS = frozenset({"resolve-target", MAKER_PATH_LABEL, WORKSPACE_LABEL})


def ready_workspace(path: str = NAMED_LOCATION, *, branch: str = TARGET_BRANCH, **extra: Any) -> dict[str, Any]:
    """The shell executor's reply to the ONE workspace dispatch when the maker answers ok at *path*."""
    return workspace_ensure_reply(path, branch=branch, **extra)


def refused_workspace(
    code: str = "OCCUPIED", message: str = "the workspace location is occupied", **extra: Any
) -> dict[str, Any]:
    """The reply when the maker REFUSES (``status: refused``); *extra* rides the answer (occupant, counts...)."""
    return workspace_refusal_reply(code, message, **extra)


def success_label_responses(
    *,
    ticket_paths: list[str],
    resolved_worktree_path: str | None = None,
    opened_worktree_path: str = NAMED_LOCATION,
    workspace_reply: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A full label_responses dict driving build-feature.js all the way to per-ticket dispatch.

    The workspace is the maker's answer to the one ``workspace-ensure`` dispatch: ready at
    ``resolved_worktree_path`` when the target already has a workspace (a reuse -- the maker answers
    ``created: false``), else at ``opened_worktree_path``. ``workspace_reply`` replaces the reply wholesale
    (a refusal, prose, no answer ...). The resolver's own ``worktree_path`` is still reported -- it is a
    claim, and the workflow must ignore it.
    """
    location = resolved_worktree_path or opened_worktree_path
    base = fx.base_epic_label_responses(
        epic_path=EPIC_NAME, worktree_path=location, ticket_paths=ticket_paths,
    )
    return {
        **base,
        "resolve-target": {
            "target_type": "epic", "epic_path": EPIC_NAME, "ticket_path": None,
            "worktree_path": resolved_worktree_path,
        },
        WORKSPACE_LABEL: (
            workspace_reply
            if workspace_reply is not None
            else ready_workspace(location, created=resolved_worktree_path is None)
        ),
    }
