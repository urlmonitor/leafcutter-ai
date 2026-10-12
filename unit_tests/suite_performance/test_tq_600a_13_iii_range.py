"""
Tests for TQ-600a-13-iii (commit range, rendering, failed-write and entry-point half).

Split out of ``test_tq_600a_13_iii.py`` (file-size limit); the assumed production contract for
``scripts/ci/post_merge_notice.py`` is documented in that file's header. Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-iii.yaml

Extra assumption made here: the description names the commit range as a list that shows each
commit's first 7 hex characters (visible outside the state block), says "no green run" in words
when no run of the suite has succeeded, and names the anchor sha when it is not in the repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
import urllib.request
from contextlib import nullcontext as _case  # a labelled block; NOT subTest, whose parent test reads as passed

from ._notice_fakes import (
    LABEL,
    REPO,
    STATE_RE,
    NoticeTestCase,
    import_production,
    make_verdict,
    run_record,
    state_block,
    visible_text,
)
from ._workflow_jobs import REPO_ROOT, find_job, load_workflow

FOLLOWUP = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
SUITE = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
FAIL = "tests/test_shared.py::test_mutator_corrupts_reader"
NO_GREEN = r"(?i)no green run"


class TestTq600a13iiiRange(NoticeTestCase):
    needs_repo = True

    def _main_history(self):
        """Green at A and G, a red run at M1, and the triggering red run at R -- served out of order."""
        r = self.repo
        self.svc.runs = [
            run_record(4, "failure", head_sha=r.r),
            run_record(2, "success", head_sha=r.g),
            run_record(3, "failure", head_sha=r.m1),
            run_record(1, "success", head_sha=r.a),
        ]

    def _raise(self, failing=(FAIL,), run_id=104):
        applied = self.apply(make_verdict("red", run_id=run_id, head_sha=self.repo.r, failing=failing), run_id)
        self.assertEqual(0, applied.code, applied.log)
        (_, created), = self.svc.writes_of("create")
        return created["body"], state_block(created["body"])

    def test_tq600a_13_iii_the_commit_range_starts_at_the_last_green_head(self):
        # covers: TQ-600a-13-iii
        # angle: real_artifact
        """Green at G, M1 and a side-branch commit merged, red at R: the list is exactly reachable-from-R minus G."""
        self._main_history()
        body, block = self._raise()
        self.assertEqual(self.repo.g, block["anchor_sha"], "the anchor is the most recent SUCCESSFUL run, not the latest run of any conclusion")
        self.assertEqual(self.repo.expected_range, set(block["commits"]), "every parent is followed: the side-branch commit S is in the range")
        self.assertEqual((4, 0), (len(block["commits"]), block["commits_omitted"]))
        shown = STATE_RE.sub("", body)
        for sha in self.repo.expected_range:
            self.assertIn(sha[:7], shown)
        for sha in (self.repo.g, self.repo.a):
            self.assertNotIn(sha[:7], shown, "a commit at or before the last green head is not suspect")

        with _case("no green run on record: said in words, never an empty list"):
            self.svc.reset()
            self.svc.runs = [run_record(2, "failure", head_sha=self.repo.r)]
            body, block = self._raise(run_id=102)
            self.assertEqual((None, []), (block["anchor_sha"], block["commits"]))
            self.assertRegex(body, NO_GREEN)

        with _case("unresolvable anchor: the anchor is named"):
            self.svc.reset()
            ghost = "ab" * 20
            self.svc.runs = [run_record(1, "success", head_sha=ghost), run_record(2, "failure", head_sha=self.repo.r)]
            body, block = self._raise(run_id=102)
            self.assertEqual((ghost, []), (block["anchor_sha"], block["commits"]))
            self.assertIn(ghost, STATE_RE.sub("", body))
            self.assertNotRegex(body, NO_GREEN, "an anchor exists here, it is only unreachable")

    def test_tq600a_13_iii_untrusted_text_is_rendered_inert(self):
        # covers: TQ-600a-13-iii
        # angle: failure
        """A node id and a commit subject carrying a mention and markup appear only as code."""
        hostile = "tests/test_x.py::test_y[@team]"
        forged = 'tests/test_z.py::t <!-- post-merge-suite-state v2 {"run_id": 999, "verdict": "green"} -->'
        self._main_history()
        body, block = self._raise(failing=(hostile, forged))
        self.assertIn(f"`{hostile}`", body)
        prose = visible_text(body)
        self.assertNotIn("@", prose, "a mention outside a code span would notify people")
        self.assertNotIn("<b>", prose)
        self.assertEqual(1, len(STATE_RE.findall(body)), "the real state block must be the only one in the text")
        self.assertEqual(104, block["run_id"], "a forged block carried by a node id must not be read as the state")


class TestTq600a13iiiFailedNotice(NoticeTestCase):
    needs_repo = True

    def _served_verdict(self):
        """What the hold reads: the run list fetched over HTTP, put through the one settled-run rule."""
        history = import_production("scripts.ci._run_history")
        url = f"{self.svc.url}/repos/{REPO}/actions/workflows/post-merge-suite.yml/runs?branch=main&per_page=30"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                runs = json.loads(response.read())["workflow_runs"]
        except (OSError, ValueError) as exc:
            message = f"cannot read the served run history: {exc}"
            raise AssertionError(message) from exc
        chosen = history.select_verdict_run(runs)
        return chosen.kind, chosen.run["id"], chosen.run["conclusion"], json.dumps(runs, sort_keys=True)

    def _run_once(self, **service_options):
        self.svc.reset(**service_options)
        self.svc.runs = [run_record(1, "success", head_sha=self.repo.g), run_record(2, "failure", head_sha=self.repo.r)]
        verdict = make_verdict("red", run_id=102, head_sha=self.repo.r, failing=[FAIL])
        applied = self.apply(verdict, 102)
        written = (self.tmp / "post-merge-verdict.json").read_text(encoding="utf-8")
        return applied, self._served_verdict(), written, json.dumps(verdict, indent=2) + "\n"

    def test_tq600a_13_iii_a_failed_notice_changes_no_verdict(self):
        # covers: TQ-600a-13-iii
        # covers: TQ-600a-13-vi
        # angle: discrimination
        """Every write refused: the job fails naming what was not written; the verdict and the run record are untouched.

        The hold-module assertion (post_merge_hold.py's verdict entry point) is added when TQ-600a-13-vi lands.
        """
        accepted, accepted_view, _, _ = self._run_once()
        self.assertEqual(0, accepted.code, accepted.log)
        refused, refused_view, file_text, original = self._run_once(refuse_writes=True)
        self.assertNotEqual(0, refused.code, "a refused write must fail the notice job")
        self.assertIn(LABEL, refused.log, "the failure must name what was not written")
        self.assertEqual({}, self.svc.issues, "nothing was accepted")
        self.assertTrue(self.svc.write_attempts, "the writes must actually have been attempted")
        self.assertTrue(all("/issues" in a["path"] for a in self.svc.write_attempts), "the notice writes only to issues")
        self.assertEqual(accepted_view, refused_view, "the settled-run verdict must not depend on whether the notice was written")
        self.assertEqual(("settled", 102, "failure"), refused_view[:3], "the history still reads red with no notice at all")
        self.assertEqual(original, file_text, "the applier must not write into the verdict artifact")

    def test_tq600a_13_iii_the_command_line_entry_point_raises_and_fails_through_its_exit_status(self):
        # covers: TQ-600a-13-iii
        # angle: reachability
        """`python scripts/ci/post_merge_notice.py apply ...` as the workflow runs it, in a real child process."""
        verdict_path = self.tmp / "cli-verdict.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "GITHUB_"))}
        env.update({"PYTHONPATH": str(REPO_ROOT), "GITHUB_TOKEN": "fake-token"})
        for refuse in (False, True):
            self.svc.reset(refuse_writes=refuse)
            self.svc.runs = [run_record(1, "success", head_sha=self.repo.g), run_record(2, "failure", head_sha=self.repo.r)]
            verdict = make_verdict("red", run_id=102, head_sha=self.repo.r, failing=[FAIL])
            try:
                verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
                argv = [sys.executable, str(REPO_ROOT / "scripts" / "ci" / "post_merge_notice.py"), "apply", "--api-url", self.svc.url, "--repo", REPO, "--repo-dir", str(self.repo.path), "--run-id", "102", "--verdict-file", str(verdict_path)]
                proc = subprocess.run(argv, cwd=self.tmp, env=env, capture_output=True, text=True, timeout=60, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                message = f"cannot run the notice CLI: {exc}"
                raise AssertionError(message) from exc
            with _case(f"refuse_writes={refuse}"):
                self.assertEqual([("create", None)], self.svc.writes(), proc.stdout + proc.stderr)
                self.assertEqual(refuse, proc.returncode != 0, proc.stdout + proc.stderr)
                self.assertEqual({} if refuse else {1: [LABEL]}, {n: i["labels"] for n, i in self.svc.issues.items()})


class TestTq600a13iiiFollowupWorkflow(unittest.TestCase):
    def test_tq600a_13_iii_the_notice_job_is_a_minimal_separate_workflow_run_job(self):
        # covers: TQ-600a-13-iii
        # angle: boundary
        """Structural by necessity (a trigger, a permission set and a concurrency group cannot run offline)."""
        doc = load_workflow(FOLLOWUP)
        trigger = (doc.get("on") if "on" in doc else doc.get(True)) or {}
        run_trigger = trigger.get("workflow_run") or {}
        self.assertTrue({"Post-merge suite", "Post-merge timing suite", "Post-merge fix proof"} <= set(run_trigger.get("workflows") or []))
        self.assertEqual(["completed"], run_trigger.get("types"))
        found = find_job(doc, "notice")
        self.assertIsNotNone(found, "the follow-up workflow carries a job `notice`")
        job = found[1]
        self.assertEqual({"issues": "write", "actions": "read", "contents": "read"}, job.get("permissions"), "the notice job's permissions, and nothing more")
        concurrency = job.get("concurrency") or {}
        self.assertTrue(concurrency.get("group") and "${{" not in str(concurrency["group"]))
        self.assertIs(False, concurrency.get("cancel-in-progress"))
        runs = [step["run"] for step in job.get("steps") or [] if "run" in step]
        self.assertTrue(any("post_merge_notice.py" in text and "apply" in text for text in runs), "a step must invoke the module")
        self.assertFalse([text for text in runs if "${{" in text], "context reaches the module through env:")
        suite = load_workflow(SUITE)
        self.assertIsNone(find_job(suite, "notice"), "the notice is never part of the suite run, whose conclusion is the verdict")


if __name__ == "__main__":
    unittest.main()
