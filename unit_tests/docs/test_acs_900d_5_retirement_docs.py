"""ACS-900d-5 -- the retire-a-superseded-AC guidance (content checks).

The AC is ``test_required: false`` (documentation deliverable). Each test reads the
delivered doc section and asserts that one clause of the AC's criteria is actually stated.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOW_TO = REPO / "docs" / "how-to" / "ac-traceability-store.md"
SCHEMA = REPO / "docs" / "reference" / "ac-schema.md"


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _retire_section() -> str:
    text = HOW_TO.read_text(encoding="utf-8")
    start = text.index("## How do I deprecate or retire an AC?")
    end = text.index("\n## ", start + 1)
    return _flat(text[start:end])


def test_how_to_gives_the_retirement_steps():
    # covers: ACS-900d-5
    # angle: criterion
    """Set status superseded_by, list existing successors, keep work_status, stage the parent."""
    sec = _retire_section()
    assert "status: superseded_by" in sec
    assert "superseded_by: [MYC-003]" in sec and "existing successor" in sec
    assert "Leave `work_status` as it was" in sec
    assert "with its parent staged" in sec


def test_how_to_states_which_gates_stop_and_which_still_apply():
    # covers: ACS-900d-5
    # angle: criterion
    """Exempt: covering test, test contract, unfinished children. Kept: successor rules and parent link."""
    sec = _retire_section()
    for exempt in ("`check-done-proof` (covering test)", "`check-ac-schema` (test contract)",
                   "unfinished-children blocking"):
        assert exempt in sec, f"exemption not stated: {exempt}"
    assert "still refuses a missing, empty, null or self successor" in sec
    assert "`check-ac-parent-covered-by` still applies" in sec


def test_how_to_says_gaming_fields_is_wrong():
    # covers: ACS-900d-5
    # angle: criterion
    """Editing readiness, change_target, test tags or test contracts to pass a gate is called wrong."""
    sec = _retire_section()
    assert "editing `readiness`, `change_target`, `# covers:` tags or test contracts to pass a gate is wrong" in sec


def test_schema_status_table_names_the_structural_rules():
    # covers: ACS-900d-5
    # angle: discrimination
    """The status table no longer says superseded is merely excluded; it names the rules that still apply."""
    text = _flat(SCHEMA.read_text(encoding="utf-8"))
    row = text[text.index("| `superseded_by` |"):text.index("| `superseded` |")]
    assert "excluded from active enforcement" not in row
    assert "Structural rules still apply" in row and "parent `covered_by` link" in row
