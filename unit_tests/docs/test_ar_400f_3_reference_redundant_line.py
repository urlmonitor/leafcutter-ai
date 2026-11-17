"""AR-400f-3 -- the frontmatter reference states that a hand-off declaration names each specialist once
(TDD red phase: the gate's finding and the doc text do not exist yet).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400f-3.yaml.

CONTRACT FOR THE DOC AUTHOR (reference-author): the `spawn_allowlist` part of
docs/reference/agent-template-frontmatter.md must contain, verbatim, the redundant-entry finding line
this fixture makes the validator print -- the line WITHOUT the door's ``ERROR:`` prefix. The fixture is
one copied package slice holding the specialist ``probe-supervisor`` whose ``spawn_allowlist`` declares
``__ticket_phase_agents__``, ``brainstorm-lead`` and ``llm-expert`` (llm-expert is a ticket-phase agent,
brainstorm-lead is not). Run the validator over such a slice, copy the line, paste it in. A paraphrase,
or a wording change in code that the doc did not follow, fails here.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "prompt_assembly"))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402

DOC = X.REPO_ROOT / "docs" / "reference" / "agent-template-frontmatter.md"


def _sections(text: str) -> list[str]:
    """The document split at every ``##``..``####`` heading (a table row outside a heading stays with it)."""
    return [part for part in re.split(r"(?m)^(?=#{2,4} )", text) if part.strip()]


class TestReferenceQuotesTheRedundantEntryLine(unittest.TestCase):
    def test_reference_redundant_entry_line_matches_build_output(self):
        # covers: AR-400f-3
        # angle: real_artifact
        # must_catch: the doc paraphrases the failure line
        # must_catch: the failure wording changes in code and not in the doc
        """Build the redundant-entry fixture, run the registry validator, and assert the one redundant-entry
        line it prints appears verbatim in a section of the reference that is about ``spawn_allowlist``."""
        with tempfile.TemporaryDirectory() as tmp:
            root = H.make_slice(tmp)
            X.plant_redundant(root)
            rc, out = H.cli(root)
        printed = X.hand_off_hits(out, X.REDUNDANT)
        self.assertEqual(len(printed), 1, f"the validator did not print exactly one redundant-entry line: {out[-1200:]}")
        self.assertEqual(rc, 1, out[-800:])
        quoting = [s for s in _sections(Path(DOC).read_text(encoding="utf-8"))
                   if printed[0] in s and "spawn_allowlist" in s]
        self.assertTrue(quoting, f"{DOC.name} does not quote this printed line verbatim in a spawn_allowlist section: {printed[0]}")


if __name__ == "__main__":
    unittest.main()
