"""
Behavioral tests for the partial-run recovery feature in scripts/workflows/plan-feature.js.

AC reference: ACD-300g-2-i
Ticket: 09_TICKET-20260622-Implement_Partial_Run_Recovery_In_Workflow.md

These tests assert the RUNTIME BEHAVIOR of the recovery scan, not just the presence
of function names in source text. They use the vm.Script replay pattern established
by tickets 07/08/10 (see test_commit_stage_output_behavioral.py for the base pattern).

Behavioral contract under test:
  1. scanOrphanedAcDrafts() finds YAML files with origin_agent in
     {product-owner, business-analyst, it-po} AND readiness: draft.
     Files with other origin_agents or non-draft readiness are NOT flagged.
  2. resolveOrphanedDrafts():
     - "yes" branch: calls commitStageOutput (dispatch to commit agent).
     - "no" branch: calls process.exit(1) / returns abort action.
     - "discard" branch:
       * tracked modified draft -> git restore called.
       * untracked new draft -> rm (or equivalent delete) called.
       * BOTH operations asserted, not just one.
  3. run() calls the scan BEFORE the Stage-0 ac-triage dispatch.
  4. Template parity: scripts/ and templates/ are byte-identical for both
     new functions and the updated run() body.

DO NOT use string-scan tests that grep the source for function names.
The phantom-done failure mode (ticket 04) happened because tests only checked
prose in SKILL.md, not the runtime execution path.
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
import unittest

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "scripts", "workflows", "plan-feature.js"
)
_TEMPLATE_PLAN_FEATURE_JS = os.path.join(
    _REPO_ROOT, "templates", "workflows-js", "plan-feature.js"
)


# ---------------------------------------------------------------------------
# Custom exception types (required by ruff TRY003 — no long inline messages)
# ---------------------------------------------------------------------------


class SourceParseError(Exception):
    """Raised when the JS source cannot be parsed as expected by a test helper."""


class NodeScriptError(Exception):
    """Raised when an inline Node.js script exits non-zero."""


# ---------------------------------------------------------------------------
# Helpers (mirroring the pattern in test_commit_stage_output_behavioral.py)
# ---------------------------------------------------------------------------


def _read_source(path: str) -> str:
    """Read and return the full text of a file."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise OSError(f"Cannot read source file {path}: {exc}") from exc


def _run_node_script(script_text: str, timeout: int = 25) -> subprocess.CompletedProcess:
    """Run an inline Node.js ESM script via stdin and return the CompletedProcess."""
    return subprocess.run(
        ["node", "--input-type=module"],
        input=script_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _build_vm_preamble(plan_feature_path: str) -> str:
    """
    Return the ESM script fragment that loads plan-feature.js into a vm.Script
    sandbox with ESM syntax stripped. Callers append their mock + invocation code.
    """
    return textwrap.dedent(f"""
        import {{ readFileSync }} from 'fs';
        import vm from 'vm';

        const source = readFileSync({json.dumps(plan_feature_path)}, 'utf8');

        // Strip ESM syntax so vm.Script can evaluate the source.
        const patchedSource = source
            .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
            .replace(/^export \\{{ run \\}};/m, '// export removed')
            .replace(/^export function/gm, 'function')
    """)


def _run_with_mock_agent(
    plan_feature_path: str,
    mock_agent_js: str,
    user_input: str = "test feature request",
    timeout: int = 25,
    extra_ctx: dict | None = None,
) -> subprocess.CompletedProcess:
    """
    Run plan-feature.js's run() function in a Node.js vm.Script sandbox.

    stdout encodes: JSON(run_result) + NUL + JSON(side_channel)
    where side_channel is { commitCalls: [...], allCalls: [...] }.

    The mock agent code and invocation boilerplate are JSON-encoded and
    concatenated onto the patched plan-feature.js source OUTSIDE of a
    JS backtick template literal. This avoids the backtick template \\n
    interpretation issue: if mock code contained '?? foo\\n' inside a
    backtick template, JS would expand \\n to a literal newline, breaking
    the string literal.

    extra_ctx:
        Optional dict of additional JS context variables to inject. Keys must
        be valid JS identifiers; values are JSON-serialisable Python objects.
        They are passed to vm.createContext() so the mock code can read them.
    """
    path_js = json.dumps(plan_feature_path)
    user_input_js = json.dumps(user_input)

    # Build the invocation wrapper (pure JS, no user-data interpolation).
    invocation_js = textwrap.dedent("""
        globalThis.__capturedCommitCalls = [];
        globalThis.__capturedAllCalls = [];

        MOCK_AGENT_CODE_PLACEHOLDER

        run({ userInput: USER_INPUT_PLACEHOLDER, agent: mockAgent })
            .then(result => {
                const side = {
                    commitCalls: globalThis.__capturedCommitCalls,
                    allCalls: globalThis.__capturedAllCalls,
                };
                process.stdout.write(JSON.stringify(result) + '\\x00' + JSON.stringify(side));
            })
            .catch(err => {
                process.stderr.write('run() threw: ' + String(err));
                process.exit(1);
            });
    """)
    # Substitute placeholders (safe — no user data in these positions).
    invocation_js = invocation_js.replace("MOCK_AGENT_CODE_PLACEHOLDER", mock_agent_js)
    invocation_js = invocation_js.replace("USER_INPUT_PLACEHOLDER", user_input_js)

    # Build extra context injection (ESM scope, before vm.createContext).
    extra_ctx_lines = ""
    extra_ctx_keys = ""
    if extra_ctx:
        for key, val in extra_ctx.items():
            extra_ctx_lines += f"const {key}_injected = JSON.parse({json.dumps(json.dumps(val))});\n"
            extra_ctx_keys += f"{key}: {key}_injected,\n"

    # JSON-encode both the plan-feature source patches and the invocation code
    # so they can be passed as string values without any escape processing.
    mock_code_js = json.dumps(invocation_js)   # safe: json.dumps escapes all special chars

    script = textwrap.dedent(f"""
        import {{ readFileSync }} from 'fs';
        import vm from 'vm';

        const source = readFileSync({path_js}, 'utf8');

        const baseSource = source
            .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
            .replace(/^export \\{{ run \\}};/m, '// export removed')
            .replace(/^export function/gm, 'function');

        {extra_ctx_lines}
        const mockCode = {mock_code_js};
        const patchedSource = baseSource + '\\x0a' + mockCode;

        const ctx = vm.createContext({{
            ...globalThis,
            process,
            console,
            setTimeout,
            clearTimeout,
            {extra_ctx_keys}
        }});
        const s = new vm.Script(patchedSource);
        s.runInContext(ctx);
    """)
    return _run_node_script(script, timeout=timeout)


def _parse_run_output(proc: subprocess.CompletedProcess) -> tuple[dict, dict]:
    """
    Parse the stdout from _run_with_mock_agent() into (run_result, side_channel).

    Raises NodeScriptError if the Node.js process exited non-zero.
    """
    if proc.returncode != 0:
        msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)
    parts = proc.stdout.split("\x00", 1)
    run_result = json.loads(parts[0])
    side = json.loads(parts[1]) if len(parts) > 1 else {}
    return run_result, side


def _build_scan_direct_script(
    plan_feature_path: str,
    git_status_output: str,
    file_contents: dict,
) -> str:
    """
    Build a self-contained Node.js ESM script that invokes scanOrphanedAcDrafts()
    directly with mocked agent responses.

    Data is passed via JSON.parse() in the ESM outer scope — NOT embedded in a
    backtick template literal. JS backtick template literals interpret backslash
    escape sequences (e.g. \\n becomes a newline), which would corrupt JSON string
    values containing \\n. By setting data on `ctx` before vm.Script runs, the
    mock code inside the vm can access it as a plain JS value with no escaping issues.

    The script structure:
      1. ESM preamble: read and patch plan-feature.js source.
      2. Parse test data in the ESM scope (safe from template-literal escaping).
      3. Build mock code string (plain JS, not a template literal at this level).
      4. Concatenate mock code onto patchedSource.
      5. Create vm context with data globals injected.
      6. Run vm.Script.
    """
    path_js = json.dumps(plan_feature_path)
    git_status_js = json.dumps(git_status_output)           # safe JS string literal
    file_contents_js = json.dumps(json.dumps(file_contents))  # double-encoded: outer=JS string, inner=JSON

    # Mock code as a plain Python string (no f-string interpolation of data).
    # Data is read from ctx.__mockGitStatus / ctx.__mockFileContents at runtime.
    mock_code = textwrap.dedent("""
        async function mockAgent(call) {
            const instructions = (call.input && call.input.instructions) || '';
            if (instructions.includes('git status --porcelain')) {
                return { output: __mockGitStatus, exit_code: 0 };
            }
            const readMatch = instructions.match(/Read the file at path "([^"]+)"/);
            if (readMatch) {
                const filePath = readMatch[1];
                const content = __mockFileContents[filePath] !== undefined
                    ? __mockFileContents[filePath] : null;
                return { content };
            }
            return { status: 'ok' };
        }
        scanOrphanedAcDrafts(mockAgent, 'docs/acceptance-criteria')
            .then(orphans => { process.stdout.write(JSON.stringify(orphans)); })
            .catch(err => { process.stderr.write(String(err)); process.exit(1); });
    """)
    mock_code_js = json.dumps(mock_code)  # encode as a JS string literal (safe)

    return textwrap.dedent(f"""
        import {{ readFileSync }} from 'fs';
        import vm from 'vm';

        const source = readFileSync({path_js}, 'utf8');

        // Strip ESM syntax.
        const baseSource = source
            .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
            .replace(/^export \\{{ run \\}};/m, '// export removed')
            .replace(/^export function/gm, 'function');

        // Test data decoded here (ESM scope — no backtick template escaping).
        const mockGitStatus = {git_status_js};
        const mockFileContents = JSON.parse({file_contents_js});

        // Mock code string (JSON-encoded — no raw newlines in this source).
        const mockCode = {mock_code_js};

        const patchedSource = baseSource + '\\x0a' + mockCode;

        const ctx = vm.createContext({{
            ...globalThis,
            process,
            console,
            setTimeout,
            clearTimeout,
            __mockGitStatus: mockGitStatus,
            __mockFileContents: mockFileContents,
        }});
        const s = new vm.Script(patchedSource);
        s.runInContext(ctx);
    """)


def _run_scan_orphans_directly(
    plan_feature_path: str,
    git_status_output: str,
    file_contents: dict,
    timeout: int = 15,
) -> list:
    """
    Invoke scanOrphanedAcDrafts() directly in a Node.js vm.Script sandbox.

    Returns a list of orphan dicts: [{ filePath, acId }, ...].
    Raises NodeScriptError if the Node.js process exits non-zero.
    """
    script = _build_scan_direct_script(plan_feature_path, git_status_output, file_contents)
    proc = _run_node_script(script, timeout=timeout)
    if proc.returncode != 0:
        msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)
    if not proc.stdout:
        msg = f"Node.js produced no stdout. stderr: {proc.stderr!r}"
        raise NodeScriptError(msg)
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Test class: scan detection logic
# ---------------------------------------------------------------------------


class TestScanOrphanedAcDrafts(unittest.TestCase):
    """
    Behavioral tests for scanOrphanedAcDrafts() detection logic.

    These tests inject controlled git status output and file contents into
    the function via a mocked agent, and assert on the returned orphan list.
    They confirm the runtime detection logic, not just that the function exists.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def test_qualifying_orphan_is_detected(self):
        """
        A YAML file with origin_agent: product-owner and readiness: draft
        is detected and returned as an orphan.

        The test confirms scanOrphanedAcDrafts() actually runs the qualification
        logic at runtime (not just that the function exists in source text).
        """
        git_status_output = "?? docs/acceptance-criteria/ACD-TEST-1.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-TEST-1.yaml": (
                "id: ACD-TEST-1\n"
                "origin_agent: product-owner\n"
                "readiness: draft\n"
                "criteria: Test AC\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(len(orphans), 1, msg=f"Expected 1 orphan, got: {orphans!r}")
        self.assertEqual(orphans[0]["acId"], "ACD-TEST-1")

    def test_business_analyst_origin_agent_is_detected(self):
        """
        A file with origin_agent: business-analyst and readiness: draft
        is detected as an orphan (business-analyst is in the allowed set).
        """
        git_status_output = "?? docs/acceptance-criteria/ACD-TEST-BA.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-TEST-BA.yaml": (
                "id: ACD-TEST-BA\n"
                "origin_agent: business-analyst\n"
                "readiness: draft\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(len(orphans), 1, msg=f"Expected 1 orphan, got: {orphans!r}")

    def test_it_po_origin_agent_is_detected(self):
        """
        A file with origin_agent: it-po and readiness: draft
        is detected as an orphan (it-po is in the allowed set).
        """
        git_status_output = "?? docs/acceptance-criteria/ACD-TEST-ITPO.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-TEST-ITPO.yaml": (
                "id: ACD-TEST-ITPO\n"
                "origin_agent: it-po\n"
                "readiness: draft\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(len(orphans), 1, msg=f"Expected 1 orphan, got: {orphans!r}")

    def test_wrong_origin_agent_not_flagged(self):
        """
        A YAML file with origin_agent NOT in {product-owner, business-analyst, it-po}
        is NOT flagged as an orphan.

        This prevents false positives for user-authored files or files from
        unrelated agents.
        """
        git_status_output = "?? docs/acceptance-criteria/ACD-USER-1.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-USER-1.yaml": (
                "id: ACD-USER-1\n"
                "origin_agent: BrainCandy\n"  # User-authored — not an authoring agent
                "readiness: draft\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(
            len(orphans),
            0,
            msg=(
                f"DEFECT: File with origin_agent='BrainCandy' was flagged as an orphan. "
                f"Only {{'product-owner', 'business-analyst', 'it-po'}} should be accepted. "
                f"Got: {orphans!r}"
            ),
        )

    def test_non_draft_readiness_not_flagged(self):
        """
        A YAML file with readiness != 'draft' is NOT flagged as an orphan.

        ACs with readiness: approved or readiness: reviewed are complete — they
        should not be treated as session leftovers.
        """
        git_status_output = "?? docs/acceptance-criteria/ACD-APPR-1.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-APPR-1.yaml": (
                "id: ACD-APPR-1\n"
                "origin_agent: product-owner\n"
                "readiness: approved\n"  # Not draft — should be skipped
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(
            len(orphans),
            0,
            msg=(
                f"DEFECT: File with readiness='approved' was flagged as an orphan. "
                f"Only readiness='draft' qualifies. Got: {orphans!r}"
            ),
        )

    def test_reviewed_readiness_not_flagged(self):
        """
        A YAML file with readiness: reviewed is NOT flagged as an orphan.
        """
        git_status_output = "M  docs/acceptance-criteria/ACD-REV-1.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-REV-1.yaml": (
                "id: ACD-REV-1\n"
                "origin_agent: business-analyst\n"
                "readiness: reviewed\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(
            len(orphans),
            0,
            msg=(
                f"DEFECT: File with readiness='reviewed' was flagged as orphan. "
                f"Got: {orphans!r}"
            ),
        )

    def test_empty_git_status_returns_no_orphans(self):
        """
        When git status returns no output (clean working tree), no orphans are returned.
        """
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, "", {}
        )
        self.assertEqual(orphans, [], msg="Expected empty orphan list for clean tree.")

    def test_multiple_qualifying_orphans_all_returned(self):
        """
        When multiple qualifying orphan files are present, all are returned.
        """
        git_status_output = (
            "?? docs/acceptance-criteria/ACD-A.yaml\n"
            "?? docs/acceptance-criteria/ACD-B.yaml\n"
        )
        file_contents = {
            "docs/acceptance-criteria/ACD-A.yaml": (
                "id: ACD-A\norigin_agent: product-owner\nreadiness: draft\n"
            ),
            "docs/acceptance-criteria/ACD-B.yaml": (
                "id: ACD-B\norigin_agent: business-analyst\nreadiness: draft\n"
            ),
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(
            len(orphans),
            2,
            msg=f"Expected 2 orphans, got: {orphans!r}",
        )
        ac_ids = {o["acId"] for o in orphans}
        self.assertEqual(ac_ids, {"ACD-A", "ACD-B"})

    def test_modified_tracked_file_is_also_detected(self):
        """
        A modified (M) tracked YAML file that qualifies is also detected as an orphan.

        The scan must pick up both untracked (??) and modified (M) files.
        """
        git_status_output = " M docs/acceptance-criteria/ACD-MOD-1.yaml\n"
        file_contents = {
            "docs/acceptance-criteria/ACD-MOD-1.yaml": (
                "id: ACD-MOD-1\n"
                "origin_agent: it-po\n"
                "readiness: draft\n"
            )
        }
        orphans = _run_scan_orphans_directly(
            self.PLAN_FEATURE_PATH, git_status_output, file_contents
        )
        self.assertEqual(
            len(orphans),
            1,
            msg=f"Expected modified tracked file to be detected as orphan. Got: {orphans!r}",
        )


# ---------------------------------------------------------------------------
# Test class: run() calls recovery scan BEFORE Stage-0 triage
# ---------------------------------------------------------------------------


class TestRecoveryScanBeforeTriage(unittest.TestCase):
    """
    Behavioral tests asserting that run() invokes the recovery scan (via
    scanOrphanedAcDrafts) BEFORE the Stage-0 ac-triage dispatch.

    This is the core phantom-done remediation assertion: the original ticket 04
    failed to add this scan to run() at all. The test instruments call ordering
    to prove the scan precedes triage.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def test_scan_git_status_called_before_triage(self):
        """
        The git status scan call (inside scanOrphanedAcDrafts) MUST appear before
        the ac-triage dispatch in run()'s call sequence.

        This is the primary phantom-done guard: if run() does not call git status
        before dispatching ac-triage, the recovery scan is absent at runtime.
        """
        mock_js = textwrap.dedent("""
            let callIndex = 0;
            globalThis.__firstGitStatusCallIndex = null;
            globalThis.__triageCallIndex = null;

            async function mockAgent(call) {
                callIndex++;
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    n: callIndex,
                    agentType,
                    instructionSnippet: instructions.slice(0, 120),
                });

                // Detect git status scan (inside scanOrphanedAcDrafts).
                if (instructions.includes('git status --porcelain') &&
                    instructions.includes('docs/acceptance-criteria') &&
                    globalThis.__firstGitStatusCallIndex === null) {
                    globalThis.__firstGitStatusCallIndex = callIndex;
                    return { output: '', exit_code: 0 };
                }

                // Detect ac-triage dispatch.
                if (agentType === 'ac-triage') {
                    if (globalThis.__triageCallIndex === null) {
                        globalThis.__triageCallIndex = callIndex;
                    }
                    return {
                        route: 'technical',
                        existing_acs: [],
                        parent_l1_id: null,
                        rationale: 'test'
                    };
                }

                // it-po for technical route.
                if (agentType === 'it-po') {
                    return { status: 'ok', acs_written: ['ACD-SCAN-ORDER-TEST'] };
                }

                // Final gate.
                if (agentType === 'status-checker') {
                    const isFinalGate = instructions.includes('IT PO v3 has enriched');
                    if (isFinalGate) {
                        return { action: 'defer', priority: 'medium' };
                    }
                    return { action: 'approve' };
                }

                if (agentType === 'commit') {
                    globalThis.__capturedCommitCalls.push({ instructions });
                    return { status: 'ok', message: 'mock commit ok' };
                }

                return { status: 'ok' };
            }
        """)

        # We need to capture the ordering globals from the vm context.
        # Extend the script to emit them in the side channel.
        preamble = _build_vm_preamble(self.PLAN_FEATURE_PATH)
        script = preamble + textwrap.dedent(f"""
            + `
            globalThis.__capturedCommitCalls = [];
            globalThis.__capturedAllCalls = [];

            {mock_js}

            run({{ userInput: "test recovery ordering", agent: mockAgent }})
                .then(result => {{
                    const side = {{
                        commitCalls: globalThis.__capturedCommitCalls,
                        allCalls: globalThis.__capturedAllCalls,
                        firstGitStatusCallIndex: globalThis.__firstGitStatusCallIndex,
                        triageCallIndex: globalThis.__triageCallIndex,
                    }};
                    process.stdout.write(JSON.stringify(result) + '\\0' + JSON.stringify(side));
                }})
                .catch(err => {{
                    process.stderr.write('run() threw: ' + String(err));
                    process.exit(1);
                }});
            `;

            const ctx = vm.createContext({{ ...globalThis, process, console, setTimeout, clearTimeout }});
            const s = new vm.Script(patchedSource);
            s.runInContext(ctx);
        """)

        proc = _run_node_script(script, timeout=25)
        if proc.returncode != 0:
            self.fail(
                f"Node.js failed (exit {proc.returncode}).\nstderr: {proc.stderr}"
            )

        parts = proc.stdout.split("\x00", 1)
        side = json.loads(parts[1]) if len(parts) > 1 else {}

        git_status_idx = side.get("firstGitStatusCallIndex")
        triage_idx = side.get("triageCallIndex")

        self.assertIsNotNone(
            git_status_idx,
            msg=(
                "DEFECT: The git status scan was never called. "
                "scanOrphanedAcDrafts() must be invoked by run() before Stage-0 triage. "
                "The recovery scan is absent from run() — this is the phantom-done failure mode."
            ),
        )
        self.assertIsNotNone(
            triage_idx,
            msg="ac-triage was never dispatched — the test scenario is misconfigured.",
        )
        self.assertLess(
            git_status_idx,
            triage_idx,
            msg=(
                f"DEFECT: git status scan (call #{git_status_idx}) was called AFTER "
                f"ac-triage dispatch (call #{triage_idx}). "
                "The recovery scan must precede Stage-0 triage. "
                "Check the order of operations in run()."
            ),
        )


# ---------------------------------------------------------------------------
# Test class: resolveOrphanedDrafts() yes branch
# ---------------------------------------------------------------------------


class TestResolveOrphanedDraftsYesBranch(unittest.TestCase):
    """
    Behavioral tests for the "yes" branch of resolveOrphanedDrafts().

    When orphans exist and the user answers "yes", the commit agent MUST be
    dispatched (via commitStageOutput, the hook-safe path). The pipeline then
    continues to Stage-0 triage.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _run_with_orphan_and_choice(self, choice: str) -> tuple[dict, dict]:
        """
        Run plan-feature with one orphaned AC file present and the given user choice.

        The mock agent:
        - Simulates git status returning one orphaned qualifying YAML file.
        - Simulates file read returning a qualifying AC YAML.
        - Answers the choice prompt with the given choice.
        - For the "yes" branch: allows the commit agent to succeed.
        - Continues through the pipeline (technical route → defer).

        Returns (run_result, side_channel).
        """
        # Inject orphan git status and file content via extra_ctx so they carry
        # real newlines without going through JS string literal escaping.
        # The git status output must end with a real newline so scanOrphanedAcDrafts
        # can split lines correctly (it splits on actual newlines, not backslash-n).
        orphan_status_line = "?? docs/acceptance-criteria/ACD-ORPHAN-1.yaml"
        orphan_content = "id: ACD-ORPHAN-1\norigin_agent: product-owner\nreadiness: draft\n"
        choice_json = json.dumps(choice)

        mock_js = textwrap.dedent(f"""
            async function mockAgent(call) {{
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({{
                    agentType,
                    instructionSnippet: instructions.slice(0, 160),
                }});

                // Simulate git status scan returning one orphaned file.
                // __orphanGitStatus is injected via vm.createContext with a real newline.
                if (instructions.includes('git status --porcelain') &&
                    instructions.includes('docs/acceptance-criteria')) {{
                    return {{ output: globalThis.__orphanGitStatus, exit_code: 0 }};
                }}

                // Simulate file read for the orphaned file.
                // __orphanContent is injected via vm.createContext.
                if (instructions.includes('Read the file at path') &&
                    instructions.includes('ACD-ORPHAN-1.yaml')) {{
                    return {{ content: globalThis.__orphanContent }};
                }}

                // Answer the yes/no/discard prompt.
                if (instructions.includes('prior session') && instructions.includes('yes/no/discard')) {{
                    return {{ choice: {choice_json} }};
                }}

                // Commit agent (dispatched by commitStageOutput for yes branch).
                if (agentType === 'commit') {{
                    globalThis.__capturedCommitCalls.push({{ agentType }});
                    return {{ status: 'ok', message: 'mock commit ok' }};
                }}

                // ac-triage (Stage 0 — reached after recovery completes).
                if (agentType === 'ac-triage') {{
                    return {{ route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' }};
                }}

                if (agentType === 'it-po') {{
                    return {{ status: 'ok', acs_written: ['ACD-NEW-1'] }};
                }}

                if (agentType === 'status-checker') {{
                    const isFinalGate = instructions.includes('IT PO v3 has enriched');
                    if (isFinalGate) {{
                        return {{ action: 'defer', priority: 'medium' }};
                    }}
                    return {{ action: 'approve' }};
                }}

                return {{ status: 'ok' }};
            }}
        """)
        extra_ctx = {
            "__orphanGitStatus": orphan_status_line + "\n",
            "__orphanContent": orphan_content,
        }
        proc = _run_with_mock_agent(
            self.PLAN_FEATURE_PATH, mock_js,
            user_input="test yes branch",
            extra_ctx=extra_ctx,
        )
        return _parse_run_output(proc)

    def test_yes_branch_dispatches_commit_agent(self):
        """
        When the user answers "yes" to the recovery prompt, the commit agent
        MUST be dispatched (via commitStageOutput's hook-safe path).

        This is the primary assertion for the "yes" branch: the orphaned files
        are committed before new triage begins.
        """
        try:
            _run_result, side = self._run_with_orphan_and_choice("yes")
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        # Check both commitCalls (explicit capture) and allCalls (universal capture).
        # allCalls is the more reliable signal since it captures every agent dispatch
        # regardless of whether the commit-specific push succeeded.
        commit_calls = side.get("commitCalls", [])
        all_calls = side.get("allCalls", [])
        commit_dispatches_in_all = [
            c for c in all_calls if c.get("agentType") == "commit"
        ]

        was_committed = len(commit_calls) > 0 or len(commit_dispatches_in_all) > 0
        self.assertTrue(
            was_committed,
            msg=(
                "DEFECT: The commit agent was not dispatched after user answered 'yes' "
                "to the recovery prompt. The 'yes' branch in resolveOrphanedDrafts() "
                "must call commitStageOutput() which dispatches the commit agent.\n"
                f"commitCalls: {commit_calls!r}\n"
                f"commit dispatches in allCalls: {commit_dispatches_in_all!r}\n"
                f"allCalls (all dispatches): {all_calls!r}"
            ),
        )

    def test_yes_branch_pipeline_continues_to_triage(self):
        """
        After the "yes" branch commits orphans, the pipeline MUST continue to
        Stage-0 ac-triage. The workflow should not abort.
        """
        try:
            run_result, side = self._run_with_orphan_and_choice("yes")
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        all_calls = side.get("allCalls", [])
        triage_calls = [c for c in all_calls if c.get("agentType") == "ac-triage"]

        self.assertGreater(
            len(triage_calls),
            0,
            msg=(
                "DEFECT: ac-triage was never dispatched after user answered 'yes'. "
                "The pipeline should continue to Stage-0 after orphan commit."
            ),
        )


# ---------------------------------------------------------------------------
# Test class: resolveOrphanedDrafts() no branch
# ---------------------------------------------------------------------------


class TestResolveOrphanedDraftsNoBranch(unittest.TestCase):
    """
    Behavioral tests for the "no" branch of resolveOrphanedDrafts().

    When the user answers "no", the workflow MUST abort with an error status.
    ac-triage must NOT be dispatched.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _run_with_orphan_no_choice(self) -> tuple[dict, dict]:
        """Run with one orphaned AC file and user choice = no."""
        mock_js = textwrap.dedent("""
            async function mockAgent(call) {
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';

                globalThis.__capturedAllCalls.push({
                    agentType,
                    instructionSnippet: instructions.slice(0, 160),
                });

                if (instructions.includes('git status --porcelain') &&
                    instructions.includes('docs/acceptance-criteria')) {
                    return { output: '?? docs/acceptance-criteria/ACD-NO-1.yaml\\n', exit_code: 0 };
                }

                if (instructions.includes('Read the file at path') &&
                    instructions.includes('ACD-NO-1.yaml')) {
                    return { content: 'id: ACD-NO-1\\norigin_agent: product-owner\\nreadiness: draft\\n' };
                }

                if (instructions.includes('prior session') && instructions.includes('yes/no/discard')) {
                    return { choice: 'no' };
                }

                if (agentType === 'commit') {
                    globalThis.__capturedCommitCalls.push({ instructions });
                    return { status: 'ok', message: 'mock commit ok' };
                }

                if (agentType === 'ac-triage') {
                    return { route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' };
                }

                return { status: 'ok' };
            }
        """)
        proc = _run_with_mock_agent(self.PLAN_FEATURE_PATH, mock_js)
        return _parse_run_output(proc)

    def test_no_branch_returns_error_status(self):
        """
        When the user answers "no" to the recovery prompt, run() MUST return
        status 'error' (abort), not status 'ok'.

        The workflow cannot proceed when the user explicitly refuses to resolve
        the uncommitted AC files.
        """
        try:
            run_result, _side = self._run_with_orphan_no_choice()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        self.assertEqual(
            run_result.get("status"),
            "error",
            msg=(
                "DEFECT: run() returned status='ok' after user answered 'no' "
                "to the recovery prompt. The 'no' branch must abort the workflow "
                "with status='error'.\n"
                f"Got: {run_result!r}"
            ),
        )

    def test_no_branch_does_not_dispatch_triage(self):
        """
        When the user answers "no", ac-triage MUST NOT be dispatched.

        The workflow must abort before any new authoring work begins.
        """
        try:
            _run_result, side = self._run_with_orphan_no_choice()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        all_calls = side.get("allCalls", [])
        triage_calls = [c for c in all_calls if c.get("agentType") == "ac-triage"]

        self.assertEqual(
            len(triage_calls),
            0,
            msg=(
                "DEFECT: ac-triage was dispatched after user answered 'no'. "
                "The workflow must abort before Stage-0 when the user refuses to "
                "resolve orphaned files."
            ),
        )

    def test_no_branch_error_message_mentions_uncommitted_files(self):
        """
        The error message returned on "no" must mention uncommitted files and
        instruct the user to resolve them before re-running.
        """
        try:
            run_result, _side = self._run_with_orphan_no_choice()
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        message = run_result.get("message", "")
        self.assertIn(
            "resolved",
            message.lower(),
            msg=(
                "DEFECT: The 'no' abort message does not mention resolving files. "
                f"Got message: {message!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Test class: resolveOrphanedDrafts() discard branch
# ---------------------------------------------------------------------------


class TestResolveOrphanedDraftsDiscardBranch(unittest.TestCase):
    """
    Behavioral tests for the "discard" branch of resolveOrphanedDrafts().

    When the user answers "discard":
    - Tracked modified files -> git restore is called.
    - Untracked new files -> rm (or delete) is called.
    - BOTH operations must be asserted, not just one.
    - The pipeline continues to Stage-0 after discard.

    This is critical for ACD-300g-2-i correctness: git restore alone does NOT
    remove untracked files. A discard that only calls git restore leaves new
    untracked draft files on disk.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _run_discard_scenario(
        self, git_status_for_orphan: str, orphan_path: str
    ) -> tuple[dict, dict]:
        """
        Run with one orphaned AC file and user choice = discard.

        Data (orphan_path and per-file status) is injected via vm.createContext()
        globals so the mock code can read them without embedding data inside a
        JS backtick template literal (which would process escape sequences).

        git_status_for_orphan: the porcelain status line for the specific orphan file
        (used in the per-file re-check that discard does to determine tracked vs untracked).
        """
        orphan_filename = orphan_path.rsplit("/", 1)[-1]
        orphan_content = (
            "id: ACD-DISCARD-1\norigin_agent: product-owner\nreadiness: draft\n"
        )

        # Mock agent reads orphan path and status from globalThis (__discardOrphanPath,
        # __discardPerFileStatus) so no data is embedded inside a backtick template.
        mock_js = textwrap.dedent(f"""
            globalThis.__restoreCalls = [];
            globalThis.__deleteCalls = [];

            async function mockAgent(call) {{
                const agentType = call.agentType || '';
                const instructions = (call.input && call.input.instructions) || '';
                const orphanPath = globalThis.__discardOrphanPath;
                const perFileStatus = globalThis.__discardPerFileStatus;
                const orphanContent = globalThis.__discardOrphanContent;

                globalThis.__capturedAllCalls.push({{
                    agentType,
                    instructionSnippet: instructions.slice(0, 200),
                }});

                // Main git status scan (all of docs/acceptance-criteria).
                if (instructions.includes('git status --porcelain') &&
                    instructions.includes('docs/acceptance-criteria') &&
                    !instructions.includes(orphanPath)) {{
                    return {{ output: perFileStatus + ' ', exit_code: 0 }};
                }}

                // Per-file git status check (inside discard loop).
                if (instructions.includes('git status --porcelain') &&
                    instructions.includes(orphanPath)) {{
                    return {{ output: perFileStatus, exit_code: 0 }};
                }}

                // Simulate file read for the orphaned file.
                if (instructions.includes('Read the file at path') &&
                    instructions.includes('{orphan_filename}')) {{
                    return {{ content: orphanContent }};
                }}

                // Answer the yes/no/discard prompt.
                if (instructions.includes('prior session') && instructions.includes('yes/no/discard')) {{
                    return {{ choice: 'discard' }};
                }}

                // Detect git restore call (tracked file revert).
                if (instructions.includes('git restore') && instructions.includes(orphanPath)) {{
                    globalThis.__restoreCalls.push({{ instructions: instructions.slice(0, 200) }});
                    return {{ exit_code: 0 }};
                }}

                // Detect rm / delete call (untracked file removal).
                if ((instructions.includes('rm -f') || instructions.includes('rm ') ||
                     instructions.includes('fs.unlinkSync') || instructions.includes('Delete the file')) &&
                    instructions.includes(orphanPath)) {{
                    globalThis.__deleteCalls.push({{ instructions: instructions.slice(0, 200) }});
                    return {{ exit_code: 0 }};
                }}

                // ac-triage (Stage 0 — reached after discard completes).
                if (agentType === 'ac-triage') {{
                    return {{ route: 'technical', existing_acs: [], parent_l1_id: null, rationale: 'test' }};
                }}

                if (agentType === 'it-po') {{
                    return {{ status: 'ok', acs_written: ['ACD-AFTER-DISCARD'] }};
                }}

                if (agentType === 'status-checker') {{
                    const isFinalGate = instructions.includes('IT PO v3 has enriched');
                    if (isFinalGate) {{
                        return {{ action: 'defer', priority: 'medium' }};
                    }}
                    return {{ action: 'approve' }};
                }}

                if (agentType === 'commit') {{
                    globalThis.__capturedCommitCalls.push({{ instructions }});
                    return {{ status: 'ok', message: 'mock commit ok' }};
                }}

                return {{ status: 'ok' }};
            }}
        """)

        # Use _run_with_mock_agent with extra_ctx to inject data-carrying globals.
        # The side channel from _run_with_mock_agent only captures commitCalls and allCalls.
        # For restoreCalls and deleteCalls, we extend by building a custom invocation.
        path_js = json.dumps(self.PLAN_FEATURE_PATH)
        extra_ctx = {
            "__discardOrphanPath": orphan_path,
            "__discardPerFileStatus": git_status_for_orphan,
            "__discardOrphanContent": orphan_content,
        }

        # Build invocation JS that also captures restoreCalls and deleteCalls.
        invocation_js = textwrap.dedent("""
            globalThis.__capturedCommitCalls = [];
            globalThis.__capturedAllCalls = [];

            MOCK_PLACEHOLDER

            run({ userInput: "test discard scenario", agent: mockAgent })
                .then(result => {
                    const side = {
                        commitCalls: globalThis.__capturedCommitCalls,
                        allCalls: globalThis.__capturedAllCalls,
                        restoreCalls: globalThis.__restoreCalls || [],
                        deleteCalls: globalThis.__deleteCalls || [],
                    };
                    process.stdout.write(JSON.stringify(result) + '\\x00' + JSON.stringify(side));
                })
                .catch(err => {
                    process.stderr.write('run() threw: ' + String(err));
                    process.exit(1);
                });
        """).replace("MOCK_PLACEHOLDER", mock_js)

        mock_code_js = json.dumps(invocation_js)

        extra_ctx_lines = ""
        extra_ctx_keys = ""
        for key, val in extra_ctx.items():
            extra_ctx_lines += f"const {key}_var = JSON.parse({json.dumps(json.dumps(val))});\n"
            extra_ctx_keys += f"{key}: {key}_var,\n"

        script = textwrap.dedent(f"""
            import {{ readFileSync }} from 'fs';
            import vm from 'vm';

            const source = readFileSync({path_js}, 'utf8');

            const baseSource = source
                .replace(/^export const meta[\\s\\S]*?^\\}};/m, 'const meta = {{}};')
                .replace(/^export \\{{ run \\}};/m, '// export removed')
                .replace(/^export function/gm, 'function');

            {extra_ctx_lines}
            const mockCode = {mock_code_js};
            const patchedSource = baseSource + '\\x0a' + mockCode;

            const ctx = vm.createContext({{
                ...globalThis,
                process,
                console,
                setTimeout,
                clearTimeout,
                {extra_ctx_keys}
            }});
            const s = new vm.Script(patchedSource);
            s.runInContext(ctx);
        """)

        proc = _run_node_script(script, timeout=25)
        if proc.returncode != 0:
            msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
            raise NodeScriptError(msg)
        parts = proc.stdout.split("\x00", 1)
        run_result = json.loads(parts[0])
        side = json.loads(parts[1]) if len(parts) > 1 else {}
        return run_result, side

    def test_discard_tracked_modified_calls_git_restore(self):
        """
        For a tracked modified (M) orphan file, the discard branch MUST call
        git restore (or git checkout --) to revert the working-tree changes.

        This is an explicit assertion that the restore path executes at runtime,
        not just that "git restore" appears in the source code.
        """
        orphan_path = "docs/acceptance-criteria/ACD-TRACKED-1.yaml"
        # Tracked worktree-modified file: status " M" (index clean, worktree modified).
        git_status_line = " M " + orphan_path

        try:
            _run_result, side = self._run_discard_scenario(git_status_line, orphan_path)
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        restore_calls = side.get("restoreCalls", [])
        self.assertGreater(
            len(restore_calls),
            0,
            msg=(
                "DEFECT: git restore was NOT called for a tracked modified orphan file. "
                "The discard branch must call 'git restore <file>' to revert "
                "working-tree changes for tracked (M) files.\n"
                f"Captured restore calls: {restore_calls!r}"
            ),
        )

    def test_discard_untracked_file_calls_delete(self):
        """
        For an untracked (??) orphan file, the discard branch MUST call rm (or
        equivalent delete) to remove the file — NOT git restore.

        This is the critical correctness assertion: git restore cannot remove
        untracked files. The discard branch must use rm/unlinkSync/git clean
        for the untracked case.
        """
        orphan_path = "docs/acceptance-criteria/ACD-UNTRACKED-1.yaml"
        git_status_line = "?? " + orphan_path

        try:
            _run_result, side = self._run_discard_scenario(git_status_line, orphan_path)
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        delete_calls = side.get("deleteCalls", [])
        self.assertGreater(
            len(delete_calls),
            0,
            msg=(
                "DEFECT: rm/delete was NOT called for an untracked orphan file. "
                "git restore alone cannot remove untracked files — the discard branch "
                "MUST explicitly delete untracked files (rm, fs.unlinkSync, or git clean).\n"
                "This is the gap described in the ticket: 'git checkout -- docs/acceptance-criteria/' "
                "will NOT remove UNTRACKED draft .yaml files.\n"
                f"Captured delete calls: {delete_calls!r}"
            ),
        )

    def test_discard_pipeline_continues_after_discard(self):
        """
        After the "discard" branch completes, the pipeline MUST continue to
        Stage-0 ac-triage (the discard should result in action='continue').
        """
        orphan_path = "docs/acceptance-criteria/ACD-DISCARD-CONT.yaml"
        git_status_line = "?? " + orphan_path

        try:
            run_result, side = self._run_discard_scenario(git_status_line, orphan_path)
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        all_calls = side.get("allCalls", [])
        triage_calls = [c for c in all_calls if c.get("agentType") == "ac-triage"]

        self.assertGreater(
            len(triage_calls),
            0,
            msg=(
                "DEFECT: ac-triage was not dispatched after discard. "
                "The 'discard' branch must return action='continue' so the pipeline "
                "proceeds to Stage-0."
            ),
        )


# ---------------------------------------------------------------------------
# Test class: template parity
# ---------------------------------------------------------------------------


class TestRecoveryFunctionParityWithTemplate(unittest.TestCase):
    """
    Verify that the new recovery functions in scripts/workflows/plan-feature.js and
    templates/workflows-js/plan-feature.js are identical (byte-level parity).

    Both files must be modified identically — the template is the canonical source
    deployed to consumer projects. A partial fix that updates only scripts/ means
    consumer projects carry the old behaviour.
    """

    def _extract_function(self, source: str, func_name: str, path: str) -> str:
        """Extract a complete async/non-async function body by name."""
        # Match both 'async function name(' and 'function name('
        start_patterns = [
            f"async function {func_name}(",
            f"function {func_name}(",
        ]
        start = -1
        for pat in start_patterns:
            idx = source.find(pat)
            if idx != -1:
                start = idx
                break
        if start == -1:
            raise SourceParseError(f"{func_name} not found in {path}")

        depth = 0
        i = start
        found_first_brace = False
        while i < len(source):
            c = source[i]
            if c == "{":
                depth += 1
                found_first_brace = True
            elif c == "}" and found_first_brace:
                depth -= 1
                if depth == 0:
                    return source[start: i + 1]
            i += 1
        raise SourceParseError(f"{func_name} closing brace not found in {path}")

    def test_scan_orphaned_ac_drafts_function_parity(self):
        """
        scanOrphanedAcDrafts() must be byte-identical in scripts/ and templates/.
        """
        scripts_source = _read_source(_PLAN_FEATURE_JS)
        template_source = _read_source(_TEMPLATE_PLAN_FEATURE_JS)

        scripts_fn = self._extract_function(scripts_source, "scanOrphanedAcDrafts", _PLAN_FEATURE_JS)
        template_fn = self._extract_function(template_source, "scanOrphanedAcDrafts", _TEMPLATE_PLAN_FEATURE_JS)

        self.assertEqual(
            scripts_fn,
            template_fn,
            msg=(
                "scripts/workflows/plan-feature.js and templates/workflows-js/plan-feature.js "
                "have DIFFERENT scanOrphanedAcDrafts() bodies. Both files must be identical."
            ),
        )

    def test_resolve_orphaned_drafts_function_parity(self):
        """
        resolveOrphanedDrafts() must be byte-identical in scripts/ and templates/.
        """
        scripts_source = _read_source(_PLAN_FEATURE_JS)
        template_source = _read_source(_TEMPLATE_PLAN_FEATURE_JS)

        scripts_fn = self._extract_function(scripts_source, "resolveOrphanedDrafts", _PLAN_FEATURE_JS)
        template_fn = self._extract_function(template_source, "resolveOrphanedDrafts", _TEMPLATE_PLAN_FEATURE_JS)

        self.assertEqual(
            scripts_fn,
            template_fn,
            msg=(
                "scripts/workflows/plan-feature.js and templates/workflows-js/plan-feature.js "
                "have DIFFERENT resolveOrphanedDrafts() bodies. Both files must be identical."
            ),
        )

    def test_run_function_parity(self):
        """
        The run() function (including the recovery scan block) must be byte-identical
        in scripts/ and templates/.
        """
        scripts_source = _read_source(_PLAN_FEATURE_JS)
        template_source = _read_source(_TEMPLATE_PLAN_FEATURE_JS)

        scripts_fn = self._extract_function(scripts_source, "run", _PLAN_FEATURE_JS)
        template_fn = self._extract_function(template_source, "run", _TEMPLATE_PLAN_FEATURE_JS)

        self.assertEqual(
            scripts_fn,
            template_fn,
            msg=(
                "scripts/workflows/plan-feature.js and templates/workflows-js/plan-feature.js "
                "have DIFFERENT run() function bodies. Both files must be identical."
            ),
        )

    def test_build_cancel_message_parity(self):
        """
        buildCancelMessage() must be byte-identical in scripts/ and templates/.

        The cancel message fix (mentioning untracked files) must also be applied
        to both copies.
        """
        scripts_source = _read_source(_PLAN_FEATURE_JS)
        template_source = _read_source(_TEMPLATE_PLAN_FEATURE_JS)

        scripts_fn = self._extract_function(scripts_source, "buildCancelMessage", _PLAN_FEATURE_JS)
        template_fn = self._extract_function(template_source, "buildCancelMessage", _TEMPLATE_PLAN_FEATURE_JS)

        self.assertEqual(
            scripts_fn,
            template_fn,
            msg=(
                "scripts/ and templates/ have DIFFERENT buildCancelMessage() bodies. "
                "The untracked-files warning fix must be applied to both."
            ),
        )


# ---------------------------------------------------------------------------
# Test class: buildCancelMessage untracked file warning
# ---------------------------------------------------------------------------


class TestBuildCancelMessageUntrackedWarning(unittest.TestCase):
    """
    Verify that buildCancelMessage() mentions that untracked files require
    explicit removal (not just git checkout --).

    The original message only advised `git checkout -- docs/acceptance-criteria/`
    which does NOT remove untracked files. This test asserts the fix is in place.
    """

    PLAN_FEATURE_PATH = _PLAN_FEATURE_JS

    def _call_build_cancel_message(
        self, committed_acs: list, draft_acs: list, cancelled_at: str
    ) -> str:
        """
        Invoke buildCancelMessage() directly in a vm.Script sandbox.

        Returns the string result.
        """
        preamble = _build_vm_preamble(self.PLAN_FEATURE_PATH)
        committed_js = json.dumps(committed_acs)
        draft_js = json.dumps(draft_acs)
        cancelled_js = json.dumps(cancelled_at)

        script = preamble + textwrap.dedent(f"""
            + `
            const result = buildCancelMessage({committed_js}, {draft_js}, {cancelled_js});
            process.stdout.write(result);
            `;

            const ctx = vm.createContext({{ ...globalThis, process, console }});
            const s = new vm.Script(patchedSource);
            s.runInContext(ctx);
        """)
        proc = _run_node_script(script, timeout=10)
        if proc.returncode != 0:
            msg = f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
            raise NodeScriptError(msg)
        return proc.stdout

    def test_cancel_message_mentions_untracked_files(self):
        """
        When buildCancelMessage() is called with draft ACs, the returned message
        MUST mention that untracked files require explicit removal (not just git checkout).

        This addresses the gap identified in the ticket: 'git checkout -- docs/acceptance-criteria/'
        will NOT remove UNTRACKED draft YAML files that were never staged.

        The message must convey that both operations (restore + explicit delete) are required.
        """
        try:
            message = self._call_build_cancel_message(
                committed_acs=[],
                draft_acs=["ACD-CANCEL-1"],
                cancelled_at="gate after product-owner",
            )
        except NodeScriptError as exc:
            self.fail(f"Node.js failed unexpectedly: {exc}")

        # The message must either explicitly mention "untracked" or note that
        # git checkout alone is insufficient (or both).
        mentions_untracked = "untracked" in message.lower()
        mentions_both_steps = (
            "git checkout" in message or "git restore" in message
        ) and (
            "rm" in message or "delete" in message or "remove" in message or "explicit" in message
        )

        self.assertTrue(
            mentions_untracked or mentions_both_steps,
            msg=(
                "DEFECT: buildCancelMessage() does not warn about untracked files. "
                "The message must mention that git checkout -- alone does NOT remove "
                "untracked new AC files, and that explicit deletion is also required.\n"
                f"Got message:\n{message}"
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
