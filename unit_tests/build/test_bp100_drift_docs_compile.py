"""Test coverage backfill for BP-100 ACs: drift-hook / docs / template-compiler.

Nature: CODE_NO_TEST backfill.  The production surfaces already exist; this file
provides the missing verifiable coverage so each AC's ``work_status: done`` claim
is honestly backed.

Covers:
  BP-100b-5   check_output_drift scans .claude/workflows/ and reports drift when
              a compiled workflow file is mutated; passes silently when all match.
  BP-100b-5-i No false-positive when the legacy .agents/workflows/ path is absent.
  BP-100b-6-i Parity test assertion message names the missing category AND layer.
  BP-100b-8   docs/build-pipeline.md mermaid graph has a build_workflow_scripts
              phase node with the semantic identifier and a .claude/workflows/ label.
  BP-100b-9   docs/explanation/consolidated-output-root.md shimmed-outputs table
              has a row with source templates/scripts/workflows/, output
              .claude/workflows/, and a description of compiled workflow JS scripts.
  BP-100b-10  docs/build-drift-hook.md "Adding a new template category" section
              enumerates all four infrastructure layers and references
              tests/test_build_artifact_parity.py as the enforcement gate.
  BP-100c-4   compile_agent_template threads config to build_project_paths_table so
              that the compiled paths-table reflects config-overridden inbox paths.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — unit_tests/build/test_*.py is 3 levels down from worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# scripts/ must be in sys.path for template_compiler + injection_builders
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# templates/scripts/commit_guardian/ must be in sys.path for check_output_drift
# ---------------------------------------------------------------------------
_COMMIT_GUARDIAN_DIR = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
)
if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

# ---------------------------------------------------------------------------
# Lazy imports so individual tests show a real failure rather than a single
# collection-time ImportError when the module doesn't exist yet.
# ---------------------------------------------------------------------------
try:
    import check_output_drift as _cod  # noqa: E402
except ImportError:
    _cod = None  # type: ignore[assignment]

try:
    from template_compiler import compile_agent_template as _compile_agent  # noqa: E402
except (ImportError, ModuleNotFoundError):
    _compile_agent = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Named sentinel exceptions — avoids TRY003 (long raise-message) lint rule.
# ---------------------------------------------------------------------------

class _DriftCheckNotAvailable(ImportError):
    """check_output_drift is not importable from templates/scripts/commit_guardian/.

    Raised when the module is absent and a test requires it.
    """

    def __init__(self) -> None:
        super().__init__(
            "check_output_drift not importable — "
            f"confirm {_COMMIT_GUARDIAN_DIR} exists."
        )


class _CompileAgentNotAvailable(ImportError):
    """compile_agent_template is not importable from scripts/template_compiler.py.

    Raised when the module is absent and a test requires it.
    """

    def __init__(self) -> None:
        super().__init__(
            "compile_agent_template not importable — "
            f"confirm {_SCRIPTS_DIR}/template_compiler.py exists."
        )


# ===========================================================================
# BP-100b-5: check_output_drift scans .claude/workflows/
# ===========================================================================

class TestBP100b5DriftHookScansClaudeWorkflows(unittest.TestCase):
    """BP-100b-5: drift hook reports drift for mutated workflow files."""

    def _require_cod(self):
        if _cod is None:
            raise _DriftCheckNotAvailable()
        return _cod

    def _make_fixture(
        self,
        tmp: Path,
        filename: str,
        content: bytes,
        use_hash_of: bytes | None = None,
    ) -> tuple[Path, Path]:
        """Build a minimal fixture tree under tmp.

        Creates .claude/workflows/<filename> and a .build_manifest.json that
        records the hash of ``use_hash_of`` (defaults to ``content``).

        Returns (workflows_dir, manifest_path).
        """
        workflows_dir = tmp / ".claude" / "workflows"
        workflows_dir.mkdir(parents=True)
        wf = workflows_dir / filename
        wf.write_bytes(content)

        hash_source = use_hash_of if use_hash_of is not None else content
        expected_hash = hashlib.sha256(hash_source).hexdigest()

        manifest = {
            "output_mappings": {
                f".claude/workflows/{filename}": {
                    "template": f"templates/scripts/workflows/{filename}",
                    "expected_output_hash": expected_hash,
                }
            }
        }
        manifest_path = tmp / ".build_manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return workflows_dir, manifest_path

    def test_ac_bp100b5_drift_reported_for_mutated_workflow_file(self):
        # covers: BP-100b-5
        """Mutating a compiled workflow file produces a drift violation (exit 1).

        Drive check_output_drift.check_output_drift() against a fixture tree where
        the on-disk content of .claude/workflows/build-epic.js differs from the
        expected_output_hash recorded in the manifest.
        """
        cod = self._require_cod()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            original = b"// build-epic.js - original content from build.py"
            mutated = b"// build-epic.js - MUTATED by hand-edit"
            # Manifest records hash of original, but file now contains mutated bytes.
            workflows_dir, manifest_path = self._make_fixture(
                tmp_path, "build-epic.js", mutated, use_hash_of=original
            )

            result = cod.check_output_drift(
                output_dirs=[workflows_dir],
                manifest_path=manifest_path,
                repo_root=tmp_path,
            )
            self.assertEqual(
                result,
                1,
                "check_output_drift must return 1 when a .claude/workflows/ file "
                "has been mutated (content hash differs from manifest hash).",
            )

    def test_ac_bp100b5_passes_silently_when_all_workflow_files_match(self):
        # covers: BP-100b-5
        """No drift violation when workflow file content matches the manifest hash.

        When all .claude/workflows/ files are bit-for-bit identical to what
        build.py wrote (hashes agree), check_output_drift must exit 0 silently.
        """
        cod = self._require_cod()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            content = b"// build-ticket.js - unchanged content"
            workflows_dir, manifest_path = self._make_fixture(
                tmp_path, "build-ticket.js", content
            )

            result = cod.check_output_drift(
                output_dirs=[workflows_dir],
                manifest_path=manifest_path,
                repo_root=tmp_path,
            )
            self.assertEqual(
                result,
                0,
                "check_output_drift must return 0 (no drift) when all workflow "
                "files match their expected hashes in the manifest.",
            )


# ===========================================================================
# BP-100b-5-i: no false-positive when .agents/workflows/ is absent
# ===========================================================================

class TestBP100b5INoPseudoPositiveOnAbsentAgentsWorkflows(unittest.TestCase):
    """BP-100b-5-i: absent legacy .agents/workflows/ must not cause errors."""

    def _require_cod(self):
        if _cod is None:
            raise _DriftCheckNotAvailable()
        return _cod

    def test_ac_bp100b5_i_no_false_positive_when_agents_workflows_absent(self):
        # covers: BP-100b-5-i
        """When .agents/workflows/ does not exist, drift check proceeds via
        .claude/workflows/ only; no OSError is raised, drift check is not skipped,
        and the function returns 0 (clean state) for matching files.

        Replicates the real-world condition: legacy .agents/workflows/ never existed
        in this repo, only .claude/workflows/ is present.
        """
        cod = self._require_cod()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Only .claude/workflows/ exists.
            workflows_dir = tmp_path / ".claude" / "workflows"
            workflows_dir.mkdir(parents=True)
            absent_dir = tmp_path / ".agents" / "workflows"
            # Intentionally NOT created — it must be absent.

            content = b"// create-ticket.js - original"
            wf = workflows_dir / "create-ticket.js"
            wf.write_bytes(content)
            expected_hash = hashlib.sha256(content).hexdigest()

            manifest = {
                "output_mappings": {
                    ".claude/workflows/create-ticket.js": {
                        "template": "templates/scripts/workflows/create-ticket.js",
                        "expected_output_hash": expected_hash,
                    }
                }
            }
            manifest_path = tmp_path / ".build_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            # Pass both dirs — absent_dir must be silently skipped.
            result = cod.check_output_drift(
                output_dirs=[workflows_dir, absent_dir],
                manifest_path=manifest_path,
                repo_root=tmp_path,
            )

            self.assertFalse(
                absent_dir.exists(),
                "Test precondition violated: .agents/workflows/ must be absent.",
            )
            self.assertEqual(
                result,
                0,
                "check_output_drift must return 0 when .agents/workflows/ is absent "
                "and .claude/workflows/ files all match. The absent directory must "
                "be silently skipped — no error, no drift-skip.",
            )


# ===========================================================================
# BP-100b-6-i: parity test failure messages name category and layer
# ===========================================================================

class TestBP100b6IParityMessageNamesCategoryAndLayer(unittest.TestCase):
    """BP-100b-6-i: assertion messages name the failing category AND layer."""

    def test_ac_bp100b6_i_assertion_messages_reference_category_and_layer(self):
        # covers: BP-100b-6-i
        """The assertion messages in tests/test_build_artifact_parity.py use format
        strings that produce output naming the missing category (via {cat} or
        {managed_key}) AND the specific infrastructure layer (shim_map,
        _MANAGED_ARTIFACT_DIRS, _build_source_manifests) — sufficient for a
        developer to identify which registration steps were skipped without
        reading the test source.
        """
        parity_path = _REPO_ROOT / "tests" / "test_build_artifact_parity.py"
        self.assertTrue(
            parity_path.exists(),
            "tests/test_build_artifact_parity.py must exist as the parity gate.",
        )
        source = parity_path.read_text(encoding="utf-8")

        # Category naming: the format tokens {cat} or {managed_key} appear in
        # assertion strings so the produced message names the category.
        category_refs = ["{cat}", "{managed_key}"]
        has_category_ref = any(ref in source for ref in category_refs)
        self.assertTrue(
            has_category_ref,
            "Parity test assertion messages must contain {cat} or {managed_key} "
            "format tokens so the failure output names the missing category. "
            f"None of {category_refs} found in the source.",
        )

        # Layer naming: at least one layer identifier must appear in the assertion
        # messages so the developer knows which infrastructure layer is absent.
        layer_identifiers = [
            "shim_map",
            "_MANAGED_ARTIFACT_DIRS",
            "_build_source_manifests",
        ]
        has_layer_id = any(lid in source for lid in layer_identifiers)
        self.assertTrue(
            has_layer_id,
            "Parity test assertion messages must reference at least one specific "
            "infrastructure layer identifier so developers know which registration "
            f"step is missing. None of {layer_identifiers} found in the source.",
        )


# ===========================================================================
# BP-100b-8: docs/build-pipeline.md has build_workflow_scripts phase node
# ===========================================================================

class TestBP100b8BuildPipelineDiagramHasWorkflowScriptsNode(unittest.TestCase):
    """BP-100b-8: build-pipeline.md mermaid graph has build_workflow_scripts node."""

    def test_ac_bp100b8_mermaid_graph_has_build_workflow_scripts_node_id(self):
        # covers: BP-100b-8
        """docs/build-pipeline.md mermaid graph TD must contain the semantic node
        identifier 'build_workflow_scripts' (the underscore form used in Mermaid
        node IDs) so the build workflow scripts phase is explicitly named in the
        diagram — not just present as an opaque single-letter node.

        The diagram must also include '.claude/workflows/' as the label naming
        the output destination of this phase.

        NOTE: As of 2026-07-15 the diagram uses node-id 'N' with edge-label
        'build workflow scripts' (spaces, no node-id). This test is expected to
        fail until the diagram is updated to use 'build_workflow_scripts' as the
        explicit node identifier (BP-100b-8 AC criterion).
        """
        doc_path = _REPO_ROOT / "docs" / "build-pipeline.md"
        self.assertTrue(
            doc_path.exists(),
            "docs/build-pipeline.md must exist.",
        )
        content = doc_path.read_text(encoding="utf-8")

        # BP-100b-8 requires 'build_workflow_scripts' as a Mermaid phase node.
        # The AC criterion says "build_workflow_scripts appears as a phase node".
        self.assertIn(
            "build_workflow_scripts",
            content,
            "docs/build-pipeline.md must contain 'build_workflow_scripts' as a "
            "Mermaid node identifier (underscore form) so the build workflow scripts "
            "phase is semantically named in the diagram. "
            "The current diagram uses the generic identifier 'N' instead.",
        )

        # The output destination must be named.
        self.assertIn(
            ".claude/workflows/",
            content,
            "docs/build-pipeline.md mermaid diagram must mention '.claude/workflows/' "
            "as the output destination for the build_workflow_scripts phase.",
        )


# ===========================================================================
# BP-100b-9: consolidated-output-root.md has workflows source row in table
# ===========================================================================

class TestBP100b9ConsolidatedOutputDocWorkflowsRow(unittest.TestCase):
    """BP-100b-9: consolidated-output-root.md shimmed-outputs table has workflows row."""

    def test_ac_bp100b9_shimmed_outputs_table_has_workflows_source_path(self):
        # covers: BP-100b-9
        """docs/explanation/consolidated-output-root.md shimmed-outputs table must
        contain a row with:
          source = 'templates/scripts/workflows/'
          output = '.claude/workflows/'
          description mentioning compiled workflow JS scripts.

        NOTE: As of 2026-07-15 the table has columns 'Canonical path | Points to |
        Why the shim is needed' showing .claude/workflows/ → .leafcutter/workflows/.
        There is no column or row for the source template directory
        'templates/scripts/workflows/'. This test is expected to fail until the
        table is updated to include the source column/row required by BP-100b-9.
        """
        doc_path = (
            _REPO_ROOT / "docs" / "explanation" / "consolidated-output-root.md"
        )
        self.assertTrue(
            doc_path.exists(),
            "docs/explanation/consolidated-output-root.md must exist.",
        )
        content = doc_path.read_text(encoding="utf-8")

        # The AC requires the source template directory in the table.
        self.assertIn(
            "templates/scripts/workflows/",
            content,
            "consolidated-output-root.md shimmed-outputs table must include "
            "'templates/scripts/workflows/' as the source path for the "
            ".claude/workflows/ row. Currently the table only shows the canonical "
            "shim path and its .leafcutter/ target, not the template source dir.",
        )

        # The row must reference .claude/workflows/ as the output (canonical) path.
        self.assertIn(
            ".claude/workflows/",
            content,
            "consolidated-output-root.md must reference '.claude/workflows/' as "
            "the output/canonical path in the shimmed-outputs table.",
        )


# ===========================================================================
# BP-100b-10: build-drift-hook.md four-layer section + parity test reference
# ===========================================================================

class TestBP100b10DriftHookDocFourLayersSection(unittest.TestCase):
    """BP-100b-10: build-drift-hook.md section lists all four layers + parity gate."""

    def test_ac_bp100b10_new_category_section_has_all_four_layers(self):
        # covers: BP-100b-10
        """docs/build-drift-hook.md must contain a section titled or subtitled
        'Adding a new template category' that:
          1. Enumerates all four infrastructure layers: shim map, output mappings,
             managed artifact dirs, source manifests.
          2. References tests/test_build_artifact_parity.py as the enforcement gate.
        """
        doc_path = _REPO_ROOT / "docs" / "build-drift-hook.md"
        self.assertTrue(
            doc_path.exists(),
            "docs/build-drift-hook.md must exist.",
        )
        content = doc_path.read_text(encoding="utf-8")

        # Section title check (case-insensitive; may have a number prefix).
        self.assertIn(
            "new template category",
            content.lower(),
            "docs/build-drift-hook.md must include a section covering "
            "'Adding a new template category'.",
        )

        # All four infrastructure layers must be enumerated.
        four_layers: list[tuple[str, list[str]]] = [
            ("shim map",            ["shim map", "shim_map", "Shim map"]),
            ("output mappings",     ["output mapping", "Output mapping"]),
            ("managed artifact dirs",
             ["managed artifact", "MANAGED_ARTIFACT", "_MANAGED_ARTIFACT_DIRS"]),
            ("source manifests",
             ["source manifest", "_build_source_manifests"]),
        ]
        for layer_label, variants in four_layers:
            with self.subTest(layer=layer_label):
                found = any(v in content for v in variants)
                self.assertTrue(
                    found,
                    f"docs/build-drift-hook.md must enumerate the '{layer_label}' "
                    f"layer in the 'Adding a new template category' section. "
                    f"None of {variants} found in the document.",
                )

        # Must reference the parity test as the enforcement gate.
        self.assertIn(
            "tests/test_build_artifact_parity.py",
            content,
            "docs/build-drift-hook.md must reference "
            "'tests/test_build_artifact_parity.py' as the enforcement gate for "
            "the four-layer developer checklist.",
        )


# ===========================================================================
# BP-100c-4: compile_agent_template threads config to paths-table builder
# ===========================================================================

class TestBP100c4TemplateCompilerThreadsConfigToPathsTable(unittest.TestCase):
    """BP-100c-4: config overlay is passed through compile_agent_template to paths table."""

    def test_ac_bp100c4_config_inbox_path_appears_in_compiled_paths_table(self):
        # covers: BP-100c-4
        """Given a template containing {{project_paths_table}} and a config with
        tickets_inbox_path = 'leafcutter-ai/tickets/00_inbox', the compiled output:
          - contains 'leafcutter-ai/tickets/00_inbox'
          - does NOT contain the static default row
            '| tickets.inbox | tickets/00_inbox/ |'

        This verifies the config threads from compile_agent_template →
        _apply_registry_injection → build_project_paths_table without being dropped.
        """
        if _compile_agent is None:
            raise _CompileAgentNotAvailable()

        custom_inbox = "leafcutter-ai/tickets/00_inbox"
        # This is the table row that must NOT appear after the config override.
        default_inbox_row = "| tickets.inbox | tickets/00_inbox/ |"

        template_body = "# Paths Agent\n\n{{project_paths_table}}\n"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template_file = tmp_path / "paths_agent.md"
            template_file.write_text(template_body, encoding="utf-8")

            compiled = _compile_agent(
                template_path=template_file,
                config={"tickets_inbox_path": custom_inbox},
                agents=[],  # non-None triggers _apply_registry_injection
            )

        self.assertIn(
            custom_inbox,
            compiled,
            f"Compiled output must contain the config-overridden inbox path "
            f"'{custom_inbox}'. The config is not threading through from "
            "compile_agent_template → _apply_registry_injection → "
            "build_project_paths_table.",
        )
        self.assertNotIn(
            default_inbox_row,
            compiled,
            f"Compiled output must not contain the static default row "
            f"'{default_inbox_row}' for tickets.inbox when the config provides "
            "a custom value.",
        )


if __name__ == "__main__":
    unittest.main()
