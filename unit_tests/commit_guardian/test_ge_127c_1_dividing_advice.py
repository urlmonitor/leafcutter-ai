"""
MODULE: unit_tests/commit_guardian/test_ge_127c_1_dividing_advice.py
COVERS: GE-127c-1 -- "The outcome states which kinds of file it measured, so
    a kind that was never measured is not read as having passed"

GOAL: RED test-first stub for the dividing-advice arm of GE-127c-1: every
    distinct form of "how to split this file" advice check_file_size.py is
    CAPABLE of producing must ALSO be producible by some kind that is
    actually in the real, current production scope. A form of advice no
    real refusal can ever trigger is dead guidance -- the AC's discoverability
    goal extends to advice text, not just to the measured/not-measured
    statement covered in test_ge_127c_1_scope_declaration.py.

    This descriptor probes empirically (never by grepping source text): it
    forces each candidate extension, one at a time, into a throwaway copy's
    own scope with a tiny limit, refuses a real file of that kind, and reads
    the advice line the refusal actually printed.

    See _ge_127c_1_scope_fixture.py for every shared helper.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127c-1.yaml and its parents GE-127c.yaml / GE-127.yaml.

DECISION HISTORY
- 2026-09-14 [GE-127c-1/test-writer]: Initial authoring of all seven RED
    test stubs per GE-127c-1's test_spec, in test_ge_127c_1.py. Verified RED
    via `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127c_1.py"`.
- 2026-09-14 [GE-127c-1/test-writer]: Split out of test_ge_127c_1.py (579
    counted lines, over the 400-line check-file-size limit this AC itself
    widened) into this standalone file -- this descriptor's probing
    (six candidate extensions, each run against the real production scope)
    is a distinct proof shape from its siblings and does not share a theme
    with either the declaration or config-driven groups. Pure move -- no
    assertion changed. Re-verified RED via `python -m pytest
    unit_tests/commit_guardian/test_ge_127c_1_dividing_advice.py -v`.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127c_1_scope_fixture import CONFIG_PATH, refusal_advice_for_extension  # noqa: E402

# ---------------------------------------------------------------------------
# 4. Every distinct form of dividing advice is producible by some measured kind
# ---------------------------------------------------------------------------


class TestEveryFormOfDividingAdviceIsProducibleBySomeMeasuredKind(unittest.TestCase):
    def test_ge_127c_1_every_form_of_dividing_advice_is_producible_by_some_measured_kind(self):
        # covers: GE-127c-1
        # angle: seam
        """Enumerate the distinct forms of dividing advice check_file_size.py
        is CAPABLE of producing (probed empirically: force each candidate
        extension, one at a time, into a throwaway copy's own scope with a
        tiny limit, refuse a real file of that kind, and read the advice
        line the refusal actually printed -- never a grep of source text).
        Then require every distinct form found this way to ALSO be
        producible by a refusal of a kind that is in the REAL, current
        production scope (read from the actual commit_guardian.json, not a
        fixture).

        RED TODAY (genuine, no mutation needed): the real production scope
        is {.py, .sql}. Probing surfaces three distinct advice forms: one
        specific to .py, one specific to .md, and one generic "else" form
        (produced by .sql and by every other non-.py/.md extension probed).
        The .py-specific and generic forms are reachable from the real
        scope (.py and .sql respectively); the .md-specific form is not,
        because .md is never in checked_extensions -- so its branch can
        never execute from any real refusal. That leaves exactly one
        unreachable form, and the assertion below fails naming it.
        """
        probe_extensions = [".py", ".sql", ".md", ".js", ".ts", ".sh"]
        capable_forms: set[str] = set()
        for ext in probe_extensions:
            capable_forms |= refusal_advice_for_extension(ext)

        self.assertTrue(capable_forms, "fixture sanity: probing must produce at least one advice line")

        real_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        scope_in_force = set(real_config.get("file_size", {}).get("checked_extensions", []))
        self.assertTrue(scope_in_force, "fixture sanity: the real production scope must be non-empty")

        reachable_forms: set[str] = set()
        for ext in scope_in_force:
            reachable_forms |= refusal_advice_for_extension(ext)

        unreachable = capable_forms - reachable_forms
        self.assertFalse(
            unreachable,
            msg=(
                "The standard carries dividing advice with no kind of file "
                f"in the REAL scope in force ({sorted(scope_in_force)}) that "
                f"can ever produce it: {unreachable!r}. Either bring a kind "
                "capable of producing this advice into scope, or remove the "
                "advice."
            ),
        )


if __name__ == "__main__":
    unittest.main()
