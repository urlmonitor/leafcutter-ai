"""
MODULE: test_inf_500d_4_iii_older_worktree_build
GOAL: Tests for review-fix defect M-3 -- the workspace maker must survive a workspace whose own
    ``build.py`` predates ``--log-root`` / ``--no-log-root``.
AC: INF-500d-4-iii (every per-drive workspace is built pointing at the enduring log location of its project;
    when it cannot be, say so loudly rather than leave a silent gap); ADR-069 section 3.

THE DEFECT: the maker runs the WORKSPACE'S OWN ``build.py`` (the branch's, not the project install's) and
    hands it ``--log-root <root>`` or ``--no-log-root``. A branch cut before those flags existed has a
    ``build.py`` whose argparse rejects them (exit 2). Treating that as "the build failed" leaves a workspace
    that is not ready and says nothing about the log root.

THE CONTRACT: a build that rejects the log-root flag is retried ONCE WITHOUT the flag; the maker prints, on
    stderr, a loud ``WARNING`` that the workspace got no durable log root (so what it logs will not survive its
    removal); its answer stays ok; and the workspace carries its own build output. A build that accepts the
    flag is called once, with the recorded root, and no warning of this kind is printed (the control).

REAL-ARTIFACT NOTE: the REAL deployed maker runs as a separate process against a real bare hub and project
    clone. The only stand-in is the project's ``scripts/build.py`` (see ``_inf_500d_4_iii_support``): it
    records every argv it receives and, when it is the "older" build, exits 2 with ``unrecognized arguments``
    on the first call that carries a log-root flag. A real build costs ~60s (CLAUDE.md "Tests must not spawn
    their own build.py").
"""
# @ac-tag: INF-500d-4-iii

from __future__ import annotations

import re

import pytest

from unit_tests.portability import _inf_500d_4_iii_support as sup


def _no_durable_root_warning(stderr: str) -> list[str]:
    """WARNING lines saying the workspace has no durable/enduring log root (its logs will not survive removal)."""
    return [
        line for line in stderr.splitlines()
        if "WARNING" in line and "root" in line.lower() and re.search(r"durable|enduring|survive", line, re.IGNORECASE)
    ]


@pytest.mark.parametrize("main_declares_a_root", [True, False], ids=["project_has_a_declaration", "project_has_none"])
def test_older_workspace_build_is_retried_without_the_flag(tmp_path, main_declares_a_root):
    # covers: INF-500d-4-iii
    # angle: failure
    """The workspace's own build.py rejects --log-root/--no-log-root (exit 2): the maker retries the build once
    without the flag, prints a WARNING that the workspace got no durable log root, answers ok, and the
    workspace carries its own build output."""
    root = tmp_path / "enduring" / "debugging" / "logs"
    install, maker = sup.project_install(tmp_path)
    if main_declares_a_root:
        sup.write_real_declaration(install, root)

    run = sup.ensure_workspace(tmp_path, "older", maker, rejects_log_flags_once=True)

    assert (run["answer"].get("status"), run["exit_code"]) == ("ok", 0), (
        f"an older workspace build must not make the maker refuse: {run['answer']}\n{run['stderr']}")
    argvs = run["calls"]
    assert len(argvs) == 2, f"the maker must retry a build that rejected the flag exactly once; saw {argvs}"
    expected_flag = "--log-root" if main_declares_a_root else "--no-log-root"
    assert expected_flag in argvs[0], f"the first attempt is the one that carries the flag: {argvs[0]}"
    assert not any(arg in sup.LOG_FLAGS for arg in argvs[1]), f"the fallback build must run WITHOUT the log-root flags: {argvs[1]}"
    workspace = run["workspace"]
    assert (workspace / "INSTALLED_MARKER.txt").is_file(), "the fallback build did not produce the workspace's own output"
    assert (workspace / ".leafcutter" / "config" / "knowledge_sink.json").is_file()
    retry_warning = [line for line in run["stderr"].splitlines() if "WARNING" in line and expected_flag in line]
    assert retry_warning, f"the retry must be announced by a WARNING naming {expected_flag}; stderr was:\n{run['stderr']}"
    assert _no_durable_root_warning(run["stderr"]), (
        "the maker must warn loudly that this workspace got no durable log root (what it logs will not survive "
        f"its removal); stderr was:\n{run['stderr']}")


def test_a_workspace_build_that_knows_the_flag_is_called_once_with_the_recorded_root(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """Control for the retry above: a build that accepts the flag runs once, gets the root the project recorded,
    and no 'no durable root' warning is printed -- so the fallback is only for a rejection and cannot be
    satisfied by always dropping the flag."""
    root = tmp_path / "enduring" / "debugging" / "logs"
    install, maker = sup.project_install(tmp_path)
    sup.write_real_declaration(install, root)

    run = sup.ensure_workspace(tmp_path, "newer", maker, rejects_log_flags_once=False)

    assert (run["answer"].get("status"), run["exit_code"]) == ("ok", 0), run["answer"]
    argvs = run["calls"]
    assert len(argvs) == 1, f"a build that accepts the flag must not be retried: {argvs}"
    assert "--log-root" in argvs[0], f"the build must be told the recorded root: {argvs[0]}"
    assert argvs[0][argvs[0].index("--log-root") + 1] == str(root), f"the recorded root must be passed verbatim: {argvs[0]}"
    assert not _no_durable_root_warning(run["stderr"]), f"nothing is wrong, nothing to warn about:\n{run['stderr']}"
