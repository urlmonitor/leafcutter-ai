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
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127c_1_scope_fixture import (  # noqa: E402
    CONFIG_PATH,
    content,
    copy_commit_guardian,
    init_repo,
    refusal_advice_for_extension,
    run_direct,
    stage_all,
)

# ---------------------------------------------------------------------------
# 4. Every distinct form of dividing advice is producible by some measured kind
# ---------------------------------------------------------------------------


class TestEveryFormOfDividingAdviceIsProducibleBySomeMeasuredKind(unittest.TestCase):
    def _probe_produced_a_real_refusal(self, ext: str) -> bool:
        """True if forcing *ext* alone into scope and refusing an over-limit
        file of that kind produced a REAL refusal from the probing
        machinery -- the unconditional "FILE TOO LARGE" marker
        `_print_too_large_file` prints on every refusal, independent of
        whether any dividing-advice sentence follows it.

        This is the surviving teeth of the old "fixture sanity: probing must
        produce at least one advice line" guard (see the comment in the test
        below for why that guard's ORIGINAL form is now wrong). A probe whose
        subprocess crashes, whose throwaway override config is malformed, or
        whose target file is not actually refused at all, fails this check
        and therefore still fails the test -- only the presence of an
        advice *line* was ever the wrong thing to require.
        """
        root = Path(tempfile.mkdtemp(prefix="ge127c1_teeth_probe_"))
        cg = copy_commit_guardian(file_size_overrides={"checked_extensions": [ext], "line_limits": {ext: 1}})
        try:
            init_repo(root)
            (root / f"probe{ext}").write_text(content(5), encoding="utf-8")
            stage_all(root)
            result = run_direct(cg, root)
            return "FILE TOO LARGE" in (result.stdout + result.stderr)
        finally:
            shutil.rmtree(root, ignore_errors=True)
            shutil.rmtree(cg, ignore_errors=True)

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

        # GE-127e-3 CROSS-AC ADJUDICATION (2026-09-23, settled by the ticket
        # supervisor, implemented here by test-writer -- see ticket
        # 04_TICKET-20260914-GE-127e-3.md's "THE CONFLICT" / "THE
        # ADJUDICATION" comments for the full reasoning this summarizes):
        #
        # GE-127e-3 required deleting the `/code-refactoring-specialist`
        # dividing-advice sentence from `_print_too_large_file` OUTRIGHT, with
        # nothing substituted (its Implementation Notes item 6: "Deletion is
        # the compliant move and must not be traded for substitution"). That
        # correctly empties `capable_forms` for every probed extension --
        # there is no longer any "Use the ..." line for ANY kind to produce.
        #
        # The `assertTrue(capable_forms, ...)` that used to sit here treated
        # that empty result as a FIXTURE failure. It is not one: this AC's own
        # criterion clause ("for every distinct form of dividing advice the
        # standard is capable of producing there is a kind of file it
        # measures that produces it") is guarded by "When the refusal offers
        # advice on how to divide the file" -- with no such advice offered,
        # the clause does not apply -- and its requirement is universally
        # quantified over the forms the standard CAN produce, which is
        # vacuously true over an empty set. The `unreachable = capable_forms -
        # reachable_forms` assertion below (kept EXACTLY as it was -- that is
        # the real AC and it must keep its teeth) is vacuously satisfied the
        # same way. The test's own failure message even names this branch by
        # name: "Either bring a kind capable of producing this advice into
        # scope, or remove the advice." GE-127e-3 took the second branch, and
        # this AC's closing phrase -- "the standard carries no advice for a
        # kind it can never refuse" -- is trivially satisfied by carrying no
        # advice at all.
        #
        # What must NOT be lost by relaxing this: the ORIGINAL guard's real
        # purpose, which was to catch a probe that silently finds nothing
        # because the probing machinery itself is broken (a crashed
        # subprocess, a malformed throwaway config, a file that was never
        # actually refused). `_probe_produced_a_real_refusal` below asserts
        # exactly that -- that every probed extension produced a REAL refusal
        # (the unconditional "FILE TOO LARGE" marker) -- without requiring
        # that refusal to carry any dividing-advice sentence. A genuinely
        # broken probe still fails this test.
        for ext in probe_extensions:
            self.assertTrue(
                self._probe_produced_a_real_refusal(ext),
                f"probe sanity: refusing an over-limit {ext!r} file must "
                "produce a real refusal (the unconditional 'FILE TOO LARGE' "
                "marker) even though it may carry no dividing-advice line -- "
                "if this fails, the probing machinery itself is broken, not "
                "merely empty of advice",
            )

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
