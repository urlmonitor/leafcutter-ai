"""
MODULE: tests.kernel.retrieval.test_retrieval_benchmark
GOAL: An offline regression benchmark of the lexical retrieval stage over the real repository
    checkout: for each named goal, the places that MUST reach the first Jev rerank batch and the
    files that must NOT crowd it, with the round E results recorded as the ratchet no change may
    fall below.
BUSINESS CONTEXT: Round E made research cheap (one rerank batch of 20 per need) and the live
    regression on goals 5 and 2 showed what that cost: the batch filled with registry JSON,
    ticket comments and AC yaml while `kernel/persistence/run_store.py`, the tests READMEs and the
    design sections that answer the question sat at pool positions 24 to 51, never judged. Cost
    and quality now trade off in the open: a change that lowers cost must not drop a must-have
    place, and one that raises quality must not regress a case.
ARCHITECTURE: benchmark_cases.json holds the cases and, per case, the round E ("baseline")
    results. The RATCHET asserts everything the baseline reached is still reached and no crowding
    count rose above the baseline. The second-domain scenario ("Where should a cache live?") runs on a
    throwaway repository with noise built to crowd the pool. No Jev, no network, no writes.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.kernel.retrieval.benchmark_support import (
    REPO_ROOT,
    BatchResult,
    crowding,
    load_cases,
    reached,
    run_case,
)

CASES = load_cases()
NOT_A_CHECKOUT = "not a full repository checkout (docs/analysis is missing)"
CACHE_ADR = ("Decision: the cache lives in process memory with a size cap, because the cached "
             "values are cheap to rebuild and must never outlive a deploy.\n")


def write(root: Path, rel: str, text: str) -> None:
    """Write one file of a throwaway repository."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class RealCheckout(unittest.TestCase):
    """Base: the cases run once per class over the checkout this file lives in."""

    results: dict[str, BatchResult]

    @classmethod
    def setUpClass(cls) -> None:
        """Run every case once (they all scan the same files)."""
        if not (REPO_ROOT / "docs" / "analysis").is_dir():
            raise unittest.SkipTest(NOT_A_CHECKOUT)
        cls.results = {c["id"]: run_case(c) for c in CASES}


class TestRatchet(RealCheckout):
    """No case may fall below what round E reached (the recorded baseline)."""

    def test_every_case_still_reaches_what_the_baseline_reached(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                got = reached(self.results[case["id"]], case)
                lost = [n for n in case["baseline"]["reached"] if not got[n]]
                self.assertEqual(lost, [], f"fell below the round E baseline: {lost}")

    def test_no_case_is_more_crowded_than_the_baseline(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                now = crowding(self.results[case["id"]], case)
                worse = {k: (v, case["baseline"]["crowding"][k]) for k, v in now.items()
                         if v > case["baseline"]["crowding"][k]}
                self.assertEqual(worse, {}, f"more crowded than the baseline (now, baseline): {worse}")


class TestSecondDomain(unittest.TestCase):
    """The same ranking serves another question: the ADR on caches beats registry noise."""

    def test_the_adr_on_cache_location_reaches_the_first_batch(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            write(root, "docs/architecture/adrs/ADR-901-cache-location.md", CACHE_ADR)
            registry = ",\n".join(
                f'  "entry{n}": "' + " ".join(["cache the cache layer where a cache lives"] * 60)
                + '"' for n in range(6))
            write(root, "docs/roadmap.json", "{\n" + registry + "\n}\n")
            for n in range(40):
                write(root, f"docs/analysis/note-{n:02d}.md",
                           f"# Note {n}\nWhere a cache could live is discussed, item {n}.\n")
            case: dict[str, Any] = {"goal": "Where should a cache live?",
                                    "category": "prior_decisions"}
            result = run_case(case, root=root)
        found = [c.path for c in result.batch]
        self.assertIn("docs/architecture/adrs/ADR-901-cache-location.md", found)


class TestHarness(unittest.TestCase):
    """The benchmark data is well formed."""

    def test_every_case_has_a_baseline_for_each_must_have_and_cap(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                names = {m["name"] for m in case["must_include"]}
                self.assertLessEqual(set(case["baseline"]["reached"]), names)
                self.assertEqual(set(case["baseline"]["crowding"]),
                                 {f["pattern"] for f in case.get("must_not_dominate", [])})

if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Benchmark of the lexical stage over the real checkout, with the
#   round E results as the ratchet (TestRatchet) and the must-have places as the target
#   (TestTarget); added before any ranking change so later fixes cannot trade quality for cost
#   unnoticed. (#KernelV01/F)
# ====================================================================
