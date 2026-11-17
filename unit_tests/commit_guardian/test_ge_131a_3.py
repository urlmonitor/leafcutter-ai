"""GE-131a-3: the README row and the complexity-reduction skill state the rule
check-complexity applies, and say it is registered.

Backfill evidence: the doc edits landed first (ced744792). Each test ties a
documentation claim to the shipped configuration it describes, so the claim
cannot drift from the limit or from the registration. The assertion helpers
take document text as an argument so a demonstration can feed them a modified
copy without touching templates/.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARDIAN = ROOT / "templates" / "scripts" / "commit_guardian"
README = GUARDIAN / "README.md"
MANIFEST = GUARDIAN / "commit_guardian.json"
SKILL = ROOT / "templates" / "skills" / "complexity-reduction" / "SKILL.md"


def load_manifest(path=MANIFEST):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def max_score(manifest):
    return manifest["complexity"]["max_score"]


def readme_row(readme_text):
    rows = [ln for ln in readme_text.splitlines() if ln.startswith("| `check_complexity.py`")]
    assert len(rows) == 1, f"expected exactly one check_complexity.py row, found {len(rows)}"
    return rows[0]


def skill_step(skill_text, number):
    match = re.search(rf"^{number}\. \*\*Re-measure\*\*.*?(?=^\d+\. \*\*)", skill_text, re.S | re.M)
    assert match, "re-measure step not found in the skill"
    return " ".join(match.group(0).split())


def assert_row_states_ratchet(row, limit):
    flat = " ".join(row.split())
    assert f"(default: {limit})" in flat, f"row must state the configured limit {limit}"
    assert "new or crossing function" in flat
    assert "above the limit" in flat
    assert "already over the limit" in flat
    assert "previous committed score" in flat
    assert "any function" not in flat and "exceeds the cyclomatic" not in flat, "old blanket wording present"


def assert_skill_claims_registered(skill_text, manifest):
    assert "not registered" not in skill_text
    assert "where it is registered" not in skill_text
    assert "`check-complexity` are both registered in the default hook" in " ".join(skill_text.split())
    ids = [hook.get("id") for hook in manifest["hooks_manifest"]["hooks"]]
    assert "check-complexity" in ids, "skill claims registration but the manifest has no such hook"


def assert_step_states_acceptance(skill_text, limit):
    step = skill_step(skill_text, 4)
    assert "at or under the limit for a new or crossing function" in step
    assert "at or under its previous committed score" in step
    assert "already over" in step
    table = [ln for ln in skill_text.splitlines() if ln.startswith("| `check-complexity`")]
    assert len(table) == 1
    assert table[0].rstrip("| ").endswith(f"| {limit}"), "skill's quoted default differs from the configured limit"


class TestGe131a3(unittest.TestCase):
    def test_readme_row_states_ratchet_with_configured_limit(self):
        # covers: GE-131a-3
        # angle: criterion
        """Arm 1: the row states the configured limit and both ratchet cases."""
        assert_row_states_ratchet(readme_row(README.read_text(encoding="utf-8")), max_score(load_manifest()))

    def test_readme_row_rejects_old_blanket_wording(self):
        # covers: GE-131a-3
        # angle: discrimination
        """Arm 1: the pre-GE-131a-3 row must fail the helper (named wrong version)."""
        old = ("| `check_complexity.py` | `check-complexity` | Blocking | Blocks Python files where "
               "any function/method exceeds the cyclomatic complexity limit. | "
               "`complexity.max_score` (default: 15) | — |")
        with self.assertRaises(AssertionError):
            assert_row_states_ratchet(old, 15)

    def test_skill_says_registered_and_manifest_agrees(self):
        # covers: GE-131a-3
        # angle: seam
        """Arm 2: the skill claims registration and the manifest really registers it."""
        assert_skill_claims_registered(SKILL.read_text(encoding="utf-8"), load_manifest())

    def test_skill_claim_fails_when_registration_removed(self):
        # covers: GE-131a-3
        # angle: failure
        """Arm 2: with the manifest entry removed the claim must be refused."""
        manifest = load_manifest()
        hooks = manifest["hooks_manifest"]["hooks"]
        manifest["hooks_manifest"]["hooks"] = [h for h in hooks if h.get("id") != "check-complexity"]
        self.assertEqual(len(hooks) - 1, len(manifest["hooks_manifest"]["hooks"]))
        with self.assertRaises(AssertionError):
            assert_skill_claims_registered(SKILL.read_text(encoding="utf-8"), manifest)

    def test_skill_remeasure_step_states_what_check_accepts(self):
        # covers: GE-131a-3
        # angle: criterion
        """Arm 3: step 4 states both acceptance cases, tied to the configured limit."""
        assert_step_states_acceptance(SKILL.read_text(encoding="utf-8"), max_score(load_manifest()))


if __name__ == "__main__":
    unittest.main()
