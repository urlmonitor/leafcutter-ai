"""
MODULE: unit_tests/prompt_assembly/test_tq_500f_1_taught_set_discrimination.py
COVERS: TQ-500f-1

GOAL (from the AC criteria): "the test writer's taught set of test kinds
lists 'discrimination' beside the seven existing kinds, with its
distinguishing rule: the test goes red under at least one named plausible
wrong version of the code, not only when the code is absent".

This test parses the REAL machine-extractable TAUGHT-TEST-ANGLES YAML block
in templates/agents/test-writer.md (the same anchor
unit_tests/prompt_assembly/test_bp_1100g_1.py already reads) and asserts it
now has EIGHT keys, one of them "discrimination", carrying a non-empty rule
that states the distinguishing criterion from the AC's own words — not just
any prose, but specifically language about going red under a NAMED wrong
version, as opposed to only when the code is absent.

RED BASELINE (2026-09-25, confirmed live): the anchor currently parses to
exactly 7 keys (criterion, reachability, seam, real_artifact, deployed,
boundary, failure) -- no "discrimination" key at all. This test is
self-contained (does not import test_bp_1100g_1.py) precisely so it proves
the CONTENT requirement (discrimination + its rule) independently of that
sibling file's own widened lockstep obligation (TQ-500f-1-i).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "agents" / "test-writer.md"

_ANCHOR_START = "<!-- TAUGHT-TEST-ANGLES:START -->"
_ANCHOR_END = "<!-- TAUGHT-TEST-ANGLES:END -->"

#: Words that must co-occur in the discrimination rule for it to actually
#: state the AC's distinguishing criterion, rather than just mentioning the
#: word "discrimination" in passing. "wrong version" / "red" together are
#: the AC-literal phrasing; "absent" is the contrast this angle must draw
#: (NOT only when the code is absent).
_REQUIRED_RULE_FRAGMENTS = ("wrong version", "red")


def _load_taught_angles(template_path: Path) -> dict:
    """Parse the taught-angle anchor out of a real test-writer.md on disk.

    Mirrors the parsing test_bp_1100g_1.py uses (same anchor markers, same
    fenced-YAML extraction), but implemented independently here so this
    file's collection does not depend on that sibling module's own import
    surface.
    """
    text = template_path.read_text(encoding="utf-8")
    if _ANCHOR_START not in text or _ANCHOR_END not in text:
        return {}
    block = text.split(_ANCHOR_START, 1)[1].split(_ANCHOR_END, 1)[0]
    match = re.search(r"```ya?ml\s*\n(.*?)```", block, re.DOTALL)
    if not match:
        return {}
    parsed = yaml.safe_load(match.group(1))
    return parsed if isinstance(parsed, dict) else {}


class TestTaughtSetHasEightKindsIncludingDiscriminationRule:
    """angle: criterion — the AC-literal happy path: parse the real anchor,
    assert the eighth key and its distinguishing rule are present."""

    def test_taught_set_has_eight_kinds_including_discrimination_rule(self) -> None:
        # covers: TQ-500f-1
        # angle: criterion
        """WRONG VERSION THIS CATCHES: 'misspell the taught-set key' (AC's
        own INTENDED must_catch note, e.g. 'discriminaton' or
        'discriminations') — the exact-key assertion below fails on any
        spelling variant, and a rule that only repeats the word
        'discrimination' without the 'wrong version' / 'red' language would
        also fail the fragment check, catching a rule that names the kind
        but never states what makes it different from criterion."""
        assert _TEMPLATE_PATH.is_file(), f"taught-side source missing: {_TEMPLATE_PATH}"

        taught = _load_taught_angles(_TEMPLATE_PATH)
        assert taught, (
            f"{_TEMPLATE_PATH} has no <!-- TAUGHT-TEST-ANGLES:START/END --> "
            f"anchor (or it parsed empty)"
        )

        assert len(taught) == 8, (
            f"taught set must have exactly 8 kinds (7 existing + "
            f"discrimination), got {len(taught)}: {sorted(taught.keys())}"
        )

        assert "discrimination" in taught, (
            f"taught set must include the exact key 'discrimination', "
            f"got: {sorted(taught.keys())}"
        )

        rule = taught["discrimination"]
        assert isinstance(rule, str) and rule.strip(), (
            "discrimination's taught rule must be a non-empty string, "
            f"got: {rule!r}"
        )
        rule_lower = rule.lower()
        missing_fragments = [
            frag for frag in _REQUIRED_RULE_FRAGMENTS if frag not in rule_lower
        ]
        assert not missing_fragments, (
            f"discrimination's rule must state the AC's distinguishing "
            f"criterion (missing phrase(s) {missing_fragments} — the rule "
            f"must say the test goes red under a NAMED wrong version, not "
            f"only when the code is absent). Actual rule: {rule!r}"
        )

        # Every other (pre-existing) taught entry must still carry a
        # non-empty rule — an additive change must not blank out a sibling
        # entry while inserting the new one.
        for name, other_rule in taught.items():
            assert isinstance(other_rule, str) and other_rule.strip(), (
                f"angle '{name}' must keep a non-empty distinguishing rule"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
