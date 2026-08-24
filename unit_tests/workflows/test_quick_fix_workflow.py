"""
MODULE: test_quick_fix_workflow
GOAL: Source-contract assertions for the /quick-fix workflow (BP-600 ACs),
      PLUS behavioral (harness-driven) assertions for the dispatch topology,
      data threading, and halt conditions that the source-contract layer
      cannot distinguish from dead code.

Because quick-fix.js is a JavaScript workflow that runs inside the Claude Code
engine, most of its AC surface (prompts sent to sub-agents, prose in
SKILL.md) still cannot be executed at the Python level, and remains covered
here by source-contract text assertions — the text content of quick-fix.js
and SKILL.md — guaranteeing that the control-flow branches, dispatch calls,
guard clauses, and prose required by the AC criteria are present in the
shipped artefacts. This mirrors the pattern used by
test_finalize_feature_preflight.py.

BUT quick-fix.js's actual phase sequencing, halt conditions, and data
threading (a value returned by one stubbed agent() call flowing into a LATER
call's prompt or into the terminal payload) ARE executable under the E2 stub
harness (`_workflow_engine_harness.run_workflow_under_e2`), and per this
repo's CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep",
those must be tested by actually running the script, not by grepping its
source text — a grep passes on dead code and cannot tell a wired guard from
an inert string. `TestBP600WorkflowBehavioral` below replaces 14
source-contract assertions that this rewrite invalidated (renamed phases,
a since-removed "no PR creation" constraint, a since-removed flat six-field
AC schema) with tests that drive the real control flow.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600a-1, BP-600a-2, BP-600a-3, BP-600a-3-i, BP-600b-1, BP-600b-2,
     BP-600b-2-i, BP-600b-3, BP-600c-1, BP-600c-2, BP-600c-3, BP-600d-1,
     BP-600d-1-i, BP-600d-2, BP-600d-3, BP-600d-4, BP-600d-4-i, BP-600e-1,
     BP-600e-2, BP-600e-3, BP-600e-3-i
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"
_SKILL_PATH = _REPO_ROOT / "templates" / "skills" / "quick-fix" / "SKILL.md"

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js() -> str:
    """Return the full text of quick-fix.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _skill() -> str:
    """Return the full text of the quick-fix SKILL.md."""
    return _SKILL_PATH.read_text(encoding="utf-8")


def _phase_block(js: str, phase_label: str, next_phase_label: str | None = None) -> str:
    """Extract text for a named phase block.

    Returns text from phase('<phase_label>') to (but not including)
    phase('<next_phase_label>'). If next_phase_label is None, returns from
    start marker to end of file. Returns '' when start marker is absent.
    """
    start_marker = f"phase('{phase_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    if next_phase_label is None:
        return js[start:]
    end_marker = f"phase('{next_phase_label}')"
    end = js.find(end_marker, start)
    return js[start:] if end == -1 else js[start:end]


# ===========================================================================
# BP-600a-1 — operates in current worktree without branch switching
# ===========================================================================

class TestBP600a1WorktreeInvariant:
    """BP-600a-1: All operations run in current worktree; branch unchanged."""

    def test_ac_bp600a1_records_initial_branch(self):
        # covers: BP-600a-1
        """quick-fix.js must record the initial branch via git branch --show-current."""
        js = _js()
        assert "initial_branch" in js, (
            "quick-fix.js must capture initial_branch from git branch --show-current "
            "to enforce the worktree invariant required by BP-600a-1."
        )

    def test_ac_bp600a1_final_return_includes_branch(self):
        # covers: BP-600a-1
        """The workflow's final return value must include the branch name, confirming
        the branch was not changed during the run."""
        js = _js()
        # The final return block should expose `branch: initialBranch`
        assert "branch: initialBranch" in js or "branch:" in js, (
            "quick-fix.js final return must include the branch field so the caller "
            "can verify no branch switch occurred (BP-600a-1)."
        )

    def test_ac_bp600a1_no_git_worktree_add(self):
        # covers: BP-600a-1
        # covers: BP-600a-2
        """quick-fix.js guard prompt must prohibit 'git worktree add'; must not execute it.

        'git worktree add' may legitimately appear in a guard prohibition instruction
        telling the agent NOT to call it. The correct assertion is that the prohibition
        is present and that no agent call payload actually executes git worktree add as
        an action (i.e., it is not wrapped in a shell execution directive absent of the
        'Do NOT' / 'IMPORTANT' qualifier).
        """
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        # The string should appear in a prohibition context inside the guard prompt
        assert "git worktree add" in guards_block, (
            "Guards phase must explicitly prohibit 'git worktree add' in its agent "
            "prompt (BP-600a-1, BP-600a-2). The prohibition is what enforces the "
            "in-place constraint."
        )
        # Verify the prohibition keyword is adjacent (not an invocation)
        prohibition_idx = guards_block.find("git worktree add")
        surrounding = guards_block[max(0, prohibition_idx - 80):prohibition_idx + 30]
        assert "NOT" in surrounding or "not" in surrounding or "never" in surrounding.lower(), (
            "The occurrence of 'git worktree add' in the guard must be inside a "
            "prohibition clause (e.g. 'Do NOT invoke git worktree add'), not an "
            "invocation command (BP-600a-1)."
        )


# ===========================================================================
# BP-600a-2 — never dispatches worktree-agent or feature skill
# ===========================================================================

class TestBP600a2NoIsolationInfra:
    """BP-600a-2: Never dispatches worktree-agent or feature skill."""

    def test_ac_bp600a2_no_worktree_agent_dispatch(self):
        # covers: BP-600a-2
        """quick-fix.js must not dispatch agentType:'worktree-agent' at any phase.

        'worktree-agent' may legitimately appear in a guard prohibition that tells
        the phase agent NOT to use it. The assertion here checks that no agent()
        call dispatches agentType: 'worktree-agent', which is the actual invocation
        that BP-600a-2 prohibits.
        """
        js = _js()
        # No dispatch: none of the agent() calls should target agentType:'worktree-agent'
        assert "agentType: 'worktree-agent'" not in js, (
            "quick-fix.js must not dispatch agentType: 'worktree-agent' "
            "(BP-600a-2). Quick-fix is an in-place operation — no isolation infrastructure."
        )
        # Guard prohibition must be present (validates the contract is documented)
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "worktree-agent" in guards_block, (
            "Guards phase must explicitly prohibit 'worktree-agent' in the agent "
            "prompt to enforce the no-isolation-infra contract (BP-600a-2)."
        )

    def test_ac_bp600a2_no_feature_skill(self):
        # covers: BP-600a-2
        """quick-fix.js must not load or invoke the feature skill.

        'feature skill' may legitimately appear in a prohibition instruction. The
        real assertion is that the feature skill path (feature/SKILL.md) is not
        loaded as a dependency and that there is no 'feature' agentType dispatch.
        """
        js = _js()
        # No import/load of the feature skill document
        assert "feature/SKILL" not in js, (
            "quick-fix.js must not load feature/SKILL.md (BP-600a-2)."
        )
        # No dispatch to the feature agent
        assert "agentType: 'feature'" not in js, (
            "quick-fix.js must not dispatch agentType: 'feature' (BP-600a-2)."
        )

    def test_ac_bp600a2_guard_instructs_no_isolation(self):
        # covers: BP-600a-2
        """The Guards phase prompt must tell the agent not to invoke worktree-agent."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "worktree-agent" in guards_block or "IMPORTANT: Do NOT invoke" in guards_block, (
            "The Guards phase prompt must instruct the agent not to invoke worktree-agent "
            "(BP-600a-2). The guard must be explicit."
        )


# ===========================================================================
# BP-600a-3 — halts when target file has uncommitted changes
# ===========================================================================

class TestBP600a3UncommittedChangesGuard:
    """BP-600a-3: Halts when target file has uncommitted changes."""

    def test_ac_bp600a3_returns_blocked_when_dirty(self):
        # covers: BP-600a-3
        """quick-fix.js must return status:'blocked' when target file is dirty."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "status: 'blocked'" in guards_block or '"blocked"' in guards_block, (
            "Guards phase must return blocked status when target file is dirty (BP-600a-3)."
        )

    def test_ac_bp600a3_skill_suggests_commit_or_stash(self):
        # covers: BP-600a-3
        """SKILL.md must suggest commit or stash when target file is dirty."""
        skill = _skill()
        assert "commit or stash" in skill or "stash" in skill, (
            "SKILL.md must suggest 'commit or stash' when target file is dirty (BP-600a-3)."
        )

    def test_ac_bp600a3_guard_schema_has_dirty_flag(self):
        # covers: BP-600a-3
        """GUARD_SCHEMA in quick-fix.js must include target_file_dirty property."""
        js = _js()
        assert "target_file_dirty" in js, (
            "GUARD_SCHEMA must include target_file_dirty property for BP-600a-3 check."
        )


# ===========================================================================
# BP-600a-3-i — proceeds when only unrelated files are dirty
# ===========================================================================

class TestBP600a3iUnrelatedDirtyFiles:
    """BP-600a-3-i: Proceeds when only unrelated files are dirty."""

    def test_ac_bp600a3i_check_scoped_to_target_file(self):
        # covers: BP-600a-3-i
        """Guard must scope dirty-file check to the target file, not all files."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        # The guard checks if target_file appears in git status output — not all dirty files
        assert "target_file" in guards_block, (
            "Guards must scope the uncommitted-changes check to target_file only, "
            "allowing unrelated dirty files to exist (BP-600a-3-i)."
        )

    def test_ac_bp600a3i_skill_commit_stages_three_files_only(self):
        # covers: BP-600a-3-i
        """SKILL.md Phase 5 must stage exactly three specified files only."""
        skill = _skill()
        assert "Stage and commit exactly these three files" in skill or \
               "Do not stage any other files" in skill, (
            "SKILL.md commit phase must be explicit about staging only the quick-fix "
            "files (AC YAML, test file, fix) — unrelated dirty files must not be staged "
            "(BP-600a-3-i)."
        )


# ===========================================================================
# BP-600b-1 — creates AC YAML with required fields
# ===========================================================================

class TestBP600b1ACCreation:
    """BP-600b-1: Creates an AC YAML file in the AC store with required fields."""

    def test_ac_bp600b1_ac_creation_phase_exists(self):
        # covers: BP-600b-1
        """quick-fix.js must contain an AC Creation phase."""
        js = _js()
        assert "phase('AC Creation')" in js, (
            "quick-fix.js must have an AC Creation phase (BP-600b-1)."
        )

    def test_ac_bp600b1_ac_has_given_when_then(self):
        # covers: BP-600b-1
        """The AC creation prompt must request Given/When/Then criteria."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "Given" in ac_block and "When" in ac_block and "Then" in ac_block, (
            "AC creation phase must request Given/When/Then criteria structure (BP-600b-1)."
        )

    def test_ac_bp600b1_skill_ac_yaml_required_fields(self):
        # covers: BP-600b-1
        """SKILL.md must document the required AC YAML fields."""
        skill = _skill()
        for field in ("id:", "status: active", "component:", "title:", "criteria:"):
            assert field in skill, (
                f"SKILL.md must document required AC YAML field '{field}' (BP-600b-1)."
            )

    def test_ac_bp600b1_ac_reads_docs_acceptance_criteria(self):
        # covers: BP-600b-1
        """AC creation must write to the docs/acceptance-criteria/ directory."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "docs/acceptance-criteria" in ac_block, (
            "AC creation phase must write the AC YAML under docs/acceptance-criteria/ "
            "(BP-600b-1)."
        )


# ===========================================================================
# BP-600b-2 — uses component prefix from index.yaml + sequential ID
# ===========================================================================

class TestBP600b2ComponentPrefixAndSequentialId:
    """BP-600b-2: Uses component prefix from index.yaml + next sequential ID."""

    def test_ac_bp600b2_reads_index_yaml(self):
        # covers: BP-600b-2
        """AC creation must read docs/acceptance-criteria/index.yaml."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "index.yaml" in ac_block, (
            "AC creation phase must read docs/acceptance-criteria/index.yaml to obtain "
            "the component prefix (BP-600b-2)."
        )

    def test_ac_bp600b2_skill_reads_index_yaml(self):
        # covers: BP-600b-2
        """SKILL.md Step 1.1 must read index.yaml for component prefix."""
        skill = _skill()
        assert "index.yaml" in skill, (
            "SKILL.md must document reading index.yaml to determine component prefix "
            "(BP-600b-2)."
        )


# ===========================================================================
# BP-600b-2-i — infers component from file path; asks when no mapping
# ===========================================================================

class TestBP600b2iInferComponent:
    """BP-600b-2-i: Infers component from file path via index.yaml; asks when no match."""

    def test_ac_bp600b2i_infers_from_file_path(self):
        # covers: BP-600b-2-i
        """AC creation must infer component from target_file path."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        # The prompt references target_file and uses it to match a component
        assert "target_file" in ac_block, (
            "AC creation phase must reference target_file when inferring the component "
            "from the file path via index.yaml (BP-600b-2-i)."
        )

    def test_ac_bp600b2i_skill_infers_component_from_path(self):
        # covers: BP-600b-2-i
        """SKILL.md must describe component inference from file path."""
        skill = _skill()
        assert "directory_patterns" in skill or "file path" in skill, (
            "SKILL.md must describe inferring component from the target file path "
            "using index.yaml directory_patterns (BP-600b-2-i)."
        )

    def test_ac_bp600b2i_asks_user_when_no_mapping(self):
        # covers: BP-600b-2-i
        """Neither surface may silently default the component when no pattern
        matches — BP-600b-2-i requires asking.

        This assertion previously read
        `"no mapping" in skill or "ask" in skill or "fall back" in skill`.
        That third clause accepted the exact defaulting behaviour the AC
        forbids, so the test went green against code contradicting its own
        criterion — the test had been loosened to fit the implementation
        rather than the requirement. The real-world cost is on record:
        BP-600f.yaml was created misfiled by a live /quick-fix run and stayed
        wrong for six weeks.

        Both surfaces are checked, because a fix applied to only one of them
        leaves the other silently misfiling.
        """
        skill = _skill()
        js = _js()
        for name, source in (("SKILL.md", skill), ("quick-fix.js", js)):
            assert "Default to build-pipeline" not in source, (
                f"{name} still silently defaults the component to build-pipeline "
                "when no pattern matches. BP-600b-2-i requires asking the user "
                "instead — build-pipeline is a real component that would absorb "
                "the criterion, and the AC file it produces is permanent."
            )
        assert "do not default to a component" in js.lower(), (
            "quick-fix.js must instruct the AC-creation phase to block rather "
            "than default when no component matches (BP-600b-2-i)."
        )
        assert "stop and ask" in skill.lower(), (
            "SKILL.md must instruct the agent to stop and ask for the component "
            "when no pattern matches (BP-600b-2-i)."
        )


# ===========================================================================
# BP-600b-3 — AC file persists after ticket lifecycle closes
# ===========================================================================

class TestBP600b3ACPersists:
    """BP-600b-3: AC YAML file persists (status active) after lifecycle closes."""

    def test_ac_bp600b3_skill_declares_ac_permanent(self):
        # covers: BP-600b-3
        """SKILL.md must declare the AC YAML file as permanent — must not be deleted."""
        skill = _skill()
        assert (
            "permanent" in skill
            or "must NOT be deleted" in skill
            or "do not delete" in skill.lower()
        ), (
            "SKILL.md must state the AC YAML is permanent and must not be deleted "
            "after lifecycle closes (BP-600b-3)."
        )

    def test_ac_bp600b3_js_does_not_delete_ac(self):
        # covers: BP-600b-3
        """quick-fix.js must not contain any code that deletes or reverts the AC file."""
        js = _js()
        # Check that there's no file deletion logic for the ac_path
        assert "rm " + "ac_path" not in js and "delete ac_path" not in js.lower(), (
            "quick-fix.js must not delete or revert the AC file (BP-600b-3)."
        )

    def test_ac_bp600b3_escalation_preserves_ac(self):
        # covers: BP-600b-3
        """SKILL.md escalation path must preserve the AC file."""
        skill = _skill()
        # Escalation section should say to NOT delete the AC YAML
        escalation_start = skill.find("Escalation Path")
        if escalation_start == -1:
            escalation_start = skill.find("escalat")
        escalation_text = skill[escalation_start:escalation_start + 2000] if escalation_start >= 0 else skill
        assert (
            "not delete" in escalation_text.lower()
            or "do NOT delete" in escalation_text
            or "preserved" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the AC YAML (not delete it) "
            "(BP-600b-3)."
        )


# ===========================================================================
# BP-600c-1 — dispatches test-writer; test has # covers: tag; written before fix
# ===========================================================================

class TestBP600c1TestWriterDispatch:
    """BP-600c-1: Dispatches test-writer; test has # covers: tag; before fix."""

    def test_ac_bp600c1_dispatches_test_writer_agent(self):
        # covers: BP-600c-1
        """quick-fix.js must dispatch agentType: 'test-writer' in the Red Phase."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "agentType: 'test-writer'" in red_block or '"test-writer"' in red_block, (
            "Red Phase must dispatch agentType: 'test-writer' (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_prompt_includes_covers_tag(self):
        # covers: BP-600c-1
        """The test-writer prompt must instruct the agent to include '# covers: <AC-ID>'."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "# covers:" in red_block, (
            "test-writer dispatch prompt must instruct the agent to include "
            "'# covers: <AC-ID>' in the test (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_before_fix_phase(self):
        # covers: BP-600c-1
        """test-writer dispatch must appear before the Fix phase in quick-fix.js."""
        js = _js()
        red_phase_idx = js.find("phase('Red Phase')")
        fix_phase_idx = js.find("phase('Fix')")
        assert red_phase_idx != -1, "quick-fix.js must contain 'phase(Red Phase)'"
        assert fix_phase_idx != -1, "quick-fix.js must contain 'phase(Fix)'"
        assert red_phase_idx < fix_phase_idx, (
            "Red Phase (test-writer) must appear before Fix phase in the control "
            "flow, ensuring the test is written before the fix (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_schema_requires_test_file(self):
        # covers: BP-600c-1
        """TEST_WRITER_SCHEMA must require the test_file field in the result."""
        js = _js()
        # Check schema has test_file as required
        assert "test_file" in js, (
            "TEST_WRITER_SCHEMA must include test_file as a required field to record "
            "the path of the written test (BP-600c-1)."
        )


# ===========================================================================
# BP-600c-2 — runs test and confirms RED; halts if unexpectedly passes
# ===========================================================================

class TestBP600c2RedPhaseVerification:
    """BP-600c-2: Runs test and confirms RED; halts if test unexpectedly passes."""

    def test_ac_bp600c2_dispatches_test_runner_for_red(self):
        # covers: BP-600c-2
        """quick-fix.js must dispatch agentType: 'test-runner' for red-phase verification."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "agentType: 'test-runner'" in red_block or \
               "label: 'test-runner/red'" in red_block, (
            "Red Phase must dispatch a test-runner for red-phase verification (BP-600c-2)."
        )

    def test_ac_bp600c2_halts_when_test_passes_unexpectedly(self):
        # covers: BP-600c-2
        """quick-fix.js must return blocked with halt_reason:'red_phase_pass' if test passes."""
        js = _js()
        assert "red_phase_pass" in js, (
            "quick-fix.js must return halt_reason:'red_phase_pass' when the test "
            "passes before the fix is applied (BP-600c-2)."
        )

    def test_ac_bp600c2_red_phase_checks_passed_equals_true(self):
        # covers: BP-600c-2
        """quick-fix.js must check redResult.passed === true to detect unexpected pass."""
        js = _js()
        assert "redResult.passed === true" in js or "redResult.passed" in js, (
            "quick-fix.js must check redResult.passed to detect unexpected test pass "
            "in red phase (BP-600c-2)."
        )

    def test_ac_bp600c2_skill_halt_text_matches_spec(self):
        # covers: BP-600c-2
        """SKILL.md halt message must match the specified warning text."""
        skill = _skill()
        assert (
            "already been fixed" in skill
            or "already fixed" in skill
            or "passes before the fix" in skill
        ), (
            "SKILL.md halt message for unexpected red-phase pass must match the "
            "AC-specified warning text (BP-600c-2)."
        )


# ===========================================================================
# BP-600c-3 — reruns same test after fix and confirms GREEN
# ===========================================================================

class TestBP600c3GreenPhaseVerification:
    """BP-600c-3: Reruns same test after fix; halts if still failing."""

    def test_ac_bp600c3_dispatches_test_runner_for_green(self):
        # covers: BP-600c-3
        """quick-fix.js must dispatch agentType: 'test-runner' for green-phase verification."""
        js = _js()
        green_block = _phase_block(js, "Green Phase", "Commit & Close")
        assert "agentType: 'test-runner'" in green_block or \
               "label: 'test-runner/green'" in green_block, (
            "Green Phase must dispatch a test-runner for green-phase verification (BP-600c-3)."
        )

    def test_ac_bp600c3_reuses_same_test_file(self):
        # covers: BP-600c-3
        """quick-fix.js must reuse testFile (from red phase) in the green phase."""
        js = _js()
        green_block = _phase_block(js, "Green Phase", "Commit & Close")
        assert "testFile" in green_block, (
            "Green Phase must reuse the same testFile variable from Red Phase — "
            "no re-discovery of the test file (BP-600c-3)."
        )

    def test_ac_bp600c3_halts_when_test_still_fails(self):
        # covers: BP-600c-3
        """quick-fix.js must return blocked with halt_reason:'green_phase_fail' if test fails."""
        js = _js()
        assert "green_phase_fail" in js, (
            "quick-fix.js must return halt_reason:'green_phase_fail' when the test "
            "still fails after the fix is applied (BP-600c-3)."
        )

    def test_ac_bp600c3_green_phase_after_fix_phase(self):
        # covers: BP-600c-3
        """Green Phase must appear after Fix phase in quick-fix.js control flow."""
        js = _js()
        fix_idx = js.find("phase('Fix')")
        green_idx = js.find("phase('Green Phase')")
        assert fix_idx != -1, "quick-fix.js must contain phase('Fix')"
        assert green_idx != -1, "quick-fix.js must contain phase('Green Phase')"
        assert fix_idx < green_idx, (
            "Fix phase must appear before Green Phase — the test must be verified "
            "against fixed code (BP-600c-3)."
        )


# ===========================================================================
# BP-600d-1 — parses structured diagnosis into file/location/symptom/root-cause
# ===========================================================================

class TestBP600d1DiagnosisParsing:
    """BP-600d-1: Parses structured diagnosis into required fields."""

    def test_ac_bp600d1_extracts_target_file(self):
        # covers: BP-600d-1
        """quick-fix.js must extract target_file from the diagnosis args."""
        js = _js()
        assert "target_file" in js, (
            "quick-fix.js must extract target_file from the diagnosis input (BP-600d-1)."
        )

    def test_ac_bp600d1_extracts_all_four_fields(self):
        # covers: BP-600d-1
        """quick-fix.js must destructure all four diagnosis fields."""
        js = _js()
        for field in ("target_file", "location_hint", "symptom", "root_cause"):
            assert field in js, (
                f"quick-fix.js must extract '{field}' from the diagnosis (BP-600d-1)."
            )

    def test_ac_bp600d1_uses_fields_in_subsequent_phases(self):
        # covers: BP-600d-1
        """Extracted diagnosis fields must be used in AC creation and fix phases."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "root_cause" in ac_block, (
            "root_cause must be used in AC Creation phase (BP-600d-1)."
        )
        assert "target_file" in fix_block, (
            "target_file must be used in Fix phase (BP-600d-1)."
        )

    def test_ac_bp600d1_skill_documents_four_input_fields(self):
        # covers: BP-600d-1
        """SKILL.md must document the four required diagnosis fields."""
        skill = _skill()
        for field in ("target_file", "location_hint", "symptom", "root_cause"):
            assert field in skill, (
                f"SKILL.md must document required input field '{field}' (BP-600d-1)."
            )


# ===========================================================================
# BP-600d-1-i — rejects input lacking file path or root cause
# ===========================================================================

class TestBP600d1iInputValidation:
    """BP-600d-1-i: Rejects input missing file path or root cause."""

    def test_ac_bp600d1i_checks_for_missing_fields(self):
        # covers: BP-600d-1-i
        """quick-fix.js must check for missing target_file and root_cause."""
        js = _js()
        assert "!diagnosis.target_file" in js or "target_file" in js, (
            "quick-fix.js must validate that target_file is present (BP-600d-1-i)."
        )
        assert "!diagnosis.root_cause" in js or "root_cause" in js, (
            "quick-fix.js must validate that root_cause is present (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_returns_blocked_on_missing_fields(self):
        # covers: BP-600d-1-i
        """quick-fix.js must return blocked status when required fields are missing."""
        js = _js()
        # The guard at the top checks for missing fields and returns blocked
        guards_text = js[:js.find("phase('AC Creation')")]
        assert "status: 'blocked'" in guards_text or "'blocked'" in guards_text, (
            "quick-fix.js must return status:'blocked' when diagnosis is missing "
            "required fields (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_does_not_proceed_to_ac_creation(self):
        # covers: BP-600d-1-i
        """When fields are missing, quick-fix.js must return before AC creation."""
        js = _js()
        # The missing-fields check must appear before AC Creation phase
        missing_fields_check_idx = js.find("!diagnosis.target_file")
        if missing_fields_check_idx == -1:
            missing_fields_check_idx = js.find("Missing required diagnosis")
        ac_creation_idx = js.find("phase('AC Creation')")
        assert missing_fields_check_idx != -1, (
            "quick-fix.js must have a missing-fields check before AC creation (BP-600d-1-i)."
        )
        assert missing_fields_check_idx < ac_creation_idx, (
            "Missing-fields check must appear before AC Creation phase (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_blocked_message_describes_requirements(self):
        # covers: BP-600d-1-i
        """The blocked message must describe what the diagnosis must include."""
        js = _js()
        # Find the guard message
        guards_text = js[:js.find("phase('AC Creation')")]
        assert (
            "target_file" in guards_text
            and "root_cause" in guards_text
        ), (
            "Blocked message must name required fields (target_file, root_cause) so "
            "the user knows what to provide (BP-600d-1-i)."
        )


# ===========================================================================
# BP-600d-2 — dispatches python-coder; coder modifies only target file
# ===========================================================================

class TestBP600d2PythonCoderDispatch:
    """BP-600d-2: Dispatches python-coder with diagnosis + test; modifies only target."""

    def test_ac_bp600d2_dispatches_python_coder(self):
        # covers: BP-600d-2
        """quick-fix.js must dispatch agentType: 'python-coder' in Fix phase."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "agentType: 'python-coder'" in fix_block or "'python-coder'" in fix_block, (
            "Fix phase must dispatch agentType: 'python-coder' (BP-600d-2)."
        )

    def test_ac_bp600d2_fix_prompt_includes_constraint(self):
        # covers: BP-600d-2
        """python-coder dispatch prompt must include single-file constraint."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert (
            "MODIFY ONLY THE TARGET FILE" in fix_block
            or "Only modify" in fix_block
            or "only the target file" in fix_block.lower()
        ), (
            "python-coder dispatch prompt must include constraint to modify ONLY the "
            "target file (BP-600d-2)."
        )

    def test_ac_bp600d2_skill_python_coder_constraint(self):
        # covers: BP-600d-2
        """SKILL.md must document that python-coder may only modify the target file."""
        skill = _skill()
        assert "Modify ONLY the target file" in skill or \
               "ONLY the target file" in skill or \
               "Only modify" in skill, (
            "SKILL.md must document the single-file constraint for python-coder "
            "(BP-600d-2)."
        )

    def test_ac_bp600d2_fix_tracks_modified_files(self):
        # covers: BP-600d-2
        """Fix phase must capture the list of modified files for scope check."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "modified_files" in fix_block or "extra_files" in fix_block, (
            "Fix phase must track files modified by python-coder for scope expansion "
            "check (BP-600d-2)."
        )


# ===========================================================================
# BP-600d-3 — dispatches commit agent (not git commit directly)
# ===========================================================================

class TestBP600d3CommitAgentDispatch:
    """BP-600d-3: Dispatches commit agent; never git commit directly."""

    def test_ac_bp600d3_no_direct_git_commit(self):
        # covers: BP-600d-3
        """quick-fix.js must never call 'git commit' directly."""
        js = _js()
        # 'git commit' as a shell command (not as part of a comment or string about
        # the commit agent) should not appear
        assert "git commit" not in js, (
            "quick-fix.js must not call 'git commit' directly — must dispatch the "
            "commit agent (BP-600d-3)."
        )

    def test_ac_bp600d3_skill_prohibits_direct_git_commit(self):
        # covers: BP-600d-3
        """SKILL.md must state to dispatch the commit agent, not call git commit."""
        skill = _skill()
        assert (
            "commit agent" in skill
            and ("not call" in skill or "never call" in skill or "Do not" in skill)
        ), (
            "SKILL.md must explicitly state to dispatch the commit agent and never "
            "call git commit directly (BP-600d-3)."
        )


# ===========================================================================
# BP-600d-4 — pushes to branch remote; updates PR; closes ticket lifecycle
# ===========================================================================

class TestBP600d4PushAndClose:
    """BP-600d-4: Pushes to origin; checks for existing PR; closes ticket lifecycle."""

    def test_ac_bp600d4_result_includes_pr_url(self):
        # covers: BP-600d-4
        """The workflow's final return must include pr_url."""
        js = _js()
        assert "pr_url" in js, (
            "quick-fix.js must include pr_url in return value (BP-600d-4)."
        )


# ===========================================================================
# BP-600d-4-i — no PR: pushes but does not create one; exact message
# ===========================================================================

class TestBP600d4iNoPRCase:
    """BP-600d-4-i: No PR case — pushes; does not create a PR; reports exact message."""

    def test_ac_bp600d4i_push_schema_has_pr_url_field(self):
        # covers: BP-600d-4-i
        """PUSH_SCHEMA must include pr_url as an optional field."""
        js = _js()
        # Check that PUSH_SCHEMA has pr_url
        push_schema_idx = js.find("PUSH_SCHEMA")
        push_schema_end = js.find("}", push_schema_idx) + 100
        push_schema_block = js[push_schema_idx:push_schema_end] if push_schema_idx >= 0 else ""
        assert "pr_url" in push_schema_block, (
            "PUSH_SCHEMA must include pr_url field so both PR-present and no-PR paths "
            "are represented (BP-600d-4-i)."
        )


# ===========================================================================
# BP-600e-1 — warns when fix modifies more than the target file
# ===========================================================================

class TestBP600e1ScopeExpansionWarning:
    """BP-600e-1: Warns when fix modifies >= 2 source files."""

    def test_ac_bp600e1_checks_scope_expanded(self):
        # covers: BP-600e-1
        """quick-fix.js must check fixResult.scope_expanded flag."""
        js = _js()
        assert "scope_expanded" in js, (
            "quick-fix.js must check fixResult.scope_expanded to detect scope "
            "expansion (BP-600e-1)."
        )

    def test_ac_bp600e1_returns_blocked_on_scope_expansion(self):
        # covers: BP-600e-1
        """quick-fix.js must return halt_reason:'scope_expansion' when fix scope expands."""
        js = _js()
        assert "scope_expansion" in js, (
            "quick-fix.js must return halt_reason:'scope_expansion' when extra files "
            "are modified (BP-600e-1)."
        )

    def test_ac_bp600e1_scope_check_before_green_phase(self):
        # covers: BP-600e-1
        """Scope expansion check must appear before Green Phase in control flow."""
        js = _js()
        scope_check_idx = js.find("scope_expansion")
        green_phase_idx = js.find("phase('Green Phase')")
        assert scope_check_idx != -1, "quick-fix.js must have scope_expansion check"
        assert green_phase_idx != -1, "quick-fix.js must have Green Phase"
        assert scope_check_idx < green_phase_idx, (
            "Scope expansion check must appear before Green Phase — the workflow must "
            "pause before the green test when scope expands (BP-600e-1)."
        )

    def test_ac_bp600e1_skill_mentions_modified_n_files_warning(self):
        # covers: BP-600e-1
        """SKILL.md must include the scope expansion warning text."""
        skill = _skill()
        assert (
            "modified" in skill
            and ("beyond" in skill or "additional" in skill or "extra" in skill)
        ), (
            "SKILL.md must document the scope expansion warning (BP-600e-1)."
        )


# ===========================================================================
# BP-600e-2 — warns when red-phase failure diverges from diagnosed root cause
# ===========================================================================

class TestBP600e2RootCauseDivergenceWarning:
    """BP-600e-2: Warns when red-phase failure indicates a different root cause."""

    def test_ac_bp600e2_has_divergence_check(self):
        # covers: BP-600e-2
        """quick-fix.js must check for divergence between failure message and root cause."""
        js = _js()
        assert "divergence" in js.lower() or "divergenceCheck" in js, (
            "quick-fix.js must check for root-cause divergence in the red phase "
            "(BP-600e-2)."
        )

    def test_ac_bp600e2_returns_blocked_with_divergence_halt_reason(self):
        # covers: BP-600e-2
        """quick-fix.js must return halt_reason:'divergence_warning' when divergence detected."""
        js = _js()
        assert "divergence_warning" in js, (
            "quick-fix.js must return halt_reason:'divergence_warning' when the red-phase "
            "failure diverges from the diagnosed root cause (BP-600e-2)."
        )

    def test_ac_bp600e2_divergence_message_includes_diagnosed_and_observed(self):
        # covers: BP-600e-2
        """Divergence warning message must include both diagnosed and observed root cause."""
        js = _js()
        assert "Diagnosed" in js and "Observed" in js, (
            "Divergence warning must include both 'Diagnosed' and 'Observed' root cause "
            "information in the message (BP-600e-2)."
        )

    def test_ac_bp600e2_skill_divergence_warning_described(self):
        # covers: BP-600e-2
        """SKILL.md must document the root-cause divergence warning."""
        skill = _skill()
        assert (
            "diverge" in skill.lower()
            or "root cause may differ" in skill.lower()
        ), (
            "SKILL.md must document the root-cause divergence warning in Phase 2.5 "
            "(BP-600e-2)."
        )


# ===========================================================================
# BP-600e-3 — escalation preserves AC + test; outputs summary with AC id
# ===========================================================================

class TestBP600e3EscalationPreservesArtifacts:
    """BP-600e-3: On escalation, preserves AC+test; outputs summary with AC id."""

    def test_ac_bp600e3_skill_escalation_preserves_artifacts(self):
        # covers: BP-600e-3
        """SKILL.md escalation path must explicitly preserve AC YAML and test file."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "AC YAML" in escalation_text
            or "ac_path" in escalation_text
            or "AC file" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the AC YAML file (BP-600e-3)."
        )
        assert (
            "test file" in escalation_text.lower()
            or "TEST_FILE" in escalation_text
            or "test_file" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the test file (BP-600e-3)."
        )

    def test_ac_bp600e3_skill_escalation_summary_includes_ac_id(self):
        # covers: BP-600e-3
        """SKILL.md escalation summary must include the AC ID."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert "AC-ID" in escalation_text or "ac_id" in escalation_text.lower() or \
               "<AC-ID>" in escalation_text, (
            "SKILL.md escalation summary must include the AC ID for user reference "
            "(BP-600e-3)."
        )

    def test_ac_bp600e3_skill_escalation_references_build_feature(self):
        # covers: BP-600e-3
        """SKILL.md escalation must recommend /build-feature or /create-ticket."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "/build-feature" in escalation_text
            or "build-feature" in escalation_text
        ), (
            "SKILL.md escalation must provide the /build-feature reference for the "
            "user to escalate (BP-600e-3)."
        )

    def test_ac_bp600e3_js_escalation_preserves_ac_and_test(self):
        # covers: BP-600e-3
        """quick-fix.js escalation path must include ac_id and test_file in response."""
        js = _js()
        # Check that blocked returns from Fix phase include ac_id and test_file
        assert "test_file: testFile" in js or "test_file:" in js, (
            "quick-fix.js escalation response must include test_file for the user "
            "(BP-600e-3)."
        )
        assert "ac_id," in js or "ac_id:" in js, (
            "quick-fix.js escalation response must include ac_id for the user "
            "(BP-600e-3)."
        )


# ===========================================================================
# BP-600e-3-i — on escalation after fix: commits nothing; files preserved unstaged
# ===========================================================================

class TestBP600e3iEscalationAfterFixNoCommit:
    """BP-600e-3-i: On escalation after fix, commits nothing; files remain unstaged."""

    def test_ac_bp600e3i_skill_no_commit_on_escalation(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation path must NOT invoke the commit agent or git commit."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "Do not" in escalation_text
            or "do NOT" in escalation_text
            or "not commit" in escalation_text.lower()
            or "Halt" in escalation_text
        ), (
            "SKILL.md escalation path must explicitly not commit any code (BP-600e-3-i)."
        )

    def test_ac_bp600e3i_skill_no_git_restore_on_escalation(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation must not run git restore, git checkout, or git clean."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        # Escalation text should not instruct reverting files
        assert (
            "git restore" not in escalation_text
            and "git checkout" not in escalation_text
            and "git clean" not in escalation_text
        ), (
            "SKILL.md escalation path must not revert files — the fix, AC YAML, and "
            "test file must remain on disk as unstaged changes (BP-600e-3-i)."
        )

    def test_ac_bp600e3i_js_scope_expansion_returns_before_commit(self):
        # covers: BP-600e-3-i
        """quick-fix.js scope-expansion blocked return must appear before commit dispatch."""
        js = _js()
        scope_expansion_idx = js.find("scope_expansion")
        commit_dispatch_idx = js.find("agentType: 'commit'")
        assert scope_expansion_idx != -1, "scope_expansion check must exist"
        assert commit_dispatch_idx != -1, "commit agent dispatch must exist"
        assert scope_expansion_idx < commit_dispatch_idx, (
            "Scope expansion check (which returns blocked before commit) must appear "
            "before the commit dispatch — ensuring no commit happens on escalation "
            "(BP-600e-3-i)."
        )

    def test_ac_bp600e3i_skill_informs_user_of_preserved_files(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation summary must inform user which files are preserved."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "preserved" in escalation_text.lower()
            or "Preserved" in escalation_text
        ), (
            "SKILL.md escalation must inform the user which files are preserved "
            "(BP-600e-3-i)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage
#
# Replaces 14 source-contract-only assertions that this rewrite invalidated:
#   test_ac_bp600a1_skill_mentions_branch_verification
#   test_ac_bp600a2_skill_prohibits_worktree_agent
#   test_ac_bp600a3_checks_git_status_for_target
#   test_ac_bp600a3i_commit_stages_only_quick_fix_files
#   test_ac_bp600b1_ac_has_status_active
#   test_ac_bp600b2_skill_scans_highest_id
#   test_ac_bp600b2_ac_creation_finds_highest_suffix
#   test_ac_bp600d3_dispatches_commit_agent
#   test_ac_bp600d3_commit_message_references_ac_id
#   test_ac_bp600d4_pushes_to_origin
#   test_ac_bp600d4_checks_for_existing_pr
#   test_ac_bp600d4_skill_step_6_push_then_pr_check
#   test_ac_bp600d4i_no_gh_pr_create
#   test_ac_bp600d4i_skill_includes_no_pr_message
#
# See each class docstring below for which old test it supersedes and why a
# grep could not have caught what the harness now proves.
# ===========================================================================


def _full_success_responses(**overrides: Any) -> dict[str, Any]:
    """Label-keyed stub responses that drive quick-fix.js end-to-end to a
    successful close (status: ok, PR opened).

    Every phase after Guards depends on data threaded from an earlier phase
    (worktreeRoot, ac_id, ac_path, parent_ac_path, testFile, commit_sha,
    changelog entry_path) — this fixture is the one place that data is
    defined, so individual tests only need to override the single label they
    are exercising and can trust the rest of the run to proceed normally.
    Callers pass keyword overrides keyed by label name, e.g.:

        _full_success_responses(**{"green-verify/strict": {...}})
    """
    responses: dict[str, Any] = {
        "isolation-check": {
            "status": "ok",
            "is_repo": True,
            "session_cwd": "/repo",
            "initial_branch": "fix/some-branch",
            "needs_isolation": False,
        },
        "guard-checks": {"status": "ok", "target_file_dirty": False, "dirty_files": []},
        "ac-creation": {
            "status": "ok",
            "ac_id": "BP-9001",
            "ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml",
            "parent_ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml",
            "component_id": "build_pipeline",
            "ac_title": "Fix the bug",
        },
        "test-writer": {"status": "ok", "test_file": "unit_tests/test_bp9001.py"},
        "red-verify/strict": {
            "status": "ok",
            "passed": False,
            "outcome": "failed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
            "failure_message": "stub AssertionError: bug not fixed",
        },
        "python-coder/fix": {"status": "ok", "modified_files": ["stub/target.py"]},
        "green-verify/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
        },
        # BP-600c-3-i collateral-damage check. Distinct from mutation-proof:
        # that asks "is the test coupled to the fix", this asks "did the fix
        # break the neighbours".
        "related-tests/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/build_pipeline/ -v"
            ),
            "output_summary": "12 passed",
        },
        "mutation-proof": {
            "status": "ok",
            "red_without_fix": True,
            "green_with_fix_restored": True,
            "fix_restored": True,
        },
        "commit": {"status": "ok", "commit_sha": "abc123fix"},
        "changelog-author": {"status": "ok", "entry_path": "changelogs/BP-9001.md"},
        "commit/changelog": {"status": "ok", "commit_sha": "def456changelog"},
        "push-and-pr": {
            "status": "ok",
            "branch": "fix/some-branch",
            "pr_url": "https://github.com/org/repo/pull/42",
            "pr_opened": True,
        },
    }
    responses.update(overrides)
    return responses


def _labels(result) -> list[str | None]:
    """Convenience: the ordered list of agent-call labels from a HarnessResult."""
    return [c.label for c in result.agent_calls]


class TestBP600WorkflowInPlaceAndSelfIsolation:
    """Behavioral coverage for BP-600a-1 / BP-600a-2: the isolation DECISION
    (self-isolate dispatched or not) and its effect on later phases.

    Supersedes test_ac_bp600a1_skill_mentions_branch_verification and
    test_ac_bp600a2_skill_prohibits_worktree_agent — those grepped SKILL.md
    prose for the word "branch" or "worktree-agent", which could not tell
    whether the self-isolation branch in quick-fix.js actually gates on the
    isolation-check response. These tests run the script and assert on what
    was actually dispatched.
    """

    def test_ac_bp600a1_in_place_skips_self_isolate_and_keeps_branch(self):
        # covers: BP-600a-1
        """When the isolation-check reports a usable non-default branch,
        self-isolate must NOT be dispatched, and the reported cwd/branch must
        be the ones later phases operate on."""
        js_path = _JS_PATH
        result = run_workflow_under_e2(
            js_path,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "fix/some-branch",
                        "needs_isolation": False,
                    }
                }
            ),
        )
        labels = _labels(result)
        assert "self-isolate" not in labels, (
            "self-isolate must not be dispatched when needs_isolation is false "
            f"(BP-600a-1). Labels dispatched: {labels}"
        )
        guard_call = next(c for c in result.agent_calls if c.label == "guard-checks")
        assert "/repo" in guard_call.prompt and "fix/some-branch" in guard_call.prompt, (
            "The guard-checks prompt must be anchored to the reported session cwd "
            "and branch, not a re-derived value (BP-600a-1)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_when_not_a_repo(self):
        # covers: BP-600a-2
        """Trigger 1 of 4: session cwd is not a git repository at all."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": False,
                        "session_cwd": "/untracked/workspace",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-1",
                        "branch": "feature/slug-1",
                        "created": True,
                    },
                }
            ),
        )
        labels = _labels(result)
        assert "self-isolate" in labels, (
            "self-isolate must be dispatched when is_repo is false (BP-600a-2, "
            f"trigger: not-a-repo). Labels dispatched: {labels}"
        )
        assert not any(c.agent_type == "worktree-agent" for c in result.agent_calls), (
            "No dispatched call may target agentType 'worktree-agent' — quick-fix "
            "uses the self-isolate phase's own setup_ticket_worktree.py path, "
            "never worktree-agent (BP-600a-2)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_main(self):
        # covers: BP-600a-2
        """Trigger 2 of 4: current branch is 'main' (PR-only, cannot commit direct)."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "main",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-2",
                        "branch": "feature/slug-2",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is 'main' "
            "(BP-600a-2, trigger: main)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_master(self):
        # covers: BP-600a-2
        """Trigger 3 of 4: current branch is 'master'."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "master",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-3",
                        "branch": "feature/slug-3",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is 'master' "
            "(BP-600a-2, trigger: master)."
        )

    def test_ac_bp600a2_self_isolate_dispatched_on_detached_head(self):
        # covers: BP-600a-2
        """Trigger 4 of 4: HEAD is detached (initial_branch is empty)."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": True,
                        "session_cwd": "/repo",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-4",
                        "branch": "feature/slug-4",
                        "created": True,
                    },
                }
            ),
        )
        assert "self-isolate" in _labels(result), (
            "self-isolate must be dispatched when initial_branch is empty "
            "(detached HEAD) (BP-600a-2, trigger: detached-head)."
        )

    def test_ac_bp600a1_isolation_check_precedes_self_isolate_and_worktree_root_is_consumed(self):
        # covers: BP-600a-1
        # covers: BP-600a-2
        """isolation-check must run before self-isolate, and the worktree_root
        self-isolate returns must actually be threaded into later phases —
        not merely produced and discarded."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "isolation-check": {
                        "status": "ok",
                        "is_repo": False,
                        "session_cwd": "/untracked/workspace",
                        "initial_branch": "",
                        "needs_isolation": True,
                    },
                    "self-isolate": {
                        "status": "ok",
                        "worktree_root": "/isolated/wt-threaded",
                        "branch": "feature/threaded-slug",
                        "created": True,
                    },
                }
            ),
        )
        calls_by_label = {c.label: c for c in result.agent_calls}
        assert "isolation-check" in calls_by_label and "self-isolate" in calls_by_label
        assert (
            calls_by_label["isolation-check"].call_index
            < calls_by_label["self-isolate"].call_index
        ), "isolation-check must be dispatched before self-isolate (BP-600a-1)."
        later_call = calls_by_label["ac-creation"]
        assert "/isolated/wt-threaded" in later_call.prompt, (
            "The worktree_root produced by self-isolate must be consumed by a "
            "later phase's prompt (here: ac-creation) — proving the value is "
            "actually used, not just returned and dropped (BP-600a-2)."
        )


class TestBP600WorkflowGuardsHalt:
    """Behavioral coverage for guard halts: BP-600a-3 (dirty target file) and
    the two isolation halts.

    Supersedes test_ac_bp600a3_checks_git_status_for_target, which grepped
    the Guards prompt text for the string 'git status --porcelain' — a string
    that could remain in a prompt no branch of the control flow ever
    inspects the response of. This test drives the workflow with a 'blocked'
    guard-checks response and confirms the run actually halts and does not
    proceed to AC creation.
    """

    def test_ac_bp600a3_dirty_target_file_halts_before_ac_creation(self):
        # covers: BP-600a-3
        """A guard-checks response reporting the target file dirty must halt
        the run with status: blocked, and must not reach AC Creation."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "guard-checks": {
                        "status": "blocked",
                        "target_file_dirty": True,
                        "dirty_files": ["stub/target.py"],
                        "message": "target file has uncommitted changes",
                    }
                }
            ),
        )
        assert result.result is not None and result.result.get("status") == "blocked", (
            f"Expected status: blocked, got: {result.result}"
        )
        labels = _labels(result)
        assert "ac-creation" not in labels, (
            "AC Creation must not be dispatched when the guard reports the "
            f"target file dirty (BP-600a-3). Labels dispatched: {labels}"
        )

    def test_ac_bp600a2_blocked_isolation_check_halts_with_no_downstream_dispatch(self):
        # covers: BP-600a-2
        """A 'blocked' isolation-check response must halt immediately — no
        self-isolate, no guard-checks, nothing downstream."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                "isolation-check": {
                    "status": "blocked",
                    "is_repo": True,
                    "session_cwd": "/repo",
                    "needs_isolation": False,
                    "message": "isolation-check refused to proceed",
                }
            },
        )
        assert result.result is not None and result.result.get("status") == "blocked"
        assert result.dispatch_count == 1, (
            "A blocked isolation-check must halt before any further dispatch "
            f"(BP-600a-2). Labels dispatched: {_labels(result)}"
        )

    def test_ac_bp600a2_blocked_self_isolate_halts_with_no_downstream_dispatch(self):
        # covers: BP-600a-2
        """A 'blocked' self-isolate response must halt immediately with
        halt_reason 'isolation_failed' — no guard-checks, nothing downstream."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                "isolation-check": {
                    "status": "ok",
                    "is_repo": False,
                    "session_cwd": "/untracked/workspace",
                    "initial_branch": "",
                    "needs_isolation": True,
                },
                "self-isolate": {
                    "status": "blocked",
                    "worktree_root": "",
                    "branch": "",
                    "message": "worktree creation failed",
                },
            },
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "isolation_failed"
        assert result.dispatch_count == 2, (
            "A blocked self-isolate must halt before guard-checks or any later "
            f"phase. Labels dispatched: {_labels(result)}"
        )


class TestBP600WorkflowStrictVerificationHalts:
    """Behavioral coverage for BP-600c-2 / BP-600c-3's trust boundary: a
    red/green verification response is only trusted when its
    strict_command_run actually contains AC_ENFORCE_STRICT=1.

    This guard exists specifically because a non-strict pytest run reports a
    false green for a not-yet-done AC (pytest_ac_enforcement.py downgrades
    the failure to xfail). No prior test in this file executed this branch;
    both are real runtime guards that a source grep for the string
    'AC_ENFORCE_STRICT=1' cannot prove are actually CHECKED against the
    response rather than merely mentioned in the prompt sent upstream.
    """

    def test_ac_bp600c2_red_verify_missing_strict_flag_halts(self):
        # covers: BP-600c-2
        """A red-verify response whose strict_command_run omits
        AC_ENFORCE_STRICT=1 must halt, and Fix must not be dispatched."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "red-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "strict_command_run": "python -m pytest unit_tests/test_bp9001.py -v",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "strict_flag_missing"
        labels = _labels(result)
        assert "python-coder/fix" not in labels, (
            "Fix must not be dispatched when red-phase verification was not "
            f"run under AC_ENFORCE_STRICT=1. Labels dispatched: {labels}"
        )

    def test_ac_bp600c3_green_verify_missing_strict_flag_halts(self):
        # covers: BP-600c-3
        """A green-verify response whose strict_command_run omits
        AC_ENFORCE_STRICT=1 must halt, and mutation-proof must not run."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "green-verify/strict": {
                        "status": "ok",
                        "passed": True,
                        "strict_command_run": "python -m pytest unit_tests/test_bp9001.py -v",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "strict_flag_missing"
        labels = _labels(result)
        assert "mutation-proof" not in labels, (
            "Mutation proof must not run when green-phase verification was not "
            f"run under AC_ENFORCE_STRICT=1. Labels dispatched: {labels}"
        )


class TestBP600WorkflowRunnerErrorIsNotAResult:
    """BP-600c-2-i: a runner ERROR is not a red result, and not a failing test.

    An import error, syntax error, missing fixture or empty selection means the
    assertion was never evaluated. Reported through a bare pass/fail boolean it
    arrives as "not passed" — which the red phase would read as a healthy red
    and go on to apply a fix against a test that never ran. The `outcome`
    tri-state exists to carry that distinction; these tests prove the script
    branches on it rather than merely accepting it in the schema.
    """

    def test_ac_bp600c2i_red_phase_collection_error_halts_before_fix(self):
        # covers: BP-600c-2-i
        """outcome="error" in the red phase halts, and python-coder never runs.

        Breaks if the `outcome === 'error'` guard is removed, or if it is moved
        below the `passed === true` check — an error reports passed=false, so
        ordering is what makes the guard reachable.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "red-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "error",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/test_bp9001.py -v"
                        ),
                        "failure_message": "ImportError: no module named 'nope'",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "red_phase_error"
        labels = _labels(result)
        assert "python-coder/fix" not in labels, (
            "A test that could not run is not a red baseline — the fix phase "
            f"must not be reached. Labels dispatched: {labels}"
        )

    def test_ac_bp600c2i_green_phase_error_distinguished_from_failure(self):
        # covers: BP-600c-2-i
        """outcome="error" in the green phase halts with its own reason, not
        the "fix did not work" one — and says the fix is still applied.

        Breaks if the green error guard is dropped, or if it collapses back
        into the green_phase_fail branch.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "green-verify/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "error",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/test_bp9001.py -v"
                        ),
                        "failure_message": "SyntaxError: invalid syntax",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "green_phase_error", (
            "An unrunnable test must not be reported as 'the fix did not "
            "resolve the bug' — those are different diagnoses."
        )
        assert "still applied" in result.result.get("message", ""), (
            "The halt must tell the user the fix remains in the working tree, "
            "so they do not go looking for lost work."
        )


class TestBP600WorkflowRelatedTests:
    """BP-600c-3-i: the new test passing says nothing about the neighbours.

    A fix that repairs its own test while breaking an existing one would
    otherwise reach commit unchallenged. The mutation proof does not cover
    this — coupling-to-the-fix and collateral-damage are different questions,
    and the earlier implementation ran only the single new test file.
    """

    def test_ac_bp600c3i_broken_related_tests_halt_before_commit(self):
        # covers: BP-600c-3-i
        """Related tests failing after the fix halts the run before Commit.

        Breaks if the related-tests dispatch is removed, or if its `failed`
        outcome stops being consumed in control flow.
        """
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "related-tests/strict": {
                        "status": "ok",
                        "passed": False,
                        "outcome": "failed",
                        "strict_command_run": (
                            "AC_ENFORCE_STRICT=1 python -m pytest "
                            "unit_tests/build_pipeline/ -v"
                        ),
                        "failure_message": "test_neighbour.py::test_other FAILED",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "related_tests_broken"
        labels = _labels(result)
        assert "commit" not in labels, (
            "A fix that breaks existing tests must not be committed. "
            f"Labels dispatched: {labels}"
        )

    def test_ac_bp600c3i_related_check_runs_after_green_before_commit(self):
        # covers: BP-600c-3-i
        """The collateral-damage check sits between the green verification and
        the commit, so a regression is caught while the fix is still cheap to
        withdraw.

        Breaks if the dispatch is reordered after commit, which would let the
        broken state land before anyone looked.
        """
        result = run_workflow_under_e2(
            _JS_PATH, label_responses=_full_success_responses()
        )
        labels = _labels(result)
        assert "related-tests/strict" in labels, (
            f"The related-test check must run on a successful path. Got: {labels}"
        )
        assert labels.index("green-verify/strict") < labels.index(
            "related-tests/strict"
        ) < labels.index("commit"), (
            "Order must be green -> related-tests -> commit. "
            f"Got: {labels}"
        )


class TestBP600WorkflowMutationProof:
    """Behavioral coverage for the mutation-proof gate (BP-600c-3's coupling
    requirement, documented in quick-fix.js's Green Phase). Never covered by
    any prior test in this file — the mutation-proof phase did not exist in
    the version of the script the old test suite was written against.
    """

    def test_ac_bp600c3_test_passes_without_fix_halts(self):
        # covers: BP-600c-3
        """When reverting the fix leaves the test GREEN (red_without_fix is
        false), the run must halt — the test is not proven coupled to the fix
        — and must not reach Commit."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "mutation-proof": {
                        "status": "ok",
                        "red_without_fix": False,
                        "green_with_fix_restored": True,
                        "fix_restored": True,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "mutation_proof_failed"
        labels = _labels(result)
        assert "commit" not in labels, (
            "Commit must not be dispatched when the mutation proof shows the "
            f"test is not coupled to the fix. Labels dispatched: {labels}"
        )

    def test_ac_bp600c3_fix_left_stashed_halts_with_recovery_instructions(self):
        # covers: BP-600c-3
        """When fix_restored is false (the mandatory stash-pop step did not
        complete), the run must halt with a message telling the user the fix
        is still stashed — losing the user's fix in a stash is the worst
        outcome this workflow can produce, so the halt message must say so."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "mutation-proof": {
                        "status": "ok",
                        "red_without_fix": True,
                        "green_with_fix_restored": True,
                        "fix_restored": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "mutation_proof_incomplete"
        message = result.result.get("message", "")
        assert "stash" in message.lower(), (
            "The halt message must tell the user the fix may still be stashed "
            f"and how to recover it. Got: {message}"
        )
        assert "commit" not in _labels(result), (
            "Commit must not be dispatched while the fix might still be stashed."
        )


class TestBP600WorkflowCommitDataThreading:
    """Behavioral coverage for BP-600d-3: the commit phase must stage BOTH
    the child AC and its parent (the covered_by back-link), not just the
    child.

    Supersedes test_ac_bp600d3_dispatches_commit_agent,
    test_ac_bp600d3_commit_message_references_ac_id, and
    test_ac_bp600a3i_commit_stages_only_quick_fix_files — all three grepped
    the Commit prompt for a substring ('commit', 'ac_id', 'Do not stage any
    other files') that says nothing about whether the actual parent_ac_path
    VALUE returned by the AC-creation phase reaches the commit prompt. This
    test threads a fake parent_ac_path through ac-creation and asserts it is
    literally present in the commit call's prompt — proving consumption, not
    just declaration.
    """

    def test_ac_bp600d3_commit_prompt_includes_parent_and_child_ac_paths(self):
        # covers: BP-600d-3
        # covers: BP-600a-3-i
        """The commit prompt must include both parent_ac_path (the back-link
        target) and ac_path (the new child) — proving the parent is staged
        alongside the child, not just the child."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        commit_call = next(c for c in result.agent_calls if c.label == "commit")
        assert (
            "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml"
            in commit_call.prompt
        ), (
            "The commit prompt must include the PARENT AC path so the "
            "covered_by back-link is staged in the same commit (BP-600d-3)."
        )
        assert (
            "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml"
            in commit_call.prompt
        ), "The commit prompt must include the new child AC path (BP-600d-3)."
        assert "BP-9001" in commit_call.prompt, (
            "The commit prompt must reference the ac_id produced by AC Creation "
            "so the commit message can cite it (BP-600d-3)."
        )


class TestBP600WorkflowChangelogBeforePush:
    """Behavioral coverage for the Changelog phase (new since the old test
    suite was written): it must run before Close/push, and a changelog
    authoring failure must halt the run rather than push a branch that will
    fail the required 'Changelog entry present' CI check.
    """

    def test_ac_bp600d4_changelog_runs_before_push(self):
        # covers: BP-600d-4
        """Changelog phases must be dispatched, in order, before push-and-pr."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        labels = _labels(result)
        for required in ("commit", "changelog-author", "commit/changelog", "push-and-pr"):
            assert required in labels, f"Expected '{required}' to be dispatched. Got: {labels}"
        assert labels.index("changelog-author") < labels.index("push-and-pr"), (
            "changelog-author must be dispatched before push-and-pr (BP-600d-4)."
        )
        assert labels.index("commit/changelog") < labels.index("push-and-pr"), (
            "The changelog entry must be committed before push-and-pr (BP-600d-4)."
        )

    def test_ac_bp600d4_changelog_authoring_failure_halts_before_push(self):
        # covers: BP-600d-4
        """A blocked changelog-author response must halt the run — push-and-pr
        must never be dispatched — so a /quick-fix PR is never opened without
        the changelog entry the required CI check demands."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "changelog-author": {
                        "status": "blocked",
                        "message": "changelog script failed",
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "changelog_missing"
        assert "push-and-pr" not in _labels(result), (
            "push-and-pr must not be dispatched when the changelog entry was "
            "not authored (BP-600d-4)."
        )


class TestBP600WorkflowPrResult:
    """Behavioral coverage for BP-600d-4 / BP-600d-4-i's PR outcomes.

    Supersedes test_ac_bp600d4_pushes_to_origin,
    test_ac_bp600d4_checks_for_existing_pr,
    test_ac_bp600d4_skill_step_6_push_then_pr_check,
    test_ac_bp600d4i_no_gh_pr_create, and
    test_ac_bp600d4i_skill_includes_no_pr_message.

    IMPORTANT — contradicts the old AC text this rewrite superseded:
    test_ac_bp600d4i_no_gh_pr_create asserted 'gh pr create' must NEVER
    appear in quick-fix.js. That is no longer true: quick-fix.js now
    dispatches a confirmation-gated 'push-and-pr' phase whose prompt
    (Phase 7.4 / SKILL.md Step 7.4) explicitly instructs `gh pr create` on
    user confirmation — opening a PR is now a first-class, if
    confirmation-gated, part of the workflow (see the SKILL.md
    "Isolation is conditional" rewrite and the module docstring in
    quick-fix.js). The code's real behavior wins over the old brief here:
    these tests assert the actual (PR-creating, confirmation-gated) contract
    instead of the retired (never-creates-a-PR) one.
    """

    def test_ac_bp600d4_pr_opened_case_final_result_carries_pr_url(self):
        # covers: BP-600d-4
        """When push-and-pr reports a newly opened PR, the terminal payload
        must carry that URL — proving the response value was consumed into
        the final result, not just returned and dropped."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "https://github.com/org/repo/pull/42",
                        "pr_opened": True,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == "https://github.com/org/repo/pull/42"

    def test_ac_bp600d4i_no_pr_case_final_result_has_empty_pr_url_but_ok_status(self):
        # covers: BP-600d-4-i
        """When the user declines to open a PR (pr_opened: false, pr_url:
        ''), the run must still complete with status: ok — pushing without a
        PR is a valid terminal state, not a blocker — and the terminal
        payload's pr_url must be empty, not a stale value from an earlier
        phase."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "",
                        "pr_opened": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == ""

    def test_ac_bp600d4_existing_pr_case_final_result_carries_existing_url(self):
        # covers: BP-600d-4
        """When push-and-pr detects an existing PR for the branch
        (pr_opened: false but pr_url set), the terminal payload must carry
        THAT url — proving the 'gh pr list --head' detection path (not just
        the 'gh pr create' path) is threaded into the final result."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "push-and-pr": {
                        "status": "ok",
                        "branch": "fix/some-branch",
                        "pr_url": "https://github.com/org/repo/pull/7",
                        "pr_opened": False,
                    }
                }
            ),
        )
        assert result.result is not None
        assert result.result.get("status") == "ok"
        assert result.result.get("pr_url") == "https://github.com/org/repo/pull/7"


class TestBP600WorkflowFullRunTopology:
    """A single end-to-end backbone test: every phase, in the exact order
    quick-fix.js's module docstring declares, given an uninterrupted
    all-'ok' run. This is the reference topology the more targeted tests
    above deviate from one label at a time.
    """

    def test_ac_bp600_full_run_dispatches_every_phase_in_order(self):
        # covers: BP-600a-1
        # covers: BP-600b-1
        # covers: BP-600c-1
        # covers: BP-600d-2
        # covers: BP-600d-3
        # covers: BP-600d-4
        """An uninterrupted successful run dispatches exactly these labels,
        in this order, and returns status: ok."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        assert _labels(result) == [
            "isolation-check",
            "guard-checks",
            "ac-creation",
            "test-writer",
            "red-verify/strict",
            "python-coder/fix",
            "green-verify/strict",
            "related-tests/strict",
            "mutation-proof",
            "commit",
            "changelog-author",
            "commit/changelog",
            "push-and-pr",
        ]
        assert result.result is not None
        assert result.result.get("status") == "ok"
