"""
MODULE: unit_tests/commit_guardian/test_bp_100k_4_ii_registry_shapes.py
COVERS: BP-100k-4-ii

GOAL: SCRIPT-keyed half of test_bp_100k_4_ii.py's H-1 registry-shape
    regression guard (test_spec 10), split into this sibling module purely
    to keep test_bp_100k_4_ii.py's line count from growing further past
    check-file-size's ratchet limit (BP-100n-4) — see that module's own
    docstring "SPLIT NOTE" paragraph for the full rationale.

BACKGROUND: BP-100n-4-i widened the SAME
    ``hook_trigger_reachability_exemption_registry`` registry key that
    BP-100k-4-ii's H-1 fix already reads to also carry SCRIPT-keyed
    declared-non-gate / withheld-broken-gate records (``{"script": ...,
    "ground": ...}``) alongside the original ID-keyed, registered-gate
    exemption shape (``{"id": ..., "ground": ...}``). The two shapes are
    consumed by two DIFFERENT code paths:

      - id-keyed entries name a real, registered ``hooks_manifest.hooks``
        gate — ``evaluate_gate`` classifies it EXEMPT. That half stays in
        test_bp_100k_4_ii.py (``TestEveryRealExemptionRegistryEntryStaysExemptOnZeroMatch``).
      - script-keyed entries name a script that is NOT in hooks_manifest at
        all — a declared non-gate / withheld-broken-gate record consumed by
        the BP-100n-4 DISK-side census (``_hook_trigger_census.py``'s
        ``validate_non_gate_records`` / ``report_unreferenced_and_
        switched_off``), a wholly separate feature from ``evaluate_gate``.
        THIS module holds that half.

    This module also carries the load-bearing property the original
    combined test enumerated the registry for: a THIRD, unrecognised entry
    shape (neither ``id`` nor ``script``) fails LOUDLY in setUp rather than
    being silently skipped — a bare ``if "id" in entry`` filter would
    silently narrow coverage back to a known shape the moment a novel shape
    appears, restoring exactly the staleness this guard exists to prevent.
    That property now lives solely here (test_bp_100k_4_ii.py's own
    id-keyed test no longer re-asserts it), which is sufficient: the
    registry is enumerated once, in one place, at run time.

DEPENDENCY NOTE — imports, never copy-pastes, from the sibling: this module
    needs several low-level fixtures that already live in
    test_bp_100k_4_ii.py (git repo helpers, the real-registry loaders, the
    reachability-hook subprocess runner, the source-tree hook path). Per
    this repo's Source-of-Truth Discipline (a duplicated helper is how two
    sibling files drift apart later), those are loaded via ``importlib``
    under a private module name — mirroring this exact codebase's own
    established convention for reusing another test file's internals
    read-only (see test_bp_100k_4_ii.py's own
    ``_load_build_synthetic_full_package``, and test_bp_100k_5_i.py /
    test_bp_100k_5.py's identical use of the same pattern) — rather than
    copy-pasted, so the two files cannot silently drift on what a real
    exemption-registry entry, a real hooks_manifest entry, or a reachability
    -hook invocation looks like.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BASE_MODULE_PATH = _THIS_DIR / "test_bp_100k_4_ii.py"

# Captures (script, ground) pairs from "DECLARED-NON-GATE: <script>
# ground=<text>" lines (BP-100n-4-i's disk-side census -- see
# _hook_trigger_census.py). A script-keyed
# hook_trigger_reachability_exemption_registry entry is a declared-non-gate
# record consumed by the DISK census, not an EXEMPT hooks_manifest verdict,
# so it needs its own line pattern rather than reusing an EXEMPT regex.
_DECLARED_NON_GATE_LINE_RE = re.compile(r"DECLARED-NON-GATE:\s*(\S+)\s+ground=(.*)")
# Captures the script name from "UNREFERENCED: <script> reason=<text>" lines
# (also _hook_trigger_census.py). Used to prove a script-keyed non-gate
# record is never left in the failing UNREFERENCED class.
_UNREFERENCED_LINE_RE = re.compile(r"UNREFERENCED:\s*(\S+)")
# Test-only override name that turns on the BP-100n-4 disk-side census and
# redirects it to a directory other than the running script's own (mirrors
# HOOK_TEST_CONFIG's convention; see _hook_trigger_census.py's
# census_is_enabled / resolve_gate_dir). Production code never sets this.
_HOOK_TEST_GATE_DIR_ENV_VAR = "HOOK_TEST_GATE_DIR"


def _load_base_module():
    """Load test_bp_100k_4_ii.py under a private module name via importlib.

    Read-only reuse of that module's git/registry/subprocess fixtures.
    Loading it this way (rather than a package-qualified ``import``) mirrors
    this same directory's own established convention and never collides
    with pytest's own normal collection of test_bp_100k_4_ii.py as its own
    test module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k4ii_registry_shapes_base", _BASE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_module()


class TestEveryRealScriptKeyedNonGateRecordIsDeclaredNotUnreferenced(unittest.TestCase):
    """SCRIPT-keyed half of the H-1 registry-shape regression guard. See
    test_bp_100k_4_ii.py's ``TestEveryRealExemptionRegistryEntryStaysExemptOnZeroMatch``
    for the ID-keyed half and this module's own docstring for the full
    split rationale.

    Enumerates the real ``hook_trigger_reachability_exemption_registry`` at
    run time (never a hardcoded list) and fails LOUDLY on any entry whose
    shape is neither ``id``- nor ``script``-keyed — the load-bearing
    property that stops this guard's own shape-recognition rule from going
    stale a second time.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _base._init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _base._add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        registry = _base._load_real_registry()
        real_hooks = _base._real_hooks_manifest_hooks(registry)
        exemption_entries = _base._real_exemption_entries(registry)
        self.assertGreater(
            len(exemption_entries),
            0,
            msg=(
                "setup bug / vacuous-test guard: the real "
                "hook_trigger_reachability_exemption_registry is empty — "
                "this test would trivially pass over zero entries"
            ),
        )

        self.id_keyed_ids: list[str] = []
        self.script_keyed_scripts: list[str] = []
        for entry in exemption_entries:
            if not isinstance(entry, dict):
                self.fail(
                    "unrecognised hook_trigger_reachability_exemption_registry "
                    f"entry: not a dict at all: {entry!r}"
                )
            elif "id" in entry:
                self.id_keyed_ids.append(entry["id"])
            elif "script" in entry:
                self.script_keyed_scripts.append(entry["script"])
            else:
                self.fail(
                    "unrecognised hook_trigger_reachability_exemption_registry "
                    f"entry shape (neither 'id' nor 'script' present): {entry!r} "
                    "— this test enumerates the registry at run time "
                    "specifically so a novel entry shape cannot go unnoticed; "
                    "add explicit handling for it in this test rather than "
                    "silently skipping or narrowing coverage back to a known shape"
                )

        self.assertGreater(
            len(self.script_keyed_scripts),
            0,
            msg="setup bug / vacuous-test guard: zero script-keyed exemption entries found",
        )

        entries_under_test = [_base._find_hook_entry(real_hooks, gid) for gid in self.id_keyed_ids]
        self.config_path = _write_full_registry_config(entries_under_test, exemption_entries)
        self.addCleanup(os.unlink, self.config_path)

        # Script-keyed non-gate records are exercised through the DISK
        # census, a wholly different feature (BP-100n-4) from the
        # hooks_manifest EXEMPT verdict above: a fixture gate directory
        # holding one dummy check_*.py per script-keyed entry, with the
        # disk census switched on and pointed at it via HOOK_TEST_GATE_DIR.
        # None of these dummy scripts is named on any hooks_manifest entry
        # line above, so each must come back DECLARED-NON-GATE.
        self.gate_dir = self.repo / "gate_scripts_fixture"
        self.gate_dir.mkdir()
        for script in self.script_keyed_scripts:
            (self.gate_dir / script).write_text(
                "#!/usr/bin/env python3\nimport sys\n\nsys.exit(0)\n", encoding="utf-8"
            )

    def test_every_real_script_keyed_non_gate_record_is_declared_not_unreferenced(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        """Script-keyed records are declared-non-gate / withheld-broken-gate
        entries in the SAME registry key BP-100n-4-i introduced — a
        different shape from the id-keyed, registered-gate exemption
        BP-100k-4-ii's own H-1 fix targets. They are consumed by the
        BP-100n-4 disk census, not by ``evaluate_gate``'s EXEMPT verdict, so
        this asserts the DECLARED-NON-GATE observable, never EXEMPT, and
        never UNREFERENCED (which would fail the run)."""
        result = _base._run_reachability_hook(
            _base._REACHABILITY_HOOK_SRC,
            self.repo,
            self.config_path,
            extra_env={_HOOK_TEST_GATE_DIR_ENV_VAR: str(self.gate_dir)},
        )
        combined = result.stdout + result.stderr

        declared_pairs = dict(_DECLARED_NON_GATE_LINE_RE.findall(combined))
        unreferenced_scripts = set(_UNREFERENCED_LINE_RE.findall(combined))

        for script in self.script_keyed_scripts:
            self.assertIn(
                script,
                declared_pairs,
                msg=(
                    f"{script} carries a real, grounded script-keyed "
                    "declared-non-gate record and is not invoked by any "
                    "hooks_manifest entry line in this fixture — it must be "
                    f"reported DECLARED-NON-GATE. Output:\n{combined}"
                ),
            )
            self.assertNotIn(
                script,
                unreferenced_scripts,
                msg=(
                    f"{script} must never be reported UNREFERENCED — it is "
                    f"a declared non-gate, not an unrecognised script. Output:\n{combined}"
                ),
            )


def _write_full_registry_config(entries_under_test: list[dict], exemption_entries: list[dict]) -> str:
    """Write the exact same HOOK_TEST_CONFIG shape the original (pre-split)
    combined test wrote: the id-keyed hooks_manifest entries plus the FULL
    exemption registry (both id- and script-keyed entries), via the real
    JSON serializer.

    Args:
        entries_under_test: Real hooks_manifest entries for the id-keyed ids.
        exemption_entries: The full, real exemption registry (both shapes).

    Returns:
        Absolute path to the temp JSON file written.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "hooks_manifest": {"hooks": entries_under_test},
                "hook_trigger_reachability_exemption_registry": exemption_entries,
            },
            f,
        )
    return path


if __name__ == "__main__":
    unittest.main()
