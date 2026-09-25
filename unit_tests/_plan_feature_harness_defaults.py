"""
MODULE: _plan_feature_harness_defaults
GOAL: plan-feature.js-specific default `agent()` label responses for
    unit_tests/_workflow_engine_harness.py's `run_workflow_under_e2()`.
BUSINESS CONTEXT: BO-1500a-5-i made plan-feature.js's Pre-Stage-0 Authoring
    Worktree Bootstrap fail CLOSED whenever the 'worktree-setup' reply is
    success-shaped (an explicit exit_code) but names no worktree_path -- and
    the harness's OWN generic default stub for an unlabeled agent() call
    (`{"exit_code": 0, "output": "", ...}`) is exactly that shape. Before
    BO-1500a-5-i that shape was silently accepted; after it, every
    PRE-EXISTING caller of `run_workflow_under_e2(plan-feature.js, ...)`
    that never supplied its own 'resolve-worktree-setup-script-path' /
    'worktree-setup' label responses started halting at Pre-Stage-0 instead
    of reaching whatever later gate/pause/dispatch it actually wanted to
    exercise (measured regression: 36 newly-failing tests). This module
    supplies a real, well-formed default for both labels, mirroring
    `scripts/setup_ticket_worktree.py`'s own `create-ac-worktree` JSON
    stdout shape exactly (`{"worktree_path", "branch", "ac_store_path",
    "created"}`) -- never a hand-typed shape that only coincidentally
    satisfies the parser -- the same precedent ACD-2100b-5 and BO-2400f-12
    already set inside _workflow_engine_harness.py itself for their own
    gates (workspace_setup_permission, check-producibility). Split into its
    own module (rather than added inline) because
    unit_tests/_workflow_engine_harness.py is covered by the
    check-file-size ratchet, which already sat at its line-count ceiling
    before this fix.

    A test that wants to exercise ANY of BO-1500a-5-i's four non-confirming
    shapes (refused / uninterpretable / no_workspace_named / silent_success)
    still can: caller-supplied label_responses always take precedence over
    this default for the SAME label (run_workflow_under_e2()'s merge order
    puts `_default_label_responses_for_script()`'s result, which calls
    into this module, UNDER caller-supplied label_responses) -- e.g.
    unit_tests/workflows/test_bo_1500a_5_i.py's own explicit override of
    the 'worktree-setup' label alone replaces this default for that label
    only; its 'resolve-worktree-setup-script-path' dispatch (which it does
    not override) resolves successfully against this default instead,
    exactly as it would against a real script.

    Matched via `_is_plan_feature_script()`, not a bare filename check, so
    a source-patched TEMP COPY of plan-feature.js -- some tests
    (test_acd_2100c_5.py) write a small, surgical text-substitution copy of
    plan-feature.js's real on-disk source to a `tempfile.NamedTemporaryFile`
    with an UNRELATED filename so they can exercise one injected line while
    every surrounding call site stays REAL and unmodified -- still gets
    these two labels' real defaults too. `_PLAN_FEATURE_CONTENT_SIGNATURE`
    is a string unique to plan-feature.js among this repo's workflow
    scripts (confirmed by `grep -rl` across templates/workflows-js/ at the
    time this was written) that survives a small text substitution
    elsewhere in the file.
ARCHITECTURE: Pure-Python helper module, no test classes of its own. Lives
    directly under unit_tests/, a sibling of _workflow_engine_harness.py,
    which imports `plan_feature_default_label_responses` as its one public
    entry point.

DECISION HISTORY
================================================================================
- 2026-09-25 [python-coder]: /quick-fix. Split out of
  unit_tests/_workflow_engine_harness.py (see this module's own GOAL/
  BUSINESS CONTEXT above for the underlying fix) because that file is
  covered by the check-file-size ratchet and had no room left to grow.
  Also fixes a related ReferenceError regression in
  templates/workflows-js/plan-feature.js itself: see that file's own
  DECISION HISTORY for BO-2300a-1-ii / BO-1500a-5-i (peekPausedGateId(),
  resolveGate(), and pauseAtGate() each gained a LOCAL
  `_shellPermittedAgentId` constant instead of referencing the module-level
  `workspaceSetupAgentId`, because those three functions are extracted
  verbatim into a standalone Node driver by
  unit_tests/workflows/test_acd_2100c_1.py's own extraction mechanism, which
  never restores this harness module's defaults or that file's top-level
  body at all). (quick-fix; no ticket file)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PLAN_FEATURE_SCRIPT_NAME = "plan-feature.js"

_WORKTREE_SETUP_SCRIPT_LABEL = "resolve-worktree-setup-script-path"
_WORKTREE_SETUP_LABEL = "worktree-setup"
_WORKTREE_SETUP_DEFAULT_SCRIPT_PATH = (
    "/tmp/harness-default-repo/.leafcutter/scripts/setup_ticket_worktree.py"
)
_WORKTREE_SETUP_DEFAULT_WORKTREE_PATH = "/tmp/harness-default-ac-worktree"
_WORKTREE_SETUP_DEFAULT_BRANCH = "ac-authoring/harness-default"
_WORKTREE_SETUP_DEFAULT_AC_STORE_PATH = (
    "/tmp/harness-default-ac-worktree/docs/acceptance-criteria"
)

# A string unique to plan-feature.js among this repo's workflow scripts
# (see module docstring) that survives a small text substitution elsewhere
# in the file -- the content-signature fallback for a source-patched temp
# copy whose basename does not match _PLAN_FEATURE_SCRIPT_NAME.
_PLAN_FEATURE_CONTENT_SIGNATURE = "resolveRepoAnchoredScriptPath"


def _is_plan_feature_script(script_path: Path) -> bool:
    """True when `script_path` is plan-feature.js, or a source-patched TEMP
    COPY of it (see module docstring for why the fallback exists).

    Matches by filename first (the common, cheap case), then falls back to
    the content-signature check. Any read error on a path that failed the
    filename check is treated as "not a match" -- never a source of a false
    default for an unrelated script.
    """
    if script_path.name == _PLAN_FEATURE_SCRIPT_NAME:
        return True
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _PLAN_FEATURE_CONTENT_SIGNATURE in source


def plan_feature_default_label_responses(script_path: Path) -> dict[str, Any]:
    """Return the plan-feature.js-specific default label_responses for
    `script_path`, or `{}` if it is not plan-feature.js (see
    `_is_plan_feature_script()`).

    The one public entry point unit_tests/_workflow_engine_harness.py's
    `_default_label_responses_for_script()` calls into. Caller-supplied
    label_responses always take precedence over this default for the same
    label -- see this module's own docstring for the merge-order guarantee.
    """
    if not _is_plan_feature_script(script_path):
        return {}
    return {
        _WORKTREE_SETUP_SCRIPT_LABEL: {
            "output": _WORKTREE_SETUP_DEFAULT_SCRIPT_PATH,
            "exit_code": 0,
            "stderr": "",
        },
        _WORKTREE_SETUP_LABEL: {
            "output": json.dumps(
                {
                    "worktree_path": _WORKTREE_SETUP_DEFAULT_WORKTREE_PATH,
                    "branch": _WORKTREE_SETUP_DEFAULT_BRANCH,
                    "ac_store_path": _WORKTREE_SETUP_DEFAULT_AC_STORE_PATH,
                    "created": False,
                }
            ),
            "exit_code": 0,
            "stderr": "",
        },
    }
