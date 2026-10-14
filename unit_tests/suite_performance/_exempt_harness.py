"""Test infrastructure for TQ-600a-13-viii (the one exemption from the post-merge hold). Not a test: underscore-named.

* ``ExemptService`` -- the hold's recording fake (issues, run history, a run's jobs, the pull request's comments and
  the notice issue's comments, all through ``CommentService``) plus the two reads -viii adds: the runs of
  ``post-merge-fix-proof.yml`` (filtered by ``head_sha`` and ``event`` and truncated by ``per_page`` the way the hosting
  service does, served OLDEST first so "take the first one" is not the right answer) and the runs of
  ``post-merge-followup.yml`` (filtered by ``head_sha``). It can fail any read by path prefix.
* ``ExemptCase`` -- the test case. ``stage`` serves a red (or did-not-complete) verdict run that settled at ``SETTLED``,
  its notice described by the REAL notice producer, and a follow-up run; ``add_proof`` serves one proof run and its jobs;
  ``drive_body`` runs the REAL ``main`` (the job's own entry point) with an event file written by ``json.dump``.
* ``SETTLED`` is the red run's ``updated_at`` (the time it settled). A proof is "of the current red run" only when it
  started strictly after it.
"""

from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from ._comment_harness import PR, CommentService, CommentTestCase, notice_description, pr_event, run_main, write_event
from ._ending_harness import CHECK
from ._hold_harness import DNC_JOBS, NOW, RED_JOBS, make_job, make_run
from ._notice_fakes import REPO, SERVER

HEAD, OTHER_HEAD, RED_HEAD = "9" * 40, "8" * 40, "7" * 40
NOTICE = 12
SETTLED = NOW - timedelta(hours=1)
PROOF_PATH = f"/repos/{REPO}/actions/workflows/post-merge-fix-proof.yml/runs"
FOLLOWUP_PATH = f"/repos/{REPO}/actions/workflows/post-merge-followup.yml/runs"
FOLLOWUP_URL = f"{SERVER}/{REPO}/actions/runs/555"
DECL = "Fixes #12"


def stamp(moment):
    """An API timestamp (``...Z``) for an aware datetime."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def followup(run_id, number, head_sha):
    """A run of the follow-up workflow as ``workflow_run`` triggers it (its ``head_sha`` is the triggering run's)."""
    return {"id": run_id, "run_number": number, "status": "completed", "conclusion": "failure", "event": "workflow_run", "head_sha": head_sha,
            "head_branch": "main", "html_url": f"{SERVER}/{REPO}/actions/runs/{run_id}", "path": ".github/workflows/post-merge-followup.yml"}


class ExemptService(CommentService):
    """``CommentService`` plus the proof runs and the follow-up runs; every other path is the shared fake's."""

    def reset(self, **kwargs):
        super().reset(**kwargs)
        self.proof_runs, self.followup_runs = [], []

    def handle(self, method, raw_path, body):
        parsed = urlparse(raw_path)
        if method == "GET" and parsed.path in (PROOF_PATH, FOLLOWUP_PATH):
            self.requests.append((method, raw_path))
            if any(parsed.path.startswith(prefix) for prefix in self.failing):
                return 500, {"message": "Server Error"}
            query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            pool = self.proof_runs if parsed.path == PROOF_PATH else self.followup_runs
            runs = [r for r in pool if query.get("head_sha") in (None, r["head_sha"]) and query.get("event") in (None, r["event"])]
            runs = sorted(runs, key=lambda r: r["run_number"])[-min(int(query.get("per_page", 30)), 100) :]
            return 200, {"total_count": len(runs), "workflow_runs": runs}
        return super().handle(method, raw_path, body)

    def seen(self, fragment):
        """Every request (method, path, query) whose path contains ``fragment``."""
        found = [(m, urlparse(raw)) for m, raw in self.requests if fragment in urlparse(raw).path]
        return [(m, u.path, {k: v[-1] for k, v in parse_qs(u.query).items()}) for m, u in found]


class ExemptCase(CommentTestCase):
    """The hold test case over an ``ExemptService``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.svc.close()
        cls.svc = ExemptService()

    # ---- the served world
    def stage(self, *, proof=True, notice=True, dnc=False):
        """A red (``dnc``: did-not-complete) verdict run settled at ``SETTLED``, its notice #12, a follow-up run, and a current proof."""
        red = make_run(7, "failure", hours_ago=2, now=NOW, head_sha=RED_HEAD)
        red["updated_at"] = stamp(SETTLED)
        self.serve([make_run(6, "success", hours_ago=4, now=NOW), red], {red["id"]: DNC_JOBS if dnc else RED_JOBS})
        self.svc.issues.clear()
        if notice:
            text = notice_description(red["id"], failing=() if dnc else ("tests/t.py::test_a",), stage="empty_selection" if dnc else None)
            self.svc.add_issue(NOTICE, title="Post-merge suite is red", body=text, labels=["post-merge-red"])
        self.svc.followup_runs = [followup(555, 9, RED_HEAD), followup(556, 10, "e" * 40)]
        if proof:
            self.add_proof()
        return red

    def add_proof(self, number=5, *, head=HEAD, started=None, conclusion="success", status="completed", event="pull_request_target", prove="success"):
        """Serve one proof run (and its two jobs); by default passing, current and on ``HEAD``. Returns the run record."""
        begun = started or SETTLED + timedelta(minutes=10)
        run_id = 200 + number
        record = {"id": run_id, "run_number": number, "status": status, "conclusion": conclusion if status == "completed" else None, "event": event,
                  "head_sha": head, "head_branch": "fix/branch", "run_started_at": stamp(begun), "updated_at": stamp(begun + timedelta(minutes=5)),
                  "html_url": f"{SERVER}/{REPO}/actions/runs/{run_id}", "path": ".github/workflows/post-merge-fix-proof.yml"}
        self.svc.proof_runs.append(record)
        job = make_job("Post-merge fix proof", prove)
        if status != "completed":
            job.update(status=status, conclusion=None)
        self.svc.jobs[run_id] = [make_job("Prepare fix proof", "success"), job]
        return record

    # ---- driving the real entry point
    @staticmethod
    def event(body, *, number=PR, head=HEAD, **pull):
        """An ``edited`` pull request payload shaped like the platform's; ``pull`` overrides or adds ``pull_request`` keys."""
        payload = pr_event(number)
        payload["repository"] = {"full_name": REPO}
        payload["pull_request"].update({"body": body, "head": {"sha": head}, **pull})
        return payload

    def drive_body(self, body, **kwargs):
        """One evaluation through the real ``main`` and a real event file whose description is ``body`` (None: null)."""
        return run_main(self.svc, write_event(self.tmp, self.event(body, **kwargs)))

    # ---- what the server saw
    def record_writes(self):
        """Every comment write on a notice issue (a create or an edit of a comment that sits on one)."""
        on_notices = {c["id"] for n in self.svc.issues for c in self.svc.pr_comments.get(n, [])}
        return [w for w in self.svc.comment_writes if w.get("pr") in self.svc.issues or w.get("id") in on_notices]

    def record_bodies(self):
        return [c["body"] for n in sorted(self.svc.issues) for c in self.svc.pr_comments.get(n, [])]

    def expect_one_record(self, *, issues=(NOTICE,), pr=PR, head=HEAD, proof_id=205, red_id=107):
        """Exactly one record, one create on one of ``issues``, naming the PR, the head and the proof, with a hidden marker."""
        writes = self.record_writes()
        CHECK.assertEqual(["create"], [w["kind"] for w in writes], f"expected one exemption record, the service saw {writes}")
        CHECK.assertIn(writes[0]["pr"], issues)
        text = writes[0]["body"]
        CHECK.assertRegex(text, rf"#{pr}\b|/pull/{pr}\b")
        CHECK.assertIn(head, text)
        CHECK.assertRegex(text, rf"\b{proof_id}\b")
        spans = re.findall(r"<!--(.*?)-->", text, re.DOTALL)
        CHECK.assertTrue(any(str(pr) in s and str(red_id) in s for s in spans), f"no hidden marker carrying PR {pr} and red run {red_id}: {spans}")

    def expect_nothing_granted(self, ran, *patterns):
        """Held (exit 1), nothing recorded on a notice, no write at all but comments, and the output says each ``pattern``."""
        CHECK.assertEqual(1, ran.code, ran.out)
        CHECK.assertEqual([], self.record_writes())
        CHECK.assertEqual([], self.svc.write_attempts)
        for pattern in patterns:
            CHECK.assertRegex(ran.out, f"(?i){pattern}")

    def expect_only_declared_reads(self):
        """No artifact read, no pull-request or commit read: the description comes from the event, the proof from two reads."""
        paths = self.svc.paths_seen()
        CHECK.assertEqual([], [p for p in paths if "/artifacts" in p or "/pulls" in p or "/commits" in p])
