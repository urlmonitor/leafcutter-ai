"""
Tests for TQ-600a-13-viii -- the one exemption from the hold: a pull request whose description declares a fix for the red
notice AND whose proof run passed on its head is not held; nothing else exempts anything. Every row drives the REAL ``main``
of ``scripts/ci/post_merge_hold.py`` (the job's own entry point) through the REAL REST client against the recording fake.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-viii.yaml
(the proof run itself is -xvi's, the re-run on proof completion is -xv's, the allowed-write audit is -xi's: none is tested here.
The proof is MODELLED by the run records the double serves: the two reads the AC names, on the declared path only.)

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py
  * ``main`` reads ``pull_request.body`` from the event file IN PYTHON (a null or absent body is no declaration). Title,
    labels and commits are never read; no ``/pulls`` or ``/commits`` request is made.
  * ``match_declaration(body, repo_full_name, notice_numbers) -> int | None`` (pure, stdlib, linear time): the nine closing
    keywords (any case, whole word, optional colon) directly followed by ``#N``, ``owner/repo#N`` (this repository, case
    insensitive) or ``https://github.com/<repo>/issues/N`` (optional trailing slash or fragment), N in ``notice_numbers``
    (the OPEN, non-pull-request ``post-merge-red`` issues). ``-xvi``'s prepare job calls this same function.
  * On the held path, ONLY when the verdict run is red or did-not-complete AND a notice carries that run's state block AND
    the description declares an open notice, the hold makes two reads and no others for the evidence:
      GET /actions/workflows/post-merge-fix-proof.yml/runs?head_sha=<event head>&event=pull_request_target&per_page<=5
          (the run with the highest ``run_number``);
      GET /actions/runs/{id}/jobs?filter=latest (the job named exactly ``Post-merge fix proof`` must be ``success``).
    The proof is current only when its ``run_started_at`` is strictly later than the verdict run's ``updated_at``. A
    description that declares nothing makes no proof read at all. Never an artifact.
  * An exemption is verdict ``state: exempt``; ``main`` exits 0 and prints a reason containing
    "declares and proves a fix for #N". Every held reason says which part was missing (proof absent, failed, running,
    skipped, earlier than the red run; or the notice is missing).
  * The record: ONE comment on the notice issue naming the pull request (``#42``), the head commit and the proof run id,
    with a hidden HTML comment carrying the PR number and the red run id; found again on a later evaluation, never
    repeated. The only writes are that comment and the PR's own comment (no issue edit, label or close).
  * With a red run and no notice: no exemption; the output says the fix route is unavailable until the notice exists and
    links the follow-up run (``GET .../workflows/post-merge-followup.yml/runs?head_sha=<verdict run head>``) whose
    ``notice`` job can be re-run.
======================================================================
"""

from __future__ import annotations

from datetime import timedelta

from ._comment_harness import PR, notice_description
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, FOLLOWUP_URL, HEAD, NOTICE, SETTLED, ExemptCase
from ._notice_fakes import REPO

FORMS = [
    "Fixes #12",
    "closes: #12",
    "RESOLVED #12",
    f"fixed {REPO}#12",
    f"Some context.\n\nResolves https://github.com/{REPO}/issues/12",
]
EARLIER = r"earlier|before|older|predat|not (the )?current"
FAILED_PROOF = r"proof[^.\n]*fail|fail[^.\n]*proof"  # the held reason's own "the tests failed" must not satisfy this


class TestTq600a13viii(ExemptCase):
    def test_tq600a_13_viii_a_declared_and_proven_fix_passes(self):
        # covers: TQ-600a-13-viii
        # angle: criterion
        """Red run, notice #12, a passing proof of the current red run on the head: each declaration form exits 0 and says it is
        passing because the pull request declares and proves a fix for #12; the exemption is recorded on #12 once (PR, head,
        proof run, hidden marker) and a second evaluation of the same pull request records nothing new. Each evaluation makes
        exactly two proof reads, bounded and on the declared path; the only writes are comments.

        Wrong versions caught: the exit code left at 0-only-for-pass (the TODO in ``main``); a record per evaluation; a record
        that omits the head or the proof run; an unbounded proof read; the proof read from an artifact.
        """
        cases = Cases()
        for form in FORMS:
            with cases.case(form):
                self.svc.reset()
                self.stage()
                first = self.drive_body(form)
                CHECK.assertEqual(0, first.code, first.out)
                CHECK.assertRegex(first.out, r"(?i)declares and proves a fix for #12")
                self.expect_one_record()
                CHECK.assertEqual((0, 1), (self.drive_body(form).code, len(self.record_writes())), "the second evaluation recorded again")
                runs = self.svc.seen("/post-merge-fix-proof.yml/runs")
                CHECK.assertEqual(2, len(runs), "one proof-run read per evaluation")
                CHECK.assertTrue(all(q["head_sha"] == HEAD and q["event"] == "pull_request_target" and int(q["per_page"]) <= 5 for _, _, q in runs), runs)
                CHECK.assertEqual([{"filter": "latest"}] * 2, [q for _, _, q in self.svc.seen("/actions/runs/205/jobs")])
                CHECK.assertEqual([], self.svc.write_attempts)
                self.expect_only_declared_reads()
        cases.check()

    def test_tq600a_13_viii_a_did_not_complete_run_is_exempted_the_same_way(self):
        # covers: TQ-600a-13-viii
        # angle: criterion
        """The AC names red OR did-not-complete. A did-not-complete verdict run (its notice built by the real producer with a
        stage and no failing tests) with a declaration and a passing current proof exits 0 and records once.

        Wrong version caught: the exemption evaluated only for ``state == "red"``.
        """
        self.stage(dnc=True)
        ran = self.drive_body(DECL)
        CHECK.assertEqual(0, ran.code, ran.out)
        CHECK.assertRegex(ran.out, r"(?i)declares and proves a fix for #12")
        self.expect_one_record()

    def test_tq600a_13_viii_declaration_without_evidence_is_held(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """Red run R2 (settled at T), notice #12, a declaration of #12 with: no proof, a failed proof, a running proof, a passing
        proof started before T, one started exactly at T, a passing run whose proof job was SKIPPED, a passing run with event
        pull_request, a passing proof of ANOTHER head, and a newest proof that failed over an older one that passed. All held,
        each saying why, nothing recorded, no artifact read. A `nightly-fix` label with no declaration and a title-only
        declaration (the proof passing in both) are held and make no proof read. Controls: a passing current proof, and an older
        failed run under a newest passing one, are exempt (so the held rows are held for their stated reason).

        Wrong versions caught: a declaration alone passes; a failed or running proof accepted; ``>=`` instead of ``>`` on the
        settle time, or the proof compared with the red run's START; the run's conclusion taken for the job's; no ``event``
        filter or no ``head_sha``; the first proof run taken rather than the highest run number; a label releasing the hold;
        the title read; any artifact request.
        """
        ok, early = self.add_proof, SETTLED - timedelta(minutes=5)
        with_label, with_title = {"labels": [{"name": "nightly-fix"}]}, {"title": DECL}
        rows = [
            ("no proof run", lambda: None, DECL, {}, "proof"),
            ("a failed proof", lambda: ok(conclusion="failure", prove="failure"), DECL, {}, FAILED_PROOF),
            ("a running proof", lambda: ok(status="in_progress"), DECL, {}, r"running|in progress|not (yet )?(finished|complete)"),
            ("a proof that started before the red run settled", lambda: ok(started=early), DECL, {}, EARLIER),
            ("a proof that started exactly when it settled", lambda: ok(started=SETTLED), DECL, {}, EARLIER),
            ("a skipped proof job in a successful run", lambda: ok(prove="skipped"), DECL, {}, "skip"),
            ("a pull_request proof run", lambda: ok(event="pull_request"), DECL, {}, "proof"),
            ("a proof of another head", lambda: ok(head="8" * 40), DECL, {}, "proof"),
            ("the newest proof failed, an older one passed", lambda: (ok(number=4), ok(number=5, conclusion="failure", prove="failure")), DECL, {}, FAILED_PROOF),
            ("a label and no declaration", ok, "A change.", with_label, None),
            ("a title and no description", ok, "A change.", with_title, None),
        ]
        cases = Cases()
        for label, setup, body, extra, why in rows:
            with cases.case(label):
                self.svc.reset()
                self.stage(proof=False)
                setup()
                ran = self.drive_body(body, **extra)
                self.expect_nothing_granted(ran, *([why] if why else []))
                self.expect_only_declared_reads()
                if why is None:
                    CHECK.assertEqual([], self.svc.seen("fix-proof"), "a description with no declaration must cost no proof read")
        controls = [("a passing current proof", ok), ("an older failed run under a newest passing one", lambda: (ok(number=4, conclusion="failure", prove="failure"), ok(number=5)))]
        for label, setup in controls:
            with cases.case(f"control: {label}"):
                self.svc.reset()
                self.stage(proof=False)
                setup()
                CHECK.assertEqual(0, self.drive_body(DECL).code)
        cases.check()

    def test_tq600a_13_viii_no_notice_means_no_exemption_and_says_how_to_recover(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """A red run, a passing current proof and a declaration, with: no `post-merge-red` issue at all and a declaration of an
        unrelated open issue #7; an open `post-merge-red` issue that describes an OLDER run and a declaration of it. Both held;
        the output says the fix route is unavailable until the notice exists and links the follow-up run of THIS verdict run
        (not a newer run for another commit); the PR's comment says the same. Control: with the notice, the same proof exempts.

        Wrong versions caught: any ``Fixes #N`` for an unrelated open issue accepted when there is no notice; the output only
        says "held"; the newest follow-up run linked whatever it ran for.
        """
        cases = Cases()
        rows = {
            "no notice, an unrelated open issue": (lambda: self.svc.add_issue(7, title="a bug", labels=["bug"]), "Fixes #7"),
            "a notice for an older run": (lambda: self.svc.add_issue(NOTICE, body=notice_description(105, failing=("tests/t.py::test_old",)), labels=["post-merge-red"]), DECL),
        }
        for label, (seed, body) in rows.items():
            with cases.case(label):
                self.svc.reset()
                self.stage(notice=False)
                seed()
                ran = self.drive_body(body)
                self.expect_nothing_granted(ran, "notice", "unavailable|until the notice exists")
                CHECK.assertIn(FOLLOWUP_URL, ran.out)
                CHECK.assertNotIn("/actions/runs/556", ran.out)
                CHECK.assertIn("unavailable until the notice exists", self.svc.own_one(PR)["body"])
        with cases.case("control: the notice exists"):
            self.svc.reset()
            self.stage()
            CHECK.assertEqual(0, self.drive_body(DECL).code)
        cases.check()

    def test_tq600a_13_viii_the_repair_is_not_deadlocked(self):
        # covers: TQ-600a-13-viii
        # angle: criterion
        """Two pull requests in one sitting on one red history: #42 declares and is proven on its head and passes; #43 declares
        but has no proof on ITS head and fails, and fails again with no declaration; #42 pushed to a new head with no new proof
        fails; with a proof for the new head it passes again. Exactly one record on #12 for #42. Exactly one way through, and it
        is open.

        Wrong versions caught: a proof (or an exemption) carried from one pull request to another, or from one head of a pull
        request to the next; a hold that releases nobody (the deadlock this record exists to prevent).
        """
        self.stage()
        cases = Cases()
        with cases.case("the declared and proven pull request passes"):
            CHECK.assertEqual(0, self.drive_body(DECL).code)
            self.expect_one_record()
        with cases.case("a declaring pull request without a proof of its head is held"):
            held = self.drive_body(DECL, number=43, head="6" * 40)
            CHECK.assertEqual(1, held.code, held.out)
        with cases.case("an undeclared pull request is held"):
            CHECK.assertEqual(1, self.drive_body("A change.", number=43, head="6" * 40).code)
        with cases.case("a later push needs a fresh proof"):
            CHECK.assertEqual(1, self.drive_body(DECL, head="5" * 40).code)
        with cases.case("and passes with one"):
            self.add_proof(number=6, head="5" * 40, started=SETTLED + timedelta(minutes=20))
            CHECK.assertEqual(0, self.drive_body(DECL, head="5" * 40).code)
        with cases.case("nothing was recorded for the held pull request"):
            CHECK.assertEqual([], [w for w in self.record_writes() if "#43" in (w.get("body") or "")])
        cases.check()
