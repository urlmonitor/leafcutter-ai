"""
MODULE: test_doc_types_dispatch_table
GOAL: Unit tests for build_doc_types_dispatch_table() injection builder and
    its {{doc_types_dispatch_table}} placeholder wiring in template_compiler.py.
BUSINESS CONTEXT: Validates EPIC-AgentRegistryAsSourceOfTruth ticket 10: the
    dispatch table replaces the hardcoded Classification Table and Dispatch
    Contract in documentation-expert.md with a single token that reads
    doc_types.json at build time.  Tests cover filtering, null-agent rendering,
    insertion-order preservation, and end-to-end template compilation.
ARCHITECTURE: Standard pytest. No database, no network. Uses tmp_path for
    synthetic doc_types.json fixtures. Loads injection_builders and
    template_compiler via sys.path so the scripts/ module can be imported
    without installing it. All tests must complete within 5 seconds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: add scripts/ to sys.path so we can import without installing.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import injection_builders as ib  # noqa: E402
import template_compiler as tc   # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_doc_types(tmp_path: Path, doc_types: dict) -> Path:
    """Write a synthetic doc_types.json under tmp_path/config/ and return its path."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "doc_types.json"
    path.write_text(
        json.dumps({"doc_types": doc_types}, indent=2),
        encoding="utf-8",
    )
    return tmp_path  # return package_root, not the file path


_SAMPLE_DOC_TYPES: dict = {
    "how_to": {
        "description": "Task-oriented procedure.",
        "writer_agent": "how-to-author",
    },
    "reference": {
        "description": "Lookup-oriented reference.",
        "writer_agent": "reference-author",
    },
    "tutorial": {
        "description": "Learning-oriented tutorial.",
        "writer_agent": None,
    },
    "adr": {
        "description": "Architecture Decision Record.",
        "writer_agent": "adr-author",
    },
    "how-to": {
        "description": "Legacy alias for how_to.",
        "writer_agent": "how-to-author",
        "_deprecated": True,
    },
    "cross-cutting": {
        "description": "Cross-cutting concern — deprecated.",
        "writer_agent": None,
        "_deprecated": True,
    },
}


# ---------------------------------------------------------------------------
# T1: Non-deprecated entries appear in output table
# ---------------------------------------------------------------------------

class TestNonDeprecatedEntriesAppear:
    """T1: Non-deprecated doc types are rendered in the dispatch table."""

    def test_non_deprecated_types_present(self, tmp_path: Path) -> None:
        """how_to, reference, tutorial, adr all appear when not deprecated."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "how_to" in result
        assert "reference" in result
        assert "tutorial" in result
        assert "adr" in result

    def test_table_has_header_row(self, tmp_path: Path) -> None:
        """The rendered table includes the expected markdown header."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "| Doc type | Description | Writer agent |" in result

    def test_writer_agent_appears_in_backticks(self, tmp_path: Path) -> None:
        """Writer agent names are rendered in backticks."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "`how-to-author`" in result
        assert "`reference-author`" in result
        assert "`adr-author`" in result


# ---------------------------------------------------------------------------
# T2: Deprecated entries are excluded
# ---------------------------------------------------------------------------

class TestDeprecatedEntriesExcluded:
    """T2: Entries with _deprecated: true must NOT appear in the dispatch table."""

    def test_deprecated_entry_absent(self, tmp_path: Path) -> None:
        """The how-to legacy alias (deprecated) is not in the output."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        # "how-to" should not appear as a table row key (only "how_to" should)
        lines = result.splitlines()
        data_lines = [ln for ln in lines if ln.startswith("| `")]
        type_keys = [ln.split("|")[1].strip().strip("`") for ln in data_lines]
        assert "how-to" not in type_keys

    def test_cross_cutting_deprecated_absent(self, tmp_path: Path) -> None:
        """cross-cutting (deprecated, null writer) does not appear in the table."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        lines = result.splitlines()
        data_lines = [ln for ln in lines if ln.startswith("| `")]
        type_keys = [ln.split("|")[1].strip().strip("`") for ln in data_lines]
        assert "cross-cutting" not in type_keys

    def test_all_deprecated_filtered_out(self, tmp_path: Path) -> None:
        """When all entries are deprecated, a descriptive fallback is returned."""
        all_deprecated = {
            "old-type": {
                "description": "Old.",
                "writer_agent": None,
                "_deprecated": True,
            },
        }
        pkg_root = _write_doc_types(tmp_path, all_deprecated)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "No non-deprecated doc types" in result


# ---------------------------------------------------------------------------
# T3: writer_agent: null renders as "no dedicated agent"
# ---------------------------------------------------------------------------

class TestNullWriterAgentRendering:
    """T3: Entries with writer_agent: null render as 'no dedicated agent'."""

    def test_null_writer_agent_renders_as_no_dedicated_agent(self, tmp_path: Path) -> None:
        """tutorial has writer_agent: null and must render as 'no dedicated agent'."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "no dedicated agent" in result

    def test_null_writer_agent_not_empty_cell(self, tmp_path: Path) -> None:
        """The null writer_agent cell is not empty — it is the fallback string."""
        pkg_root = _write_doc_types(tmp_path, _SAMPLE_DOC_TYPES)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        # Find the tutorial row
        lines = result.splitlines()
        tutorial_lines = [ln for ln in lines if "tutorial" in ln and "|" in ln]
        assert tutorial_lines, "tutorial row not found in output"
        tutorial_row = tutorial_lines[0]
        # The writer cell must not be blank or "None"
        assert "None" not in tutorial_row
        assert "no dedicated agent" in tutorial_row

    def test_only_null_writer_agent(self, tmp_path: Path) -> None:
        """A doc type with writer_agent: null renders correctly in isolation."""
        only_null = {
            "retro": {
                "description": "Retrospective.",
                "writer_agent": None,
            },
        }
        pkg_root = _write_doc_types(tmp_path, only_null)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "retro" in result
        assert "no dedicated agent" in result


# ---------------------------------------------------------------------------
# T4: Adding a new entry to doc_types.json includes it in the table
# ---------------------------------------------------------------------------

class TestNewEntryIncluded:
    """T4: Adding a new non-deprecated entry to doc_types.json causes it to appear."""

    def test_new_entry_appears_after_rebuild(self, tmp_path: Path) -> None:
        """A newly added doc type (not deprecated) appears in the rebuilt table."""
        initial_types = {
            "how_to": {
                "description": "Task-oriented procedure.",
                "writer_agent": "how-to-author",
            },
        }
        pkg_root = _write_doc_types(tmp_path, initial_types)
        result_before = ib.build_doc_types_dispatch_table(pkg_root)
        assert "my-new-type" not in result_before

        # Add the new entry and re-call the builder (simulates re-running build.py)
        extended_types = dict(initial_types)
        extended_types["my-new-type"] = {
            "description": "Brand new doc type.",
            "writer_agent": "my-new-author",
        }
        pkg_root2 = _write_doc_types(tmp_path, extended_types)
        result_after = ib.build_doc_types_dispatch_table(pkg_root2)
        assert "my-new-type" in result_after
        assert "my-new-author" in result_after

    def test_insertion_order_preserved(self, tmp_path: Path) -> None:
        """Entries appear in JSON insertion order, not alphabetical order."""
        ordered_types = {
            "zzz_last": {"description": "Last alphabetically.", "writer_agent": "agent-z"},
            "aaa_first": {"description": "First alphabetically.", "writer_agent": "agent-a"},
        }
        pkg_root = _write_doc_types(tmp_path, ordered_types)
        result = ib.build_doc_types_dispatch_table(pkg_root)
        lines = result.splitlines()
        data_lines = [ln for ln in lines if ln.startswith("| `")]
        keys_in_order = [ln.split("|")[1].strip().strip("`") for ln in data_lines]
        assert keys_in_order.index("zzz_last") < keys_in_order.index("aaa_first"), (
            "Insertion order must be preserved; zzz_last should appear before aaa_first"
        )


# ---------------------------------------------------------------------------
# T5: {{doc_types_dispatch_table}} placeholder is resolved by template_compiler
# ---------------------------------------------------------------------------

class TestPlaceholderReplacedByTemplateCompiler:
    """T5: The {{doc_types_dispatch_table}} token is resolved during compilation.

    compile_agent_template only calls _apply_registry_injection when agents is
    not None (the standard production code path always passes agents). Tests here
    pass agents=[] to trigger the injection path while keeping the test minimal.
    """

    def test_placeholder_replaced_in_compiled_output(self, tmp_path: Path) -> None:
        """compile_agent_template replaces {{doc_types_dispatch_table}} with table."""
        # Write a minimal template that uses the new placeholder
        template_file = tmp_path / "test-doc-agent.md"
        template_file.write_text(
            "---\nname: test-doc-agent\nmodel: sonnet\ntools: Bash\n---\n\n"
            "{{doc_types_dispatch_table}}\n",
            encoding="utf-8",
        )

        # Pass agents=[] to trigger _apply_registry_injection (production always passes agents)
        result = tc.compile_agent_template(template_file, {}, agents=[])

        # The raw token must not appear in the output
        assert "{{doc_types_dispatch_table}}" not in result
        # The table header must appear instead
        assert "| Doc type | Description | Writer agent |" in result

    def test_placeholder_removed_when_doc_types_file_exists(self, tmp_path: Path) -> None:
        """Verifies the token expands to a non-empty table (not a fallback string)."""
        template_file = tmp_path / "minimal-agent.md"
        template_file.write_text(
            "---\nname: minimal-agent\nmodel: sonnet\ntools: Bash\n---\n\n"
            "{{doc_types_dispatch_table}}\n",
            encoding="utf-8",
        )
        # Pass agents=[] to trigger _apply_registry_injection
        result = tc.compile_agent_template(template_file, {}, agents=[])
        # Real doc_types.json exists so we should get actual table rows
        assert "how_to" in result or "reference" in result, (
            "Expected at least one doc type row to appear in compiled output"
        )


# ---------------------------------------------------------------------------
# Fallback / error path tests
# ---------------------------------------------------------------------------

class TestFallbackPaths:
    """Edge cases: missing file, malformed JSON, empty doc_types."""

    def test_missing_doc_types_json_returns_fallback(self, tmp_path: Path) -> None:
        """When doc_types.json does not exist, a descriptive fallback is returned."""
        # tmp_path has no config/ subdirectory
        result = ib.build_doc_types_dispatch_table(tmp_path)
        assert "doc_types.json not found" in result

    def test_empty_doc_types_returns_fallback(self, tmp_path: Path) -> None:
        """When doc_types is an empty dict, a descriptive fallback is returned."""
        pkg_root = _write_doc_types(tmp_path, {})
        result = ib.build_doc_types_dispatch_table(pkg_root)
        assert "No doc types defined" in result

    def test_malformed_json_returns_fallback(self, tmp_path: Path) -> None:
        """When doc_types.json is not valid JSON, a descriptive fallback is returned."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "doc_types.json").write_text("NOT { valid json", encoding="utf-8")
        result = ib.build_doc_types_dispatch_table(tmp_path)
        assert "could not be parsed" in result
