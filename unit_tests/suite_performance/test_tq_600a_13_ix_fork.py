"""TQ-600a-13-ix: a pull request from a fork receives the verdict and the requests a same-repository pull request receives.

The check never branches on ``pull_request.head.repo.full_name``. Each history (red, green, unreadable) is evaluated through the
job's own ``main`` with a same-repository payload and with a fork payload (and one whose fork was deleted: ``head.repo`` null),
and the exit code, the output, the comment the check keeps and the exact set of requests the service saw must be identical.
"""

from __future__ import annotations

import re

from ._comment_harness import PR, write_event
from ._ending_harness import CHECK, Cases
from ._exempt_harness import HEAD
from ._ix_harness import FAST_ENV, WORKFLOW_PATH, FaultCase, http, run_main
from ._notice_fakes import REPO

STAMP = re.compile(r"Evaluated at \S+;")


def _head(repo):
    return {"sha": HEAD, "ref": "fix/it", "repo": repo}


PAYLOADS = {
    "same repository": _head({"full_name": REPO, "fork": False}),
    "fork": _head({"full_name": "someone-else/leafcutter-ai", "fork": True}),
    "deleted fork": _head(None),
}


class ForkPullRequests(FaultCase):
    def _world(self, history):
        self.svc.reset()
        if history == "red":
            self.red_history()
        elif history == "green":
            self.green_history()
        else:
            self.green_history()
            self.svc.fail("GET", WORKFLOW_PATH, http(403))

    def _observe(self, history, head):
        """One evaluation of the pull request in a freshly served world: what a user and the service could tell."""
        self._world(history)
        payload = self.event("A change.")
        payload["pull_request"]["head"] = head
        ran = run_main(self.svc.url, write_event(self.tmp, payload), FAST_ENV)
        comments = [STAMP.sub("Evaluated at T;", c["body"]) for c in self.svc.pr_comments.get(PR, [])]
        return {"exit": ran.code, "out": ran.out, "requests": sorted(self.svc.requests), "writes": self.svc.kinds(), "comments": comments}

    def test_tq600a_13_ix_a_fork_pull_request_gets_the_same_verdict(self):
        # covers: TQ-600a-13-ix
        # angle: criterion
        """AC TQ-600a-13-ix: red, green and unreadable histories give a fork the same exit, output, comment and requests as the repository itself.

        Wrong version caught: the check branches on the head repository and skips the comment or the verdict for a fork.
        """
        cases = Cases()
        expected_exit = {"red": 1, "green": 0, "unreadable": 1}
        for history, code in expected_exit.items():
            seen = {name: self._observe(history, head) for name, head in PAYLOADS.items()}
            base = seen["same repository"]
            with cases.case(f"{history}: the same-repository answer is the one the history calls for"):
                CHECK.assertEqual(code, base["exit"], base["out"])
                CHECK.assertEqual([] if history == "green" else ["create"], base["writes"], "a held PR gets its one comment; a passing one gets none")
                CHECK.assertTrue(base["requests"], "the check read nothing")
            for name in ("fork", "deleted fork"):
                with cases.case(f"{history}: {name} equals same repository"):
                    for field in ("exit", "out", "writes", "comments", "requests"):
                        CHECK.assertEqual(base[field], seen[name][field], f"{field} differs for a {name}")
        cases.check()
