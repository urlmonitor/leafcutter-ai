"""AR-400c-4 -- a build of the package's own tree prints no ability or hand-off warnings and passes
(TDD red phase; the goal's own acceptance run).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400c-4.yaml.
The "ability and hand-off part of the run" is the output of the two producers the criteria name: the
registry validator and the ability gate. Both are reached through their real doors: the validator CLI,
and ``scripts/build.py --validate-only`` (the validation phase of a real build, which runs the validator
AND the ability gate, without the ~60 s deploy). The full deploy is the session's shared reference build,
requested as a reader: its fixture refuses to hand over a layout whose build did not exit 0.

HONEST SCOPE: on the real tree today the clean-output halves hold (the earlier AR-400 slices fixed
their causes); what is red is the control row -- a copy with ticket-supervisor's llm-expert entry
restored must be REFUSED (an error, not a warning), which needs the AR-400f-1 gate.
"""

from __future__ import annotations

import os
import sys
import unittest

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402


def _warning_lines(out: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines() if "[WARNING]" in ln]


@pytest.mark.shared_layout_reader
def test_real_build_ability_and_handoff_output_has_zero_warning_lines(shared_reference_layout):
    # covers: AR-400c-4
    # angle: real_artifact
    # must_catch: a residual warning is hidden by filtering stdout rather than fixing its cause
    """The shared reference build of the checked-out package exited 0 (its fixture raises otherwise) and
    left a manifest; the validation phase of a real build (validator + ability gate) and the validator
    CLI print zero ``[WARNING]`` lines and exit 0. Control row: the same build door over a copy with
    ticket-supervisor's llm-expert entry restored refuses it with a redundant-entry finding that is not
    a warning -- so the clean output is not a check that stopped looking, and no warning is being
    filtered out of the output."""
    assert (X.Path(shared_reference_layout) / ".build_manifest.json").is_file()
    rc, out = X.real_validate_only()
    v_rc, v_out = F.real_cli()
    assert rc == 0, out[-1500:]
    assert v_rc == 0, v_out[-1500:]
    assert _warning_lines(out) == [], _warning_lines(out)
    assert _warning_lines(v_out) == [], _warning_lines(v_out)
    c_rc, c_out = X.run_build(X.restored_copy(), X.restored_copy().parent, "--validate-only")
    hits = X.hand_off_hits(c_out, X.REDUNDANT)
    assert len(hits) == 1 and X.names_all(hits[0], "ticket-supervisor", "llm-expert", X.MACRO), c_out[-1200:]
    assert c_rc != 0, "the build must refuse the restored leftover, not warn about it"
    assert X.redundancy_warnings(c_out) == [], X.redundancy_warnings(c_out)


def test_examined_specialists_equals_definitions_in_tree():
    # covers: AR-400c-4
    # angle: boundary
    """The figure each door reports next to 'definitions' equals the number of specialist definitions
    derived independently from templates/agents/ and the registry (two derivations that must agree),
    never a hard-coded count."""
    expected = X.definitions_in_tree(F.REPO_ROOT)
    named = X.E.declared(F.REPO_ROOT)
    assert expected == len(named) == H.expected_counts(F.REPO_ROOT)[0], (expected, len(named))
    assert expected >= 60, f"control: implausibly few definitions ({expected})"
    for where, text in (("validator", F.real_cli()[1]), ("build", X.real_validate_only()[1])):
        reported = H.reported(text, "definition")
        assert reported, f"{where}: the run no longer states how many specialists it examined"
        assert set(reported) == {expected}, f"{where}: reported {reported}, tree has {expected}"


class TestReintroducedWarningCause(unittest.TestCase):
    def test_reintroducing_a_2026_10_12_warning_cause_fails_the_run(self):
        # covers: AR-400c-4
        # angle: discrimination
        """In a copy of the real tree, ticket-supervisor lists llm-expert beside
        ``__ticket_phase_agents__`` again (declaration and derived copy). The validator CLI fails with the
        redundant-entry finding naming ticket-supervisor, llm-expert and the covering entry -- and prints
        no redundancy ``[WARNING]``, which is how line 297 of the 2026-10-12 report looked."""
        root = X.restored_copy()
        self.assertIn("llm-expert", X.declared_spawn_of(root, "ticket-supervisor"))
        rc, out = H.cli(root)
        hits = X.hand_off_hits(out, X.REDUNDANT)
        self.assertEqual(len(hits), 1, f"expected one redundant-entry finding: {out[-1200:]}")
        self.assertTrue(X.names_all(hits[0], "ticket-supervisor", "llm-expert", X.MACRO), hits[0])
        self.assertEqual(X.redundancy_warnings(out), [], "the finding must be a failure, not a warning")
        self.assertEqual(rc, 1, out[-800:])
        self.assertEqual(F.of_kind(out, F.UNGRANTED) + F.of_kind(out, F.NONEXIST), [], "only the redundancy may be wrong in the copy")


if __name__ == "__main__":
    unittest.main()
