"""
MODULE: check_identifier_uniqueness_authoring.py
GOAL: Evaluate GE-122's whole-collection numbering rule at AUTHORING time
    (PostToolUse Edit|Write), importing and calling the SAME evaluation
    module the commit-time and shared-build stages use — never a second,
    independently-maintained copy of the rule.
BUSINESS CONTEXT: GE-122d-1 requires that one rule, evaluated at three
    stages (authoring time, commit time, shared-build time), cannot give
    three different answers. A per-stage reimplementation is the exact
    failure mode this AC exists to forbid: three stages that all evaluate
    "the same rule" only in the sense that someone copied the code once are
    indistinguishable, from a reader's perspective, from three stages that
    silently drifted apart. This module therefore contains NO scanning logic
    of its own — it locates and imports
    ``check_identifier_uniqueness.run_uniqueness_pass`` (the GE-122a-1
    evaluation module) and reports whatever it returns.
ARCHITECTURE: A single public function, ``evaluate_identifier_uniqueness``,
    that resolves the shared module by path relative to this file's own
    location rather than via a fixed absolute import. This is deliberate,
    not incidental: this hook deploys to THREE different locations, at
    THREE different depths relative to the shared module —
      - Source tree: ``templates/hooks/`` (1 level above the shared
        module's parent: ``templates/scripts/commit_guardian/`` is a
        SIBLING of ``templates/hooks/``).
      - Deployed (Claude Code): ``<root>/.leafcutter/hooks/`` (also a
        SIBLING of ``<root>/.leafcutter/scripts/commit_guardian/``).
      - Deployed (Antigravity/Gemini): ``<root>/.leafcutter/gemini/hooks/``
        (NOT a sibling of ``scripts/commit_guardian/`` — there is an EXTRA
        ``gemini/`` directory between it and the shared module, which
        lives at ``<root>/.leafcutter/scripts/commit_guardian/``, never at
        ``<root>/.leafcutter/gemini/scripts/commit_guardian/``).
    A single fixed number of ``..`` hops (e.g. ``parent.parent``) is
    therefore WRONG for at least one of the three deployed copies: it
    resolves the source tree and the Claude Code deployment correctly, but
    raises ``ModuleNotFoundError`` from the Antigravity deployment (see the
    2026-08-31 bug-fix DECISION HISTORY entry below — this was actually
    shipped and actually reproduced). Rather than hardcode a fixed hop count
    (which would only be correct for whichever layouts existed when it was
    written) or a hardcoded list of the three known deploy roots (which
    silently breaks the day a fourth platform is added), this module WALKS
    this file's ancestor directories outward, stopping at the first one
    that has a ``scripts/commit_guardian/check_identifier_uniqueness.py``
    descendant — see ``_find_shared_module_path``. This is correct for any
    depth at which the shared module's grandparent happens to sit, without
    per-platform branching and without a maintained list of deploy roots.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/hooks/ticket_frontmatter_guard.py
  - templates/settings.json

DECISION HISTORY:
  - 2026-08-31 [python-coder/GE-122d-1]: Created. Fills the previously-empty
    authoring-time stage for GE-122's numbering rule by importing the
    existing commit-time module (``check_identifier_uniqueness.py``, built
    for GE-122a-1) rather than reimplementing the scan — the coverage note
    on GE-122d-1 explicitly rejects any test (and, by the same reasoning,
    any implementation) that lets the three stages hold independent copies
    of the rule. PostToolUse hook wiring (reading Claude Code's stdin
    payload and emitting a blocking decision) is intentionally NOT added in
    this increment: GE-122d-1's own test_spec scopes this AC to proving the
    three stages evaluate identically, not to the authoring hook's full
    Claude Code integration, which is a separate, not-yet-scheduled
    increment.
  - 2026-09-01 [python-coder/GE-122d-1, reachability fix]: Added ``main()``
    and registered this hook in ``templates/settings.json``'s PostToolUse
    Edit|Write entry. The prior increment's module was correct but
    unreachable: GE-122d-1's own amended_by history (2026-08-31, "manual")
    records that a previous ``work_status: done`` flip was reverted because
    this exact module "appears ZERO times in the ten hooks wired in
    .leafcutter/settings.json" — a module that behaves correctly when
    called is not evidence anything calls it. ``main()`` reads the
    PostToolUse stdin payload (fail-open on malformed input, per the
    sibling hooks in this directory), resolves the project root by walking
    up from ``Path.cwd()`` for the same marker files
    ticket_frontmatter_guard.py's ``find_project_root`` uses, and evaluates
    ``evaluate_identifier_uniqueness`` against it. Fails open (exit 0) on
    any condition that prevents evaluation itself (no resolvable root, the
    shared module missing, malformed stdin); blocks (exit 2, per the
    PostToolUse "exit 2 = block with content" contract this directory's
    other hooks already use) only on a genuinely contested collection.
  - 2026-08-31 [python-coder/GE-122d-6, bug-fix, PR #635 empirical review
    findings 1/2/9]: Three fixes, each independently reproduced before being
    fixed:
      - [Finding 1] ``_load_shared_uniqueness_module`` resolved the shared
        module via a single fixed ``parent.parent / "scripts" /
        "commit_guardian" / ...`` hop. Reproduced by invoking the deployed
        Antigravity copy (``.leafcutter/gemini/hooks/...``) directly: it
        raised ``ModuleNotFoundError`` looking for
        ``.leafcutter/gemini/scripts/commit_guardian/check_identifier_uniqueness.py``
        — a path that has never existed, because the shared module deploys
        once, to ``.leafcutter/scripts/commit_guardian/``, not per platform.
        Fixed by replacing the fixed hop with ``_find_shared_module_path``,
        an ancestor walk that finds the shared module regardless of how
        many directories separate this file's platform-specific hook
        directory from the shared module's common ancestor — verified
        against all three deployed/source locations (see the sign-off
        comment for exact invocations).
      - [Finding 2, THE SERIOUS ONE] ``evaluate_identifier_uniqueness``
        computed ``contested_numbers`` purely from
        ``namespace_verdict.findings``, discarding
        ``namespace_verdict.passed`` entirely. GE-122e-3's "unresolvable
        namespace" contract (see
        _commit_disposition.py and _work_items_scanner.py) reports exactly
        this shape for a misconfigured root: ``passed=False`` with an
        EMPTY ``findings`` list — the root/config itself is the finding,
        so there is no number to name. This function's old logic therefore
        reported ``{"contested_numbers": []}`` (indistinguishable from
        "genuinely clean") on precisely the root shape where the
        commit-time stage's own ``main()`` / ``compute_commit_disposition``
        exits 1, fail-closed — two stages of the SAME guard giving OPPOSITE
        verdicts on the SAME input, exactly what GE-122d-1 exists to
        forbid. Reproduced with a fixture root holding real, empty (but
        RESOLVED) acceptance-criteria/decisions/diagrams directories and a
        ``tickets/`` directory with NO ``ticket_lifecycle.json`` — before
        the fix: commit-time ``verdict.passed == False`` /
        ``disposition.blocking == True`` /
        ``disposition.unresolvable_namespaces == ["work-items"]``, while
        authoring-time reported ``{"contested_numbers": []}``, i.e. clean.
        Fixed by having this function ALSO surface
        ``namespace_verdict.passed`` — added ``"passed"`` (the whole
        verdict's own ``verdict.passed``, verbatim — a caller that checks
        only this one boolean field can never disagree with the
        commit-time stage's own pass/fail outcome) and
        ``"unresolvable_namespaces"`` (the same "passed=False with empty
        findings" test ``compute_commit_disposition`` already uses,
        applied here so a caller can name WHICH namespace could not be
        resolved, mirroring ``main()``'s own operator-facing message) to
        the returned JSON. ``contested_numbers`` keeps its exact prior
        meaning and is unchanged for every input where every namespace
        resolved — this is a strictly ADDITIVE fix; no existing consumer
        (GE-122d-1's own three-stages-agree test only reads
        ``contested_numbers`` for a genuine collision) is narrowed.
      - [Finding 9] ``_load_shared_uniqueness_module`` called
        ``sys.modules.setdefault(spec.name, module)`` BEFORE
        ``spec.loader.exec_module(module)``. Two failure modes: (a) if
        ``exec_module`` raised, the not-yet-executed (half-initialised)
        module object stayed registered in ``sys.modules`` under
        ``"check_identifier_uniqueness"`` for the rest of the process,
        so a LATER, unrelated import of that name could silently receive
        the broken half-init object rather than either a working module or
        a fresh ``ImportError``; (b) ``setdefault`` never overwrites an
        existing entry, so if some other loader had already registered a
        DIFFERENT module object under that same name, this function would
        execute and return a freshly-populated module while leaving the
        stale, different object sitting in ``sys.modules`` — a caller that
        looked the name up via ``sys.modules`` rather than this function's
        own return value would silently diverge from what this function
        just loaded. Fixed by moving the ``sys.modules`` write to AFTER a
        successful ``exec_module`` call (inside a ``try`` whose
        ``except`` re-raises after removing anything this call itself may
        have started to register), and by unconditionally assigning
        (``sys.modules[spec.name] = module``, never ``setdefault``) so the
        registered object and the returned object are always identical on
        success, and nothing is registered at all on failure.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_SHARED_MODULE_NAME = "check_identifier_uniqueness"
_SHARED_MODULE_RELATIVE_PATH = Path("scripts") / "commit_guardian" / "check_identifier_uniqueness.py"

#: Project-root markers checked in order of preference when this hook is
#: invoked with no explicit root argument (the real PostToolUse invocation
#: shape — see templates/settings.json's Edit|Write registration). Mirrors
#: ticket_frontmatter_guard.py's MARKER_FILES list so both hooks agree on
#: what "the project root" means.
_ROOT_MARKER_FILES = [".git", "CLAUDE.md", "pyproject.toml", "requirements-dev.txt"]


def _find_shared_module_path() -> Path | None:
    """Walk this file's ancestor directories to find the shared evaluation module.

    Checks this file's own hook directory and every ancestor above it (the
    hook directory itself, its parent, its grandparent, and so on) for a
    ``scripts/commit_guardian/check_identifier_uniqueness.py`` descendant,
    returning the first match. This is deliberately NOT a fixed hop count
    (``parent.parent``) — this hook deploys to three locations at three
    different depths relative to the shared module's common ancestor (see
    this module's ARCHITECTURE note), and a fixed hop count is only correct
    for whichever of those three happens to match it. Walking outward until
    a match is found is correct for all three today, and for any future
    deploy layout whose hook directory sits at yet another depth, with no
    per-platform branching and no maintained list of deploy roots.

    Returns:
        The resolved path to the shared module, or None if no ancestor
        (up to the filesystem root) has one.
    """
    hooks_dir = _THIS_FILE.parent
    for ancestor in (hooks_dir, *hooks_dir.parents):
        candidate = ancestor / _SHARED_MODULE_RELATIVE_PATH
        if candidate.exists():
            return candidate
    return None


def _load_shared_uniqueness_module():
    """Import the shared GE-122a-1 evaluation module by file path.

    Loaded via ``importlib.util.spec_from_file_location`` (rather than a
    normal package import) so this hook works unmodified from every
    deployed location, none of which necessarily has the sibling
    ``scripts/commit_guardian/`` directory on ``sys.path``. The shared
    module's path is resolved fresh on every call via
    ``_find_shared_module_path`` (an ancestor walk, not a fixed hop count)
    so this works from all three deploy depths (source tree, Claude Code,
    Antigravity — see this module's ARCHITECTURE note).

    ``sys.modules`` is populated only AFTER ``exec_module`` succeeds, and is
    always assigned (never ``setdefault``) — so a failed load never strands
    a half-initialised module under this name, and a successful load never
    silently diverges from what this function itself returns.

    Returns:
        The executed ``check_identifier_uniqueness`` module object, exposing
        ``run_uniqueness_pass``.

    Raises:
        ModuleNotFoundError: if the shared module is not present at any
            resolvable ancestor of this file — this stage cannot evaluate
            the same rule as the commit-time stage without it, so it fails
            loudly rather than silently reporting no findings.
    """
    shared_module_path = _find_shared_module_path()
    if shared_module_path is None:
        raise ModuleNotFoundError(
            "Shared uniqueness evaluation module "
            f"({_SHARED_MODULE_RELATIVE_PATH}) not found in any ancestor "
            f"directory of {_THIS_FILE}. The authoring-time stage cannot "
            "evaluate the same rule as the commit-time and shared-build "
            "stages without it (GE-122d-1)."
        )
    spec = _ilu.spec_from_file_location(_SHARED_MODULE_NAME, shared_module_path)
    module = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_SHARED_MODULE_NAME, None)
        raise
    sys.modules[_SHARED_MODULE_NAME] = module
    return module


def evaluate_identifier_uniqueness(root_path: str) -> str:
    """Evaluate GE-122's whole-collection uniqueness rule at authoring time.

    Delegates entirely to the shared ``run_uniqueness_pass`` — this function
    performs no scanning of its own, per this module's ARCHITECTURE note.

    Args:
        root_path: Root directory of the collection to inspect (the same
            argument shape ``run_uniqueness_pass`` accepts).

    Returns:
        A JSON string of the form
        ``{"contested_numbers": [...], "passed": bool,
        "unresolvable_namespaces": [...]}``.

        ``contested_numbers`` names every number claimed by two or more
        artifacts across every namespace the shared module is responsible
        for — unchanged from this function's original contract.

        ``passed`` is ``verdict.passed`` verbatim: True iff EVERY namespace
        both resolved (its root/config could be read at all) AND found no
        collision. A caller that branches on this single field can never
        disagree with the commit-time stage's own whole-collection
        pass/fail outcome.

        ``unresolvable_namespaces`` names every namespace whose own
        NamespaceVerdict reported ``passed=False`` with an EMPTY
        ``findings`` list — GE-122e-3's contract for "the root/config
        itself could not be resolved at all", as opposed to a genuine
        collision (which always populates ``findings``). Reading
        ``contested_numbers`` alone cannot distinguish these two cases,
        which is exactly how this function previously reported a clean
        result on a root the commit-time stage refuses (see the
        2026-08-31 bug-fix DECISION HISTORY entry above).
    """
    shared = _load_shared_uniqueness_module()
    verdict = shared.run_uniqueness_pass(root_path)
    contested = sorted(
        {
            finding.number
            for namespace_verdict in verdict.namespaces.values()
            for finding in namespace_verdict.findings
        }
    )
    unresolvable_namespaces = sorted(
        namespace
        for namespace, namespace_verdict in verdict.namespaces.items()
        if namespace_verdict.passed is False and not namespace_verdict.findings
    )
    return json.dumps(
        {
            "contested_numbers": contested,
            "passed": verdict.passed,
            "unresolvable_namespaces": unresolvable_namespaces,
        }
    )


# ---------------------------------------------------------------------------
# PostToolUse entry point
# ---------------------------------------------------------------------------


def _find_project_root(start: Path) -> Path | None:
    """Walk up from *start* to the first ancestor holding a project-root marker.

    Uses the same marker list as ticket_frontmatter_guard.py's
    ``find_project_root`` so every authoring-time hook agrees on what "the
    project root" means, without a cross-file import (this hook resolves its
    own dependencies by path-walking, not by package import — see this
    module's ARCHITECTURE note).

    Args:
        start: Path to begin the search from.

    Returns:
        The first ancestor directory containing any marker in
        ``_ROOT_MARKER_FILES``, or ``None`` when no marker is found within
        15 levels.
    """
    cur = start
    for _ in range(15):
        if any((cur / marker).exists() for marker in _ROOT_MARKER_FILES):
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _build_block_message(payload: dict) -> str:
    """Build the human-readable blocking message for a contested collection.

    Args:
        payload: The parsed JSON payload returned by
            ``evaluate_identifier_uniqueness``.

    Returns:
        Multi-line string injected back to Claude as a blocking feedback entry.
    """
    lines = [
        "NUMBERING GUARANTEE VIOLATION (GE-122) — a number claims more than one thing:",
        "",
    ]
    for number in payload.get("contested_numbers", []):
        lines.append(f"  {number} is claimed by more than one artifact.")
    for namespace in payload.get("unresolvable_namespaces", []):
        lines.append(f"  namespace '{namespace}' could not be resolved at all (root/config missing or unreadable).")
    lines.append("")
    lines.append(
        "This is the same whole-collection rule the commit-time and shared-build "
        "stages enforce (GE-122d-1) — fixing it now is cheaper than at commit time."
    )
    return "\n".join(lines)


def main() -> None:
    """Entry point. Evaluates the numbering rule and emits a PostToolUse decision.

    Reads the PostToolUse payload from stdin (the same shape every other
    Edit|Write hook in this directory reads — see
    check_exception_handling_hook.py / ticket_frontmatter_guard.py), then
    evaluates GE-122's whole-collection rule against the current project
    root via ``evaluate_identifier_uniqueness``. This is the ONLY authoring
    stage entry point that Claude Code's PostToolUse mechanism can actually
    reach (see this AC's amended_by history: a correctly-behaving module
    that nothing calls is not a working stage).

    Fails open (exits 0, never blocks) on any condition that prevents
    evaluation itself: malformed stdin, no resolvable project root, or the
    shared module being unavailable — per CLAUDE.md's hook fail-open
    carve-out, a hook crash must never block an unrelated Edit/Write. A
    *contested* collection is not fail-open: it is the exact condition this
    hook exists to surface, so it blocks (exit 2) with a message naming
    every contested number and every unresolvable namespace.
    """
    try:
        sys.stdin.read()
    except (OSError, ValueError):
        sys.exit(0)

    project_root = _find_project_root(Path.cwd())
    if project_root is None:
        sys.exit(0)

    try:
        payload = json.loads(evaluate_identifier_uniqueness(str(project_root)))
    except (ModuleNotFoundError, OSError, ValueError) as exc:
        print(
            f"[check_identifier_uniqueness_authoring] could not evaluate the numbering "
            f"rule: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)

    if payload.get("passed", True):
        sys.exit(0)

    print(_build_block_message(payload))
    sys.exit(2)


if __name__ == "__main__":
    main()
