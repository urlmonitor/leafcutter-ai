"""
MODULE: test_readiness_gate
GOAL: Verify the AC readiness gate — schema validation for readiness/priority fields
    and scanner filtering by readiness: approved.
BUSINESS CONTEXT: Ticket 00 of EPIC-ACDrivenDevelopment introduces a `readiness` field
    (draft | reviewed | approved) and a `priority` field (critical | high | medium | low)
    on every AC YAML. Only `approved` ACs are eligible for scanner pickup. The
    validate_ac_schema.py hook enforces both fields on commit.
ARCHITECTURE: Runs against fixture AC YAML files (no DB, no network). Invokes
    validate_ac_schema.py and scan_ac_store.py as subprocess calls so integration
    seams are tested end-to-end.

Source ACs:
    ACS-100a-1  — schema validator rejects missing required fields
    ACD-200a    — BA v3 produces documentation ACs with readiness: draft
    ACD-200a-1  — BA v3 template contains documentation AC generation rules
    ACD-200b    — IT PO v3 sets readiness: reviewed
    ACD-200b-1  — IT PO v3 template instructs promotion to reviewed
    ACD-200c    — Scanner only picks readiness: approved
    ACD-200c-1  — Scanner sort order by priority
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root and script paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATE_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
_SCAN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"
_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_schema.json"


# ---------------------------------------------------------------------------
# Helper: build a minimal valid AC YAML string
# ---------------------------------------------------------------------------


def _make_ac_yaml(**overrides) -> str:
    """Return a minimal valid AC YAML string with optional overrides."""
    base = {
        "id": "TEST-001",
        "title": "Test AC",
        "component": "ac-store",
        "components": ["ac_store"],
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "criteria": "Given X, When Y, Then Z.",
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "delivers_to": None,
        "expects_from": None,
        "origin_agent": "test-writer",
        "created": "2026-06-05",
        "amended_by": [],
        "superseded_by": None,
        "covered_by": [],
        "implemented_by": [],
        "readiness": "draft",
        "priority": "medium",
    }
    base.update(overrides)
    lines = []
    for key, val in base.items():
        if val is None:
            lines.append(f"{key}: null")
        elif isinstance(val, list):
            if val:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: []")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        else:
            lines.append(f"{key}: {val!r}")
    return "\n".join(lines) + "\n"


def _run_validator(ac_yaml_content: str) -> subprocess.CompletedProcess:
    """Write AC YAML to a temp file and run validate_ac_schema.py on it."""
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", encoding="utf-8", delete=False
    ) as fh:
        fh.write(ac_yaml_content)
        tmppath = fh.name
    return subprocess.run(
        ["python3", str(_VALIDATE_SCRIPT), tmppath],
        capture_output=True,
        text=True,
    )


def _run_scanner(ac_store_dir: str) -> subprocess.CompletedProcess:
    """Run scan_ac_store.py on the given directory."""
    return subprocess.run(
        [
            "python3",
            str(_SCAN_SCRIPT),
            "--ac-store-dir",
            ac_store_dir,
            "--level",
            "leaf",
            "--work-status",
            "todo",
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Test: schema rejects missing readiness field
# ---------------------------------------------------------------------------


class TestSchemaRejectsMissingReadiness(unittest.TestCase):
    """
    AC-1: AC schema requires readiness field.

    Given config/ac_schema.json defines the AC YAML schema,
    When a new AC YAML is committed without a readiness field,
    Then the validate_ac_schema.py hook exits non-zero,
    And the error message names the missing field and valid enum values.
    """

    def test_schema_rejects_missing_readiness(self):
        # covers: ACS-100a-1
        """validate_ac_schema.py must exit non-zero when readiness is absent."""
        if not _VALIDATE_SCRIPT.exists():
            self.fail(
                f"validate_ac_schema.py not found at {_VALIDATE_SCRIPT}. "
                "Expected: python-coder creates this script as part of ticket 00."
            )
        ac_without_readiness = _make_ac_yaml()
        # Remove readiness field
        lines = [line for line in ac_without_readiness.splitlines() if not line.startswith("readiness:")]
        ac_without_readiness = "\n".join(lines) + "\n"

        result = _run_validator(ac_without_readiness)
        self.assertNotEqual(
            result.returncode,
            0,
            "validate_ac_schema.py must exit non-zero when 'readiness' is absent.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "readiness",
            combined.lower(),
            "Error message must name the missing 'readiness' field.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


# ---------------------------------------------------------------------------
# Test: schema rejects missing priority field
# ---------------------------------------------------------------------------


class TestSchemaRejectsMissingPriority(unittest.TestCase):
    """
    AC-2: AC schema requires priority field.

    Given config/ac_schema.json defines the AC YAML schema,
    When a new AC YAML is committed without a priority field,
    Then the validate_ac_schema.py hook exits non-zero,
    And the error message names the missing field and valid enum values.
    """

    def test_schema_rejects_missing_priority(self):
        # covers: ACS-100a-1
        """validate_ac_schema.py must exit non-zero when priority is absent."""
        if not _VALIDATE_SCRIPT.exists():
            self.fail(
                f"validate_ac_schema.py not found at {_VALIDATE_SCRIPT}. "
                "Expected: python-coder creates this script as part of ticket 00."
            )
        ac_without_priority = _make_ac_yaml()
        lines = [line for line in ac_without_priority.splitlines() if not line.startswith("priority:")]
        ac_without_priority = "\n".join(lines) + "\n"

        result = _run_validator(ac_without_priority)
        self.assertNotEqual(
            result.returncode,
            0,
            "validate_ac_schema.py must exit non-zero when 'priority' is absent.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "priority",
            combined.lower(),
            "Error message must name the missing 'priority' field.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


# ---------------------------------------------------------------------------
# Test: schema accepts valid readiness enum
# ---------------------------------------------------------------------------


class TestSchemaAcceptsValidReadinessEnum(unittest.TestCase):
    """
    AC-1 (positive path): AC schema accepts ACs with valid readiness values.

    Given config/ac_schema.json defines the AC YAML schema,
    When an AC YAML has readiness: draft (or reviewed or approved),
    Then the validate_ac_schema.py hook exits zero.
    """

    def test_schema_accepts_readiness_draft(self):
        # covers: ACS-100a-1
        """validate_ac_schema.py must exit zero for readiness: draft."""
        if not _VALIDATE_SCRIPT.exists():
            self.fail(
                f"validate_ac_schema.py not found at {_VALIDATE_SCRIPT}. "
                "Expected: python-coder creates this script as part of ticket 00."
            )
        ac_valid = _make_ac_yaml(readiness="draft", priority="medium")
        result = _run_validator(ac_valid)
        self.assertEqual(
            result.returncode,
            0,
            "validate_ac_schema.py must exit zero for a valid AC with readiness: draft.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_schema_accepts_readiness_reviewed(self):
        # covers: ACS-100a-1
        """validate_ac_schema.py must exit zero for readiness: reviewed."""
        if not _VALIDATE_SCRIPT.exists():
            self.fail(
                f"validate_ac_schema.py not found at {_VALIDATE_SCRIPT}. "
                "Expected: python-coder creates this script as part of ticket 00."
            )
        ac_valid = _make_ac_yaml(readiness="reviewed", priority="high")
        result = _run_validator(ac_valid)
        self.assertEqual(
            result.returncode,
            0,
            "validate_ac_schema.py must exit zero for a valid AC with readiness: reviewed.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def test_schema_accepts_readiness_approved(self):
        # covers: ACS-100a-1
        """validate_ac_schema.py must exit zero for readiness: approved."""
        if not _VALIDATE_SCRIPT.exists():
            self.fail(
                f"validate_ac_schema.py not found at {_VALIDATE_SCRIPT}. "
                "Expected: python-coder creates this script as part of ticket 00."
            )
        ac_valid = _make_ac_yaml(readiness="approved", priority="critical")
        result = _run_validator(ac_valid)
        self.assertEqual(
            result.returncode,
            0,
            "validate_ac_schema.py must exit zero for a valid AC with readiness: approved.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


# ---------------------------------------------------------------------------
# Test: scanner excludes draft and reviewed ACs (AC-6)
# ---------------------------------------------------------------------------


class TestScannerExcludesDraftAndReviewed(unittest.TestCase):
    """
    AC-6: Scanner only picks readiness: approved ACs.

    Given the AC store contains ACs with readiness values draft, reviewed, and approved,
    When scan_ac_store.py --level leaf --work-status todo is run,
    Then only ACs with readiness: approved appear in the ready list,
    And draft and reviewed ACs are excluded entirely.
    """

    def setUp(self):
        # covers: ACD-200c
        if not _SCAN_SCRIPT.exists():
            self.skipTest(
                f"scan_ac_store.py not found at {_SCAN_SCRIPT}. "
                "This test is red until python-coder implements the scanner (ticket 01)."
            )

    def test_scanner_excludes_draft_and_reviewed(self):
        # covers: ACD-200c
        """Only approved ACs should appear in the scanner's ready list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Write three ACs: draft, reviewed, approved
            (tmppath / "draft_ac.yaml").write_text(
                _make_ac_yaml(id="TEST-001", work_status="todo", readiness="draft"),
                encoding="utf-8",
            )
            (tmppath / "reviewed_ac.yaml").write_text(
                _make_ac_yaml(id="TEST-002", work_status="todo", readiness="reviewed"),
                encoding="utf-8",
            )
            (tmppath / "approved_ac.yaml").write_text(
                _make_ac_yaml(id="TEST-003", work_status="todo", readiness="approved"),
                encoding="utf-8",
            )

            result = _run_scanner(tmpdir)
            output = result.stdout + result.stderr

            self.assertIn(
                "TEST-003",
                output,
                "Scanner must include the approved AC (TEST-003) in its ready list.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertNotIn(
                "TEST-001",
                output,
                "Scanner must NOT include the draft AC (TEST-001).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertNotIn(
                "TEST-002",
                output,
                "Scanner must NOT include the reviewed AC (TEST-002).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )


# ---------------------------------------------------------------------------
# Test: priority sort order (AC-7)
# ---------------------------------------------------------------------------


class TestPrioritySortOrder(unittest.TestCase):
    """
    AC-7: Priority field controls scanner sort order.

    Given three approved ACs with priorities high, low, critical,
    When scan_ac_store.py --level leaf --work-status todo is run,
    Then the ready list is sorted: critical first, then high, then low,
    And within the same priority, sorted by estimated_complexity ascending.
    """

    def setUp(self):
        # covers: ACD-200c-1
        if not _SCAN_SCRIPT.exists():
            self.skipTest(
                f"scan_ac_store.py not found at {_SCAN_SCRIPT}. "
                "This test is red until python-coder implements the scanner (ticket 01)."
            )

    def test_priority_sort_order(self):
        # covers: ACD-200c-1
        """Scanner output must order: critical, high, low."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "high_ac.yaml").write_text(
                _make_ac_yaml(
                    id="TEST-HIGH",
                    work_status="todo",
                    readiness="approved",
                    priority="high",
                    estimated_complexity="M",
                ),
                encoding="utf-8",
            )
            (tmppath / "low_ac.yaml").write_text(
                _make_ac_yaml(
                    id="TEST-LOW",
                    work_status="todo",
                    readiness="approved",
                    priority="low",
                    estimated_complexity="S",
                ),
                encoding="utf-8",
            )
            (tmppath / "critical_ac.yaml").write_text(
                _make_ac_yaml(
                    id="TEST-CRITICAL",
                    work_status="todo",
                    readiness="approved",
                    priority="critical",
                    estimated_complexity="L",
                ),
                encoding="utf-8",
            )

            result = _run_scanner(tmpdir)
            output = result.stdout

            critical_pos = output.find("TEST-CRITICAL")
            high_pos = output.find("TEST-HIGH")
            low_pos = output.find("TEST-LOW")

            self.assertNotEqual(critical_pos, -1, "TEST-CRITICAL not found in scanner output.")
            self.assertNotEqual(high_pos, -1, "TEST-HIGH not found in scanner output.")
            self.assertNotEqual(low_pos, -1, "TEST-LOW not found in scanner output.")

            self.assertLess(
                critical_pos,
                high_pos,
                "critical AC must appear before high AC in scanner output.",
            )
            self.assertLess(
                high_pos,
                low_pos,
                "high AC must appear before low AC in scanner output.",
            )


if __name__ == "__main__":
    unittest.main()
