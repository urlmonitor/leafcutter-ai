"""
MODULE: tests.kernel.retrieval.test_retrieval_benchmark
GOAL: An offline regression benchmark of the lexical retrieval stage over a pinned corpus (the
    files of `corpus_commit`): for each named goal, the places that MUST reach the first Jev rerank
    batch and the files that must NOT crowd it, with two recorded results as ratchets no change
    may fall below: round E (the "before") and round F (the current best).
BUSINESS CONTEXT: Round E made research cheap (one rerank batch of 20 per need) and the live
    regression on goals 5 and 2 showed what that cost: the batch filled with registry JSON,
    ticket comments and AC yaml while `kernel/persistence/run_store.py`, the tests READMEs and the
    design sections that answer the question sat at pool positions 24 to 51, never judged. Cost
    and quality now trade off in the open: a change that lowers cost must not drop a must-have
    place, and one that raises quality must not regress a case (and records its gain here).
ARCHITECTURE: benchmark_cases.json holds the cases and, per case, the round E ("baseline") and
    round F ("current") results. RATCHETS: everything the baseline reached is still reached, and
    everything "current" reached is too; no crowding count rose above its recorded value; the real
    rerank loop, run with a scripted oracle, judges at least the recorded must-haves in at most
    the recorded number of Jev calls (round E's loop is derived from its pool positions). CAPS:
    no noisy file pattern exceeds its `max` in the first batch. Must-haves a lexical search does
    not reach stay listed in the fixture (`current.pool_position`) as the gap that semantic
    retrieval, not this score, has to close. The second-domain scenario ("Where should a cache
    live?") runs on a throwaway repository with noise built to crowd the pool. CORPUS: the files
    scored are those of `corpus_commit`, so only ranking code and parameters move the ratchets;
    a missing pin skips locally and fails under CI. No Jev, no network, no writes to the checkout.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tests.kernel.retrieval.benchmark_support import (
    CORPUS_COMMIT,
    REPO_ROOT,
    BatchResult,
    CorpusUnavailable,
    JudgedResult,
    crowding,
    judged_names,
    judged_with_oracle,
    load_cases,
    materialise,
    pinned_corpus,
    reached,
    run_case,
)

CASES = load_cases()
MISSING_SHA = "0" * 40
CACHE_ADR = ("Decision: the cache lives in process memory with a size cap, because the cached "
             "values are cheap to rebuild and must never outlive a deploy.\n")


def write(root: Path, rel: str, text: str) -> None:
    """Write one file of a throwaway repository."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


_RESULTS: dict[str, BatchResult] = {}


def case_results() -> dict[str, BatchResult]:
    """Run every case once for the whole module (they all scan the same several thousand files)."""
    if not _RESULTS:
        _RESULTS.update({c["id"]: run_case(c) for c in CASES})
    return _RESULTS


class PinnedCorpus(unittest.TestCase):
    """Base: the cases run over the pinned corpus (skipped locally, failed under CI, if missing)."""

    results: dict[str, BatchResult]

    @classmethod
    def setUpClass(cls) -> None:
        """Share the one run of every case over the corpus of `corpus_commit`."""
        pinned_corpus()
        cls.results = case_results()


class TestRatchet(PinnedCorpus):
    """No case may fall below what round E reached, or below what round F reached."""

    def lost(self, case: dict[str, Any], record: str) -> list[str]:
        got = reached(self.results[case["id"]], case)
        return [n for n in case[record]["reached"] if not got[n]]

    def test_every_case_still_reaches_what_the_baseline_reached(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                self.assertEqual(self.lost(case, "baseline"), [], "fell below the round E baseline")

    def test_every_case_still_reaches_what_round_f_reached(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                self.assertEqual(self.lost(case, "current"), [], "fell below round F")

    def test_no_case_is_more_crowded_than_the_baseline(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                now = crowding(self.results[case["id"]], case)
                worse = {k: (v, case["baseline"]["crowding"][k]) for k, v in now.items()
                         if v > case["baseline"]["crowding"][k]}
                self.assertEqual(worse, {}, f"more crowded than the baseline (now, baseline): {worse}")

    def test_no_case_is_more_crowded_than_round_f_recorded(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                now = crowding(self.results[case["id"]], case)
                worse = {k: (v, case["current"]["crowding"][k]) for k, v in now.items()
                         if v > case["current"]["crowding"][k]}
                self.assertEqual(worse, {}, f"more crowded than round F recorded: {worse}")

    def test_round_f_reaches_more_than_round_e_in_total_and_loses_no_case(self) -> None:
        before = sum(len(c["baseline"]["reached"]) for c in CASES)
        after = sum(len(c["current"]["reached"]) for c in CASES)
        self.assertGreater(after, before)
        for case in CASES:
            self.assertLessEqual(set(case["baseline"]["reached"]), set(case["current"]["reached"]),
                                 case["id"])


class TestJudged(PinnedCorpus):
    """What the real rerank loop would judge (scripted oracle: must-haves 0.9, the rest 0.1)."""

    judged: dict[str, JudgedResult]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.judged = {c["id"]: judged_with_oracle(c, cls.results[c["id"]]) for c in CASES}

    def names(self, case: dict[str, Any]) -> list[str]:
        return judged_names(case, self.judged[case["id"]], self.results[case["id"]])

    def test_the_loop_judges_at_least_what_it_judged_in_round_e_and_round_f(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                got = set(self.names(case))
                self.assertLessEqual(set(case["baseline"]["judged"]["reached"]), got, "round E")
                self.assertLessEqual(set(case["current"]["judged"]["reached"]), got, "round F")

    def test_a_need_costs_no_more_jev_calls_than_recorded(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                self.assertLessEqual(self.judged[case["id"]].calls,
                                     case["current"]["judged"]["calls"])

    def test_the_loop_judges_more_must_haves_than_round_e_did(self) -> None:
        before = sum(len(c["baseline"]["judged"]["reached"]) for c in CASES)
        after = sum(len(self.names(c)) for c in CASES)
        self.assertGreater(after, before)


class TestCaps(PinnedCorpus):
    """No noisy file pattern (registry JSON, AC yaml, tickets) dominates the first batch."""

    def test_no_noisy_pattern_exceeds_its_cap_in_the_first_batch(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                caps = {f["pattern"]: f["max"] for f in case.get("must_not_dominate", [])}
                over = {k: v for k, v in crowding(self.results[case["id"]], case).items()
                        if v > caps[k]}
                self.assertEqual(over, {}, f"first batch dominated (count in batch): {over}")


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


class TestPinnedCorpus(unittest.TestCase):
    """The files scored are the pinned commit's; a missing pin cannot silence the ratchet in CI."""

    def test_a_missing_pin_skips_locally_and_fails_under_ci(self) -> None:
        with self.assertRaises(unittest.SkipTest) as local:
            materialise(MISSING_SHA, ["kernel"], env={})
        self.assertIn(f"git fetch --no-tags --depth=1 origin {MISSING_SHA}", str(local.exception))
        for flag in ("CI", "GITHUB_ACTIONS"):
            with self.subTest(flag), self.assertRaises(CorpusUnavailable):
                materialise(MISSING_SHA, ["kernel"], env={flag: "true"})

    def test_the_corpus_holds_only_files_of_the_pinned_commit(self) -> None:
        corpus = pinned_corpus()
        pinned = set(subprocess.run(["git", "ls-tree", "-r", "--name-only", CORPUS_COMMIT],
                                    cwd=REPO_ROOT, capture_output=True, text=True,
                                    check=True).stdout.splitlines())
        on_disk = {p.relative_to(corpus).as_posix() for p in corpus.rglob("*") if p.is_file()}
        self.assertIn("kernel/capabilities/retrieval/repository.py", on_disk)
        self.assertEqual(on_disk - pinned, set(), "files that are not in the pinned commit")


class TestHarness(unittest.TestCase):
    """The benchmark data is well formed."""

    def test_the_corpus_is_pinned_to_a_full_commit_sha(self) -> None:
        self.assertRegex(CORPUS_COMMIT, r"^[0-9a-f]{40}$")

    def test_every_case_has_a_baseline_for_each_must_have_and_cap(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                names = {m["name"] for m in case["must_include"]}
                self.assertLessEqual(set(case["baseline"]["reached"]), names)
                self.assertEqual(set(case["baseline"]["crowding"]),
                                 {f["pattern"] for f in case.get("must_not_dominate", [])})

    def test_every_case_records_round_f_and_what_the_loop_judged_in_both_rounds(self) -> None:
        for case in CASES:
            with self.subTest(case["id"]):
                names = {m["name"] for m in case["must_include"]}
                caps = {f["pattern"] for f in case.get("must_not_dominate", [])}
                for record in ("baseline", "current"):
                    self.assertLessEqual(set(case[record]["judged"]["reached"]), names)
                self.assertLessEqual(set(case["current"]["reached"]), names)
                self.assertEqual(set(case["current"]["crowding"]), caps)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The cases run over the pinned corpus (`corpus_commit`), not the live
#   checkout, so docs-only changes cannot move the ratchets; a missing pin skips locally and fails
#   under CI, and the corpus is shown to hold only the pinned commit's files. The git-ignored
#   filter test went with the filter. (#KernelBenchmarkPinnedCorpus)
# - 2026-10-01 [python-coder]: Round F `current` values re-recorded at CI's checkout path after the
#   checkout-folder fix: tighter positions and crowding, and 3 calls (was 2) for
#   lessons_approval_provenance; round E baselines unchanged. (#KernelV01/CI)
# - 2026-10-01 [python-coder]: The real-checkout cases need a git checkout and score only what git
#   does not ignore; a build's ignored copies are shown to change no score. CI (Linux) and a
#   Windows worktree disagreed on the same commit. (#KernelV01/CI)
# - 2026-10-01 [python-coder]: Round F records its results next to round E's: both are ratchets,
#   the caps are asserted, and the must-haves a lexical score cannot reach (design-3 section
#   Persistence layout, Stage-0 delta part 4, concept parts 3 and 4, the default config JSON) stay
#   listed with their pool position as the gap for semantic retrieval. (#KernelV01/F)
# - 2026-10-01 [python-coder]: Benchmark of the lexical stage over the real checkout, with the
#   round E results as the ratchet; added before any ranking change so later fixes cannot trade
#   quality for cost unnoticed. (#KernelV01/F)
# ====================================================================
