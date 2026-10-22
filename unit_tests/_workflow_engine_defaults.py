"""
MODULE: _workflow_engine_defaults
GOAL: Script-specific default label responses and default ``args`` that the
      workflow engine harness merges under every caller's own.
BUSINESS CONTEXT: plan-feature.js and fast-lane-ship.js carry unconditional
    gates (workspace-setup permission, producibility, context bundle, the
    BO-4300 workspace step). Every pre-existing and future test that runs them
    needs a sane default for those gates without having to know about them.
ARCHITECTURE: Pure helpers (one real subprocess for the registry-backed
    permission verdict) read by ``run_workflow_under_e2`` in
    _workflow_engine_harness, which imports the two ``_default_*`` functions.
    Caller-supplied keys always win. Split out of the harness to honour the
    file-size ratchet.

DECISION HISTORY:
    - 2026-10-12 (BO-4300 ticket 10): moved verbatim out of
      _workflow_engine_harness.py; behaviour unchanged.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from _plan_feature_harness_defaults import plan_feature_default_label_responses
from _workflow_engine_workspace import _workspace_step_default_responses
from _wrong_version_harness_defaults import wrong_version_default_label_responses

logger = logging.getLogger(__name__)

# ACD-2100b-5: plan-feature.js's pre-Stage-0 workspace-setup permission gate
# no longer dispatches an agent() call at all (see the module docstring's
# "ACD-2100b-5" note) — its default now lives in _default_args_for_script()
# below, keyed by _WORKSPACE_SETUP_PERMISSION_ARGS_KEY, not here.
_PLAN_FEATURE_SCRIPT_NAME = "plan-feature.js"
_AGENT_REGISTRY_RELATIVE_PATH = Path("config") / "agent_registry.json"
_WORKSPACE_SETUP_PERMISSION_ARGS_KEY = "workspace_setup_permission"
_PREFLIGHT_SCRIPT_RELATIVE_PATH = Path("scripts") / "worktree" / "check_workspace_setup_permission.py"
_PREFLIGHT_DEFAULT_AGENT_ID = "worktree-agent"
_PREFLIGHT_SUBPROCESS_TIMEOUT_SECONDS = 15

# BO-2400f-12: fast-lane-ship.js dispatches an unconditional producibility-guard
# check ("check-producibility") between Resolve and the claim step. Its
# fail-closed default (a missing/unreadable verdict) REFUSES the run before any
# claim or build-agent dispatch — exactly the behavior BO-2400f-12 requires, but
# it means every PRE-EXISTING caller of this script that drives it past Resolve
# without knowing about the new label would otherwise see its claim/test-writer/
# coder dispatches vanish behind a refusal the moment this gate was added. As
# with _WORKSPACE_SETUP_PERMISSION_LABEL above, a real producible default is
# supplied here so every existing and future caller gets a sane "producible"
# verdict without having to know about this gate; a test that deliberately wants
# to exercise the refusal path still can — caller-supplied label_responses
# always take precedence over this default.
_FAST_LANE_SHIP_SCRIPT_NAME = "fast-lane-ship.js"
_CHECK_PRODUCIBILITY_LABEL = "check-producibility"

# BO-2400f-12: a producible verdict is meant to let the run proceed exactly as
# before this gate existed — including all the way to the test-writer dispatch,
# which sits behind the (pre-existing, BO-2400c-1) "fastlane-context-bundle"
# assembly step. A caller asserting only "test-writer was reached on a
# producible verdict" (BO-2400f-12-ii) has no reason to also know about that
# unrelated, earlier-shipped gate, so a real, schema-conforming default bundle
# (mirroring the one every context-bundle-aware caller already hand-stubs) is
# supplied here too — never a source of a false "obtained" verdict for a test
# that deliberately stubs its own bundle response instead.
_CONTEXT_BUNDLE_LABEL = "fastlane-context-bundle"
_CONTEXT_BUNDLE_DEFAULT_TEXT = (
    "ARCHITECTURE (stub)\n\nCONVENTIONS (stub)\n\nHIGH-LEVEL ACS (stub)"
    "\n\n<!-- CACHE_BREAKPOINT -->\n\nBATCH ACS (stub)\n\nPRIOR TESTS (stub)"
)

def _find_ancestor_containing(start: Path, relative_path: Path) -> Path | None:
    """Walk upward from `start` looking for an ancestor containing `relative_path`.

    Returns the ancestor directory (not the joined path) the first time
    ``ancestor / relative_path`` exists, or None if no ancestor up to the
    filesystem root has it. Used to locate the worktree/repo root from an
    arbitrary workflow script path without assuming a fixed nesting depth.
    """
    for ancestor in [start, *start.parents]:
        if (ancestor / relative_path).exists():
            return ancestor
    return None






















def _default_label_responses_for_script(script_path: Path) -> dict[str, Any]:
    """Return baseline label_responses every caller of `script_path` implicitly needs.

    fast-lane-ship.js has unconditional gates (BO-2400f-12's
    "check-producibility" and "fastlane-context-bundle") this supplies real
    defaults for. plan-feature.js's own two ('worktree-setup' /
    'resolve-worktree-setup-script-path', BO-1500a-5-i) are delegated to
    _plan_feature_harness_defaults.py (imported above; see its docstring),
    which returns `{}` for any other script.

    Caller-supplied label_responses always take precedence over any default
    here (see run_workflow_under_e2()'s merge order), so a test can still
    exercise a refusal path by overriding the same label. plan-feature.js's
    workspace-setup PERMISSION gate (distinct, earlier) is handled via
    `args`, not a label — see _default_args_for_script() (ACD-2100b-5).
    """
    defaults = _workspace_step_default_responses(script_path)
    if script_path.name == _FAST_LANE_SHIP_SCRIPT_NAME:
        return {
            **defaults,
            _CHECK_PRODUCIBILITY_LABEL: {
                "producible": True,
                "unproducible": [],
                "message": "all producible (harness default)",
            },
            _CONTEXT_BUNDLE_LABEL: {
                "obtained": True,
                "bundle": _CONTEXT_BUNDLE_DEFAULT_TEXT,
                "message": "bundle assembled (harness default)",
            },
        }

    return {**defaults, **plan_feature_default_label_responses(script_path), **wrong_version_default_label_responses(script_path)}


def _default_args_for_script(script_path: Path) -> dict[str, Any]:
    """Return baseline `args` every caller of `script_path` implicitly needs.

    ACD-2100b-5: plan-feature.js's Pre-Stage-0 workspace-setup permission
    gate no longer makes an agent() dispatch (see the module docstring's
    "ACD-2100b-5" note) — it reads `args.workspace_setup_permission`
    directly and fails closed when that key is absent, so every
    PRE-EXISTING caller of run_workflow_under_e2(plan-feature.js, ...) would
    otherwise see its run halt at Stage 0 the moment this gate landed,
    without ever knowing the new key exists.

    This returns a real, registry-backed "permitted" default for that key by
    running the ACTUAL pre-flight script (scripts/worktree/
    check_workspace_setup_permission.py) as a real subprocess against the
    real, on-disk config/agent_registry.json — never a hand-typed verdict
    literal, so the exact shape the script emits is what every caller's
    default is built from (mirrors this same "run the real thing, never
    fake its output shape" discipline as the removed label-shaped default
    it replaces).

    A test that wants to exercise the DENIAL path still can: caller-supplied
    `args` always take precedence over this default (see
    run_workflow_under_e2()'s merge order), so an explicit
    `args={"workspace_setup_permission": {...}}` override replaces it
    entirely.

    Returns an empty dict (no default) for any other script, or if the
    pre-flight script cannot be located/run/parsed — in which case
    plan-feature.js's own fail-closed behavior applies exactly as it would
    for a caller that never learned about this gate, so this is never a
    source of a false "permitted" verdict.
    """
    if script_path.name != _PLAN_FEATURE_SCRIPT_NAME:
        return {}

    repo_root = _find_ancestor_containing(
        script_path.resolve().parent, _AGENT_REGISTRY_RELATIVE_PATH
    )
    if repo_root is None:
        logger.warning(
            "Could not locate config/agent_registry.json above %s; no default "
            "workspace_setup_permission response supplied.",
            script_path,
        )
        return {}

    preflight_script = repo_root / _PREFLIGHT_SCRIPT_RELATIVE_PATH
    if not preflight_script.is_file():
        logger.warning(
            "Pre-flight script not found at %s; no default "
            "workspace_setup_permission response supplied.",
            preflight_script,
        )
        return {}

    try:
        proc = subprocess.run(
            [sys.executable, str(preflight_script), "--agent-id", _PREFLIGHT_DEFAULT_AGENT_ID],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=_PREFLIGHT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Failed to run pre-flight script %s: %s", preflight_script, exc)
        return {}

    if not proc.stdout.strip():
        logger.warning("Pre-flight script %s produced no stdout.", preflight_script)
        return {}

    try:
        verdict = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Pre-flight script %s produced non-JSON stdout: %s", preflight_script, exc
        )
        return {}

    return {_WORKSPACE_SETUP_PERMISSION_ARGS_KEY: verdict}
