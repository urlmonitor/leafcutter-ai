"""
MODULE: _test_design_pending
GOAL: Word the commit-time error for an approved leaf code AC that declares no test contract,
    telling "its test design is pending" apart from "it has no test contract at all".
BUSINESS CONTEXT: ACD-2500b-2-i (ADR-071). A record that carries test intent and no test design
    must not be committed approved: the readiness gate and the ticket generator refuse to build it,
    so the commit check names the real reason instead of asking for a test_spec from scratch.
ARCHITECTURE: Pure stdlib function, no leafcutter imports, no I/O. Split out of
    _ac_schema_validators.py (over the file-size ratchet) so the two texts live in one place;
    validate_test_contract calls it from its `elif not has_spec:` branch. The existing
    "approved code AC must declare a test contract" text is moved verbatim. Deployed with the
    rest of templates/scripts/commit_guardian/ (the whole directory is copied by the build).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def missing_contract_message(path: Path, data: dict[str, Any]) -> str:
    """Return the error for an approved leaf code AC that has no test_spec.

    Args:
        path: Filesystem path to the AC file (named in the message).
        data: Parsed AC YAML content; a non-empty ``test_intent`` list selects the
            "test design pending" text.

    Returns:
        The error message string.
    """
    intent = data.get("test_intent")
    if isinstance(intent, list) and intent:
        return (
            f"{path}: test design pending — this AC records test_intent but no test_spec "
            f"(test design). Intent alone is never a test contract: run the test-design "
            f"step so each needs_test clause has a test_spec entry linked by proves_clause."
        )
    return (
        f"{path}: approved code AC must declare a test contract — add a "
        f"non-empty test_spec (what test-writer should author, derived from "
        f"the Gherkin criteria). If this AC is genuinely test-free, "
        f"reclassify it as non-code (change_target docs/prompt with a "
        f"non-coder assigned_agent). ACs are the source of truth for tests."
    )
