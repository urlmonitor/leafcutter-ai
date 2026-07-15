"""
MODULE: tests/commit_guardian/test_diagram_type_enum.py
GOAL: Verify the diagram_type frontmatter enum accepts the canonical values used
      by real architecture docs (data_flow, user_flow, agent_flow) plus the
      legacy alias (dataflow), so check_doc_frontmatter does not reject valid
      docs at commit time.
BUSINESS CONTEXT: GE-105. The effective runtime enum source is
      commit_guardian.json -> doc_frontmatter.diagram_type_values (the fallback
      validate_diagram_type uses when diagram_types.json is not deployed). That
      list was stale — it lacked data_flow/user_flow/agent_flow — so once
      doc-frontmatter enforcement was restored (GE-103), editing any of the
      arch docs that use those values would have been blocked. This test pins
      the enum contract to the canonical values.
ARCHITECTURE: The commit_guardian modules import their siblings by bare name,
      so the package dir must be on sys.path before importing by file stem.
      covers: GE-105
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
CG_DIR = WORKTREE_ROOT / "templates" / "scripts" / "commit_guardian"

# Canonical values that real docs/architecture/*.md files declare today.
CANONICAL_VALUES = ["data_flow", "user_flow", "agent_flow"]
# Legacy alias that must keep working for backward compatibility.
LEGACY_ALIAS = "dataflow"


@pytest.fixture(autouse=True)
def _cg_on_syspath():
    """Put the commit_guardian directory on sys.path for the duration of a test."""
    inserted = str(CG_DIR)
    sys.path.insert(0, inserted)
    try:
        yield
    finally:
        if inserted in sys.path:
            sys.path.remove(inserted)
        sys.modules.pop("diagram_type_validators", None)
        sys.modules.pop("config", None)


def _validate(value: str) -> list[str]:
    """Import the validator fresh and validate a single diagram_type value.

    A fresh import is used so the module's enum cache reflects the current
    commit_guardian.json on disk rather than a value cached by a prior test.
    """
    sys.modules.pop("diagram_type_validators", None)
    sys.modules.pop("config", None)
    mod = importlib.import_module("diagram_type_validators")
    return mod.validate_diagram_type({"diagram_type": value})


@pytest.mark.parametrize("value", CANONICAL_VALUES)
def test_canonical_diagram_type_accepted(value: str):
    """Canonical diagram_type values must be accepted (no validation error)."""
    errors = _validate(value)
    assert errors == [], (
        f"diagram_type '{value}' was rejected but is a canonical value used by "
        f"real arch docs: {errors}"
    )


def test_legacy_alias_still_accepted():
    """The legacy 'dataflow' alias must remain valid (backward compatibility)."""
    assert _validate(LEGACY_ALIAS) == []


def test_bogus_diagram_type_rejected():
    """A value outside the enum must still be rejected (the gate still works)."""
    assert _validate("not_a_real_type")
