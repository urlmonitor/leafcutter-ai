"""AR-400d-5 -- the reference's example ``skills:`` declaration with ``provided_by`` is valid, and
the shape check refuses it once its value is changed to an unknown one (TDD red phase: the
reference does not document the marking yet).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400d-5.yaml.
The block is EXTRACTED from docs/reference/agent-template-frontmatter.md (a fenced ``yaml`` block that
holds a ``skills:`` list with a ``provided_by`` key), placed into a planted specialist's frontmatter
in a copied package slice, and checked by the build's own ability gate
(``agent_ability_gate.ability_errors``, whose 'malformed' findings are the declaration-shape check).
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "prompt_assembly"))
sys.path.insert(0, str(Path(HERE).resolve().parents[1] / "scripts"))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
from agent_ability_gate import ability_errors  # noqa: E402

DOC = F.REPO_ROOT / "docs" / "reference" / "agent-template-frontmatter.md"
YAML_BLOCK = re.compile(r"^```ya?ml\n(.*?)^```", re.DOTALL | re.MULTILINE)


def example_skills() -> list:
    """The ``skills:`` entries of the first yaml block in the reference that uses ``provided_by``."""
    for m in YAML_BLOCK.finditer(DOC.read_text(encoding="utf-8")):
        if "provided_by" in m.group(1):
            return (yaml.safe_load(m.group(1)) or {}).get("skills") or []
    return []


def malformed_in(grants: list) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = H.make_slice(tmp)
        F.plant(root, "probe-coder", ["Apply the `postgres` skill before writing SQL"], grants=tuple(grants))
        return [m for m in ability_errors(root) if "malformed" in m]


class TestReferenceExample(unittest.TestCase):
    def test_reference_example_declaration_passes_shape_check(self):
        # covers: AR-400d-5
        # angle: real_artifact
        """Extract the example ``skills:`` block that documents provided_by, place it in a fixture
        specialist's frontmatter, and run the build's declaration-shape check: no finding. Changing
        its provided_by value to 'vendor' produces exactly one."""
        grants = example_skills()
        self.assertTrue(grants, f"{DOC.name} has no yaml example declaring a `skills:` entry with provided_by")
        self.assertTrue(any(isinstance(g, dict) and g.get("provided_by") == "project" for g in grants),
                        "the example must show the one accepted value, `provided_by: project`")
        self.assertEqual(malformed_in(grants), [], "the documented example fails the declaration-shape check")
        mutated = [dict(g, provided_by="vendor") if isinstance(g, dict) and "provided_by" in g else g for g in grants]
        found = malformed_in(mutated)
        self.assertEqual(len(found), 1, found)
        self.assertIn("vendor", found[0])


if __name__ == "__main__":
    unittest.main()
