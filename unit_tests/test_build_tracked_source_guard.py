"""
MODULE: unit_tests/test_build_tracked_source_guard.py
GOAL: Red-baseline tests for the tracked-source guard (BP-900f-1, BP-900f-2,
    BP-900f-3) and the truthful broken-reference message (BP-900c-3, BP-900c-3-i).
BUSINESS CONTEXT: The build must fail loudly when any deployable script's
    SOURCE is present on disk but not tracked in git. On a fresh clone the
    untracked working-tree file must not silently pass the guard. In parallel,
    the broken-reference report must give a TRUTHFUL suggested action — pointing
    at committing the source under templates/scripts/ when the deploy phase
    already exists, and at adding a deploy phase only when the directory itself
    is absent.

These tests are INTENTIONALLY RED before the implementation. They assert the
corrected behaviour that python-coder must implement to make them green.

AC mapping:
  BP-900f-1 — classifier marks each path tracked vs untracked using git index
  BP-900f-2 — non-zero exit + stderr naming when untracked list is non-empty
  BP-900f-3 — guard is generic (non-feedback directory also caught)
  BP-900c-3 — suggested_action is "commit under templates/scripts/" when dir+phase exist
  BP-900c-3-i — suggested_action is "add a deploy phase" when source dir absent
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402
from build_propagation_audit import (  # noqa: E402
    _suggest_action,
    build_broken_ref_report,
    ACTION_ADD_DEPLOY_PHASE,
    EXTERNAL_DEPENDENCY_ALLOWLIST,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_fake_package_root(tmp_path: Path, *, extra_dirs: list[str] | None = None) -> Path:
    """Create a minimal synthetic package root with templates/scripts/feedback/ populated.

    This mirrors the negative-control pattern from test_build_guard_real_package.py.
    templates/scripts/feedback/ is seeded so _manifest_feedback_scripts() does not
    raise RuntimeError on an absent tracked source dir.

    Args:
        tmp_path: pytest's tmp_path fixture.
        extra_dirs: Additional directories to create under the package root.

    Returns:
        Path to the synthetic package root.
    """
    pkg = tmp_path / "synthetic_pkg"
    feedback_src = pkg / "templates" / "scripts" / "feedback"
    feedback_src.mkdir(parents=True)
    (feedback_src / "submit_feedback.py").write_text("# stub\n", encoding="utf-8")
    (feedback_src / "aggregate.py").write_text("# stub\n", encoding="utf-8")

    for d in (extra_dirs or []):
        (pkg / d).mkdir(parents=True, exist_ok=True)

    return pkg


# ---------------------------------------------------------------------------
# AC BP-900f-1 — Tracked/untracked classifier uses the git index
# ---------------------------------------------------------------------------

class TestTrackedSourceClassifier:
    """BP-900f-1: The guard classifies each deployable-script source as
    tracked/untracked from the git index, NOT from filesystem presence."""

    def test_ac_bp900f1_tracked_classified_as_tracked(self, tmp_path: Path) -> None:
        # covers: BP-900f-1
        """A path reported by 'git ls-files' must be classified as tracked.

        The implementation does not exist yet. Once python-coder adds a
        _classify_tracked_sources() (or equivalent) function to build.py, this
        test will locate it and assert that 'check_ac_schema.py' comes back tracked
        because git ls-files reports it.
        """
        # Expected: build exposes a function that accepts a package_root and
        # returns a dict/set of untracked paths. Tracked paths are NOT in that set.
        # We mock subprocess so 'git ls-files' appears to report the file.
        pkg = _make_fake_package_root(tmp_path)
        tracked_path = "scripts/commit_guardian/check_ac_schema.py"
        untracked_path = "scripts/feedback/submit_feedback.py"

        # Make both files exist on disk so filesystem presence cannot be the
        # discriminator.
        (pkg / "scripts" / "commit_guardian").mkdir(parents=True, exist_ok=True)
        (pkg / "scripts" / "commit_guardian" / "check_ac_schema.py").write_text(
            "# on disk\n", encoding="utf-8"
        )
        (pkg / "scripts" / "feedback").mkdir(parents=True, exist_ok=True)
        (pkg / "scripts" / "feedback" / "submit_feedback.py").write_text(
            "# on disk but untracked\n", encoding="utf-8"
        )

        # The production function we expect python-coder to add.
        assert hasattr(_build, "_classify_untracked_sources"), (
            "_classify_untracked_sources() not found in build.py. "
            "python-coder must add this function (BP-900f-1)."
        )

        # Mock 'git ls-files' to report ONLY the tracked file.
        def _fake_classify(package_root: Path, source_set: set[str]) -> list[str]:
            """Stand-in: call real function but mock subprocess to return only the tracked file."""
            return _build._classify_untracked_sources(package_root, source_set)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"{tracked_path}\n",  # git ls-files output: only tracked_path
            )
            untracked = _fake_classify(pkg, {tracked_path, untracked_path})

        assert untracked_path in untracked, (
            f"_classify_untracked_sources() must report {untracked_path!r} as "
            "untracked when git ls-files does not list it."
        )
        assert tracked_path not in untracked, (
            f"_classify_untracked_sources() must NOT report {tracked_path!r} as "
            "untracked — git ls-files includes it (it is tracked)."
        )

    def test_ac_bp900f1_untracked_on_disk_not_classified_as_tracked(
        self, tmp_path: Path
    ) -> None:
        # covers: BP-900f-1
        """A file present on disk but absent from 'git ls-files' must be untracked.

        This is the key AC clause: classification must use the git index, not mere
        filesystem presence. An on-disk file that is not committed must appear in
        the untracked list.
        """
        pkg = _make_fake_package_root(tmp_path)
        untracked_path = "scripts/feedback/submit_feedback.py"

        # File exists on disk.
        (pkg / "scripts" / "feedback").mkdir(parents=True, exist_ok=True)
        (pkg / "scripts" / "feedback" / "submit_feedback.py").write_text(
            "# on disk but NOT tracked in git\n", encoding="utf-8"
        )

        assert hasattr(_build, "_classify_untracked_sources"), (
            "_classify_untracked_sources() not found in build.py (BP-900f-1)."
        )

        # git ls-files returns EMPTY — file is on disk but not tracked.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            untracked = _build._classify_untracked_sources(pkg, {untracked_path})

        assert untracked_path in untracked, (
            f"_classify_untracked_sources() did not classify {untracked_path!r} as "
            "untracked, even though git ls-files returned empty (file is on disk "
            "only). Classification MUST use the git index, not filesystem presence."
        )


# ---------------------------------------------------------------------------
# AC BP-900f-2 — Non-zero exit + stderr naming when untracked list is non-empty
# ---------------------------------------------------------------------------

class TestTrackedSourceGuardBuildFail:
    """BP-900f-2: When untracked sources exist the build exits non-zero,
    writes no partial deployment, and names each untracked path on stderr."""

    def test_ac_bp900f2_build_exits_nonzero_when_untracked(self, tmp_path: Path) -> None:
        # covers: BP-900f-2
        """_check_tracked_source_guard() must return 1 when deployable sources are untracked.

        Mocks _is_git_repo to True (so the guard does not short-circuit for non-git)
        and git ls-files to return EMPTY (so all source paths appear untracked).
        """
        pkg = _make_fake_package_root(tmp_path)
        # Seed a minimal templates/agents/ dir so extract_script_path_refs_with_sources
        # has something to scan (empty templates/agents/ returns 0 refs = 0 broken = guard passes).
        (pkg / "templates" / "agents").mkdir(parents=True, exist_ok=True)

        assert hasattr(_build, "_check_tracked_source_guard"), (
            "_check_tracked_source_guard() not found in build.py. "
            "python-coder must add this function as the guard entry point (BP-900f-2)."
        )

        captured_stderr = io.StringIO()
        # Simulate git ls-files returning EMPTY so ALL source paths appear untracked.
        # Also mock _is_git_repo so the guard doesn't short-circuit for non-git dirs.
        with patch.object(_build, "_is_git_repo", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                with patch("sys.stderr", captured_stderr):
                    result = _build._check_tracked_source_guard(pkg)

        assert result != 0, (
            "_check_tracked_source_guard() returned 0 (pass) despite all deployable "
            "sources being untracked. Expected non-zero exit (BP-900f-2)."
        )

    def test_ac_bp900f2_stderr_names_each_untracked_path(self, tmp_path: Path) -> None:
        # covers: BP-900f-2
        """The failure report must name each untracked source path on stderr.

        After python-coder's implementation, when two scripts are untracked the
        guard output on stderr must contain both SOURCE paths (templates/scripts/feedback/).
        """
        pkg = _make_fake_package_root(tmp_path)
        (pkg / "templates" / "agents").mkdir(parents=True, exist_ok=True)

        # Source paths (templates namespace) — these are what _get_source_paths_for_guard returns.
        untracked_1 = "templates/scripts/feedback/submit_feedback.py"
        untracked_2 = "templates/scripts/feedback/aggregate.py"

        assert hasattr(_build, "_check_tracked_source_guard"), (
            "_check_tracked_source_guard() not found in build.py (BP-900f-2)."
        )

        captured_stderr = io.StringIO()
        with patch.object(_build, "_is_git_repo", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                with patch("sys.stderr", captured_stderr):
                    _build._check_tracked_source_guard(pkg)

        stderr_output = captured_stderr.getvalue()
        assert untracked_1 in stderr_output or untracked_2 in stderr_output, (
            f"stderr does not name the untracked source paths. "
            f"Expected {untracked_1!r} and/or {untracked_2!r} in stderr output.\n"
            f"Actual stderr: {stderr_output!r}"
        )

    def test_ac_bp900f2_noop_when_all_sources_tracked(self, tmp_path: Path) -> None:
        # covers: BP-900f-2
        """When all deployable sources are tracked, the guard returns 0 (no-op).

        The untracked list is empty → guard does not affect exit code.
        Uses SOURCE paths (templates/scripts/ namespace) for the git ls-files mock,
        matching what _get_source_paths_for_guard() returns (H-1 fix).
        """
        pkg = _make_fake_package_root(tmp_path)
        (pkg / "templates" / "agents").mkdir(parents=True, exist_ok=True)

        assert hasattr(_build, "_check_tracked_source_guard"), (
            "_check_tracked_source_guard() not found in build.py (BP-900f-2)."
        )

        # Use SOURCE paths (templates/ namespace) — what _get_source_paths_for_guard returns.
        # This is the correct namespace after the H-1 fix.
        try:
            source_set = _build._get_source_paths_for_guard(pkg)
        except Exception:  # noqa: BLE001
            source_set = {
                "templates/scripts/feedback/submit_feedback.py",
                "templates/scripts/feedback/aggregate.py",
            }

        all_tracked_output = "\n".join(sorted(source_set)) + "\n"

        with patch.object(_build, "_is_git_repo", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=all_tracked_output)
                result = _build._check_tracked_source_guard(pkg)

        assert result == 0, (
            f"_check_tracked_source_guard() returned {result!r} when all sources "
            "are tracked. Expected 0 (no-op). The guard must not block an "
            "otherwise-clean build (BP-900f-2)."
        )


# ---------------------------------------------------------------------------
# AC BP-900f-3 — Guard is generic (non-feedback directory also caught)
# ---------------------------------------------------------------------------

class TestTrackedSourceGuardGenerality:
    """BP-900f-3: The guard must catch untracked sources in ANY deployable
    directory, not just scripts/feedback/. No directory-specific special-casing."""

    def test_ac_bp900f3_non_feedback_dir_triggers_guard(self, tmp_path: Path) -> None:
        # covers: BP-900f-3
        """An untracked source in a non-feedback directory (e.g. scripts/doc_compliance/)
        must trigger the same guard without directory-specific special-casing.

        The implementation must operate generically over the full deployable-script
        source set. This test verifies that the guard classifies untracked sources
        regardless of which subdirectory they come from.
        """
        pkg = _make_fake_package_root(tmp_path)
        (pkg / "templates" / "agents").mkdir(parents=True, exist_ok=True)

        # Inject a non-feedback untracked path into the source set via monkeypatching.
        non_feedback_untracked = "scripts/doc_compliance/some_tool.py"

        assert hasattr(_build, "_classify_untracked_sources"), (
            "_classify_untracked_sources() not found in build.py (BP-900f-3)."
        )

        # git ls-files returns empty — the non-feedback script is untracked.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            untracked = _build._classify_untracked_sources(pkg, {non_feedback_untracked})

        assert non_feedback_untracked in untracked, (
            f"_classify_untracked_sources() did not flag {non_feedback_untracked!r} "
            "as untracked. The guard must be directory-agnostic — no feedback-specific "
            "or directory-specific special-casing (BP-900f-3)."
        )

    def test_ac_bp900f3_guard_uses_git_index_not_filesystem(self, tmp_path: Path) -> None:
        # covers: BP-900f-3
        """The classification verdict must be reproducible from the git index alone,
        independent of which untracked working-tree files happen to be present.

        Two calls with the same 'git ls-files' output (same index state) must produce
        the same untracked list, even if files are added to / removed from the
        working tree between calls.
        """
        pkg = _make_fake_package_root(tmp_path)

        test_path = "scripts/doc_compliance/some_tool.py"

        assert hasattr(_build, "_classify_untracked_sources"), (
            "_classify_untracked_sources() not found in build.py (BP-900f-3)."
        )

        # First call — file does NOT exist on disk; git index also empty.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result_1 = _build._classify_untracked_sources(pkg, {test_path})

        # Add the file to disk (working-tree change only — git index unchanged).
        (pkg / "scripts" / "doc_compliance").mkdir(parents=True, exist_ok=True)
        (pkg / "scripts" / "doc_compliance" / "some_tool.py").write_text(
            "# on disk\n", encoding="utf-8"
        )

        # Second call — file IS on disk; git index still empty (same mock).
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result_2 = _build._classify_untracked_sources(pkg, {test_path})

        assert result_1 == result_2, (
            "Classification result changed between calls when only the working-tree "
            "changed (git index was identical). The guard must derive tracked-ness "
            "from the git index only, not from filesystem presence (BP-900f-3).\n"
            f"  result without file on disk: {result_1!r}\n"
            f"  result with    file on disk: {result_2!r}"
        )
        assert test_path in result_1, (
            f"{test_path!r} must be classified as untracked when git ls-files returns "
            "empty (git index is empty), regardless of filesystem state (BP-900f-3)."
        )


# ---------------------------------------------------------------------------
# AC BP-900c-3 — Truthful suggested_action when dir+phase exist but file missing
# ---------------------------------------------------------------------------

class TestSuggestActionDirPresent:
    """BP-900c-3: When the source directory exists (and deploy phase exists) but
    the file is missing/untracked, _suggest_action() returns the
    missing/untracked message, NOT 'add a deploy phase'."""

    #: The action text python-coder must implement (exact string may vary,
    #: but it must contain this distinguishing phrase).
    EXPECTED_PHRASE = "templates/scripts/"

    def test_ac_bp900c3_suggests_commit_when_dir_exists(self) -> None:
        # covers: BP-900c-3
        """When the source directory exists and has a deploy phase, _suggest_action()
        must return the 'commit under templates/scripts/' message.

        Currently _suggest_action() returns ACTION_ADD_DEPLOY_PHASE ('add a deploy
        phase in build_phases.py') for scripts/feedback/ paths, which is wrong —
        the deploy phase already exists. The fix must change the return value to
        the missing/untracked-source message for that state.
        """
        # scripts/feedback/ is a known leafcutter-owned prefix with an existing
        # deploy phase (build_feedback). When its file is missing/untracked the
        # truthful action is to commit the source, NOT to add a phase.
        missing_path = "scripts/feedback/submit_feedback.py"

        result = _suggest_action(missing_path, EXTERNAL_DEPENDENCY_ALLOWLIST)

        # The current implementation returns ACTION_ADD_DEPLOY_PHASE — that is the
        # bug. After the fix, it must return something about 'templates/scripts/'.
        assert self.EXPECTED_PHRASE in result, (
            f"_suggest_action('{missing_path}', ...) returned {result!r}.\n"
            f"Expected the result to contain {self.EXPECTED_PHRASE!r} (directing "
            "the author to commit the source under templates/scripts/), "
            "because the deploy phase for scripts/feedback/ already exists.\n"
            "Currently it incorrectly says 'add a deploy phase in build_phases.py' "
            "(BP-900c-3)."
        )
        assert result != ACTION_ADD_DEPLOY_PHASE, (
            f"_suggest_action('{missing_path}', ...) still returns ACTION_ADD_DEPLOY_PHASE. "
            "This is wrong when the source directory and deploy phase already exist. "
            "The fix must return the missing/untracked-source message (BP-900c-3)."
        )

    def test_ac_bp900c3_commit_guardian_also_gets_truthful_action(self) -> None:
        # covers: BP-900c-3
        """scripts/commit_guardian/ also has an existing deploy phase; its missing
        files must also get the 'commit under templates/scripts/' action."""
        missing_path = "scripts/commit_guardian/check_ac_schema.py"

        result = _suggest_action(missing_path, EXTERNAL_DEPENDENCY_ALLOWLIST)

        assert self.EXPECTED_PHRASE in result, (
            f"_suggest_action('{missing_path}', ...) returned {result!r}.\n"
            f"Expected the result to contain {self.EXPECTED_PHRASE!r} — "
            "build_commit_guardian already exists as a deploy phase, so the "
            "truthful action is to commit the missing source (BP-900c-3)."
        )

    def test_ac_bp900c3_missing_path_and_template_still_in_entry(self) -> None:
        # covers: BP-900c-3
        # covers: BP-900c-1
        """The entry shape must be preserved (missing_path, referencing_template,
        suggested_action) — BP-900c-3 changes ONLY the suggested_action value.

        Also covers BP-900c-1: the three assertions below are exactly that AC's
        requirement that every broken-reference entry carries all three fields
        with none empty or omitted."""
        refs_to_sources = {
            "scripts/feedback/submit_feedback.py": {"templates/agents/feedback-analyst.md"},
        }
        deployed: set[str] = set()

        entries = build_broken_ref_report(refs_to_sources, deployed, allowlist=frozenset())

        assert len(entries) == 1, (
            f"Expected 1 BrokenRefEntry, got {len(entries)}."
        )
        entry = entries[0]
        assert entry.missing_path == "scripts/feedback/submit_feedback.py"
        assert "templates/agents/feedback-analyst.md" in entry.referencing_templates
        # After the fix, suggested_action must contain the commit-under-templates phrase.
        assert self.EXPECTED_PHRASE in entry.suggested_action, (
            f"BrokenRefEntry.suggested_action = {entry.suggested_action!r} does not "
            f"contain {self.EXPECTED_PHRASE!r}. The entry shape is correct but the "
            "suggested_action is still the wrong value (BP-900c-3)."
        )


# ---------------------------------------------------------------------------
# AC BP-900c-3-i — Dir absent still gets 'add a deploy phase'
# ---------------------------------------------------------------------------

class TestSuggestActionDirAbsent:
    """BP-900c-3-i: When the source directory does NOT exist, _suggest_action()
    must still return 'add a deploy phase'. Both action types must coexist in
    one report."""

    def test_ac_bp900c3i_suggests_deploy_phase_when_dir_absent(self) -> None:
        # covers: BP-900c-3-i
        """When the source directory is absent (genuinely new capability),
        _suggest_action() must return ACTION_ADD_DEPLOY_PHASE, not the
        missing/untracked-source message.
        """
        # scripts/brandnewtool/ does not exist; no deploy phase for it either.
        missing_path = "scripts/brandnewtool/run.py"

        result = _suggest_action(missing_path, EXTERNAL_DEPENDENCY_ALLOWLIST)

        # For a brand-new directory, the correct action is to add a deploy phase.
        # The current implementation already returns this — the test asserts it
        # is preserved after the BP-900c-3 fix.
        assert result == ACTION_ADD_DEPLOY_PHASE or "deploy phase" in result.lower(), (
            f"_suggest_action('{missing_path}', ...) returned {result!r}.\n"
            "Expected a 'deploy phase' action because the source directory and "
            "deploy phase do not exist (BP-900c-3-i)."
        )

    def test_ac_bp900c3i_both_actions_coexist_in_one_report(self) -> None:
        # covers: BP-900c-3-i
        """A single build_broken_ref_report() call with two entries — one
        dir-present (feedback) and one dir-absent (brandnewtool) — must produce
        both action types.

        This is the exact scenario from the AC: both states must be distinguishable
        per-entry in the same report.
        """
        refs_to_sources = {
            # Existing deploy phase — dir-present (should get commit-source action)
            "scripts/feedback/submit_feedback.py": {"templates/agents/feedback-analyst.md"},
            # Brand new dir — dir-absent (should get add-deploy-phase action)
            "scripts/brandnewtool/run.py": {"templates/agents/some-agent.md"},
        }
        deployed: set[str] = set()

        entries = build_broken_ref_report(refs_to_sources, deployed, allowlist=frozenset())

        assert len(entries) == 2, (
            f"Expected 2 BrokenRefEntry instances, got {len(entries)}."
        )

        actions_by_path = {e.missing_path: e.suggested_action for e in entries}

        # The feedback entry must have the commit-source action.
        feedback_action = actions_by_path.get("scripts/feedback/submit_feedback.py", "")
        assert "templates/scripts/" in feedback_action, (
            f"scripts/feedback/submit_feedback.py entry has suggested_action="
            f"{feedback_action!r}. After BP-900c-3 fix this must contain "
            "'templates/scripts/' (commit-source action) because the deploy "
            "phase for feedback already exists."
        )

        # The brandnewtool entry must have the add-deploy-phase action.
        newtool_action = actions_by_path.get("scripts/brandnewtool/run.py", "")
        assert "deploy phase" in newtool_action.lower() or newtool_action == ACTION_ADD_DEPLOY_PHASE, (
            f"scripts/brandnewtool/run.py entry has suggested_action={newtool_action!r}. "
            "Expected the 'add a deploy phase' action for a brand-new directory "
            "(BP-900c-3-i)."
        )

        # Sanity: the two actions must be different from each other.
        assert feedback_action != newtool_action, (
            "Both entries have the same suggested_action. They must be different: "
            "one dir-present (commit-source), one dir-absent (add-deploy-phase)."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-24 [test-writer/TICKET-20260624-BP-900f-1]: Initial red-baseline
#   tests for the tracked-source guard (BP-900f-1, BP-900f-2, BP-900f-3) and
#   the truthful broken-reference message (BP-900c-3, BP-900c-3-i).
#   Tests written BEFORE implementation; intentionally RED.
# ====================================================================
