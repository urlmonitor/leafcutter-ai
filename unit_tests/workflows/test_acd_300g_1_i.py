"""
MODULE: unit_tests/workflows/test_acd_300g_1_i.py
COVERS: ACD-300g-1-i
GOAL: Red-first specification of a failed commit after a stage approval: a hook rejection stops the pipeline
    before the next authoring agent, the user-facing text names the hook AND the hook's own error message, lists
    the failing files, advises fixing and re-running; an index conflict is reported as such, never retried and
    never forced; the stage's files stay on disk as uncommitted changes.
ARCHITECTURE: formatCommitError is the REAL function run through run_isolated_e2 (_plan_feature_e2_runner.py).
    The workflow-body tests resume the REAL plan-feature.js at gate-po with a person's approve and a scripted
    commit-stage-output reply (_acd_300g_support.py; run_workflow_under_e2 stands in for run_plan_feature_e2,
    which needs a hand-written JS mock per test).
RED STATE: formatCommitError drops commitOutcome.message: the text says only 'Hook "<name>" rejected the staged
    files', so the hook's own error text never reaches the user. The other six tests are green-today guards.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300g_support import PO_IDS, UNDO, calls, commit_failure, format_commit_error, gate_run, names, terminal  # noqa: E402

HOOK = "check-ac-schema"
HOOK_ERROR = "criteria assert ... declares_side_effect is not set"
FILES = ["docs/acceptance-criteria/x/ACD-9301.yaml", "docs/acceptance-criteria/x/ACD-9302.yaml"]
_FORCE = re.compile(r"--force|--force-with-lease|\bpush -f\b|\bgit [^\n]*\s-f\b")


def _hook_outcome(**changes) -> dict:
    return {"status": "error", "message": HOOK_ERROR, "hook_name": HOOK, "failing_files": FILES, "is_conflict": False, **changes}


def _approve_po(commit_reply: dict):
    return gate_run("strategic", "gate-po", "approve", PO_IDS, **{"commit-stage-output": commit_reply})


def test_acd_300g_1_i_hook_rejection_stops_the_pipeline():
    # covers: ACD-300g-1-i
    # angle: reachability
    """Strategic route, gate-po approved, the commit agent returns status error with hook_name
    check-ac-schema: no stage-ba-author dispatch follows and the run returns status error.

    Wrong version caught: the next authoring agent is dispatched after a hook rejection.
    """
    result = _approve_po(commit_failure(HOOK))

    assert len(calls(result, "commit-stage-output")) == 1, names(result)
    assert calls(result, "stage-ba-author") == [], names(result)
    assert terminal(result).get("status") == "error", terminal(result)


def test_acd_300g_1_i_message_names_hook_and_its_error():
    # covers: ACD-300g-1-i
    # angle: discrimination
    """formatCommitError with hook_name check-ac-schema and the hook's message: the returned text contains
    both the hook name and the hook's own error text.

    Wrong versions caught: the message says only that a pre-commit hook rejected the staged files when
    hook_name is set; the hook's own error message is dropped from the user-facing text.
    """
    text = format_commit_error(_hook_outcome())

    assert HOOK in text, text
    assert HOOK_ERROR in text, text


def test_acd_300g_1_i_message_lists_failing_files():
    # covers: ACD-300g-1-i
    # angle: criterion
    """formatCommitError with two failing_files: each path appears in the returned text; with failing_files
    absent the text still renders without a file list."""
    text = format_commit_error(_hook_outcome())
    assert [path for path in FILES if path not in text] == [], text

    outcome = _hook_outcome()
    del outcome["failing_files"]
    bare = format_commit_error(outcome)
    assert HOOK in bare and "undefined" not in bare and "- docs/" not in bare, bare


def test_acd_300g_1_i_hook_failure_advises_fix_and_rerun():
    # covers: ACD-300g-1-i
    # angle: criterion
    """On the hook branch (is_conflict false) the text tells the user to fix the validation errors and re-run
    /plan-feature; the conflict branch does not give this advice."""
    hook_text = format_commit_error(_hook_outcome())
    assert re.search(r"fix the validation errors", hook_text, re.IGNORECASE), hook_text
    assert "re-run /plan-feature" in hook_text, hook_text

    conflict_text = format_commit_error(_hook_outcome(hook_name=None, is_conflict=True))
    assert not re.search(r"validation errors", conflict_text, re.IGNORECASE), conflict_text


def test_acd_300g_1_i_failed_commit_leaves_files_on_disk():
    # covers: ACD-300g-1-i
    # angle: criterion
    """A failing commit: no dispatch after the commit carries git restore, git checkout, git reset or rm, the
    commit instructions say to leave the files as uncommitted changes, and the run's acs_as_drafts lists the
    stage's ids."""
    result = _approve_po(commit_failure(HOOK))

    commit_at = max(i for i, c in enumerate(result.agent_calls) if c.label == "commit-stage-output")
    later = [str(c.label) for c in result.agent_calls[commit_at + 1:] if UNDO.search(str(c.prompt))]
    assert later == [], names(result)
    assert "uncommitted changes" in result.agent_calls[commit_at].prompt, result.agent_calls[commit_at].prompt[-300:]
    assert sorted(terminal(result).get("acs_as_drafts") or []) == PO_IDS, terminal(result)


def test_acd_300g_1_i_conflict_reports_index_conflict_and_paths():
    # covers: ACD-300g-1-i
    # angle: discrimination
    """formatCommitError with is_conflict true and a failing path: the text contains 'index conflict' and the
    path, and does not claim a hook rejected the files.

    Wrong version caught: an index conflict is reported as a pre-commit hook rejection.
    """
    text = format_commit_error(commit_failure(conflict=True))

    assert "index conflict" in text, text
    assert "docs/acceptance-criteria/x/ACD-9301.yaml" in text, text
    assert not re.search(r"\bhook\b", text, re.IGNORECASE), text


def test_acd_300g_1_i_conflict_is_not_retried_or_forced():
    # covers: ACD-300g-1-i
    # angle: discrimination
    """A commit agent returning is_conflict true: exactly one commit-stage-output dispatch is recorded, and its
    instructions forbid a retry and --no-verify and contain no force flag.

    Wrong versions caught: the workflow re-dispatches the commit after a conflict; the commit instructions
    allow --no-verify or a force overwrite.
    """
    result = _approve_po(commit_failure(conflict=True))

    dispatched = calls(result, "commit-stage-output")
    assert len(dispatched) == 1, names(result)
    prompt = dispatched[0].prompt
    assert "Do NOT retry the commit" in prompt and "Do NOT run git commit --no-verify" in prompt, prompt[-400:]
    assert _FORCE.search(prompt) is None, _FORCE.search(prompt)
    assert terminal(result).get("status") == "error", terminal(result)
