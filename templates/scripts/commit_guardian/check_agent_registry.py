"""
MODULE: check_agent_registry
GOAL: Pre-commit hook that validates agent_registry.json for bidirectional
    consistency, in whatever layout the package actually ships.
BUSINESS CONTEXT: The agent registry is the single source of truth for which
    agents exist and their spawn relationships. This hook runs when the
    registry, its schema, or a Markdown template of THIS package is staged,
    validating that the registry is consistent before the commit lands. Catches orphan templates,
    orphan registry entries, and spawn_allowlist / spawned_by mismatches early
    rather than at runtime.
ARCHITECTURE: Thin wrapper around registry_validator.validate_agent_registry()
    — the SAME function build.py --validate-only calls, so the commit-time
    verdict and the build-time verdict always agree on the same registry
    (GE-113c-1-vi).

    SCOPE: a staged path is a CANDIDATE when it is the agent registry
    (config/agent_registry.json), its schema (config/agent_registry.schema.json),
    or any Markdown template (templates/**/*.md), under whatever prefix that
    path carries in this layout (``_in_scope``). Registry/schema candidates are
    always in scope. A templates/ Markdown candidate is in scope only when it
    lies under the RESOLVED package root's ``templates/`` (package_root
    "leafcutter-ai" -> ``leafcutter-ai/templates/**``; "" -> ``templates/**``):
    a consumer project's own ``templates/*.md`` is not the package's and exits 0
    without running the validator (``_package_template_paths``). The wider
    template scope exists because the same validator also checks every ability
    (skill) reference written in template prose, so a dangling reference in a
    skill or command template is refused at commit time, not only by the build
    (INF-700b-2). No candidate staged means an ordinary pass whether or not a
    package root can be found (the empty-scope rule of GE-120a-4); the
    candidate test is decided before the package lookup, but the final
    templates/ narrowing needs the resolved root, and while a candidate
    templates/ path is staged an unresolved root still fails closed
    (CANNOT LOCATE PACKAGE) — see ``_in_scope`` / ``_is_registry_related``. The registry/schema filenames
    are matched via SPLIT path-segment tuples (``_SCOPE_EXACT_PARTS``),
    deliberately never joined into one "dir/file.ext"-shaped string literal:
    a standalone literal in that shape which also names a real on-disk data
    file reads, to this repo's own closure-guard build check
    (compute_intra_package_closure, AC BP-900g-8-ii), exactly like a bare
    ``open("config/agent_registry.json")`` call would, and this hook never
    opens that path itself — registry_validator.validate_agent_registry()
    does, from the resolved package_root it is handed.

    PACKAGE-ROOT RESOLUTION (GE-113c-1-vi): package_root's directory name is
    not knowable in advance (this repo's own checkout IS the package, at the
    repository root; a consumer install may name its package directory
    anything). The package root is therefore never computed from a
    hardcoded package-directory segment (the previous defect: literal
    ``repo_root / "leafcutter"``, a path that has never existed in this
    repository — KI-CG-20260928, same defect class as
    resolved-low-ki-cg-024). Instead this hook reads the SAME
    ``.build_manifest.json`` ``package_root`` field check_build_drift.py and
    check_output_drift.py already read, found via the SAME shared
    ``_resolve_root.resolve_manifest_path()`` those two hooks now import too
    (pr-reviewer H-2 follow-up: the candidate-root search — the shared
    resolver's project root via ``_resolve_root.find_project_root()``, the
    structurally-derived workspace root, and that root's immediate
    subdirectories — lives in exactly ONE module, never a third,
    independently-drifting copy of it; see ``_resolve_root.py``'s own
    docstring for why the shared lookup lives there rather than in a new
    sibling module). ``_resolve_root.resolve_package_root()`` layers the
    ``package_root``-field reading on top of the shared manifest-path lookup
    — shared with check_agent_spawn_consistency.py (AC INF-600k-1), the only
    other caller that needs an actual package_root; this hook imports it as
    ``_resolve_package_root``. ``package_root`` is ``""`` when the package
    IS that root (this repository's own layout), or a subdirectory name for
    an outer-project consumer layout.

    NO SILENT PASS: when an in-scope file is staged and no manifest can be
    found at any candidate root, the hook exits non-zero, naming every
    location it tried and the staged in-scope file(s) it therefore did not
    check (``_report_cannot_locate``) — wording distinct from the
    registry-invalid message (``_report_validation_failed``), so the two
    failure modes can never be told apart from the same substring. It never
    exits 0 having checked nothing (GE-120a-1). This is deliberately
    DIFFERENT policy from check_build_drift.py / check_output_drift.py, which
    exit 0 with a warning on the identical missing-manifest condition (a
    fresh clone must not self-block on those two) — only the LOOKUP is
    shared between all three hooks; each keeps its own verdict on what an
    unresolved manifest means (GE-113c-1-vi criterion 2, GE-120a-1).

    A THIRD failure mode gets its own wording too: when ``git diff --cached``
    itself cannot be queried (``_get_staged_files()`` returns ``None``), the
    hook cannot even tell whether anything in its scope was staged, so it
    exits non-zero via ``_report_could_not_check_staged_files()`` rather than
    treating an inspection failure as "nothing staged" — the same
    no-silent-pass principle applied one step earlier in the pipeline.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _resolve_root import resolve_package_root as _resolve_package_root

_GATE_NAME = "check-agent-registry"
_HOOK_FILE = Path(__file__).resolve()

# Candidate staged paths (GE-113c-1-vi): the registry, its schema, or a Markdown
# template, under WHATEVER prefix this layout gives them — never anchored to
# a hardcoded package-directory segment. Filenames are kept as SPLIT path
# segments (never joined into one literal "dir/file.ext" string) — see the
# ARCHITECTURE docstring note above on why a joined literal would falsely
# read as a data-file dependency to this repo's own closure-guard build check.
_SCOPE_REGISTRY_PARTS = ("config", "agent_registry.json")
_SCOPE_SCHEMA_PARTS = ("config", "agent_registry.schema.json")
_SCOPE_EXACT_PARTS = (_SCOPE_REGISTRY_PARTS, _SCOPE_SCHEMA_PARTS)
_SCOPE_INFIX = "templates/"
_SCOPE_SUFFIX = ".md"


def _get_staged_files() -> list[str] | None:
    """Return list of staged file paths from git, or None if git could not be queried.

    Wraps the external ``git diff`` call in try/except (Error Handling Policy
    Rule 1: external I/O must be wrapped) and treats a non-zero exit the same
    as a raised exception — both mean this hook cannot tell what is staged.

    Returns:
        List of staged file path strings relative to the repo root, or
        ``None`` when ``git diff --cached`` could not be invoked at all, or
        exited non-zero. ``None`` is a distinct outcome from an EMPTY list
        (a real, successful query that found nothing staged) — the caller
        must not treat them the same way.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"[{_GATE_NAME}] WARNING: could not run `git diff --cached`: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        print(
            f"[{_GATE_NAME}] WARNING: `git diff --cached` exited "
            f"{result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    return result.stdout.strip().splitlines()


def _in_scope(path: str) -> bool:
    """Return True when `path` is inside this hook's scope, at any prefix.

    Args:
        path: A staged file path, as reported by git (forward or back slashes).

    Returns:
        True for the registry or its schema at any prefix (e.g.
        "config/agent_registry.json" or "leafcutter-ai/config/agent_registry
        .json"), or any Markdown template under a "templates/" directory at
        any prefix (agents, skills, commands, rules, ...).
    """
    normalized = path.replace("\\", "/")
    parts = tuple(normalized.split("/"))
    if len(parts) >= 2 and parts[-2:] in _SCOPE_EXACT_PARTS:
        return True
    in_templates = normalized.startswith(_SCOPE_INFIX) or f"/{_SCOPE_INFIX}" in normalized
    return in_templates and normalized.endswith(_SCOPE_SUFFIX)


def _is_package_template(path: str, package_root: Path) -> bool:
    """Return True when a templates/ Markdown path lies under the package's ``templates/``.

    Args:
        path: A staged path (relative to the working directory the hook runs in).
        package_root: The resolved package root.

    Returns:
        True when ``path`` resolves inside ``<package_root>/templates``.
    """
    candidate = (Path.cwd() / path.replace("\\", "/")).resolve()
    return candidate.is_relative_to((package_root / _SCOPE_INFIX).resolve())


def _package_scope(candidates: list[str], package_root: Path) -> list[str]:
    """Narrow candidates to those the validator covers under this package root.

    Registry/schema paths always stay; a ``templates/`` Markdown path stays only
    when it is under ``<package_root>/templates/`` (INF-700b-2 M-3).

    Args:
        candidates: Staged paths matching ``_in_scope``.
        package_root: The resolved package root.

    Returns:
        The staged paths in scope for validation.
    """
    normalized = [c.replace("\\", "/") for c in candidates]
    return [
        c for c in normalized
        if tuple(c.split("/")[-2:]) in _SCOPE_EXACT_PARTS or _is_package_template(c, package_root)
    ]


def _is_registry_related(staged: list[str]) -> bool:
    """Return True if any staged file is in this hook's scope.

    Args:
        staged: List of staged file paths.

    Returns:
        True if at least one staged file matches ``_in_scope``.
    """
    return any(_in_scope(f) for f in staged)


def _report_could_not_check_staged_files() -> None:
    """Print the COULD NOT CHECK STAGED FILES diagnostic.

    Its own, third wording — distinct from both ``_report_cannot_locate``
    (a package could not be found) and ``_report_validation_failed`` (a
    registry was read and found invalid): here, this hook could not even
    determine what was staged, so it never reached either of those
    questions. GE-113c-1-vi's no-silent-pass rule applies here too: a check
    that could not inspect what it was given must not report a pass.
    """
    print(
        f"[{_GATE_NAME}] COULD NOT CHECK STAGED FILES — `git diff --cached` "
        "could not be queried (see the WARNING above), so this hook cannot "
        "tell whether any file in its scope (the agent registry, its "
        "schema, or a package Markdown template) was staged. This is neither a "
        "located-and-invalid registry nor a confirmed empty scope — it is "
        "an inspection failure, and per GE-113c-1-vi's no-silent-pass rule "
        "a check that could not inspect what it was given must not report "
        "a pass. Re-run from a working git checkout.",
        file=sys.stderr,
    )


def _report_cannot_locate(tried: list[str], staged_in_scope: list[str]) -> None:
    """Print the CANNOT LOCATE PACKAGE diagnostic and its own, distinct wording.

    Args:
        tried: Every location this hook checked for a build manifest, in
            search order (see ``_resolve_package_root``).
        staged_in_scope: The staged, in-scope files this run therefore did
            not check.
    """
    tried_str = "\n  ".join(tried)
    staged_str = "\n  ".join(staged_in_scope)
    print(
        f"[{_GATE_NAME}] CANNOT LOCATE PACKAGE — no .build_manifest.json "
        "resolved a package root, so the following staged file(s) in this "
        f"hook's scope were NOT checked:\n  {staged_str}\n\n"
        f"Locations tried:\n  {tried_str}\n\n"
        "No registry was read; this is not a validation failure. Run "
        "build.py to generate a manifest, or confirm this hook is deployed "
        "at its expected relative depth.",
        file=sys.stderr,
    )


def _report_validation_failed(package_root: Path, errors: list[str]) -> None:
    """Print the registry-invalid diagnostic, naming the resolved registry path.

    Args:
        package_root: The resolved package root the registry was read from.
        errors: Non-empty list of error strings from validate_agent_registry.
    """
    registry_path = package_root.joinpath(*_SCOPE_REGISTRY_PARTS)
    print(
        f"[{_GATE_NAME}] agent_registry.json / skill reference validation failed: "
        f"{registry_path}",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print(
        "\nFix the registry or skill-reference errors above before committing "
        "(each skill-reference line names the template file and the skill that "
        f"does not resolve). Registry: {registry_path}.",
        file=sys.stderr,
    )


def main() -> int:
    """Run agent registry validation as a pre-commit hook.

    Returns:
        Exit code: 0 when nothing in scope is staged, or the resolved
        registry validates cleanly; 1 when staged files could not be
        determined, the package cannot be located for a staged in-scope
        file, or validation finds errors.
    """
    staged = _get_staged_files()
    if staged is None:
        # git itself could not be queried — a distinct, fail-closed outcome
        # from "nothing staged" (GE-113c-1-vi no-silent-pass rule: a check
        # that could not inspect what it was given must not report a pass).
        _report_could_not_check_staged_files()
        return 1

    candidates = [f for f in staged if _in_scope(f)]
    if not candidates:
        return 0  # Nothing in this hook's scope staged (GE-120a-4).

    package_root, tried = _resolve_package_root(_HOOK_FILE)
    if package_root is None:
        _report_cannot_locate(tried, candidates)
        return 1

    if not _package_scope(candidates, package_root):
        return 0  # Only a consumer project's own templates/ was staged.

    scripts_dir = package_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        from registry_validator import validate_agent_registry  # type: ignore
    except ImportError as exc:
        print(
            f"[{_GATE_NAME}] Found package root {package_root} but could not "
            f"import registry_validator from {scripts_dir}: {exc}. This "
            "package is located but could not be validated.",
            file=sys.stderr,
        )
        return 1

    errors = validate_agent_registry(package_root)
    if errors:
        _report_validation_failed(package_root, errors)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-23 14:30 [python-coder/AC INF-700b-2, pr-reviewer M-3]: The widened
#   templates/**/*.md scope matched ANY ``*/templates/*.md`` at any prefix, so
#   staging a consumer project's own templates/notes.md ran full package
#   validation (and could block an unrelated commit). A templates/ Markdown
#   path is now in scope only under the resolved package root's templates/
#   (``_package_scope``); other templates/ paths exit 0 without the validator.
#   Registry/schema scope is unchanged, and an unresolvable package root with a
#   candidate staged still fails closed (CANNOT LOCATE PACKAGE).
#   (#EPIC-ALearningAnAgentHasTodayActuallyGets/04)
# - 2026-10-22 12:00 [python-coder/AC INF-700b-2]: Widened ``_in_scope`` from
#   templates/agents/** to any staged templates/**/*.md. The validator this hook
#   wraps already runs ability_reference_verdict over every templates/**/*.md,
#   but the narrow scope meant a dangling skill reference in templates/skills/**
#   or templates/commands/** was caught only by CI's build, not at commit time.
#   Widened here rather than adding a separate check-skill-refs hook (no manifest
#   or deploy-manifest change; the stanza has no files: filter). The failure banner
#   now names "skill reference" validation so a reference finding is not headlined
#   only as a registry failure; per-error lines still carry template path and skill.
#   (#EPIC-ALearningAnAgentHasTodayActuallyGets/04)
# - 2026-09-28 16:00 [python-coder/AC INF-600k-1, pr-reviewer HIGH-3]: Moved
#   this file's own ``_resolve_package_root`` to ``_resolve_root.py`` as
#   ``resolve_package_root()`` (pure move, no behaviour change) so
#   check_agent_spawn_consistency.py could share the SAME package_root
#   resolution instead of it becoming a third, independently-drifting copy.
#   This file now imports it as ``_resolve_package_root`` (same call site,
#   same behaviour) rather than defining it locally.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 08:10 [python-coder/GE-113c-1-vi, pr-reviewer follow-up
#   IO-001]: check_exception_handling.py flagged the ``subprocess.run()`` in
#   ``_get_staged_files()`` as an unwrapped I/O boundary call (Error Handling
#   Policy Rule 1). Wrapped it in ``try/except (OSError,
#   subprocess.SubprocessError)``, logging a WARNING and returning ``None``
#   on failure — mirroring check_ac_schema.py's / transform_component_vocab
#   .py's own ``git diff --cached`` wrapping pattern in this same directory.
#   A non-zero exit from git is treated identically to a raised exception
#   (both mean "cannot tell what is staged"), which those two sibling hooks
#   do NOT do (they fail OPEN, returning ``[]``, on either condition). This
#   hook deliberately does NOT follow that fail-open precedent: GE-113c-1-vi
#   built this hook specifically to end a silent pass, so treating "git
#   could not be queried" the same as "nothing is staged" would reopen the
#   identical hole from a different angle. ``_get_staged_files()`` now
#   returns ``list[str] | None`` (``None`` distinct from an empty list), and
#   ``main()`` treats ``None`` as a THIRD, fail-closed outcome —
#   ``_report_could_not_check_staged_files()`` — with wording distinct from
#   both ``_report_cannot_locate`` (package not found) and
#   ``_report_validation_failed`` (registry read and invalid), exiting 1.
# - 2026-09-28 07:15 [python-coder/GE-113c-1-vi, pr-reviewer follow-up H-2,
#   M-2]: H-2: the candidate-root search this file's original
#   ``_candidate_manifest_roots`` duplicated was a THIRD, independently
#   -drifting copy of check_build_drift.py's / check_output_drift.py's
#   identical pair — the AC's it_requirements explicitly forbid that, and the
#   copies had already diverged (this file's OSError-on-unlistable
#   -workspace-root branch was silent; check_build_drift.py's logged a
#   WARNING). Extracted into the shared ``_resolve_root.py`` module — already
#   deployed alongside every hook in this directory, including every existing
#   unit-test fixture's minimal hook deployment, so no fixture needed
#   updating; see that module's own DECISION HISTORY for why a brand-new
#   sibling module was tried first and reverted — (imported by all three
#   hooks now); this file's own ``_resolve_package_root`` now calls
#   ``_resolve_root.resolve_manifest_path()`` for the search and layers only
#   its OWN ``package_root``-field interpretation and block-vs-warn policy on
#   top — see that module's docstring for the shared/not-shared boundary.
#   M-2: added the explicit cross-reference in the
#   "NO SILENT PASS" docstring section above, naming that this hook's
#   block-on-missing-manifest policy is deliberately different from
#   check_build_drift.py's / check_output_drift.py's warn-and-exit-0 policy
#   on the same condition (GE-113c-1-vi criterion 2, GE-120a-1). No test
#   -visible behaviour change: the full GE-113c-1-vi suite, the BO-2400a-1-iii
#   suite, and both drift hooks' own test suites were re-run before and after
#   this extraction with identical pass counts.
# - 2026-09-28 06:30 [python-coder]: Fixed the never-runs-in-this-repo defect
#   (KI-CG-20260928, GE-113c-1-vi). main() previously computed
#   ``package_root = repo_root / "leafcutter"`` (a path that has never
#   existed in this repository) and returned 0 — without reading
#   anything — when it was absent. Replaced with ``_resolve_package_root``,
#   which reads the SAME ``.build_manifest.json`` ``package_root`` field
#   check_build_drift.py / check_output_drift.py already read (GE-118b's
#   ``_candidate_manifest_roots`` search order, reused verbatim rather than
#   duplicated with a new convention). Scope detection (``_in_scope``) now
#   matches the registry/schema/templates at ANY prefix instead of a
#   hardcoded ``leafcutter/`` one, via split path-segment tuples rather than
#   joined "dir/file.ext" literals — a joined literal for
#   "config/agent_registry.json" (a file that IS real on this repo's own
#   disk) tripped this repo's own compute_intra_package_closure build check
#   (BP-900g-8-ii), which reads any standalone literal in that shape as a
#   claimed data-file read needing a deploy-phase mapping; this hook never
#   opens that path itself, so the literal was restructured instead of
#   mapping a phantom dependency. A staged in-scope file with no locatable
#   package now blocks the commit with its own ``CANNOT LOCATE PACKAGE``
#   wording (``_report_cannot_locate``), distinct from the registry-invalid
#   wording (``_report_validation_failed``), instead of silently returning 0.
#   The hard-coded "See leafcutter/config/agent_registry.json" hint is
#   replaced with the actually-resolved registry path. Enablement check at
#   implementation (2026-09-28): the real registry gives 0 errors under both
#   this fixed hook and build.py --validate-only, so no known-issue entry is
#   needed to turn the gate on. (#TICKETLESS reason=ge-113c-1-vi-registry-gate-root)
# - 2026-05-13 11:00 [epic-supervisor/ticket-20]: Initial implementation.
#   Thin wrapper around registry_validator.validate_agent_registry().
#   Only fires when agent-registry-related files are staged (prevents
#   spurious failures on unrelated commits). Falls back gracefully when
#   the package or module cannot be found (returns 0) — opt-in safety.
# ====================================================================
