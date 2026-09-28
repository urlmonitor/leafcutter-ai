"""
MODULE: unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py
GOAL: RED test stubs for TQ-500f-3-ii -- /build-feature's per-ticket phase
    driver (driveTicketPhases in templates/workflows-js/build-feature.js) and
    its declared twin (build-ticket.js) must run the SAME verify_red_baseline
    reader the fast lane runs, between the test-writer phase and the first
    coder dispatch, and must NOT take the test-writer's own
    ``red_baseline_verified`` sign-off claim as a substitute.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

TODAY (unmodified code): driveTicketPhases() dispatches every needed phase
(test-writer, then python-coder) back-to-back with NO gate dispatch between
them at all -- the only "evidence" is test-writer's own self-reported
``red_baseline_verified`` field in its PHASE_RESULT_SCHEMA reply, which this
file's fixtures (_tq500f3ii_fixtures.py) ALWAYS set to True. Every test below
is expected to fail against that unmodified code: no dispatch carries the
label ``red-baseline-gate`` (see _tq500f3ii_fixtures.py's own docstring for
the pinned target contract), and the coder is dispatched unconditionally.

Every test drives the REAL, unmodified workflow script's own top-level body
via unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() -- a
real Node.js subprocess -- and asserts on the RECORDED dispatch sequence
(agent_calls, in order) and the terminal payload (.result), never on a
string found in the driver's source. Per CLAUDE.md "Gate / Workflow ACs --
Verify Behaviorally, Not by Grep".

WRONG-VERSION DISCRIMINATION this file proves against (IT-PO's own
must_catch list for TQ-500f-3-ii): "gate placed after the coder" / "gate
dispatched but verdict ignored" / "trusts red_baseline_verified" all leave
the K1 test (test 2) green against the bug and red against the fix -- the
opposite of what a real fix needs, so today's code (which does exactly
"trusts red_baseline_verified") fails it. "build-ticket.js twin not
updated" is caught by test 4. "heavy lane passes different ids or omits the
AC root" / "run the reader for K3 and halt on no_new_covering_tests" /
"record K3 as verified" are caught by tests 3 and 5.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import unit_tests.workflows._tq500f3ii_fixtures as fx  # noqa: E402
import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
BUILD_TICKET_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"
FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_TIMEOUT = 30
_ORDERED_PHASES = [
    {"agent": "test-writer", "status": "needed"},
    {"agent": "python-coder", "status": "needed"},
]


_UNSET = object()


def _drive_build_feature(ac_id, gate_response, *, source_ac_override=_UNSET):
    source_ac = ac_id if source_ac_override is _UNSET else source_ac_override
    label_responses = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH,
        worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=_ORDERED_PHASES,
        source_ac=source_ac,
        gate_response=gate_response,
    )
    return run_workflow_under_e2(
        BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": fx.TICKET_ABS_PATH},
    )


def test_build_feature_runs_red_baseline_reader_between_test_writer_and_coder():
    # covers: TQ-500f-3-ii
    # angle: reachability
    # surface_invoked: templates/workflows-js/build-feature.js driven under unit_tests/_workflow_engine_harness.py (single-ticket target)
    """The recorded dispatch sequence has a heavy_lane_gate execution (the
    thin fast_lane.py CLI subcommand wrapping verify_red_baseline -- see
    _tq500f3ii_fixtures.py's DESIGN CHANGE note) after the test-writer phase
    and before any python-coder dispatch, and its prompt carries the
    ticket's source_ac and worktree.
    """
    ac_id = "TQ-FIX-3II-REACH"
    result = _drive_build_feature(
        ac_id, fx.red_baseline_gate_response(gate_passed=True)
    )
    assert result.error == "", f"Harness error: {result.error}"

    dispatched_labels = [c.label for c in result.agent_calls]
    tw_idx = fx.first_index_with_label(result, "test-writer")
    gate_idx = fx.first_index_with_label(result, fx.RED_BASELINE_GATE_LABEL)
    coder_idx = fx.first_index_with_label(result, "python-coder")

    assert tw_idx is not None, f"test-writer was never dispatched; labels={dispatched_labels}"
    assert gate_idx is not None, (
        "No dispatch carrying label 'red-baseline-gate' was recorded -- the "
        "heavy lane must run heavy_lane_gate (which wraps the SAME "
        "verify_red_baseline reader the fast lane runs -- no second reader), "
        f"between test-writer and the coder; labels={dispatched_labels}"
    )
    assert coder_idx is not None, f"python-coder was never dispatched; labels={dispatched_labels}"
    assert tw_idx < gate_idx < coder_idx, (
        "The gate dispatch must sit strictly between test-writer and the "
        f"first coder dispatch; indices tw={tw_idx} gate={gate_idx} coder={coder_idx}, "
        f"labels(in order)={dispatched_labels}"
    )

    gate_calls = fx.calls_with_label(result, fx.RED_BASELINE_GATE_LABEL)
    gate_prompt = gate_calls[0].prompt if gate_calls else ""
    gate_prompt_text = gate_prompt if isinstance(gate_prompt, str) else json.dumps(gate_prompt)
    # presence-only: checks the prompt the workflow actually dispatched at runtime (captured by the harness), not source text; gate ordering and verdict are asserted behaviourally above and below
    assert "heavy_lane_gate" in gate_prompt_text, (
        "The gate dispatch prompt must invoke the fast_lane.py 'heavy_lane_gate' "
        f"subcommand (DESIGN CHANGE -- see _tq500f3ii_fixtures.py); got: {gate_prompt_text!r}"
    )
    assert fx.WORKTREE_ABS_PATH in gate_prompt_text, (
        f"The gate dispatch prompt must carry the ticket's worktree as --test-root; "
        f"got: {gate_prompt_text!r}"
    )
    assert ac_id in gate_prompt_text, (
        f"The gate dispatch prompt must carry the ticket's source_ac; got: {gate_prompt_text!r}"
    )


def test_build_feature_halts_k1_before_coder_despite_writer_claiming_red():
    # covers: TQ-500f-3-ii
    # angle: criterion
    """K1: the test-writer's own sign-off claims red_baseline_verified=True,
    but the independently re-run gate reports gate_passed=False (absence
    refusal). No coder is dispatched, and the halt payload names the
    refusal. K2: gate_passed=True, and the coder is dispatched as today.
    """
    k1_ac_id = "TQ-FIX-3II-K1"
    k1_reason = "declared_test_refused_absence_only_red"
    result_k1 = _drive_build_feature(
        k1_ac_id,
        fx.red_baseline_gate_response(
            gate_passed=False,
            reason=k1_reason,
            refused=[
                {
                    "nodeid": "tests/test_k1.py::test_t1_absence",
                    "ac_id": k1_ac_id,
                    "kind": "absence",
                    "message": "a test naming wrong versions to catch must fail by reaching the code",
                }
            ],
        ),
    )
    assert result_k1.error == "", f"Harness error: {result_k1.error}"
    coder_calls_k1 = fx.calls_with_label(result_k1, "python-coder")
    assert coder_calls_k1 == [], (
        "K1 must NOT reach the coder -- the test-writer's own "
        "red_baseline_verified=True claim (always set by this fixture, see "
        "_tq500f3ii_fixtures.test_writer_claims_red_response) must not "
        "substitute for the independently re-run gate's own gate_passed=False "
        f"verdict; dispatched labels={[c.label for c in result_k1.agent_calls]}"
    )
    payload_text = json.dumps(result_k1.result or {}).lower()
    # presence-only: checks the workflow's runtime halt payload (result_k1.result), not fast-lane-ship.js source; the halt itself is asserted behaviourally above (no coder dispatch)
    assert (
        k1_reason.lower() in payload_text
        or "red-baseline" in payload_text
        or "verify_red_baseline" in payload_text
    ), (
        "K1's halt payload must name the red-baseline gate's own refusal, "
        f"not a generic halt; result={result_k1.result!r}"
    )

    k2_ac_id = "TQ-FIX-3II-K2"
    result_k2 = _drive_build_feature(
        k2_ac_id, fx.red_baseline_gate_response(gate_passed=True)
    )
    assert result_k2.error == "", f"Harness error: {result_k2.error}"
    coder_calls_k2 = fx.calls_with_label(result_k2, "python-coder")
    assert len(coder_calls_k2) >= 1, (
        "K2 (gate_passed=True) must still dispatch the coder, exactly as "
        f"today; dispatched labels={[c.label for c in result_k2.agent_calls]}"
    )


def test_heavy_and_fast_lane_invocations_yield_identical_verdict():
    # covers: TQ-500f-3-ii
    # angle: seam
    """Real producer, real consumer, real fixture: the gate command captured
    from a REAL build-feature.js dispatch, and the gate command
    fast-lane-ship.js's own (already-shipped, unchanged) redBaselineInvocation
    template builds for the SAME ac id + worktree, are each executed for
    real against the SAME real temp git repo + real temp AC store (the
    TQ-500f-3-i T1/T2 shape). Both must print byte-identical JSON verdicts.
    """
    import subprocess
    import tempfile

    ac_id = "TQ-FIX-3II-SEAM"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        work_dir, base_sha = gitfx.make_worktree(tmp_root)
        # AC store lives at the SAME location build-feature.js's own
        # AC_STORE_REL_PATH convention ("docs/acceptance-criteria", relative
        # to the ticket's worktree) resolves it to -- so the captured
        # command's own --ac-root value, once the worktree placeholder is
        # re-pointed at this real work_dir below, already names a directory
        # that actually holds this fixture's AC YAML (no separate temp dir).
        ac_root = work_dir / "docs" / "acceptance-criteria"
        gitfx.write_ac_yaml(ac_root, ac_id, gitfx.t1_t2_t3_test_spec())
        test_root = work_dir / "tests"
        gitfx.write_t1_t2_t3_test_files(test_root, ac_id)
        # The heavy lane's captured command's own script path is anchored at
        # "<worktree>/{{config.output_root}}/scripts/build_orchestration/
        # fast_lane.py" -- a REAL, physically distinct copy of the fast_lane
        # module family must exist there for the re-pointed command to run
        # at all (FIXTURE BUG fix: the raw template was executed unresolved
        # before, which always failed with Errno 2 regardless of what the
        # production code did).
        gitfx.install_fast_lane_scripts_into(work_dir)

        # --- side A: the REAL command captured from a real build-feature.js dispatch ---
        result = _drive_build_feature(
            ac_id,
            fx.red_baseline_gate_response(gate_passed=True),
        )
        gate_calls = fx.calls_with_label(result, fx.RED_BASELINE_GATE_LABEL)
        assert gate_calls, (
            "No 'red-baseline-gate' dispatch was captured from build-feature.js -- "
            "cannot extract its real command; the gate dispatch this seam test "
            f"needs does not exist yet. labels={[c.label for c in result.agent_calls]}"
        )
        heavy_prompt = gate_calls[0].prompt
        heavy_prompt_text = heavy_prompt if isinstance(heavy_prompt, str) else json.dumps(heavy_prompt)
        heavy_command = fx.extract_gate_invocation(heavy_prompt_text)
        assert heavy_command is not None, (
            "Could not find a 'python3 ... fast_lane.py verify_red_baseline|"
            f"heavy_lane_gate ...' command line in the captured gate prompt: {heavy_prompt_text!r}"
        )
        # This fixture's worktree is a temp path (not fx.WORKTREE_ABS_PATH), and
        # the command's own script-path segment carries the UNRESOLVED
        # "{{config.output_root}}" build-time placeholder (never substituted
        # when a workflow script is driven as raw source under the harness,
        # as opposed to through build.py) -- both must be resolved to real,
        # on-disk locations before the command can actually run. This is the
        # SAME substitution unit_tests/workflows/test_acd_2100a_1.py's own
        # JS-side shim applies (`.replace(/\{\{config\.output_root\}\}/g,
        # '.leafcutter')`), applied here on the Python side since this test
        # executes the extracted command directly rather than through a
        # second harness-shim run.
        heavy_command = heavy_command.replace(fx.WORKTREE_ABS_PATH, str(work_dir))
        heavy_command = heavy_command.replace("{{config.output_root}}", ".leafcutter")
        assert "{{config.output_root}}" not in heavy_command, (
            f"Unresolved build-time placeholder left in the command to execute: {heavy_command!r}"
        )

        # --- side B: fast-lane-ship.js's OWN existing, unchanged invocation
        # template (redBaselineInvocation), read from the real source file and
        # substituted with this fixture's real runtime values. Runs the REAL
        # repo's own fast_lane.py directly (not the worktree-anchored copy --
        # fast-lane-ship.js's own command is never worktree-relative). ---
        fast_lane_ship_source = FAST_LANE_SHIP_JS.read_text(encoding="utf-8")
        # presence-only: fixture precondition that the fast lane's command template still exists before side B is built; the seam itself is proven by executing both commands and comparing verdicts below
        assert "verify_red_baseline --ac-ids ${batchIds} --test-root ${worktreePath}" in fast_lane_ship_source, (
            "fast-lane-ship.js's redBaselineInvocation template line was not "
            "found verbatim -- cannot build side B of the seam comparison from "
            "the real source."
        )
        fast_lane_command = (
            f"{sys.executable} {gitfx.GATE_SCRIPT} verify_red_baseline "
            f"--ac-ids {ac_id} --test-root {work_dir} --ac-root {ac_root}"
        )

        def _run(cmd_text: str) -> dict:
            cmd_text = cmd_text.replace("python3", sys.executable, 1)
            argv = shlex.split(cmd_text, posix=False)
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return {
                    "__unparseable_stdout__": proc.stdout,
                    "__stderr__": proc.stderr,
                    "__returncode__": proc.returncode,
                    "__argv__": argv,
                }

        heavy_verdict = _run(heavy_command)
        fast_lane_verdict = _run(fast_lane_command)

        # heavy_lane_gate wraps verify_red_baseline's own verdict with three
        # additional keys (applicable/verified/outcome) -- see
        # test_heavy_lane_gate_verdict_equals_verify_red_baseline_no_second_reader
        # in test_tq500f3ii_heavy_lane_gate_subcommand.py, which pins the SAME
        # "strip the wrapper, compare the rest" comparison for the subcommand
        # in isolation. Here the wrapper keys are stripped for the byte-equality
        # check below, then separately pinned so this test still proves the
        # wrapper itself is correct for this fixture, not just discarded.
        wrapper_only_keys = {"applicable", "verified", "outcome"}
        heavy_core = {k: v for k, v in heavy_verdict.items() if k not in wrapper_only_keys}

        assert heavy_core == fast_lane_verdict, (
            "The heavy lane's captured gate command (after stripping its own "
            "applicable/verified/outcome wrapper keys) and fast-lane-ship.js's "
            "own redBaselineInvocation command must produce IDENTICAL "
            f"verify_red_baseline verdicts for the same fixture: "
            f"heavy(core)={heavy_core!r} fast_lane={fast_lane_verdict!r} "
            f"(heavy_command={heavy_command!r} fast_lane_command={fast_lane_command!r})"
        )
        assert heavy_verdict.get("applicable") is True, (
            f"This fixture supplies a real source_ac with real covering tests -- "
            f"heavy_lane_gate's own 'applicable' wrapper key must be True; "
            f"heavy_verdict={heavy_verdict!r}"
        )
        assert heavy_verdict.get("verified") == heavy_verdict.get("gate_passed"), (
            "heavy_lane_gate's own 'verified' wrapper key must track "
            f"'gate_passed' exactly for this (applicable=True) fixture; "
            f"heavy_verdict={heavy_verdict!r}"
        )


def test_build_ticket_twin_gates_coder_identically():
    # covers: TQ-500f-3-ii
    # angle: deployed
    """build-ticket.js -- the declared TWIN of build-feature.js's per-ticket
    driver -- driven under the same harness with the K1/K2 gate responses,
    halts K1 before the coder and dispatches the coder for K2, so the twin
    cannot drift from build-feature.js.
    """

    def _drive_build_ticket(ac_id, gate_response):
        label_responses = fx.base_label_responses(
            ticket_path=fx.TICKET_ABS_PATH,
            worktree_path=fx.WORKTREE_ABS_PATH,
            ordered_phases=_ORDERED_PHASES,
            source_ac=ac_id,
            gate_response=gate_response,
        )
        return run_workflow_under_e2(
            BUILD_TICKET_JS,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ticket_path": fx.TICKET_ABS_PATH, "worktree_path": fx.WORKTREE_ABS_PATH},
        )

    result_k1 = _drive_build_ticket(
        "TQ-FIX-3II-TWIN-K1",
        fx.red_baseline_gate_response(
            gate_passed=False, reason="declared_test_refused_absence_only_red"
        ),
    )
    assert result_k1.error == "", f"Harness error: {result_k1.error}"
    coder_calls_k1 = fx.calls_with_label(result_k1, "python-coder")
    assert coder_calls_k1 == [], (
        "build-ticket.js (the twin) must halt K1 before the coder, exactly as "
        f"build-feature.js does; dispatched labels={[c.label for c in result_k1.agent_calls]}"
    )

    result_k2 = _drive_build_ticket(
        "TQ-FIX-3II-TWIN-K2", fx.red_baseline_gate_response(gate_passed=True)
    )
    assert result_k2.error == "", f"Harness error: {result_k2.error}"
    coder_calls_k2 = fx.calls_with_label(result_k2, "python-coder")
    assert len(coder_calls_k2) >= 1, (
        "build-ticket.js (the twin) must dispatch the coder for K2, exactly as "
        f"build-feature.js does; dispatched labels={[c.label for c in result_k2.agent_calls]}"
    )


def test_build_feature_records_reader_not_applicable_for_ticket_without_source_ac():
    # covers: TQ-500f-3-ii
    # angle: failure
    """K3: a ticket with NO source_ac. No verify_red_baseline gate dispatch
    is made at all, the drive records 'red-baseline reader not applicable:
    no source requirement', the coder is still dispatched, and no recorded
    field marks the red baseline verified.
    """
    result = _drive_build_feature(
        "TQ-FIX-3II-K3-UNUSED", gate_response=None, source_ac_override=None
    )
    assert result.error == "", f"Harness error: {result.error}"

    gate_calls = fx.calls_with_label(result, fx.RED_BASELINE_GATE_LABEL)
    assert gate_calls == [], (
        "K3 (no source_ac) must NOT dispatch the red-baseline gate at all; "
        f"dispatched labels={[c.label for c in result.agent_calls]}"
    )
    coder_calls = fx.calls_with_label(result, "python-coder")
    assert len(coder_calls) >= 1, (
        "K3 must still reach the coder (no source requirement to gate against); "
        f"dispatched labels={[c.label for c in result.agent_calls]}"
    )
    payload_text = json.dumps(result.result or {}).lower()
    assert "red-baseline reader not applicable: no source requirement" in payload_text, (
        "K3's recorded outcome must state the exact decided phrase "
        f"'red-baseline reader not applicable: no source requirement'; result={result.result!r}"
    )
    assert '"red_baseline_verified": true' not in payload_text.replace(" ", ""), (
        "K3 must never be recorded as red-baseline VERIFIED -- there was no "
        f"source requirement to verify against; result={result.result!r}"
    )
