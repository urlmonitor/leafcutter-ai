"""
MODULE: remedy_handoff
GOAL: Turn a hook's structured refusal record plus its remedy declaration into the
    ``status: handoff`` payload a depth-1 commit agent returns, so a depth-0 dispatcher
    can engage the declared restructuring specialist.
BUSINESS CONTEXT: BO-3800a-2. The commit agent runs at depth 1 and cannot spawn
    (ADR-019); it hands off instead (BO-3000a). The payload is built here, by a
    script, so the agent passes it through and never composes it from refusal prose.
ARCHITECTURE: Run from the project root as ``python remedy_handoff.py --hook-id <id>``
    with the hook's refusal output on stdin. The demand is the ``*REFUSAL_RECORD:``
    JSON list the hook printed, verbatim and in refusal order. The disposition,
    skills and specialist come from the shared loader ``_remedy_declarations``, never
    from the prose. Exactly one JSON object is printed on success. Unreadable input,
    a missing record or a hook without an engage-specialist declaration exits
    non-zero with a named reason on stderr and nothing on stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from _remedy_declarations import RemedyInputError, load

RECORD_LINE = re.compile(r"^\s*[A-Z_]*REFUSAL_RECORD:\s*(\[.*\])\s*$")


class HandoffInputError(Exception):
    """The refusal output or declaration cannot be turned into a handoff payload."""


def read_demand(refusal_output: str) -> list:
    """Return the machine-readable demand from a hook's refusal output.

    Args:
        refusal_output: The full text the refusing hook printed.

    Returns:
        The parsed record list, verbatim and in refusal order.

    Raises:
        HandoffInputError: No record line, an unparseable one, or an empty record.
    """
    for line in refusal_output.splitlines():
        match = RECORD_LINE.match(line)
        if not match:
            continue
        try:
            demand = json.loads(match.group(1))
        except ValueError as exc:
            msg = f"the refusal record line is not valid JSON: {exc}"
            raise HandoffInputError(msg) from exc
        if not demand:
            msg = "the refusal record is empty"
            raise HandoffInputError(msg)
        return demand
    msg = "the refusal output carries no REFUSAL_RECORD line"
    raise HandoffInputError(msg)


def build_payload(hook_id: str, refusal_output: str) -> dict:
    """Build the handoff payload for one refused hook.

    Args:
        hook_id: Registered id of the refusing hook.
        refusal_output: The text the hook printed when it refused.

    Returns:
        The ``status: handoff`` payload naming the declared specialist.

    Raises:
        HandoffInputError: Unreadable declaration, no engage-specialist declaration
            naming a party, or no readable demand.
    """
    try:
        decl = load(hook_id)
    except RemedyInputError as exc:
        msg = f"cannot read the remedy declaration of {hook_id}: {exc}"
        raise HandoffInputError(msg) from exc
    if not decl or decl.get("disposition") != "engage-specialist" or not decl.get("agent"):
        msg = f"{hook_id} has no engage-specialist declaration naming a party"
        raise HandoffInputError(msg)
    demand = read_demand(refusal_output)
    agent = decl["agent"]
    return {
        "status": "handoff",
        "handoff_target": agent,
        "record_handoff_target": agent,
        "flips_signed_off": False,
        "message": f"{hook_id} refused the commit; {agent} is needed to meet the demand, then the commit is re-offered unchanged.",
        "remedy": {
            "hook_id": hook_id,
            "disposition": decl["disposition"],
            "skills": decl["skills"],
            "demand": demand,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Read the refusal from stdin and print the payload.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        0 with the payload on stdout, or 1 with a named reason on stderr.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hook-id", required=True)
    args = parser.parse_args(argv)
    try:
        refusal_output = sys.stdin.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[remedy-handoff] cannot read the refusal output: {exc}", file=sys.stderr)
        return 1
    try:
        payload = build_payload(args.hook_id, refusal_output)
    except HandoffInputError as exc:
        print(f"[remedy-handoff] {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
