"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_ii.py
COVERS: GE-127e-3-ii -- "Every tool named by an instruction a refusal sends
    the author to actually exists"

GOAL: RED test-first stubs proving that every filesystem-path tool
    invocation inside templates/workflows/code-refactoring-specialist.md --
    the command check_file_size.py's file-size refusal names for `.py`
    files -- resolves against the real repository, and that a path which
    does NOT resolve is reported by name.

THE DEFECT THIS FILE IS RED AGAINST. Step 1 of that command
    (templates/workflows/code-refactoring-specialist.md:12) instructs
    running `python .agent/skills/code-analysis/scripts/analyze_structure.py
    <file>`. No file named analyze_structure.py exists anywhere in this
    workspace and no `.agent/skills/code-analysis/` directory exists --
    verified by hand at authoring time and by this module's own extraction
    below. Every earlier hop in the chain (the guard names a command; the
    command exists and is deployed) resolves; only this last hop is dead.

EXTRACTION IS GENERIC, NOT A STRING MATCH ON THE KNOWN-BAD LINE. Both
    descriptors below share `_unresolved_path_invocations`, which discovers
    filesystem-path tool invocations from the command file's own text at run
    time: a backtick code span containing a token with at least one "/" and
    a dot-extension. It never hardcodes `analyze_structure.py`. An agent
    reference such as `@documentation-expert` has no "/" and is never
    extracted -- it is out of scope per GE-127e-3-ii's own it_requirements.
    Descriptor 2 exists to prove this extraction is real (not merely
    satisfiable by finding zero paths) by running it against a copy of the
    file with one added, deliberately-broken instruction.

DECISION HISTORY
- 2026-09-09 [GE-127e-3-ii/test-writer]: Initial authoring of both RED test
    stubs per GE-127e-3-ii's test_spec. Verified via
    `AC_ENFORCE_STRICT=1 python -m pytest unit_tests/commit_guardian/test_ge_127e_3_ii.py -v`
    -- see the test-writer report for the exact captured outcomes.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMAND_FILE = _REPO_ROOT / "templates" / "workflows" / "code-refactoring-specialist.md"

# A backtick code span, e.g. `python some/path/tool.py <file>`.
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")

# A filesystem-path-looking token WITHIN a code span: optionally one or two
# leading dots (relative / hidden-dir markers, e.g. ".agent/..."), at least
# one "/"-separated segment, and a dot-extension at the end. Never matches a
# bare tool name (`run_command`) or an agent reference (`@documentation-expert`)
# because neither contains a "/".
_PATH_TOKEN_RE = re.compile(r"(?<![\w@])(\.{0,2}[\w][\w\-]*(?:/[\w\-.]+)+\.[A-Za-z0-9]+)")


def _extract_path_invocations(markdown_text: str) -> list[dict[str, str]]:
    """Discover every filesystem-path tool invocation in *markdown_text*.

    Args:
        markdown_text: The full text of a command/workflow markdown file.

    Returns:
        One entry per matched path, each ``{"instruction": <source line>,
        "path": <extracted path>}``. Discovery happens purely from the
        text's own content -- nothing here names a specific known-bad path.
    """
    findings: list[dict[str, str]] = []
    for line in markdown_text.splitlines():
        for span in _CODE_SPAN_RE.findall(line):
            for match in _PATH_TOKEN_RE.finditer(span):
                findings.append({"instruction": line.strip(), "path": match.group(1)})
    return findings


def _unresolved_path_invocations(markdown_path: Path, repo_root: Path) -> list[dict[str, str]]:
    """Return every path invocation in *markdown_path* that does not resolve.

    Args:
        markdown_path: The command/workflow markdown file to scan.
        repo_root: The repository root the author would experience -- every
            extracted path is resolved relative to this.

    Returns:
        One entry per unresolved invocation: ``{"command": <markdown_path>,
        "instruction": <source line>, "path": <unresolved path>}``. Empty
        when every discovered path resolves (including vacuously, when zero
        paths are discovered at all).
    """
    text = markdown_path.read_text(encoding="utf-8")
    unresolved: list[dict[str, str]] = []
    for finding in _extract_path_invocations(text):
        candidate = repo_root / finding["path"]
        if not candidate.exists():
            unresolved.append(
                {
                    "command": str(markdown_path),
                    "instruction": finding["instruction"],
                    "path": finding["path"],
                }
            )
    return unresolved


# ---------------------------------------------------------------------------
# 1. Every path invoked by the real, shipped command must resolve
# ---------------------------------------------------------------------------


class TestEveryPathInvokedToolInTheNamedCommandResolves(unittest.TestCase):
    def test_ge_127e_3_ii_every_path_invoked_tool_in_the_named_command_resolves(self):
        # covers: GE-127e-3-ii
        # angle: criterion
        """Every filesystem path an instruction in
        templates/workflows/code-refactoring-specialist.md invokes must
        resolve against the repository root. Paths are DISCOVERED from the
        file's own text at run time via `_unresolved_path_invocations` --
        never hardcoded here.

        RED TODAY: step 1 invokes
        `.agent/skills/code-analysis/scripts/analyze_structure.py`, which
        exists nowhere in this workspace, so it is reported as unresolved.

        Vacuous-after-fix is EXPECTED, not a defect in this test: the
        prescribed fix is deletion (see GE-127e-3-ii's it_requirements), so
        once step 1's dead invocation is removed this descriptor becomes
        trivially satisfied by zero discovered paths -- exactly what the
        Gherkin's conditional ("that command's own instructions invoke one
        or more tools by path") allows. Descriptor 2 below is what keeps
        this descriptor honest afterwards.
        """
        unresolved = _unresolved_path_invocations(_COMMAND_FILE, _REPO_ROOT)

        self.assertEqual(
            [],
            unresolved,
            msg=(
                f"Every filesystem path invoked by an instruction in {_COMMAND_FILE} "
                f"must resolve against {_REPO_ROOT}. Unresolved: {unresolved!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 2. Named mutation -- an added dead invocation is reported by name
# ---------------------------------------------------------------------------


class TestAnInstructionNamingAMissingToolIsReported(unittest.TestCase):
    def test_ge_127e_3_ii_an_instruction_naming_a_missing_tool_is_reported_with_command_instruction_and_path(
        self,
    ):
        # covers: GE-127e-3-ii
        # angle: failure
        """NAMED MUTATION. A COPY of the real command file, with one added
        instruction invoking a path that does not exist, is written to a
        temp directory and resolved with the SAME `_unresolved_path_invocations`
        helper descriptor 1 uses. The result must report the finding naming
        the mutated command file, the injected instruction line, and the
        unresolved path.

        Without this arm, descriptor 1 is satisfiable by a helper that
        extracts zero paths and reports nothing -- exactly the shape that
        let the real dead pointer ship (KI-TQ-010 / KI-CG-034: a scanner
        that compares nothing and exits 0). This test does not depend on
        the real defect at all -- it constructs its own broken fixture, so
        it is expected to PASS independently of whether the real file has
        been fixed yet.
        """
        tmp_dir = Path(tempfile.mkdtemp(prefix="ge127e3ii_mutation_"))
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)

        mutated = tmp_dir / "code-refactoring-specialist.md"
        original_text = _COMMAND_FILE.read_text(encoding="utf-8")
        injected_path = "scripts/does_not_exist_ge_127e_3_ii.py"
        injected_line = (
            f"6.  **Ghost step:** Run `python {injected_path} <file>` "
            "to do something that has never existed.\n"
        )
        mutated.write_text(original_text + "\n" + injected_line, encoding="utf-8")

        unresolved = _unresolved_path_invocations(mutated, _REPO_ROOT)

        matching = [finding for finding in unresolved if finding["path"] == injected_path]
        self.assertEqual(
            1,
            len(matching),
            msg=f"Expected exactly one unresolved finding for the injected path. Got: {unresolved!r}",
        )
        finding = matching[0]
        self.assertEqual(
            str(mutated),
            finding["command"],
            msg=f"The report must name the (mutated) command file. Got: {finding!r}",
        )
        self.assertIn(
            injected_path,
            finding["instruction"],
            msg=f"The report must name the offending instruction. Got: {finding!r}",
        )
        self.assertEqual(
            injected_path,
            finding["path"],
            msg=f"The report must name the unresolved path itself. Got: {finding!r}",
        )


if __name__ == "__main__":
    unittest.main()
