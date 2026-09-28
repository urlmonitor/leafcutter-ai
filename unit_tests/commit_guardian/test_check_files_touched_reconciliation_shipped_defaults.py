"""
MODULE: test_check_files_touched_reconciliation_shipped_defaults
GOAL: Pin the SHIPPED files_touched_reconciliation defaults in the real
    commit_guardian.json against the documented contract (BP-1100e-2):
    enabled:true, strict:true (blocking-by-default since a36837dc,
    2026-08-13).
BUSINESS CONTEXT: The existing remediation suite
    (test_check_files_touched_reconciliation_remediation.py) exhaustively
    tests the hook's _load_config/main() LOGIC by mocking _load_config's
    return value or writing its own throwaway temp configs — it never once
    reads the real, shipped templates/scripts/commit_guardian/
    commit_guardian.json. That gap is exactly how the shipped default
    silently drifted from its documented contract on 2026-08-13 without
    any test noticing. This module closes that gap by asserting directly
    against the shipped file.
ARCHITECTURE: A single pure assertion helper (_assert_shipped_defaults)
    encodes the contract and raises an AssertionError naming both the
    shipped value and the documented contract on divergence. One test
    exercises it against the real shipped file; a second test exercises
    the SAME helper against a deliberately flipped in-memory copy to prove
    the check is not vacuously green, without ever touching the real file.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "commit_guardian.json"
)


def _assert_shipped_defaults(section: dict[str, Any]) -> None:
    """Assert a files_touched_reconciliation section matches the documented
    contract: enabled:true, strict:true (blocking by default since
    a36837dc, 2026-08-13; see BP-1100e-2 and this section's own _comment
    field in commit_guardian.json).

    Raises:
        AssertionError: naming both the shipped value and the documented
            contract when they diverge, so a future drift's failure
            message states plainly what changed.
    """
    enabled = section.get("enabled")
    strict = section.get("strict")
    if enabled is not True or strict is not True:
        msg = (
            "files_touched_reconciliation SHIPPED DEFAULT has DIVERGED "
            f"from its DOCUMENTED CONTRACT: shipped enabled={enabled!r}, "
            f"strict={strict!r}; documented contract (BP-1100e-2, "
            "blocking-by-default per a36837dc 2026-08-13) requires "
            "enabled=True, strict=True."
        )
        raise AssertionError(msg)


class TestShippedFilesTouchedReconciliationDefaults(unittest.TestCase):
    """covers: BP-1100e-2"""

    def test_shipped_config_matches_documented_contract(self) -> None:
        # covers: BP-1100e-2
        """The real shipped commit_guardian.json must ship enabled:true, strict:true."""
        content = CONFIG_PATH.read_text(encoding="utf-8")
        config = json.loads(content)
        section = config.get("files_touched_reconciliation")
        self.assertIsNotNone(
            section,
            "files_touched_reconciliation section missing from shipped "
            f"config at {CONFIG_PATH}",
        )
        _assert_shipped_defaults(section)

    def test_assertion_helper_fails_on_flipped_in_memory_copy(self) -> None:
        # covers: BP-1100e-2
        """Prove the check is not vacuously green.

        Exercises the SAME assertion helper used above against a
        deliberately wrong in-memory section (strict flipped to False)
        without touching the real shipped file, to demonstrate the helper
        actually discriminates a diverged default and names both values
        in its failure message.
        """
        flipped = {"enabled": True, "strict": False}
        with self.assertRaises(AssertionError) as ctx:
            _assert_shipped_defaults(flipped)
        message = str(ctx.exception)
        self.assertIn("DIVERGED", message)
        self.assertIn("strict=False", message)
        self.assertIn("BP-1100e-2", message)


if __name__ == "__main__":
    unittest.main()
