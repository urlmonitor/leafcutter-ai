"""
MODULE: scripts/commit_guardian/check_reachability.py
GOAL: Enforce the forward direction of the runtime-reachability guard
    (BO-2900b-1): every capability a command surface's BUILT argparse parser
    registers must have at least one real automation invocation naming it, or
    the change is refused. Two modes mirror the proven check_done_proof.py
    two-layer precedent: ``--mode precommit`` (fast, staged-change loop) and
    ``--mode ci`` (authoritative backstop, catches ``--no-verify`` commits and
    hook-config-less worktrees).
BUSINESS CONTEXT: A registered command-surface action (an argparse
    subcommand) that nothing in the build pipeline ever runs is dead surface
    -- exactly the BO-2400f lifecycle-function shape (claim_build_set,
    release_claim) this guard family exists to catch before it strands again.
    REFUSES, NOT WARNS: a finding is a non-zero exit, never a downgraded
    advisory; the only sanctioned relief is a recorded exemption (BO-2900d-1),
    consulted directly by this module's own finding computation via
    _reachability_inventory.load_exemptions()/exemptions_in_force()/
    is_exempt() -- there is no separate wiring step. An exemption's ``item``
    is matched as ``f"{surface_label}:{capability}"`` (the exact
    ``--surface`` ``MODULE_PATH`` text joined to the capability name), and
    only an in-force entry (non-empty ``reason``) suppresses a finding; a
    reasonless entry grants nothing (BO-2900d-1-i). This module's own output
    never names its own bypass (no ``SKIP=`` / ``--no-verify`` text).
ARCHITECTURE: registered_capabilities()/collected_invocations() are NOT
    redefined here -- both live in the shared seam
    _reachability_inventory.py (see that module's docstring); this module is
    the CLI/orchestration layer on top of it.

    ``--surface MODULE_PATH:BUILDER`` (repeatable): a filesystem path to a
    .py file and the name of a zero-arg callable in it that returns a built
    ``argparse.ArgumentParser`` (mirrors
    scripts/build_orchestration/fast_lane.py's own ``_build_cli_parser()``
    convention, imported there from _fl_cli.py). Importing the module never
    executes its ``main()`` -- only the named builder is called. Defaults to
    ``scripts/build_orchestration/fast_lane.py:_build_cli_parser`` when
    omitted (the minimum surface BO-2900b-1's own constraints name; the full
    derived multi-surface set is BO-2900c-4's scope, not this AC's).

    ``--automation SCRIPT_PATH`` (repeatable): an automation script to scan
    via _reachability_inventory.collected_invocations(). NO DEFAULT is
    derived here (BO-2900c-4 owns deriving the real automation-script set).
    ROLLOUT NOTE: when no ``--automation`` is supplied at all, this run has
    nothing to compare the built surface against -- that is reported as
    "nothing to check yet" (exit 0, a stderr note naming why), never as
    "every capability is uncalled". The distinction matters because this
    repository's real automation (templates/workflows-js/fast-lane-ship.js)
    is JavaScript, and collected_invocations() does not yet parse JavaScript
    command construction (BO-2900b-3's scope) -- until that lands, a
    default that silently ran the real surface against zero recognised
    invocations would refuse every commit and PR touching
    scripts/build_orchestration/ or templates/workflows-js/, which is not
    this AC's contract (its own Gherkin and fixtures test the refusal
    against a supplied, deterministic set, never the real evolving repo).
    An explicitly-supplied empty automation set is impossible to express via
    a repeated ``--automation`` flag (absence and "supplied but empty" are
    the same argparse state here), so this is the one safe reading.

    Error handling: surface loading (import + builder call) is wrapped and
    converted to SurfaceLoadError (Rule 1/3) -- an arbitrary surface module's
    import-time code can raise anything, and it must degrade to a reported,
    fail-closed finding rather than a hook crash. Pre-commit fail-open: the
    ``if __name__ == '__main__'`` guard exits 0 on a genuinely unexpected
    error so a crash in this script never blocks an unrelated commit.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

# Sibling imports below (_reachability_inventory, _resolve_root) assume this
# script's own directory is on sys.path -- true when run_hook.py dispatches
# this script directly (its own working-directory convention), but NOT when
# this module is imported package-qualified as
# scripts.commit_guardian.check_reachability (this AC's own test suite's
# import style). Self-heal here so both invocation shapes resolve identically
# -- the same deliberate idiom ruff.toml's E402 exclusion documents for this
# whole package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _reachability_inventory import (  # noqa: E402
    REGISTRY_RELATIVE_PATH,
    ReachabilityRegistryError,
    collected_invocations,
    is_exempt,
    load_exemptions,
    registered_capabilities,
)
from _resolve_root import find_project_root  # noqa: E402

# BO-2900b-1's own constraint: "at minimum it must include
# scripts/build_orchestration/fast_lane.py". The full derived surface set is
# BO-2900c-4's scope.
_DEFAULT_SURFACE_MODULE = Path("scripts") / "build_orchestration" / "fast_lane.py"
_DEFAULT_SURFACE_BUILDER = "_build_cli_parser"

# Exactly two entries, per this AC's own config_schema_fragment
# (``uncalled_capability_finding.ways_forward``) -- BO-2900b-1-i pins this to
# exactly these two and forbids naming a skip/bypass mechanism.
_WAYS_FORWARD = (
    "add the automation invocation in this change",
    "record an exemption for the capability with a stated reason",
)


class SurfaceLoadError(Exception):
    """Raised when a --surface spec cannot be parsed, imported, or built.

    Deliberately distinct from "the built parser registers zero
    capabilities" -- BO-2900c-4 depends on this seam signalling "could not
    be established" as an outcome separate from "established and empty".
    """


def _import_module_from_path(module_path: Path) -> ModuleType:
    """Import *module_path* as a standalone module, without executing its main().

    Inserts the module's own parent directory onto ``sys.path`` for the
    duration of the import (removed again afterwards) so a surface module's
    own sibling-relative imports -- e.g. fast_lane.py's
    ``from _fl_cli import _build_cli_parser`` -- resolve exactly as they do
    when the surface is run directly.

    Args:
        module_path: Filesystem path to the ``.py`` file to import.

    Returns:
        The imported module object.

    Raises:
        SurfaceLoadError: *module_path* does not exist, cannot be turned
            into an import spec, or raises anything at all while its
            top-level code executes (an arbitrary surface module's
            module-level code can raise anything; per BO-2900c-4's
            sandboxing constraint this must degrade to a reported finding,
            never a hook crash).
    """
    if not module_path.is_file():
        raise SurfaceLoadError(f"surface module not found: {module_path}")  # noqa: TRY003
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise SurfaceLoadError(f"cannot build an import spec for {module_path}")  # noqa: TRY003
    module = importlib.util.module_from_spec(spec)
    parent_dir = str(module_path.resolve().parent)
    inserted = parent_dir not in sys.path
    if inserted:
        sys.path.insert(0, parent_dir)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 -- an arbitrary surface module's
        # import-time code can raise anything at all; it must degrade to a
        # reported SurfaceLoadError, never crash this hook (BO-2900c-4's own
        # sandboxing constraint on this same import step).
        raise SurfaceLoadError(  # noqa: TRY003
            f"cannot import surface module {module_path}: {exc}"
        ) from exc
    finally:
        if inserted:
            sys.path.remove(parent_dir)
    return module


def _load_surface(spec: str) -> tuple[argparse.ArgumentParser, str]:
    """Load and build the parser named by a ``MODULE_PATH:BUILDER`` spec.

    Args:
        spec: ``"<path to .py file>:<zero-arg parser-builder function name>"``.

    Returns:
        ``(built_parser, module_path_str)`` -- *module_path_str* is the exact
        path text from *spec*, used verbatim as the "surface" label in
        findings (naming the surface the capability is registered on, per
        this AC's Gherkin).

    Raises:
        SurfaceLoadError: *spec* is malformed, the module cannot be
            imported, the named builder is missing/not callable, or it does
            not return an ``argparse.ArgumentParser``.
    """
    module_path_str, sep, builder_name = spec.rpartition(":")
    if not sep or not module_path_str or not builder_name:
        raise SurfaceLoadError(  # noqa: TRY003
            f"invalid --surface spec (expected MODULE_PATH:BUILDER): {spec!r}"
        )
    module = _import_module_from_path(Path(module_path_str))
    builder = getattr(module, builder_name, None)
    if builder is None or not callable(builder):
        raise SurfaceLoadError(  # noqa: TRY003
            f"surface module {module_path_str} has no callable {builder_name!r}"
        )
    parser = builder()
    if not isinstance(parser, argparse.ArgumentParser):
        raise SurfaceLoadError(  # noqa: TRY003
            f"{module_path_str}:{builder_name} did not return an argparse.ArgumentParser"
        )
    return parser, module_path_str


def _load_exemptions_for_run(project_root: Path) -> list[dict]:
    """Load recorded reachability exemptions for this run, degrading safely.

    The only sanctioned relief from a refusal (this AC's own constraints):
    a recorded, reasoned exemption in ``config/reachability_exemptions.yaml``
    (BO-2900d-1), read via the shared ``_reachability_inventory`` seam so
    this guard and BO-2900d-1's own no-way-in gate can never disagree about
    what is recorded.

    Args:
        project_root: Project root containing the exemption registry.

    Returns:
        Exemptions as returned by ``load_exemptions``, or an empty list when
        the registry cannot be read/parsed. Fail-closed with respect to
        relief: a corrupt registry must never be silently treated as
        blanket exemption -- it is treated as granting none, so findings it
        would otherwise have suppressed are still reported.
    """
    registry_path = project_root / REGISTRY_RELATIVE_PATH
    try:
        return load_exemptions(registry_path)
    except ReachabilityRegistryError as exc:
        print(f"[check-reachability] WARNING: {exc}", file=sys.stderr)
        return []


def _default_surface_specs(project_root: Path) -> list[str]:
    """Return the default ``--surface`` spec list when none is supplied on the CLI.

    Args:
        project_root: Absolute project root, used to build an absolute
            default surface path.

    Returns:
        A single-entry list naming
        ``scripts/build_orchestration/fast_lane.py:_build_cli_parser`` -- the
        minimum surface this AC's own constraints require.
    """
    return [f"{project_root / _DEFAULT_SURFACE_MODULE}:{_DEFAULT_SURFACE_BUILDER}"]


def _format_finding(capability: str, surface: str) -> str:
    """Render one uncalled_capability_finding as a single printable line.

    Args:
        capability: The registered-but-uncalled capability name.
        surface: The surface label the capability is registered on.

    Returns:
        A line naming the capability, the surface, and both ways forward --
        never a skip flag or ``--no-verify`` (BO-2900e-1 final clause).
    """
    ways = "; ".join(f"({i + 1}) {way}" for i, way in enumerate(_WAYS_FORWARD))
    return (
        f"[check-reachability] uncalled_capability: capability '{capability}' "
        f"registered on surface {surface} is never invoked by any automation. "
        f"Ways forward: {ways}."
    )


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the check_reachability CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Reachability guard, forward direction (BO-2900b-1): every "
            "capability a command surface's BUILT parser registers must "
            "have at least one automation invocation naming it, or the "
            "change is refused."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["precommit", "ci"],
        default="precommit",
        help="Operating mode (both currently share the same check; kept for "
        "parity with check_done_proof.py's two-layer registration shape).",
    )
    parser.add_argument(
        "--surface",
        action="append",
        metavar="MODULE_PATH:BUILDER",
        help=(
            "Repeatable. A command surface to inventory, as "
            "'<path to .py file>:<zero-arg parser-builder function name>'. "
            "Defaults to scripts/build_orchestration/fast_lane.py:"
            "_build_cli_parser when omitted."
        ),
    )
    parser.add_argument(
        "--automation",
        action="append",
        metavar="SCRIPT_PATH",
        help=(
            "Repeatable. An automation script to scan for capability "
            "invocations. No default is derived (see module docstring's "
            "ROLLOUT NOTE): omitting this entirely means nothing is checked "
            "this run, not that every capability is uncalled."
        ),
    )
    return parser


def _findings_for_surface(
    spec: str, called_capabilities: set[str], exemptions: list[dict]
) -> tuple[list[tuple[str, str]], str | None]:
    """Evaluate one surface spec against the already-collected called-capability set.

    Args:
        spec: A ``--surface`` spec string.
        called_capabilities: Capability names collected from automation.
        exemptions: Raw exemption entries, as returned by
            ``_load_exemptions_for_run`` -- an in-force entry (non-empty
            ``reason``) whose ``item`` exactly matches
            ``f"{surface_label}:{capability}"`` suppresses that capability's
            finding; a reasonless entry grants nothing (BO-2900d-1-i).

    Returns:
        ``(findings, load_error)`` -- *findings* is a list of
        ``(capability, surface_label)`` pairs for capabilities registered on
        this surface, not in *called_capabilities*, and not exempt;
        *load_error* is ``None`` on success or the surface's load-failure
        message otherwise (in which case *findings* is always empty).
    """
    try:
        surface_parser, surface_label = _load_surface(spec)
    except SurfaceLoadError as exc:
        return [], f"cannot load surface {spec}: {exc}"
    capabilities = registered_capabilities(surface_parser)
    findings = [
        (capability, surface_label)
        for capability in sorted(capabilities)
        if capability not in called_capabilities
        and not is_exempt(f"{surface_label}:{capability}", exemptions)
    ]
    return findings, None


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the forward reachability guard.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        0 when every registered capability across every evaluated surface
        has at least one collected invocation or an in-force exemption (or
        when no ``--automation`` was supplied at all -- nothing to check
        yet, see module docstring); 1 when at least one capability is found
        uncalled and not exempt, or a surface could not be loaded at all
        (fail-closed).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = find_project_root()

    surface_specs = args.surface if args.surface else _default_surface_specs(project_root)
    automation_paths = [Path(p) for p in args.automation] if args.automation else []

    if not automation_paths:
        print(
            "[check-reachability] no --automation scripts supplied and "
            "automatic derivation of the repository's automation-script set "
            "is not yet implemented (BO-2900c-4); nothing to check this run.",
            file=sys.stderr,
        )
        return 0

    called_capabilities = {
        invocation.capability for invocation in collected_invocations(automation_paths)
    }
    exemptions = _load_exemptions_for_run(project_root)

    all_findings: list[tuple[str, str]] = []
    for spec in surface_specs:
        findings, load_error = _findings_for_surface(spec, called_capabilities, exemptions)
        if load_error is not None:
            print(f"[check-reachability] {load_error}", file=sys.stderr)
            return 1
        all_findings.extend(findings)

    for capability, surface_label in all_findings:
        print(_format_finding(capability, surface_label))

    return 1 if all_findings else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"[check-reachability] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)
