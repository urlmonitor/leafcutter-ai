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
        module via a single fixed hop, which raised ``ModuleNotFoundError``
        from the deployed Antigravity copy (a path that has never existed,
        since the shared module deploys once, not per platform). Fixed by
        ``_find_shared_module_path``, an ancestor walk correct at any depth.
      - [Finding 2, THE SERIOUS ONE] ``evaluate_identifier_uniqueness``
        computed ``contested_numbers`` purely from
        ``namespace_verdict.findings``, discarding
        ``namespace_verdict.passed`` entirely. GE-122e-3's "unresolvable
        namespace" shape (``passed=False``, EMPTY ``findings`` -- the
        root/config itself is the finding) therefore reported
        ``{"contested_numbers": []}`` (indistinguishable from clean) on
        exactly the root shape where the commit-time stage's own ``main()``
        exits 1 fail-closed -- two stages of the SAME guard giving OPPOSITE
        verdicts, exactly what GE-122d-1 forbids. Reproduced with a
        resolved-but-misconfigured fixture root (real empty
        acceptance-criteria/decisions/diagrams, ``tickets/`` with no
        ``ticket_lifecycle.json``). Fixed, ADDITIVELY, by also surfacing
        ``"passed"`` (verdict.passed verbatim) and
        ``"unresolvable_namespaces"`` in the returned JSON;
        ``contested_numbers`` is unchanged for every resolved input.
      - [Finding 9] ``_load_shared_uniqueness_module`` called
        ``sys.modules.setdefault(spec.name, module)`` BEFORE
        ``exec_module``, so a raise left a half-initialised module
        registered, and ``setdefault`` never overwrote a differing existing
        entry. Fixed by writing ``sys.modules`` only AFTER a successful
        ``exec_module`` (unconditional assignment, never ``setdefault``, and
        removed on failure).
  - 2026-09-01 [python-coder/GE-122d-1, adversarial-review bug-fix]: Four
    fixes, each reproduced against real fixtures before being fixed (see the
    sign-off comment for exact before/after exit codes):
      - [Blocker 1, agreement in both directions] ``main()`` branched on the
        raw ``verdict.passed`` where the commit-time stage branches on
        ``compute_commit_disposition(...).blocking`` (diff-scoped
        attribution). Reproduced: a COMMITTED collision with NOTHING staged
        made commit-time exit 0 while this hook exited 2 -- disagreement
        swung the OPPOSITE way from the AC's original defect. Fixed by
        calling the SAME ``compute_commit_disposition`` over the SAME
        ``_get_staged_paths`` and adding a ``"blocking"`` field ``main()``
        now branches on; falls back to ``not verdict.passed`` when the
        staged set can't be determined, mirroring commit-time ``main()``.
        ``"passed"`` is unchanged for any caller still reading only it.
      - [Blocker 2, unscaffolded-project denial-of-service] A directory
        holding only CLAUDE.md made every namespace report "unresolvable"
        (an absent root is NOT an empty collection, per GE-122e-3 /
        GE-122d-3-ii), previously blocking EVERY Edit/Write in ANY
        unscaffolded project. GE-122d-3-ii's sanctioned fix is scaffolding
        the four roots at install time, never teaching the scanner absence
        means empty -- untouched here. This hook adds a narrower
        authoring-only heuristic: a new ``"unscaffolded"`` field, True iff
        EVERY namespace is unresolvable SIMULTANEOUSLY (a partially
        scaffolded project still reports 1-3 and still blocks as before).
        ``main()`` checks it before ``"blocking"`` and fails open.
      - [Fix 3] The block message printed to stdout while exiting 2;
        PostToolUse feeds stderr back to Claude. Fixed: print to stderr.
      - [Fix 4] ``main()`` discarded stdin and used only ``Path.cwd()``.
        Fixed by parsing the payload and extracting
        ``tool_input.file_path``/``tool_input.path`` (new
        ``_resolve_root_start_path``, mirroring
        ticket_frontmatter_guard.py's ``_resolve_ticket_path``), falling
        back to ``Path.cwd()`` only when the payload names no usable path.
  - 2026-09-07 [python-coder/GE-122d-3]: Added the ``could_not_establish``
    field to ``evaluate_identifier_uniqueness``'s returned JSON and the new,
    additive ``edited_path`` parameter (``main()`` passes the same path
    ``_resolve_root_start_path`` resolves), plus the message-building it
    feeds ``_build_block_message`` -- printing the same three statements
    GE-122d-3 requires at every stage (named artifact, "NOT established",
    read count), with the author's own just-written file excluded from the
    reported count when it falls inside the affected namespace. The
    could-not-establish namespace already made this hook block before this
    change (caught by the pre-existing ``unresolvable_namespaces`` check,
    since a lone unreadable artifact reports ``passed=False, findings=[]``
    exactly like an unresolvable root/config) -- only the printed MESSAGE
    was silent on which artifact and how many were read. The block message
    now also states the author's file has NOT been reverted (true throughout:
    this hook performs no write/revert of its own). The actual logic --
    ``namespace_contains_edited_path`` / ``build_could_not_establish_entries``
    / ``append_could_not_establish_lines`` -- moved to the new sibling
    ``_identifier_uniqueness_could_not_establish.py`` (see that module's own
    DECISION HISTORY) once this file's growth crossed the check_file_size.py
    ratchet ceiling; see that module for the exclusion rationale in full.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_SHARED_MODULE_NAME = "check_identifier_uniqueness"
_SHARED_MODULE_RELATIVE_PATH = Path("scripts") / "commit_guardian" / "check_identifier_uniqueness.py"
_COULD_NOT_ESTABLISH_MODULE_NAME = "_identifier_uniqueness_could_not_establish"

#: Project-root markers checked in order of preference when this hook is
#: invoked with no explicit root argument (the real PostToolUse invocation
#: shape — see templates/settings.json's Edit|Write registration). Mirrors
#: ticket_frontmatter_guard.py's MARKER_FILES list so both hooks agree on
#: what "the project root" means.
_ROOT_MARKER_FILES = [".git", "CLAUDE.md", "pyproject.toml", "requirements-dev.txt"]

_HOOK_PREFIX = "[check_identifier_uniqueness_authoring]"


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


def _load_could_not_establish_module():
    """Import the GE-122d-3 could-not-establish message module by file path.

    Resolved via the SAME ancestor walk as ``_load_shared_uniqueness_module``
    -- both modules live together in ``scripts/commit_guardian/`` -- so this
    works from every deploy depth with no second, separately-maintained
    resolution strategy. See
    ``_identifier_uniqueness_could_not_establish.py``'s own DECISION HISTORY
    for why this module is NOT a plain same-directory sibling import: the
    ``templates/hooks/*.py`` wildcard deploy mapping skips any filename
    starting with ``_``, so a plain sibling file placed directly in this
    hook's own directory silently never deploys at all.

    Returns:
        The executed module, exposing ``build_could_not_establish_entries``
        and ``append_could_not_establish_lines``.

    Raises:
        ModuleNotFoundError: mirrors ``_load_shared_uniqueness_module``'s own
            contract when the shared ``scripts/commit_guardian/`` directory
            cannot be located at all.
    """
    shared_module_path = _find_shared_module_path()
    if shared_module_path is None:
        raise ModuleNotFoundError(
            f"{_COULD_NOT_ESTABLISH_MODULE_NAME} could not be located: its sibling "
            f"scripts/commit_guardian/ directory was not found in any ancestor of {_THIS_FILE}."
        )
    module_path = shared_module_path.parent / f"{_COULD_NOT_ESTABLISH_MODULE_NAME}.py"
    spec = _ilu.spec_from_file_location(_COULD_NOT_ESTABLISH_MODULE_NAME, module_path)
    module = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_COULD_NOT_ESTABLISH_MODULE_NAME, None)
        raise
    sys.modules[_COULD_NOT_ESTABLISH_MODULE_NAME] = module
    return module


def evaluate_identifier_uniqueness(root_path: str, edited_path: str | None = None) -> str:
    """Evaluate GE-122's whole-collection uniqueness rule at authoring time.

    Delegates entirely to the shared ``run_uniqueness_pass`` — this function
    performs no scanning of its own, per this module's ARCHITECTURE note.

    Args:
        root_path: Root directory of the collection to inspect (the same
            argument shape ``run_uniqueness_pass`` accepts).
        edited_path: ADDITIVE (GE-122d-3). The author's just-written file
            path, when known (``main()`` passes the path
            ``_resolve_root_start_path`` resolved). Forwarded verbatim to
            ``build_could_not_establish_entries`` (see that function's own
            docstring in ``_identifier_uniqueness_could_not_establish.py``);
            has no effect on any other field, and none at all when ``None``.

    Returns:
        A JSON string of the form
        ``{"contested_numbers": [...], "passed": bool, "blocking": bool,
        "unresolvable_namespaces": [...], "unscaffolded": bool,
        "could_not_establish": [...]}``.

        ``contested_numbers`` names every number claimed by two or more
        artifacts across every namespace the shared module is responsible
        for — unchanged from this function's original contract.

        ``passed`` is ``verdict.passed`` verbatim: True iff EVERY namespace
        both resolved (its root/config could be read at all) AND found no
        collision. Kept for any existing caller that reads only this field;
        ``main()`` no longer branches on it directly (see ``"blocking"``).

        ``blocking`` is computed by calling the SAME
        ``compute_commit_disposition`` the commit-time stage's own
        ``main()`` calls, over the SAME staged-path lookup (the commit-time
        module's own ``_get_staged_paths``) — never a second,
        independently-maintained attribution rule. This is what fixes
        GE-122d-1's own "one rule, one answer" requirement in the direction
        this hook previously got wrong: a contested number with no claimant
        in the current change set is reported-but-unattributed by the
        commit-time stage (does not block) and must not block here either.
        When the staged set itself cannot be determined (e.g. no git
        repository present), falls back to ``not verdict.passed`` — the
        commit-time stage's own literal fallback for that same condition —
        rather than a disposition computed against an unknowable diff.

        ``unresolvable_namespaces`` names every namespace whose own
        NamespaceVerdict reported ``passed=False`` with an EMPTY
        ``findings`` list — GE-122e-3's contract for "the root/config
        itself could not be resolved at all", as opposed to a genuine
        collision (which always populates ``findings``). Reading
        ``contested_numbers`` alone cannot distinguish these two cases,
        which is exactly how this function previously reported a clean
        result on a root the commit-time stage refuses (see the
        2026-08-31 bug-fix DECISION HISTORY entry above).

        ``unscaffolded`` is True iff EVERY namespace in the verdict is
        unresolvable simultaneously — the signature of a project that has
        no GE-122 namespace scaffolding at all (see the 2026-09-01 bug-fix
        DECISION HISTORY entry above), as opposed to a genuine
        misconfiguration of one specific root, which leaves at least one
        other namespace resolved. ``main()`` checks this before
        ``"blocking"`` and fails open when set.

        ``could_not_establish`` (ADDITIVE, GE-122d-3) names every namespace
        with at least one individually unreadable/unparsable artifact -- as
        opposed to ``unresolvable_namespaces``, whose own ROOT/CONFIG could
        not be resolved at all. Built by
        ``build_could_not_establish_entries`` (see
        ``_identifier_uniqueness_could_not_establish.py`` for the entry
        shape and the ``inspected_count`` exclusion rule); empty when every
        namespace's artifacts were all individually readable and parsable.
    """
    shared = _load_shared_uniqueness_module()
    could_not_establish_mod = _load_could_not_establish_module()
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
    could_not_establish = could_not_establish_mod.build_could_not_establish_entries(verdict, root_path, edited_path)
    total_namespaces = len(verdict.namespaces)
    unscaffolded = total_namespaces > 0 and len(unresolvable_namespaces) == total_namespaces

    staged_paths = shared._get_staged_paths()  # noqa: SLF001 -- reuse, never reimplement
    if staged_paths is None:
        blocking = not verdict.passed
    else:
        disposition = shared.compute_commit_disposition(verdict, staged_paths)
        blocking = disposition.blocking

    return json.dumps(
        {
            "contested_numbers": contested,
            "passed": verdict.passed,
            "blocking": blocking,
            "unresolvable_namespaces": unresolvable_namespaces,
            "unscaffolded": unscaffolded,
            "could_not_establish": could_not_establish,
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


def _resolve_root_start_path(hook_payload: dict) -> Path:
    """Resolve the ancestor-walk start path from a PostToolUse payload.

    Prefers the edited file's own path (``tool_input.file_path`` /
    ``tool_input.path``), mirroring ticket_frontmatter_guard.py's
    ``_resolve_ticket_path`` and check_exception_handling_hook.py's own
    ``tool_input`` read exactly — the payload names the file Claude Code
    actually touched, which is the authoritative signal a PostToolUse hook
    is designed to use. ``Path.cwd()`` is only ever an approximation of it
    (the agent process's current directory, not necessarily the location of
    the edited file), so it is used only as a fallback, never as the
    primary source (see the 2026-09-01 bug-fix DECISION HISTORY entry above
    — this function is what makes that fix real rather than cosmetic).

    Args:
        hook_payload: The parsed PostToolUse JSON payload (may be ``{}``
            when stdin was empty or unparsable).

    Returns:
        The path to start ``_find_project_root``'s ancestor walk from:
        the edited file's own (resolved) path when the payload names one,
        else ``Path.cwd()``.
    """
    tool_input = hook_payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or ""
    if not raw:
        return Path.cwd()
    try:
        return Path(raw).resolve()
    except (ValueError, OSError):
        return Path.cwd()


def _build_block_message(evaluation: dict) -> str:
    """Build the human-readable blocking message for a contested collection.

    Args:
        evaluation: The parsed JSON payload returned by
            ``evaluate_identifier_uniqueness``.

    Returns:
        Multi-line string injected back to Claude as a blocking feedback entry.
    """
    lines = [
        "NUMBERING GUARANTEE VIOLATION (GE-122) — a number claims more than one thing:",
        "",
    ]
    for number in evaluation.get("contested_numbers", []):
        lines.append(f"  {number} is claimed by more than one artifact.")
    for namespace in evaluation.get("unresolvable_namespaces", []):
        lines.append(f"  namespace '{namespace}' could not be resolved at all (root/config missing or unreadable).")
    _load_could_not_establish_module().append_could_not_establish_lines(lines, evaluation)
    lines.append("")
    lines.append(
        "This is the same whole-collection rule the commit-time and shared-build "
        "stages enforce (GE-122d-1) — fixing it now is cheaper than at commit time. "
        "This file you just wrote has NOT been reverted."
    )
    return "\n".join(lines)


def main() -> None:
    """Entry point. Evaluates the numbering rule and emits a PostToolUse decision.

    Reads and parses the PostToolUse JSON payload from stdin (the same
    shape check_exception_handling_hook.py and ticket_frontmatter_guard.py
    read) and extracts ``tool_input.file_path`` / ``tool_input.path`` via
    ``_resolve_root_start_path`` to seed project-root discovery, falling
    back to ``Path.cwd()`` only when the payload carries no usable file
    path. Evaluates GE-122's whole-collection rule against that root via
    ``evaluate_identifier_uniqueness``. This is the ONLY authoring stage
    entry point that Claude Code's PostToolUse mechanism can actually reach
    (see this AC's amended_by history: a correctly-behaving module that
    nothing calls is not a working stage).

    Fails open (exits 0, never blocks) on any condition that prevents
    evaluation itself: malformed/empty stdin, no resolvable project root,
    the shared module being unavailable, or the project being unscaffolded
    for GE-122 entirely (every namespace unresolvable at once — see the
    ``"unscaffolded"`` field and the 2026-09-01 bug-fix DECISION HISTORY
    entry above) — per CLAUDE.md's hook fail-open carve-out, a hook crash
    (or an adopter's fresh, not-yet-scaffolded project) must never block an
    unrelated Edit/Write. An *attributed* contested collection is not
    fail-open: it is the exact condition this hook exists to surface, so it
    blocks (exit 2, message on stderr since PostToolUse feeds stderr back
    to Claude) with a message naming every contested number and every
    unresolvable namespace. The block/no-block decision itself
    (``"blocking"``) is computed by the SAME ``compute_commit_disposition``
    the commit-time stage calls — see ``evaluate_identifier_uniqueness``'s
    own docstring — never a second, independently-maintained rule.
    """
    try:
        hook_payload = json.loads(sys.stdin.read() or "{}")
    except (OSError, ValueError):
        sys.exit(0)

    start_path = _resolve_root_start_path(hook_payload)
    project_root = _find_project_root(start_path)
    if project_root is None:
        sys.exit(0)

    try:
        evaluation = json.loads(evaluate_identifier_uniqueness(str(project_root), edited_path=str(start_path)))
    except (ModuleNotFoundError, OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} could not evaluate the numbering rule: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)

    if evaluation.get("unscaffolded", False):
        sys.exit(0)

    if not evaluation.get("blocking", False):
        sys.exit(0)

    print(_build_block_message(evaluation), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
