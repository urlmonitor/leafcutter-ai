"""
MODULE: unit_tests/workflows/_tq500g1vi_remedy.py
GOAL: Drive both twins (templates/workflows-js/build-feature.js and build-ticket.js) through a commit that is
    refused once with a remedy handoff, the remedy agent runs, and the commit is dispatched again, with the
    wrong-version steps answered by the scenario.
BUSINESS CONTEXT: The remedy loop needs REAL ticket records (the driver confirms the handed-to agent by reading
    its new sign-off back), so this uses unit_tests/prompt_assembly/_driver_harness.py and its node harness,
    the same pair test_bo_3800a_2.py drives. That harness knows nothing of the wrong-version labels, so this
    module runs a PATCHED COPY of harness_build_ticket_guard.mjs written to a temp folder (the shared file is
    left untouched): any ``*-wv-*`` dispatch is answered from ``scenario.wv_replies[label]`` (a list is served
    one entry per call, the last repeated) and recorded in ``dispatched``; the ticket planner reports
    ``cfg.source_ac``. Nothing else in the harness changes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

import _bo3800b_support as S  # noqa: E402
import _driver_harness as H  # noqa: E402
import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402

_ANCHOR = "  // --- remedy-declaration read (BO-3800b)"
_COUNTS = 'const attemptCounts = {};'
_PLANNER = "has_test_requirements: cfg.has_test_requirements === true,"
_ROOT = 'const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");'
_WV_BLOCK = """  if (/-wv-/.test(label)) {
    const wvIndex = wvCounts[label] || 0;
    wvCounts[label] = wvIndex + 1;
    let wvSpec = (scenario.wv_replies || {})[label];
    if (Array.isArray(wvSpec)) wvSpec = wvSpec[Math.min(wvIndex, wvSpec.length - 1)];
    dispatched.push(label);
    timeline.push({ kind: "wv", label, ticket_path: null });
    dispatches.push({ label, agent_type: opts.agentType || null, phase: opts.phase || null, ticket_path: null,
      attempt: wvIndex + 1, prompt: String(prompt), opts_keys: Object.keys(opts || {}), opts_brief: null, opts_ticket_path: null });
    return wvSpec === undefined ? null : wvSpec;
  }

"""


def patched_harness_source() -> str:
    src = Path(H.HARNESS).read_text(encoding="utf-8")
    for needle in (_ANCHOR, _COUNTS, _PLANNER, _ROOT):
        assert src.count(needle) == 1, f"driver harness changed shape: {needle!r}"
    src = src.replace(_ANCHOR, _WV_BLOCK + _ANCHOR).replace(_COUNTS, _COUNTS + " const wvCounts = {};")
    src = src.replace(_PLANNER, _PLANNER + "\n      ...(cfg.source_ac !== undefined ? { source_ac: cfg.source_ac } : {}),")
    return src.replace(_ROOT, f"const REPO_ROOT = {str(Path(H.REPO_ROOT).as_posix())!r};")


def commit_refusal() -> dict:
    """The commit phase's reply to a complexity refusal: a handoff to restructuring-specialist with its remedy record."""
    decl = S.declaration("check-complexity")
    return S.refusal_reply(decl, S.complexity_demand())


def drive_refused_once(driver: str, route: fx.Route, wv_by_label: dict) -> tuple[dict, str]:
    """Drive one ticket whose commit is refused once then accepted, under *driver* (a TWIN_DRIVERS key).

    Returns ``(observation, ticket path)``; ``wv_by_label`` is the scenario's wrong-version reply table.
    """
    wt = S.make_worktree("tq500g1vi-")
    try:
        decl = S.declaration("check-complexity")
        path = H.write_ticket_record(wt, S.TICKET, ["commit"], extra_frontmatter={"component": "build-orchestration"})
        Path(path).write_bytes(Path(path).read_bytes().replace(bytes([13, 10]), bytes([10])))  # the node harness parses LF records only
        cfg = {"title": "remedy loop", "phases": ["commit"], "has_test_requirements": True, "source_ac": [fx.AC],
               "results": {"commit": [commit_refusal(), {"status": "ok"}], S.SPECIALIST: {"status": "ok"}}}
        scenario = H.single_ticket_scenario(wt, path, cfg)
        scenario["remedy_declarations"] = {decl["hook_id"]: decl}
        scenario["wv_replies"] = wv_by_label
        with tempfile.TemporaryDirectory(prefix="tq500g1vi-harness-") as scratch:
            patched = Path(scratch) / "harness_wv.mjs"
            patched.write_text(patched_harness_source(), encoding="utf-8")
            with mock.patch.object(H, "HARNESS", str(patched)):
                return H.run_driver(H.TWIN_DRIVERS[driver], scenario), path
    finally:
        S.drop_worktree(wt)


def wv_table(route: fx.Route, finish_replies) -> dict:
    """Wrong-version replies for the scenario: nothing owed; *finish_replies* is served one entry per call."""
    return {**fx.wv_replies(route), route.finish: finish_replies}


def wv_and_commit_order(obs: dict, route: fx.Route) -> list[str]:
    """The recorded dispatches that matter to the remedy loop, in order."""
    keep = {route.recover, route.list, route.breaker, route.finish, "commit", S.SPECIALIST}
    return [label for label in obs["dispatched"] if label in keep]


def passing_finish() -> dict:
    return v.finish_reply(v.verdict_f1())
