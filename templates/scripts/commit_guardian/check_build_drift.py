"""
MODULE: check_build_drift
GOAL: Pre-commit hook — blocks the commit when a template file in
      leafcutter/templates/agents/ has been modified without
      re-running build.py (i.e. the file's SHA-256 differs from the hash
      recorded in leafcutter/.build_manifest.json).
BUSINESS CONTEXT: The leafcutter package compiles agent templates
    into .claude/agents/*.md inside the consumer project. If a developer edits
    a template but forgets to re-run build.py, the installed agents silently
    diverge from their source of truth. This hook is the sole guardrail that
    catches that class of drift at commit time (Master_Plan.md §9).
ARCHITECTURE: Reads .build_manifest.json written by build.py
    (build_helpers.write_build_manifest) at
    ``package_root / ".build_manifest.json"`` after each successful build
    run. For every .md file under ``<package_root>/templates/agents/``,
    computes the SHA-256 of the current on-disk content and compares it
    against the manifest entry. Exits 1 if any mismatch is found; exits 0
    otherwise. If the manifest is absent (e.g. fresh clone before first
    build), the hook exits 0 with a warning — no false-blocks on first-time
    setup.

    MANIFEST RESOLUTION (GE-118b): package_root's directory name is not
    knowable in advance (this repo's own checkout is "leafcutter-ai"; a
    consumer install may name it anything), so the manifest path — and the
    template directories derived from its parent — are never built from a
    hardcoded package-directory segment. See ``_candidate_manifest_roots``
    below for the layout-independent search order (git toplevel, then the
    structurally-derived workspace root, then that root's immediate
    subdirectories). check_output_drift.py shares this identical resolver.

    SCOPE: Covers two template trees:
    (1) templates/agents/ — .md files that build.py compiles into .claude/agents/.
    (2) templates/scripts/commit_guardian/ — .py hook scripts that build.py
        deploys into scripts/commit_guardian/. Added to close the blind spot
        where hook script edits in the deployed tree were not caught by drift
        detection (ACS-500f post-epic gap closure, 2026-06-18).

    UNCOMPARABLE REPORTING (BP-100k-3): a template absent from the manifest is
    no longer folded into a silent INFO line that still exits 0. It is
    reported as either a declared exemption (``UNCOMPARABLE: EXEMPT <key>
    ground=<ground>``) or a coverage gap (``UNCOMPARABLE: GAP <key>
    action=run build.py to register it``), counted in a single aggregate
    ``RESULT verified=<N> uncomparable=<M> drifted=<D> missing=<X>`` summary
    line, and reflected in the process exit status (0 clean / 1 drift / 2
    uncomparable-only — see ``main()``). The exemption registry is read from
    the ``drift_gate_exemption_registry`` key of ``commit_guardian.json``
    (colocated with this hook), or from ``HOOK_TEST_CONFIG`` for testing — the
    SAME registry check_output_drift.py reads, so a declaration honoured by
    one gate is honoured by its sibling (AC-5). An entry with no non-blank
    ``ground`` is rejected (``REJECTED EXEMPTION ENTRY: <key> reason=no
    ground stated``) and its artifact falls through to the GAP form.

    MISSING-TEMPLATE REPORTING (BP-100k-6): a manifest key that IS recorded
    but whose template file has been deleted from disk is a third, distinct
    case — reported as ``UNCOMPARABLE: MISSING <key> reason=recorded but not
    found on disk``, counted in its own ``missing=<X>`` RESULT field (never
    folded into ``verified`` or ``uncomparable``), and always a BLOCKED,
    non-clean exit. check_output_drift.py reports the identical verdict
    shape for a deleted deployed output — the two gates must agree, or an
    absence caught by one and ignored by the other reproduces the ambiguity
    BP-100k-3 removed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import logging

from _resolve_root import find_project_root

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

try:
    from _drift_exemptions import (
        ScanResult as _ScanResult,
        load_exemption_registry as _load_exemption_registry,
        validate_exemption_registry as _validate_exemption_registry,
    )
except ImportError:
    # Deploy-manifest gap fallback: some synthetic test fixtures deploy this
    # hook file alone rather than the whole scripts/commit_guardian/ tree
    # (the real build.py always deploys the directory verbatim, so this
    # never fires in production). Degrade to "every uncomparable artifact is
    # a GAP, never a declared exemption" instead of crashing the hook.
    from typing import NamedTuple

    logger.warning(
        "_drift_exemptions module not found alongside check_build_drift.py; "
        "exemption registry disabled for this run."
    )

    # MUST mirror _drift_exemptions._ScanResult field-for-field. This fallback
    # exists for installs where the helper is not deployed alongside the hook,
    # so it is the path that runs precisely when nothing else can catch a
    # mismatch — a missing field here raises TypeError at the one moment the
    # degraded path is needed, turning a graceful degradation into a crash.
    class _ScanResult(NamedTuple):  # type: ignore[no-redef]
        verified: int
        uncomparable: int
        gaps: int
        missing: int
        violations: list

    def _load_exemption_registry(_gate_name: str) -> list:  # type: ignore[misc]
        return []

    def _validate_exemption_registry(_entries: list) -> dict[str, str]:  # type: ignore[misc]
        return {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HOOK_FILE = Path(__file__).resolve()
_GATE_NAME = "check-build-drift"


# ---------------------------------------------------------------------------
# Manifest resolution (GE-118b)
# ---------------------------------------------------------------------------


def _candidate_manifest_roots(hook_file: Path) -> list[Path]:
    """Build the ordered list of plausible roots for .build_manifest.json.

    build_helpers.write_build_manifest() always writes to
    ``package_root / ".build_manifest.json"``, but package_root's directory
    name is NOT knowable in advance: this repo's own checkout is named
    "leafcutter-ai", while a consumer install may name it anything at all.
    Roots are tried in priority order, never by matching a hardcoded name:

    1. The git repository/worktree toplevel containing the current process
       (via the sibling ``_resolve_root.find_project_root()``, already used
       by the other hooks in this directory). pre-commit always invokes
       hooks with cwd == the repo root, so for a package checkout or a
       worktree of it this directly resolves to package_root.
    2. The "workspace root" derived structurally from this hook's own
       deployed location: two directories up from
       ``scripts/commit_guardian/<hook>.py`` is the deploy root (e.g.
       ``.leafcutter`` when deployed, ``templates`` when run from the
       source tree); one more level up is the workspace root that holds
       package_root as a sibling. Checked directly, for layouts where
       package_root IS the workspace root.
    3. Every immediate subdirectory of that workspace root (sorted for
       deterministic output) — covers the deployed-consumer-install layout,
       where package_root is a named sibling of the deploy root (this
       repo's real production layout: ``.leafcutter/`` and ``leafcutter-ai/``
       are siblings under the workspace root).

    Args:
        hook_file: Absolute, resolved path to this hook module
            (``Path(__file__).resolve()``).

    Returns:
        Ordered list of candidate root directories. May include directories
        that do not exist or do not contain the manifest — callers check
        each with ``.exists()``.
    """
    roots: list[Path] = [find_project_root().resolve()]

    deploy_root = hook_file.parents[2]
    workspace_root = deploy_root.parent
    roots.append(workspace_root)

    try:
        roots.extend(
            sorted(
                d.resolve()
                for d in workspace_root.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
        )
    except OSError as exc:
        logger.warning(
            "cannot list workspace root %s while searching for the build "
            "manifest: %s",
            workspace_root,
            exc,
        )

    return roots


def _resolve_manifest_path(hook_file: Path) -> tuple[Path | None, list[Path]]:
    """Locate the real .build_manifest.json, searching plausible roots.

    Args:
        hook_file: Absolute, resolved path to this hook module.

    Returns:
        Tuple of (manifest_path, tried_paths). ``manifest_path`` is None
        when no candidate exists on disk; ``tried_paths`` lists every
        absolute path checked, in search order, for use in a diagnostic
        message when the manifest genuinely cannot be found.
    """
    tried: list[Path] = []
    seen_roots: set[Path] = set()
    for root in _candidate_manifest_roots(hook_file):
        if root in seen_roots:
            continue
        seen_roots.add(root)
        candidate = root / ".build_manifest.json"
        tried.append(candidate)
        if candidate.exists():
            return candidate, tried
    return None, tried


def _warn_manifest_not_found(tried: list[Path]) -> None:
    """Print a visible, path-naming warning when no manifest was found.

    Args:
        tried: Every absolute candidate path that was checked.
    """
    tried_str = "\n  ".join(str(p) for p in tried)
    print(
        "check-build-drift: WARNING — .build_manifest.json not found. "
        f"Tried:\n  {tried_str}\n"
        "Run build.py to generate it. Skipping drift check.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file's content.

    Args:
        path: Absolute path to the file to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _load_manifest(manifest_path: Path) -> dict[str, str] | None:
    """Load the build manifest JSON file.

    Args:
        manifest_path: Absolute path to .build_manifest.json.

    Returns:
        Mapping of template-relative-path strings to SHA-256 hex strings,
        or None if the file does not exist or cannot be parsed.
    """
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"check-build-drift: WARNING — cannot read manifest "
            f"{manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None


def _collect_template_files(templates_dir: Path) -> list[Path]:
    """Return all .md files under the given templates directory (sorted).

    Args:
        templates_dir: Absolute path to the directory to scan.

    Returns:
        Sorted list of absolute Path objects for every .md file found.
    """
    if not templates_dir.is_dir():
        return []
    return sorted(templates_dir.rglob("*.md"))


def _collect_py_template_files(templates_dir: Path) -> list[Path]:
    """Return all .py files under the given templates directory (sorted).

    Used for the commit-guardian template tree, which contains Python scripts
    rather than Markdown agent templates.

    Args:
        templates_dir: Absolute path to the directory to scan.

    Returns:
        Sorted list of absolute Path objects for every .py file found.
    """
    if not templates_dir.is_dir():
        return []
    return sorted(
        f for f in templates_dir.rglob("*.py")
        if "__pycache__" not in f.parts
    )


def _make_manifest_key(template_path: Path, repo_root: Path) -> str:
    """Return the manifest key for a template file.

    Keys use forward slashes and are relative to the repo root, matching the
    format written by build.py's write_build_manifest().

    Args:
        template_path: Absolute path to the template file.
        repo_root: Absolute path to the repository root.

    Returns:
        Forward-slash relative path string used as the manifest dictionary key.
    """
    return template_path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# Template scanning (BP-100k-3 — exemption registry lives in _drift_exemptions)
# ---------------------------------------------------------------------------


def _scan_templates(
    template_files: list[Path],
    manifest: dict[str, str],
    repo_root: Path,
    exemptions: dict[str, str],
    family_prefix: str | None = None,
) -> _ScanResult:
    """Compare template hashes against the manifest, reporting uncomparables.

    Args:
        template_files: Absolute paths to the template files to check.
        manifest: The loaded build manifest (key -> recorded sha256 hex).
        repo_root: Repository root used to form relative manifest keys.
        exemptions: Valid declared-exemption map (key -> ground text) from
            ``_validate_exemption_registry``.
        family_prefix: Repo-root-relative directory prefix (e.g.
            ``"templates/agents"``) identifying which manifest keys belong
            to THIS family, so a manifest key whose file was deleted (and
            therefore never appears in ``template_files`` — ``rglob()``
            cannot return a path that no longer exists) can still be swept
            and reported as MISSING (BP-100k-6). ``None`` skips the
            missing-artifact sweep entirely (e.g. a caller with no natural
            family boundary).

    Returns:
        The scan outcome (see ``_ScanResult``). Prints one ``UNCOMPARABLE:``
        line per artifact absent from the manifest, and one
        ``UNCOMPARABLE: MISSING`` line per manifest key (within
        ``family_prefix``) recorded but absent from disk.
    """
    verified = 0
    uncomparable = 0
    gaps = 0
    violations: list[str] = []
    seen_keys: set[str] = set()

    for tpl_path in template_files:
        key = _make_manifest_key(tpl_path, repo_root)
        seen_keys.add(key)
        if key not in manifest:
            uncomparable += 1
            ground = exemptions.get(key)
            if ground:
                print(f"UNCOMPARABLE: EXEMPT {key} ground={ground}", file=sys.stderr)
            else:
                gaps += 1
                print(
                    f"UNCOMPARABLE: GAP {key} action=run build.py to register it",
                    file=sys.stderr,
                )
            continue

        current_hash = _sha256_of_file(tpl_path)
        recorded_hash = manifest[key]
        verified += 1
        if current_hash != recorded_hash:
            violations.append(key)

    # BP-100k-6: a manifest-recorded template whose file was deleted never
    # appears in template_files at all — _collect_template_files() /
    # _collect_py_template_files() use rglob(), which cannot return a path
    # that no longer exists, so the loop above never even sees it. Sweep
    # every manifest key belonging to this family (identified by
    # family_prefix, since the manifest is a single flat dict shared across
    # both template families plus non-hash metadata keys like
    # "output_mappings" and "package_root") that was never seen above and
    # is genuinely absent from disk.
    missing = 0
    if family_prefix is not None:
        prefix = family_prefix.rstrip("/") + "/"
        for key, value in manifest.items():
            if not isinstance(value, str) or not key.startswith(prefix):
                continue
            if key in seen_keys:
                continue
            if not (repo_root / key).exists():
                missing += 1
                print(
                    f"UNCOMPARABLE: MISSING {key} reason=recorded but not found on disk",
                    file=sys.stderr,
                )

    return _ScanResult(
        verified=verified, uncomparable=uncomparable, gaps=gaps, missing=missing, violations=violations
    )


def _print_blocked_block(violations: list[str]) -> None:
    """Print the BLOCKED diagnostic block for drifted templates.

    Args:
        violations: Manifest keys whose current hash differs from the
            recorded hash.
    """
    print(
        "\n[check-build-drift] BLOCKED — template(s) modified without "
        "re-running build.py:\n",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    print(
        "\nFix: re-run build.py to regenerate outputs and update the manifest,\n"
        "then stage the updated outputs alongside your template change.\n"
        "  cd leafcutter && python scripts/build.py --force\n",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Resolves the manifest via ``_resolve_manifest_path`` (layout-independent
    — see GE-118b docstring note above), then derives both template
    directories from the manifest's own location (``package_root =
    manifest_path.parent``) since they always live under the same package
    root the manifest was found in. Scans both template families —
    1. Agent templates (``templates/agents/``, ``.md`` files), and
    2. Commit-guardian templates (``templates/scripts/commit_guardian/``,
       ``.py`` files) —
    against the SAME exemption registry, then prints exactly one aggregate
    ``RESULT verified=<N> uncomparable=<M> drifted=<D> missing=<X>`` summary
    line combining both families (BP-100k-3; ``missing`` added BP-100k-6).

    Returns:
        0 when gaps == 0, drifted == 0, and missing == 0 (clean — a
        declared, grounded exemption does NOT block: BP-100k-3's three-way
        distinction of gap / declared exemption / clean pass collapses to
        two if stating a ground still gets the commit blocked, per
        BP-100k-3-i.yaml's own criterion, which permits any exempt count on
        a freshly built tree); 1 when drifted > 0 or missing > 0 (BLOCKED —
        a deleted, still-recorded template is drift, BP-100k-6); 2 when
        drifted == 0, missing == 0, and gaps > 0 (an undeclared, uncomparable
        artifact — the run skipped something with no stated ground and must
        not report as clean — AC-4), or when the manifest records a non-empty
        ``output_mappings_skipped_sections`` (a sibling section's Direction B
        enumeration is known to be incomplete). The RESULT line's
        ``uncomparable`` count still reports exempt + gap transparently; it
        does not by itself drive the verdict.
    """
    manifest_path, tried = _resolve_manifest_path(_HOOK_FILE)
    if manifest_path is None:
        _warn_manifest_not_found(tried)
        return 0

    manifest = _load_manifest(manifest_path)
    if manifest is None:
        print(
            "check-build-drift: WARNING — .build_manifest.json not found. "
            "Run build.py to generate it. Skipping drift check.",
            file=sys.stderr,
        )
        return 0

    # build.py records a PARTIAL output_mappings enumeration failure — one
    # section (e.g. agents/commands/workflows/hooks) could not be enumerated
    # while the rest of the manifest, including this hook's own Direction A
    # template_hashes, computed normally. This hook does not read
    # output_mappings itself (that is check_output_drift.py's job), but a
    # manifest recording an incomplete Direction B computation is evidence
    # the SAME build run may not be trustworthy, and reporting a clean
    # Direction A result while staying silent about a known-incomplete
    # sibling section is the identical "gate that cannot check everything
    # must not act as though it did" failure BP-100k-3/-5 exist to remove —
    # just surfacing through the sibling gate instead of the one that
    # actually owns the incomplete section. Honour it here too, exactly as
    # check_output_drift.py does.
    skipped_sections = manifest.get("output_mappings_skipped_sections") or []
    if skipped_sections:
        print(
            f"{_GATE_NAME}: BLOCKED - the build recorded {len(skipped_sections)} "
            f"output_mappings section(s) that could not be enumerated in this "
            f"same manifest, so this build run is not fully trustworthy. "
            f"Recorded cause(s): {'; '.join(skipped_sections)}. Re-run build.py "
            f"and address the cause(s); this gate will not report a clean run "
            f"while any part of the manifest is known to be incomplete.",
            file=sys.stderr,
        )
        return 2

    package_root = manifest_path.parent
    # repo_root == package_root == manifest_path.parent by construction: the
    # manifest is written into target_root (write_build_manifest() falls back
    # to package_root only when target_root is absent), and this hook found
    # the manifest via _resolve_manifest_path() — wherever it actually is IS
    # the base every key in it was computed relative to. No layout detection
    # needed (BP-100k-3-i follow-up: the git-based heuristic this replaced
    # failed open for any git-unavailable layout — see DECISION HISTORY).
    repo_root = package_root
    # Templates do NOT necessarily live under the manifest's own directory. The
    # manifest is written to target_root; on a consumer install the package is a
    # subdirectory of that (leafcutter-ai/), so "<manifest dir>/templates" does
    # not exist and this gate would scan nothing — reporting verified=0 with no
    # violations, which reads exactly like a clean run. Self-host hides it,
    # because package_root and target_root are the same directory there.
    #
    # write_build_manifest() records the offset as DATA under "package_root"
    # (empty string when they coincide). Read it rather than inferring the
    # layout from a directory name or a git probe — both fail open when wrong,
    # which is the failure mode this whole ticket exists to remove. Missing key
    # degrades to "" for manifests written before this field existed.
    package_offset = manifest.get("package_root", "") or ""
    templates_base = (repo_root / package_offset) if package_offset else repo_root
    templates_dir = templates_base / "templates" / "agents"
    cg_templates_dir = templates_base / "templates" / "scripts" / "commit_guardian"

    exemptions = _validate_exemption_registry(_load_exemption_registry(_GATE_NAME))

    agents_prefix = templates_dir.relative_to(repo_root).as_posix()
    cg_prefix = cg_templates_dir.relative_to(repo_root).as_posix()
    agents_result = _scan_templates(
        _collect_template_files(templates_dir), manifest, repo_root, exemptions,
        family_prefix=agents_prefix,
    )
    cg_result = _scan_templates(
        _collect_py_template_files(cg_templates_dir), manifest, repo_root, exemptions,
        family_prefix=cg_prefix,
    )

    verified = agents_result.verified + cg_result.verified
    uncomparable = agents_result.uncomparable + cg_result.uncomparable
    gaps = agents_result.gaps + cg_result.gaps
    missing = agents_result.missing + cg_result.missing
    violations = agents_result.violations + cg_result.violations

    if violations:
        _print_blocked_block(violations)

    # ``uncomparable`` stays the gaps+exempt total; ``exempt`` and ``gaps``
    # break it down so only GAPS drive the verdict and a non-zero gaps count is
    # never described as clean. Mirrors check_output_drift.py — the two gates
    # must report in the same vocabulary or a reader cannot compare their runs.
    # ``missing`` (BP-100k-6) breaks ``drifted`` down the same way ``exempt``
    # and ``gaps`` break ``uncomparable`` down: a hash mismatch (changed in
    # place) and a deletion (missing entirely) are both instances of
    # "on-disk content no longer matches what was recorded" — deletion is
    # the most complete form of drift there is — so ``drifted`` is their
    # total and ``missing`` names how many of that total are deletions.
    exempt_count = uncomparable - gaps
    drifted_total = len(violations) + missing
    print(
        f"{_GATE_NAME}: RESULT verified={verified} uncomparable={uncomparable} "
        f"exempt={exempt_count} gaps={gaps} drifted={drifted_total} "
        f"missing={missing}",
        file=sys.stderr,
    )

    if violations or missing:
        # A deleted, still-recorded template is the most complete form of
        # drift there is (BP-100k-6) — BLOCKED, same severity as a
        # hash-mismatch violation, never merely an uncomparable gap.
        return 1
    if gaps:
        return 2

    # A run that compared nothing must not exit as if it had compared
    # everything (BP-100k-3 it_requirements). verified == 0 with templates
    # present means the gate resolved no template to any manifest entry and is
    # structurally unable to detect drift.
    if manifest and verified == 0:
        print(
            f"{_GATE_NAME}: BLOCKED - compared 0 templates against a manifest "
            f"holding {len(manifest)} entr(ies). The gate could not verify "
            f"anything, so this run is not clean. Re-run build.py, or check "
            f"that the templates directory resolved for this layout is the one "
            f"the manifest describes.",
            file=sys.stderr,
        )
        return 2

    return 0


# ---------------------------------------------------------------------------
# Entry point (called by run_hook.py / pre-commit)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation, post-merge
#   defect fix]: build_helpers._compute_output_mappings() could silently drop
#   an entire output_mappings section (e.g. agents/commands/workflows/hooks)
#   while the rest of the SAME manifest — including this hook's own Direction
#   A template_hashes — still computed and wrote normally. Fixed at the
#   source: the reason is now recorded as manifest DATA
#   (output_mappings_skipped_sections). This hook reads that field right
#   after loading the manifest and returns 2 (BLOCKED) when it is non-empty,
#   mirroring check_output_drift.py's identical new check — a build run
#   known to be partially incomplete must not be reported clean by either
#   gate, even the one whose own scanned trees are unaffected.
# - 2026-08-19 [python-coder/EPIC-BuildPipelinePhantomRemediation/08, r1-r3]:
#   BP-100k-3 in three rounds. r1: an absent-from-manifest template is
#   reported UNCOMPARABLE: EXEMPT <key> ground=<g> or GAP <key>
#   action=run build.py to register it (never a silent INFO+exit-0);
#   exemption registry is DATA in commit_guardian.json's
#   drift_gate_exemption_registry (shared with check_output_drift.py, AC-5,
#   or HOOK_TEST_CONFIG for testing; groundless entries rejected, fall
#   through to GAP); one aggregate RESULT verified=<N> uncomparable=<M>
#   drifted=<D> line covering both template families; removed check_drift()
#   (zero external callers — grep-audited). r2: reverted a git-based
#   resolve_repo_root() heuristic (failed open for any git-unavailable
#   layout) for the real invariant — manifest_path.parent IS the base every
#   key was computed relative to, by construction, no detection needed (see
#   build_helpers.py write_build_manifest() history for the write side). r3:
#   verdict now keys off GAPS, not total uncomparable — a declared, grounded
#   exemption no longer blocks (BP-100k-3-i.yaml permits any exempt count on
#   a fresh tree; only ungrounded gaps must be zero); RESULT's uncomparable
#   count is still exempt+gap, reported but not verdict-driving.
# - 2026-08-13 [python-coder/GE-118b]: Fixed manifest resolution. _REPO_ROOT /
#   _MANIFEST_PATH / _TEMPLATES_DIR / _COMMIT_GUARDIAN_TEMPLATES_DIR were all
#   computed from Path(__file__).resolve().parents[2] / "leafcutter" / ... —
#   a hardcoded package-directory segment. Deployed under
#   .leafcutter/scripts/commit_guardian/, .resolve() follows the symlink so
#   parents[2] lands on the workspace root, and "leafcutter" never matches
#   the real package directory (this repo's is "leafcutter-ai"), so the
#   computed paths never existed and the gate silently no-op'd (main
#   checkout AND worktrees). Fix: _resolve_manifest_path() searches git
#   toplevel (via the sibling _resolve_root.find_project_root(), reused
#   rather than duplicated as a fresh subprocess call), the
#   structurally-derived workspace root, and that root's immediate
#   subdirectories — never a hardcoded name; both template dirs are then
#   derived from the found manifest's own parent (package_root) instead of a
#   separate hardcoded constant. A missing manifest now prints every
#   absolute path tried. check_output_drift.py received the identical fix
#   (the AC calls out that both hooks share the bug and must share the fix).
# - 2026-05-13 00:00 [python-coder/ticket-37]: Created module.
#   Content-hash (SHA-256) chosen over mtime because git checkouts
#   reset mtime, making mtime unreliable in multi-worktree setups.
#   .build_manifest.json written by build.py's write_build_manifest()
#   is the ground truth; this hook reads it and compares.
#   Scope intentionally limited to templates/agents/ per ticket-37 scope
#   decision; other template dirs added via follow-up ticket.
# - 2026-06-18 [workflow-architect/EPIC-Acpatternenforcementismechanically]:
#   Extended to cover templates/scripts/commit_guardian/ (.py files).
#   Added _COMMIT_GUARDIAN_TEMPLATES_DIR constant and
#   _collect_py_template_files() collector. main() now runs two drift
#   passes: agents (.md) and commit-guardian (.py). The file_collector
#   parameter on check_drift() allows per-tree extension without
#   duplicating the hash-comparison logic.
#   Rationale: the ACS-500f post-epic spot-check found that hook script
#   edits in the deployed scripts/commit_guardian/ tree went undetected
#   because check_build_drift only hashed templates/agents/. Adding
#   commit-guardian closes this drift blind spot.
# ====================================================================
