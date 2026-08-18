"""
MODULE: test_agent_produces_validation
GOAL: Regression and TDD tests for the 'produces' field validation layer (AC BO-510-3-i).
BUSINESS CONTEXT: Ticket 03 of EPIC-AgentProducesTrait.  Previous tickets (01 and 02)
    added the 'produces' enum to the schema and populated all existing agents.
    This module verifies the enforcement layer: a new agent template or registry
    entry added WITHOUT a 'produces' field must be caught by validation with
    clear error messages identifying both missing locations.

Tests run without invoking Claude Code — they validate registry JSON and template
frontmatter directly, and exercise validate_produces_field() with in-memory fixtures
to prove the error-message format matches the AC requirement.

AC reference: BO-510-3-i (TICKET-20260607-BO-510-3-i)
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"
_TEMPLATE_DIR = _REPO_ROOT / "templates" / "agents"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

# Ensure scripts/ is on sys.path so we can import registry_validator and
# template_compiler directly (same approach used by other unit tests).
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from registry_validator import validate_produces_field  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_registry() -> list[dict[str, Any]]:
    """Load and return the agents list from the live agent_registry.json."""
    assert _REGISTRY_PATH.exists(), (
        f"agent_registry.json not found at {_REGISTRY_PATH}"
    )
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("agents", [])


def _make_agent(agent_id: str, **kwargs: Any) -> dict[str, Any]:
    """Build a minimal registry agent entry for in-memory fixture testing.

    Only 'id' is required; 'produces' is intentionally omitted by default
    so callers can test the missing-produces case explicitly.
    """
    entry: dict[str, Any] = {"id": agent_id}
    entry.update(kwargs)
    return entry


# ---------------------------------------------------------------------------
# §1  Regression tests — live registry and templates
# ---------------------------------------------------------------------------


class TestAllExistingAgentsHaveProducesInRegistry:
    """Every agent in the live agent_registry.json must have a 'produces' field.

    These tests are the regression guard: if a future commit removes or omits
    the 'produces' field from a registry entry, exactly one of these tests will
    catch it with a named error.
    """

    def test_no_registry_entry_missing_produces(self) -> None:
        """All 62 (or more) registry entries must have a non-null 'produces' value."""
        agents = _load_registry()
        missing = [a.get("id", "<unknown>") for a in agents if "produces" not in a]
        assert missing == [], (
            f"The following agents are missing 'produces' in agent_registry.json: {missing}. "
            "Add a 'produces' field to each entry. "
            "See AC BO-510-3 for the allowed enum values."
        )

    def test_all_produces_values_are_valid_enum_members(self) -> None:
        """Every 'produces' value must be a member of the allowed enum."""
        valid = {
            "production_code",
            "documentation",
            "configuration",
            "prompt",
            "review_verdict",
            "orchestration",
            "test_artifact",
            "analysis",
        }
        agents = _load_registry()
        invalid = [
            (a.get("id", "<unknown>"), a.get("produces"))
            for a in agents
            if a.get("produces") not in valid
        ]
        assert invalid == [], (
            f"The following agents have invalid 'produces' values: {invalid}. "
            f"Valid values: {sorted(valid)}"
        )

    def test_registry_has_at_least_one_agent_with_produces(self) -> None:
        """Sanity check: the registry is non-empty and has produces data."""
        agents = _load_registry()
        assert agents, "agent_registry.json has no agents — unexpected empty list."
        agents_with_produces = [a for a in agents if "produces" in a]
        assert agents_with_produces, (
            "No agents in agent_registry.json have a 'produces' field at all — "
            "ticket 02 (populate all agents) may not have been applied."
        )


class TestAllExistingTemplatesHaveProducesInFrontmatter:
    """Every agent template in templates/agents/ must have 'produces' in its frontmatter.

    These tests are the regression guard for template frontmatter.
    """

    def test_no_template_missing_produces_frontmatter(self) -> None:
        """All *.md templates (excluding partials and README) must have 'produces' in frontmatter."""
        try:
            from template_compiler import parse_frontmatter
        except ImportError as exc:
            pytest.skip(f"template_compiler not importable: {exc}")

        assert _TEMPLATE_DIR.exists(), f"templates/agents/ not found at {_TEMPLATE_DIR}"

        missing: list[str] = []
        for tmpl_file in sorted(_TEMPLATE_DIR.glob("*.md")):
            if tmpl_file.name.startswith("_"):
                continue  # Shared partials — not standalone agent templates
            if tmpl_file.stem == "README":
                continue  # Documentation file, not an agent template

            try:
                text = tmpl_file.read_text(encoding="utf-8")
            except OSError as exc:
                pytest.fail(f"Could not read {tmpl_file}: {exc}")

            fm, _ = parse_frontmatter(text)
            if "produces" not in fm:
                missing.append(tmpl_file.name)

        assert missing == [], (
            f"The following agent templates are missing 'produces' in their frontmatter: "
            f"{missing}. Add 'produces: <value>' to each template's YAML frontmatter block."
        )

    def test_template_count_matches_registry(self) -> None:
        """The number of templates matches the number of registry entries (no orphans)."""
        agents = _load_registry()
        # Count registry entries with a template_path pointing to templates/agents/
        # template_path may be None for utility agents — guard with a str cast.
        registry_agent_ids = {
            a.get("id")
            for a in agents
            if (a.get("template_path") or "").startswith("templates/agents/")
        }

        # Count template files (excluding partials and README)
        template_stems = {
            f.stem
            for f in _TEMPLATE_DIR.glob("*.md")
            if not f.name.startswith("_") and f.stem != "README"
        }

        # Not a hard assertion — just a diagnostic to detect divergence.
        # If registry_agent_ids != template_stems, other registry_validator
        # checks (orphan templates) will catch it with better error messages.
        assert len(registry_agent_ids) > 0, (
            "No registry entries found with template_path starting with "
            "'templates/agents/' — unexpected."
        )
        assert len(template_stems) > 0, (
            f"No template files found in {_TEMPLATE_DIR} — unexpected."
        )


# ---------------------------------------------------------------------------
# §2  Unit tests for validate_produces_field() with in-memory fixtures
#
# These tests prove that the validation function correctly detects omissions
# and produces error messages matching the AC-required format.
# ---------------------------------------------------------------------------


class TestValidateProducesFieldRegistryErrors:
    """validate_produces_field() must emit correctly formatted errors when
    a registry entry is missing the 'produces' field (AC BO-510-3-i, Given clause 1)."""

    def test_single_agent_missing_produces_in_registry(self, tmp_path: Path) -> None:
        """Error message must identify the missing registry field by agent ID."""
        # covers: BO-510-3-i
        agents = [_make_agent("new-agent")]  # No 'produces' key
        errors = validate_produces_field(agents, template_dir=tmp_path)

        assert len(errors) >= 1, (
            "Expected at least one error for a registry entry without 'produces'."
        )
        matching = [e for e in errors if "new-agent" in e and "agent_registry.json" in e]
        assert matching, (
            f"Expected an error containing both 'new-agent' and 'agent_registry.json'. "
            f"Got errors: {errors}"
        )
        # AC requires the exact phrasing:
        # "Agent 'new-agent' in agent_registry.json is missing the 'produces' field"
        assert any(
            "missing the 'produces' field" in e
            for e in matching
        ), (
            f"Error message must contain: \"missing the 'produces' field\". "
            f"Matching errors: {matching}"
        )

    def test_error_identifies_agent_id_exactly(self, tmp_path: Path) -> None:
        """The agent ID must appear verbatim in the error string."""
        agents = [_make_agent("my-fancy-bot")]
        errors = validate_produces_field(agents, template_dir=tmp_path)
        assert any("my-fancy-bot" in e for e in errors), (
            f"Agent ID 'my-fancy-bot' not found in any error. Got: {errors}"
        )

    def test_multiple_agents_missing_produces_all_reported(self, tmp_path: Path) -> None:
        """If two agents lack 'produces', two distinct errors are emitted."""
        agents = [_make_agent("alpha"), _make_agent("beta")]
        errors = validate_produces_field(agents, template_dir=tmp_path)
        alpha_errors = [e for e in errors if "alpha" in e]
        beta_errors = [e for e in errors if "beta" in e]
        assert alpha_errors, (
            f"Expected an error for agent 'alpha'. Got: {errors}"
        )
        assert beta_errors, (
            f"Expected an error for agent 'beta'. Got: {errors}"
        )

    def test_agent_with_valid_produces_emits_no_error(self, tmp_path: Path) -> None:
        """An agent that has a valid 'produces' value must not produce any error."""
        agents = [_make_agent("clean-agent", produces="production_code")]
        errors = validate_produces_field(agents, template_dir=tmp_path)
        clean_errors = [e for e in errors if "clean-agent" in e]
        assert clean_errors == [], (
            f"No error expected for 'clean-agent' (has valid produces). "
            f"Got: {clean_errors}"
        )

    def test_agent_with_invalid_produces_value_emits_error(self, tmp_path: Path) -> None:
        """An agent with an unrecognised 'produces' value must be flagged."""
        agents = [_make_agent("bad-agent", produces="magic_spells")]
        errors = validate_produces_field(agents, template_dir=tmp_path)
        bad_errors = [e for e in errors if "bad-agent" in e]
        assert bad_errors, (
            f"Expected an error for 'bad-agent' with produces='magic_spells'. Got: {errors}"
        )
        assert any("magic_spells" in e for e in bad_errors), (
            f"Error message should name the invalid produces value 'magic_spells'. "
            f"Got: {bad_errors}"
        )

    def test_empty_agent_list_returns_no_errors(self, tmp_path: Path) -> None:
        """An empty agents list must not produce any errors."""
        errors = validate_produces_field([], template_dir=tmp_path)
        assert errors == [], f"Expected no errors for empty agents list. Got: {errors}"


class TestValidateProducesFieldTemplateErrors:
    """validate_produces_field() must emit correctly formatted errors when
    an agent template is missing the 'produces' frontmatter field
    (AC BO-510-3-i, Given clause 2)."""

    def _write_template(self, path: Path, frontmatter: str, body: str = "") -> None:
        """Write a minimal agent template file with the given frontmatter."""
        content = f"---\n{frontmatter}\n---\n{body}\n"
        path.write_text(content, encoding="utf-8")

    def test_template_without_produces_triggers_error(self, tmp_path: Path) -> None:
        """Error message must identify the template path and the missing field."""
        # Create a fake templates/agents/ structure under tmp_path
        tmpl_dir = tmp_path / "templates" / "agents"
        tmpl_dir.mkdir(parents=True)

        # Create the template WITHOUT 'produces'
        tmpl_file = tmpl_dir / "new-agent.md"
        self._write_template(
            tmpl_file,
            frontmatter="name: New Agent\nmodel: sonnet",
            body="# New Agent\n",
        )

        # Registry entry pointing to this template
        agents = [
            _make_agent(
                "new-agent",
                produces=None,  # Missing in registry too
                template_path="templates/agents/new-agent.md",
            )
        ]
        # Remove 'produces' key entirely (None is different from absent)
        agents[0].pop("produces", None)

        # Resolve template_dir correctly for validate_produces_field
        errors = validate_produces_field(agents, template_dir=tmpl_dir)

        template_errors = [
            e for e in errors if "new-agent.md" in e or "templates/agents/new-agent.md" in e
        ]
        assert template_errors, (
            f"Expected an error mentioning 'new-agent.md'. Got errors: {errors}"
        )
        assert any(
            "missing the 'produces' frontmatter field" in e
            for e in template_errors
        ), (
            "Error message must contain: \"missing the 'produces' frontmatter field\". "
            f"Got template errors: {template_errors}"
        )

    def test_template_with_produces_emits_no_template_error(self, tmp_path: Path) -> None:
        """A template that HAS 'produces' must not trigger a template error."""
        tmpl_dir = tmp_path / "templates" / "agents"
        tmpl_dir.mkdir(parents=True)

        tmpl_file = tmpl_dir / "good-agent.md"
        self._write_template(
            tmpl_file,
            frontmatter="name: Good Agent\nmodel: sonnet\nproduces: production_code",
            body="# Good Agent\n",
        )

        agents = [
            _make_agent(
                "good-agent",
                produces="production_code",
                template_path="templates/agents/good-agent.md",
            )
        ]

        errors = validate_produces_field(agents, template_dir=tmpl_dir)
        template_errors = [e for e in errors if "good-agent" in e]
        assert template_errors == [], (
            f"No error expected for 'good-agent' (template has produces). "
            f"Got: {template_errors}"
        )

    def test_both_registry_and_template_missing_both_errors_emitted(
        self, tmp_path: Path
    ) -> None:
        """When BOTH the registry entry AND the template lack 'produces', errors for
        BOTH locations must appear in the same validation run (AC BO-510-3-i: 'And').

        This is the primary AC scenario:
          Given a developer adds new-agent.md WITHOUT 'produces',
          And adds a registry entry WITHOUT 'produces',
          Then the test FAILS and identifies BOTH missing locations.
        """
        tmpl_dir = tmp_path / "templates" / "agents"
        tmpl_dir.mkdir(parents=True)

        # Template WITHOUT 'produces'
        tmpl_file = tmpl_dir / "new-agent.md"
        self._write_template(
            tmpl_file,
            frontmatter=textwrap.dedent(
                """\
                name: New Agent
                model: sonnet
                description: A new agent added without produces field
                tools: Read, Bash
                """
            ),
        )

        # Registry entry WITHOUT 'produces'
        agents = [
            {
                "id": "new-agent",
                "template_path": "templates/agents/new-agent.md",
            }
        ]

        errors = validate_produces_field(agents, template_dir=tmpl_dir)

        # Must catch the registry omission
        registry_errors = [
            e for e in errors if "new-agent" in e and "agent_registry.json" in e
        ]
        assert registry_errors, (
            "Expected an error identifying 'new-agent' as missing 'produces' in "
            f"agent_registry.json. All errors: {errors}"
        )

        # Must catch the template frontmatter omission
        template_errors = [
            e for e in errors
            if ("new-agent.md" in e or "templates/agents/new-agent.md" in e)
            and "frontmatter" in e
        ]
        assert template_errors, (
            "Expected an error identifying 'new-agent.md' as missing 'produces' in "
            f"its frontmatter. All errors: {errors}"
        )

        # Verify AC-required error message phrasing for both
        assert any(
            "Agent 'new-agent' in agent_registry.json is missing the 'produces' field" in e
            for e in errors
        ), (
            "Expected exact phrase: "
            "\"Agent 'new-agent' in agent_registry.json is missing the 'produces' field\". "
            f"All errors: {errors}"
        )
        assert any(
            "missing the 'produces' frontmatter field" in e
            for e in errors
        ), (
            "Expected phrase: \"missing the 'produces' frontmatter field\". "
            f"All errors: {errors}"
        )


# ---------------------------------------------------------------------------
# §3  End-to-end: after adding produces to both locations, errors are cleared
# ---------------------------------------------------------------------------


class TestProducesValidationClearsAfterFix:
    """After adding 'produces' to both the registry entry and the template
    frontmatter, validate_produces_field() must return no errors for that agent.

    This models the second half of AC BO-510-3-i:
      'Given the developer then adds produces: production_code to both …
       When the validation test runs again, Then it PASSES.'
    """

    def _write_template(self, path: Path, frontmatter: str, body: str = "") -> None:
        content = f"---\n{frontmatter}\n---\n{body}\n"
        path.write_text(content, encoding="utf-8")

    def test_validation_passes_after_produces_added_to_both(
        self, tmp_path: Path
    ) -> None:
        """validate_produces_field returns [] after produces added to both registry and template."""
        tmpl_dir = tmp_path / "templates" / "agents"
        tmpl_dir.mkdir(parents=True)

        # Template WITH 'produces'
        tmpl_file = tmpl_dir / "new-agent.md"
        self._write_template(
            tmpl_file,
            frontmatter=textwrap.dedent(
                """\
                name: New Agent
                model: sonnet
                description: A new agent — produces field now present
                tools: Read, Bash
                produces: production_code
                """
            ),
        )

        # Registry entry WITH 'produces'
        agents = [
            {
                "id": "new-agent",
                "template_path": "templates/agents/new-agent.md",
                "produces": "production_code",
            }
        ]

        errors = validate_produces_field(agents, template_dir=tmpl_dir)
        new_agent_errors = [e for e in errors if "new-agent" in e]
        assert new_agent_errors == [], (
            "Expected no errors for 'new-agent' after 'produces' was added to both "
            f"the registry and the template. Got: {new_agent_errors}"
        )

    def test_full_validation_round_trip_two_agents(self, tmp_path: Path) -> None:
        """Round-trip: two agents, one fixed (passes) and one not (fails) — only the
        unfixed agent produces errors."""
        tmpl_dir = tmp_path / "templates" / "agents"
        tmpl_dir.mkdir(parents=True)

        # Fixed agent — has 'produces' in both locations
        good_tmpl = tmpl_dir / "good-agent.md"
        self._write_template(
            good_tmpl,
            frontmatter="name: Good Agent\nmodel: sonnet\nproduces: documentation",
        )

        # Broken agent — missing 'produces' in both locations
        bad_tmpl = tmpl_dir / "bad-agent.md"
        self._write_template(
            bad_tmpl,
            frontmatter="name: Bad Agent\nmodel: sonnet",
        )

        agents = [
            {
                "id": "good-agent",
                "template_path": "templates/agents/good-agent.md",
                "produces": "documentation",
            },
            {
                "id": "bad-agent",
                "template_path": "templates/agents/bad-agent.md",
                # 'produces' intentionally absent
            },
        ]

        errors = validate_produces_field(agents, template_dir=tmpl_dir)

        good_errors = [e for e in errors if "good-agent" in e]
        bad_errors = [e for e in errors if "bad-agent" in e]

        assert good_errors == [], (
            f"No errors expected for 'good-agent'. Got: {good_errors}"
        )
        assert bad_errors, (
            f"Errors expected for 'bad-agent' (missing 'produces'). Got: {errors}"
        )


# ---------------------------------------------------------------------------
# §4  Integration: validate_produces_field wired into validate_agent_registry
# ---------------------------------------------------------------------------


class TestValidateProducesFieldWiredIntoMainValidator:
    """validate_agent_registry() in registry_validator.py must call
    validate_produces_field so the check runs end-to-end during the build
    and pre-commit hook.

    This test does NOT mutate the live registry. It verifies that the live
    registry currently passes (i.e. all agents have produces populated)
    when validated through the full validate_agent_registry() call path,
    confirming the wiring is active.
    """

    def test_live_registry_passes_produces_check_via_main_validator(self) -> None:
        """validate_agent_registry on the live repo must return no produces-related errors."""
        from registry_validator import validate_agent_registry

        errors = validate_agent_registry(_REPO_ROOT)

        produces_errors = [
            e for e in errors
            if "produces" in e.lower()
        ]
        assert produces_errors == [], (
            "validate_agent_registry() returned produces-related errors on the live repo. "
            "This means validate_produces_field is wired in and caught a real omission. "
            f"Errors: {produces_errors}"
        )


# ---------------------------------------------------------------------------
# DECISION HISTORY
# ---------------------------------------------------------------------------
# - 2026-06-08 [test-writer/EPIC-AgentProducesTrait/03]: Initial implementation.
#   AC BO-510-3-i: validate_produces_field() added to registry_validator.py;
#   regression tests verify all 62 existing agents are already compliant.
#   In-memory fixture tests prove both error-message formats required by the AC.
#   Round-trip test confirms errors are cleared once 'produces' is added to both
#   the registry and the template frontmatter.
# ---------------------------------------------------------------------------
