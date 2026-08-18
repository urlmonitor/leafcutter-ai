"""
MODULE: build_propagation_audit
GOAL: Post-install audit that walks every hook entry in .pre-commit-config.yaml,
    verifies the referenced script is installed, and auto-copies or warns when it
    is not. Prevents the dangling-hook-script bug class from recurring. Also
    provides broken-reference checking with an external-dependency allowlist so
    that well-known external scripts do not trigger false-positive failures.
BUSINESS CONTEXT: EPIC-PortableInstallHardening discovered 5 scripts registered
    in .pre-commit-config.yaml but never installed to scripts/commit_guardian/.
    This module adds a fail-open (exit 0) audit phase after build_commit_guardian
    so any future omission is caught at the next build.py run rather than at
    smoke-test time on a fresh install. AC BP-900b-1-1 adds an external-dependency
    allowlist so agent templates that legitimately reference external scripts
    (e.g. a user-supplied tool path) do not produce broken-reference failures.
    AC BP-900c-1 adds a three-field broken-reference report entry: missing path,
    referencing template, and a suggested action.
ARCHITECTURE: One public phase function ``propagation_audit``, one guard
    function ``check_broken_references``, a ``BrokenRefEntry`` dataclass, and
    a ``build_broken_ref_report`` factory. Parsing uses ``yaml.safe_load`` with a
    regex fallback if PyYAML is absent. The audit is intentionally fail-open: it
    never raises and always returns, even when warnings are emitted. The allowlist
    is a module-level frozenset constant that callers can extend by passing an
    explicit ``allowlist`` argument to ``check_broken_references``.
    AC BP-900c-1-1: ``build_broken_ref_report`` consolidates multiple templates
    that reference the same missing script into a single ``BrokenRefEntry`` with
    a ``referencing_templates`` tuple, so the suggested action appears exactly
    once per missing path.
    AC BP-900c-2: ``emit_broken_ref_report_jsonl`` serialises a list of
    ``BrokenRefEntry`` instances to stderr as JSONL (one JSON object per line)
    with keys ``"missing_path"``, ``"referencing_template"``, and
    ``"suggested_action"``, ensuring error output is never written to stdout.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# External-dependency allowlist (AC BP-900b-1-1)
# ---------------------------------------------------------------------------
# Script paths listed here are treated as resolved by the broken-reference
# guard even when the path does not exist in the deployed output. Add an entry
# whenever a template legitimately references a script that is installed by an
# external tool or by the user's own project rather than by the leafcutter
# build pipeline.
#
# Each entry must be a ``scripts/<relative-path>`` string matching the form
# produced by ``extract_script_path_refs()`` in ``build_referential_integrity``.

EXTERNAL_DEPENDENCY_ALLOWLIST: frozenset[str] = frozenset([
    # scripts/inline_adr/append_entry.py — referenced in doc-enforcer/SKILL.md
    # with an explicit "if scripts/inline_adr/append_entry.py is present:" guard.
    # The doc-enforcer workflow is fully functional without it.
    "scripts/inline_adr/append_entry.py",
    # scripts/list_sql_helpers.py — referenced in sql-coder.md with an explicit
    # "If no helpers are listed, or the script does not exist, skip this step"
    # guard. Pure Python/TypeScript consumers never need it.
    "scripts/list_sql_helpers.py",
    # scripts/build.py — self-reference. The build orchestrator is referenced in
    # skills (feature/SKILL.md, knowledge-query/SKILL.md) as an instructional
    # reminder for package developers, not a consumer-side runtime dependency.
    "scripts/build.py",
    # scripts/epic_lock.py — epic branch lock management; host-side orchestration
    # tool used by the leafcutter package maintainer. Consumer projects do not
    # manage epic locks themselves. A new script must be authored before this can
    # be deployed (tracked as a separate ticket per EPIC-BuildGuardFalsePositive/01
    # OPEN QUESTIONS). Safe to allowlist: the referencing skill (building-epics)
    # includes "if absent, skip" semantics for lock acquisition.
    "scripts/epic_lock.py",
    # scripts/scaffold/new_arch_doc.py — architecture doc scaffolding tool.
    # Referenced by documentation agents (architecture-diagram-author.md,
    # write-c4-diagram/SKILL.md) but the script does not yet exist as a package
    # deliverable. Allowlisted so the guard does not block; however, this causes
    # a hard user-visible failure in write-c4-diagram when the script is absent
    # (SKILL.md says "surface to the user and DO NOT improvise" — not a graceful
    # skip). A separate authoring ticket is required to create and deploy this script.
    "scripts/scaffold/new_arch_doc.py",
    # scripts/onboard_hook_opt_in.py — referenced in agents/onboard.md as an
    # optional standalone helper ("You can also run this step via the standalone
    # script"). The reference is advisory — onboard.md describes the same
    # detection-and-prompt logic inline above the note, so absence of the script
    # does not break the onboarding flow. The script lives in scripts/ (source)
    # and is deployed to consumer projects via the onboarding flow itself (not via
    # build_template_standalone_scripts), so it is legitimately absent from the
    # _manifest_template_standalone_scripts scan of templates/scripts/.
    "scripts/onboard_hook_opt_in.py",
    # scripts/feedback/{submit_feedback,aggregate,resolve_feedback}.py — the
    # feedback subsystem scripts were untracked in #164 ("untrack previously-
    # committed real files (now .gitignore'd build-output symlinks)") and are
    # supplied to consumer projects via the install_shims() shim_map rather than
    # committed to the package tree. They are referenced by feedback agents/skills
    # (epic-supervisor, ticket-supervisor, retrospective-agent, user-surface-smoker,
    # build-single-ticket, signoff, feedback-review, ticket-wiring) but are absent
    # from a fresh clone, so the reference guard blocked every fresh-clone build.
    # Allowlisted so the guard does not block; the feedback subsystem degrades
    # gracefully when the scripts are absent. A follow-up should add a proper
    # deploy phase (build_phases.py) so feedback works out of the box.
    "scripts/feedback/submit_feedback.py",
    "scripts/feedback/aggregate.py",
    "scripts/feedback/resolve_feedback.py",
])

# ---------------------------------------------------------------------------
# Known-undeployed allowlist (AC BP-900g-4, emptied by BP-900g-5) — KEEP EMPTY
# ---------------------------------------------------------------------------
# These are NOT external dependencies. An entry here is a leafcutter script that
# exists in the package source, is referenced by a deployed agent or skill, and
# has no deploy phase — so the capability is silently dead in a consumer install.
#
# It is kept separate from EXTERNAL_DEPENDENCY_ALLOWLIST so the distinction stays
# legible: that set means "legitimately not ours to deploy", this one means
# "our bug, seen, not yet fixed".
#
# BP-900g-4 populated it with the references that widening the extraction pattern
# made visible. BP-900g-5 emptied it: six of those now deploy via
# build_agent_support_scripts(), and the seventh
# (debugging/scripts/check/prod_status_check.py in status-checker.md) turned out
# not to be a leafcutter script at all — it is a HOST-project path that the
# then-too-permissive prefix had mis-normalised into a scripts/... deploy key. The
# prefix now requires a dot-prefixed output root, so it is no longer captured.
#
# This set is empty and must stay empty. Adding an entry is a regression, not a
# fix: it means shipping an agent that cannot run. Deploy the script instead.

KNOWN_UNDEPLOYED_ALLOWLIST: frozenset[str] = frozenset()

# The guard treats both sets as resolved. They are unioned rather than merged so
# that emptying KNOWN_UNDEPLOYED_ALLOWLIST is a self-contained change.
_RESOLVED_ALLOWLIST: frozenset[str] = (
    EXTERNAL_DEPENDENCY_ALLOWLIST | KNOWN_UNDEPLOYED_ALLOWLIST
)

# Regex to extract script basename from entries like:
#   python scripts/commit_guardian/check_foo.py [args...]
_ENTRY_RE = re.compile(r"scripts[/\\]commit_guardian[/\\]([\w.]+\.py)")


def _parse_hook_entries_yaml(precommit_path: Path) -> list[str]:
    """Parse hook entry fields from .pre-commit-config.yaml using yaml.safe_load.

    Falls back to regex line scan when PyYAML is not importable.

    Args:
        precommit_path: Path to the .pre-commit-config.yaml file.

    Returns:
        List of ``entry`` field strings from all hook definitions.
    """
    text = precommit_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        _log.debug("PyYAML not available; falling back to regex scan.")
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    try:
        data = yaml.safe_load(text) or {}
        entries: list[str] = []
        for repo in data.get("repos", []):
            for hook in repo.get("hooks", []):
                entry = hook.get("entry", "")
                if entry:
                    entries.append(entry)
    except yaml.YAMLError as exc:
        _log.warning("Could not parse .pre-commit-config.yaml as YAML: %s — falling back to regex scan.", exc)
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    else:
        return entries


def _candidate_template_paths(script_name: str, package_root: Path) -> list[Path]:
    """Return ordered list of template locations to search for script_name.

    Args:
        script_name: Basename of the hook script (e.g. ``check_foo.py``).
        package_root: Root of the leafcutter package.

    Returns:
        List of candidate Paths (canonical only).
    """
    return [
        package_root / "templates" / "scripts" / "commit_guardian" / script_name,
    ]


def check_broken_references(
    refs: set[str],
    deployed_scripts: set[str],
    allowlist: frozenset[str] | None = None,
) -> set[str]:
    """Return the set of script references that are broken (not deployed and not allowlisted).

    Compares the set of script path references extracted from source agent and
    skill templates against the set of scripts that this build run will deploy.
    A reference is considered *broken* when it appears in ``refs`` but not in
    ``deployed_scripts`` and is also absent from the allowlist.

    Allowlisted references are silently treated as resolved: they do not appear
    in the returned broken set and do not cause the build to warn or fail, even
    if the path is not present in ``deployed_scripts``.

    Args:
        refs: Set of ``scripts/<path>`` strings extracted from templates.
        deployed_scripts: Set of ``scripts/<path>`` strings that will be
            deployed by this build run.
        allowlist: Frozenset of ``scripts/<path>`` strings that are exempt from
            broken-reference failures. Defaults to ``EXTERNAL_DEPENDENCY_ALLOWLIST``
            when ``None``.

    Returns:
        Set of ``scripts/<path>`` strings that are broken: referenced in
        templates but neither deployed nor allowlisted. An empty set means all
        references are accounted for and the build may exit zero.
    """
    effective_allowlist = _RESOLVED_ALLOWLIST if allowlist is None else allowlist
    resolved = deployed_scripts | effective_allowlist
    return refs - resolved


# ---------------------------------------------------------------------------
# Broken-reference report entries (AC BP-900c-1)
# ---------------------------------------------------------------------------

#: Suggested action when the missing script belongs to the leafcutter build
#: pipeline and should be added as a new deploy phase.
ACTION_ADD_DEPLOY_PHASE = "add a deploy phase in build_phases.py"

#: Suggested action when the missing script is supplied externally (not built
#: by leafcutter) and should be registered in the allowlist instead.
ACTION_ADD_TO_ALLOWLIST = "add to the external-dependency allowlist"

#: Suggested action when the source directory and its deploy phase already
#: exist but the script file is missing or untracked in git (AC BP-900c-3).
#: The author must commit the source under the tracked deploy-source mirror.
ACTION_COMMIT_UNDER_TEMPLATES = (
    "source is missing or untracked — commit the file under templates/scripts/ "
    "(the tracked deploy-source mirror)"
)

# Prefixes that have an established deploy phase in build_phases.py.
# When a broken reference falls under one of these prefixes the directory and
# deploy phase already exist, so the truthful corrective action is to commit
# the missing source rather than to add a new deploy phase (AC BP-900c-3).
#
# M-1 MAINTENANCE NOTE: Keep this tuple in sync with the phase functions in
# build_phases.py that deploy into scripts/. Each entry here corresponds to a
# build phase: build_ac_store → scripts/ac_store/, build_feedback →
# scripts/feedback/, build_commit_guardian → scripts/commit_guardian/.
# A focused test (test_build_tracked_source_guard.py::TestSuggestActionDirPresent)
# will fail if a new phase is added to build_phases.py without a matching prefix
# entry here, preventing silent drift.
_PREFIXES_WITH_EXISTING_DEPLOY_PHASE: tuple[str, ...] = (
    "scripts/ac_store/",
    "scripts/feedback/",
    "scripts/commit_guardian/",
)


def _suggest_action(missing_path: str, allowlist: frozenset[str]) -> str:
    """Return the appropriate suggested action for a single broken reference.

    State-based selector (AC BP-900c-3 / BP-900c-3-i / M-2). The branches are
    evaluated in this order — leafcutter-ownership wins over allowlisting:

    * When the missing path is under a directory that already has an established
      deploy phase in build_phases.py the source file is missing or untracked
      in git; the truthful action is to commit the source under
      ``templates/scripts/`` (the tracked deploy-source mirror). This is checked
      FIRST so a leafcutter-owned path that also appears in the allowlist (e.g.
      the feedback subsystem scripts) still gets the commit-source action.
    * When the missing path is in the external-dependency allowlist AND is not
      leafcutter-owned, the path is external — return ``ACTION_ADD_TO_ALLOWLIST``.
    * When the path is under an entirely new directory (no deploy phase exists)
      the action is to add a deploy phase in build_phases.py.

    The three states are distinguishable per-entry so a single report can
    contain all action types.

    Args:
        missing_path: The ``scripts/<path>`` string that was not deployed and
            not allowlisted.
        allowlist: The effective allowlist in use during the audit.  When the
            path appears in the allowlist it is classified as an external
            dependency (M-2: restore ACTION_ADD_TO_ALLOWLIST branch).

    Returns:
        One of ``ACTION_ADD_TO_ALLOWLIST`` (external dependency, not owned by
        leafcutter), ``ACTION_COMMIT_UNDER_TEMPLATES`` (dir+phase exist, source
        missing/untracked), or ``ACTION_ADD_DEPLOY_PHASE`` (genuinely new
        capability, no deploy phase yet).
    """
    # Dir+phase already exist — the path is leafcutter-owned (it lives under a
    # directory that has an established deploy phase), so the source file is
    # merely missing or untracked in git.  This branch MUST be evaluated BEFORE
    # the allowlist branch: some leafcutter-owned paths (e.g. the feedback
    # subsystem scripts) are ALSO present in EXTERNAL_DEPENDENCY_ALLOWLIST, but
    # for those the truthful action is to commit the source under
    # templates/scripts/, not to register them as an external dependency
    # (AC BP-900c-3).
    if any(missing_path.startswith(prefix) for prefix in _PREFIXES_WITH_EXISTING_DEPLOY_PHASE):
        return ACTION_COMMIT_UNDER_TEMPLATES

    # M-2: external-dependency branch — path is in the allowlist and is NOT
    # leafcutter-owned (no matching deploy-phase prefix).  Return the allowlist
    # action so consumers know this path should be registered, not authored.
    if missing_path in allowlist:
        return ACTION_ADD_TO_ALLOWLIST

    # Genuinely new capability — no deploy phase exists yet.
    return ACTION_ADD_DEPLOY_PHASE


@dataclass(frozen=True)
class BrokenRefEntry:
    """A single broken-reference report entry with all three required fields.

    AC BP-900c-1 requires that each broken-reference entry names the missing
    script path, the compiled templates that reference it, and a suggested
    corrective action.

    AC BP-900c-1-1 requires consolidation: when multiple templates reference
    the same missing script, a single ``BrokenRefEntry`` is emitted that lists
    all referencing templates rather than one entry per template.

    Attributes:
        missing_path: The ``scripts/<path>`` string that was referenced in
            one or more templates but is absent from the deployable script set.
        referencing_templates: Tuple of relative paths of every template file
            that references the missing script, sorted lexicographically.
        suggested_action: A human-readable corrective action.
    """

    missing_path: str
    referencing_templates: tuple[str, ...]
    suggested_action: str


def build_broken_ref_report(
    refs_to_sources: dict[str, set[str]],
    deployed_scripts: set[str],
    allowlist: frozenset[str] | None = None,
) -> list[BrokenRefEntry]:
    """Build a consolidated list of broken-reference report entries.

    For every script path in ``refs_to_sources`` that is neither deployed nor
    allowlisted, this function emits exactly one ``BrokenRefEntry`` that
    collects all referencing templates into the ``referencing_templates`` tuple.

    Args:
        refs_to_sources: Mapping from ``scripts/<path>`` strings to the set of
            relative template paths that reference them.  Typically produced by
            ``build_referential_integrity.extract_script_path_refs_with_sources()``.
        deployed_scripts: Set of ``scripts/<path>`` strings that will be
            deployed by this build run.
        allowlist: Frozenset of ``scripts/<path>`` strings exempt from failure.
            Defaults to ``EXTERNAL_DEPENDENCY_ALLOWLIST`` when ``None``.

    Returns:
        List of ``BrokenRefEntry`` instances, one per unique missing script
        path. An empty list means all references are accounted for.
    """
    effective_allowlist = _RESOLVED_ALLOWLIST if allowlist is None else allowlist
    resolved = deployed_scripts | effective_allowlist
    entries: list[BrokenRefEntry] = []
    for script_path, source_templates in refs_to_sources.items():
        if script_path in resolved:
            continue
        action = _suggest_action(script_path, effective_allowlist)
        entries.append(
            BrokenRefEntry(
                missing_path=script_path,
                referencing_templates=tuple(sorted(source_templates)),
                suggested_action=action,
            )
        )
    return entries


def emit_broken_ref_report_jsonl(
    entries: list[BrokenRefEntry],
    stream: "IO[str] | None" = None,
) -> None:
    """Emit a broken-reference report to *stream* in JSONL format (AC BP-900c-2).

    Each ``BrokenRefEntry`` is serialised as one JSON object per line with
    exactly three keys: ``"missing_path"``, ``"referencing_template"``, and
    ``"suggested_action"``. All output is written to *stream* (defaults to
    ``sys.stderr``) so that the error report is never interleaved with normal
    stdout build output.

    Args:
        entries: List of ``BrokenRefEntry`` instances to serialise. May be
            empty; in that case the function is a no-op.
        stream: Writable text stream that receives the JSONL output.
            Defaults to ``sys.stderr`` when ``None``.
    """
    out = sys.stderr if stream is None else stream
    for entry in entries:
        refs = entry.referencing_templates
        ref_value: str | list[str] = refs[0] if len(refs) == 1 else list(refs)
        record = {
            "missing_path": entry.missing_path,
            "referencing_template": ref_value,
            "suggested_action": entry.suggested_action,
        }
        print(json.dumps(record, ensure_ascii=False), file=out)


def propagation_audit(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Audit .pre-commit-config.yaml hook entries and auto-copy missing scripts.

    For each hook entry referencing ``scripts/commit_guardian/<name>.py``:
    - If the script is already installed: silent pass.
    - If a template exists: auto-copy (or dry-run report). Log at INFO.
    - If no template found: print a WARNING. Never blocks build (exit 0).

    The audit runs after ``build_commit_guardian`` so freshly-installed scripts
    are visible immediately.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build config dict (unused; reserved for future use).
        dry_run: When True, auto-copy is skipped but WARNINGs are still emitted.
        force: Unused; propagation_audit always copies missing scripts regardless.

    Returns:
        Count of scripts auto-copied (0 in dry_run mode).
    """
    precommit_path = target_root / "pre-commit-config.yaml"
    if not precommit_path.exists():
        _log.debug("No .pre-commit-config.yaml at %s — propagation audit skipped.", target_root)
        return 0

    package_root = Path(__file__).resolve().parent.parent
    scripts_dir = target_root / "scripts" / "commit_guardian"
    copied = 0

    try:
        entries = _parse_hook_entries_yaml(precommit_path)
    except Exception as exc:  # noqa: BLE001
        _log.warning("propagation_audit: could not parse .pre-commit-config.yaml: %s", exc)
        return 0

    checked: set[str] = set()
    for entry in entries:
        m = _ENTRY_RE.search(entry)
        if not m:
            continue
        script_name = m.group(1)
        if script_name in checked:
            continue
        checked.add(script_name)

        target_script = scripts_dir / script_name
        if target_script.exists():
            continue  # already installed

        candidates = _candidate_template_paths(script_name, package_root)
        for candidate in candidates:
            if candidate.exists():
                if dry_run:
                    print(f"  [DRY-RUN] propagation_audit: would copy {script_name} from {candidate.relative_to(package_root)}")
                else:
                    target_script.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, target_script)
                    print(f"  [PROPAGATION] copied {script_name} from {candidate.relative_to(package_root)}")
                    copied += 1
                break
        else:
            print(
                f"  WARNING: hook entry references {script_name} — not installed and no template found. "
                "Install manually or remove the hook entry.",
                file=sys.stderr,
            )

    return copied


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-18 11:30 [EPIC-PortableInstallHardening/T04]: Created module. Fail-open propagation audit that walks .pre-commit-config.yaml hook entries, auto-copies missing scripts from templates, and warns when no template is found. Extracted as sibling module to keep build_phases.py within 400-line limit. (#EPIC-PortableInstallHardening/T04)
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]: Added three allowlist
#   entries (epic_lock.py, scaffold/new_arch_doc.py, commit_guardian/known_failing_tests.py)
#   with inline justification comments. These scripts require separate authoring tickets
#   before they can be deployed. Only epic_lock.py has a documented "if absent, skip"
#   fallback (building-epics SKILL). scaffold/new_arch_doc.py causes a hard user-visible
#   failure when absent (write-c4-diagram SKILL.md: "surface to the user and DO NOT
#   improvise" — not a graceful skip). commit_guardian/known_failing_tests.py also causes
#   a hard failure when absent: commit.md has no documented fallback and explicitly forbids
#   --no-verify as an escape path. Separate authoring tickets are required for the latter
#   two before they can be deployed. (#EPIC-BuildGuardFalsePositive/03)
# - 2026-08-18 [python-coder/test-authoring]: Removed the
#   scripts/commit_guardian/known_failing_tests.py allowlist entry (added
#   2026-06-17 above). The 2026-06-17 justification ("does not yet exist as a
#   package deliverable") had gone stale: the script DID exist as a tracked
#   template and was deployed, but was never registered in any pre-commit
#   config and its baseline file was never created, so it never actually ran.
#   TQ-100d-1 specifies its replacement (config/known_failing_tests.yaml +
#   expiry/staleness checks) under a settled design, so the dead script was
#   deleted outright rather than wired up as a weaker competitor. commit.md
#   no longer references it as a live invocation (only as historical prose),
#   so the allowlist entry is no longer needed to keep the broken-reference
#   guard green. (#TQ-100d-1)
# ===========================================================================
