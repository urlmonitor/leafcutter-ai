"""
Tests for TQ-600a-11 -- "The fast YAML parser earns its place at the one
whole-store walk whose volume pays for it, and nowhere else."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-11.yaml
(test_spec + test_rationale; that record's YAML wins wherever a summary here
differs). This file covers ALL FIVE of that AC's test_spec entries as amended
2026-10-08 (the second `amended_by` entry). The amendment is a RETRACTION:
the migration to the fast parser was narrowed from ~85 call sites to the one
whole-store walk in scripts/generate_agent_cards.py, and three clauses of the
original text (end-to-end speedups at the validation gate, "every reader
resolves through the accessor", the deployed-hook reachability check) were
struck. This file therefore asserts a NEGATIVE invariant -- where the
permissive C-backed parser may not go -- next to the one speed claim that
survived. Do not reinstate the struck tests.

Cost discipline (a previous speed change here added 667s of verification to
save 190s): the two timing tests each need one whole-store walk per arm
(~2s fast + ~20s pure-Python) and nothing else -- no deployed layout, no
second worktree, no build.py spawn. The behavioural gate test runs one small
subprocess; the reachability tests run the build phases into a tmp dir.

Helpers (call-site deriver, counting walk runner, tmp-root builder, the
declared set) live in the sibling _test_helpers_tq_600a_11.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pytest
import yaml

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
sys.path.insert(0, str(_AC_STORE_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_HERE))

from _test_helpers_tq_600a_11 import (  # noqa: E402
    DECLARED_C_PARSER_SITES,
    derive_c_parser_resolutions,
    is_decision_point,
    real_store_paths,
)


class TestTq600a11ParserSpeed(unittest.TestCase):
    """The PARSER claim -- measures the parser, not any entry point."""

    @pytest.mark.timing_ratio
    def test_tq600a_11_store_sweep_is_at_least_five_times_faster_than_the_pure_python_parser(self):
        # covers: TQ-600a-11
        # angle: real_artifact
        """
        Over the REAL on-disk store, in one process, time a full sweep with the
        pure-Python parser and a full sweep through the shared accessor; assert
        the RATIO (never an absolute second count) is at least 5. UNCHANGED by
        the 2026-10-08 amendment: this measures the PARSER, so a green result is
        NOT evidence that any gate, hook or check got faster -- the next test
        is the one that measures an entry point.
        """
        from yaml_safe_loader import load_yaml_file  # the module under test

        paths = real_store_paths()
        self.assertGreater(
            len(paths),
            0,
            "the real AC store resolved to zero files -- cannot time a sweep over nothing",
        )

        start = time.perf_counter()
        for path in paths:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        pure_seconds = time.perf_counter() - start

        start = time.perf_counter()
        for path in paths:
            load_yaml_file(path)
        accessor_seconds = time.perf_counter() - start

        self.assertGreater(
            accessor_seconds,
            0.0,
            "accessor sweep measured as zero seconds -- timer resolution problem",
        )
        ratio = pure_seconds / accessor_seconds
        self.assertGreaterEqual(
            ratio,
            5.0,
            f"accessor sweep was only {ratio:.2f}x faster than the pure-Python "
            f"sweep over {len(paths)} files (pure={pure_seconds:.2f}s, "
            f"accessor={accessor_seconds:.2f}s) -- the AC requires at least 5x.",
        )


class TestTq600a11CParserSeam(unittest.TestCase):
    """The NEGATIVE invariant: where the permissive parser may not go."""

    def test_tq600a_11_no_undeclared_call_site_resolves_the_c_backed_parser(self):
        # covers: TQ-600a-11
        # angle: seam
        """
        Derive, from the source and never from the declared set, every call
        site that resolves the C-backed parser (shared accessor OR the inline
        getattr(yaml, "CSafeLoader", ...) idiom) and assert it EQUALS the
        declared set. An undeclared adopter fails; so does a declared site that
        no longer resolves it (stale declaration). Also assert that no derived
        or declared site is a commit-guardian hook, validate_ac_schema.py or
        anything else that decides BLOCK or PASS, and that the set is
        NON-EMPTY so deleting the last adopter is a failure, not a vacuous
        pass. Nothing is asserted about files that name the pure-Python parser.
        """
        derived = derive_c_parser_resolutions()

        self.assertTrue(
            derived,
            "the derivation found NO C-parser call site at all -- either the "
            "last adopter was removed (update the AC) or the derivation broke",
        )
        undeclared = sorted(derived - DECLARED_C_PARSER_SITES)
        stale = sorted(DECLARED_C_PARSER_SITES - derived)
        self.assertEqual(
            (undeclared, stale),
            ([], []),
            f"derived C-parser call sites differ from the declared set. "
            f"UNDECLARED (resolve the C parser without a declaration -- admit "
            f"via the AC's four-part test or revert): {undeclared}; "
            f"STALE (declared but no longer resolve it): {stale}",
        )
        decision_points = sorted(
            site for site in derived | DECLARED_C_PARSER_SITES if is_decision_point(site[0])
        )
        self.assertEqual(
            decision_points,
            [],
            f"a C-parser call site is a commit-guardian hook, the store-wide "
            f"schema validation, or another BLOCK/PASS decision point, which "
            f"the AC forbids: {decision_points}",
        )


class TestTq600a11RequiredGateKeepsErrorFidelity(unittest.TestCase):
    """The behavioural guard on the retraction."""

    def test_tq600a_11_the_required_store_validation_gate_rejects_a_record_the_c_parser_accepts(self):
        # covers: TQ-600a-11
        # angle: discrimination
        """
        Feed the REAL gate (scripts/ac_store/validate_ac_schema.py, run as the
        required PR check runs it) a record containing a tab inside a flow
        sequence. Assert it exits non-zero with a YAML parse error; in the SAME
        test assert the accessor parses that identical text to {'key': []}
        without raising, and that the pure-Python parser rejects it -- so the
        divergence is proven real on this install and the gate sits on the
        strict side of it. Goes RED if the gate is re-routed onto the accessor
        (it would then parse to a dict with no 'id', be skipped as "not an AC
        file", and exit 0). Executes the gate; never greps it for SafeLoader.

        The malformed text is a hand-typed literal on purpose: a serializer
        cannot emit a tab inside a flow sequence, and the malformation IS the
        input under test.
        """
        from yaml_safe_loader import load_yaml_text

        malformed = "key: [\t]\n"

        self.assertEqual(
            load_yaml_text(malformed),
            {"key": []},
            "the accessor must parse a tab-in-flow-sequence to an empty list "
            "without raising -- if it raises, this install has no C parser and "
            "the divergence this AC guards against cannot be demonstrated here",
        )
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(malformed)

        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "TQ-600a-11-tab-in-flow-sequence.yaml"
            record.write_text(malformed, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(_AC_STORE_DIR / "validate_ac_schema.py"), str(record)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(_REPO_ROOT),
            )
        self.assertNotEqual(
            result.returncode,
            0,
            f"the required gate ACCEPTED a record the pure-Python parser "
            f"rejects (exit 0) -- it has been re-routed onto the permissive "
            f"parser. stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "YAML parse error",
            result.stderr,
            f"the gate failed, but not by reporting the parse failure as a "
            f"violation -- stderr={result.stderr!r}",
        )


class TestTq600a11Reachability(unittest.TestCase):
    """The card phase runs the way build.py runs it: from the package tree."""

    def test_tq600a_11_the_card_phase_runs_the_way_the_build_runs_it(self):
        # covers: TQ-600a-11
        # angle: reachability
        """
        In a FRESH interpreter whose only sys.path entry is scripts/ (how
        build.py runs its phases), run the real "Agent cards" phase
        (build_phases_agent_validation.build_agent_cards, the function
        build.py registers) against a tmp target root holding one agent
        template and a registry. Assert the phase completes and writes that
        agent's card. Nothing is asserted about AC ids: cards no longer carry
        AC-store data (the walk was removed 2026-10-09).
        """
        agent = "reachability-stub"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates" / "agents").mkdir(parents=True)
            (root / "templates" / "agents" / f"{agent}.md").write_text(
                f"---\nname: {agent}\ndescription: reachability stub\n---\nbody\n",
                encoding="utf-8",
            )
            (root / "config").mkdir()
            (root / "config" / "agent_registry.json").write_text(
                json.dumps([{"id": agent}]), encoding="utf-8"
            )

            script = (
                "import sys\n"
                f"sys.path.insert(0, {str(_SCRIPTS_DIR)!r})\n"
                "from pathlib import Path\n"
                "from build_phases_agent_validation import build_agent_cards\n"
                f"written = build_agent_cards(Path({str(root)!r}), {{}}, False, True)\n"
                "print('WRITTEN', written)\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root),
            )
            self.assertEqual(
                result.returncode,
                0,
                f"the card-generation phase did not run the way the build runs "
                f"it -- stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            card = root / "docs" / "agents" / "cards" / f"{agent}.card.md"
            self.assertTrue(card.is_file(), f"phase wrote no card at {card}: {result.stdout!r}")

    def test_tq600a_11_the_vestigial_deploy_map_entry_still_deploys_an_importable_accessor(self):
        # covers: TQ-600a-11
        # angle: deployed
        """
        The amended AC lets the now-vestigial AC_STORE_DEPLOY_MAP entry for the
        accessor be pruned OR kept; while it is kept, the DEPLOYED copy must
        still import. Runs the real deploy phase (build_ac_store) into a tmp
        target and imports the deployed file in a fresh interpreter -- a
        source-tree import is blind to a manifest gap. If the entry is pruned,
        replace this test with "no deployed module imports the accessor".
        Cheap by design: one phase function, not a build.py spawn.
        """
        from build_phases_ac_store import build_ac_store

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            build_ac_store(target, {}, False, True)
            deployed_dir = target / "scripts" / "ac_store"
            self.assertTrue(
                (deployed_dir / "yaml_safe_loader.py").is_file(),
                "yaml_safe_loader.py is missing from the deployed ac_store/ -- "
                "the deploy-map entry was pruned (then replace this test) or broke",
            )
            script = (
                "import sys\n"
                f"sys.path.insert(0, {str(deployed_dir)!r})\n"
                "from yaml_safe_loader import load_yaml_text\n"
                "print('LOADED', load_yaml_text('a: 1\\n'))\n"
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tmp,
            )
        self.assertEqual(
            result.returncode,
            0,
            f"deployed accessor does not import -- stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn("LOADED {'a': 1}", result.stdout)


if __name__ == "__main__":
    unittest.main()

# DECISION HISTORY
# ================================================================================
# - 2026-10-08 [test-writer] (classification: test_drift): realigned this file to
#   TQ-600a-11's 2026-10-08 amendment. Replaced the validation-gate end-to-end
#   timing test (retracted claim; both arms were identical code, 1.00x), the
#   "no reader names the pure-Python parser" allowlist seam test (inverted by
#   the amendment), and the deployed-commit-hook reachability test (no hook
#   uses the accessor now). The CI-gated ratio and best-of-5 machinery went
#   with the test it served. The surviving timing test asserts unconditionally,
#   as the AC specifies; the 5x floor against a 10-13x expectation is its only
#   headroom for host contention.
# - 2026-10-08 [test-writer]: moved the helpers into
#   _test_helpers_tq_600a_11.py to stay under the 400-measured-line file-size
#   limit; no assertion changed.
# - 2026-10-09 [python-coder/agent-cards-static]: deleted
#   TestTq600a11AgentCardWalk (it benchmarked _scan_all_ac_assignments, which
#   was removed: the AC store is the source of truth, and caching it in
#   generated card markdown produced an uncommittable, permanently dirty tree).
#   Rewrote the reachability test to keep its surviving half -- the card phase
#   completes and writes the card under a fresh interpreter with only scripts/
#   on sys.path -- and dropped its assertion that an AC id is in the card, which
#   the change directly contradicts. Dead-test deletion, not softening.
