"""Finalize step 3.5 sub-step A ends at the feature branch's HEAD on both paths.

`git merge --abort` is `reset --merge`: it keeps unstaged working-tree edits, so an
unstaged `status: done` left by the completion write survives, step 3.5 B2 skips the
ticket as already closed, and the closure never happens. The merge-in-progress branch
must therefore also run `git reset --hard HEAD` after the abort, as the no-merge
branch already does.

Established pattern for this file: structural tests over the text of the shipped
prompt (see unit_tests/test_finalize_feature_single_writer_close.py); no driver
harness exists for finalize-feature.js. The prompt is extracted by its dispatch
label, so the assertion reads the real `step-3.5-reset-merge` instructions.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_LABEL = 'label: "step-3.5-reset-merge"'


def _reset_merge_prompt() -> str:
    js = _JS_PATH.read_text(encoding="utf-8")
    end = js.index(_LABEL)
    start = js.rindex("await agent(", 0, end)
    return js[start:end]


def test_step_3_5_resets_to_head_after_merge_abort():
    # covers: UNKNOWN
    # angle: discrimination
    # must_catch: merge-in-progress branch runs only `merge --abort` (keeps unstaged edits)
    prompt = _reset_merge_prompt()
    m = re.search(r"2\. If exit code is 0.*?(?=\n\"?\s*\+?\s*\"?\n?\s*\"?3\. If exit code)", prompt, re.S)
    assert m, "merge-in-progress branch (step 2) not found in the step-3.5-reset-merge prompt"
    branch = m.group(0)
    assert "merge --abort" in branch, branch
    assert "reset --hard HEAD" in branch, (
        "merge --abort keeps unstaged edits; the merge-in-progress branch must also "
        "run `git reset --hard HEAD`:\n" + branch
    )
    assert branch.index("merge --abort") < branch.index("reset --hard HEAD"), (
        "reset --hard HEAD must run after the abort"
    )
    # control: the no-merge branch keeps its reset
    no_merge = prompt[prompt.index("3. If exit code is non-zero"):]
    assert "reset --hard HEAD" in no_merge
