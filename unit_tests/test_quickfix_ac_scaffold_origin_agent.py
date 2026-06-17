"""
unit_tests/test_quickfix_ac_scaffold_origin_agent.py

Content-guard test: the /quick-fix Phase 1 Step 1.3 AC YAML scaffold block
in templates/skills/quick-fix/SKILL.md must include an ``origin_agent`` field.

Background
----------
AC ACS-700 documents the bug where AC files authored by /quick-fix omit
``origin_agent``, causing the check-ac-governance pre-commit hook
(requirement ACS-400c-1 — "new AC files must have origin_agent") to
hard-block the commit.  The root cause is that the scaffold template at
Phase 1 Step 1.3 does not include ``origin_agent:`` in the Required fields
yaml block.

This test MUST FAIL (red) until ``origin_agent:`` is added to the fenced
```yaml``` block that follows the "### Step 1.3" heading in
templates/skills/quick-fix/SKILL.md.
"""
# @ac-tag: ACS-700

import os
import re
import unittest

# ---------------------------------------------------------------------------
# Resolve the path to the skill template relative to this test file so the
# test works regardless of which directory the test runner is invoked from.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_SKILL_MD = os.path.join(
    _REPO_ROOT,
    "templates",
    "skills",
    "quick-fix",
    "SKILL.md",
)


def _extract_step_1_3_yaml_scaffold(text: str) -> str:
    """Return the contents of the first ```yaml fenced block after
    the '### Step 1.3' heading.

    Raises AssertionError if either the heading or the fenced block cannot be
    found — that signals a structural change to the template that would itself
    need investigation.
    """
    # Locate the "### Step 1.3" heading (case-insensitive suffix matching).
    step_match = re.search(r"^###\s+Step\s+1\.3\b", text, re.MULTILINE | re.IGNORECASE)
    if step_match is None:
        _msg = (
            "Could not locate '### Step 1.3' heading in "
            f"{_SKILL_MD}. The template structure may have changed."
        )
        raise AssertionError(_msg)

    text_after_heading = text[step_match.end():]

    # Find the first ```yaml ... ``` block after the heading.
    fence_match = re.search(
        r"```yaml\s*\n(.*?)```",
        text_after_heading,
        re.DOTALL,
    )
    if fence_match is None:
        _msg = (
            "Could not find a ```yaml fenced block after '### Step 1.3' "
            f"in {_SKILL_MD}. The scaffold may have been restructured."
        )
        raise AssertionError(_msg)

    return fence_match.group(1)


class TestQuickFixAcScaffoldOriginAgent(unittest.TestCase):
    """The /quick-fix Step 1.3 AC YAML scaffold must include origin_agent.

    ACS-700: AC files authored by /quick-fix must include ``origin_agent`` so
    they satisfy ACS-400c-1 and pass the check-ac-governance pre-commit hook
    without requiring a mid-commit patch by the commit agent.
    """

    @classmethod
    def setUpClass(cls):
        try:
            with open(_SKILL_MD, "r", encoding="utf-8") as fh:
                cls.full_content = fh.read()
        except OSError as exc:
            raise AssertionError(
                f"Could not read skill template at {_SKILL_MD}: {exc}"
            ) from exc
        cls.scaffold_block = _extract_step_1_3_yaml_scaffold(cls.full_content)

    def test_ac_acs700_scaffold_contains_origin_agent_field(self):
        # covers: ACS-700
        """The Step 1.3 Required-fields yaml scaffold must contain origin_agent:.

        ACS-700 / ACS-400c-1 linkage: the check-ac-governance pre-commit hook
        rejects any new AC YAML file that lacks an ``origin_agent`` field.
        When /quick-fix uses this scaffold to create an AC file and the commit
        is attempted, the hook hard-blocks the commit — the commit agent must
        then inject ``origin_agent`` manually to recover.

        To make this test green: add a line ``origin_agent: <agent-or-user>``
        inside the ```yaml``` block that follows '### Step 1.3 — Write the AC
        YAML' in templates/skills/quick-fix/SKILL.md.
        """
        # Match the YAML key 'origin_agent' as a standalone field (start of
        # line, optional leading whitespace, then 'origin_agent:').
        key_pattern = re.compile(r"^\s*origin_agent\s*:", re.MULTILINE)
        self.assertRegex(
            self.scaffold_block,
            key_pattern,
            msg=(
                "The /quick-fix Step 1.3 AC YAML scaffold does not contain an "
                "'origin_agent:' field.  AC files generated from this scaffold "
                "will be rejected by the check-ac-governance pre-commit hook "
                "(ACS-400c-1), hard-blocking the commit until origin_agent is "
                "injected manually.  Add 'origin_agent: <agent-or-user>' to "
                "the Required fields block in "
                "templates/skills/quick-fix/SKILL.md Phase 1 Step 1.3 "
                "(ACS-700)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
