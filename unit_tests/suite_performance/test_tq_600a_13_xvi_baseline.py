"""
Tests for TQ-600a-13-xvi -- what a whole-lane proof is measured against, and which tree main's shared-layout code builds.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xvi.yaml

Two properties of the proof's child session (main's plugins, the head's tests): the shared reference layout is built from
the HEAD (the code under test), and a whole-lane proof may not run fewer tests than main's own correctness lane collects
when the red verdict carries no count. See test_tq_600a_13_xvi.py for the assumed contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

from ._hold_harness import HoldService
from ._proof_harness import MAIN_ADDOPTS, SHARED_PLUGIN, driven
from ._workflow_jobs import REPO_ROOT

ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_SOURCE_ROOT"
PROBE = (
    "import json, os\n"
    "from scripts.suite_performance import _shared_layout_producer as producer, pytest_shared_reference_layout as plugin\n"
    "print(json.dumps([str(producer._WORKTREE_ROOT), str(plugin._WORKTREE_ROOT)]))\n"
)


def roots(env_extra):
    """The two ``_WORKTREE_ROOT`` values a fresh interpreter computes, with ``env_extra`` added to the environment."""
    env = {k: v for k, v in os.environ.items() if k != ENV_VAR}
    env.update(env_extra)
    done = subprocess.run([sys.executable, "-c", PROBE], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False, timeout=60)
    if done.returncode != 0:
        message = f"the probe failed: {done.stderr[-800:]}"
        raise AssertionError(message)
    return json.loads(done.stdout)


class TestTq600a13xviProofBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = HoldService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def test_tq_600a_13_xvi_the_shared_layout_is_built_from_the_head(self):
        # covers: TQ-600a-13-xvi
        # angle: seam
        """AC-xvi: main's pytest.ini names main's shared-layout plugin; the head's tree differs from main's. A lane test
        at the head asks the plugin and the producer behind it which root they build the shared layout from.

        Both answer the head (the proof's child session), so a ``shared_layout_reader`` test reads the head's deploy.
        With the override unset, a fresh interpreter computes exactly the root it always did (the post-merge run).

        Wrong versions caught: the layout is built from main's tree because main's modules are the ones imported (a fix
        to a template or build.py reads as failing; a head that breaks deployment reads as passing); the default path
        changes when the override is unset.
        """
        with driven(self.svc, kind="dnc", head={"other_ok": True, "probe": True}, main_addopts=f"{MAIN_ADDOPTS} -p {SHARED_PLUGIN}") as proof:
            self.assertEqual("true", proof.prepare.outputs.get("run_proof"), proof.prepare.log_text()[-1500:])
            self.assertEqual(["a", "other", "probe", "x", "y"], proof.ran(), proof.prove.log_text()[-2500:])
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-2500:])
        repo = str(REPO_ROOT)
        self.assertEqual([repo, repo], roots({}), "the default root must be unchanged when the override is unset")
        self.assertEqual([repo, repo], roots({ENV_VAR: ""}), "an empty override is no override")
        self.assertEqual(["/override/root"] * 2, roots({ENV_VAR: "/override/root"}))

    def test_tq_600a_13_xvi_a_whole_lane_may_not_shrink_below_mains_own_lane(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: a did-not-complete red run (its verdict carries no collected count). Main's own lane collects four tests;
        the head has taken two of them out of the lane and the rest pass.

        The proof fails and the log says why (``head lane ran 2 < baseline 4``): the baseline is a collect-only of main's
        lane under main's ini and plugins, so a missing count never turns the guard off.

        Wrong versions caught: the shrink guard is skipped whenever the verdict has no usable count, so a head that drops
        the tests that failed proves a green remainder.
        """
        with driven(self.svc, kind="dnc", head={"other_ok": True, "lane_marked": False}) as proof:
            self.assertEqual("true", proof.prepare.outputs.get("run_proof"), proof.prepare.log_text()[-1500:])
            self.assertEqual(["a", "other"], proof.ran())
            self.assertEqual("failure", proof.prove.conclusion, "a shrunken lane must not prove a fix")
            self.assertIn("head lane is missing 2 of 4 baseline tests", proof.prove.log_text())
            self.assertIn("break-glass", proof.prove.log_text())
        with driven(self.svc, kind="dnc", head={"other_ok": True}) as proof:  # the lane is whole: the same head, nothing dropped
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1800:])
            self.assertEqual(["a", "other", "x", "y"], proof.ran())

    def test_tq_600a_13_xvi_deleting_the_broken_test_and_adding_a_passing_one_is_not_a_fix(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: a did-not-complete red run; the head deletes a lane test of main's and adds a different, passing one, so
        its lane has the same size as main's and every test in it passes.

        The proof fails and the log names the missing test: the baseline is a set of ids, not a count.

        Wrong versions caught: the guard compares counts, so a delete-and-replace proves a fix.
        """
        with driven(self.svc, kind="dnc", head={"swap": True, "other_ok": True}) as proof:
            self.assertEqual(["a", "other", "x", "y"], proof.ran(), "every test of the head's lane passes and the lane has four tests")
            self.assertEqual("failure", proof.prove.conclusion, "replacing the broken test by another must not prove a fix")
            self.assertIn("test_x_fails_until_fixed", proof.prove.log_text())
            self.assertIn("head lane is missing 1 of 4 baseline tests", proof.prove.log_text())


if __name__ == "__main__":
    unittest.main()
