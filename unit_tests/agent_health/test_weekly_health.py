"""Unit tests for scripts/agent-health/weekly_health.py.

Covers the pure metric computations and the honesty guarantees the report
makes: that an unwired telemetry sink reports "no data" rather than a zero
completion rate, and that a zero denominator never raises.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "agent-health"
sys.path.insert(0, str(_SCRIPTS))

import weekly_health as wh  # noqa: E402


class TestClassifyPath(unittest.TestCase):
    """classify_path buckets a repository path into (language, kind)."""

    def test_python_source_is_code(self):
        # covers: INF-500e-4
        self.assertEqual(wh.classify_path("scripts/build.py"), ("Python", "code"))

    def test_yaml_is_spec(self):
        self.assertEqual(
            wh.classify_path("docs/acceptance-criteria/ac-store/ACS-100.yaml"),
            ("YAML", "spec"),
        )

    def test_markdown_is_prose(self):
        self.assertEqual(wh.classify_path("docs/known-issues/ac-store.md"), ("Markdown", "prose"))

    def test_dockerfile_without_extension_is_recognised(self):
        self.assertEqual(wh.classify_path("deploy/Dockerfile"), ("Docker", "spec"))

    def test_extension_match_is_case_insensitive(self):
        self.assertEqual(wh.classify_path("notes/README.MD"), ("Markdown", "prose"))

    def test_unknown_extension_falls_through_to_other(self):
        self.assertEqual(wh.classify_path("assets/logo.qqq"), ("Other", "other"))

    def test_dotfile_is_not_read_as_an_extension(self):
        self.assertEqual(wh.classify_path(".gitignore"), ("Other", "other"))


class TestAcKey(unittest.TestCase):
    """ac_key resolves a store path to the criterion's identity, not its location."""

    def test_returns_the_identifier_stem(self):
        self.assertEqual(
            wh.ac_key("docs/acceptance-criteria/ac-store/ACS-100.yaml"), "ACS-100"
        )

    def test_same_criterion_in_a_feature_folder_yields_the_same_key(self):
        # A record moving into a feature folder must not read as a new criterion;
        # keying on the path would score the move as one filed and one vanished.
        root = wh.ac_key("docs/acceptance-criteria/build-orchestration/BO-2400f-13.yaml")
        moved = wh.ac_key(
            "docs/acceptance-criteria/build-orchestration/fast-lane/BO-2400f-13.yaml"
        )
        self.assertEqual(root, moved)

    def test_registry_index_is_not_a_criterion(self):
        self.assertIsNone(wh.ac_key("docs/acceptance-criteria/ac-store/index.yaml"))

    def test_non_yaml_is_not_a_criterion(self):
        self.assertIsNone(wh.ac_key("docs/acceptance-criteria/ac-store/PROJECT_CONTEXT.md"))

    def test_moved_criterion_is_not_counted_as_filed(self):
        # End-to-end intent: the same identifier at two different paths across a
        # period is a stationary record, so filed and done both stay at zero.
        before = {wh.ac_key("docs/acceptance-criteria/x/AC-1.yaml"): "done"}
        after = {wh.ac_key("docs/acceptance-criteria/x/feature/AC-1.yaml"): "done"}
        result = wh.ac_deltas(before, after)
        self.assertEqual(result["filed"], 0)
        self.assertEqual(result["done"], 0)
        self.assertEqual(result["reopened"], 0)


class TestIsTestPath(unittest.TestCase):
    """is_test_path separates test surfaces from production code."""

    def test_unit_tests_directory(self):
        # covers: INF-500e-4
        self.assertTrue(wh.is_test_path("unit_tests/agent_health/test_x.py"))

    def test_nested_tests_directory(self):
        self.assertTrue(wh.is_test_path("scripts/foo/tests/test_bar.py"))

    def test_production_module_is_not_a_test(self):
        self.assertFalse(wh.is_test_path("scripts/agent-health/weekly_health.py"))


class TestAcDeltas(unittest.TestCase):
    """ac_deltas computes criterion movement between two store snapshots."""

    def test_counts_filed_done_and_reopened(self):
        # covers: INF-500e-1
        before = {"a.yaml": "todo", "b.yaml": "done", "c.yaml": "done"}
        after = {
            "a.yaml": "done",     # closed during the period
            "b.yaml": "todo",     # reopened during the period
            "c.yaml": "done",     # unchanged
            "d.yaml": "todo",     # filed during the period
        }
        result = wh.ac_deltas(before, after)
        self.assertEqual(result["filed"], 1)
        self.assertEqual(result["done"], 1)
        self.assertEqual(result["reopened"], 1)
        self.assertEqual(result["net_done"], 0)
        self.assertEqual(result["store_size"], 4)

    def test_criterion_filed_and_closed_in_the_same_period_counts_once_as_done(self):
        result = wh.ac_deltas({}, {"new.yaml": "done"})
        self.assertEqual(result["filed"], 1)
        self.assertEqual(result["done"], 1)
        self.assertEqual(result["net_done"], 1)

    def test_deleted_criterion_is_not_counted_as_reopened(self):
        # covers: INF-500e-1
        # A record that disappears was not retracted, it was removed. Counting it
        # as a reopen would inflate the trust metric on every store cleanup.
        result = wh.ac_deltas({"gone.yaml": "done"}, {})
        self.assertEqual(result["reopened"], 0)

    def test_empty_snapshots_are_all_zero(self):
        result = wh.ac_deltas({}, {})
        self.assertEqual(result["net_done"], 0)
        self.assertEqual(result["store_size"], 0)


class TestSafeRatio(unittest.TestCase):
    """safe_ratio returns None rather than raising on a zero denominator."""

    def test_normal_division(self):
        self.assertAlmostEqual(wh.safe_ratio(1, 4), 0.25)

    def test_zero_denominator_returns_none(self):
        self.assertIsNone(wh.safe_ratio(5, 0))

    def test_zero_numerator_is_zero_not_none(self):
        self.assertEqual(wh.safe_ratio(0, 3), 0.0)


class TestCompositeScore(unittest.TestCase):
    """composite_score discounts delivery by how much of it was retracted."""

    def test_clean_week_scores_its_full_net(self):
        self.assertAlmostEqual(wh.composite_score(40, 40, 0), 40.0)

    def test_fully_retracted_week_scores_zero(self):
        self.assertAlmostEqual(wh.composite_score(0, 40, 40), 0.0)

    def test_negative_net_produces_a_negative_score(self):
        # 36 closed, 47 reopened -> net -11, reopen rate 1.306
        self.assertLess(wh.composite_score(-11, 36, 47), 0)

    def test_no_closures_returns_none(self):
        self.assertIsNone(wh.composite_score(0, 0, 0))


class TestIsoWeekStarts(unittest.TestCase):
    """iso_week_starts returns Mondays, oldest first, ending with this week."""

    def test_returns_requested_number_of_mondays(self):
        weeks = wh.iso_week_starts(date(2026, 8, 26), 4)
        self.assertEqual(len(weeks), 4)
        self.assertTrue(all(w.weekday() == 0 for w in weeks))

    def test_last_entry_is_the_monday_of_the_reference_week(self):
        # covers: INF-500e-5
        weeks = wh.iso_week_starts(date(2026, 8, 26), 3)  # a Wednesday
        self.assertEqual(weeks[-1], date(2026, 8, 24))

    def test_ordered_oldest_first(self):
        # covers: INF-500e-5
        weeks = wh.iso_week_starts(date(2026, 8, 26), 3)
        self.assertEqual(weeks, sorted(weeks))

    def test_a_monday_reference_maps_to_itself(self):
        weeks = wh.iso_week_starts(date(2026, 8, 24), 1)
        self.assertEqual(weeks, [date(2026, 8, 24)])

    def test_zero_weeks_is_clamped_to_one(self):
        self.assertEqual(len(wh.iso_week_starts(date(2026, 8, 26), 0)), 1)


class TestCollectCycleTimes(unittest.TestCase):
    """collect_cycle_times ages each criterion closed during the period."""

    def test_age_is_measured_from_first_appearance_to_period_end(self):
        ages = wh.collect_cycle_times(
            after={"a.yaml": "done"},
            before={"a.yaml": "todo"},
            births={"a.yaml": date(2026, 8, 20)},
            period_end=date(2026, 8, 26),
        )
        self.assertEqual(ages, [6])

    def test_already_done_criteria_are_excluded(self):
        ages = wh.collect_cycle_times(
            after={"a.yaml": "done"},
            before={"a.yaml": "done"},
            births={"a.yaml": date(2026, 8, 1)},
            period_end=date(2026, 8, 26),
        )
        self.assertEqual(ages, [])

    def test_criterion_with_no_known_birth_is_skipped_not_zero(self):
        # covers: INF-500e-3-i
        ages = wh.collect_cycle_times(
            after={"a.yaml": "done"}, before={}, births={}, period_end=date(2026, 8, 26)
        )
        self.assertEqual(ages, [])

    def test_birth_after_period_end_clamps_to_zero(self):
        # covers: INF-500e-3-i
        ages = wh.collect_cycle_times(
            after={"a.yaml": "done"},
            before={"a.yaml": "todo"},
            births={"a.yaml": date(2026, 8, 30)},
            period_end=date(2026, 8, 26),
        )
        self.assertEqual(ages, [0])


class TestCollectLaneHealth(unittest.TestCase):
    """The lane section must distinguish 'no data' from a 0% completion rate."""

    def _sink(self, lines: list[dict]) -> Path:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for entry in lines:
            handle.write(json.dumps(entry) + "\n")
        handle.close()
        return Path(handle.name)

    def test_absent_sink_reports_unavailable_with_a_reason(self):
        result = wh.collect_lane_health(Path("/nonexistent/telemetry.jsonl"))
        self.assertFalse(result["available"])
        self.assertIn("absent", result["reason"])

    def test_sink_with_no_lane_events_is_unavailable_not_zero_percent(self):
        # covers: INF-500e-2
        # This is the live state of the repo's sink: events exist, but none are
        # lane-run events. Reporting 0% completion here would assert that runs
        # were attempted and all failed, which is a different and false claim.
        path = self._sink([
            {"event": "knowledge_captured", "agent": "it-po"},
            {"event": "knowledge_captured", "agent": "product-owner"},
        ])
        try:
            result = wh.collect_lane_health(path)
            self.assertFalse(result["available"])
            self.assertIsNone(result["completion_rate"])
            self.assertEqual(result["event_total"], 2)
            self.assertIn("none are lane-run events", result["reason"])
        finally:
            path.unlink()

    def test_lane_events_produce_a_completion_rate(self):
        path = self._sink([
            {"event": "run_started", "lane": "fast"},
            {"event": "run_started", "lane": "fast"},
            {"event": "pr_opened", "lane": "fast"},
            {"event": "halted", "lane": "fast"},
        ])
        try:
            result = wh.collect_lane_health(path)
            self.assertTrue(result["available"])
            self.assertEqual(result["starts"], 2)
            self.assertEqual(result["successes"], 1)
            self.assertEqual(result["halts"], 1)
            self.assertAlmostEqual(result["completion_rate"], 0.5)
        finally:
            path.unlink()

    def test_malformed_line_is_skipped_without_raising(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        handle.write('{"event": "run_started", "lane": "fast"}\n')
        handle.write("not json at all\n")
        handle.write('{"event": "pr_opened", "lane": "fast"}\n')
        handle.close()
        path = Path(handle.name)
        try:
            result = wh.collect_lane_health(path)
            self.assertEqual(result["starts"], 1)
            self.assertEqual(result["successes"], 1)
        finally:
            path.unlink()


class TestPrCoverageFloor(unittest.TestCase):
    """A capped GitHub page must not report its truncation as a quiet week.

    `gh pr list` returns the N most recently merged PRs repository-wide. An
    under-provisioned --limit does not error; it stops short, and the oldest
    weeks show a low count indistinguishable from a genuine lull. Observed on
    this repo: --weeks 2 budgeted 120 results and reported 51 PRs for the week
    of 2026-08-17, while --weeks 8 budgeted 480 and reported 59 for the same week.
    """

    def test_uncapped_page_covers_every_week(self):
        floor, reason = pr_floor = wh.pr_coverage_floor(
            returned=120, limit=480,
            merged_dates=[date(2026, 8, 25)], earliest_week=date(2026, 7, 6),
        )
        self.assertIsNone(floor)
        self.assertEqual(reason, "")
        self.assertEqual(len(pr_floor), 2)

    def test_capped_page_reaching_far_enough_still_covers(self):
        floor, reason = wh.pr_coverage_floor(
            returned=480, limit=480,
            merged_dates=[date(2026, 7, 1), date(2026, 8, 25)],
            earliest_week=date(2026, 7, 6),
        )
        self.assertIsNone(floor)
        self.assertEqual(reason, "")

    def test_capped_page_stopping_short_reports_a_floor(self):
        # covers: INF-500e-2-i
        floor, reason = wh.pr_coverage_floor(
            returned=120, limit=120,
            merged_dates=[date(2026, 8, 17), date(2026, 8, 25)],
            earliest_week=date(2026, 7, 6),
        )
        self.assertEqual(floor, date(2026, 8, 17))
        self.assertIn("cap", reason)
        self.assertIn("2026-08-17", reason)

    def test_empty_page_is_not_treated_as_truncated(self):
        floor, reason = wh.pr_coverage_floor(
            returned=0, limit=480, merged_dates=[], earliest_week=date(2026, 7, 6)
        )
        self.assertIsNone(floor)
        self.assertEqual(reason, "")


class TestAcBirthDates(unittest.TestCase):
    """ac_birth_dates establishes first appearance by walking a real git log.

    Every other cycle-time test injects a `births` mapping directly, which
    proves the consumer and leaves the producer unexercised. This class drives
    `ac_birth_dates` against an actual repository so the claim "age is measured
    from first appearance, not from the last time the file was written" is
    proven end to end rather than assumed.
    """

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="wh_birth_"))
        self.store = self.repo / "docs" / "acceptance-criteria" / "comp"
        self.store.mkdir(parents=True)
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        )

    def _commit(self, message, when):
        stamp = f"{when}T12:00:00"
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-q", "-m", message],
            check=True, capture_output=True, text=True,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.repo),
                "GIT_AUTHOR_DATE": stamp,
                "GIT_COMMITTER_DATE": stamp,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            },
        )

    def test_birth_is_the_first_add_not_the_latest_write(self):
        # covers: INF-500e-3
        (self.store / "AC-1.yaml").write_text("id: AC-1\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("add AC-1", "2026-08-01")

        (self.store / "AC-1.yaml").write_text("id: AC-1\nwork_status: done\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("edit AC-1", "2026-08-15")

        births = wh.ac_birth_dates(self.repo, "HEAD")
        self.assertEqual(births["AC-1"], date(2026, 8, 1))

    def test_moving_a_criterion_does_not_reset_its_age(self):
        # covers: INF-500e-3
        # The move re-adds the file at a new path. Keying by identifier and
        # keeping the earliest add is what stops the criterion reading as
        # newly born on the day it was reorganised.
        (self.store / "AC-2.yaml").write_text("id: AC-2\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("add AC-2", "2026-08-02")

        feature = self.store / "feature"
        feature.mkdir()
        self._git("mv", "docs/acceptance-criteria/comp/AC-2.yaml",
                  "docs/acceptance-criteria/comp/feature/AC-2.yaml")
        self._commit("move AC-2 into a feature folder", "2026-08-20")

        births = wh.ac_birth_dates(self.repo, "HEAD")
        self.assertEqual(births["AC-2"], date(2026, 8, 2))

    def test_registry_index_is_excluded_from_the_index(self):
        # covers: INF-500e-3
        (self.store / "index.yaml").write_text("component: comp\n", encoding="utf-8")
        (self.store / "AC-3.yaml").write_text("id: AC-3\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("add AC-3 and the registry index", "2026-08-03")

        births = wh.ac_birth_dates(self.repo, "HEAD")
        self.assertIn("AC-3", births)
        self.assertNotIn("index", births)

    def test_repository_with_no_store_yields_an_empty_index(self):
        # covers: INF-500e-3
        (self.repo / "README.md").write_text("no store here\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("no acceptance criteria at all", "2026-08-04")

        self.assertEqual(wh.ac_birth_dates(self.repo, "HEAD"), {})


class TestReportEndToEnd(unittest.TestCase):
    """One command produces the whole report, trust tier first.

    This is the L1-level check: `build_report` is driven against a real
    temporary repository and its output rendered, so the claim "one command
    answers both whether delivery is getting healthier and whether it is
    getting faster" is proven by running it, not by reasoning about the parts.
    """

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="wh_e2e_"))
        self.store = self.repo / "docs" / "acceptance-criteria" / "comp"
        self.store.mkdir(parents=True)
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")

        (self.store / "AC-1.yaml").write_text("id: AC-1\nwork_status: todo\n", encoding="utf-8")
        (self.repo / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("seed the store and a module", "2026-08-18")

        (self.store / "AC-1.yaml").write_text("id: AC-1\nwork_status: done\n", encoding="utf-8")
        (self.repo / "notes.md").write_text("# notes\n\nprose\n", encoding="utf-8")
        self._git("add", "-A")
        self._commit("close AC-1 and add prose", "2026-08-25")

        self.report = wh.build_report(
            self.repo, weeks=2, today=date(2026, 8, 26),
            telemetry_path=self.repo / "nonexistent.jsonl", use_gh=False,
        )
        self.rendered = wh._render_markdown(self.report)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        )

    def _commit(self, message, when):
        stamp = f"{when}T12:00:00"
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-q", "-m", message],
            check=True, capture_output=True, text=True,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.repo),
                "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp,
                "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            },
        )

    def test_one_run_answers_both_health_and_speed(self):
        # covers: INF-500e
        for heading in ("Tier 1 — Trust", "Tier 2 — Autonomy",
                        "Tier 3 — Velocity", "Code volume by language"):
            self.assertIn(heading, self.rendered)

    def test_trust_tier_is_rendered_before_the_velocity_tier(self):
        # covers: INF-500e
        # Ordering is the guarantee, not decoration: velocity read over an
        # untrusted store is meaningless, so trust has to come first.
        self.assertLess(
            self.rendered.index("Tier 1 — Trust"),
            self.rendered.index("Tier 3 — Velocity"),
        )

    def test_the_closed_criterion_is_counted_in_the_period_it_closed(self):
        # covers: INF-500e
        by_week = {p["week"]: p for p in self.report["periods"]}
        self.assertEqual(by_week["2026-08-24"]["ac_done"], 1)
        self.assertEqual(by_week["2026-08-24"]["ac_reopened"], 0)

    def test_absent_telemetry_renders_a_named_reason_not_a_zero_rate(self):
        # covers: INF-500e
        self.assertIn("No lane data", self.rendered)
        self.assertNotIn("Completion rate: 0%", self.rendered)


class TestUnknownIsNotZero(unittest.TestCase):
    """A figure that could not be obtained must not render as 0.

    A transient `gh` failure once produced a TSV row reading `0` merged PRs for
    every week. Zero-as-unknown is indistinguishable from zero-as-none-merged,
    which is the false-green shape the trust tier exists to surface.
    """

    def test_int_formatter_distinguishes_unknown_from_zero(self):
        # covers: INF-500e-2
        self.assertEqual(wh._int(0), "0")
        self.assertEqual(wh._int(None), "—")

    def test_ratio_of_propagates_unknown_numerator(self):
        self.assertIsNone(wh._ratio_of(None, 10))

    def test_ratio_of_propagates_unknown_denominator(self):
        self.assertIsNone(wh._ratio_of(5, None))

    def test_ratio_of_computes_when_both_known(self):
        self.assertAlmostEqual(wh._ratio_of(5, 10), 0.5)

    def test_tsv_renders_unknown_pr_counts_as_empty_not_zero(self):
        report = {
            "periods": [{
                "week": "2026-08-24", "days": 3, "commits": 69,
                "prs_available": False, "prs": None, "feat_prs": None, "fix_prs": None,
                "prod_loc": 6435, "test_loc": 21696, "ac_filed": 321, "ac_done": 40,
                "ac_reopened": 46, "ac_net_done": -6, "reopen_rate": 1.15,
                "composite": -2.79, "ki_open": 122, "ki_filed": 73, "ki_closed": 2,
                "ki_repeats": 29, "rework": 12, "cycle_median": 1.0,
            }],
        }
        lines = wh._render_tsv(report).splitlines()
        header, row = lines[0].split("\t"), lines[1].split("\t")
        self.assertEqual(row[header.index("prs")], "")
        self.assertEqual(row[header.index("prs_available")], "False")
        # A genuinely-measured figure still renders its value.
        self.assertEqual(row[header.index("commits")], "69")

    def test_tsv_renders_a_real_zero_as_zero(self):
        report = {
            "periods": [{
                "week": "2026-07-27", "days": 7, "commits": 0,
                "prs_available": True, "prs": 0, "feat_prs": 0, "fix_prs": 0,
                "prod_loc": 0, "test_loc": 0, "ac_filed": 0, "ac_done": 0,
                "ac_reopened": 0, "ac_net_done": 0, "reopen_rate": None,
                "composite": None, "ki_open": 0, "ki_filed": 0, "ki_closed": 0,
                "ki_repeats": 0, "rework": 0, "cycle_median": None,
            }],
        }
        lines = wh._render_tsv(report).splitlines()
        header, row = lines[0].split("\t"), lines[1].split("\t")
        self.assertEqual(row[header.index("prs")], "0")
        self.assertEqual(row[header.index("cycle_median")], "")


if __name__ == "__main__":
    unittest.main()
