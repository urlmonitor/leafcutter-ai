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
    STORE_ROOT as _STORE_ROOT,
    build_card_phase_root,
    derive_c_parser_resolutions,
    is_decision_point,
    real_store_paths,
    run_walk_arm,
    yaml_files_on_disk,
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


class TestTq600a11AgentCardWalk(unittest.TestCase):
    """The ENTRY-POINT claim, at the one call site where it is true."""

    @pytest.mark.timing_ratio
    def test_tq600a_11_the_agent_card_store_walk_beats_a_fifth_of_its_same_sitting_pure_python_baseline(self):
        # covers: TQ-600a-11
        # angle: real_artifact
        """
        Run scripts/generate_agent_cards.py::_scan_all_ac_assignments -- the
        walk build.py actually calls; its sibling _scan_ac_assignments has NO
        production caller, so timing it would time dead code -- over the REAL
        store twice in this process: as shipped, then with the loader resolver
        forced to the pure-Python SafeLoader. Asserts (a) fast <= 1/5 of pure,
        as a ratio; (b) both arms return EQUAL output; (c) each arm's
        parsed-file count is equal to the other's AND to the files on disk, so
        an arm that parsed nothing cannot pass; (d) both raw figures are in the
        failure message (and printed on every run) so "host loaded" and "walk
        left the accessor" are distinguishable. Never an absolute threshold.

        The fast arm runs first, so a cold page cache penalises the arm the
        claim favours -- the conservative direction.
        """
        import generate_agent_cards as gac

        on_disk = yaml_files_on_disk()
        fast_out, fast_n, fast_s = run_walk_arm(gac, gac.get_safe_yaml_loader)
        pure_out, pure_n, pure_s = run_walk_arm(gac, lambda: yaml.SafeLoader)

        figures = (
            f"fast={fast_s:.2f}s ({fast_n} files) pure-Python={pure_s:.2f}s "
            f"({pure_n} files) on_disk={on_disk} "
            f"ratio={pure_s / fast_s if fast_s else float('inf'):.2f}x (floor 5.0x)"
        )
        print(f"\n[TQ-600a-11 agent-card walk] {figures}")

        self.assertGreater(on_disk, 0, f"real store is empty -- {figures}")
        self.assertEqual(fast_n, pure_n, f"arms parsed different file counts -- {figures}")
        self.assertEqual(
            fast_n, on_disk, f"arms did not parse every record file on disk -- {figures}"
        )
        self.assertGreater(len(fast_out), 0, f"walk returned no groupings -- {figures}")
        self.assertEqual(fast_out, pure_out, f"arms returned different output -- {figures}")
        self.assertLessEqual(
            fast_s * 5.0,
            pure_s,
            f"agent-card store walk is not at least 5x faster than forced "
            f"pure-Python: either the walk has left the accessor or the host is "
            f"pathologically loaded -- {figures}",
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
    """The accessor's one caller is a build.py phase running from the package tree."""

    def test_tq600a_11_the_accessor_is_reachable_the_way_the_build_reaches_it(self):
        # covers: TQ-600a-11
        # angle: reachability
        """
        In a FRESH interpreter whose only sys.path entry is scripts/ (how
        build.py runs its phases -- the card generator then reaches
        scripts/ac_store/ through its own sys.path insertion, the fragile
        seam), run the real "Agent cards" phase
        (build_phases_agent_validation.build_agent_cards, the function
        build.py registers) against a tmp target root holding one agent
        template and one REAL AC record copied verbatim from the store. Assert
        the phase completes and the written card lists that AC under its
        agent -- i.e. the walk ran and its grouping was consumed, not merely
        imported.
        """
        records = sorted(_STORE_ROOT.rglob("TQ-600a-11.yaml"))
        self.assertEqual(len(records), 1, f"expected one TQ-600a-11.yaml, got {records}")
        record = records[0]
        data = yaml.safe_load(record.read_text(encoding="utf-8"))
        agent, ac_id = data["assigned_agent"], data["id"]
        self.assertEqual(data["status"], "active", "precondition: the walk only groups active ACs")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_card_phase_root(root, agent, record)

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
            self.assertIn(
                ac_id,
                card.read_text(encoding="utf-8"),
                "the card lacks the AC the store walk should have grouped under "
                "its agent -- the walk's result was not consumed",
            )

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
