"""
MODULE: test_bp_1100b_4
GOAL: Calibrate `_workflow_engine_harness.py` against the real E2 engine's
    injected-globals contract (ADR-030) BEFORE any journal test is re-authored
    against it — the harness fidelity fix is the prerequisite this ticket
    mandates comes FIRST (see BP-1100b-4's it_requirements "ORDERING"
    constraint).
BUSINESS CONTEXT: A reviewer executed run_workflow_under_e2() against
    finalize-feature.js and it wrote journal records under the OLD (pre-vm)
    harness with ZERO implementation, because the harness ran the target
    script as a plain Node.js module — `require`, `fs`, `process`, `module`,
    etc. were all still reachable from the workflow body, unlike the real E2
    engine, which injects only a fixed set of named globals into the script
    body and exposes no module loader or filesystem primitive. Authoring
    behavioral tests against that harness would certify behaviour production
    cannot perform. These tests prove, by execution, that the harness now
    denies exactly what the real engine denies.
ARCHITECTURE: Drives the REAL harness (`run_workflow_under_e2`) against small,
    synthetic workflow-script bodies (not finalize-feature.js) written to a
    temp .js file, so each test isolates exactly one fidelity property. Each
    synthetic script reports what it observed back to the Python side via a
    single `agent()` call whose `opts` dict carries the probe results — this
    is the only public channel `HarnessResult` exposes (agent_calls,
    contract_violations, stdout/stderr/returncode/error, result), and using
    it keeps these tests EXECUTED (they actually run the harness), never a
    presence-only grep of `_workflow_engine_harness.py` itself — the exact
    defect class BP-1100b-5 exists to reject.

    MODULE SPLIT: the calibration tests (filesystem-dependent journaling
    produces zero records; a run that cannot append fails rather than
    passing) moved to test_bp_1100b_4_calibration.py, and the sandbox-escape
    / strict-mode regression tests moved to
    test_bp_1100b_4_sandbox_fidelity.py, once this file grew past the
    project's 400-line new-file guideline. `_write_script()` and `_TIMEOUT`
    are re-exported (imported) by both sibling files rather than duplicated.
AC: BP-1100b-4
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/). E402 is suppressed in ruff.toml.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import (  # noqa: E402
    ADR_030_INJECTED_GLOBALS,
    SANDBOX_BACK_COMPAT_GLOBALS,
    run_workflow_under_e2,
)

_TIMEOUT = 15

# F7 FIX: the injected-globals set is NO LONGER hand-typed a second time here.
# ADR_030_INJECTED_GLOBALS and SANDBOX_BACK_COMPAT_GLOBALS are imported
# directly from _workflow_engine_harness — the SAME constants the harness
# uses to build the actual vm sandbox object (_SANDBOX_ENTRIES_JS) — so this
# test can never independently drift from what the harness really exposes.
# An adversarial review found the previous local copy
# (_ENGINE_INJECTED_GLOBALS) was exactly the "second hand-typed copy" that
# BP-1100b-4's own it_requirements constraint forbids, despite this file's
# own docstring claiming the opposite ("not asserted against a copy of the
# list taken from the harness source").

# Names that must NOT be reachable from the workflow body: module loaders and
# filesystem primitives that a plain (un-sandboxed) Node.js module always
# exposes, but the real E2 engine does not. This list is intentionally local
# (not part of the ADR-030 contract the harness constants declare) — it
# enumerates what the DENIAL side of the fidelity property must cover, not
# what the sandbox positively exposes.
_FORBIDDEN_NAMES = [
    "require",
    "module",
    "exports",
    "process",
    "__dirname",
    "__filename",
]


def _write_script(tmp_dir: Path, body: str) -> Path:
    """Write a synthetic workflow-script body to a temp .js file.

    Args:
        tmp_dir: Directory to write the script into.
        body: The JS source for the script body (no wrapping needed — the
            harness itself wraps the body in an async IIFE).

    Returns:
        Path to the written .js file.
    """
    script_path = tmp_dir / "probe.js"
    script_path.write_text(body, encoding="utf-8")
    return script_path


def _compute_bare_vm_context_baseline_names(timeout: int = _TIMEOUT) -> set[str]:
    """Return the own-property-name set of a FRESH, empty, null-prototype
    `vm.createContext()` global object, ENUMERATED FROM INSIDE THAT CONTEXT
    (via `vm.runInContext`) — i.e. exactly the JS intrinsics (`Object`,
    `Array`, `Function`, `eval`, `globalThis`, ...) that any contextified
    realm carries for free, with nothing added.

    "From inside" matters and is not a stylistic choice: enumerating the
    sandbox object from the OUTSIDE (`Object.getOwnPropertyNames(ctx)` in the
    driver realm, without ever running code in the context) returns only the
    explicitly-set own properties of the plain shell object — none of V8's
    global intrinsics, because `vm.createContext()` associates a context with
    an internal global object lazily; the intrinsics only become visible
    through `globalThis` as seen BY CODE RUNNING IN THAT CONTEXT. Enumerating
    from outside first (an earlier version of this probe) produced a baseline
    of ~2 names against a real sandbox enumeration of ~70, which would have
    misattributed every JS intrinsic to this harness's own sandbox additions.
    Matching the measurement technique to how the real enumeration test below
    measures the sandbox (also via `vm.runInContext`, from inside) is what
    makes the diff meaningful.

    F6 FIX support: rather than hardcoding a list of "known JS intrinsics"
    (which would silently go stale across Node versions and re-introduce the
    same drift problem F7 exists to prevent), this measures the baseline
    EMPIRICALLY on whatever Node the test actually runs under, so the
    enumeration test below can compute a version-independent DIFF: sandbox
    names minus baseline names must equal exactly the declared globals.

    Raises:
        RuntimeError: if the node subprocess fails or its output cannot be
            parsed as a JSON array of strings.
    """
    script = (
        "const vm = require('vm');\n"
        "const ctx = Object.create(null);\n"
        "vm.createContext(ctx);\n"
        "const names = vm.runInContext("
        "'Object.getOwnPropertyNames(globalThis)', ctx);\n"
        "process.stdout.write(JSON.stringify(names));\n"
    )
    try:
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(f"Could not compute vm baseline: {exc}") from exc

    if proc.returncode != 0:
        raise RuntimeError(
            f"node -e baseline probe exited {proc.returncode}: {proc.stderr}"
        )
    try:
        names = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not parse baseline probe output as JSON: {proc.stdout!r}"
        ) from exc
    return set(names)


class TestHarnessExposesOnlyEngineInjectedGlobals(unittest.TestCase):
    """BP-1100b-4: the harness exposes exactly the engine-injected globals and
    no module loader or filesystem primitive.
    """

    def test_harness_exposes_only_the_engine_injected_globals(self):
        # covers: BP-1100b-4
        """A workflow body run under run_workflow_under_e2() can reach
        EXACTLY the globals the real engine injects (agent, parallel,
        pipeline, phase, log, args, workflow, budget) plus the documented
        `console` back-compat exception, and nothing else — a true
        ENUMERATION of the sandbox's namespace, not a spot-check.

        F6 FIX: the previous version checked 8 names present and 6 names
        absent — an allowlist/denylist spot-check over 14 identifiers, which
        an adversarial review correctly noted is not what "EXACTLY this set —
        no more, no less" (this class's own docstring) or "nothing else"
        (the module docstring) claim. It could not catch a future accidental
        addition to the sandbox object, because it never looked at the whole
        namespace.

        This version enumerates `Object.getOwnPropertyNames(globalThis)`
        from INSIDE the sandboxed body and diffs it against the same
        enumeration of a bare, empty, null-prototype `vm.createContext()`
        (computed fresh by `_compute_bare_vm_context_baseline_names()` on
        whatever Node this test actually runs under, never a hardcoded
        intrinsics list that could go stale across Node versions). The
        result of that diff — what the sandbox adds BEYOND a bare context —
        must equal EXACTLY `ADR_030_INJECTED_GLOBALS`, imported directly from
        the harness (F7 fix: no second hand-typed copy).

        `console` is checked SEPARATELY, not folded into the diff: measured
        empirically, `console` is already present on a bare, un-augmented
        `vm.createContext()` — it is a Node vm intrinsic, not something the
        harness's `__sandbox__` object literal actually adds. The harness's
        `console: console` entry overrides which `console` object the
        sandbox sees (the driver's, not the context's own default one) but
        does not add a new NAME to the namespace, so it would never appear in
        an "added beyond baseline" diff regardless of whether the harness
        code exists at all. The property this AC actually cares about —
        `console` remains reachable — is asserted directly against
        `sandbox_names`, which is true unconditionally on today's Node and
        would only ever need the harness's explicit override to keep being
        true if some future Node version stopped providing it for free.
        """
        body = (
            "await agent('probe', { label: 'probe', "
            "names: Object.getOwnPropertyNames(globalThis) });\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(
            result.error,
            "",
            msg=f"Harness itself errored (stderr: {result.stderr}): {result.error}",
        )
        self.assertEqual(
            result.dispatch_count,
            1,
            msg=(
                "Expected exactly one probe agent() call to be captured. "
                f"stderr: {result.stderr}"
            ),
        )
        sandbox_names = set(result.agent_calls[0].opts.get("names", []))
        baseline_names = _compute_bare_vm_context_baseline_names()

        # What the sandbox adds BEYOND a bare vm context must be exactly the
        # 8 ADR-030 globals — no more, no less. `console` is intentionally
        # excluded from this side of the check: measured empirically (see
        # this test's own docstring), it is already present in
        # `baseline_names` as a Node vm intrinsic, so it never appears in a
        # "beyond baseline" diff regardless of the harness's own code.
        added_names = sandbox_names - baseline_names
        expected_added = set(ADR_030_INJECTED_GLOBALS)

        self.assertEqual(
            added_names,
            expected_added,
            msg=(
                f"The sandbox's namespace, minus a bare empty vm context's own "
                f"intrinsics, is {added_names}. The ADR-030 contract declares "
                f"exactly {expected_added}. Missing: "
                f"{expected_added - added_names}. Unexpected extra (a "
                f"namespace leak): {added_names - expected_added}."
            ),
        )

        # `console` (the documented back-compat exception) must still be
        # reachable — checked directly against the full enumeration, not via
        # the baseline diff, since it is not a name the sandbox "adds".
        missing_back_compat = set(SANDBOX_BACK_COMPAT_GLOBALS) - sandbox_names
        self.assertEqual(
            missing_back_compat,
            set(),
            msg=(
                f"Documented back-compat global(s) not reachable in the "
                f"sandbox: {missing_back_compat}."
            ),
        )

        # VACUOUS-ASSERTION FIX (2026-08-26): the `missing_back_compat` check
        # above can never fail — `console` is already present on a bare,
        # un-augmented `vm.createContext()` (this test's own docstring says
        # so), so `console` being IN sandbox_names is true whether or not the
        # harness's own console entry exists at all. The property that
        # actually matters, and that the round-1 harness got wrong, is
        # BEHAVIORAL: `console.log()` must be a true no-op that never writes
        # to the SAME stdout stream the driver uses to serialise
        # `HarnessResult` as JSON. Round 1 assigned the DRIVER's own live
        # `console` object into the sandbox (`console: console`); calling
        # `console.log()` from the sandboxed body therefore wrote real text
        # to the driver's stdout ahead of the JSON payload, which did not
        # raise a parse error but silently corrupted `dispatch_count` (a
        # script that dispatched exactly one `agent()` call read back as
        # zero). Round 2 replaced it with a sandbox-realm no-op stub (see
        # `_MOCK_GLOBAL_JS_SNIPPETS["console"]` in `_workflow_engine_harness.
        # py`). Confirmed by direct execution: RED against the round-1-only
        # harness (the marker text leaked into `result.stdout` and
        # `dispatch_count` read 0), GREEN against the current one.
        console_probe_body = (
            "console.log('BP_1100B_4_CONSOLE_NOOP_MARKER');\n"
            "await agent('probe2', { label: 'probe2' });\n"
        )
        with tempfile.TemporaryDirectory() as tmp2:
            probe_script = _write_script(Path(tmp2), console_probe_body)
            probe_result = run_workflow_under_e2(probe_script, timeout=_TIMEOUT)

        self.assertEqual(
            probe_result.error,
            "",
            msg=f"Harness errored on console no-op probe: {probe_result.error}",
        )
        self.assertNotIn(
            "BP_1100B_4_CONSOLE_NOOP_MARKER",
            probe_result.stdout,
            msg=(
                "console.log() output leaked into the driver's own JSON "
                "stdout channel — the sandboxed console is not a true "
                f"no-op. stdout: {probe_result.stdout!r}"
            ),
        )
        self.assertEqual(
            probe_result.dispatch_count,
            1,
            msg=(
                "console.log() output corrupted parsing of the captured "
                f"agent() dispatch (got {probe_result.dispatch_count}, "
                "expected 1) — the exact silent-corruption failure mode a "
                "leaking console causes."
            ),
        )

    def test_harness_exposes_no_module_loader_to_the_workflow_body(self):
        # covers: BP-1100b-4
        """A workflow body that attempts to reach a module loader or a
        filesystem primitive under the harness is refused exactly as the
        real engine refuses it — i.e. `require('fs')` throws a
        ReferenceError (require is not defined), not a successful import.
        """
        body = (
            "let __requireThrew__ = false;\n"
            "let __errorType__ = null;\n"
            "try {\n"
            "  require('fs');\n"
            "} catch (__e__) {\n"
            "  __requireThrew__ = true;\n"
            "  __errorType__ = __e__.constructor.name;\n"
            "}\n"
            "await agent('probe', { label: 'probe', requireThrew: __requireThrew__, "
            "errorType: __errorType__ });\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            script_path = _write_script(Path(tmp), body)
            result = run_workflow_under_e2(script_path, timeout=_TIMEOUT)

        self.assertEqual(
            result.error,
            "",
            msg=f"Harness itself errored (stderr: {result.stderr}): {result.error}",
        )
        self.assertEqual(result.dispatch_count, 1, msg=f"stderr: {result.stderr}")
        opts = result.agent_calls[0].opts

        self.assertTrue(
            opts.get("requireThrew"),
            msg=(
                "require('fs') did NOT throw inside the harness — the module loader "
                "is still reachable from the workflow body. The real E2 engine has no "
                f"`require` identifier in scope, so this must throw. opts: {opts}"
            ),
        )
        self.assertEqual(
            opts.get("errorType"),
            "ReferenceError",
            msg=(
                "require('fs') threw, but not the ReferenceError a real engine would "
                f"produce for an undefined identifier. Got: {opts.get('errorType')!r}. opts: {opts}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
