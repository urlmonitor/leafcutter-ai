"""
MODULE: test_inf_700a_1_i_reachability
GOAL: Reach INF-700a-1-i's build-time knowledge-routing-wiring guard through
    build.py's REAL entry point (subprocess), not through a direct Python
    import of check_knowledge_routing_wiring(). Split out of the sibling
    module test_inf_700a_1_i_completion_path_guard.py to keep both files
    under the check-file-size 400-content-line limit for new files (the
    module-split pattern documented for build_phases.py / build_helpers.py).

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1-i.yaml

BUSINESS CONTEXT (H-2, pr-reviewer finding, 2026-09-14): every test in the
    sibling module calls check_knowledge_routing_wiring() directly as a
    Python import -- valid unit coverage of the pure function, but none of
    it proves build.py's main() actually calls the function and aborts the
    build. That is exactly the failure this AC's own test_rationale names:
    "a guard that exists, is tested in isolation, and is never reached from
    the deployed entry point" -- the done_proof.py defect this repository
    has already shipped once (cited in this AC's it_requirements #66). The
    sibling module this AC explicitly models itself on,
    test_command_reachability_guard.py, proves reachability the same way:
    by running the real build.py as a subprocess and asserting on its exit
    code.

ARCHITECTURE: The guard's candidate set is deliberately read from
    PACKAGE_ROOT (the real package SOURCE tree, resolved from build.py's own
    ``__file__`` -- see scripts/build.py's own
    ``_check_knowledge_routing_wiring_guard`` docstring), never from the
    deployed output_root. So a test that wants to inject an unlisted
    workflow artefact, or edit the wired/excluded declaration, cannot do so
    by mutating the deployed target directory (as
    test_command_reachability_guard.py's own subprocess tests do for THEIR
    guard, whose candidate set IS read from the deployed tree) -- it must
    mutate a copy of the SOURCE tree instead, and run build.py from that
    copy so PACKAGE_ROOT resolves to it. ``_copy_synthetic_package()``
    follows the established precedent for exactly this shape:
    unit_tests/build_guards/test_bp_100k_2.py's
    ``_build_synthetic_full_package()``.

test_spec descriptors covered here (see the AC's own test_spec block):
    - test_a_new_completion_path_with_neither_wiring_nor_an_exclusion_blocks_the_build
    - test_removing_a_path_from_the_exclusion_list_makes_the_guard_block
    - test_a_passing_guard_run_states_which_artefact_kinds_it_cannot_see
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCS_PRODUCT_TRUTH_SRC = _REPO_ROOT / "docs" / "product-truth"

# Real subprocess builds of build.py routinely take 60-90s against this
# repo's full template/skill/hook corpus (confirmed empirically, 2026-09-14)
# -- generous per the existing precedent this module follows
# (test_command_reachability_guard.py uses a 180s ceiling).
_SUBPROCESS_TIMEOUT_SECONDS = 240


def _copy_synthetic_package(workspace: Path) -> Path:
    """Copy templates/, scripts/, config/ (and docs/product-truth/, which
    build_product_truth declares as a source outside those three trees) into
    a synthetic package root under ``workspace``.

    Mirrors the self-hosting production layout
    (``pkg_root.parent == target_dir`` passed to ``build.py``), so a test can
    mutate the COPY (add an unlisted templates/workflows-js/*.js file, or
    edit config/guardrail_gates.yaml's knowledge_routing_wiring section) and
    run the real build.py against it, without ever touching this repo's own
    source tree.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_REPO_ROOT / "templates", pkg_root / "templates", ignore=ignore)
    shutil.copytree(_REPO_ROOT / "scripts", pkg_root / "scripts", ignore=ignore)
    shutil.copytree(_REPO_ROOT / "config", pkg_root / "config", ignore=ignore)
    if _DOCS_PRODUCT_TRUTH_SRC.is_dir():
        shutil.copytree(
            _DOCS_PRODUCT_TRUTH_SRC,
            pkg_root / "docs" / "product-truth",
            ignore=ignore,
        )
    return pkg_root


def _run_build(pkg_root: Path, target_dir: Path) -> subprocess.CompletedProcess:
    """Run the real ``<pkg_root>/scripts/build.py`` as a subprocess against
    ``target_dir``, with workflows enabled (mirrors
    test_command_reachability_guard.py's own real-build invocations)."""
    config_path = target_dir.parent / "skills_config.json"
    config_path.write_text(
        json.dumps({"workflows": {"enabled": True}}), encoding="utf-8"
    )
    return subprocess.run(
        [
            sys.executable,
            str(pkg_root / "scripts" / "build.py"),
            "--target-dir",
            str(target_dir),
            "--config",
            str(config_path),
            "--self-description-enforcement",
            "warning",
        ],
        cwd=str(pkg_root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestNewCompletionPathBlocksTheBuildThroughTheRealEntryPoint:
    """INF-700a-1-i test_spec:
    test_a_new_completion_path_with_neither_wiring_nor_an_exclusion_blocks_the_build.

    surface_invoked: "the guard invoked from build.py through its real entry
    point, run as a subprocess against a temp target". The sibling module's
    direct-call test (TestNewCompletionPathWithNeitherWiringNorExclusionBlocks)
    already proves check_knowledge_routing_wiring() itself reports the
    unlisted artefact; this test proves build.py's main() actually consumes
    that result and aborts -- the reachability gap H-2 identified.
    """

    def test_a_new_completion_path_with_neither_wiring_nor_an_exclusion_blocks_the_build(
        self, tmp_path
    ):
        # covers: INF-700a-1-i
        # angle: reachability
        pkg_root = _copy_synthetic_package(tmp_path)
        new_artefact = (
            pkg_root / "templates" / "workflows-js" / "new-unlisted-driver.js"
        )
        new_artefact.write_text(
            "// synthetic: a completion path with neither wiring nor an "
            "exclusion\n",
            encoding="utf-8",
        )

        target_dir = tmp_path / "deploy_target"
        result = _run_build(pkg_root, target_dir)

        assert result.returncode != 0, (
            "build.py must exit non-zero when a real "
            "templates/workflows-js/*.js artefact is neither listed under "
            "knowledge_routing_wiring.wired nor .excluded. A guard that "
            "reports the problem via check_knowledge_routing_wiring() but is "
            "never reached from main() would leave this at exit 0 -- exactly "
            "the reachability gap this test exists to catch.\n"
            f"returncode: {result.returncode}\n"
            f"stdout (last 1000): {result.stdout[-1000:]}\n"
            f"stderr (last 1000): {result.stderr[-1000:]}"
        )
        combined = result.stdout + result.stderr
        assert "new-unlisted-driver.js" in combined, (
            "The build's failure output must name the new, unlisted "
            f"artefact. Output (last 1500): {combined[-1500:]}"
        )


class TestRemovingAnExclusionEntryMakesTheGuardBlockThroughTheRealEntryPoint:
    """INF-700a-1-i test_spec:
    test_removing_a_path_from_the_exclusion_list_makes_the_guard_block.

    This descriptor was missing entirely (under any name) from the RED
    baseline this pair of modules shipped -- H-2's second finding. Deleting
    one excluded entry from the real config/guardrail_gates.yaml's
    knowledge_routing_wiring.excluded list must make the real build.py
    abort, naming that path -- proving the guard reads the single declared
    list rather than embedding a second, independently-hardcoded copy that
    could silently drift from it.
    """

    def test_removing_a_path_from_the_exclusion_list_makes_the_guard_block(
        self, tmp_path
    ):
        # covers: INF-700a-1-i
        # angle: seam
        pkg_root = _copy_synthetic_package(tmp_path)
        config_path = pkg_root / "config" / "guardrail_gates.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        section = config["knowledge_routing_wiring"]
        excluded = section.get("excluded", [])
        target_path = "build-ticket.js"
        assert any(e.get("path") == target_path for e in excluded), (
            f"Sanity check failed: {target_path!r} is not currently in "
            "knowledge_routing_wiring.excluded in the real "
            f"config/guardrail_gates.yaml -- this test's premise (removing "
            f"an existing exclusion) does not hold. Excluded: {excluded}"
        )
        section["excluded"] = [e for e in excluded if e.get("path") != target_path]
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )

        target_dir = tmp_path / "deploy_target"
        result = _run_build(pkg_root, target_dir)

        assert result.returncode != 0, (
            f"Removing {target_path!r} from knowledge_routing_wiring.excluded "
            "(while it remains absent from .wired too) must make build.py "
            "abort -- proving the guard reads THIS single declared list "
            "artefact rather than a second copy that could drift from it.\n"
            f"returncode: {result.returncode}\n"
            f"stdout (last 1000): {result.stdout[-1000:]}\n"
            f"stderr (last 1000): {result.stderr[-1000:]}"
        )
        combined = result.stdout + result.stderr
        assert target_path in combined, (
            "The build's failure output must name the now-unwired path. "
            f"Output (last 1500): {combined[-1500:]}"
        )


class TestPassingGuardRunDisclosesExaminedAndUnreachableArtefactKinds:
    """INF-700a-1-i test_spec:
    test_a_passing_guard_run_states_which_artefact_kinds_it_cannot_see.

    H-1 (pr-reviewer finding, 2026-09-14): the AC's residual clause requires
    the guard to say, IN ITS OWN OUTPUT AND ON A PASSING RUN, which artefact
    kind it examined (workflow, via templates/workflows-js/*.js) and which
    kinds it structurally cannot see (a completion path shipped only as a
    skill or only as a command carries no workflow artefact for this guard's
    glob to enumerate) -- so a reader of a green build cannot conclude every
    future way of completing work is covered. Runs the real, currently
    fully-wired repo (no injected artefact) so the run is genuinely a PASS.
    """

    def test_a_passing_guard_run_states_which_artefact_kinds_it_cannot_see(
        self, tmp_path
    ):
        # covers: INF-700a-1-i
        # angle: criterion
        target_dir = tmp_path / "deploy_target"
        result = _run_build(_REPO_ROOT, target_dir)

        assert result.returncode == 0, (
            "Sanity check failed: the real, fully-wired repo must build "
            "cleanly (exit 0) before this test can assert on its PASSING "
            f"disclosure output.\n"
            f"stdout (last 1000): {result.stdout[-1000:]}\n"
            f"stderr (last 1000): {result.stderr[-1000:]}"
        )
        combined = result.stdout + result.stderr
        assert "workflow" in combined and "templates/workflows-js" in combined, (
            "A passing run must name the artefact kind it examined "
            "(workflow, via templates/workflows-js/*.js) in its own output. "
            f"Output (last 2000): {combined[-2000:]}"
        )
        assert "skill" in combined and "command" in combined, (
            "A passing run must ALSO name the artefact kinds it "
            "structurally cannot see (a completion path shipped only as a "
            "skill or only as a command carries no workflow artefact) -- a "
            "limitation disclosed only in a failure message is invisible to "
            "every reader who sees a green build, which is every reader "
            f"who matters here. Output (last 2000): {combined[-2000:]}"
        )


if __name__ == "__main__":
    import pytest  # noqa: PLC0415

    raise SystemExit(pytest.main([__file__, "-v"]))
