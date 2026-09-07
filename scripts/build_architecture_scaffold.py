"""
MODULE: build_architecture_scaffold
GOAL: Guarantee that every namespace root the whole-collection identifier
    uniqueness pass (GE-122a-1) holds itself responsible for exists as a real,
    git-trackable directory after a BASE ``build.py`` install — never gated
    behind the opt-in ``--seed-docs`` step.
BUSINESS CONTEXT: KI-BO-030 records that a base install does not create
    ``docs/architecture/adrs/`` or ``docs/architecture/diagrams/`` in a fresh
    project. GE-122d-3-ii's binding design decision is that an absent
    namespace root must never be excused as an empty one — the fail-closed
    ``check_identifier_uniqueness.py`` pass reports a MISSING root as a
    could-not-establish, commit-blocking condition (GE-122e-3, 2026-08-25),
    distinct from an existing-but-empty root, which passes cleanly with an
    inspected count of zero. The only implementation that satisfies BOTH
    halves of that criterion is to make the roots exist unconditionally on
    every install, never to teach the pass that absence means empty. This
    module is that scaffold step.
ARCHITECTURE: A single public function, ``build_architecture_namespace_scaffolds``,
    following the exact write-if-absent convention already established by
    ``build_ac_store_scaffold.build_ac_store_scaffold`` (KI-BO-030's own
    comparison point): each destination file is written only when absent, so
    a re-run never clobbers content an adopter has since edited (BP-900h-2's
    install-idempotency contract). ``docs/architecture/adrs/`` already has a
    seed source (``templates/docs/architecture/adrs/README.md``);
    ``docs/architecture/diagrams/`` gets a new placeholder README (drafted in
    ``docs/reference/architecture-docs-layout.md``, added alongside this
    module).

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3-ii.yaml
  - docs/known-issues/build-orchestration.md
  - docs/reference/architecture-docs-layout.md
  - templates/scripts/commit_guardian/_uniqueness_scanners.py

DECISION HISTORY:
  - 2026-08-31 [python-coder/GE-122d-3-ii]: Created. Scaffolds
    ``docs/architecture/adrs/README.md`` and
    ``docs/architecture/diagrams/README.md`` unconditionally on the base
    install path so both namespace roots the uniqueness pass depends on
    exist as real directories in a project built from empty, with no
    opt-in documentation-seeding step performed. Deliberately scoped to
    directory scaffolding only — this module does not touch
    ``config/paths.json`` or the hardcoded diagrams root in
    ``check_identifier_uniqueness.py`` (KI-CG-013); that resolver-mechanism
    change is a separate, not-yet-scheduled increment of this same AC.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_ARCHITECTURE_TEMPLATES_DIR = _PACKAGE_ROOT / "templates" / "docs" / "architecture"

# (namespace subdirectory, seed filename) pairs. Both roots are namespaces the
# whole-collection uniqueness pass holds itself responsible for
# (ADR-037) — see _uniqueness_scanners.scan_decisions / scan_diagrams.
_NAMESPACE_SEEDS: list[tuple[str, str]] = [
    ("adrs", "README.md"),
    ("diagrams", "README.md"),
]


def build_architecture_namespace_scaffolds(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Scaffold every architecture-docs namespace root onto the base install.

    Writes ``docs/architecture/adrs/README.md`` and
    ``docs/architecture/diagrams/README.md`` from their template sources under
    ``templates/docs/architecture/<namespace>/`` whenever the destination is
    absent. Uses write-if-absent semantics — an existing file (including one
    an adopter has since edited) is never overwritten, regardless of
    ``force``, matching ``build_ac_store_scaffold``'s contract and
    BP-900h-2's install-idempotency requirement.

    Args:
        target_root: Absolute path to the target project root. Scaffolds are
            installed at ``{target_root}/{docs_root}/architecture/<namespace>/``.
        config: Build configuration dict; only ``docs_root`` is consulted.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics so
            a re-run can never clobber adopter-edited scaffold content.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    architecture_dir = target_root / docs_dir / "architecture"
    written = 0

    for namespace, filename in _NAMESPACE_SEEDS:
        template_path = _ARCHITECTURE_TEMPLATES_DIR / namespace / filename
        dest = architecture_dir / namespace / filename
        if dest.exists():
            continue
        if not template_path.exists():
            print(
                f"  [WARNING] architecture scaffold: template not found: {template_path}"
            )
            continue
        if dry_run:
            print(f"  [DRY-RUN] would scaffold docs/architecture/{namespace}/{filename}")
            written += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            content = template_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"  [WARNING] architecture scaffold: could not read template "
                f"{template_path}: {exc}"
            )
            continue
        dest.write_text(content, encoding="utf-8")
        print(f"  docs/architecture/{namespace}/{filename}")
        written += 1

    if written == 0:
        print("  Architecture namespace scaffolds: already present, skipping")

    return written
