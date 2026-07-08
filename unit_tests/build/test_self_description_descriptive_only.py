"""
MODULE: test_self_description_descriptive_only
GOAL: Test suite for descriptive_only support in self-description validation
    (TICKET-20260708-BP-1300a-descriptive-skills.md) and the M-1 follow-on fix
    that extends the same exemption to check_skills_invoked_xref in
    scripts/registry_validator.py.

    Tests the four Gherkin scenarios from the ticket body. The suite must be RED
    (non-zero exit) until python-coder implements:
      1. descriptive_only: true support in validate_agent_self_description()
      2. run-tests (python-coder) + direct-write (documentation-expert) entries
         marked descriptive_only: true in config/agent_registry.json

RED/GREEN mapping at time of authoring
----------------------------------------
test_ac_bp1300a_1_unmarked_unresolvable_fails
    REGRESSION GUARD — asserts PRESERVED existing behavior (already green).
    Unmarked unresolvable skill_ids must still fail after the fix lands.

test_ac_bp1300a_1i_descriptive_only_passes
    RED — descriptive_only key not yet read by validator → still flags as error.

test_ac_scenario3_python_coder_has_run_tests_marked
    RED — 'run-tests' entry absent from python-coder's skills_invoked in registry.

test_ac_scenario3_documentation_expert_has_direct_write_marked
    RED — 'direct-write' entry absent from documentation-expert's skills_invoked.

test_ac_scenario3_real_validation_reports_zero_errors
    GUARD — runs the real validator; passes today (no unresolvable IDs currently),
    becomes a regression blocker once python-coder adds the new entries without
    descriptive_only: true (that intermediate state would make this RED).
    Note: may be under-specified as a standalone red-now test; tests 3a/3b are
    the primary RED signals for scenario 3.

test_ac_bp1300a_1ii_verdict_independent_of_stale_deployed_artifacts
    RED — with descriptive_only unsupported, the verdict changes when a stale
    .claude/skills/ dir is added (current code resolves it via in_project check),
    so the assertion that both error counts equal 0 fails.

Validator seam for python-coder
---------------------------------
Function: ``validate_agent_self_description`` in scripts/build_phases.py
Location: inside the ``for inv in skills_invoked:`` loop (~line 1742).

AFTER the existing ``if not skill_id: continue`` guard, ADD:

    if inv.get("descriptive_only") is True:
        continue  # Intentional inline capability — no skill dir required

This causes the validator to skip resolution for entries explicitly marked as
documenting inline capabilities (no deployed skill dir by design). Unmarked
unresolvable entries continue to hard-fail in error mode.

Registry fix for python-coder
--------------------------------
In config/agent_registry.json:

  python-coder.skills_invoked — ADD:
      {"skill_id": "run-tests", "mode": "conditional", "descriptive_only": true}

  documentation-expert.skills_invoked — ADD:
      {"skill_id": "direct-write", "mode": "conditional", "descriptive_only": true}

Both entries document INLINE capabilities (the agents perform the work directly
without loading a deployed skill dir), hence no templates/skills/<id>/ directory
exists by design. The descriptive_only: true marker tells the validator this is
intentional, not a dangling pointer.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Lazy import — validator exists but may not yet support descriptive_only
# ---------------------------------------------------------------------------
try:
    from build_phases import validate_agent_self_description as _VALIDATOR
except ImportError:
    _VALIDATOR = None  # type: ignore[assignment]


class _ValidatorNotImportable(ImportError):
    """Raised when validate_agent_self_description cannot be imported from build_phases."""

    def __init__(self) -> None:
        super().__init__(
            "validate_agent_self_description not importable from build_phases. "
            "Ensure scripts/ is in sys.path and build_phases.py exists."
        )


def _require_validator():
    """Return validate_agent_self_description or raise _ValidatorNotImportable."""
    if _VALIDATOR is None:
        raise _ValidatorNotImportable()
    return _VALIDATOR


# ---------------------------------------------------------------------------
# Fixture helpers (shared across all test classes)
# ---------------------------------------------------------------------------

# Minimal valid agent frontmatter (all 5 required fields populated)
_FULL_FRONTMATTER: dict = {
    "name": "fake-agent",
    "behavioral_patterns": [
        {
            "name": "Stop-and-Ask",
            "trigger": "ambiguity detected",
            "behavior": "ask user before proceeding",
            "related_agent": None,
        }
    ],
    "pre_flight_reads": ["ticket body"],
    "inputs": [
        {"name": "ticket_path", "type": "path", "description": "Path to the ticket file"}
    ],
    "outputs": [
        {"name": "Sign-off comment", "type": "comment", "description": "status: ok | blocker"}
    ],
    "mutates": [
        {
            "name": "Ticket frontmatter",
            "type": "file",
            "description": "agents.fake-agent: signed_off",
        }
    ],
}


def _make_agent_md(frontmatter: dict) -> str:
    """Render frontmatter dict to a YAML-fenced agent template string."""
    import yaml  # type: ignore[import]

    return "---\n" + yaml.dump(frontmatter, default_flow_style=False) + "---\n\nYou are a test agent.\n"


def _write_agent_template(tmp_dir: Path, agent_name: str, frontmatter: dict) -> None:
    """Write agent <name>.md into tmp_dir/templates/agents/."""
    agents_dir = tmp_dir / "templates" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{agent_name}.md").write_text(_make_agent_md(frontmatter))


def _write_registry(tmp_dir: Path, entries: list[dict]) -> None:
    """Write minimal agent_registry.json with error enforcement into tmp_dir/config/."""
    config_dir = tmp_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    registry = {
        "self_description_enforcement": "error",
        "agents": entries,
    }
    (config_dir / "agent_registry.json").write_text(json.dumps(registry, indent=2))


def _write_skill_template(tmp_dir: Path, skill_id: str) -> None:
    """Create a minimal templates/skills/<id>/SKILL.md so the validator resolves the skill."""
    skill_dir = tmp_dir / "templates" / "skills" / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\n---\n\n# {skill_id}\n"
    )


def _write_stale_deployed_skill(tmp_dir: Path, skill_id: str) -> None:
    """Create a stale .claude/skills/<id>/SKILL.md — simulates a deployed artifact.

    The validator currently resolves via in_project check against this dir.
    After the descriptive_only fix, this dir must NOT change the verdict for
    descriptive_only entries (the fix must check the marker, not the deployed tree).
    """
    stale_dir = tmp_dir / ".claude" / "skills" / skill_id
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\n---\n\nStale deployed artifact — must not affect verdict.\n"
    )


# ---------------------------------------------------------------------------
# Scenario BP-1300a-1 — Regression guard (should already pass)
# ---------------------------------------------------------------------------


class TestUnmarkedUnresolvableFails:
    """BP-1300a-1: UNMARKED unresolvable skill_id fails the build in error mode."""

    def test_ac_bp1300a_1_unmarked_unresolvable_fails(self, tmp_path: Path) -> None:
        # covers: UNKNOWN
        """Regression guard: an UNMARKED unresolvable skill_id must still fail.

        Given a skills_invoked entry with no 'descriptive_only' marker whose
        skill_id resolves to no templates/skills/<id>/ directory,
        When validate_agent_self_description runs in error mode,
        Then error_count > 0 (build fails),
        And the error names the offending agent and skill_id.

        Status: REGRESSION GUARD — this asserts existing behaviour that the
        descriptive_only fix must NOT remove. If this test fails after the fix,
        the fix is over-broad (it skips resolution for entries it should not skip).

        What must remain unchanged after python-coder's fix:
            The existing resolution block:
                in_package = (package_skills_dir / skill_id).exists()
                in_project = (project_skills_dir / skill_id).exists()
                if not in_package and not in_project:
                    problems.append(...)
            must still fire for entries that lack 'descriptive_only: true'.
        """
        validator = _require_validator()
        agent_name = "fake-agent"
        fm = dict(_FULL_FRONTMATTER)
        fm["name"] = agent_name

        registry_entry = {
            "id": agent_name,
            "category": "implementation",
            "skills_invoked": [
                # Unresolvable skill_id, NO descriptive_only marker — must be flagged
                {"skill_id": "definitely-nonexistent-skill-xyz", "mode": "always"},
            ],
            "knowledge_channels": [{"channel": 1, "source": "template description"}],
        }

        _write_agent_template(tmp_path, agent_name, fm)
        _write_registry(tmp_path, [registry_entry])
        # Intentionally no templates/skills/definitely-nonexistent-skill-xyz/ dir

        error_count, _warning_count = validator(
            target_root=tmp_path,
            config={},
            dry_run=False,
            enforcement_level="error",
        )

        assert error_count > 0, (
            "Expected validator to flag unmarked unresolvable skill_id "
            "'definitely-nonexistent-skill-xyz' with error_count > 0, "
            f"but got error_count={error_count}. "
            "The guardrail for genuine dangling skill pointers must remain active."
        )


# ---------------------------------------------------------------------------
# Scenario BP-1300a-1-i — RED: descriptive_only not yet supported
# ---------------------------------------------------------------------------


class TestDescriptiveOnlyPasses:
    """BP-1300a-1-i: A descriptive_only: true entry with no skill dir must NOT be flagged."""

    def test_ac_bp1300a_1i_descriptive_only_passes(self, tmp_path: Path) -> None:
        # covers: UNKNOWN
        """Given a skills_invoked entry with descriptive_only: true and no skill dir,
        When validate_agent_self_description runs in error mode,
        Then error_count == 0 (build proceeds — the entry documents inline capability).

        RED now: the validator does not read the 'descriptive_only' key → still
        flags 'inline-capability' as unresolvable → AssertionError (error_count > 0).

        What python-coder must implement to make this green:
            In validate_agent_self_description (scripts/build_phases.py),
            inside the ``for inv in skills_invoked:`` loop, AFTER the existing
            ``if not skill_id: continue`` guard, ADD:

                if inv.get("descriptive_only") is True:
                    continue  # Intentional inline capability — no skill dir required

            The check is a strict identity test (``is True``), not truthiness, to
            avoid accidental skipping when 'descriptive_only' holds a string or 1.
        """
        validator = _require_validator()
        agent_name = "fake-agent"
        fm = dict(_FULL_FRONTMATTER)
        fm["name"] = agent_name

        registry_entry = {
            "id": agent_name,
            "category": "implementation",
            "skills_invoked": [
                # descriptive_only: true — no skill dir expected; must NOT produce an error
                {
                    "skill_id": "inline-capability",
                    "mode": "conditional",
                    "descriptive_only": True,
                },
            ],
            "knowledge_channels": [{"channel": 1, "source": "template description"}],
        }

        _write_agent_template(tmp_path, agent_name, fm)
        _write_registry(tmp_path, [registry_entry])
        # Intentionally: NO templates/skills/inline-capability/ dir (not needed for descriptive entries)

        error_count, _warning_count = validator(
            target_root=tmp_path,
            config={},
            dry_run=False,
            enforcement_level="error",
        )

        assert error_count == 0, (
            "Expected validator NOT to flag descriptive_only: true entry 'inline-capability', "
            f"but got error_count={error_count}. "
            "python-coder must add the ``if inv.get('descriptive_only') is True: continue`` "
            "guard inside the skills_invoked resolution loop in validate_agent_self_description."
        )


# ---------------------------------------------------------------------------
# Scenario 3 — Real registry entries: RED (entries missing in registry)
# ---------------------------------------------------------------------------


class TestRealRegistryEntriesMarked:
    """Scenario 3: real config/agent_registry.json must have run-tests + direct-write marked."""

    def test_ac_scenario3_python_coder_has_run_tests_marked(self) -> None:
        # covers: UNKNOWN
        """Assert python-coder has a skills_invoked entry for 'run-tests' with descriptive_only: true.

        RED now: the 'run-tests' entry is absent from python-coder's skills_invoked
        in config/agent_registry.json.

        What python-coder must implement to make this green:
            In config/agent_registry.json, in the python-coder entry's skills_invoked,
            ADD the following object (INF-600d-1 compliance — keep the entry, mark it):
                {
                    "skill_id": "run-tests",
                    "mode": "conditional",
                    "descriptive_only": true
                }
        """
        registry_path = _REPO_ROOT / "config" / "agent_registry.json"
        assert registry_path.is_file(), f"Registry not found at {registry_path}"

        registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
        agents_by_id = {
            a["id"]: a
            for a in registry_data.get("agents", [])
            if isinstance(a, dict) and "id" in a
        }

        python_coder = agents_by_id.get("python-coder")
        assert python_coder is not None, (
            "python-coder entry not found in config/agent_registry.json"
        )

        skills_invoked = python_coder.get("skills_invoked") or []
        run_tests_entries = [
            inv
            for inv in skills_invoked
            if isinstance(inv, dict) and inv.get("skill_id") == "run-tests"
        ]

        assert len(run_tests_entries) >= 1, (
            "python-coder skills_invoked must contain a 'run-tests' entry "
            "(required by INF-600d-1 to document the inline test-running capability). "
            "Add: {\"skill_id\": \"run-tests\", \"mode\": \"conditional\", "
            "\"descriptive_only\": true} to python-coder.skills_invoked."
        )
        assert run_tests_entries[0].get("descriptive_only") is True, (
            "python-coder's 'run-tests' skills_invoked entry must have descriptive_only: true. "
            f"Current entry: {run_tests_entries[0]}. "
            "Set descriptive_only: true so the validator skips skill-dir resolution for it."
        )

    def test_ac_scenario3_documentation_expert_has_direct_write_marked(self) -> None:
        # covers: UNKNOWN
        """Assert documentation-expert has a skills_invoked entry for 'direct-write' with descriptive_only: true.

        RED now: 'direct-write' appears only as a behavioral_pattern (pattern_id),
        not as a skills_invoked entry, in documentation-expert's registry entry.

        What python-coder must implement to make this green:
            In config/agent_registry.json, in the documentation-expert entry's skills_invoked,
            ADD the following object:
                {
                    "skill_id": "direct-write",
                    "mode": "conditional",
                    "descriptive_only": true
                }
            The behavioral_pattern with pattern_id='direct-write' can remain as-is;
            this adds a parallel skills_invoked documentation entry.
        """
        registry_path = _REPO_ROOT / "config" / "agent_registry.json"
        assert registry_path.is_file(), f"Registry not found at {registry_path}"

        registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
        agents_by_id = {
            a["id"]: a
            for a in registry_data.get("agents", [])
            if isinstance(a, dict) and "id" in a
        }

        doc_expert = agents_by_id.get("documentation-expert")
        assert doc_expert is not None, (
            "documentation-expert entry not found in config/agent_registry.json"
        )

        skills_invoked = doc_expert.get("skills_invoked") or []
        direct_write_entries = [
            inv
            for inv in skills_invoked
            if isinstance(inv, dict) and inv.get("skill_id") == "direct-write"
        ]

        assert len(direct_write_entries) >= 1, (
            "documentation-expert skills_invoked must contain a 'direct-write' entry "
            "(documents the inline doc-writing capability per INF-600d-1). "
            "Add: {\"skill_id\": \"direct-write\", \"mode\": \"conditional\", "
            "\"descriptive_only\": true} to documentation-expert.skills_invoked."
        )
        assert direct_write_entries[0].get("descriptive_only") is True, (
            "documentation-expert's 'direct-write' skills_invoked entry must have "
            f"descriptive_only: true. Current entry: {direct_write_entries[0]}. "
            "Set descriptive_only: true so the validator skips skill-dir resolution."
        )

    def test_ac_scenario3_real_validation_reports_zero_errors(self) -> None:
        # covers: UNKNOWN
        """Integration guard: validate_agent_self_description on the real repo must return 0 errors.

        Given config/agent_registry.json marks run-tests (python-coder) and
        direct-write (documentation-expert) as descriptive_only: true,
        When validate_agent_self_description runs against the real repo in error mode,
        Then error_count == 0 (no dangling-skill_id errors).

        Status: may currently PASS if run-tests/direct-write don't exist yet
        (no unresolvable IDs → validator returns 0 errors). The primary RED signals
        for scenario 3 are the two preceding registry-assertion tests. This test
        becomes a blocker in the INTERMEDIATE state: after run-tests/direct-write
        are ADDED to the registry but before descriptive_only: true is set.

        What python-coder must implement:
            1. Add descriptive_only: true guard in validate_agent_self_description.
            2. Add run-tests + direct-write entries with descriptive_only: true.
        """
        validator = _require_validator()

        error_count, _warning_count = validator(
            target_root=_REPO_ROOT,
            config={},
            dry_run=False,
            enforcement_level="error",
        )

        assert error_count == 0, (
            f"validate_agent_self_description on real repo returned {error_count} error(s). "
            "Expected 0 after marking run-tests (python-coder) and direct-write "
            "(documentation-expert) as descriptive_only: true. "
            "Check the validator output above for which agents/skill_ids are failing."
        )


# ---------------------------------------------------------------------------
# Scenario BP-1300a-1-ii — RED: verdict must be independent of stale deployed artifacts
# ---------------------------------------------------------------------------


class TestVerdictIndependentOfStaleDeploy:
    """BP-1300a-1-ii: descriptive_only verdict independent of stale .claude/skills/ artifacts."""

    def test_ac_bp1300a_1ii_verdict_independent_of_stale_deployed_artifacts(
        self, tmp_path: Path
    ) -> None:
        # covers: UNKNOWN
        """Given a descriptive_only: true entry AND a stale .claude/skills/<id>/ artifact,
        the validator verdict (pass) must be the same as when the stale artifact is absent.

        Two sub-checks:
          (a) WITH stale .claude/skills/inline-capability/ dir: error_count == 0
          (b) WITHOUT the stale dir: error_count == 0
          (c) Both are equal (verdict is invariant to the deployed artifact)

        RED now (two failure modes):
          - Without descriptive_only support the validator checks .claude/skills/ via
            the in_project flag. WITH the stale dir: in_project=True → no error (passes).
            WITHOUT the stale dir: in_package=False, in_project=False → error (fails).
          - So error_count_with_stale != error_count_without_stale → assertion (c) fails.
          - And error_count_without_stale > 0 → assertion (b) fails.

        After the fix:
          - descriptive_only: true skips the resolution check regardless of .claude/skills/
          - Both runs return error_count == 0 → all three assertions pass.

        What python-coder must implement:
            Same as test_ac_bp1300a_1i_descriptive_only_passes:
            ``if inv.get('descriptive_only') is True: continue``
            This makes the pass verdict driven solely by the marker, not by
            the presence of any .claude/skills/ artifact.
        """
        validator = _require_validator()
        agent_name = "fake-agent"
        fm = dict(_FULL_FRONTMATTER)
        fm["name"] = agent_name

        registry_entry = {
            "id": agent_name,
            "category": "implementation",
            "skills_invoked": [
                {
                    "skill_id": "inline-capability",
                    "mode": "conditional",
                    "descriptive_only": True,
                },
            ],
            "knowledge_channels": [{"channel": 1, "source": "template description"}],
        }

        _write_agent_template(tmp_path, agent_name, fm)
        _write_registry(tmp_path, [registry_entry])
        # No canonical templates/skills/inline-capability/ dir (never needed for descriptive entries)

        # ---- Sub-check (a): WITH stale deployed artifact ----
        _write_stale_deployed_skill(tmp_path, "inline-capability")

        error_count_with_stale, _ = validator(
            target_root=tmp_path,
            config={},
            dry_run=False,
            enforcement_level="error",
        )

        # Remove the stale dir and re-run to test sub-check (b)
        shutil.rmtree(tmp_path / ".claude" / "skills" / "inline-capability")

        # ---- Sub-check (b): WITHOUT stale deployed artifact ----
        error_count_without_stale, _ = validator(
            target_root=tmp_path,
            config={},
            dry_run=False,
            enforcement_level="error",
        )

        # (a) With stale dir: must pass
        assert error_count_with_stale == 0, (
            "Expected error_count == 0 with stale .claude/skills/inline-capability/ present "
            "and descriptive_only: true, "
            f"but got error_count={error_count_with_stale}. "
            "The validator must skip resolution for descriptive_only entries regardless "
            "of .claude/skills/ contents."
        )

        # (b) Without stale dir: must also pass
        assert error_count_without_stale == 0, (
            "Expected error_count == 0 without stale deployed artifact and descriptive_only: true, "
            f"but got error_count={error_count_without_stale}. "
            "The validator must not rely on .claude/skills/ resolution for descriptive_only entries."
        )

        # (c) Verdict must be identical whether stale artifact is present or absent
        assert error_count_with_stale == error_count_without_stale, (
            "Verdict changed when stale deployed artifact was added/removed — "
            f"with={error_count_with_stale}, without={error_count_without_stale}. "
            "The validator must be invariant to .claude/skills/ for descriptive_only entries."
        )


# ---------------------------------------------------------------------------
# M-1 follow-on: check_skills_invoked_xref must honour descriptive_only too
# ---------------------------------------------------------------------------


class TestCheckSkillsInvokedXrefDescriptiveOnly:
    """M-1: check_skills_invoked_xref must not emit warnings for descriptive_only entries.

    pr-reviewer advisory M-1 (TICKET-20260708-BP-1300a-descriptive-skills.md):
    After marking run-tests and direct-write as descriptive_only: true, the
    registry_validator.check_skills_invoked_xref function still emitted advisory
    [WARNING] lines for both entries (Direction 2: declared in skills_invoked but
    no reference found in the template body). These entries legitimately have no
    template body reference because they document inline capabilities, not deployed
    skills. Fix: exclude descriptive_only: true entries from declared_ids so the
    Direction 2 advisory is suppressed for them. Guards both directions: the fix
    must only suppress warnings for explicitly marked entries.
    """

    def test_descriptive_only_entry_suppresses_direction2_warning(
        self, tmp_path: Path
    ) -> None:
        """A skills_invoked entry with descriptive_only: true must produce no xref warning.

        Given an agent whose skills_invoked contains one entry with descriptive_only: true
        and whose template body has NO reference to that skill_id,
        When check_skills_invoked_xref runs,
        Then no warning is emitted for that entry (Direction 2 check is skipped for it).

        Rationale: descriptive_only entries document inline capabilities — no template body
        reference is expected. Emitting a "declares X but no reference found" advisory for
        them is misleading noise suppressed by this fix (M-1).
        """
        from registry_validator import check_skills_invoked_xref

        agent_name = "fake-agent"
        agents_dir = tmp_path / "templates" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        # Template body has NO reference to 'inline-capability'
        (agents_dir / f"{agent_name}.md").write_text(
            "You are a test agent with inline capabilities.\n"
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        registry = {
            "agents": [
                {
                    "id": agent_name,
                    "portable": True,
                    "template_path": f"templates/agents/{agent_name}.md",
                    "skills_invoked": [
                        {
                            "skill_id": "inline-capability",
                            "mode": "conditional",
                            "descriptive_only": True,
                        }
                    ],
                }
            ]
        }
        (config_dir / "agent_registry.json").write_text(json.dumps(registry, indent=2))

        xref_warnings = check_skills_invoked_xref(tmp_path)

        assert xref_warnings == [], (
            "Expected no xref warnings for descriptive_only: true entry 'inline-capability', "
            f"but got: {xref_warnings}. "
            "check_skills_invoked_xref must exclude entries where descriptive_only is True "
            "from declared_ids — they document inline capabilities and have no template "
            "body reference by design."
        )

    def test_non_descriptive_unreferenced_entry_still_warns(
        self, tmp_path: Path
    ) -> None:
        """A skills_invoked entry WITHOUT descriptive_only must still produce a Direction 2 warning.

        Guards the negative direction: the descriptive_only exemption must be narrow.
        Only explicitly marked entries are exempted. An entry without descriptive_only
        that has no template body reference must still trigger the advisory warning.

        Given an agent whose skills_invoked contains one entry WITHOUT descriptive_only
        and whose template body has NO reference to that skill_id,
        When check_skills_invoked_xref runs,
        Then a warning is emitted naming that agent and skill_id.
        """
        from registry_validator import check_skills_invoked_xref

        agent_name = "fake-agent"
        agents_dir = tmp_path / "templates" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        # Template body has NO reference to 'unreferenced-skill'
        (agents_dir / f"{agent_name}.md").write_text(
            "You are a test agent.\n"
        )

        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        registry = {
            "agents": [
                {
                    "id": agent_name,
                    "portable": True,
                    "template_path": f"templates/agents/{agent_name}.md",
                    "skills_invoked": [
                        {
                            "skill_id": "unreferenced-skill",
                            "mode": "always",
                            # Deliberately no descriptive_only — must still warn
                        }
                    ],
                }
            ]
        }
        (config_dir / "agent_registry.json").write_text(json.dumps(registry, indent=2))

        xref_warnings = check_skills_invoked_xref(tmp_path)

        matching = [
            w
            for w in xref_warnings
            if "unreferenced-skill" in w and "no reference found" in w
        ]
        assert len(matching) >= 1, (
            "Expected a Direction 2 xref warning for non-descriptive unreferenced entry "
            f"'unreferenced-skill', but got warnings: {xref_warnings}. "
            "The descriptive_only fix must only suppress warnings for entries explicitly "
            "marked descriptive_only: true — unmarked entries must still be warned about."
        )
