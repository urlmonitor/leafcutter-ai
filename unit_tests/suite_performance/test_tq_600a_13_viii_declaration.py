"""
Tests for TQ-600a-13-viii, the declaration half -- what counts as declaring a fix, which issue it may name, and the states in
which no declaration is read at all. The verdict rows drive the REAL ``main`` against the recording fake with a passing current
proof served, so a held row is held ONLY because of the declaration (or the state); each test carries a control row that is
exempt. The matcher rows call ``match_declaration(body, repo_full_name, notice_numbers)`` (the name ``-xvi``'s prepare job
shares, see the contract in test_tq_600a_13_viii.py).

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-viii.yaml
(the stale / disabled / never-run / could-not-read wording is -xiv's and -ix's; only "no exemption applies" is asserted here)
"""

from __future__ import annotations

from ._comment_harness import notice_description
from ._ending_harness import CHECK, Cases
from ._exempt_harness import DECL, NOTICE, ExemptCase
from ._hold_harness import make_run
from ._notice_fakes import REPO, import_production

HOLD = "scripts.ci.post_merge_hold"
OTHER = "https://github.com/other/repo/issues/12"
NEAR_MISSES = {
    "names another open issue": "Fixes #7",
    "see": "see #12",
    "related to": "related to #12",
    "a number that begins with 12": "Fixes #123",
    "another repository's issue 12": "Fixes other/repo#12",
    "the real repository's name hard-coded": "Fixes urlmonitor/leafcutter-ai#12",
    "a keyword inside a word": "prefixes #12",
    "a keyword outside the nine": "Closing #12",
    "another repository's issue URL": f"Fixes {OTHER}",
    "a pull request URL": f"Fixes https://github.com/{REPO}/pull/12",
    "another host": f"Fixes https://evil.example/{REPO}/issues/12",
    "an issue URL for a number that begins with 12": f"Fixes https://github.com/{REPO}/issues/123",
    "a null description": None,
}
KEYWORDS = ("close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved")
REFERENCES = ("#12", f"{REPO}#12", f"{REPO.upper()}#12", f"https://github.com/{REPO}/issues/12", f"https://github.com/{REPO}/issues/12/", f"https://github.com/{REPO}/issues/12#issuecomment-9")
NOT_DECLARATIONS = [
    "see #12", "related to #12", "Fixes #123", "Fixes #1", "Fixes other/repo#12", "prefixes #12", "unresolved #12", "disclosed #12", "Fixes the flake in #12",
    "Closing #12", "#12", "Fixes #", "Fixes", "Fixes #１２", "Fixes #١٢", f"Fixes {OTHER}", f"Fixes https://github.com/{REPO}/pull/12",
    f"Fixes https://github.com/{REPO}/issues/123", f"Fixes https://evil.example/{REPO}/issues/12", f"Fixes http://github.com.evil.example/{REPO}/issues/12", "", "   \n\t",
]


def matcher():
    found = getattr(import_production(HOLD), "match_declaration", None)
    CHECK.assertTrue(callable(found), f"{HOLD}.match_declaration is not implemented yet")
    return found


class TestTq600a13viiiDeclaration(ExemptCase):
    def test_tq600a_13_viii_a_near_miss_declaration_is_still_held(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """With a passing current proof, a notice #12 and an open unrelated issue #7: `Fixes #7`, `see #12`, `related to #12`,
        `Fixes #123`, `Fixes other/repo#12`, the real repository's own name hard-coded, a keyword inside a word, a keyword outside
        the nine, another repository's issue URL, a pull request URL, another host, a URL for 123 and a null description are each
        held and record nothing. Control: `Fixes #12` is exempt.

        Wrong versions caught: the match is on `#12` anywhere ("see #12"); a prefix match ("Fixes #123"); the repository ignored
        or hard-coded; no word boundary before the keyword; a null description raising.
        """
        cases = Cases()
        for label, body in NEAR_MISSES.items():
            with cases.case(label):
                self.svc.reset()
                self.stage()
                self.svc.add_issue(7, title="an unrelated bug", labels=["bug"])
                self.expect_nothing_granted(self.drive_body(body))
        with cases.case("control: the declaration"):
            self.svc.reset()
            self.stage()
            CHECK.assertEqual(0, self.drive_body(DECL).code)
        cases.check()

    def test_tq600a_13_viii_no_exemption_unless_the_check_holds_for_a_red_run(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """The notice, a declaration and a passing proof are all served, and the check holds because the latest run is stale
        (31 h old), the workflow is disabled, the workflow never ran, or the run history cannot be read. Each is held with its own
        reason, records nothing and reads no proof. Control: the same world with a red verdict run exempts.

        Wrong version caught: the declaration evaluated before the state, releasing a hold that is not about a red run.
        """
        suite_runs = f"/repos/{REPO}/actions/workflows/post-merge-suite.yml/runs"

        def stale():
            self.serve([make_run(6, "success", hours_ago=31)])

        def disabled():
            self.svc.workflow_state = "disabled_manually"

        def never_run():
            self.serve([])

        def unreadable():
            self.svc.failing = [suite_runs]

        cases = Cases()
        for label, setup, why in [("stale", stale, "fresh verdict|stale"), ("disabled", disabled, "not active"), ("never run", never_run, "never run"), ("could not read", unreadable, "could not be read")]:
            with cases.case(label):
                self.svc.reset()
                self.stage()
                setup()
                self.expect_nothing_granted(self.drive_body(DECL), why)
                CHECK.assertEqual([], self.svc.seen("fix-proof"), "a proof was read although the hold is not about a red run")
        with cases.case("control: a red verdict run"):
            self.svc.reset()
            self.stage()
            CHECK.assertEqual(0, self.drive_body(DECL).code)
        cases.check()

    def test_tq600a_13_viii_a_failed_read_of_the_evidence_is_never_an_exemption(self):
        # covers: TQ-600a-13-viii
        # angle: failure
        """With a declaration and a passing proof, a failing read of the proof runs, of the proof's jobs, of the notice list or of
        the verdict run's jobs is held, records nothing and says it could not read. Control: no failure exempts.

        Wrong versions caught: an exception from a read caught as "no objection"; a failed notice read treated as a notice found.
        """
        cases, base = Cases(), f"/repos/{REPO}"
        reads = {
            "the proof runs": f"{base}/actions/workflows/post-merge-fix-proof.yml/runs",
            "the proof's jobs": f"{base}/actions/runs/205/jobs",
            "the notice list": f"{base}/issues",
            "the verdict run's jobs": f"{base}/actions/runs/107/jobs",
        }
        for label, prefix in reads.items():
            with cases.case(label):
                self.svc.reset()
                self.stage()
                self.svc.failing = [prefix]
                self.expect_nothing_granted(self.drive_body(DECL), r"could not|cannot|unable|http 500")
        with cases.case("control: every read works"):
            self.svc.reset()
            self.stage()
            CHECK.assertEqual(0, self.drive_body(DECL).code)
        cases.check()

    def test_tq600a_13_viii_any_open_post_merge_red_issue_counts_and_nothing_else(self):
        # covers: TQ-600a-13-viii
        # angle: discrimination
        """An open duplicate #13 of the notice is a valid declaration (exempt, one record on an open notice). Held: the notice #12
        itself CLOSED; a declared duplicate #14 that is closed; a pull request numbered #15 that carries the `post-merge-red`
        label (the issues API lists pull requests); an open issue #7 without the label.

        Wrong versions caught: only the run's own notice accepted (a repairer who named a duplicate is blocked); closed issues
        accepted; a pull request counted as a notice; the label not required.
        """
        def duplicate(number, *, state="open", pull_request=False, labels=("post-merge-red",)):
            self.svc.add_issue(number, title=f"duplicate {number}", body="Duplicate of #12", labels=list(labels), state=state, pull_request=pull_request)

        cases = Cases()
        with cases.case("an open duplicate is accepted"):
            self.svc.reset()
            self.stage()
            duplicate(13)
            CHECK.assertEqual(0, self.drive_body("Fixes #13").code)
            self.expect_one_record(issues=(NOTICE, 13))
        rows = {
            "the notice itself closed": (lambda: self.svc.issues[NOTICE].update(state="closed"), DECL),
            "a closed duplicate": (lambda: duplicate(14, state="closed"), "Fixes #14"),
            "a pull request carrying the label": (lambda: duplicate(15, pull_request=True), "Fixes #15"),
            "an open issue without the label": (lambda: duplicate(7, labels=("bug",)), "Fixes #7"),
        }
        for label, (seed, body) in rows.items():
            with cases.case(label):
                self.svc.reset()
                self.stage()
                seed()
                self.expect_nothing_granted(self.drive_body(body))
        cases.check()

    def test_tq600a_13_viii_the_notice_is_the_one_that_describes_the_verdict_run(self):
        # covers: TQ-600a-13-viii
        # angle: seam
        """Seam: the REAL notice producer's descriptions (state block included) are what the hold reads. A NEWER open notice (#20)
        describes another run (999); the older #12 describes the verdict run (107). `Fixes #12` is exempt and recorded once.

        Wrong version caught: the notice taken from the newest `post-merge-red` issue rather than the one whose state block names
        the verdict run.
        """
        self.stage(notice=False)
        self.svc.add_issue(20, title="newer, for another run", body=notice_description(999, failing=("tests/t.py::test_other",)), labels=["post-merge-red"])
        self.svc.add_issue(NOTICE, title="the notice", body=notice_description(107, failing=("tests/t.py::test_a",)), labels=["post-merge-red"])
        ran = self.drive_body(DECL)
        CHECK.assertEqual(0, ran.code, ran.out)
        self.expect_one_record()

    def test_tq600a_13_viii_the_declaration_forms_are_githubs_own(self):
        # covers: TQ-600a-13-viii
        # angle: criterion
        """The pure matcher: each of the nine keywords, as written, upper-cased and with a colon, followed by `#12`, `owner/repo#12`
        (any letter case of the repository), the issue URL, with a trailing slash and with a fragment, names 12; the declaration may
        sit on a later line, in CRLF text, after prose, and be followed by punctuation. Among several, a declared OPEN notice wins
        over `see #12`.

        Wrong versions caught: a two-keyword matcher; case-sensitive keywords or repository; a colon not accepted; a URL form missing.
        """
        match, cases = matcher(), Cases()
        for keyword in KEYWORDS:
            for spelling in (keyword, keyword.upper(), f"{keyword}:", keyword.capitalize()):
                for reference in REFERENCES:
                    with cases.case(f"{spelling} {reference}"):
                        CHECK.assertEqual(12, match(f"{spelling} {reference}", REPO, {12}))
        for body in ("Intro text.\n\nFixes #12.", "a\r\nCloses #12\r\nb", "(Fixes #12)", "Fixes\t#12", "Fixes  #12", "see #13\nFixes #12\n"):
            with cases.case(repr(body)):
                CHECK.assertEqual(12, match(body, REPO, {12}))
        with cases.case("an open notice wins over a non-declaration"):
            CHECK.assertEqual(13, match("see #12\nFixes #13", REPO, {12, 13}))
        cases.check()

    def test_tq600a_13_viii_the_matcher_names_an_open_notice_or_nothing(self):
        # covers: TQ-600a-13-viii
        # angle: boundary
        """The pure matcher over the boundary: null, empty and whitespace descriptions, an empty set of open notices, a set that does
        not hold the declared number, numbers that merely begin with 12, other repositories and hosts, a keyword inside a word, and
        Unicode digits that `int()` would read as 12, all give None; the declared number must be in the set.

        Wrong versions caught: `\\d` matching fullwidth or Arabic-Indic digits; a prefix match; the set ignored; a null body raising.
        """
        match, cases = matcher(), Cases()
        for body in [*NOT_DECLARATIONS, None]:
            with cases.case(repr(body)):
                CHECK.assertIsNone(match(body, REPO, {12}))
        for numbers in (set(), {13}, {1}, {120}):
            with cases.case(f"open notices {numbers}"):
                CHECK.assertIsNone(match(DECL, REPO, numbers))
        with cases.case("control: one declaration of an open notice"):
            CHECK.assertEqual(12, match(DECL, REPO, {12}))
        cases.check()
