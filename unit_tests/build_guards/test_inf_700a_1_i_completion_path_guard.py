"""
MODULE: test_inf_700a_1_i_completion_path_guard
GOAL: Failing (RED) test baseline for INF-700a-1-i's build-time guard — a
    real completion-path-wiring reachability GUARD, modelled directly on
    scripts/build_phases.py's check_command_reachability (see
    unit_tests/build_guards/test_command_reachability_guard.py for the
    precedent this module mirrors).

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1-i.yaml

Per this AC's it_requirements:
  - "THE MECHANISM THAT FAILS ... A BUILD-TIME GUARD INVOKED FROM build.py,
    with the same shape and the same abort semantics as the existing
    _check_command_reachability_guard."
  - "THE ENUMERATION DERIVES FROM THE ARTEFACTS; ONLY THE EXCLUSIONS ARE
    HAND-WRITTEN. The guard globs templates/workflows-js/*.js for the
    candidate set and checks each against the config's two lists."
  - "WHERE THE LIST LIVES — a new top-level section in
    config/guardrail_gates.yaml, carrying wired paths and excluded paths,
    each exclusion with a reason and the path whose routing step covers its
    emissions instead."
  - "THE GUARD IS ALSO TESTED THROUGH ITS OWN ENTRY POINT, in
    unit_tests/build_guards/ alongside test_command_reachability_guard.py,
    with a positive run and a must-block negative run."

NOTE: every test in THIS module calls check_knowledge_routing_wiring()
directly as a Python import -- unit coverage of the pure function only. The
"tested through its own entry point" subprocess coverage above (positive run
+ must-block negative run, reached via build.py's real main()) lives in the
sibling module unit_tests/build_guards/test_inf_700a_1_i_reachability.py,
split out to keep both files under the check-file-size 400-line limit.

Detector seam
-------------
The unit tests are written against a pure function with this signature (to be
added to scripts/build_phases.py by python-coder):

    def check_knowledge_routing_wiring(
        workflows_dir: Path, guardrail_config: dict
    ) -> dict:
        '''Enumerate every *.js file directly under workflows_dir and check
        each against guardrail_config["knowledge_routing_wiring"]["wired"]
        and ["excluded"] (a list of {"path": ..., "reason": ..., ...}).

        Returns a dict:
            {
                "examined": [<file names examined>],
                "unwired": [<file names neither wired nor excluded>],
            }

        A non-empty "unwired" list is the build-failing condition (mirrors
        check_command_reachability's "ok iff empty verdicts" contract).
        '''

Wiring contract (build.py must honour): after the deploy phases run, build.py
must call check_knowledge_routing_wiring(...) against the real
templates/workflows-js/ directory and config/guardrail_gates.yaml's new
section, and abort the build (non-zero exit) when "unwired" is non-empty —
mirroring _check_command_reachability_guard's existing wiring in build.py's
main().
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_WORKFLOWS_DIR = _REPO_ROOT / "templates" / "workflows-js"
_GUARDRAIL_CONFIG_PATH = _REPO_ROOT / "config" / "guardrail_gates.yaml"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from build_phases import check_knowledge_routing_wiring as _CHECK  # noqa: E402
except ImportError:
    _CHECK = None  # type: ignore[assignment]


class _CheckerMissing(ImportError):
    """Raised when check_knowledge_routing_wiring is not yet in build_phases."""

    def __init__(self) -> None:
        super().__init__(
            "check_knowledge_routing_wiring not found in build_phases — "
            "python-coder must implement this function (INF-700a-1-i guardrail)"
        )


def _require_checker():
    if _CHECK is None:
        raise _CheckerMissing()
    return _CHECK


def _make_workflows_dir(tmp_path: Path, filenames: list[str]) -> Path:
    workflows_dir = tmp_path / "workflows-js"
    workflows_dir.mkdir(parents=True)
    for name in filenames:
        (workflows_dir / name).write_text(f"// synthetic: {name}\n", encoding="utf-8")
    return workflows_dir


class TestGuardDerivesCandidateSetFromArtefacts:
    """INF-700a-1-i: 'run the guard against the real templates/workflows-js/
    directory and assert it reports having examined every .js file present
    there, by count and by name' — the anti-vacuous-pass check."""

    def test_the_guard_derives_its_candidate_set_from_the_workflow_artefacts(self):
        # covers: INF-700a-1-i
        # angle: real_artifact
        check_knowledge_routing_wiring = _require_checker()

        real_js_names = sorted(p.name for p in _WORKFLOWS_DIR.glob("*.js"))
        assert real_js_names, (
            f"Sanity check failed: no .js files found under {_WORKFLOWS_DIR} — "
            "the fixture this test depends on (a non-empty real workflows-js "
            "directory) is not present."
        )

        result = check_knowledge_routing_wiring(_WORKFLOWS_DIR, {})

        examined = sorted(result.get("examined", []))
        assert examined == real_js_names, (
            "The guard must report having examined EVERY .js file present "
            "under templates/workflows-js/ by name — a guard whose candidate "
            "set comes from its config would report only the names already "
            f"listed there. Real files: {real_js_names}. Examined: {examined}"
        )


class TestNewCompletionPathWithNeitherWiringNorExclusionBlocks:
    """INF-700a-1-i's last clause: a workflow artefact added later that
    completes a unit of work without either harvesting or being listed as
    excluded is detected — 'something fails when it appears'."""

    def test_a_new_completion_path_with_neither_wiring_nor_an_exclusion_is_reported(
        self, tmp_path
    ):
        # covers: INF-700a-1-i
        # angle: failure
        check_knowledge_routing_wiring = _require_checker()

        workflows_dir = _make_workflows_dir(
            tmp_path, ["fast-lane-ship.js", "new-unlisted-driver.js"]
        )
        guardrail_config = {
            "knowledge_routing_wiring": {
                "wired": ["fast-lane-ship.js"],
                "excluded": [],
            }
        }

        result = check_knowledge_routing_wiring(workflows_dir, guardrail_config)

        unwired = result.get("unwired", [])
        assert "new-unlisted-driver.js" in unwired, (
            "A .js artefact under templates/workflows-js/ that is neither in "
            "the 'wired' list nor the 'excluded' list must be reported as "
            f"unwired. Got: {result}"
        )
        assert "fast-lane-ship.js" not in unwired, (
            f"A correctly wired artefact must not be reported as unwired. Got: {result}"
        )


class TestExclusionListSuppressesAFalsePositive:
    """A path deliberately not given a routing step (per INF-700a-1-i's
    'named as excluded ... together with the reason') must NOT be reported
    as unwired."""

    def test_an_excluded_path_is_not_reported_as_unwired(self, tmp_path):
        # covers: INF-700a-1-i
        # angle: boundary
        check_knowledge_routing_wiring = _require_checker()

        workflows_dir = _make_workflows_dir(
            tmp_path, ["fast-lane-ship.js", "build-feature.js"]
        )
        guardrail_config = {
            "knowledge_routing_wiring": {
                "wired": ["fast-lane-ship.js"],
                "excluded": [
                    {
                        "path": "build-feature.js",
                        "reason": (
                            "user-facing entry point that resolves to "
                            "build-epic or build-ticket; completes nothing "
                            "itself."
                        ),
                        "covered_by": "build-epic.js / build-ticket.js",
                    }
                ],
            }
        }

        result = check_knowledge_routing_wiring(workflows_dir, guardrail_config)

        assert "build-feature.js" not in result.get("unwired", []), (
            "A path explicitly excluded, with a reason, must not be reported "
            f"as unwired. Got: {result}"
        )


class TestWiringOnlyOnePathStillReportsAllOthers:
    """INF-700a-1-i's predicted partial-wiring failure: a guard that reports
    only the FIRST missing path lets a fixer close them one build at a time
    without ever seeing the scale."""

    def test_wiring_only_one_path_reports_every_other_unwired_path(self, tmp_path):
        # covers: INF-700a-1-i
        # angle: failure
        check_knowledge_routing_wiring = _require_checker()

        all_five = [
            "build-epic.js",
            "build-ticket.js",
            "fast-lane-ship.js",
            "quick-fix.js",
            "finalize-feature.js",
        ]
        workflows_dir = _make_workflows_dir(tmp_path, all_five)
        guardrail_config = {
            "knowledge_routing_wiring": {
                "wired": ["build-epic.js"],
                "excluded": [],
            }
        }

        result = check_knowledge_routing_wiring(workflows_dir, guardrail_config)

        unwired = set(result.get("unwired", []))
        expected_unwired = set(all_five) - {"build-epic.js"}
        assert unwired == expected_unwired, (
            "With only one of five paths wired, the guard must report ALL "
            f"four remaining paths as unwired — not just the first. "
            f"Expected: {sorted(expected_unwired)}. Got: {sorted(unwired)}"
        )


class TestRealDeployedGuardrailConfigHasTheNewSection:
    """A companion real-artifact check: the actual config/guardrail_gates.yaml
    on disk must eventually carry the new 'knowledge_routing_wiring' section
    naming all five completion paths as wired or excluded (with reasons)."""

    def test_real_guardrail_config_declares_all_five_completion_paths(self):
        # covers: INF-700a-1-i
        # angle: real_artifact
        import yaml  # noqa: PLC0415

        check_knowledge_routing_wiring = _require_checker()

        assert _GUARDRAIL_CONFIG_PATH.is_file(), (
            f"Expected {_GUARDRAIL_CONFIG_PATH} to exist."
        )
        config = yaml.safe_load(_GUARDRAIL_CONFIG_PATH.read_text(encoding="utf-8"))

        result = check_knowledge_routing_wiring(_WORKFLOWS_DIR, config)
        unwired = result.get("unwired", [])
        assert not unwired, (
            "The real, deployed config/guardrail_gates.yaml must name every "
            "real .js file under templates/workflows-js/ as either wired or "
            f"excluded (with a reason). Currently unwired: {unwired}"
        )


if __name__ == "__main__":
    import pytest  # noqa: PLC0415

    raise SystemExit(pytest.main([__file__, "-v"]))
