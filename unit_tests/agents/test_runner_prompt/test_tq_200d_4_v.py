"""
MODULE: unit_tests/agents/test_runner_prompt/test_tq_200d_4_v.py
COVERS: TQ-200d-4-v
GOAL: Red-first specification of the test-runner prompt change of TQ-200d-4-v: the fixed
    "Database Not Configured" message (the `not_configured` fenced block) ends with the sentence
    "The database tests were not run.", and nothing else of the block changes.
HONEST LIMIT: a prompt; what a model relays is proved by the recorded probes in
    unit_tests/evals/tq200d4v/. This test pins the template text, scoped to the fenced block.
RED STATE: the block has four lines and no not-run sentence.
"""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

_SUPPORT_FILE = Path(__file__).with_name("_support.py")
_spec = importlib.util.spec_from_file_location("_tq_200d_4_support", _SUPPORT_FILE)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

SENTENCE = "The database tests were not run."
SETTING = "testing_context.db_connection_test"
# The block as it stood before TQ-200d-4-v (lines 152-155 of the template); the new sentence follows it.
PRE_CHANGE_LINES = [
    "## Database Not Configured",
    "",
    "testing_context.db_connection_test is not configured. Set it in this",
    "project's skills_config.json before running database tests.",
]
SQL_SUITE_LINE = "Do NOT attempt to run the SQL suite unless the checker reports `reachable`."


def not_configured_block(text: str) -> list[str] | None:
    """The lines of the fenced block that holds the '## Database Not Configured' heading, dedented."""
    for body in S.fences(text):
        lines = textwrap.dedent(body).rstrip("\n").splitlines()
        if lines and lines[0].strip() == "## Database Not Configured":
            return [line.rstrip() for line in lines]
    return None


def test_not_configured_block_says_the_database_tests_were_not_run():
    # covers: TQ-200d-4-v
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: the sentence placed outside the fenced block
    # must_catch: another line of the block reworded
    """The not_configured block names the setting, says where to set it, ends with the new sentence."""
    text = S.read(S.TEMPLATE)
    block = not_configured_block(text)
    assert block is not None, "the template must hold the '## Database Not Configured' fenced block"
    joined = S.flat(" ".join(block))
    assert SETTING in joined, "the message names testing_context.db_connection_test by its full path"
    assert "skills_config.json" in joined, "the message tells the user to set it in skills_config.json"
    assert SENTENCE in block, f"the fenced block must hold the line {SENTENCE!r} (outside the block it is not relayed)"
    assert block == [*PRE_CHANGE_LINES, SENTENCE], \
        "the block must be the pre-change lines unchanged, then the new sentence as the last line"
    assert SQL_SUITE_LINE in S.flat(S.prose(text)), "the 'Do NOT attempt to run the SQL suite' line stays in the template"
