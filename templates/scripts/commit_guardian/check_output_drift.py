"""
MODULE: check_output_drift
GOAL: Pre-commit hook — blocks the commit when a built output file in
    .claude/agents/, .claude/skills/, .claude/commands/, or .agents/rules/
    has been directly edited without editing its source-of-truth template.
BUSINESS CONTEXT: The leafcutter package compiles templates into
    output files. If a developer (or agent) edits a built output directly
    instead of the template, the change will be silently overwritten the next
    time build.py runs. This hook (Direction B detection) catches that class
    of drift at commit time. Direction A (template edited without re-running
    build.py) is handled by check_build_drift.py.

OPERATIONAL NOTE — first-time enablement in an existing codebase:
    Before turning this hook on in a codebase that has been edited freely for
    a while, audit pre-existing drift against a clean branch (e.g. compare
    every output_mappings entry's on-disk hash against the template's expected
    output). If any pre-existing drift exists (template and output diverged
    BEFORE the manifest was captured), resolve it FIRST — either by
    regenerating outputs from templates (`build.py --force`) or by promoting
    the richer output back into the template — BEFORE the first epic commit.
    Otherwise the first commit on the next epic will hit drift errors that
    aren't caused by the in-flight work. This bit EPIC-EmbeddedArchDiagrams-
    Hardening tickets 06+07: `.claude/skills/README.md` had pre-existing
    drift; the supervisor had to promote the output back to template mid-
    flight to clear it.
    See retro: docs/retrospectives/EPIC-EmbeddedArchDiagramsHardening.md.
ARCHITECTURE: Reads the ``output_mappings`` section of the
    ``.build_manifest.json`` written by build.py (build_helpers.
    write_build_manifest) at ``package_root / ".build_manifest.json"`` after
    each successful build run. For each staged output file listed in
    output_mappings, computes the SHA-256 of the current on-disk content and
    compares it against the ``expected_output_hash`` recorded at last build
    time. If a mismatch is found the hook exits 1 and names both the
    offending output file and the template the developer should have edited
    instead. Absent manifest, absent output_mappings section, or unknown
    output files all produce a warning (not a block) to avoid false
    positives on fresh clones or intentional one-off outputs.

    MANIFEST RESOLUTION (GE-118b): package_root's directory name is not
    knowable in advance (this repo's own checkout is "leafcutter-ai"; a
    consumer install may name it anything), so the manifest path is never
    built from a hardcoded package-directory segment. See
    ``_candidate_manifest_roots`` below for the layout-independent search
    order (git toplevel, then the structurally-derived workspace root, then
    that root's immediate subdirectories).

    UNCOMPARABLE REPORTING (BP-100k-3): an output file absent from
    output_mappings is reported as a declared exemption (``UNCOMPARABLE:
    EXEMPT <key> ground=<ground>``) or a coverage gap (``UNCOMPARABLE: GAP
    <key> action=run build.py to register it``) — never a silent INFO line.
    Both are counted in the ``RESULT verified=<N> uncomparable=<M>
    drifted=<D> missing=<X>`` line, but only GAPS drive the exit verdict (0
    clean / 1 drift / 2 gap-only — see ``main()``): a declared, grounded
    exemption is reported but never blocks, per BP-100k-3-i.yaml's own
    criterion, which permits any exempt count on a freshly built tree. The
    exemption registry is read from ``drift_gate_exemption_registry`` in
    ``commit_guardian.json`` (colocated with this hook) or
    ``HOOK_TEST_CONFIG`` for testing — the SAME registry check_build_drift.py
    reads (AC-5). An entry with no non-blank ``ground`` is rejected
    (``REJECTED EXEMPTION ENTRY: <key> reason=no ground stated``) and falls
    through to the GAP form.

    MISSING-OUTPUT REPORTING (BP-100k-6): an output_mappings key whose file
    has been deleted from disk is a THIRD, distinct case from the two above
    — the key is neither ungrounded (no exemption question applies) nor
    unregistered (it IS in output_mappings). It is reported as
    ``UNCOMPARABLE: MISSING <key> reason=recorded but not found on disk``,
    counted in its own ``missing=<X>`` RESULT field (never folded into
    ``verified`` or ``uncomparable``), and always drives a non-clean,
    non-zero exit — deletion is the most complete form of drift there is.
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
        "_drift_exemptions module not found alongside check_output_drift.py; "
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
_GATE_NAME = "check-output-drift"


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
        "check-output-drift: WARNING — .build_manifest.json not found. "
        f"Tried:\n  {tried_str}\n"
        "Run build.py to generate it. Skipping output drift check.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file's content.

    Line endings are normalised to LF before hashing so that the result
    matches the hash stored in the build manifest, which is computed from
    the template compiler's LF-only output.  On Windows, git may write CRLF
    to disk even when the manifest was generated with LF content; normalising
    here avoids spurious drift violations on Windows workstations.

    Args:
        path: Absolute path to the file to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    raw = path.read_bytes()
    normalised = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalised).hexdigest()


def _load_manifest(manifest_path: Path) -> dict | None:
    """Load the build manifest JSON file.

    Args:
        manifest_path: Absolute path to .build_manifest.json.

    Returns:
        Parsed manifest dict, or None if the file does not exist or cannot be
        parsed.
    """
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"check-output-drift: WARNING — cannot read manifest "
            f"{manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None


def _collect_output_files(output_dirs: list[Path]) -> list[Path]:
    """Return all files under the managed output directories (sorted).

    ``__pycache__`` is excluded — a compiled Python bytecode cache is not
    source content build.py deploys; it is generated (and re-generated
    non-reproducibly, differing by Python version and mtime) whenever a
    deployed skill script is imported. Comparing it would be an inherently
    unstable target, permanently reporting drift the first time any deployed
    script is executed once. Mirrors the same exclusion
    ``build_phases._skill_deploy_files()`` applies on the write side, so
    neither side ever tries to compare it.

    Args:
        output_dirs: List of absolute paths to output directories to scan.

    Returns:
        Sorted list of absolute Path objects for every real file found.
    """
    seen: set[Path] = set()
    for d in output_dirs:
        if d.is_dir():
            seen.update(d.rglob("*"))
    return sorted(
        f for f in seen if f.is_file() and "__pycache__" not in f.parts
    )


def _derive_scan_dirs(
    repo_root: Path, output_mappings: dict, floor_dirs: list[Path]
) -> list[Path]:
    """Return every directory the gate must scan for deployed outputs.

    The scan set is the union of two sources:

    1. The parent directory of every key the manifest records. This is what
       makes the manifest and the gate structurally unable to disagree about
       WHERE outputs live: if the build records an output, its directory is
       scanned by construction, and any unrecorded sibling sitting in that
       same directory is therefore reported as a gap rather than ignored.
    2. ``floor_dirs`` — the canonical tool directories, retained so that an
       empty or truncated manifest cannot shrink the scan to nothing and
       thereby manufacture a clean run.

    Deriving (1) rather than hardcoding it is the direct fix for BP-100k-2's
    failure mode: ``.agents/rules`` was hardcoded here while the build wrote
    to ``<output_root>/.agents/rules``, so 16 real deployed files were scanned
    by no gate at all and 16 manifest keys were never looked up. Because
    ``_collect_output_files`` skips directories that do not exist, that
    disagreement produced neither a GAP nor an EXEMPT line — it was silent.
    A hardcoded list can drift from the build; a derived one cannot.

    Args:
        repo_root: Absolute path every manifest key is relative to.
        output_mappings: The manifest's ``output_mappings`` dict.
        floor_dirs: Canonical directories always scanned regardless of
            manifest contents.

    Returns:
        Sorted list of unique absolute directory paths to scan.
    """
    dirs: set[Path] = set(floor_dirs)
    for key in output_mappings:
        candidate = (repo_root / key).parent
        # Defensive: a malformed key such as an absolute path or one using
        # ".." must not widen the scan outside the tree the manifest describes.
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            continue
        dirs.add(candidate)
    return sorted(dirs)


def _make_output_key(output_path: Path, repo_root: Path) -> str:
    """Return the manifest output_mappings key for an output file.

    Keys use forward slashes and are relative to the repo root, matching the
    format written by build.py's _compute_output_mappings().

    Args:
        output_path: Absolute path to the output file.
        repo_root: Absolute path to the repository root.

    Returns:
        Forward-slash relative path string used as the output_mappings key.
    """
    return output_path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# Output scanning (BP-100k-3 — exemption registry lives in _drift_exemptions)
# ---------------------------------------------------------------------------


def _scan_output_files(
    output_files: list[Path],
    output_mappings: dict,
    repo_root: Path,
    exemptions: dict[str, str],
) -> _ScanResult:
    """Compare output hashes against output_mappings, reporting uncomparables.

    Args:
        output_files: Absolute paths to the output files to check.
        output_mappings: The manifest's output_mappings section.
        repo_root: Repository root used to form relative manifest keys.
        exemptions: Valid declared-exemption map (key -> ground text) from
            ``_validate_exemption_registry``.

    Returns:
        The scan outcome (see ``_ScanResult``). Prints one ``UNCOMPARABLE:``
        line per output absent from output_mappings, and one
        ``UNCOMPARABLE: MISSING`` line per output_mappings key recorded but
        absent from disk (BP-100k-6).
    """
    verified = 0
    uncomparable = 0
    gaps = 0
    violations: list[tuple[str, str]] = []
    seen_keys: set[str] = set()

    for out_path in output_files:
        try:
            out_key = _make_output_key(out_path, repo_root)
        except ValueError:
            # File outside repo root — skip silently.
            continue
        seen_keys.add(out_key)

        if out_key not in output_mappings:
            uncomparable += 1
            ground = exemptions.get(out_key)
            if ground:
                print(f"UNCOMPARABLE: EXEMPT {out_key} ground={ground}", file=sys.stderr)
            else:
                gaps += 1
                print(
                    f"UNCOMPARABLE: GAP {out_key} action=run build.py to register it",
                    file=sys.stderr,
                )
            continue

        entry = output_mappings[out_key]
        expected_hash = entry.get("expected_output_hash", "")
        template_key = entry.get("template", "<unknown>")

        if not out_path.exists():
            # Defensive only: output_files is built from a real rglob() over
            # on-disk files, so a path collected there normally still exists
            # a moment later. The deletion case BP-100k-6 exists for — a
            # manifest-recorded key whose file is gone — never reaches this
            # loop at all, because rglob() simply never returns a deleted
            # file; that case is handled by the missing-key sweep below.
            print(
                f"check-output-drift: INFO — {out_key} listed in manifest but "
                "missing on disk; skipping.",
                file=sys.stderr,
            )
            continue

        try:
            current_hash = _sha256_of_file(out_path)
        except OSError as exc:
            print(
                f"check-output-drift: WARNING — cannot read {out_key}: {exc}; skipping.",
                file=sys.stderr,
            )
            continue

        verified += 1
        if current_hash != expected_hash:
            violations.append((out_key, template_key))

    # BP-100k-6: a manifest-recorded key whose file was deleted never appears
    # in output_files at all (rglob() cannot return a path that no longer
    # exists), so it is invisible to the loop above no matter what it does.
    # Sweep every output_mappings key that was never seen there and report it
    # as its own MISSING verdict — never folded into "verified" (it plainly
    # was not) or "uncomparable"/"gaps" (a declared-and-deleted artifact
    # demands restoring the file or removing the record, not registering it).
    missing = 0
    for key in output_mappings:
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


def _load_output_mappings(manifest_path: Path) -> dict | None:
    """Load the manifest and return its output_mappings section.

    Centralises the two legacy warn-and-skip edge cases (manifest absent;
    output_mappings section absent) so ``check_output_drift()`` and
    ``main()`` share one implementation instead of two copies.

    Args:
        manifest_path: Path to .build_manifest.json written by build.py.

    Returns:
        The output_mappings dict, or None if the manifest or the section is
        absent/malformed (a WARNING is printed to stderr in either case).
    """
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        print(
            "check-output-drift: WARNING — .build_manifest.json not found. "
            "Run build.py to generate it. Skipping output drift check.",
            file=sys.stderr,
        )
        return None

    output_mappings = manifest.get("output_mappings")
    if not isinstance(output_mappings, dict):
        print(
            "check-output-drift: WARNING — manifest has no output_mappings section. "
            "Re-run build.py to regenerate the manifest with Direction B support. "
            "Skipping output drift check.",
            file=sys.stderr,
        )
        return None

    return output_mappings


def _print_blocked_block(violations: list[tuple[str, str]]) -> None:
    """Print the BLOCKED diagnostic block for directly-edited outputs.

    Args:
        violations: (output_key, template_key) pairs whose current hash
            differs from the expected hash.
    """
    print(
        "\n[check-output-drift] BLOCKED — output file(s) were directly edited "
        "instead of their source templates:\n",
        file=sys.stderr,
    )
    for out_key, tpl_key in violations:
        print(f"  output:   {out_key}", file=sys.stderr)
        print(f"  template: {tpl_key}", file=sys.stderr)
        print(file=sys.stderr)
    print(
        "Fix: Edit the template at the path shown above, re-run\n"
        "  build.py  (or: python leafcutter/scripts/build.py --force)\n"
        "then stage both the template and the updated output.\n",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_output_drift(
    output_dirs: list[Path],
    manifest_path: Path,
    repo_root: Path,
) -> int:
    """Compare on-disk output hashes against the build manifest output_mappings.

    THE ONE CONTRACT (BP-100k-3 remediation, 2026-08-25): this function IS the
    scan+report+verdict implementation ``main()`` runs — ``main()`` only
    resolves the manifest path and derives ``output_dirs`` before calling this
    function by keyword, exactly as any other direct caller would. Before this
    fix, ``main()`` duplicated this entire scan inline and never called this
    function at all, so this function's own body still implemented an older,
    permissive contract (return 0 even with undeclared gaps; no RESULT line).
    A caller that imported and invoked ``check_output_drift()`` directly —
    this module's own docstring named ``test_bp100_drift_docs_compile.py`` as
    exactly such a caller — got a silent "clean" verdict on a tree with an
    unrecorded, undeclared output, while running the same hook as a subprocess
    via ``main()`` correctly blocked. Two contracts for the same gate is
    precisely how the next drift-gate regression would hide: whichever code
    path a caller happens to take decides whether drift is caught at all.

    For each output file under ``output_dirs``, looks up its expected hash in
    ``manifest["output_mappings"]``. Reports a drift violation when the current
    on-disk content hash does not match the expected hash. An output absent
    from output_mappings is reported per the BP-100k-3 UNCOMPARABLE contract
    (declared exemption or coverage gap — see module docstring) rather than a
    silent INFO line, and is counted in the same aggregate ``RESULT
    verified=<N> uncomparable=<M> exempt=<E> gaps=<G> drifted=<D> missing=<X>``
    line ``main()`` prints — this function prints it directly so a direct
    caller sees the identical summary a pre-commit run would. A key IN
    output_mappings whose file is absent from disk is reported as its own
    ``UNCOMPARABLE: MISSING`` verdict (BP-100k-6) — deletion is drift too,
    and the most complete form of it: never folded into ``verified`` (it
    plainly was not verified) or into ``uncomparable``/``gaps`` (a declared
    exemption or coverage gap is a registration question; a deleted,
    still-recorded artifact is a content question with a different remedy —
    restore the file or remove the record).

    Edge-case handling:
    - Absent manifest or output_mappings section: warn and return 0 (no
      false-block on a fresh clone / old manifest format) — see
      ``_load_output_mappings``.
    - Output file in output_mappings but missing on disk: reported as
      ``UNCOMPARABLE: MISSING`` and counted in ``missing`` (BP-100k-6); never
      described as clean, never counted as verified.
    - A run that compared zero artifacts while the manifest records at least
      one mapping is treated as "could not verify anything" (BLOCKED, return
      2), not as clean — see the ``verified == 0`` floor below.

    Args:
        output_dirs: Directories to scan for output files.
        manifest_path: Path to .build_manifest.json written by build.py.
        repo_root: Repository root used to form relative manifest keys.

    Returns:
        0 when gaps == 0, drifted == 0, and missing == 0 (clean — a
        declared, grounded exemption does NOT block; see module docstring);
        1 when drifted > 0 or missing > 0 (BLOCKED — a recorded-but-absent
        output is drift, BP-100k-6); 2 when drifted == 0, missing == 0, and
        gaps > 0 (an undeclared uncomparable artifact — AC-4), or when the
        scan verified zero artifacts against a non-empty manifest (see
        DECISION HISTORY).
    """
    output_mappings = _load_output_mappings(manifest_path)
    if output_mappings is None:
        return 0

    output_files = _collect_output_files(output_dirs)

    exemptions = _validate_exemption_registry(_load_exemption_registry(_GATE_NAME))
    result = _scan_output_files(output_files, output_mappings, repo_root, exemptions)

    if result.violations:
        _print_blocked_block(result.violations)

    # ``uncomparable`` is retained as the gaps+exempt total so BP-100k-3's
    # "states a non-zero count of artifacts it could not compare" clause reads
    # off one number, while ``exempt`` and ``gaps`` break that total down.
    # Without the breakdown the two counts were indistinguishable in the
    # summary, which is what put BP-100k-3 ("a non-zero uncomparable count
    # must not describe the run as clean") in apparent contradiction with
    # BP-100k-3-i ("each gate reports the run as clean and exits zero" on a
    # freshly built tree that legitimately carries grounded exemptions).
    # Reporting them separately lets both hold at once: only GAPS drive the
    # verdict, and a non-zero gaps count is never described as clean.
    exempt_count = result.uncomparable - result.gaps
    # ``drifted`` is the total count of artifacts whose on-disk content no
    # longer matches what was recorded — a hash mismatch (changed in place)
    # AND a deletion (missing entirely) are both instances of that (BP-100k-6:
    # "deletion is the most complete form of drift there is"). ``missing`` is
    # then reported as its own field breaking that total down, mirroring the
    # existing ``uncomparable = gaps + exempt`` breakdown pattern (BP-100k-3)
    # rather than a sixth, independent bucket.
    drifted_total = len(result.violations) + result.missing
    print(
        f"{_GATE_NAME}: RESULT verified={result.verified} "
        f"uncomparable={result.uncomparable} exempt={exempt_count} "
        f"gaps={result.gaps} drifted={drifted_total} "
        f"missing={result.missing}",
        file=sys.stderr,
    )

    if result.violations or result.missing:
        # A deleted, still-recorded output is the most complete form of
        # drift there is (BP-100k-6) — reported with the same BLOCKED
        # severity as a hash-mismatch violation, never merely as an
        # uncomparable gap (which is a coverage question, not a content
        # question).
        return 1
    if result.gaps:
        return 2

    # A run that compared nothing must not exit as if it had compared
    # everything (BP-100k-3 it_requirements). Reaching here with verified == 0
    # while the manifest DOES record outputs means every recorded mapping
    # failed to resolve to a file on disk — the gate is structurally unable to
    # detect drift, and saying "clean" would be a lie of exactly the kind this
    # gate exists to catch. Observed live at verified=0 against 275 recorded
    # mappings before this floor existed. This floor is safe for a direct
    # caller scanning a deliberately narrow ``output_dirs`` subset too: every
    # existing direct caller's fixture manifest only records mappings for the
    # files it places under that same subset, so verified is never 0 there
    # unless the scan is genuinely unable to compare anything.
    if output_mappings and result.verified == 0:
        print(
            f"{_GATE_NAME}: BLOCKED - compared 0 artifacts while the build "
            f"manifest records {len(output_mappings)} output mapping(s). The "
            f"gate could not verify anything, so this run is not clean. "
            f"Re-run build.py, or check that the manifest at {manifest_path} "
            f"describes the tree being scanned.",
            file=sys.stderr,
        )
        return 2

    return 0


def main() -> int:
    """Entry point for the pre-commit hook.

    Resolves the manifest via ``_resolve_manifest_path`` (layout-independent
    — see GE-118b docstring note above), checks the three conditions that are
    specific to running as the hook itself (manifest wholly absent; build.py
    recorded an ``output_mappings_error`` instead of computing mappings;
    build.py recorded a non-empty ``output_mappings_skipped_sections`` — a
    PARTIAL enumeration failure limited to one section, e.g. agents/commands/
    workflows/hooks, while the rest of ``output_mappings`` still computed
    normally), then derives the output directories to scan and DELEGATES the
    actual scan+report+verdict to ``check_output_drift()`` — the single
    shared implementation direct callers use too (see that function's
    docstring for why this delegation is the fix, not an optimisation).

    Returns:
        0 when gaps == 0, drifted == 0, and missing == 0 (clean — a
        declared, grounded exemption does NOT block; see module docstring);
        1 when drifted > 0 or missing > 0 (BLOCKED — a recorded-but-absent
        output is drift, BP-100k-6); 2 when drifted == 0, missing == 0, and
        gaps > 0 (an undeclared uncomparable artifact — AC-4), or when
        build.py recorded an ``output_mappings_error`` or a non-empty
        ``output_mappings_skipped_sections``. ``uncomparable`` in the RESULT
        line is still exempt + gap, reported but not verdict-driving.
    """
    manifest_path, tried = _resolve_manifest_path(_HOOK_FILE)
    if manifest_path is None:
        _warn_manifest_not_found(tried)
        return 0

    # build.py records the reason output_mappings could not be computed rather
    # than leaving an empty dict behind for the gate to misread as "nothing to
    # police". Honour it: Direction B is unavailable, so this run cannot be
    # described as clean no matter what the scan finds.
    manifest_for_error = _load_manifest(manifest_path) or {}
    mappings_error = manifest_for_error.get("output_mappings_error") or ""
    if mappings_error:
        print(
            f"{_GATE_NAME}: BLOCKED - the build could not compute "
            f"output_mappings, so no deployed artifact can be compared "
            f"against its template. Recorded cause: {mappings_error}. "
            f"Re-run build.py and address the cause; this gate will not "
            f"report a clean run while Direction B detection is unavailable.",
            file=sys.stderr,
        )
        return 2

    # build.py also records a PARTIAL failure — one section of output_mappings
    # (e.g. agents/commands/workflows/hooks) could not be enumerated while the
    # rest of the computation completed and returned a normal-looking dict.
    # Unlike ``output_mappings_error`` above, ``output_mappings`` is NOT empty
    # here, so nothing else in this function would ever notice the gap: every
    # file under the skipped section's directories would simply never appear
    # as a key, and an absent directory means ``_collect_output_files`` finds
    # nothing there to scan either — silent on both ends, exactly the shape
    # BP-100k-3 forbids. Honour it the same way: BLOCKED, not clean.
    skipped_sections = manifest_for_error.get("output_mappings_skipped_sections") or []
    if skipped_sections:
        print(
            f"{_GATE_NAME}: BLOCKED - the build could not enumerate "
            f"output_mappings for {len(skipped_sections)} section(s), so this "
            f"manifest is partial and no deployed artifact in those sections "
            f"can be compared against its template. Recorded cause(s): "
            f"{'; '.join(skipped_sections)}. Re-run build.py and address the "
            f"cause(s); this gate will not report a clean run while any "
            f"section of Direction B detection is incomplete.",
            file=sys.stderr,
        )
        return 2

    # Load best-effort ONLY to derive the scan set. An absent or malformed
    # manifest must NOT short-circuit here: main()'s contract is that it always
    # hands a directory list to check_output_drift(), which owns the
    # manifest-absent warning and the verdict. Returning early instead meant a
    # resolved-but-unreadable manifest made the gate scan nothing while never
    # entering the function that reports what it scanned —
    # tests/test_build_artifact_parity.py exists to catch exactly that
    # ("main() never reached check_output_drift(); the drift gate would scan
    # nothing"), and it caught this.
    output_mappings = _load_output_mappings(manifest_path) or {}

    # repo_root == manifest_path.parent by construction: the manifest is
    # written into target_root (write_build_manifest() falls back to
    # package_root only when target_root is absent), and this hook found the
    # manifest via _resolve_manifest_path() — wherever it actually is IS the
    # base every key in it was computed relative to. No layout detection
    # needed (BP-100k-3-i follow-up: the git-based heuristic this replaced
    # failed open for any git-unavailable layout — see DECISION HISTORY).
    repo_root = manifest_path.parent
    # Floor only — the authoritative scan set is derived from the manifest's
    # own keys (see _derive_scan_dirs). Listing a directory here can only ADD
    # coverage, never define it, so this list drifting from the build is no
    # longer able to open a hole the way the hardcoded ".agents/rules" entry
    # did (BP-100k-2).
    floor_dirs = [
        repo_root / ".claude" / "agents",
        repo_root / ".claude" / "skills",
        repo_root / ".claude" / "commands",
        repo_root / ".claude" / "hooks",
        repo_root / ".claude" / "workflows",
    ]
    output_dirs = _derive_scan_dirs(repo_root, output_mappings, floor_dirs)

    return check_output_drift(
        output_dirs=output_dirs,
        manifest_path=manifest_path,
        repo_root=repo_root,
    )


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
#   an entire section (e.g. agents/commands/workflows/hooks, when
#   package_root lacks a full scripts/ tree) while still returning a normal-
#   looking, non-empty output_mappings dict — a manifest that never described
#   that section, indistinguishable from a genuinely-clean one. Fixed at the
#   source by recording the reason as manifest DATA
#   (output_mappings_skipped_sections, the per-section analogue of
#   output_mappings_error). main() now reads that field immediately after the
#   existing output_mappings_error check and returns 2 (BLOCKED) when it is
#   non-empty, before deriving output_dirs or calling check_output_drift() —
#   the same "cannot report clean while a required computation is known to be
#   incomplete" posture as the output_mappings_error branch immediately above
#   it.
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation, adversarial
#   review remediation]: Removed the two-contract split an adversarial review
#   found: main() reimplemented the whole scan inline and NEVER called
#   check_output_drift(), so that function's body still shipped the r1
#   "legacy 0/1 contract preserved for direct callers" compromise noted below
#   — permissive (0 even with undeclared gaps, no RESULT line) — while main()
#   (the pre-commit hook's actual entry point) had already moved on to the
#   tri-state BP-100k-3 contract. A caller that imported and called
#   check_output_drift() directly (test_bp100_drift_docs_compile.py, named in
#   this function's own docstring) got a silent clean verdict on a gap that
#   the real hook would have blocked. Fix: check_output_drift() IS now the
#   scan+report+verdict implementation; main() only resolves the manifest and
#   derives output_dirs, then calls check_output_drift() by keyword. Verified
#   the three real call sites in test_bp100_drift_docs_compile.py (all fixture
#   manifests have output_mappings covering every file in their fixture
#   output_dirs, so the added verified==0 floor and gap detection do not
#   change their expected 0/1 results) before making the change, per the
#   Contract-Shrinkage Guard.
# - 2026-08-19 [python-coder/EPIC-BuildPipelinePhantomRemediation/08, r1-r3]:
#   BP-100k-3 in three rounds. r1: an absent-from-output_mappings file is
#   reported UNCOMPARABLE: EXEMPT <key> ground=<g> or GAP <key>
#   action=run build.py to register it (never a silent INFO+exit-0); exemption
#   registry is DATA in commit_guardian.json's drift_gate_exemption_registry
#   (shared with check_build_drift.py, AC-5, or HOOK_TEST_CONFIG for testing;
#   groundless entries rejected, fall through to GAP); one aggregate RESULT
#   verified=<N> uncomparable=<M> drifted=<D> line; check_output_drift()'s
#   legacy 0/1 contract preserved for direct callers (e.g.
#   test_bp100_drift_docs_compile.py). r2: reverted a git-based
#   resolve_repo_root() heuristic (failed open for any git-unavailable
#   layout) for the real invariant — manifest_path.parent IS the base every
#   key was computed relative to, by construction, no detection needed (see
#   build_helpers.py write_build_manifest() history for the write side). r3:
#   verdict now keys off GAPS, not total uncomparable — a declared, grounded
#   exemption no longer blocks (BP-100k-3-i.yaml permits any exempt count on
#   a fresh tree; only ungrounded gaps must be zero); RESULT's uncomparable
#   count is still exempt+gap, reported but not verdict-driving.
# - 2026-08-13 [python-coder/GE-118b]: Fixed manifest resolution — hardcoded
#   "leafcutter" package-segment paths never matched this repo's real
#   directory name, so the gate silently no-op'd everywhere. Fix:
#   _resolve_manifest_path() searches git toplevel, the structurally-derived
#   workspace root, and its subdirectories — no hardcoded name. Shared with
#   check_build_drift.py.
# - 2026-05-18 [commit/EPIC-GlossaryAutomation]: _sha256_of_file normalises
#   CRLF->LF before hashing (Windows git checkouts wrote CRLF against an
#   LF-based manifest hash, causing spurious drift).
# - 2026-05-15 [retro/EPIC-EmbeddedArchDiagramsHardening]: Added the
#   OPERATIONAL NOTE above on auditing pre-existing drift before first
#   enabling this hook in an unguarded codebase (docs/retrospectives/
#   EPIC-EmbeddedArchDiagramsHardening.md).
# - 2026-05-15 [python-coder/TICKET-20260515]: Created module — Direction B
#   companion to check_build_drift.py's Direction A. Warn-and-skip on every
#   edge case (absent manifest/output_mappings, unknown/unreadable files);
#   exit 1 only on an actual hash mismatch against a registered output.
# ====================================================================
