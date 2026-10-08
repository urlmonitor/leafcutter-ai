"""One definition of the fast lane's claim-step reply shape, for test stubs.

`fast-lane-ship.js` dispatches its claim command step to `command-step-runner`,
whose contract is to run the given command and hand back that command's own
output untouched:

    {"command": ..., "workspace": ..., "exit_status": 0,
     "stdout": "<the command's stdout, verbatim>", "stderr": ...}

It does not read, reshape, or interpret what the command printed. So the gate
payload that the lane actually branches on — `claimed`, `excluded_claimed`,
`target_refused`, produced by `_fl_lifecycle.py` — arrives as JSON *text inside
`stdout`*, and the lane parses it out (`interpretClaimRunnerReply`).

Every workflow test that needs the lane to get past its claim step has to stub
that shape. This module exists so the shape is written down ONCE. Seven test
files previously carried their own literal copy of the older reply shape, and
when the dispatch contract changed all seven went stale together — which is the
drift `BO-2400f-7-iv` warns about in its own it_requirements: a restatement of a
contract can diverge from the contract silently, and that divergence is the
defect, not a symptom of it.

A decline is deliberately NOT modelled with an `exit_status` key, because that
absence is exactly how the lane tells "the agent would not run the command"
apart from "the command ran and reported contention". A helper that quietly
supplied `exit_status` on the decline path would erase the distinction the
tests are here to protect.
"""

from __future__ import annotations

import json
from typing import Any


def claim_ran(
    claimed: list[str],
    *,
    excluded_claimed: list[str] | None = None,
    target_refused: bool = False,
    message: str | None = None,
    include_excluded_key: bool = True,
    exit_status: int = 0,
) -> dict[str, Any]:
    """A reply from a runner that DID run the claim command.

    Args:
        claimed: ids the gate flipped to in_progress.
        excluded_claimed: ids the gate found already held by another run.
        target_refused: the gate's own refusal flag. `_fl_lifecycle.py` sets
            this only when nothing was claimable AND something was excluded, so
            a caller passing `True` with an empty excluded set is modelling a
            payload the real gate cannot emit.
        message: optional human-readable note from the gate.
        include_excluded_key: when False, omit `excluded_claimed` entirely
            rather than sending an empty list. This is the observed 2026-09-23
            shape that `BO-2400f-7-iv` exists for — absent must read as empty.
        exit_status: the command's exit status. Non-zero means the command ran
            and failed, which the lane treats as "no AC was flipped", not as
            contention.

    Returns:
        The runner-shaped reply, with the gate payload encoded into `stdout`.
    """
    payload: dict[str, Any] = {"claimed": claimed, "target_refused": target_refused}
    if include_excluded_key:
        payload["excluded_claimed"] = excluded_claimed or []
    if message is not None:
        payload["message"] = message
    return {
        "exit_status": exit_status,
        "stdout": json.dumps(payload),
        "stderr": "",
    }


def claim_declined(reason: str, step: str = "claim-connected") -> dict[str, Any]:
    """A reply from a runner that REFUSED to run the claim command at all.

    Carries no `exit_status`, which is the whole point: nothing was ever put to
    the store, so the lane must halt as not-attempted and must not describe the
    set as held by anyone.
    """
    return {
        "declined": True,
        "step": step,
        "agent": "command-step-runner",
        "reason": reason,
    }
