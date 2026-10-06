"""
MODULE: scripts/commit_guardian/check_done_proof.py
GOAL: Enforce mechanical proof-of-done at two layers: a fast static pre-commit
    check (covers-tag PRESENCE only) and an authoritative CI check that runs
    the full verify_done_eligible oracle to confirm every done AC is backed by
    a passing test.
BUSINESS CONTEXT: BO-2500b mandates that no AC may reach work_status:done without
    a covers-tagged, passing test. Pre-commit (BO-2500b-1) is the fast developer
    loop — it checks only that a ``# covers: <ac_id>`` tag EXISTS somewhere in
    the test tree for every newly-done AC (static scan, no pytest). CI (BO-2500b-2)
    is the authoritative backstop: it calls verify_done_eligible for every done AC
    in the store and requires every linked test to PASS — so --no-verify commits
    and hook-config-less worktrees (BO-2500b-1-i) are still caught before merge.
ARCHITECTURE: Four public symbols consumed by tests and the CLI:
    check_staged_done_proofs(staged_yaml_paths, *, test_root) -> list[dict]
        STATIC pre-commit check. Scans test_root for covers tags; returns
        violation dicts for done ACs that have no tag. No subprocess calls.
        Level-aware (BO-2500b-1-ii): a done L0/L1 composite is proven by its
        covered_by children being themselves done-and-covered (resolved via
        _find_ac_root/_resolve_child_ac/_unproven_composite_children), not by
        a covers tag naming the composite's own id — that tag may never
        legitimately exist. A composite with any unproven child is still a
        violation naming that child; composites are never skipped
        unconditionally. L2/L3 leaves keep the original direct-tag check.
        On that leaf path only, ACs with ``test_required: false`` are silently
        exempted — same exemption semantics as the two CI functions below, kept
        in parity so a documentation-only AC does not pass CI while failing
        pre-commit. The exemption waives the direct-tag obligation; it does not
        waive a composite's child-derivation obligation, which is why the level
        branch is evaluated first.
    check_all_done_acs(*, ac_root, test_root) -> list[dict]
        CI-authoritative check. Calls verify_done_eligible (from done_proof)
        for every done AC under ac_root; returns violation dicts for ineligible
        ACs. ACs with ``test_required: false`` are silently exempted — they do
        not require a covers-tagged test (documentation/prompt-convention ACs).
        Invokes pytest as a subprocess via the done_proof engine.
    check_changed_done_acs(changed_yaml_paths, *, ac_root, test_root) -> list[dict]
        PR-scoped CI check. Calls verify_done_eligible only for done ACs in the
        provided changed_yaml_paths list; never scans the full store. ACs with
        ``test_required: false`` are silently exempted from the covers-tag
        mandate. Makes it safe to promote to a required gate without failing on
        legacy done ACs that predate the covers-tag mandate (BO-2500b-3).
    main(argv) -> int
        CLI entry point. --mode precommit (default), --mode ci, or
        --mode ci-changed (with --base <ref>, default origin/main).

    Root resolution: uses _resolve_root.find_project_root() for project-root
    defaults in main(); the done_proof import's own sibling-directory lookup
    (BP-100n-4-ii-ii) lives in the sibling module _ac_store_locator.py — safe
    because the directory relationship is fixed in both source and deployed
    layouts. Staged-AC-yaml-path resolution similarly lives in the sibling
    module _staged_ac_yaml_paths.py.

    Error handling: all I/O wrapped per the Error Handling Policy (Rules 1-3).
    Pre-commit hook fail-open: the if __name__ == '__main__' guard exits 0 on
    unexpected errors so a crash never blocks a commit.

DECISION HISTORY:
  - 2026-08-14 [python-coder/BO-2500b-5]: Changed _DEFAULT_TEST_ROOT's
    resolution in main() from the project root's "unit_tests" subdirectory to
    the project root itself. Root cause: the pre-commit hook entry in
    commit_guardian.json passes --test-root . explicitly, but the CI
    invocation (.github/workflows/ci.yml) passes no --test-root at all and
    silently fell back to the "unit_tests" default — so the two callers
    disagreed about which tests count as proof, and JS/TS-covered ACs (whose
    tests live outside unit_tests/) were reported unproven by CI alone
    (BO-2500e-5). Fixing the DEFAULT (not the CI command line) repairs every
    caller that omits --test-root, including consumer installs and ad-hoc
    runs. _EXCLUDED_SCAN_DIRS continues to apply so the widened default does
    not traverse node_modules/, dist/, etc. An explicit --test-root still
    overrides the default unchanged.
  - 2026-09-07 [python-coder/BO-2500b-1-ii]: Made check_staged_done_proofs
    level-aware. Root cause: the check had no notion of AC level at all and
    demanded a direct "# covers: <id>" tag for every done AC, including L0/L1
    composites — whose fulfilment is DERIVED from their children per the
    ac-fulfillment-gate model, so a tag naming the composite's own id may
    never legitimately exist. This blocked real commits (GE-127a, GE-127b)
    until a workaround tag was hand-added. Fix: a done L0/L1 AC is now proven
    by walking its covered_by children (_find_ac_root resolves the AC-store
    root from the staged path; _resolve_child_ac loads each child by id;
    _unproven_composite_children recurses through nested composites) and is
    reported as a violation, naming the unproven child, only when some child
    is not itself done-and-covered — composites are never skipped
    unconditionally (the ACD-400a falsely-done-composite defect this repo has
    20 recorded instances of). L2/L3 leaves are untouched: the original
    direct-covers-tag requirement and its exact reason string still apply.
  - 2026-09-17 [python-coder/BO-2500b-1-iii]: Replaced the L0/L1 ``level``
    check with "``covered_by`` has at least one AC-id child"
    (_composite_child_ids), matching done_proof.py's own
    _verify_composite_eligible convention, since a done L2 composite (e.g.
    UXP-700d-3) was refused for lacking a tag naming its own id. A same-day
    follow-up then had to teach _composite_child_ids to exclude entries that
    LOOK LIKE test-file paths (path separator or .py/.ts/.tsx extension):
    this store also uses ``covered_by`` on a LEAF to record its own proving
    test file(s) (e.g. this very AC's own record), and the first version of
    the fix misread every such leaf's test path as an unresolved child,
    which would have blocked this very commit.
  - 2026-10-06 [python-coder/BO-202 review follow-up, EPIC-BuildToolingRunsThrough/06]:
    the _done_proof_composite import is now fail-safe like the
    _reachability_inventory one: on ImportError (ac_store not locatable) a
    stderr WARNING names the module and the skipped composite check, and
    fallbacks classify no AC as composite, so the hook degrades (check
    skipped, never silent) instead of dying at load and blocking commits.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Resolve ac_store so done_proof is importable from commit_guardian context.
# BP-100n-4-ii-ii: resolution logic lives in sibling _ac_store_locator.py
# (see its own docstring for the full layout rationale) -- moved out of this
# file for file-size-ratchet headroom; pure move, no behaviour change.
# ---------------------------------------------------------------------------
from _resolve_root import find_project_root  # noqa: E402
from _ac_store_locator import ensure_ac_store_on_syspath  # noqa: E402
from _staged_ac_yaml_paths import (  # noqa: E402
    _get_staged_ac_yaml_paths,
    _is_gated_ac_yaml,
)

ensure_ac_store_on_syspath()
try:  # BO-202: ONE shared composite classifier (fail-safe, as below)
    from _done_proof_composite import (
        _collect_all_covered_ids,
        _composite_child_ids,
        _find_ac_root,
        _unproven_composite_children,
    )
except ImportError as _composite_import_exc:  # pragma: no cover - see below
    print(
        "WARNING: check_done_proof: _done_proof_composite unavailable "
        f"({_composite_import_exc}); composite done-proof check SKIPPED "
        "(no AC is classified as composite).",
        file=sys.stderr,
    )

    def _collect_all_covered_ids(*_args):  # type: ignore[no-redef]
        """Fallback: no covered ids when _done_proof_composite is absent."""
        return set()

    def _composite_child_ids(*_args):  # type: ignore[no-redef]
        """Fallback: no AC is composite when _done_proof_composite is absent."""
        return []

    _find_ac_root = _unproven_composite_children = _composite_child_ids  # type: ignore

# ---------------------------------------------------------------------------
# BO-2900d-2: shared reachability-exemption seam (same module BO-2900d-1's
# no-way-in gate in done_proof.py reads — see that module's own comment for
# why there is exactly one reader). Imported at module load time since this
# file already lives directly beside _reachability_inventory.py in both
# layouts (no sibling-directory hop needed, unlike done_proof.py's case).
# ---------------------------------------------------------------------------
try:
    from _reachability_inventory import exemptions_in_force, load_exemptions
except ImportError as _reachability_import_exc:  # pragma: no cover - see below
    print(
        "WARNING: check_done_proof: reachability-exemption seam unavailable "
        f"({_reachability_import_exc}); exemption inventory will report zero "
        "entries on every run.",
        file=sys.stderr,
    )

    def load_exemptions(_registry_path):  # type: ignore[no-redef]
        """Fallback used only when _reachability_inventory is not importable."""
        return []

    def exemptions_in_force(_exemptions):  # type: ignore[no-redef]
        """Fallback used only when _reachability_inventory is not importable."""
        return []

# ---------------------------------------------------------------------------
# Fail-safe top-level import so ``verify_done_eligible`` is a module-level
# attribute that unittest.mock.patch can replace.  Falls back to None when
# ``done_proof`` is not importable (e.g. the templates/ source layout whose
# sibling ac_store/ contains only .gitkeep).  The _load_verify_done_eligible()
# helper below is kept as the None-fallback path.
# ---------------------------------------------------------------------------
try:
    from done_proof import is_covers_tag_waived, verify_done_eligible
    # Import the shared covers-tag seam (BO-2500e-1) — handles both
    # Python "# covers:" and JavaScript/TypeScript "// covers:".
    from test_enforcement import COVERS_TAG_RE  # noqa: F401  # kept as module attr
except (ImportError, ModuleNotFoundError):
    # Fallback: define the unified regex locally when test_enforcement is absent
    # (e.g. in a templates/ source layout with no deployed ac_store neighbour).
    COVERS_TAG_RE = re.compile(r"(?:#|//)\s*covers:\s*(\S+)")

    def verify_done_eligible(*args, **kwargs):
        """Lazy shim used when done_proof is not importable at module load.

        Keeps ``verify_done_eligible`` a real, patchable module-level attribute
        (so unittest.mock.patch("check_done_proof.verify_done_eligible") always
        takes effect) while deferring the real import until first call, resolved
        via the sibling ac_store in the deployed layout.
        """
        return _load_verify_done_eligible()(*args, **kwargs)

    def is_covers_tag_waived(*args, **kwargs):
        """Lazy shim used when done_proof is not importable at module load.

        Mirrors ``verify_done_eligible``'s lazy-shim pattern above (see its
        docstring) so ``is_covers_tag_waived`` — the ONE shared BO-2500a-1-ii
        predicate — stays a real, patchable module-level attribute even when
        the ac_store sibling is not yet on ``sys.path`` at import time.
        """
        return _load_is_covers_tag_waived()(*args, **kwargs)


def _load_verify_done_eligible():
    """Import ``done_proof.verify_done_eligible`` from the sibling ac_store.

    Serves as the None-fallback when the top-level import failed (e.g. in the
    templates/ source layout where ``scripts/ac_store/done_proof.py`` is
    absent) or when the module attribute is None.  Call sites read the module
    global ``verify_done_eligible`` first and only invoke this helper when it
    is None, so that ``unittest.mock.patch("check_done_proof.verify_done_eligible",
    ...)`` takes effect without requiring done_proof to be importable at test
    collection time.

    Returns:
        The ``verify_done_eligible`` callable from the ac_store ``done_proof`` module.
    """
    ensure_ac_store_on_syspath()
    from done_proof import verify_done_eligible

    return verify_done_eligible


def _load_is_covers_tag_waived():
    """Import ``done_proof.is_covers_tag_waived`` from the sibling ac_store.

    See :func:`_load_verify_done_eligible` for the None-fallback rationale —
    the same pattern applies here so the ONE shared BO-2500a-1-ii predicate
    (test_required is False AND a non-empty, non-whitespace test_rationale)
    is never re-derived as a second copy in this module.

    Returns:
        The ``is_covers_tag_waived`` callable from the ac_store ``done_proof``
        module.
    """
    ensure_ac_store_on_syspath()
    from done_proof import is_covers_tag_waived

    return is_covers_tag_waived

# Default paths relative to the project root (used in main() when no explicit
# --ac-root / --test-root argument is supplied).
_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
# BO-2500b-5: the default scan root for covers-tag discovery is the project
# root itself (""), not a hardcoded subdirectory such as "unit_tests" — see
# DECISION HISTORY above. An empty relative path resolves to project_root
# unchanged via `project_root / _DEFAULT_TEST_ROOT`.
_DEFAULT_TEST_ROOT = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# BP-100n-4-ii-ii: _is_gated_ac_yaml and _get_staged_ac_yaml_paths now live in
# the sibling module _staged_ac_yaml_paths.py (imported at top level, see
# that module's own docstring) -- moved verbatim, no behaviour change, to buy
# back file-size-ratchet headroom. _get_changed_ac_yaml_paths below calls the
# re-exported _is_gated_ac_yaml unchanged.


def _get_changed_ac_yaml_paths(base_ref: str, project_root: Path) -> list[Path]:
    """Return absolute paths of AC YAML files changed since *base_ref* via git diff.

    Runs ``git diff --name-only <base_ref>...HEAD`` and filters for files under
    ``docs/acceptance-criteria/`` with a ``.yaml`` extension.  Git errors are
    logged and an empty list is returned (fail-open for the diff step).

    Args:
        base_ref: Git reference to diff against (e.g., ``"origin/main"``).
        project_root: Absolute path to the project (git) root.

    Returns:
        List of absolute Paths for changed AC YAML files.  Returns an empty list
        when the git command fails or no matching files were changed.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: check_done_proof: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []
    result: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = Path(line.strip())
        if not _is_gated_ac_yaml(rel):
            continue
        abs_path = project_root / rel
        if abs_path.exists():
            result.append(abs_path)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# UXP-700d-2: the project's own product root. An AC whose `example_product` field
# is set and differs from this describes an example product shipped alongside the
# project's own record, not the project's own work (ADR-044/UXP-700d-3-i renamed
# this from `product`). A done-proof gate that demands a covering test from such
# a record is picking the example product up as work, which is what UXP-700d-2
# exists to stop -- the ready-leaf scanner already sets the same records aside.
# Ownership is decided by `example_product` alone and never by
# component/components: the example and real criteria routinely share a component.
_PROJECT_PRODUCT: str = "leafcutter"


def _is_example_content(data: dict) -> bool:
    """Return True when the AC describes an example product, not the project's own.

    Args:
        data: Parsed AC record.

    Returns:
        True when ``example_product`` is set and differs from :data:`_PROJECT_PRODUCT`.
    """
    example_product = data.get("example_product")
    return bool(example_product) and example_product != _PROJECT_PRODUCT


def check_staged_done_proofs(
    staged_yaml_paths: list[Path],
    *,
    test_root: Path,
) -> list[dict]:
    """Fast static pre-commit check: covers-tag PRESENCE for newly-done ACs.

    For each AC YAML path in *staged_yaml_paths* whose ``work_status`` field
    is ``"done"``, checks whether at least one ``# covers: <ac_id>`` tag exists
    anywhere under *test_root*.  Does NOT invoke pytest — this is a pure
    filesystem scan designed to fit within the latency budget of a pre-commit
    hook.  Only ACs staged as ``done`` are evaluated (bounded blast radius);
    ACs in any other work_status are silently ignored.

    Composite-aware (BO-2500b-1-ii/iii): a done AC whose ``covered_by``
    contains at least one AC-id child — at any level, matching
    :func:`scripts.ac_store.done_proof._verify_composite_eligible` used by
    ``mark_ac_done.py`` — is a composite whose fulfilment is DERIVED from its
    children rather than a tag naming its own id, which may never
    legitimately exist. A composite is a violation (naming the unproven
    child) only when at least one child is not done-and-covered; never
    skipped unconditionally (see :func:`_unproven_composite_children` for
    the ACD-400a guard). ``covered_by`` entries that look like test-file
    paths (:func:`_composite_child_ids`) are never AC-id children — this
    store also uses ``covered_by`` on a LEAF to record its own proving test
    file(s) — so a leaf (empty ``covered_by``, or one holding only test
    paths) keeps the original direct-covers-tag requirement below.

    On the leaf path only, the covers-tag mandate is waived by
    :func:`done_proof.is_covers_tag_waived` — the ONE shared BO-2500a-1-ii
    predicate, which requires the CONJUNCTION of ``test_required: false`` (the
    Python boolean ``False``, not the string ``"false"``) AND a non-empty,
    non-whitespace ``test_rationale``.  This covers documentation ACs and
    prompt-convention ACs where a covers-tagged test is structurally
    impossible, while still refusing an AC that declares itself untestable
    without recording why.  An absent or ``True`` value for ``test_required``
    is always enforced, and so is ``test_required: false`` with a missing or
    whitespace-only rationale.  The waiver keys ONLY on the AC record's own
    declared fields — never on whether a tag happens to be missing — so it
    cannot be triggered by the very condition (no tag found) it is meant to
    exempt from.

    Until 2026-09-23 this path ALSO carried a standalone
    ``if data.get("test_required") is False: continue`` ahead of the coverage
    branch.  That early return made the conjunction below structurally
    unreachable for exactly the records it was added to catch: a rationale-less
    ``test_required: false`` AC returned before ``is_covers_tag_waived`` was
    ever consulted, so the pre-commit arm kept the pre-BO-2500a-1-ii behaviour
    while the CI arms had moved on.  The early return is gone; the shared
    predicate is now the only waiver on this path.

    The remaining checks are ordered level-first deliberately.  The waiver
    speaks to whether ``test-writer`` must author a DIRECT test for this AC, so
    it waives the direct-covers-tag obligation only.  A composite's obligation
    is a different one — that its children are done and covered — and nothing
    in ``test_required`` speaks to it.  Evaluating the waiver first would let a
    composite that legitimately declares ``test_required: false`` (e.g.
    ACS-500g: ``level: L1``, seven children, ``test_required: false``) skip the
    ACD-400a falsely-done-composite guard entirely, which is the exact shape of
    defect that guard exists to catch.  The CI functions have no level branch
    of their own (their composite handling lives inside
    ``verify_done_eligible``, gated on ``covered_by`` resolving), so for that
    one shape this pre-commit check is deliberately STRICTER than CI — a
    fail-closed asymmetry.

    Args:
        staged_yaml_paths: Paths to staged AC YAML files to evaluate.  May
            include non-done ACs — they are skipped automatically.
        test_root: Root directory to search recursively for ``*.py`` files
            containing ``# covers:`` tags.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means no violations.
    """
    all_covered_ids = _collect_all_covered_ids(test_root)
    violations: list[dict] = []
    for yaml_path in staged_yaml_paths:
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if data.get("work_status") != "done":
            continue
        if _is_example_content(data):
            continue
        ac_id = data.get("id")
        if not ac_id:
            continue
        ac_id_str = str(ac_id)

        if _composite_child_ids(data.get("covered_by")):
            ac_root = _find_ac_root(yaml_path)
            unproven = _unproven_composite_children(data, ac_root, all_covered_ids)
            if unproven:
                violations.append(
                    {
                        "ac_id": ac_id_str,
                        "reason": (
                            f"composite {ac_id_str} is marked done but its covered_by "
                            f"children are not all done-and-covered — unproven: {', '.join(unproven)}"
                        ),
                    }
                )
            continue

        if ac_id_str not in all_covered_ids:
            if is_covers_tag_waived(data):
                continue
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": (
                        f"no '# covers: {ac_id_str}' or '// covers: {ac_id_str}' "
                        f"tag found anywhere under {test_root}"
                    ),
                }
            )
    return violations


def check_all_done_acs(
    *,
    ac_root: Path,
    test_root: Path,
) -> list[dict]:
    """CI-authoritative check: every done AC must pass verify_done_eligible.

    Scans *ac_root* recursively for all AC YAML files whose ``work_status`` is
    ``"done"``, then calls :func:`done_proof.verify_done_eligible` for each.
    ACs for which ``eligible`` is ``False`` are reported as violations.

    ACs for which :func:`done_proof.is_covers_tag_waived` accepts the
    conjunction of ``test_required: false`` (the Python boolean ``False``,
    not the string ``"false"``) AND a non-empty, non-whitespace
    ``test_rationale`` are silently exempted and never passed to
    verify_done_eligible (BO-2500a-1-ii). This covers documentation ACs and
    prompt-convention ACs where a covers-tagged test is structurally
    impossible. ``test_required: false`` with NO recorded rationale is
    tightened by this predicate — it is NOT exempted and is still passed to
    verify_done_eligible, closing a hole this CI sweep previously left open.
    An absent or ``True`` value for ``test_required`` is always enforced.

    Unlike the pre-commit check, this function DOES run pytest (via
    verify_done_eligible → subprocess) so that a covers tag whose linked test
    is failing still produces a violation.  This is the authoritative backstop
    that catches commits made with ``--no-verify`` or from worktrees lacking
    hook config (BO-2500b-1-i).

    Args:
        ac_root: Root directory of the AC YAML store to scan recursively.
        test_root: Root directory to scan for ``*.py`` test files containing
            ``# covers:`` tags; passed to verify_done_eligible unchanged.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means all done ACs are
        eligible.
    """
    violations: list[dict] = []
    try:
        yaml_files = sorted(ac_root.rglob("*.yaml"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {ac_root}: {exc}",
            file=sys.stderr,
        )
        return violations
    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if data.get("work_status") != "done":
            continue
        if _is_example_content(data):
            continue
        ac_id = data.get("id")
        if not ac_id:
            continue
        ac_id_str = str(ac_id)
        if is_covers_tag_waived(data):
            continue
        verdict = verify_done_eligible(ac_id_str, ac_root=ac_root, test_root=test_root)
        if not verdict.get("eligible"):
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": verdict.get("reason", "coverage gate failed"),
                }
            )
    return violations


def check_changed_done_acs(
    changed_yaml_paths: list[Path],
    *,
    ac_root: Path,
    test_root: Path,
) -> list[dict]:
    """PR-scoped CI check: done-proof evaluated only for changed AC yaml paths.

    For each AC YAML path in *changed_yaml_paths* whose ``work_status`` is
    ``"done"``, calls :func:`done_proof.verify_done_eligible` to confirm the
    AC has a covers-tagged, passing test.  ACs NOT in *changed_yaml_paths* are
    never evaluated — this scoping invariant makes it safe to promote this mode
    to a required CI gate without failing on pre-existing done ACs that predate
    the covers-tag mandate (BO-2500b-3).

    ACs for which :func:`done_proof.is_covers_tag_waived` accepts the
    conjunction of ``test_required: false`` (the Python boolean ``False``,
    not the string ``"false"``) AND a non-empty, non-whitespace
    ``test_rationale`` are silently exempted and never passed to
    verify_done_eligible (BO-2500a-1-ii). This covers documentation ACs and
    prompt-convention ACs where a covers-tagged test is structurally
    impossible. ``test_required: false`` with NO recorded rationale is
    tightened by this predicate — it is NOT exempted and is still passed to
    verify_done_eligible, closing a hole this CI sweep previously left open.
    An absent or ``True`` value for ``test_required`` is always enforced.

    Args:
        changed_yaml_paths: AC YAML paths changed in the current PR (e.g. from
            ``git diff --name-only <base>...HEAD``).  Only these paths are
            evaluated.  Pre-existing done ACs not in this list are silently
            ignored.
        ac_root: Root directory of the AC YAML store; passed to
            :func:`done_proof.verify_done_eligible`.
        test_root: Root directory to scan for covers-tagged tests; passed to
            :func:`done_proof.verify_done_eligible`.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means no violations among
        the changed done ACs.
    """
    violations: list[dict] = []
    for yaml_path in changed_yaml_paths:
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if data.get("work_status") != "done":
            continue
        if _is_example_content(data):
            continue
        ac_id = data.get("id")
        if not ac_id:
            continue
        ac_id_str = str(ac_id)
        if is_covers_tag_waived(data):
            continue
        verdict = verify_done_eligible(ac_id_str, ac_root=ac_root, test_root=test_root)
        if not verdict.get("eligible"):
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": verdict.get("reason", "coverage gate failed"),
                }
            )
    return violations


# ---------------------------------------------------------------------------
# BO-2900d-2: exemption inventory report
#
# Emitted on EVERY run of the guard, regardless of mode and regardless of
# whether any violation was found — the natural implementation (printing
# exemptions only when explaining a suppressed finding) is the defect this
# AC exists to close: nobody ever sees the whole accumulated set otherwise.
# ---------------------------------------------------------------------------


def build_exemption_inventory_report(project_root: Path) -> dict:
    """Build the ``exemption_inventory_report`` for *project_root*.

    Reads ``config/reachability_exemptions.yaml`` via the shared
    ``_reachability_inventory`` seam (the same reader BO-2900d-1's no-way-in
    gate uses) so the guard's refusal and its own inventory can never
    disagree about what is recorded.

    Args:
        project_root: Root directory containing ``config/``.

    Returns:
        ``{"in_force": [{"item", "kind", "reason"}, ...], "total_in_force": int,
        "stale": []}`` per BO-2900d-2's schema. ``stale`` detection
        (BO-2900d-3) is out of this AC's scope and is always empty here.
        A registry that cannot be read/parsed logs a warning and reports
        zero exemptions (fail-closed: an unreadable registry must never be
        treated as "everything is exempt").
    """
    registry_path = project_root / "config" / "reachability_exemptions.yaml"
    try:
        exemptions = load_exemptions(registry_path)
    except (OSError, ValueError) as exc:
        print(
            f"WARNING: check_done_proof: cannot load {registry_path}: {exc}",
            file=sys.stderr,
        )
        exemptions = []
    in_force = exemptions_in_force(exemptions)
    return {
        "in_force": [
            {
                "item": entry.get("item"),
                "kind": entry.get("kind"),
                "reason": entry.get("reason"),
            }
            for entry in in_force
        ],
        "total_in_force": len(in_force),
        "stale": [],
    }


def print_exemption_inventory_report(project_root: Path) -> None:
    """Print the exemption inventory: one line per entry, then the total.

    Called unconditionally from :func:`main` for every mode and every
    outcome (BO-2900d-2's "on a run that reports no findings" clause) — this
    is a SEPARATE section of the output from any violations printed above
    it; a refusing run still prints both.

    Args:
        project_root: Root directory containing ``config/``.
    """
    report = build_exemption_inventory_report(project_root)
    for entry in report["in_force"]:
        print(
            f"[check-done-proof] exemption in force: {entry['item']} "
            f"({entry['kind']}) — {entry['reason']}"
        )
    print(f"[check-done-proof] exemptions in force: {report['total_in_force']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the check_done_proof CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Enforce mechanical proof-of-done (BO-2500b). "
            "pre-commit mode: static covers-tag presence check for staged done ACs. "
            "ci mode: full verify_done_eligible run over every done AC in the store."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["precommit", "ci", "ci-changed"],
        default="precommit",
        help=(
            "Operating mode: 'precommit' (fast static, default), 'ci' (full store), "
            "or 'ci-changed' (PR-scoped; only changed AC yamls are evaluated)."
        ),
    )
    parser.add_argument(
        "--base",
        metavar="REF",
        default="origin/main",
        help=(
            "Git base ref for diff in ci-changed mode "
            "(default: origin/main). Ignored in precommit and ci modes."
        ),
    )
    parser.add_argument(
        "--ac-root",
        metavar="DIR",
        default=None,
        help=(
            "Root directory of the AC YAML store "
            "(default: <project-root>/docs/acceptance-criteria)."
        ),
    )
    parser.add_argument(
        "--test-root",
        metavar="DIR",
        default=None,
        help=(
            "Root directory to scan for covers-tagged tests "
            "(default: <project-root>, i.e. the whole project)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the proof-of-done gate.

    Dispatches to check_staged_done_proofs (precommit mode),
    check_all_done_acs (ci mode), or check_changed_done_acs (ci-changed mode)
    based on --mode.  Prints each violation's ac_id and reason; exits 1 when
    violations are found, 0 otherwise.

    Args:
        argv: Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        0 when no violations are found; 1 when at least one violation exists.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_root = find_project_root()
    ac_root = Path(args.ac_root) if args.ac_root else project_root / _DEFAULT_AC_ROOT
    test_root = (
        Path(args.test_root) if args.test_root else project_root / _DEFAULT_TEST_ROOT
    )

    if args.mode == "ci":
        try:
            violations = check_all_done_acs(ac_root=ac_root, test_root=test_root)
        except (OSError, ValueError, KeyError) as exc:
            print(
                f"[check-done-proof] CI checker error (fail-closed): {exc}",
                file=sys.stderr,
            )
            return 1
    elif args.mode == "ci-changed":
        changed_paths = _get_changed_ac_yaml_paths(args.base, project_root)
        try:
            violations = check_changed_done_acs(
                changed_paths, ac_root=ac_root, test_root=test_root
            )
        except (OSError, ValueError, KeyError) as exc:
            print(
                f"[check-done-proof] CI-changed checker error (fail-closed): {exc}",
                file=sys.stderr,
            )
            return 1
    else:
        staged_paths = _get_staged_ac_yaml_paths(project_root)
        violations = check_staged_done_proofs(staged_paths, test_root=test_root)

    for v in violations:
        print(f"[check-done-proof] {v['ac_id']}: {v['reason']}")

    # BO-2900d-2: printed on EVERY run — clean or refusing, every mode —
    # never gated behind `if violations`. See the module docstring above.
    print_exemption_inventory_report(project_root)

    return 1 if violations else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"[check-done-proof] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)
