"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_unreferenced_and_switched_off.py
COVERS: BP-100n-4

GOAL: the two additional reported-verdict classes BP-100n-4's disk-side
    census introduces beyond the plain compared/registered counts: a script
    named by NO emitted entry line is reported UNREFERENCED and the run
    fails; a script named only by a registry entry carrying ``enabled:
    false`` is reported SWITCHED-OFF and does NOT by itself fail the run.
    Split out of test_bp_100n_4.py purely to keep that NEW file under
    check-file-size's absolute 400-counted-line cap for new files — see that
    module's own "SPLIT NOTE" paragraph for the full rationale and where its
    other test_spec descriptors landed.

LOAD-BEARING DESCRIPTOR: ``TestEveryUnreferencedScriptIsReportedAndFails``
    below is the AC's decisive anti-grep synthetic-unregistered-script
    injection test (test_spec 2) — it must survive here with its behaviour
    unchanged.

DEPENDENCY NOTE — imports, never copy-pastes, from the sibling: this module
    reuses the low-level git/registry/subprocess fixtures that already live
    in test_bp_100n_4.py (``_git``, ``_init_repo``, ``_commit_all``,
    ``_deploy_gate_dir_copy``, ``_run_reachability_hook``,
    ``_write_gate_script``, ``_FixtureRepoTestCase``, ``_RESULT_LINE_RE``,
    ``_REACHABILITY_HOOK_NAME``). Per this repo's Source-of-Truth Discipline
    (a duplicated helper is how two sibling files drift apart later), those
    are loaded via ``importlib`` under a private module name — mirroring
    this exact directory's own established convention for reusing another
    test file's internals read-only (see test_bp_100k_4_ii_registry_shapes.py
    and test_bp_100k_5_i.py / test_bp_100k_5.py's identical use of the same
    pattern) — rather than copy-pasted, so the two files cannot silently
    drift on what the fixture repo, the real gate-directory copy, or a
    reachability-hook invocation looks like.

RED BASELINE (expected): every test below is RED for the same reason
    test_bp_100n_4.py's are — the extended RESULT line fields and the
    UNREFERENCED/SWITCHED-OFF diagnostic lines do not exist yet.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BASE_MODULE_PATH = _THIS_DIR / "test_bp_100n_4.py"


def _load_base_module():
    """Load test_bp_100n_4.py under a private module name via importlib.

    Read-only reuse of that module's git/registry/subprocess fixtures.
    Loading it this way (rather than a package-qualified ``import``) mirrors
    this same directory's own established convention and never collides
    with pytest's own normal collection of test_bp_100n_4.py as its own
    test module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location("_bp100n4_base_unref_switched", _BASE_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_module()


# ---------------------------------------------------------------------------
# test_spec 2: every script named by no entry line is reported and fails.
# ---------------------------------------------------------------------------


class TestEveryUnreferencedScriptIsReportedAndFails(_base._FixtureRepoTestCase):
    def test_bp_100n_4_every_script_named_by_no_entry_line_is_reported_and_the_run_fails(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: criterion
        """Every script no entry line names is reported and the run fails.

        NOT asserted against today's raw unreferenced count on the real,
        live registry: BP-100n-4's own day-one-triage mandate means the
        real registry legitimately reaches unreferenced=0 once triage is
        complete — test_bp_100n_4.py's own deployed-copy test requires
        exactly that against the same real tree. A fixed ``> 0`` assertion
        here would falsify itself the moment triage succeeds (it has, as of
        this AC's own correction — see check_hook_trigger_reachability.py's
        DECISION HISTORY, unreferenced=0), so both descriptors cannot pass
        together against that shared reality.

        Instead this injects ONE synthetic, deliberately-unregistered
        ``check_*.py`` into this test's OWN fixture copy of the gate
        directory — mirroring TestAddedGateScriptRaisesComparedCount's own
        idiom in test_bp_100n_4.py — and asserts the PROPERTY: the census
        names that script on its own UNREFERENCED diagnostic line and the
        run fails. That holds regardless of how many other unreferenced
        scripts the real tree currently has (zero or more), so it is never
        falsified by correct, AC-mandated triage.
        """
        _base._write_gate_script(
            self.gate_dir / "check_bp_100n_4_defect1_unregistered_fixture.py"
        )

        result = _base._run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        match = _base._RESULT_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            "expected a RESULT line stating the unreferenced count; got: "
            f"{output!r}",
        )
        unreferenced_count = int(match.group(3))
        self.assertGreaterEqual(
            unreferenced_count,
            1,
            "the injected synthetic gate script names no registry entry "
            "line and must be counted as unreferenced",
        )
        self.assertIn(
            "UNREFERENCED: check_bp_100n_4_defect1_unregistered_fixture.py",
            output,
            "the injected synthetic script must be named, by path, on its "
            f"own UNREFERENCED diagnostic line; got: {output!r}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "a run that reports an unreferenced script must fail",
        )


# ---------------------------------------------------------------------------
# test_spec 4: a disabled entry is reported switched off, does not fail.
# ---------------------------------------------------------------------------


class TestDisabledEntryScriptReportedSwitchedOff(_base._FixtureRepoTestCase):
    def test_bp_100n_4_a_disabled_entry_is_reported_switched_off_and_does_not_fail_the_run(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: criterion
        """The real registry carries enabled:false entries (e.g.
        check_mermaid_drift.py under id check-mermaid-drift). A script named
        only by such an entry is reported as deliberately switched off —
        registered-and-off is a third state, distinct from invoked and from
        absent — and does not by itself fail the run.
        """
        result = _base._run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        self.assertRegex(
            output,
            r"SWITCHED-OFF:\s*\S*check_mermaid_drift\.py",
            "a script named only by a disabled registry entry must be "
            f"reported as deliberately switched off; got {output!r}",
        )


if __name__ == "__main__":
    unittest.main()
