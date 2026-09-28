#!/usr/bin/env python3
"""
MODULE: check_consumer_install
GOAL: Simulate a real consumer install of the leafcutter-ai package into an
    empty scratch project — run the real build.py against it and verify the
    deployed tree is complete and internally consistent.
BUSINESS CONTEXT: AC BP-900a..BP-900g verify deployment completeness
    *statically*, from inside the build. Nothing had verified it
    *empirically*, by performing an install and inspecting the result — the
    gap that let seven consumer-install defects (BP-900g-4/-5/-6, BP-015,
    BP-016, BP-017, BP-018) ship and get hotfixed after release between
    2026-08-13 and 2026-08-17 (AC BP-900h-1). This script is the CI-facing
    entry point that closes that gap: it drives a real ``build.py`` run into a
    genuinely empty scratch directory (never a copy of this repository, which
    would reintroduce the source-tree bias that hides missing-deploy defects)
    and then reuses the existing reference-resolution machinery against the
    deployed output.
ARCHITECTURE: A single CLI entry point (``main``) that composes five small,
    independently testable steps: (1) ``_ensure_scratch_environment`` creates
    ``--target-dir`` and seeds a minimal ``skills_config.json`` when absent;
    (2) ``_maybe_run_build`` shells out to ``<--package-dir>/scripts/build.py``
    unless ``--skip-build`` is given; (3) ``_verify_deployed_tree`` asserts the
    deployed output root contains ``scripts/`` and ``agents/``; (4)
    ``_check_unresolved_references`` imports
    ``build_referential_integrity.extract_compiled_script_path_refs`` and
    ``build_propagation_audit.build_broken_ref_report`` from
    ``--package-dir/scripts`` and reuses them, unmodified, against the
    deployed tree — per the ticket's Implementation Notes, this script does
    not reimplement the matching rules those modules already own; (5), only
    when ``--use-install`` is given, ``run_use_install_and_report`` (in the
    sibling module ``_use_install_step.py``, kept there to stay within this
    file's line-size budget and per BP-900h-6's "one entry point for the job
    and its test" it_requirement) drives a real ``git init`` + real
    ``pre-commit install`` + real ``git commit`` over the built tree and
    reports which guards the commit path actually executed — the "use it,
    don't just build it" half BP-900h-1..BP-900h-2 leave uncovered, since a
    guard only speaks when a commit is attempted. ``_maybe_probe_route_before_install``
    is a sixth small step (ACD-2100d-3): it takes the BEFORE route-start
    reading, or skips entirely when ``--skip-build`` means no installer runs
    in this invocation — see the ACD-2100d-3 EXTENSION note below.

ACD-2100d-3 EXTENSION: between step (1) and step (2) above, if
``target_dir/.leafcutter/workflows/plan-feature.js`` already exists (a
route deployed by some prior install, real or seeded), this script probes
it via ACD-2100d-1's shared ``unit_tests/_installed_route_probe.py``
harness for its BEFORE stopping point. After step (3) verifies the
deployed tree, the SAME target is probed again for its AFTER stopping
point, and a verdict comparing the two readings is printed: a project
that did not reach its first question BEFORE the install is reported
PRECONDITION NOT MET (exit 3, never a pass) regardless of the after
reading; one that reached it before but not after is reported a
route-start regression (exit 1) naming both readings; otherwise both
readings are printed and the pipeline continues. When no route is
deployed yet (a genuinely fresh scratch install), this whole check is
skipped — the existing empty-scratch-directory CI usage stays green.
This before/after measurement only runs when ``--skip-build`` is NOT
given: ACD-2100d-3's Given/When are both about an invocation that
actually runs the installer, and several already-`done` ACs
(BP-900h-1, BP-900h-6-i, BP-900h-6-ii) legitimately re-invoke this
script with ``--skip-build`` against a target_dir that already has a
deployed, non-git route, for purposes unrelated to route start (see
``main()``'s inline comment and pr-reviewer finding H-1, 2026-09-08).

Usage::

    python scripts/ci/check_consumer_install.py \\
        --package-dir <path-to-leafcutter-ai-checkout> \\
        --target-dir <scratch-dir> \\
        [--skip-build] [--use-install]

CI registration::

    # In your CI YAML (e.g. .github/workflows/ci.yml):
    - name: Consumer install simulation
      run: python leafcutter-ai/scripts/ci/check_consumer_install.py \\
             --package-dir leafcutter-ai --target-dir . --use-install

Exit codes:
    0 — build succeeded, deployed tree is complete, all references resolve,
        and (with --use-install) the adopter's first commit completed with a
        non-empty executed-guard record.
    1 — build.py exited non-zero, the deployed tree is missing scripts/ or
        agents/, one or more compiled-template script references do not
        resolve to a deployed file (unresolved paths are named on stderr),
        a route-start regression was found (ACD-2100d-3: the project
        reached its first startup question before the install but no
        longer does after it), or (with --use-install) the commit failed
        or its executed-guard record was empty.
    2 — usage/environment error (bad --package-dir, filesystem error, or the
        reference-resolution or shared installed-route-probe modules could
        not be imported).
    3 — ACD-2100d-3's Given precondition was not met: a route already
        deployed at --target-dir did not reach its first startup question
        BEFORE this run's own installer invocation, so no before/after
        comparison could be made. Never conflated with a pass (0) or a
        plain failure (1). Never produced when --skip-build is given (no
        installer runs in that invocation, so the before/after measurement
        does not apply — see the ACD-2100d-3 EXTENSION note above).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    # Guarantees the sibling module resolves for an import-based caller too,
    # not only under direct script execution (where the interpreter already
    # adds argv[0]'s directory to sys.path implicitly). See BP-900h-6-i
    # review finding (b): an unqualified `from _use_install_step import ...`
    # relies on that implicit script-execution behaviour and raises
    # ModuleNotFoundError for any caller that imports this module instead of
    # running it as __main__.
    sys.path.insert(0, str(_THIS_DIR))

from _route_start_regression_check import probe_route_before_install, verdict_after_install
from _use_install_step import check_target_entitlement, run_use_install_and_report

_MINIMAL_SKILLS_CONFIG: dict[str, str] = {
    "_comment": "Minimal config for consumer-install simulation (BP-900h-1).",
}


def _ensure_scratch_environment(target_dir: Path) -> int:
    """Create ``target_dir`` and seed a minimal skills_config.json if absent.

    Never clobbers a caller-supplied ``skills_config.json`` — only writes one
    when the file does not already exist.

    Args:
        target_dir: Scratch consumer-install directory to create/seed.

    Returns:
        0 on success, 2 on any filesystem error.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: could not create --target-dir {target_dir}: {exc}", file=sys.stderr)
        return 2

    config_path = target_dir / "skills_config.json"
    if config_path.exists():
        return 0

    try:
        config_path.write_text(json.dumps(_MINIMAL_SKILLS_CONFIG), encoding="utf-8")
    except OSError as exc:
        print(
            f"ERROR: could not write minimal skills_config.json to {config_path}: {exc}",
            file=sys.stderr,
        )
        return 2

    return 0


def _maybe_run_build(package_dir: Path, target_dir: Path, skip_build: bool) -> int:
    """Run ``build.py --target-dir <target_dir>`` unless ``skip_build`` is set.

    Args:
        package_dir: Path to the leafcutter-ai package checkout containing
            ``scripts/build.py``.
        target_dir: Scratch consumer-install directory to build into.
        skip_build: When true, skip invoking build.py entirely.

    Returns:
        0 on success (or when skipped), 1 when build.py exits non-zero
        (its combined stdout/stderr is printed to our stderr), 2 when the
        subprocess itself cannot be started.
    """
    if skip_build:
        return 0

    build_py = package_dir / "scripts" / "build.py"
    try:
        result = subprocess.run(
            [sys.executable, str(build_py), "--target-dir", str(target_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"ERROR: could not invoke build.py subprocess: {exc}", file=sys.stderr)
        return 2

    if result.returncode != 0:
        print(
            "CONSUMER INSTALL SIMULATION FAILED: build.py exited non-zero.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            file=sys.stderr,
        )
        return 1

    # Forward the underlying build's own stdout on success too (AC
    # INF-400c-4-v): a caller of this simulation must be able to see
    # per-build statements build.py itself makes (e.g. the knowledge-sink
    # declaration notice) rather than only ever seeing them on a failure
    # path, where they were already included above.
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")

    return 0


def _resolve_output_root(target_dir: Path) -> Path:
    """Resolve the deployed output root from ``target_dir/skills_config.json``.

    Reads the ``output_root`` key, defaulting to ``.leafcutter`` when the key
    is absent or the file cannot be parsed.

    Args:
        target_dir: Scratch consumer-install directory.

    Returns:
        The resolved output root path (``target_dir / output_root_name``).
    """
    config_path = target_dir / "skills_config.json"
    output_root_name = ".leafcutter"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"WARNING: could not parse {config_path}: {exc} — "
                "defaulting output_root to .leafcutter",
                file=sys.stderr,
            )
        else:
            output_root_name = data.get("output_root", ".leafcutter")
    return target_dir / output_root_name


def _verify_deployed_tree(target_dir: Path) -> tuple[Path, int]:
    """Verify the deployed output root contains ``scripts/`` and ``agents/``.

    Args:
        target_dir: Scratch consumer-install directory that was built into.

    Returns:
        A ``(output_root, code)`` pair: ``code`` is 0 on success, or 1 with
        the missing directory named on stderr.
    """
    output_root = _resolve_output_root(target_dir)

    if not output_root.is_dir():
        print(
            f"CONSUMER INSTALL SIMULATION FAILED: deployed output root missing: {output_root}",
            file=sys.stderr,
        )
        return output_root, 1

    for sub in ("scripts", "agents"):
        sub_dir = output_root / sub
        if not sub_dir.is_dir():
            print(
                f"CONSUMER INSTALL SIMULATION FAILED: missing deployed directory: {sub_dir}",
                file=sys.stderr,
            )
            return output_root, 1

    return output_root, 0


def _import_audit_modules(package_dir: Path) -> tuple[ModuleType, ModuleType]:
    """Import the existing reference-resolution modules from ``package_dir/scripts``.

    Reuses ``build_referential_integrity`` and ``build_propagation_audit``
    as-is (per the ticket's Implementation Notes — the matching rules are not
    reimplemented here).

    Args:
        package_dir: Path to the leafcutter-ai package checkout.

    Returns:
        A ``(build_referential_integrity, build_propagation_audit)`` module
        pair.

    Raises:
        ImportError: if either module cannot be imported.
    """
    scripts_dir = str(package_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import build_propagation_audit as bpa
    import build_referential_integrity as bri

    return bri, bpa


def _collect_deployed_scripts(scripts_dir: Path) -> set[str]:
    """Walk ``scripts_dir`` and return the set of deployed ``scripts/<relpath>`` strings.

    Args:
        scripts_dir: The deployed output root's ``scripts/`` directory.

    Returns:
        The set of deployed ``"scripts/<relpath>"`` strings.
    """
    deployed: set[str] = set()
    if not scripts_dir.is_dir():
        return deployed
    try:
        for script_file in scripts_dir.rglob("*.py"):
            deployed.add(f"scripts/{script_file.relative_to(scripts_dir).as_posix()}")
    except OSError as exc:
        print(
            f"ERROR: could not walk deployed scripts directory {scripts_dir}: {exc}",
            file=sys.stderr,
        )
        raise
    return deployed


def _check_unresolved_references(package_dir: Path, output_root: Path) -> int:
    """Reuse the BP-900b/BP-900c reference-resolution machinery against the deployed tree.

    Args:
        package_dir: Path to the leafcutter-ai package checkout.
        output_root: The deployed output root verified by
            ``_verify_deployed_tree``.

    Returns:
        0 when every compiled-template script reference resolves to a
        deployed file, 1 when unresolved references are found (each named on
        stderr), 2 on an environment error (e.g. the audit modules cannot be
        imported, or the deployed scripts directory cannot be walked).
    """
    try:
        bri, bpa = _import_audit_modules(package_dir)
    except ImportError as exc:
        print(
            f"ERROR: could not import reference-resolution modules from {package_dir}: {exc}",
            file=sys.stderr,
        )
        return 2

    refs = bri.extract_compiled_script_path_refs(output_root)
    refs_to_sources: dict[str, set[str]] = {}
    for template_path, script_path in refs:
        refs_to_sources.setdefault(script_path, set()).add(template_path)

    try:
        deployed_scripts = _collect_deployed_scripts(output_root / "scripts")
    except OSError:
        return 2

    broken = bpa.build_broken_ref_report(refs_to_sources, deployed_scripts)
    if not broken:
        return 0

    print(
        f"CONSUMER INSTALL SIMULATION FAILED: {len(broken)} unresolved script reference(s).",
        file=sys.stderr,
    )
    for entry in broken:
        referencing = ", ".join(entry.referencing_templates)
        print(
            f"  MISSING: {entry.missing_path} — referenced by: {referencing} "
            f"— suggested action: {entry.suggested_action}",
            file=sys.stderr,
        )
    return 1


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        required=True,
        help="Path to a leafcutter-ai package checkout containing scripts/build.py.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        required=True,
        help="Scratch consumer-install directory. Created if absent.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help=(
            "Skip invoking build.py and only run the reference-resolution "
            "check against an already-deployed tree."
        ),
    )
    parser.add_argument(
        "--use-install",
        action="store_true",
        help=(
            "After building and verifying the deployed tree, git-init the "
            "install, stage an ordinary adopter change, and attempt a real "
            "commit through the ordinary commit path (BP-900h-6). Reports "
            "an 'EXECUTED GUARDS:' line naming every guard the commit path "
            "itself reported as having run."
        ),
    )
    return parser


def _maybe_probe_route_before_install(
    skip_build: bool, package_dir: Path, target_dir: Path
) -> tuple[str | None, ModuleType | None, int | None]:
    """Take ACD-2100d-3's BEFORE route-start reading, unless this invocation
    will not actually run the installer.

    ACD-2100d-3's Given is "a run reaches the first question ... BEFORE the
    installer is run" and its When is "the current installer is run against
    that project" -- both presuppose an invocation that actually installs.
    ``skip_build`` means no installer runs in THIS invocation at all, so
    there is no before/after pair to measure: the "before" and "after"
    states would be the same, unchanged, already-deployed tree. Several
    already-``done`` ACs (BP-900h-1, BP-900h-6-i, BP-900h-6-ii) legitimately
    re-invoke this script with ``--skip-build`` against a ``target_dir``
    that already carries a deployed, non-git route, for purposes unrelated
    to route-start regression (re-checking references, exercising the
    use-install commit path). Probing route start there manufactured a
    false PRECONDITION NOT MET, because the real ``plan-feature.js``'s
    repository-resolution pre-flight halts on any target without git
    ancestry -- an artifact of these callers' own git-init timing, not a
    genuine before/after regression. See pr-reviewer finding H-1,
    2026-09-08.

    Args:
        skip_build: The parsed ``--skip-build`` flag.
        package_dir: Path to the leafcutter-ai package checkout.
        target_dir: Scratch consumer-install directory to probe.

    Returns:
        A ``(before_stopping_point, probe_module, error_code)`` triple.
        ``error_code`` is ``None`` on success (including the skipped case,
        where the other two members are also ``None``), or 2 when the
        shared installed-route probe cannot be imported.
    """
    if skip_build:
        return None, None, None
    try:
        before_stopping_point, probe_module = probe_route_before_install(package_dir, target_dir)
    except ImportError as exc:
        print(f"ERROR: could not import shared installed-route probe: {exc}", file=sys.stderr)
        return None, None, 2
    return before_stopping_point, probe_module, None


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Command-line arguments (excluding argv[0]), or ``None`` to use
            ``sys.argv[1:]``.

    Returns:
        An exit code — see this module's own "Exit codes" docstring section
        above (0 = OK, 1 = simulation failed, 2 = usage/environment error,
        3 = ACD-2100d-3 precondition not met).
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    package_dir: Path = args.package_dir.resolve()
    target_dir: Path = args.target_dir.resolve()

    if not (package_dir / "scripts" / "build.py").exists():
        print(
            f"ERROR: --package-dir {package_dir} does not contain scripts/build.py",
            file=sys.stderr,
        )
        return 2

    if args.use_install and target_dir.exists():
        # Entitlement (BP-900h-6-i) must be checked BEFORE any mutation at
        # all — including the scratch-environment bootstrap below, which
        # writes a skills_config.json into target_dir when one is absent.
        # Skipped when target_dir does not exist yet: a not-yet-created
        # directory holds nothing a census could catch as mutated, and
        # run_use_install_and_report re-checks entitlement once the
        # directory exists, later in this same flow.
        entitlement_violation = check_target_entitlement(target_dir)
        if entitlement_violation is not None:
            print(
                f"CONSUMER INSTALL SIMULATION REFUSED: target {target_dir} is not "
                f"entitled to the use-install step's destructive actions: "
                f"{entitlement_violation}.",
                file=sys.stderr,
            )
            return 1

    setup_code = _ensure_scratch_environment(target_dir)
    if setup_code != 0:
        return setup_code

    before_stopping_point, probe_module, probe_error_code = _maybe_probe_route_before_install(
        args.skip_build, package_dir, target_dir
    )
    if probe_error_code is not None:
        return probe_error_code

    build_code = _maybe_run_build(package_dir, target_dir, args.skip_build)
    if build_code != 0:
        return build_code

    output_root, tree_code = _verify_deployed_tree(target_dir)
    if tree_code != 0:
        return tree_code

    if before_stopping_point is not None:
        try:
            message, verdict_code = verdict_after_install(before_stopping_point, probe_module, target_dir)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: after-install route-start probe failed: {exc}", file=sys.stderr)
            return 2
        if verdict_code != 0:
            print(message, file=sys.stderr)
            return verdict_code
        print(message)

    refs_code = _check_unresolved_references(package_dir, output_root)
    if refs_code != 0:
        return refs_code

    if args.use_install:
        use_install_code = run_use_install_and_report(target_dir)
        if use_install_code != 0:
            return use_install_code

    print(f"CONSUMER INSTALL SIMULATION OK: deployed output root at {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [python-coder/EPIC-DeploymentCompleteness/12_BP-900h-1]: Created
#   scripts/ci/check_consumer_install.py to close the empirical-install gap
#   identified in the ticket: BP-900a..BP-900g verify deployment completeness
#   statically, from inside the build, but nothing had performed a real
#   install into a genuinely empty scratch project and inspected the result.
#   Composed of four small steps (scratch-env setup, build invocation,
#   deployed-tree shape check, reference-resolution check) so each is
#   independently testable and main() stays low-complexity. The
#   reference-resolution check reuses
#   build_referential_integrity.extract_compiled_script_path_refs() and
#   build_propagation_audit.build_broken_ref_report() unmodified (per the
#   ticket's Implementation Notes) rather than reimplementing the matching
#   rules BP-900b-1/BP-900c-1 already built. (#EPIC-DeploymentCompleteness/12)
# - 2026-09-07 [python-coder]: _maybe_run_build now forwards the underlying
#   build.py subprocess's own stdout on the SUCCESS path too (previously only
#   surfaced on failure, inside the FAILED message) -- needed so a caller of
#   this simulation can see per-build statements build.py itself prints (e.g.
#   the knowledge-sink declaration NOTE), not only ever on a failing run.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-v)
# - 2026-09-08 [python-coder/EPIC-StartingNewWorkTheProperWayAlways/22]: Wired
#   ACD-2100d-3's before/after route-start regression check into this
#   ALREADY-GATED entry point rather than adding a second script, per the
#   ticket's own "wire into the gate that already runs" instruction, and
#   reused ACD-2100d-1's shared unit_tests/_installed_route_probe.py harness
#   as-is rather than duplicating it. Probes target_dir's pre-existing
#   deployed route (if any) before _maybe_run_build() runs, then probes the
#   same target again after _verify_deployed_tree() succeeds, and reports a
#   verdict distinguishing precondition-not-met (exit 3, before never
#   reached the first question) from a route-start regression (exit 1,
#   before did but after does not) from a pass (exit 0, both readings
#   printed). A fresh scratch install with nothing yet deployed skips the
#   whole check (before/probe_module stay None) so the existing
#   empty-scratch-directory CI usage is unaffected.
#   (#EPIC-StartingNewWorkTheProperWayAlways/22)
# - 2026-09-09 [python-coder/EPIC-StartingNewWorkTheProperWayAlways/22,
#   regression fix]: pr-reviewer's H-1 finding (2026-09-08 16:32) reproduced a
#   regression on 5 pre-existing, already-`done` AC tests sharing this entry
#   point (BP-900h-1's test_consumer_simulation_detects_unresolved_reference;
#   BP-900h-6-i's test_bp900h6i_an_entitled_disposable_target_still_completes;
#   BP-900h-6-ii's three accounting tests): each re-invokes this script with
#   --skip-build against a target_dir that already has a deployed, non-git
#   route, for purposes unrelated to route-start (reference-checking,
#   use-install accounting). The route-start probe fired anyway, and the
#   REAL plan-feature.js's repository-resolution pre-flight halts on any
#   target without git ancestry, so `before` read `halted:error` and every
#   one of these invocations was misreported PRECONDITION NOT MET (exit 3)
#   before its own actual check ever ran. Fix: gate the whole before/after
#   route-start measurement on `not args.skip_build` — ACD-2100d-3's Given
#   ("a run reaches the first question ... BEFORE the installer is run") and
#   When ("the current installer is run") both presuppose an invocation that
#   actually installs; --skip-build means no installer runs in THIS
#   invocation, so there is no before/after pair to measure at all. The real
#   CI job (.github/workflows/ci.yml) never passes --skip-build, so this
#   ticket's own guarantee is unaffected for the invocation it actually
#   gates. Verified: all 4 of this ticket's own tests
#   (unit_tests/portability/test_acd_2100d_3.py — none of which use
#   --skip-build) remain green; all 5 previously-regressed tests are green
#   again; full unit_tests/portability/ suite: 86 passed (was 81 passed / 5
#   failed before this fix), under AC_ENFORCE_STRICT=1.
#   (#EPIC-StartingNewWorkTheProperWayAlways/22)
# ====================================================================
