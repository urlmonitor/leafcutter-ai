"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/_slim_support.py
GOAL: Shared helpers of the ACD-2500e-2 prompt tests (test_acd_2500e_2.py, test_acd_2500e_2_seams.py): the
    it-po template body, the real rule-check vocabulary (_rc_report), the S8 checklist items and the
    fenced package-surface example. Builds on the G4 support module (S) and adds nothing that reads a file twice.
BUSINESS CONTEXT: Ticket 43 slims templates/agents/it-po.md to the duties the technical planner keeps. What a
    unit test can decide about a prompt is structure and the presence of named rules inside the paragraph that
    carries them; the vocabulary the prompt points at (families, dispositions, hold reasons) is read from the
    real modules so a rename turns the prompt tests red.
ARCHITECTURE: Test-support module (no test_ prefix, not collected). Pure helpers; the scripts/ac_store modules
    are imported flat, the way the deployed store imports them.
"""

from __future__ import annotations

import re
import sys

import yaml

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

sys.path.insert(0, str(S.REPO / "scripts" / "ac_store"))
import _impl_readiness_gate  # noqa: E402
import _rc_report  # noqa: E402
import _test_intent  # noqa: E402

MARKER = "reference file pending"
FOUR_FIELDS = {"config_schema_fragment", "n_location_rule", "required_skills", "post_write_commands"}
# The families the planner itself acts on (architect note D3); the other two are the test designer's.
ACTING_FAMILIES = (
    "FAMILY_CONTRACTS", "FAMILY_DOC_TRIGGERS", "FAMILY_SURFACE", "FAMILY_TEST_INTENT", "FAMILY_BACKLINKS",
    "FAMILY_COMPONENTS", "FAMILY_READINESS", "FAMILY_MODIFIES", "FAMILY_RECORD_SCHEMA",
)
_ITEM = re.compile(r"^\[ \] (\d+)\. (.*?)(?=^\[ \] \d+\. |\Z)", re.DOTALL | re.MULTILINE)


def planner() -> str:
    """The it-po template body (frontmatter removed)."""
    return S.template("it-po")


def family(name: str) -> str:
    """The real rule-family string of the constant `name` in scripts/ac_store/_rc_report.py."""
    return getattr(_rc_report, name)


def s5b(text: str | None = None) -> str:
    """Section S5b 'What the rule check owns' (found by the 'S5b' heading, any level 2-4)."""
    return S.section_titled(planner() if text is None else text, "S5b")


def s8_items(text: str | None = None) -> list[str]:
    """The flattened S8 self-review checklist items, in order."""
    section = S.section_titled(planner() if text is None else text, "S8 Self-Review Checklist")
    return [S.flat(match.group(2)) for match in _ITEM.finditer(section)]


def package_surface_fragment(text: str | None = None) -> dict:
    """The fenced package-surface record fragment the prompt teaches: every fenced mapping whose
    `it_requirements` is an object or that carries `hold_reason`, merged and parsed."""
    merged: dict = {}
    for block in S.YAML_FENCE.findall(planner() if text is None else text):
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict) and (isinstance(parsed.get("it_requirements"), dict) or "hold_reason" in parsed):
            merged.update(parsed)
    assert isinstance(merged.get("it_requirements"), dict), (
        "the prompt needs a fenced yaml example whose it_requirements is an object (package-surface record)"
    )
    return merged


def few_shot(which: str) -> dict:
    """The first fenced record of the few-shot 'Before' / 'After' enrichment block."""
    section = S.section_titled(planner(), f"{which} enrichment")
    return yaml.safe_load(S.YAML_FENCE.findall(section)[0])


def missing_from(haystack: str, needles: tuple[str, ...]) -> list[str]:
    return [needle for needle in needles if needle not in haystack]


__all__ = [
    "ACTING_FAMILIES", "FOUR_FIELDS", "MARKER", "S", "_impl_readiness_gate", "_rc_report", "_test_intent",
    "family", "few_shot", "missing_from", "package_surface_fragment", "planner", "s5b", "s8_items",
]
