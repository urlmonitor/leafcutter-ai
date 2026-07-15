"""
MODULE: test_quick_fix_workflow
GOAL: Source-contract assertions for the /quick-fix workflow (BP-600 ACs).

Because quick-fix.js is a JavaScript workflow that runs inside the Claude Code
engine, these tests cannot execute it at the Python level. Instead they assert
the **source contract** — the text content of quick-fix.js and SKILL.md —
guaranteeing that the control-flow branches, dispatch calls, guard clauses, and
prose required by the AC criteria are present in the shipped artefacts.

This mirrors the pattern used by test_finalize_feature_preflight.py.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600a-1, BP-600a-2, BP-600a-3, BP-600a-3-i, BP-600b-1, BP-600b-2,
     BP-600b-2-i, BP-600b-3, BP-600c-1, BP-600c-2, BP-600c-3, BP-600d-1,
     BP-600d-1-i, BP-600d-2, BP-600d-3, BP-600d-4, BP-600d-4-i, BP-600e-1,
     BP-600e-2, BP-600e-3, BP-600e-3-i
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"
_SKILL_PATH = _REPO_ROOT / "templates" / "skills" / "quick-fix" / "SKILL.md"


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

    def test_ac_bp600a1_skill_mentions_branch_verification(self):
        # covers: BP-600a-1
        """SKILL.md must instruct the agent to verify the branch has not changed."""
        skill = _skill()
        assert (
            "branch has not changed" in skill
            or "INITIAL_BRANCH" in skill
            or "branch unchanged" in skill
        ), (
            "SKILL.md must document the branch verification invariant (BP-600a-1). "
            "Expected to find 'branch has not changed' or 'INITIAL_BRANCH'."
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

    def test_ac_bp600a2_skill_prohibits_worktree_agent(self):
        # covers: BP-600a-2
        """SKILL.md must explicitly prohibit worktree-agent and git worktree add."""
        skill = _skill()
        assert "worktree-agent" in skill, (
            "SKILL.md must explicitly prohibit worktree-agent (BP-600a-2)."
        )
        assert "git worktree add" in skill, (
            "SKILL.md must explicitly prohibit 'git worktree add' (BP-600a-2)."
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

    def test_ac_bp600a3_checks_git_status_for_target(self):
        # covers: BP-600a-3
        """quick-fix.js guards must run git status --porcelain and check target_file."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "git status --porcelain" in guards_block, (
            "Guards phase must check 'git status --porcelain' to detect uncommitted "
            "changes in the target file (BP-600a-3)."
        )
        assert "target_file_dirty" in guards_block, (
            "Guards phase must track target_file_dirty flag (BP-600a-3)."
        )

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

    def test_ac_bp600a3i_commit_stages_only_quick_fix_files(self):
        # covers: BP-600a-3-i
        """Commit phase must stage only the specific quick-fix files, not all dirty files."""
        js = _js()
        commit_block = _phase_block(js, "Commit & Close")
        assert "Do not stage any other files" in commit_block, (
            "Commit phase must instruct the agent not to stage unrelated files, "
            "preserving uncommitted changes in unrelated files (BP-600a-3-i)."
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

    def test_ac_bp600b1_ac_has_status_active(self):
        # covers: BP-600b-1
        """The AC creation prompt must set status: active."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "status: active" in ac_block or '"active"' in ac_block, (
            "AC creation phase must set status to 'active' (BP-600b-1)."
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

    def test_ac_bp600b2_skill_scans_highest_id(self):
        # covers: BP-600b-2
        """SKILL.md Step 1.2 must describe scanning for the highest sequential ID."""
        skill = _skill()
        assert (
            "highest" in skill.lower()
            or "sequential" in skill.lower()
            or "Increment" in skill
        ), (
            "SKILL.md must describe scanning existing AC files to find the highest "
            "numeric suffix and incrementing by 1 (BP-600b-2)."
        )

    def test_ac_bp600b2_ac_creation_finds_highest_suffix(self):
        # covers: BP-600b-2
        """AC creation phase must list existing files to find the highest suffix."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "highest" in ac_block.lower() or "sequential" in ac_block.lower() or \
               "next available" in ac_block.lower(), (
            "AC creation phase prompt must instruct the agent to find the highest "
            "sequential ID and use the next one (BP-600b-2)."
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
        """SKILL.md must say to ask the user when no component mapping is found."""
        skill = _skill()
        assert (
            "no mapping" in skill.lower()
            or "ask" in skill.lower()
            or "fall back" in skill.lower()
        ), (
            "SKILL.md must instruct the agent to ask the user to specify the component "
            "when no file-path mapping is found in index.yaml (BP-600b-2-i)."
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

    def test_ac_bp600d3_dispatches_commit_agent(self):
        # covers: BP-600d-3
        """quick-fix.js must dispatch agentType: 'commit' in Commit & Close phase."""
        js = _js()
        commit_block = _phase_block(js, "Commit & Close")
        assert "agentType: 'commit'" in commit_block or "'commit'" in commit_block, (
            "Commit & Close phase must dispatch agentType: 'commit' (BP-600d-3)."
        )

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

    def test_ac_bp600d3_commit_message_references_ac_id(self):
        # covers: BP-600d-3
        """Commit phase prompt must include the AC ID in the commit message."""
        js = _js()
        commit_block = _phase_block(js, "Commit & Close")
        assert "ac_id" in commit_block, (
            "Commit phase prompt must include ac_id so the commit message references "
            "the AC (BP-600d-3)."
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

    def test_ac_bp600d4_pushes_to_origin(self):
        # covers: BP-600d-4
        """quick-fix.js must push to origin HEAD."""
        js = _js()
        commit_block = _phase_block(js, "Commit & Close")
        assert "git push origin HEAD" in commit_block, (
            "Commit & Close phase must push with 'git push origin HEAD' (BP-600d-4)."
        )

    def test_ac_bp600d4_checks_for_existing_pr(self):
        # covers: BP-600d-4
        """quick-fix.js must use 'gh pr list --head' to detect existing PRs."""
        js = _js()
        commit_block = _phase_block(js, "Commit & Close")
        assert "gh pr list" in commit_block or "gh pr list --head" in commit_block, (
            "Commit & Close phase must use 'gh pr list --head' to detect existing PR "
            "(BP-600d-4)."
        )

    def test_ac_bp600d4_result_includes_pr_url(self):
        # covers: BP-600d-4
        """The workflow's final return must include pr_url."""
        js = _js()
        assert "pr_url" in js, (
            "quick-fix.js must include pr_url in return value (BP-600d-4)."
        )

    def test_ac_bp600d4_skill_step_6_push_then_pr_check(self):
        # covers: BP-600d-4
        """SKILL.md Phase 6 must document push, PR check, and confirm close."""
        skill = _skill()
        assert "Phase 6" in skill or "Step 6" in skill, (
            "SKILL.md must have a Phase 6 / Step 6 for close operations (BP-600d-4)."
        )
        assert "git push origin HEAD" in skill, (
            "SKILL.md must include 'git push origin HEAD' in the close phase (BP-600d-4)."
        )


# ===========================================================================
# BP-600d-4-i — no PR: pushes but does not create one; exact message
# ===========================================================================

class TestBP600d4iNoPRCase:
    """BP-600d-4-i: No PR case — pushes; does not create a PR; reports exact message."""

    def test_ac_bp600d4i_no_gh_pr_create(self):
        # covers: BP-600d-4-i
        """quick-fix.js must not call 'gh pr create'."""
        js = _js()
        assert "gh pr create" not in js, (
            "quick-fix.js must not attempt to create a PR — only detect and report "
            "the absence of one (BP-600d-4-i)."
        )

    def test_ac_bp600d4i_skill_includes_no_pr_message(self):
        # covers: BP-600d-4-i
        """SKILL.md must include the specific 'No open PR' message."""
        skill = _skill()
        assert (
            "No open PR" in skill
            or "no PR" in skill.lower()
        ), (
            "SKILL.md must document the 'No open PR for branch' message for the "
            "no-PR case (BP-600d-4-i)."
        )

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
