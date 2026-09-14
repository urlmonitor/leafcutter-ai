"""
MODULE: unit_tests/ac_store/test_uxp700d2_done_proof_exempts_example.py
GOAL: The done-proof gate does not demand a covering test from the example
    product, and still demands one from the project's own record.
BUSINESS CONTEXT: UXP-700d-2 says no piece of the example product can be picked
    up as work. The ready-leaf scanner was the obvious pick-up surface, but it
    is not the only one: check_done_proof reads every staged AC at
    work_status done and reports the ones with no '# covers:' tag. The
    fern-and-fig records UXP-210a, UXP-210b and UXP-220a are done and have no
    covering test -- they describe a fictional plant shop, so no real test will
    ever cover them -- and the gate flagged all three the moment marking them
    as example content brought them into its diff scope. A gate that requires
    test proof from example content is treating it as work.
ARCHITECTURE: Drives check_staged_done_proofs against real temp AC files rather
    than asserting on source text, so the test exercises the predicate instead
    of its spelling. The second case is the load-bearing one: it fails if the
    exemption is ever widened to swallow the project's own records, which would
    silently disable the whole gate.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GUARDIAN = _REPO_ROOT / "scripts" / "commit_guardian"
if str(_GUARDIAN) not in sys.path:
    sys.path.insert(0, str(_GUARDIAN))

import check_done_proof as cdp  # noqa: E402


def _write_ac(directory: Path, ac_id: str, product: str | None) -> Path:
    body = [f"id: {ac_id}", "work_status: done", "readiness: approved"]
    if product is not None:
        body.append(f"product: {product}")
    path = directory / f"{ac_id}.yaml"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


class TestDoneProofExemptsExampleContent(unittest.TestCase):
    def test_example_product_done_ac_needs_no_covering_test(self) -> None:
        # covers: UXP-700d-2
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "tests").mkdir()
            ac = _write_ac(d, "UXP-210a", "fern-and-fig")
            violations = cdp.check_staged_done_proofs([ac], test_root=d / "tests")
        self.assertEqual(
            violations,
            [],
            "A done AC belonging to the example product must not be asked for a "
            "covering test. No real test will ever cover a fictional plant shop, "
            "so demanding one makes the gate unsatisfiable for content that is "
            "not the project's work.",
        )

    def test_the_projects_own_done_ac_still_needs_one(self) -> None:
        # covers: UXP-700d-2
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "tests").mkdir()
            ac = _write_ac(d, "UXP-999z", None)
            violations = cdp.check_staged_done_proofs([ac], test_root=d / "tests")
        self.assertEqual(
            [v["ac_id"] for v in violations],
            ["UXP-999z"],
            "An AC with no product field is the project's own record and must "
            "still be held to BO-2500b. If this passes, the exemption has been "
            "widened into a hole that disables the gate for everything.",
        )

    def test_the_projects_own_product_is_not_treated_as_an_example(self) -> None:
        # covers: UXP-700d-2
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "tests").mkdir()
            ac = _write_ac(d, "UXP-998z", "leafcutter")
            violations = cdp.check_staged_done_proofs([ac], test_root=d / "tests")
        self.assertEqual(
            [v["ac_id"] for v in violations],
            ["UXP-998z"],
            "An explicit product of 'leafcutter' names the project's own record, "
            "not an example, and must not be exempted.",
        )


if __name__ == "__main__":
    unittest.main()
