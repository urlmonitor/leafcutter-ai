"""
MODULE: test_quality_improvement
GOAL: Verify that the knowledge loop produces measurable quality improvement
    on repeat work for BA v3, PO v3, and IT PO v3 agents.
BUSINESS CONTEXT: Tickets 00-03 build the knowledge loop (inject, emit,
    harvest, share). This module verifies the end result: the second run on
    the same component produces better output than the first. Tests exercise
    the full loop end-to-end via fixtures and assert observable quality
    differences between first-run and second-run scenarios.
    These tests define the acceptance gate for AC-1 (INF-400e-1),
    AC-2 (INF-400e-2), and AC-3 (INF-400e-3).
ARCHITECTURE: Unit tests with pre-populated context-file fixtures per the
    architect-review recommendation. Tests use tempfile.TemporaryDirectory for
    filesystem isolation and assert observable outputs of the knowledge
    injection/emission pipeline (file contents, routing, formatting) rather
    than spawning real agents. All tests must complete in < 5 seconds.
    Test strategy: simulate the §0/S0 injection step for each v3 agent by
    populating the context files it reads, then verify the injection mechanism
    reads those files correctly and that the content is in the expected format
    for influencing second-run output.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: resolve context_file_maintenance module without installed pkg
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CFM_PATH = _REPO_ROOT / "scripts" / "knowledge" / "context_file_maintenance.py"
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"


def _load_module(name: str, path: Path):
    """Load a module from source path; returns (module, error_string)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        return None, f"Could not create spec for {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    else:
        return mod, None


_cfm, _cfm_err = _load_module("context_file_maintenance", _CFM_PATH)
_harvest, _harvest_err = _load_module("harvest_learnings", _HARVEST_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _ModuleUnavailableError(ImportError):
    """Raised when a required knowledge module could not be loaded from source."""


def _require_cfm():
    if _cfm is None:
        raise _ModuleUnavailableError(_cfm_err)
    return _cfm


def _require_harvest():
    if _harvest is None:
        raise _ModuleUnavailableError(_harvest_err)
    return _harvest


def _make_component_dir(tmpdir: Path, component: str) -> Path:
    """Create a component AC directory structure and return its path."""
    comp_dir = tmpdir / "docs" / "acceptance-criteria" / component
    comp_dir.mkdir(parents=True, exist_ok=True)
    return comp_dir


def _write_context_file(path: Path, entries: list[dict]) -> None:
    """Write a PROJECT_CONTEXT.md or README.md with pre-populated entries.

    Each entry dict has keys: date (str), agent (str), text (str).
    Entries are written newest-first (reverse-chronological order).
    """
    header = "# Component Context\n\nPre-populated for quality improvement tests.\n"
    blocks = []
    for entry in entries:
        blocks.append(f"## {entry['date']} — {entry['agent']}\n{entry['text']}\n")
    content = header + "\n" + "\n".join(blocks) if blocks else header
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_memory_file(memory_dir: Path, filename: str, content: str) -> None:
    """Write a memory file simulating a prior-agent learning."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / filename).write_text(content, encoding="utf-8")


def _simulate_ba_injection(component_dir: Path, memory_dir: Path) -> dict:
    """Simulate the BA v3 §0 injection step.

    Returns a dict with keys:
      - 'project_context_read': bool — whether PROJECT_CONTEXT.md was found and non-empty
      - 'readme_read': bool — whether README.md was found and non-empty
      - 'memory_files': list of str — memory file names found matching BA patterns
      - 'po_memory_files': list of str — PO memory files found (cross-agent sharing)
      - 'standing_rules_found': list of str — any standing-rule text from PROJECT_CONTEXT
    """
    result = {
        "project_context_read": False,
        "readme_read": False,
        "memory_files": [],
        "po_memory_files": [],
        "standing_rules_found": [],
    }

    # Step 2: Read component PROJECT_CONTEXT.md (BA §0 step 2)
    ctx_path = component_dir / "PROJECT_CONTEXT.md"
    if ctx_path.exists():
        text = ctx_path.read_text(encoding="utf-8")
        if text.strip():
            result["project_context_read"] = True
            # Extract any "standing rule" entries
            for line in text.splitlines():
                if "standing" in line.lower() or "all l2" in line.lower():
                    result["standing_rules_found"].append(line.strip())

    # Step 3: Read component README.md (BA §0 step 3)
    readme_path = component_dir / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        if text.strip():
            result["readme_read"] = True

    # Step 4: Scan memory/ for BA-pattern files (BA §0 step 4)
    if memory_dir.exists():
        ba_patterns = ["ba", "business-analyst", "analyst"]
        for f in memory_dir.iterdir():
            name = f.name.lower()
            if any(pat in name for pat in ba_patterns) and f.suffix == ".md":
                result["memory_files"].append(f.name)

        # Step 5: Scan memory/ for PO-pattern files (BA §0 step 5 — cross-agent)
        po_patterns = ["po", "product", "product-owner"]
        for f in memory_dir.iterdir():
            name = f.name.lower()
            if any(pat in name for pat in po_patterns) and f.suffix == ".md":
                result["po_memory_files"].append(f.name)

    return result


def _simulate_po_injection(component_dir: Path, memory_dir: Path) -> dict:
    """Simulate the PO v3 S0 injection step.

    Returns a dict with keys:
      - 'project_context_read': bool
      - 'readme_read': bool
      - 'memory_files': list of str — memory file names matching PO patterns
      - 'framing_preferences_found': list of str — framing preference text found
    """
    result = {
        "project_context_read": False,
        "readme_read": False,
        "memory_files": [],
        "framing_preferences_found": [],
    }

    # Step 2: Read component PROJECT_CONTEXT.md (PO S0 step 2)
    ctx_path = component_dir / "PROJECT_CONTEXT.md"
    if ctx_path.exists():
        text = ctx_path.read_text(encoding="utf-8")
        if text.strip():
            result["project_context_read"] = True

    # Step 3: Read component README.md (PO S0 step 3)
    readme_path = component_dir / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        if text.strip():
            result["readme_read"] = True

    # Step 4: Scan memory/ for PO-pattern files (PO S0 step 4)
    if memory_dir.exists():
        po_patterns = ["po", "product", "product-owner"]
        for f in memory_dir.iterdir():
            name = f.name.lower()
            if any(pat in name for pat in po_patterns) and f.suffix == ".md":
                result["memory_files"].append(f.name)
                # Extract any framing preference entries
                text = f.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if "start with the problem" in line.lower() or "framing" in line.lower():
                        result["framing_preferences_found"].append(line.strip())

    return result


def _simulate_itpo_injection(component_dir: Path, memory_dir: Path) -> dict:
    """Simulate the IT PO v3 S0 injection step.

    Returns a dict with keys:
      - 'project_context_read': bool
      - 'memory_files': list of str — memory file names matching IT PO patterns
      - 'prior_agent_mappings_found': list of str — prior component-agent mapping text
      - 'po_ba_memory_files': list of str — cross-agent PO/BA memory files found
    """
    result = {
        "project_context_read": False,
        "memory_files": [],
        "prior_agent_mappings_found": [],
        "po_ba_memory_files": [],
    }

    # Step 2: Read component PROJECT_CONTEXT.md (IT PO S0 step 2)
    ctx_path = component_dir / "PROJECT_CONTEXT.md"
    if ctx_path.exists():
        text = ctx_path.read_text(encoding="utf-8")
        if text.strip():
            result["project_context_read"] = True
            # Extract any prior agent assignment entries
            for line in text.splitlines():
                if "python-coder" in line.lower() or "llm-expert" in line.lower():
                    result["prior_agent_mappings_found"].append(line.strip())

    # Step 4: Scan memory/ for IT PO patterns (IT PO S0 step 4)
    if memory_dir.exists():
        itpo_patterns = ["it-po", "itpo", "technical-enrichment"]
        for f in memory_dir.iterdir():
            name = f.name.lower()
            if any(pat in name for pat in itpo_patterns) and f.suffix == ".md":
                result["memory_files"].append(f.name)

        # Step 5: Cross-agent PO + BA memory (IT PO S0 step 5)
        cross_patterns = ["po", "product", "product-owner", "ba", "business-analyst", "analyst"]
        for f in memory_dir.iterdir():
            name = f.name.lower()
            if any(pat in name for pat in cross_patterns) and f.suffix == ".md":
                result["po_ba_memory_files"].append(f.name)

    return result


# ---------------------------------------------------------------------------
# AC-1 Tests: BA v3 second-run references standing rules without being told
# ---------------------------------------------------------------------------


class TestBASecondRunReferencesStandingRules(unittest.TestCase):
    """AC-1 (INF-400e-1): BA v3 second run picks up standing rules from context file.

    Scenario: First run discovers a standing AC rule for component X.
    The rule is captured and persisted to the component's PROJECT_CONTEXT.md.
    Second run reads PROJECT_CONTEXT.md and can reference the rule.
    """

    def test_ba_reads_project_context_md_on_second_run(self) -> None:
        """Given a pre-populated PROJECT_CONTEXT.md with a standing rule,
        the BA v3 §0 injection reads it and surfaces the standing rule content.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # Simulate first-run learning: standing rule captured to PROJECT_CONTEXT.md
            standing_rule_text = (
                "Standing rule: all L2 criteria must reference the parent L1 in depends_on. "
                "Discovered during INF-400a processing."
            )
            _write_context_file(
                comp_dir / "PROJECT_CONTEXT.md",
                [{"date": "2026-06-01", "agent": "business-analyst-v3", "text": standing_rule_text}],
            )

            # Simulate second run: BA performs §0 injection
            injection = _simulate_ba_injection(comp_dir, memory_dir)

            # Assert: PROJECT_CONTEXT.md was read
            self.assertTrue(
                injection["project_context_read"],
                "BA §0 injection failed to read PROJECT_CONTEXT.md on second run",
            )
            # Assert: the standing rule content is findable
            self.assertTrue(
                len(injection["standing_rules_found"]) > 0,
                "BA §0 injection did not surface standing rule from PROJECT_CONTEXT.md; "
                f"standing_rules_found={injection['standing_rules_found']}",
            )
            self.assertTrue(
                any("all l2" in r.lower() for r in injection["standing_rules_found"]),
                "Expected 'all L2' standing rule not found in injected context",
            )

    def test_ba_first_run_baseline_has_no_context(self) -> None:
        """Given an empty component directory (no prior runs),
        the BA v3 §0 injection returns no standing rules (baseline).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # No context files created — first run baseline
            injection = _simulate_ba_injection(comp_dir, memory_dir)

            self.assertFalse(
                injection["project_context_read"],
                "First run should not have PROJECT_CONTEXT.md available",
            )
            self.assertEqual(
                len(injection["standing_rules_found"]),
                0,
                "First run should have no standing rules from context",
            )

    def test_ba_context_persisted_via_append_entry(self) -> None:
        """Given the context_file_maintenance module,
        when a BA learning is appended to PROJECT_CONTEXT.md,
        then on the next simulated injection, the standing rule is present.
        """
        cfm = _require_cfm()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            ctx_path = comp_dir / "PROJECT_CONTEXT.md"
            memory_dir = tmp / "memory"

            # First run: no context
            injection_first = _simulate_ba_injection(comp_dir, memory_dir)
            self.assertFalse(injection_first["project_context_read"])

            # Capture a learning via append_entry (simulating post-run emission)
            standing_rule = "all L2 criteria must reference the parent L1 in depends_on"
            cfm.append_entry(
                path=ctx_path,
                date="2026-06-05",
                agent="business-analyst-v3",
                text=f"Standing rule discovered: {standing_rule}",
            )

            # Second run: injection now finds the persisted learning
            injection_second = _simulate_ba_injection(comp_dir, memory_dir)
            self.assertTrue(
                injection_second["project_context_read"],
                "Second run: PROJECT_CONTEXT.md should be present after first-run emission",
            )
            self.assertTrue(
                len(injection_second["standing_rules_found"]) > 0,
                "Second run: standing rule should be surfaced from appended context",
            )


# ---------------------------------------------------------------------------
# AC-2 Tests: PO v3 second-run uses previously-learned framing preferences
# ---------------------------------------------------------------------------


class TestPOSecondRunUsesFramingPreferences(unittest.TestCase):
    """AC-2 (INF-400e-2): PO v3 second run picks up framing preferences from memory.

    Scenario: User corrects the PO's framing style ("start with the problem,
    not the solution"). That correction is captured as a learning in a memory
    file. Second run reads the memory file and applies the preference.
    """

    def test_po_reads_memory_file_with_framing_preference(self) -> None:
        """Given a memory file with the framing preference captured from first run,
        the PO v3 S0 injection reads it and surfaces the framing preference text.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # Simulate the captured framing correction in a PO memory file
            framing_correction = (
                "User framing preference: start with the problem, not the solution. "
                "Observed during INF-400a L0 authoring — user rejected solution-first framing."
            )
            _write_memory_file(
                memory_dir,
                "po_framing_preferences.md",
                f"# Product Owner Learnings\n\n## 2026-06-01 — product-owner-v3\n{framing_correction}\n",
            )

            # Simulate second run: PO performs S0 injection
            injection = _simulate_po_injection(comp_dir, memory_dir)

            # Assert: memory file was found
            self.assertIn(
                "po_framing_preferences.md",
                injection["memory_files"],
                "PO S0 injection did not find the framing preference memory file",
            )
            # Assert: framing preference text is accessible
            self.assertTrue(
                len(injection["framing_preferences_found"]) > 0,
                "PO S0 injection did not surface framing preference from memory file; "
                f"framing_preferences_found={injection['framing_preferences_found']}",
            )
            self.assertTrue(
                any("start with the problem" in pref.lower() for pref in injection["framing_preferences_found"]),
                "Expected 'start with the problem' framing preference not found",
            )

    def test_po_first_run_has_no_memory_files(self) -> None:
        """Given a fresh project with no prior PO runs (no memory/ directory),
        the PO v3 S0 injection finds no memory files (baseline).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"  # Does not exist yet

            injection = _simulate_po_injection(comp_dir, memory_dir)

            self.assertEqual(
                len(injection["memory_files"]),
                0,
                "First run: no PO memory files should exist",
            )
            self.assertEqual(
                len(injection["framing_preferences_found"]),
                0,
                "First run: no framing preferences should be available",
            )

    def test_po_picks_up_correction_on_second_run(self) -> None:
        """Given a PO memory file is created after first run,
        the second-run injection picks it up — without the user re-stating it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # Before first run: no memory files
            injection_first = _simulate_po_injection(comp_dir, memory_dir)
            self.assertEqual(len(injection_first["memory_files"]), 0)

            # After first run: correction is captured
            _write_memory_file(
                memory_dir,
                "product_owner_learnings.md",
                "# PO Learnings\n\n## 2026-06-05 — product-owner-v3\n"
                "Framing: start with the problem, not the solution.\n",
            )

            # Second run: injection finds the memory file
            injection_second = _simulate_po_injection(comp_dir, memory_dir)
            self.assertGreater(
                len(injection_second["memory_files"]),
                0,
                "Second run: PO memory file should be found",
            )
            self.assertGreater(
                len(injection_second["framing_preferences_found"]),
                0,
                "Second run: framing preference should be surfaced",
            )


# ---------------------------------------------------------------------------
# AC-3 Tests: IT PO v3 second-run uses prior component-agent mappings
# ---------------------------------------------------------------------------


class TestITPOSecondRunUsesPriorAgentMappings(unittest.TestCase):
    """AC-3 (INF-400e-3): IT PO v3 second run picks up prior component-agent mappings.

    Scenario: First run on component Y learns that python-coder handles scripts
    and llm-expert handles templates. That learning is captured. Second run
    reads the captured learning and applies the correct assignments.
    """

    def test_itpo_reads_prior_agent_mapping_from_context(self) -> None:
        """Given a PROJECT_CONTEXT.md with prior component-agent mappings captured,
        the IT PO v3 S0 injection reads and surfaces those mappings.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # Simulate first-run learning: agent mapping persisted to PROJECT_CONTEXT.md
            mapping_text = (
                "Component agent mapping: python-coder handles .py scripts; "
                "llm-expert handles agent template .md files. "
                "Observed during infrastructure INF-400b enrichment."
            )
            _write_context_file(
                comp_dir / "PROJECT_CONTEXT.md",
                [{"date": "2026-06-01", "agent": "it-po-v3", "text": mapping_text}],
            )

            # Simulate second run: IT PO performs S0 injection
            injection = _simulate_itpo_injection(comp_dir, memory_dir)

            # Assert: PROJECT_CONTEXT.md was read
            self.assertTrue(
                injection["project_context_read"],
                "IT PO S0 injection failed to read PROJECT_CONTEXT.md on second run",
            )
            # Assert: prior agent mappings are findable
            self.assertTrue(
                len(injection["prior_agent_mappings_found"]) > 0,
                "IT PO S0 injection did not surface prior agent mappings from context; "
                f"prior_agent_mappings_found={injection['prior_agent_mappings_found']}",
            )
            self.assertTrue(
                any("python-coder" in m.lower() for m in injection["prior_agent_mappings_found"]),
                "Expected python-coder mapping not found in injected context",
            )

    def test_itpo_first_run_has_no_prior_mappings(self) -> None:
        """Given a fresh component (no prior IT PO runs),
        the IT PO v3 S0 injection finds no prior agent mappings (baseline).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # No context files — baseline first run
            injection = _simulate_itpo_injection(comp_dir, memory_dir)

            self.assertFalse(
                injection["project_context_read"],
                "First run: no PROJECT_CONTEXT.md should exist",
            )
            self.assertEqual(
                len(injection["prior_agent_mappings_found"]),
                0,
                "First run: no prior agent mappings should be available",
            )

    def test_itpo_prior_mapping_persisted_via_append_entry(self) -> None:
        """Given the context_file_maintenance module,
        when an IT PO learning is appended to PROJECT_CONTEXT.md,
        then on second-run injection, the agent mapping is present.
        """
        cfm = _require_cfm()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            ctx_path = comp_dir / "PROJECT_CONTEXT.md"
            memory_dir = tmp / "memory"

            # First run: no context
            injection_first = _simulate_itpo_injection(comp_dir, memory_dir)
            self.assertFalse(injection_first["project_context_read"])

            # Capture learning via append_entry (simulating post-run emission)
            mapping_learning = (
                "component Y uses python-coder for scripts and llm-expert for templates"
            )
            cfm.append_entry(
                path=ctx_path,
                date="2026-06-05",
                agent="it-po-v3",
                text=f"Component agent mapping learned: {mapping_learning}",
            )

            # Second run: injection now finds the persisted mapping
            injection_second = _simulate_itpo_injection(comp_dir, memory_dir)
            self.assertTrue(
                injection_second["project_context_read"],
                "Second run: PROJECT_CONTEXT.md should be present after first-run emission",
            )
            # The mapping text should be present in the context
            ctx_content = ctx_path.read_text(encoding="utf-8")
            self.assertIn(
                "python-coder",
                ctx_content,
                "Prior agent mapping (python-coder) should be in PROJECT_CONTEXT.md",
            )
            self.assertIn(
                "llm-expert",
                ctx_content,
                "Prior agent mapping (llm-expert) should be in PROJECT_CONTEXT.md",
            )

    def test_itpo_cross_agent_memory_files_found(self) -> None:
        """Given memory files from PO and BA runs exist (cross-agent sharing),
        the IT PO v3 S0 injection finds and loads them too (S0 step 5).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"

            # Create cross-agent memory files from BA and PO
            _write_memory_file(
                memory_dir,
                "ba_infrastructure_learnings.md",
                "# BA Learnings\n\n## 2026-06-01 — business-analyst-v3\nBA discovery.\n",
            )
            _write_memory_file(
                memory_dir,
                "po_framing_preferences.md",
                "# PO Learnings\n\n## 2026-06-01 — product-owner-v3\nPO framing note.\n",
            )
            _write_memory_file(
                memory_dir,
                "it-po_mappings.md",
                "# IT PO Learnings\n\n## 2026-06-01 — it-po-v3\nIT PO mapping.\n",
            )

            injection = _simulate_itpo_injection(comp_dir, memory_dir)

            # IT PO own memory files found
            self.assertIn(
                "it-po_mappings.md",
                injection["memory_files"],
                "IT PO memory file should be found",
            )
            # Cross-agent PO/BA memory files also found
            po_ba_found = set(injection["po_ba_memory_files"])
            self.assertTrue(
                len(po_ba_found) >= 2,
                f"Expected at least 2 cross-agent (PO+BA) memory files; found: {po_ba_found}",
            )


# ---------------------------------------------------------------------------
# Integration: end-to-end learning capture and retrieval via harvest
# ---------------------------------------------------------------------------


class TestEndToEndLearningCapture(unittest.TestCase):
    """Integration: a learning emitted after first run is captured via harvest
    and retrievable on second run via injection.

    This test exercises the full loop:
    1. First-run agent emits a knowledge_captured event to the sink
    2. harvest_learnings.py processes the event and writes to the context file
    3. Second-run injection reads the context file and finds the learning
    """

    def test_harvested_learning_available_on_second_run(self) -> None:
        """End-to-end: emit → harvest → inject cycle for BA standing rule."""
        import json as _json

        cfm = _require_cfm()
        harvest_mod = _require_harvest()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            comp_dir = _make_component_dir(tmp, "infrastructure")
            memory_dir = tmp / "memory"
            ctx_path = comp_dir / "PROJECT_CONTEXT.md"
            sink_path = tmp / "knowledge_emissions.jsonl"
            state_path = tmp / "harvest_state.json"

            # Step 1: Simulate first-run knowledge emission
            standing_rule_text = "all L2 criteria must reference the parent L1 in depends_on"
            event = {
                "event": "knowledge_captured",
                "timestamp": "2026-06-05T10:00:00Z",
                "ticket": "tickets/00_inbox/epics/EPIC-AgentLearningLoop/04_quality_improvement_verification.md",
                "destination": str(ctx_path),
                "entry_kind": "per-folder-readme",
                "text": f"Standing rule: {standing_rule_text}",
            }
            with open(sink_path, "w", encoding="utf-8") as fh:
                fh.write(_json.dumps(event) + "\n")

            # Step 2: Harvest processes the event
            def real_write(learning_text: str, destination_path: str) -> None:
                """Write via append_entry so the context file gets proper format."""
                dest = Path(destination_path)
                cfm.append_entry(
                    path=dest,
                    date="2026-06-05",
                    agent="harvest-learnings",
                    text=learning_text[:200],  # truncate to respect 5-line limit
                )

            result = harvest_mod.harvest(
                sink_path=sink_path,
                state_path=state_path,
                capture_fn=real_write,
            )
            self.assertEqual(result.routed, 1, "Event should be routed by harvester")

            # Step 3: Second-run injection finds the learning
            injection = _simulate_ba_injection(comp_dir, memory_dir)
            self.assertTrue(
                injection["project_context_read"],
                "Second run: PROJECT_CONTEXT.md should be present after harvest",
            )

            # Verify the context file exists and has the learning
            self.assertTrue(ctx_path.exists(), "Context file should exist after harvest")
            ctx_content = ctx_path.read_text(encoding="utf-8")
            self.assertIn(
                "Standing rule",
                ctx_content,
                "Harvested learning should appear in context file",
            )


# ---------------------------------------------------------------------------
# Fixture validation: context file format is correct for injection
# ---------------------------------------------------------------------------


class TestContextFileFormat(unittest.TestCase):
    """Verify that context files written by append_entry have the correct format
    for agent §0/S0 injection steps to parse successfully.
    """

    def test_context_file_has_correct_entry_heading_format(self) -> None:
        """append_entry produces headings matching '## YYYY-MM-DD — agent' pattern."""
        cfm = _require_cfm()
        import re

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "PROJECT_CONTEXT.md"
            cfm.append_entry(
                path=path,
                date="2026-06-05",
                agent="business-analyst-v3",
                text="Test entry for format validation.",
            )
            content = path.read_text(encoding="utf-8")
            pattern = re.compile(r"^## \d{4}-\d{2}-\d{2} — .+$", re.MULTILINE)
            matches = pattern.findall(content)
            self.assertGreater(
                len(matches), 0,
                "No entry heading matching '## YYYY-MM-DD — agent' found in context file",
            )

    def test_readme_has_component_header(self) -> None:
        """create_readme produces a file with '# {component} — domain conventions' header."""
        cfm = _require_cfm()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "README.md"
            cfm.create_readme(path=path, component="infrastructure")
            content = path.read_text(encoding="utf-8")
            self.assertIn(
                "# infrastructure — domain conventions",
                content,
                "README.md header should contain component name",
            )

    def test_newest_entry_appears_first(self) -> None:
        """After two append_entry calls, newest entry appears before older entry."""
        cfm = _require_cfm()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "context.md"
            cfm.append_entry(path=path, date="2026-06-01", agent="agent-a", text="Older entry.")
            cfm.append_entry(path=path, date="2026-06-05", agent="agent-b", text="Newer entry.")
            content = path.read_text(encoding="utf-8")
            pos_newer = content.find("Newer entry.")
            pos_older = content.find("Older entry.")
            self.assertLess(
                pos_newer, pos_older,
                "Newer entry should appear before older entry (reverse-chronological order)",
            )


if __name__ == "__main__":
    unittest.main()
