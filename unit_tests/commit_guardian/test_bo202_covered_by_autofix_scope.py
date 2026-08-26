"""
MODULE: unit_tests/commit_guardian/test_bo202_covered_by_autofix_scope.py
GOAL: RED test stubs pinning KI-ACD-003 / KI-ACD-019 -- the narrowed
    covered_by auto-fix mechanism specified in
    templates/agents/ac-fulfillment-gate.md, which BO-202's 2026-08-25
    REOPENED notes record as false against the criterion's literal text.

BUSINESS CONTEXT: BO-202's criterion says the gate "populates covered_by
    with test file paths from the diff that contain a '# covers: <AC-ID>'
    tag matching this AC's ID". It carries NO L2-only qualifier and NO
    directory qualifier -- it says FROM THE DIFF. The template as written
    narrows this on two independent axes:

      (a) Section "### 3c. Auto-fix `covered_by` (L2 ACs only)" -- gated by
          AC level, with "### 2f. Verify `covered_by` (L2 ACs only)" stating
          "L3 ACs: skip this check (empty `covered_by` is permitted)".
      (b) The mechanism itself, `grep -r "# covers: <AC-ID>" tests/`, only
          ever searches the fixed directory `tests/` -- a genuine covering
          tag living anywhere else (e.g. under `unit_tests/`, where much of
          this repo's own suite lives, including this very file) is
          invisible to it.

    Both were independently confirmed against ACD-1900b-5-i, an L3 AC whose
    six `# covers:` tags all lived in unit_tests/ac_driven_dev/: the gate
    returned ok, left covered_by: [], and done_proof.verify_done_eligible
    independently returned eligible: True with all five test node-ids
    listed -- the proof existed and was discoverable, the gate simply never
    looked.

WHY THIS IS AN AGENT-TEMPLATE TARGET, NOT A PYTHON MODULE:
    scripts/ac_store/ac_coverage_resolver.py -- the module named as the
    preferred, stronger test target when the real resolution logic lives in
    Python -- was read first. It does NOT implement this behaviour: its sole
    covered_by check is `if not record.get("covered_by"): failed_fields
    .append("covered_by")` (a non-empty check), with no logic that reads a
    diff, greps a directory, or applies a per-level exemption. The auto-fix
    mechanism BO-202 is about exists ONLY as natural-language instructions
    inside the agent template that an LLM agent reads and acts on at
    runtime -- there is no executable Python entry point to import and call.

    Given that, the tests below take the strongest verification available
    for a prose-agent-template artifact, per the project's "Verify
    Behaviorally, Not by Grep" convention -- never a bare string search for
    the mechanism's presence:

      - Defect (b) is executed for real: the exact shell command in section
        3c is extracted from the live template file (never re-typed) and run
        via subprocess against a constructed directory tree where the
        covering tag genuinely exists under unit_tests/ -- demonstrating the
        documented mechanism's failure to find it, behaviourally, not
        textually.
      - Defect (a) has no executable counterpart to run (the L2-only
        decision is made by an LLM reading prose, not by any function this
        repo can invoke), so the strongest available proxy mechanically
        evaluates the SAME literal condition the template states --
        extracted from the real file at test time, not duplicated by hand --
        against a concrete AC level. This is a spec-consistency test: it
        will go green exactly when, and only when, the template's own
        wording stops narrowing to L2.

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) result -- this
repo's pytest_ac_enforcement plugin otherwise xfails not-yet-done ACs:

    AC_ENFORCE_STRICT=1 python3 -m pytest \
        unit_tests/commit_guardian/test_bo202_covered_by_autofix_scope.py -v
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "agents" / "ac-fulfillment-gate.md"


def _read_template() -> str:
    """Read the live ac-fulfillment-gate.md template text.

    Fails loudly (via a plain read error) rather than masking a missing
    template behind an empty string -- a missing template is itself a
    defect this test suite must never hide.
    """
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _extract_section(template_text: str, header_prefix: str) -> str:
    """Return the body of the first markdown section whose header starts
    with *header_prefix*, verbatim from *template_text* -- never a
    hand-typed guess at the section's current wording.

    Args:
        template_text: The full template file content.
        header_prefix: The literal start of a "### ..." header line
            identifying the section (e.g. "### 3c. Auto-fix `covered_by`").

    Returns:
        The section's text, from its header line up to (but excluding) the
        next "### " header or a "---" divider line.

    Raises:
        AssertionError: When no matching header line is found -- this is a
            fixture/setup failure (the template's structure changed
            underneath this test), not the behaviour under test, so it is
            reported distinctly from the assertions below.
    """
    lines = template_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(header_prefix):
            start = index
            break
    if start is None:
        raise AssertionError(
            f"Could not locate a section starting with {header_prefix!r} in "
            f"{_TEMPLATE_PATH} -- the template's structure may have changed."
        )
    body = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("### ") or line.strip() == "---":
            break
        body.append(line)
    return "\n".join(body)


def _extract_3c_grep_command(template_text: str) -> str:
    """Extract the literal shell command from section 3c's fenced bash
    block, verbatim -- not re-typed -- so the behavioral test below tracks
    the template's ACTUAL instructed mechanism rather than a guess at it.

    Args:
        template_text: The full template file content.

    Returns:
        The command string exactly as it appears inside the ```bash fence.

    Raises:
        AssertionError: When the expected fenced command block cannot be
            found -- a fixture/setup failure, reported distinctly from the
            behavioral assertions below.
    """
    section = _extract_section(template_text, "### 3c. Auto-fix `covered_by`")
    match = re.search(r"```bash(.*?)```", section, re.DOTALL)
    if match is None:
        raise AssertionError(
            "Could not locate the fenced bash command in section 3c of "
            f"{_TEMPLATE_PATH} -- the template's structure may have changed."
        )
    # The fence is indented as part of a markdown list item (e.g. two-space
    # indented ```bash / ``` lines), so strip per-line indentation rather
    # than requiring the closing fence flush against a newline.
    command_lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    return "\n".join(command_lines)


def _autofix_covered_by_would_run_per_template(
    template_text: str, *, level: str
) -> bool:
    """Mechanically evaluate, from the LITERAL wording of section 3c, whether
    the covered_by auto-fix step is even reached for an AC of *level*.

    This is the strongest available behavioral proxy for a prose agent
    template: there is no executable Python implementing this decision (it
    lives entirely in natural-language instructions an LLM agent reads and
    acts on), so this evaluates the SAME condition the template states,
    extracted from the real file rather than duplicated by hand. It goes
    green exactly when the template's own header no longer names an L2-only
    scope.

    Args:
        template_text: The full template file content.
        level: The AC's `level` field value (e.g. "L2", "L3").

    Returns:
        True iff the template's section 3c header does not scope the step to
        "L2 ACs only", or *level* is "L2".
    """
    section_3c = _extract_section(template_text, "### 3c. Auto-fix `covered_by`")
    header_line = section_3c.splitlines()[0]
    scoped_to_l2_only = "L2 ACs only" in header_line
    return not (scoped_to_l2_only and level != "L2")


# ---------------------------------------------------------------------------
# Defect (b): the grep mechanism is scoped to a fixed directory, not "the
# diff". Executed for real via subprocess -- not a string search.
# ---------------------------------------------------------------------------


class TestCoveredByAutofixMechanismDirectoryScope(unittest.TestCase):
    """BO-202 / KI-ACD-003: the criterion says covered_by must be populated
    "from the diff", with no directory qualifier. Section 3c's documented
    mechanism instead runs `grep -r "# covers: <AC-ID>" tests/` -- a search
    of the FIXED directory `tests/` only.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac2_grep_mechanism_misses_a_real_covering_test_outside_tests_dir(
        self,
    ) -> None:
        # covers: BO-202
        """Extracts the EXACT command from the live template (never
        re-typed) and executes it, verbatim, against a constructed tree
        where a genuine `# covers: <AC-ID>` tag exists -- but under
        `unit_tests/`, exactly the ACD-1900b-5-i incident the AC's notes
        cite, and exactly where this very test file itself lives. A
        mechanism honouring the criterion ("from the diff", no directory
        qualifier) would find this tag; the documented mechanism cannot,
        because it only ever searches `tests/`.
        """
        template_text = _read_template()
        raw_command = _extract_3c_grep_command(template_text)
        self.assertIn(
            "tests/",
            raw_command,
            "Fixture/setup sanity check: expected the extracted command to "
            "reference the tests/ directory this test is about; the "
            f"template's wording may have changed. Extracted: {raw_command!r}",
        )

        ac_id = "BO-TEST-COVERAGE-1"
        command = raw_command.replace("<AC-ID>", ac_id)

        (self.tmp_root / "tests").mkdir()
        covering_dir = self.tmp_root / "unit_tests" / "build_orchestration"
        covering_dir.mkdir(parents=True)
        covering_test = covering_dir / "test_something.py"
        covering_test.write_text(
            f"def test_something():\n    # covers: {ac_id}\n    assert True\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["bash", "-c", command],
            cwd=self.tmp_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Sanity check confirming the defect is live in THIS run: grep finds
        # nothing under tests/, because there is nothing there to find.
        self.assertEqual(
            result.stdout.strip(),
            "",
            "Fixture sanity check: tests/ is empty in this scenario, so the "
            f"documented command must find nothing there. Got: {result.stdout!r}",
        )

        # The criterion demands the tag be found "from the diff", with no
        # directory qualifier -- so a covering test under unit_tests/ must
        # be discoverable. It is not: this is the failing assertion.
        self.assertIn(
            f"# covers: {ac_id}",
            result.stdout,
            "BO-202 requires covered_by to be auto-fixed 'from the diff' "
            "with no directory qualifier, so a covering test under "
            "unit_tests/ must be discoverable -- but the documented "
            "mechanism (grep -r \"# covers: <AC-ID>\" tests/) only ever "
            "searches tests/, so it finds nothing here even though the tag "
            "genuinely exists (KI-ACD-003 / ACD-1900b-5-i). Command run: "
            f"{command!r}; stdout: {result.stdout!r}",
        )


# ---------------------------------------------------------------------------
# Defect (a): the step is scoped to L2 ACs only, though the criterion
# carries no such qualifier.
# ---------------------------------------------------------------------------


class TestCoveredByAutofixLevelScope(unittest.TestCase):
    """BO-202 / KI-ACD-019: the criterion carries no L2-only qualifier, but
    section 3c is headed "(L2 ACs only)" and section 2f states "L3 ACs:
    skip this check". An L3 AC with a genuine covering test is therefore
    never auto-fixed at all.
    """

    def test_ac2_l3_ac_with_a_covering_test_is_not_scoped_out_of_autofix(
        self,
    ) -> None:
        # covers: BO-202
        """Mechanically evaluates section 3c's literal, live-extracted
        header condition against level="L3". BO-202's criterion draws no
        distinction by level -- covered_by must be populated "from the
        diff" for any AC whose covering tag is found there -- but the
        template's own stated rule currently excludes L3 outright, as
        observed on ACD-1900b-5-i.
        """
        template_text = _read_template()

        would_autofix = _autofix_covered_by_would_run_per_template(
            template_text, level="L3"
        )

        self.assertTrue(
            would_autofix,
            "BO-202's criterion carries no L2-only qualifier -- it says the "
            "gate populates covered_by 'with test file paths from the diff "
            "that contain a \"# covers: <AC-ID>\" tag matching this AC's "
            "ID', for any AC. But templates/agents/ac-fulfillment-gate.md "
            "section 3c is headed '(L2 ACs only)', so an L3 AC's covered_by "
            "is never auto-fixed even when a genuine covering test exists "
            "(KI-ACD-019 / ACD-1900b-5-i, where covered_by was left [] "
            "despite done_proof.verify_done_eligible independently "
            "returning eligible: True with all five test node-ids listed).",
        )

    def test_ac2_l2_ac_with_a_covering_test_is_still_autofixed_control(
        self,
    ) -> None:
        # covers: BO-202
        """Positive control: an L2 AC is NOT excluded by the same rule --
        this confirms the interpreter above is discriminating on level
        correctly, rather than always returning False. This assertion is
        expected to PASS today; it is not part of the red baseline.
        """
        template_text = _read_template()

        would_autofix = _autofix_covered_by_would_run_per_template(
            template_text, level="L2"
        )

        self.assertTrue(
            would_autofix,
            "Sanity check: an L2 AC must not be excluded by section 3c's "
            "own stated scope -- if this fails, the interpreter above (not "
            "the template) is broken.",
        )


if __name__ == "__main__":
    unittest.main()
