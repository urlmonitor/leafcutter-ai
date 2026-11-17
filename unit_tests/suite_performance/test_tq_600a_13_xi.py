"""
Tests for TQ-600a-13-xi, the bound -- no run of the family changes the repository's code, and every write it makes to the hosting
service is on the allowed list. This file is the BEHAVIOURAL half over every path; the client allowlist is in
test_tq_600a_13_xi_client.py, the workflow scopes in test_tq_600a_13_xi_scopes.py, the mutation descriptor in
test_tq_600a_13_xi_mutation.py.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xi.yaml

The paths (``_xi_paths.py``) are the family's real entry points -- the notice (correctness, timing, flaky), the re-evaluation, the
hold (with and without App publication, held, exempt, every verdict state) and the proof's prepare job -- run against the shared
recording fakes, with a real scratch repository whose ``origin`` is a local bare repository.
"""

from __future__ import annotations

from ._ending_harness import CHECK, Cases
from ._xi_paths import PathsCase
from ._xi_support import category_of, changed, make_origin, snapshot, verdict_on

WRITES_NOTHING = {"notice superseded", "hold pass", "proof prepare", "reeval no change", "reeval timing run"}
REQUIRED_KINDS = {"issue-create", "issue-edit", "comment-create", "comment-edit", "hold-rerun", "check-create", "check-complete", "exchange"}


class TestTq600a13XiEveryPath(PathsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.origin = make_origin(cls.repo.path, cls.tmp / "origin.git")

    def test_tq600a_13_xi_every_path_writes_only_the_allowed_set(self):
        # covers: TQ-600a-13-xi
        # angle: criterion
        """Run every path; the writes the SERVER recorded are a subset of the allowed list, the fix proof records none, and the
        scratch repository's branches, tags, index and working tree and the bare origin's refs are equal before and after.

        Rows: each path's own subset check (a path that writes outside the list names the write); non-vacuity (each path that
        must write did, so the subset is over real writes, and every KIND of allowed write was exercised at least once);
        the proof's prepare job and the superseded notice record no write; the git state is unchanged.

        Wrong versions caught: a step that pushes, opens a pull request, labels another issue, writes a status or a check run
        with the GITHUB_TOKEN, or re-runs a run that is not the hold's (each is an unlisted write); a test double that records
        nothing (the non-vacuity rows); a path that edits the working tree (the snapshot rows).
        """
        before = snapshot(self.repo.path, self.origin)
        for driver in (self.path_notices, self.path_timing_notices, self.path_flaky_notice, self.path_hold, self.path_exempt, self.path_reeval, self.path_proof_prepare):
            driver()
        cases = Cases()
        for name, (writes, world) in self.found.items():
            with cases.case(f"{name}: subset of the list"):
                CHECK.assertEqual([], [f"{w.method} {w.path}: {why}" for w in writes if (why := verdict_on(w, world))])
            with cases.case(f"{name}: non-vacuous"):
                CHECK.assertEqual(name in WRITES_NOTHING, not writes, f"{name} recorded {[(w.method, w.path) for w in writes]}")
        with cases.case("every kind of allowed write was exercised"):
            seen = {category_of(w) for writes, _ in self.found.values() for w in writes}
            CHECK.assertEqual(set(), REQUIRED_KINDS - seen, f"never exercised: {sorted(REQUIRED_KINDS - seen)}")
        with cases.case("the fix proof's prepare job made no write at all"):
            CHECK.assertEqual([], self.found["proof prepare"][0])
        with cases.case("branches, tags, index, working tree and the origin's refs are unchanged"):
            CHECK.assertEqual([], changed(before, snapshot(self.repo.path, self.origin)))
        cases.check()
