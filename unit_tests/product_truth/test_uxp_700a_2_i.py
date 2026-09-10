"""
MODULE: test_uxp_700a_2_i
GOAL: Pin the shape of the store index the product-truth generator produces for a
    record that holds zero artifacts: every derived lookup (by_component, by_entity,
    by_flow, by_ac) must be a PRESENT key whose value is an empty collection, never a
    missing key. An absent map and an empty map are indistinguishable to a reader that
    only checks truthiness, so this test asserts presence explicitly.
BUSINESS CONTEXT: AC UXP-700a-2-i. depends_on UXP-700a-2 (the generator producing an
    index from zero artifacts with no hand-written file). This ticket constrains the
    SHAPE of that index once produced: "the state 'this lookup was never written' does
    not occur, so an empty result is the only thing a reader has to interpret."
ARCHITECTURE: Uses a self-contained tempdir fixture that mirrors the minimal
    product-truth store layout (flows/, mock-data/, index.json, acceptance-criteria/),
    seeded with an index.json that declares zero artifacts and, deliberately, has NONE
    of the four derived keys written yet -- the "never written" starting state the AC
    names. test_zero_artifact_index_has_every_derived_lookup_present_and_empty calls the
    generator directly (angle: boundary). test_uxp_700a_2_i_reachable_from_entry_point
    invokes the real CLI script (docs/product-truth/scripts/generate_product_truth.py)
    as a subprocess against an equivalent fixture (angle: reachability) -- the real
    production entry point, per the CLI-script branch of the Reachability Entry-Point
    Resolution procedure: the script has a main() guarded by
    `if __name__ == "__main__":` with argparse, so a subprocess invocation of that
    script is the entry point, not a direct call to generate().

NOTE ON RED BASELINE (see unit_tests/README.md #1 "A passing test is not evidence
    until you know it can fail"): both assertions in this file are negative controls --
    they assert an absence of the exact "missing key" bug the AC forbids. The current
    generate_product_truth.py already writes by_component/by_entity/by_flow/by_ac
    unconditionally (write_index() assigns them with no "if truthy" guard), so BOTH
    tests in this file pass green on arrival by construction; there is no red phase to
    capture from a plain run. A mutation proof was performed instead (documented in the
    ticket's sign-off comment): write_index() was temporarily patched to omit an empty
    by_component key (`if by_component: index["by_component"] = by_component`, the
    exact class of bug the AC exists to forbid), both tests below went RED
    (KeyError / AssertionError), and reverting restored green. This is the sanctioned
    substitute the README names for this exact test shape.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import the
# generator directly for the boundary test.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_REAL_GENERATOR_SCRIPT = _SCRIPTS_DIR / "generate_product_truth.py"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402

# The four derived lookups the AC names: "belonging to a component, to an entity, to a
# journey [flow], and to an acceptance criterion". Named once here (per the AC's own
# notes: "Named here rather than in criteria so the criterion survives a rename of the
# index fields") so a rename only needs to change this list, not every assertion below.
_DERIVED_LOOKUP_KEYS = ("by_component", "by_entity", "by_flow", "by_ac")


def _make_zero_artifact_store(tmp: Path) -> Path:
    """Build a minimal product-truth store holding zero artifacts.

    Layout: <tmp>/product-truth/{flows,mock-data}/ (both empty) and
    <tmp>/product-truth/index.json declaring zero artifacts. Deliberately does NOT
    pre-populate by_component/by_entity/by_flow/by_ac -- those keys are, at this
    point, in the "never written" state the AC names; the generator run is what must
    put them there, present and empty. <tmp>/acceptance-criteria/ is also created
    (empty) so AC_STORE.rglob does not touch a nonexistent directory.

    Returns the product-truth store root (the directory the generator calls STORE).
    """
    store = tmp / "product-truth"
    (store / "flows").mkdir(parents=True)
    (store / "mock-data").mkdir(parents=True)
    (tmp / "acceptance-criteria").mkdir(parents=True)
    index = {"artifacts": [], "entity_registry": []}
    (store / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return store


class TestZeroArtifactIndexDerivedLookups(unittest.TestCase):
    """AC UXP-700a-2-i: the four derived lookups are present and empty, never absent."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)
        self.store = _make_zero_artifact_store(self.tmp)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_zero_artifact_index_has_every_derived_lookup_present_and_empty(self) -> None:
        # covers: UXP-700a-2-i
        # angle: boundary
        """Each of the four derived lookups is a present key whose value is empty.

        Implementation requirement: generate_product_truth.py's write_index() must
        assign by_component / by_entity / by_flow / by_ac on the index dict
        unconditionally -- never behind an "if truthy" guard that would omit the key
        when its computed value is empty. If this test goes green with no
        implementation change, that is expected (see module docstring "NOTE ON RED
        BASELINE") -- the guarantee is pinned by this test plus the mutation proof
        recorded in the ticket's sign-off comment, not by a red-to-green transition.
        """
        original_store, original_ac_store = gpt.STORE, gpt.AC_STORE
        gpt.STORE = self.store
        gpt.AC_STORE = self.tmp / "acceptance-criteria"
        try:
            gpt.generate(check=False, run_date="2026-09-09")
        finally:
            gpt.STORE, gpt.AC_STORE = original_store, original_ac_store

        index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))

        for key in _DERIVED_LOOKUP_KEYS:
            self.assertIn(
                key,
                index,
                f"derived lookup '{key}' is ABSENT from the index -- the AC forbids "
                "the 'never written' state; an empty result must be present instead.",
            )
            self.assertEqual(
                index[key],
                {},
                f"derived lookup '{key}' is present but not empty for a zero-artifact "
                f"store: {index[key]!r}",
            )

    def test_uxp_700a_2_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700a-2-i
        # angle: reachability
        """Invokes the real CLI entry point (subprocess) and asserts the behaviour.

        Entry point resolution (Reachability Entry-Point Resolution, step 1 -- CLI
        script): generate_product_truth.py exposes a main() guarded by
        `if __name__ == "__main__":` with argparse, invoked in production as
        `python docs/product-truth/scripts/generate_product_truth.py`. This test
        copies that real script (verbatim bytes, read from disk -- not re-typed) into
        a fixture store shaped like the real one, then runs it as a subprocess with
        real argv. Importing generate_product_truth and calling generate() directly
        (as the sibling boundary test above does) does NOT satisfy this angle on its
        own; this test exists specifically to prove the behaviour survives the
        CLI-argument-parsing path a direct import bypasses.
        """
        scripts_dir = self.store / "scripts"
        scripts_dir.mkdir(parents=True)
        script_copy = scripts_dir / "generate_product_truth.py"
        script_copy.write_bytes(_REAL_GENERATOR_SCRIPT.read_bytes())
        # generate_product_truth imports product_truth_derivations; deploy the
        # whole "*.py" glob the way build.py does so the copy can actually run.
        for _sibling in sorted(_SCRIPTS_DIR.glob("*.py")):
            (script_copy.parent / _sibling.name).write_bytes(_sibling.read_bytes())

        result = subprocess.run(
            [sys.executable, str(script_copy), "--now", "2026-09-09", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"CLI entry point exited non-zero.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        index = json.loads((self.store / "index.json").read_text(encoding="utf-8"))
        for key in _DERIVED_LOOKUP_KEYS:
            self.assertIn(
                key,
                index,
                f"derived lookup '{key}' is ABSENT from the index after the real CLI "
                "entry point ran -- reachability must reproduce the same guarantee "
                "the direct-call boundary test pins.",
            )
            self.assertEqual(index[key], {}, f"derived lookup '{key}' is present but not empty: {index[key]!r}")


if __name__ == "__main__":
    unittest.main()
