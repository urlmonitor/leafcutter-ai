"""AR-400a-4 -- the reference for specialist definitions quotes, word for word, the line the build
prints for each ability-reference fault kind (TDD red phase: the gate's kinds and the doc section
do not exist yet).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400a-4.yaml.
(AR-400b-5 is a docs AC with ``test_required: false`` and no test_spec: it has no test here.)

CONTRACT FOR THE DOC AUTHOR (reference-author): docs/reference/agent-template-frontmatter.md must
contain, verbatim, the finding line this fixture makes the validator print for each kind -- the
line WITHOUT the door's ``ERROR:`` prefix. The fixture is one copied package slice holding four
planted specialists, so the example names are fixed:

    kind                               specialist   ability / text        line
    ability does not exist             probe-nx     ghost-ability         40
    ability exists but is not granted  probe-agent  knowledge-query       88   (grants only signoff)
    differs only in case               probe-author Write-C4-Diagram      40   (grants write-c4-diagram)
    names an agent, not an ability     probe-coder  sql-query             40   (spawn_allowlist: sql-query)

Run the validator over such a slice, copy the four lines, paste them in. A paraphrase, or a wording
change in code that the doc did not follow, fails here.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "prompt_assembly"))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

DOC = Path(F.REPO_ROOT) / "docs" / "reference" / "agent-template-frontmatter.md"
# kind -> (specialist, body line, line number, grants, spawn)
EXAMPLES = {
    F.NONEXIST: ("probe-nx", "Load `.claude/skills/ghost-ability/SKILL.md` and follow it", 40, (), ()),
    F.UNGRANTED: ("probe-agent", "load the `knowledge-query` skill to search the graph", 88, ("signoff",), ()),
    F.CASE: ("probe-author", "Step 1 -- Load the Write-C4-Diagram Skill", 40, ("write-c4-diagram",), ()),
    F.AGENT: ("probe-coder", "Use the `sql-query` skill if available to scaffold the object", 40, (), ("sql-query",)),
}


class TestReferenceDocQuotesTheBuild(unittest.TestCase):
    def test_reference_example_failure_lines_match_build_output_verbatim(self):
        # covers: AR-400a-4
        # angle: real_artifact
        # must_catch: the doc paraphrases a failure line
        # must_catch: a fault kind's wording changes in code and not in the doc
        """For each of the four fault kinds, build the fixture that reproduces it, run the registry
        validator, and assert the line it prints for that fault appears verbatim in the reference."""
        with tempfile.TemporaryDirectory() as tmp:
            root = H.make_slice(tmp)
            for name, line, at, grants, spawn in EXAMPLES.values():
                F.plant(root, name, [line], grants=grants, spawn=spawn, at_line=at)
            rc, out = H.cli(root)
        doc = DOC.read_text(encoding="utf-8")
        not_printed, not_in_doc = [], []
        for kind, (name, _line, _at, _grants, _spawn) in EXAMPLES.items():
            printed = F.of_kind(out, kind, subject=name)
            if len(printed) != 1:
                not_printed.append((kind, name, printed))
            elif printed[0] not in doc:
                not_in_doc.append(printed[0])
        self.assertEqual(not_printed, [], f"the validator did not print exactly one line per fixture fault: {out[-1500:]}")
        self.assertEqual(not_in_doc, [], f"{DOC.name} does not quote these printed lines verbatim")
        self.assertEqual(rc, 1, out[-800:])


if __name__ == "__main__":
    unittest.main()
