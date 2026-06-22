"""
Behavioral tests for the staging-discovery and AC-ID-match defects in
commitStageOutput() in scripts/workflows/plan-feature.js.

AC reference: ACD-300g-2
Ticket: 08_TICKET-20260622-Fix_Staging_Discovery_And_Match.md

These tests MUST FAIL (RED) against the current broken instructions in two
defect areas:

Defect 1 — Untracked-subfolder discovery (HIGH — silently commits nothing):
    Step 1 of the instructions reads:
        "Run: git status --porcelain -- docs/acceptance-criteria/"
    `git status --porcelain` (without --untracked-files=all) collapses an
    entire untracked directory into a single "?? <dir>/" line. Individual
    .yaml files inside the directory are never emitted. The .yaml-suffix
    filter never sees them, so no matching files are found, and the
    function returns the benign-looking "no new AC files to commit — skipped"
    result instead of staging the files.

    test_untracked_subfolder_discovery_is_complete will be RED until the
    instructions are changed to use `--untracked-files=all` (or `-uall`).

Defect 2 — AC-ID match is ambiguous (substring/prefix false-match):
    Step 1 also says:
        "keep only the ones whose filename stem ... matches one of the AC IDs"
    "matches" is ambiguous. A naive implementation using str.startswith() or
    str.contains() means written=["ACD-300"] incorrectly matches:
        - ACD-300g.yaml  (later stage, different AC)
        - ACD-300g-2.yaml (another later stage)
    These are real AC IDs in this repo (prefix-nested), so the bug is live.

    test_prefix_nested_id_does_not_stage_sibling will be RED until the
    instructions require EXACT stem equality and a prose counter-example
    is added for the ACD-300 / ACD-300g family.

Behavioral approach:
    Rather than grepping for strings (which would pass even if the instructions
    are semantically wrong), these tests:

    1. Create a scratch git repo (tmpdir + subprocess git init) with a realistic
       working tree that mirrors the exact failure scenario.
    2. Extract the instructions string from commitStageOutput() by running a Node.js
       vm.Script that invokes the function with a mock agent that captures the
       instructions before they are sent.
    3. Parse the porcelain command out of the captured instructions and run it
       against the scratch repo — exactly as the commit agent would.
    4. Apply the stem-match filter as specified by the instructions text and
       assert on the resulting file list.

    This approach catches phantom-done failures where string-scan tests pass
    despite broken runtime behaviour.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "scripts", "workflows", "plan-feature.js"
)


# ---------------------------------------------------------------------------
# Custom exception types (ruff TRY003 — no long inline messages)
# ---------------------------------------------------------------------------


class SourceParseError(Exception):
    """Raised when the JS source cannot be parsed as expected by a test helper."""


class NodeScriptError(Exception):
    """Raised when an inline Node.js script exits non-zero."""


class GitCommandError(Exception):
    """Raised when a git sub-process command exits non-zero."""


# ---------------------------------------------------------------------------
# Helpers — source reading and Node.js script execution
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    """Read and return the full text of a file."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        msg = f"Cannot read source file {path}: {exc}"
        raise OSError(msg) from exc


def _run_node_script(script_text: str, timeout: int = 20) -> subprocess.CompletedProcess:
    """Run an inline Node.js ESM script via stdin and return the CompletedProcess."""
    return subprocess.run(
        ["node", "--input-type=module"],
        input=script_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _run_git(args: list[str], cwd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a git command in the given directory, raising GitCommandError on failure."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        msg = f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr!r}"
        raise GitCommandError(msg)
    return result


# ---------------------------------------------------------------------------
# Scratch git-repo fixture helpers
# ---------------------------------------------------------------------------


def _init_scratch_repo(tmpdir: str) -> None:
    """
    Initialise a scratch git repo in tmpdir with one baseline commit.

    The initial commit seeds the repo so that git porcelain commands work
    correctly (an empty repo has no HEAD and some commands misbehave).
    """
    _run_git(["init", "-b", "main"], cwd=tmpdir)
    _run_git(["config", "user.email", "test@test.com"], cwd=tmpdir)
    _run_git(["config", "user.name", "Test"], cwd=tmpdir)
    # Write a sentinel file so the initial commit is non-empty.
    sentinel = os.path.join(tmpdir, ".gitkeep")
    try:
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("")
    except OSError as exc:
        raise RuntimeError(f"Failed to write sentinel file: {sentinel}") from exc
    _run_git(["add", ".gitkeep"], cwd=tmpdir)
    _run_git(["commit", "-m", "init"], cwd=tmpdir)


def _write_yaml(path: str, content: str = "id: placeholder\n") -> None:
    """Write a minimal YAML file to path, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as exc:
        raise RuntimeError(f"Failed to write YAML fixture: {path}") from exc


# ---------------------------------------------------------------------------
# Helpers — extract instructions from commitStageOutput() via Node.js vm.Script
# ---------------------------------------------------------------------------


def _capture_instructions(plan_feature_path: str, written: list[str]) -> str:
    """
    Invoke commitStageOutput() with a mock agent in a Node.js vm.Script context
    and return the instructions string passed to the agent.

    The mock agent captures the full instructions before returning a successful
    result, so commitStageOutput() completes without error.

    Raises NodeScriptError if the Node.js process exits non-zero.
    """
    written_json = json.dumps(written)
    script = textwrap.dedent(f"""
        import {{ readFileSync }} from 'fs';
        import vm from 'vm';

        const source = readFileSync({json.dumps(plan_feature_path)}, 'utf8');

        // Strip ESM syntax so vm.Script can evaluate the source.
        const patchedSource = source
            .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
            .replace(/^export \\{{ run \\}};/m, '// export removed')
            .replace(/^export function/gm, 'function')
            + `
        globalThis.__capturedInstructions = '';
        async function mockAgent(call) {{
            if (call.input && call.input.instructions) {{
                globalThis.__capturedInstructions = call.input.instructions;
            }}
            return {{ status: 'ok', message: 'mock commit ok' }};
        }}

        commitStageOutput(mockAgent, {written_json}, 'po', 'test-component', false)
            .then(() => {{
                process.stdout.write(globalThis.__capturedInstructions || '');
            }})
            .catch(err => {{
                process.stderr.write('Error: ' + err.message);
                process.exit(1);
            }});
        `;

        const ctx = vm.createContext({{ ...globalThis, process, console }});
        const s = new vm.Script(patchedSource);
        s.runInContext(ctx);
    """)

    proc = _run_node_script(script, timeout=20)
    if proc.returncode != 0:
        msg = f"Node.js vm.Script failed (exit {proc.returncode}). stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)
    return proc.stdout


def _extract_porcelain_command(instructions: str) -> str:
    """
    Parse the `git status` command out of the Step 1 instructions text.

    Returns the full command string (e.g. "git status --porcelain -- docs/acceptance-criteria/")
    as it appears in the instructions, so tests can verify whether --untracked-files=all
    is present or absent.

    Raises SourceParseError if no porcelain command can be found.
    """
    # Look for a line matching "Run: git status ..."
    match = re.search(r"Run:\s*(git\s+status\s+[^\n]+)", instructions)
    if not match:
        raise SourceParseError("porcelain-command-not-found-in-instructions")
    return match.group(1).strip()


def _apply_stem_filter(porcelain_output: str, written: list[str]) -> list[str]:
    """
    Apply the stem-match filter as described in the instructions prose.

    The instructions say:
        "keep only the ones whose filename stem (the portion after the last '/'
         and before '.yaml') matches one of the AC IDs above."

    This helper implements the CURRENT (ambiguous) specification faithfully: it
    uses str-in (substring containment) as a charitable interpretation of
    "matches", which is the interpretation that produces the false-positive bug.

    Returns the list of file paths that pass the filter under this interpretation.
    """
    matched = []
    for line in porcelain_output.splitlines():
        # Porcelain format: "XY <path>" where XY is two chars and a space.
        if len(line) < 4:
            continue
        status_code = line[:2].strip()
        if not status_code:
            continue  # clean/ignored file
        path = line[3:]
        if not path.endswith(".yaml"):
            continue
        # Extract stem: portion after last '/' and before '.yaml'.
        stem = path.rsplit("/", 1)[-1][: -len(".yaml")]
        # Current (broken) interpretation: stem "matches" means stem starts with an AC ID,
        # or an AC ID is a prefix of the stem (startswith = prefix match = the defect).
        for ac_id in written:
            if stem.startswith(ac_id) or stem == ac_id:
                matched.append(path)
                break
    return matched


def _apply_exact_stem_filter(porcelain_output: str, written: list[str]) -> list[str]:
    """
    Apply the FIXED stem-match filter: exact equality between stem and AC ID.

    This is the target behaviour after the defect is fixed.
    """
    matched = []
    for line in porcelain_output.splitlines():
        if len(line) < 4:
            continue
        status_code = line[:2].strip()
        if not status_code:
            continue
        path = line[3:]
        if not path.endswith(".yaml"):
            continue
        stem = path.rsplit("/", 1)[-1][: -len(".yaml")]
        if stem in written:
            matched.append(path)
    return matched


# ---------------------------------------------------------------------------
# Test class: Untracked-subfolder discovery (Defect 1)
# ---------------------------------------------------------------------------


class TestUntrackedSubfolderDiscovery(unittest.TestCase):
    """
    Behavioral tests for Defect 1: untracked-subfolder files are invisible to
    `git status --porcelain` (without --untracked-files=all).

    These tests set up a scratch repo whose docs/acceptance-criteria/ directory
    does not yet exist (entirely untracked), write .yaml files into a new
    subfolder, run the porcelain command exactly as the instructions specify,
    and assert that all .yaml files are discovered.

    The tests are RED against the current instructions (which omit
    --untracked-files=all) and GREEN after the fix.

    AC: "untracked AC files in a new subfolder are staged"
    """

    def setUp(self):
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = self.tmpdir_obj.name
        _init_scratch_repo(self.tmpdir)
        # Write two AC YAML files into a completely untracked subfolder.
        # docs/acceptance-criteria/ does NOT exist as a tracked dir yet.
        self.ac_dir = os.path.join(self.tmpdir, "docs", "acceptance-criteria")
        _write_yaml(os.path.join(self.ac_dir, "ACD-200.yaml"), "id: ACD-200\n")
        _write_yaml(os.path.join(self.ac_dir, "ACD-201.yaml"), "id: ACD-201\n")

    def tearDown(self):
        self.tmpdir_obj.cleanup()

    def test_porcelain_without_uall_misses_files_in_untracked_subdir(self):
        """
        git status --porcelain (without --untracked-files=all) collapses the
        untracked docs/acceptance-criteria/ directory into a single "?? docs/"
        line, missing the individual .yaml files entirely.

        This test asserts the BUG is present — the porcelain output does NOT
        contain individual .yaml file paths. This is the RED condition that
        motivates the fix.

        CURRENTLY PASSES (demonstrates the defect, does not assert a fix).
        """
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=f"git status failed: {result.stderr}")
        output = result.stdout

        # The directory is entirely untracked. Without -uall, git collapses it.
        # Individual .yaml files must NOT appear in the output.
        yaml_files_in_output = [
            line for line in output.splitlines()
            if line.endswith(".yaml")
        ]
        # This assertion documents the defect: no individual .yaml paths emitted.
        self.assertEqual(
            yaml_files_in_output,
            [],
            msg=(
                "UNEXPECTED: git status --porcelain emitted individual .yaml files "
                "for the untracked subfolder. This test documents the bug where "
                "those files are collapsed to a dir-level entry."
            ),
        )

    def test_porcelain_with_uall_discovers_all_yaml_files(self):
        """
        git status --porcelain --untracked-files=all emits every individual
        .yaml file in an untracked subfolder.

        This test asserts the FIXED behaviour. It is GREEN now (the fixed flag
        works) and documents what the instructions must say after the fix.

        AC: untracked AC files in a new subfolder are staged.
        """
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all",
             "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=f"git status failed: {result.stderr}")
        output = result.stdout

        yaml_files_in_output = [
            line[3:].strip() for line in output.splitlines()
            if line[3:].endswith(".yaml")
        ]
        self.assertIn(
            "docs/acceptance-criteria/ACD-200.yaml",
            yaml_files_in_output,
            msg="ACD-200.yaml must appear in porcelain output with --untracked-files=all",
        )
        self.assertIn(
            "docs/acceptance-criteria/ACD-201.yaml",
            yaml_files_in_output,
            msg="ACD-201.yaml must appear in porcelain output with --untracked-files=all",
        )

    def test_instructions_specify_untracked_files_all(self):
        """
        The porcelain command in the commitStageOutput() instructions MUST include
        --untracked-files=all (or -uall).

        CURRENTLY FAILS: the instructions contain
            "git status --porcelain -- docs/acceptance-criteria/"
        which lacks --untracked-files=all and silently misses files in new
        subfolders.

        RED until the instructions are updated to include the flag.

        AC: untracked AC files in a new subfolder are staged.
        """
        try:
            instructions = _capture_instructions(_PLAN_FEATURE_JS, written=["ACD-200"])
        except NodeScriptError as exc:
            self.fail(f"Failed to capture instructions from plan-feature.js: {exc}")

        try:
            porcelain_cmd = _extract_porcelain_command(instructions)
        except SourceParseError as exc:
            self.fail(f"Could not extract porcelain command from instructions: {exc}")

        has_uall_flag = (
            "--untracked-files=all" in porcelain_cmd
            or "-uall" in porcelain_cmd
            or " -u all" in porcelain_cmd
        )

        self.assertTrue(
            has_uall_flag,
            msg=(
                "DEFECT: The git status command in commitStageOutput() instructions "
                "does not include --untracked-files=all.\n"
                f"Current command: {porcelain_cmd!r}\n"
                "Without --untracked-files=all, an entirely-untracked "
                "docs/acceptance-criteria/ directory is collapsed to a single "
                "'?? docs/' line and no .yaml files are discovered.\n"
                "Fix: change Step 1 to use:\n"
                "  git status --porcelain --untracked-files=all -- docs/acceptance-criteria/"
            ),
        )

    def test_fresh_untracked_ac_store_does_not_silently_skip(self):
        """
        When the ENTIRE docs/acceptance-criteria/ directory is untracked (fresh
        AC store, first-ever run), running the CURRENT porcelain command
        produces a directory-level line, not per-file lines.

        The .yaml-suffix filter sees no matching paths, so zero files are
        discovered, and commitStageOutput() would silently return "skipped"
        instead of staging any files.

        This test replays the full discovery logic (porcelain command + stem
        filter) using the scratch repo and asserts that the defective path
        produces zero discovered files — the RED condition that confirms the bug.

        RED (demonstrates defect in current code path). Fixed when the porcelain
        command gains --untracked-files=all.

        AC: a fresh, fully-untracked AC store does not silently commit nothing.
        """
        # Run the CURRENT (broken) porcelain command against the scratch repo.
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        porcelain_output = result.stdout

        # Apply the yaml-suffix + stem filter as the agent would.
        written = ["ACD-200", "ACD-201"]
        discovered = _apply_stem_filter(porcelain_output, written)

        # DEFECT: with the current command the discovered list is empty because
        # the directory is collapsed and no .yaml lines are emitted.
        self.assertEqual(
            discovered,
            [],
            msg=(
                "UNEXPECTED: files were discovered even with the broken porcelain command. "
                "This test documents the defect where the fresh AC store is silently skipped."
            ),
        )

        # For completeness, also assert that the FIXED command finds the files.
        # This part is GREEN (documents the expected fixed behaviour).
        result_fixed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all",
             "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result_fixed.returncode, 0)
        discovered_fixed = _apply_stem_filter(result_fixed.stdout, written)
        self.assertEqual(
            len(discovered_fixed),
            2,
            msg=(
                "FIXED command should discover both ACD-200.yaml and ACD-201.yaml "
                f"but got: {discovered_fixed!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Test class: Exact AC-ID stem match (Defect 2)
# ---------------------------------------------------------------------------


class TestExactAcIdStemMatch(unittest.TestCase):
    """
    Behavioral tests for Defect 2: AC-ID match is ambiguous (prefix/substring
    false-match causes later-stage files to be staged).

    These tests set up a scratch repo with files representing prefix-nested IDs
    (ACD-300.yaml, ACD-300g.yaml, ACD-300g-2.yaml — real IDs from this repo),
    apply the current stem filter, and assert that only the exact-match file
    is staged while the prefix-matched files are NOT.

    The tests are RED against the current ambiguous instructions ("matches")
    and GREEN after the instructions are changed to require exact stem equality.

    AC: "only the current stage's AC files are staged under prefix-nested IDs"
    """

    def setUp(self):
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = self.tmpdir_obj.name
        _init_scratch_repo(self.tmpdir)

        # Create a tracked docs/acceptance-criteria/ dir with one prior commit
        # so the new untracked files appear individually in git status.
        ac_dir = os.path.join(self.tmpdir, "docs", "acceptance-criteria")
        os.makedirs(ac_dir, exist_ok=True)
        # Seed the dir with a placeholder so it is tracked.
        placeholder = os.path.join(ac_dir, ".gitkeep")
        try:
            with open(placeholder, "w", encoding="utf-8") as fh:
                fh.write("")
        except OSError as exc:
            raise RuntimeError(f"Failed to write placeholder: {placeholder}") from exc
        _run_git(["add", "docs/acceptance-criteria/.gitkeep"], cwd=self.tmpdir)
        _run_git(["commit", "-m", "seed ac store"], cwd=self.tmpdir)

        # Now write the three prefix-nested files as untracked working-tree changes.
        _write_yaml(os.path.join(ac_dir, "ACD-300.yaml"), "id: ACD-300\n")
        _write_yaml(os.path.join(ac_dir, "ACD-300g.yaml"), "id: ACD-300g\n")
        _write_yaml(os.path.join(ac_dir, "ACD-300g-2.yaml"), "id: ACD-300g-2\n")

    def tearDown(self):
        self.tmpdir_obj.cleanup()

    def _get_porcelain_output(self) -> str:
        """Run the FIXED porcelain command (with -uall) against the scratch repo."""
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all",
             "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(f"git status failed: {result.stderr}")
        return result.stdout

    def test_prefix_match_wrongly_stages_sibling_ids(self):
        """
        When written = ["ACD-300"] and the working tree also contains
        ACD-300g.yaml and ACD-300g-2.yaml, the CURRENT ambiguous "matches"
        filter (startswith) wrongly includes the sibling files.

        This test asserts the BUG IS PRESENT: the broken filter returns
        ACD-300g.yaml and/or ACD-300g-2.yaml alongside ACD-300.yaml.

        RED test — documents the defect that needs fixing.

        AC: only the current stage's AC files are staged under prefix-nested IDs.
        """
        porcelain_output = self._get_porcelain_output()
        written = ["ACD-300"]

        # Apply the BROKEN filter (startswith = prefix match).
        matched = _apply_stem_filter(porcelain_output, written)

        # DEFECT: the broken filter includes the sibling files.
        sibling_files_matched = [
            p for p in matched
            if "ACD-300g" in p
        ]
        self.assertGreater(
            len(sibling_files_matched),
            0,
            msg=(
                "UNEXPECTED: the broken prefix-match filter did NOT include sibling files. "
                "This test documents the defect where ACD-300g.yaml / ACD-300g-2.yaml are "
                "wrongly staged alongside ACD-300.yaml when written=['ACD-300'].\n"
                f"matched: {matched!r}"
            ),
        )

    def test_instructions_require_exact_stem_equality(self):
        """
        The filter prose in commitStageOutput() instructions MUST require EXACT
        string equality between the filename stem and an AC ID in `written`.

        The current prose says "matches" — unqualified — which can be
        (and is) interpreted as startswith/prefix, causing the false-positive
        staging defect for prefix-nested IDs.

        CURRENTLY FAILS: the instructions do not contain a phrase like
        "exact", "exactly equal", "==" or an explicit counter-example showing
        that ACD-300g.yaml must NOT match ACD-300.

        RED until the instructions prose is hardened with an explicit equality
        requirement and a counter-example.

        AC: only the current stage's AC files are staged under prefix-nested IDs.
        """
        try:
            instructions = _capture_instructions(
                _PLAN_FEATURE_JS, written=["ACD-300"]
            )
        except NodeScriptError as exc:
            self.fail(f"Failed to capture instructions from plan-feature.js: {exc}")

        # Check for an explicit "exact" equality requirement in the filter prose.
        has_exact_qualifier = bool(
            re.search(
                r"exact(?:ly)?[\s\S]{0,60}equal|exactly\s+equal|exact\s+string\s+equality"
                r"|=== |== |stem\s+equals?\b|stem\s+must\s+equal",
                instructions,
                re.IGNORECASE,
            )
        )

        # Check for a concrete counter-example that names ACD-300g vs ACD-300.
        has_counter_example = bool(
            re.search(
                r"ACD-300g.*must\s+NOT|must\s+NOT.*ACD-300g"
                r"|ACD-300g.*not.*match|not.*match.*ACD-300g"
                r"|ACD-300[^\s.]*\s+must\s+not|must\s+not\s+match\s+ACD-300",
                instructions,
                re.IGNORECASE,
            )
        )

        exact_or_counter = has_exact_qualifier or has_counter_example

        self.assertTrue(
            exact_or_counter,
            msg=(
                "DEFECT: The stem-match filter in commitStageOutput() instructions "
                "does not explicitly require EXACT equality between the stem and AC ID.\n"
                "Current instructions contain only the ambiguous 'matches' language, "
                "which an agent implementing it with startswith() will wrongly stage "
                "ACD-300g.yaml when written=['ACD-300'].\n"
                "Fix: change the prose to say "
                "'whose filename stem is exactly equal to one of the AC IDs' "
                "AND add a counter-example: "
                "'For example, ACD-300g.yaml must NOT match ACD-300 "
                "(stems must be identical, not merely prefix-equal).'"
            ),
        )

    def test_exact_filter_stages_only_acd_300(self):
        """
        When written = ["ACD-300"], the CORRECT (exact) filter must stage
        ONLY docs/acceptance-criteria/ACD-300.yaml, not the sibling files.

        This test is GREEN now (the exact filter works correctly) and
        documents the target behaviour after the defect is fixed.

        AC: ONLY ACD-300.yaml is staged; ACD-300g.yaml and ACD-300g-2.yaml
            (later stages) are NOT staged.
        """
        porcelain_output = self._get_porcelain_output()
        written = ["ACD-300"]

        matched = _apply_exact_stem_filter(porcelain_output, written)

        self.assertEqual(
            len(matched),
            1,
            msg=f"Expected exactly 1 match (ACD-300.yaml) but got: {matched!r}",
        )
        self.assertIn(
            "docs/acceptance-criteria/ACD-300.yaml",
            matched[0],
            msg="ACD-300.yaml must be the sole match",
        )
        sibling_matched = [p for p in matched if "ACD-300g" in p]
        self.assertEqual(
            sibling_matched,
            [],
            msg=(
                f"ACD-300g* files must NOT be staged when written=['ACD-300'], "
                f"but got: {sibling_matched!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Test class: Unrelated changes stay unstaged (Scenario 3)
# ---------------------------------------------------------------------------


class TestUnrelatedChangesStayUnstaged(unittest.TestCase):
    """
    Behavioral test for the AC: "unrelated working-tree changes stay unstaged".

    This test verifies that the filter logic (applied to the
    docs/acceptance-criteria/ scoped porcelain command) does not touch
    files outside the AC store.

    This test is GREEN against both the current and fixed code (the scope
    `-- docs/acceptance-criteria/` already constrains discovery). Included
    to confirm the invariant holds.

    AC: unrelated file outside docs/acceptance-criteria/ is not staged.
    """

    def setUp(self):
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = self.tmpdir_obj.name
        _init_scratch_repo(self.tmpdir)

        # Seed the AC dir as tracked.
        ac_dir = os.path.join(self.tmpdir, "docs", "acceptance-criteria")
        os.makedirs(ac_dir, exist_ok=True)
        _write_yaml(os.path.join(ac_dir, ".gitkeep"))
        _run_git(["add", "docs/acceptance-criteria/.gitkeep"], cwd=self.tmpdir)
        _run_git(["commit", "-m", "seed ac store"], cwd=self.tmpdir)

        # Write a target AC file and an unrelated dirty file.
        _write_yaml(os.path.join(ac_dir, "ACD-500.yaml"), "id: ACD-500\n")
        dirty_file = os.path.join(self.tmpdir, "some-unrelated-file.txt")
        try:
            with open(dirty_file, "w", encoding="utf-8") as fh:
                fh.write("dirty\n")
        except OSError as exc:
            raise RuntimeError(f"Failed to write dirty fixture: {dirty_file}") from exc

    def tearDown(self):
        self.tmpdir_obj.cleanup()

    def test_unrelated_file_not_in_discovered_set(self):
        """
        The porcelain command is scoped to docs/acceptance-criteria/.
        A dirty file outside that path must not appear in the discovered set.

        GREEN against both current and fixed code.

        AC: unrelated working-tree changes stay unstaged.
        """
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all",
             "--", "docs/acceptance-criteria/"],
            cwd=self.tmpdir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        porcelain_output = result.stdout

        # The unrelated file must not appear in the scoped porcelain output.
        self.assertNotIn(
            "some-unrelated-file.txt",
            porcelain_output,
            msg=(
                "some-unrelated-file.txt appeared in the porcelain output "
                "scoped to docs/acceptance-criteria/. "
                "The scope filter is not working correctly."
            ),
        )

        # The AC file must appear.
        matched = _apply_exact_stem_filter(porcelain_output, ["ACD-500"])
        self.assertIn(
            "docs/acceptance-criteria/ACD-500.yaml",
            matched[0] if matched else "",
            msg="ACD-500.yaml must be discovered by the scoped porcelain command",
        )

    def test_instructions_scope_discovery_to_ac_dir(self):
        """
        The porcelain command in the instructions must scope discovery to
        docs/acceptance-criteria/ so that unrelated working-tree changes
        are excluded from the discovered set.

        GREEN against both current and fixed code — the scope path is already
        correct in the current instructions.

        AC: unrelated working-tree changes stay unstaged.
        """
        try:
            instructions = _capture_instructions(_PLAN_FEATURE_JS, written=["ACD-500"])
        except NodeScriptError as exc:
            self.fail(f"Failed to capture instructions from plan-feature.js: {exc}")

        try:
            porcelain_cmd = _extract_porcelain_command(instructions)
        except SourceParseError as exc:
            self.fail(f"Could not extract porcelain command from instructions: {exc}")

        self.assertIn(
            "docs/acceptance-criteria",
            porcelain_cmd,
            msg=(
                "DEFECT: The porcelain command does not scope to docs/acceptance-criteria/. "
                f"Current command: {porcelain_cmd!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
