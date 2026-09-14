"""
MODULE: build_phases_reachability
GOAL: Post-deploy command-reference reachability guardrail (BP-900g-1 /
    BP-900g-1-i), extracted from build_phases.py to relieve its
    400-counted-line check-file-size limit.
BUSINESS CONTEXT: build_phases.py measured 2671 content lines (the
    check-file-size hook's own counter) against the 400-line limit. This
    module carries the command-reachability guard family out of
    build_phases.py verbatim, with no behaviour change, so build_phases.py
    has headroom for further work.
ARCHITECTURE: One public function, ``check_command_reachability``, plus its
    two private helpers ``_handoff_target_resolves`` and
    ``_resolve_declared_workflows_enabled``, and the module-level compiled
    regex ``_HANDOFF_TARGET_RE`` they share. Re-exported from build_phases.py
    so every existing caller (notably build.py) keeps working unchanged —
    the same re-export pattern build_phases.py already uses for
    build_precommit_config from build_precommit.py. ``check_command_reachability``
    defers its import of build_phases's shared ``TEMPLATES_DIR`` constant and
    ``_log`` logger to function scope via ``import build_phases as _bp``, both
    to avoid a circular import at module load time (build_phases.py imports
    this module at its own top level) and so tests that monkeypatch
    ``build_phases.TEMPLATES_DIR`` continue to take effect.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Command-reference reachability guard (BP-900g-1 / BP-900g-1-i guardrail)
# ---------------------------------------------------------------------------

#: Matches handoff calls in a deployed command body, capturing the call name
#: (group 1) and the raw target string (group 2). Every form below is present
#: in the real deployed command corpus:
#:
#:     Workflow("target")                     positional, double quote
#:     Workflow('target')                     positional, single quote
#:     Workflow(`target`)                     positional, backtick
#:     Skill(skill="target", args="...")      keyword, `=`
#:     Workflow(name: "target", args: {...})  keyword, `:`
#:
#: The original pattern required a quote immediately after ``(``, so it saw
#: only the two positional-quoted forms. A probe carrying three unmistakably
#: bogus targets in the kwarg, named-arg and backtick forms produced ZERO
#: verdicts — 5 of the 9 live call sites in the deployed tree were invisible
#: to the guard, which also meant a "full-tree scan found 0 problems" result
#: was partly just the scanner failing to look (BP-900g-1).
#:
#: Backticks are matched because this repo's own conventions use them for
#: inline code, and a structural regex that only understands quotes silently
#: skips them.
_HANDOFF_TARGET_RE = re.compile(
    r"""\b(Workflow|Skill)\(\s*                # call name, open paren
        (?:[A-Za-z_][A-Za-z0-9_]*\s*[:=]\s*)?  # optional keyword: skill= / name:
        ["'`]([^"'`]+)["'`]                    # quoted target (", ' or `)
    """,
    re.VERBOSE,
)


def _handoff_target_resolves(
    target: str,
    kind: str,
    output_root: Path,
    registered_workflows: set[str],
    registered_skills: set[str],
) -> bool:
    """Return True if a single Workflow()/Skill() handoff target resolves post-deploy.

    Name-form targets (no "/") resolve via deployed-registry membership only
    (BP-900g-1-i): the target must equal the stem of a ``*.js`` file directly
    under ``output_root/workflows/`` (kind="workflow") or the name of a
    directory directly under ``output_root/skills/`` (kind="skill").
    Path-form targets (containing "/") resolve ONLY as a literal relative
    path against output_root (BP-900g-1) — a path such as
    "scripts/workflows/foo.js" is never rewritten or special-cased into the
    name-form registry lookup, even when "foo" is itself registered.

    This is a pure function — no I/O — per the project Error Handling Policy
    (Rule 4).

    Args:
        target: The raw handoff target string extracted from a command body.
        kind: "workflow" or "skill".
        output_root: Absolute path to the consolidated, already-deployed
            build output directory.
        registered_workflows: Stems of ``*.js`` files directly under
            ``output_root/workflows/``.
        registered_skills: Names of directories directly under
            ``output_root/skills/``.

    Returns:
        True if the target resolves to a deployed artifact; False otherwise.
    """
    if "/" not in target:
        registry = registered_workflows if kind == "workflow" else registered_skills
        return target in registry
    return (output_root / target).exists()


def _resolve_declared_workflows_enabled(
    config: dict[str, Any] | None,
) -> tuple[bool, bool]:
    """Read the declared ``config["workflows"]["enabled"]`` value.

    This is the ONLY source ``check_command_reachability`` consults to decide
    whether a name-form workflow reference should be skipped — never whether
    ``output_root/workflows/`` happens to exist on disk (BP-100n-2). The
    default (``config`` absent, or ``config["workflows"]`` absent) is
    ``False``, matching ``build_workflow_scripts()``'s own documented default
    so the guard and the producer can never disagree about whether the
    capability is enabled.

    A declaration that cannot be read (``config["workflows"]`` present but
    not a dict, or its ``"enabled"`` value present but not a bool) is a
    distinct, reported condition — it must never silently collapse to "off".

    This is a pure function — no I/O — per the project Error Handling Policy
    (Rule 4).

    Args:
        config: The build's merged configuration dict, or ``None`` for
            legacy callers that have not been updated to pass one (treated
            as "no declaration available", which defaults to disabled — the
            same as an absent ``workflows`` key).

    Returns:
        A ``(enabled, malformed)`` tuple. When ``malformed`` is ``True``,
        ``enabled`` is meaningless and must not be consulted — the caller
        must report an "unreadable declaration" condition instead of
        treating it as either enabled or disabled.
    """
    if config is None:
        return False, False
    workflows_config = config.get("workflows", {}) if isinstance(config, dict) else {}
    if not isinstance(workflows_config, dict):
        return False, True
    enabled = workflows_config.get("enabled", False)
    if not isinstance(enabled, bool):
        return False, True
    return enabled, False


def check_command_reachability(
    output_root: Path, config: dict[str, Any] | None = None
) -> list[dict]:
    """Scan deployed commands for Workflow()/Skill() targets unresolvable post-deploy.

    Extracts every ``Workflow("...")``/``Skill("...")`` handoff target from
    every ``*.md`` file directly under ``output_root/commands/``, resolves
    each against the TRUE post-deploy layout, and returns one verdict dict
    per unresolvable target (BP-900g-1). A target resolves if EITHER it
    names a registered workflow/skill in the deployed registry (name-form,
    BP-900g-1-i) OR it is a literal path that exists relative to
    output_root (path-form). A bare ``.js`` path such as
    "scripts/workflows/build-feature.js" does NOT resolve, because
    ``build_workflow_scripts()`` deploys workflow ``.js`` files to
    ``output_root/workflows/``, never ``output_root/scripts/workflows/``.

    This is the COMMAND-SIDE analogue of the BP-811 ``.claude/workflows``
    shim guardrail (BP-811 resolves the deployed workflow artifact's own
    reachability; this function resolves the COMMAND's reference to it). It
    does not modify or re-parent BP-811.

    Whether a name-form workflow reference is skipped is decided SOLELY from
    the declared ``config["workflows"]["enabled"]`` value (via
    ``_resolve_declared_workflows_enabled``), never from whether
    ``output_root/workflows/`` happens to exist on disk (BP-100n-2). A
    declaration of "enabled" with no deployed output is exactly the failure
    this guard exists to catch and is reported, not skipped; a malformed
    declaration is reported as a distinct "unreadable" condition; every skip
    the guard performs is logged at WARNING, naming the target and stating
    that the skip was authorised by the declared configuration value, so a
    skipped check is never indistinguishable from one that ran and passed.

    Per the project Error Handling Policy (Rule 1 / Rule 3), reading a
    command file is external I/O: a read failure is logged at WARNING and
    that file is skipped (best-effort — an unreadable command cannot be
    scanned, which is a distinct failure mode from an unresolvable target).

    Args:
        output_root: Absolute path to the consolidated, ALREADY-DEPLOYED
            build output directory (e.g. ``<target>/.leafcutter``), expected
            to contain ``commands/*.md``, ``workflows/*.js``, and
            ``skills/*/`` post-deploy.
        config: The build's merged configuration dict, read for
            ``config["workflows"]["enabled"]``. Defaults to ``None`` (treated
            as "disabled") for legacy callers; new callers should always pass
            the same configuration object the build itself used to decide
            whether to produce the workflows output.

    Returns:
        List of dicts, one per unresolvable target::

            {
                "command": Path,               # the command .md file
                "target":  str,                # the raw handoff target string
                "kind":    "workflow" | "skill",
                "reason":  str,                 # names the target and states
                                                 # it does not resolve to a
                                                 # deployed artifact post-deploy
            }

        Empty list means every extracted reference resolves (build may
        proceed) — mirroring the "ok=true iff empty" contract established by
        ``detect_deploy_collisions()`` (BP-100m) in this same module.
    """
    import build_phases as _bp

    # Every platform surface build_workflows() deploys prose commands to — not
    # just the Claude one. Scanning only "commands/" left 23 real command files
    # under gemini/workflows/ unscanned, two of them carrying live Skill()
    # handoffs, so the guard degraded toward a silent no-op for Antigravity /
    # cursor / copilot / cline adopters (BP-900g-1).
    _COMMAND_SURFACES = (
        "commands",
        "gemini/workflows",
        "cursor/rules",
        "copilot-instructions",
        "cline/rules",
    )
    command_dirs = [
        d for d in (output_root / sub for sub in _COMMAND_SURFACES) if d.is_dir()
    ]

    if not command_dirs:
        # Fail closed, but only where failing closed is meaningful.
        #
        # "I found nothing to inspect" must not be reported as "everything
        # resolves" — that is the defect class this guard belongs to. But two
        # different situations reach this branch and only one of them is a
        # problem:
        #
        #   (a) Nothing was deployed at all (output_root absent), or the
        #       package ships no command templates in the first place. There
        #       is genuinely nothing for this guard to police, and blocking
        #       here would break legitimate minimal builds.
        #   (b) The package HAS command templates and a deploy did happen, yet
        #       no command surface exists under output_root. Commands were
        #       written somewhere this guard is not looking, so its silence
        #       would be meaningless.
        #
        # Only (b) is a verdict.
        package_has_commands = any(
            (_bp.TEMPLATES_DIR / sub).is_dir() and any((_bp.TEMPLATES_DIR / sub).glob("*.md"))
            for sub in ("commands", "workflows")
        )
        if not output_root.is_dir() or not package_has_commands:
            return []
        return [
            {
                "command": output_root,
                "target": "(none)",
                "kind": "scan",
                "reason": (
                    f"no deployed command directory found under {output_root} "
                    f"(looked for: {', '.join(_COMMAND_SURFACES)}), yet the "
                    "package does ship command templates. The reachability "
                    "guard inspected zero commands and cannot confirm any "
                    "handoff target resolves."
                ),
            }
        ]

    workflows_dir = output_root / "workflows"
    workflows_deployed = workflows_dir.is_dir()
    registered_workflows = (
        {p.stem for p in workflows_dir.glob("*.js")} if workflows_deployed else set()
    )
    # The SKIP decision below is taken from the declared configuration value
    # ONLY (BP-100n-2) — `workflows_deployed` above is used solely to build
    # the registry `registered_workflows` resolves against, never to decide
    # whether a name-form reference should be skipped, on ANY call path.
    #
    # A caller that omits `config` entirely (e.g. a legacy positional-only
    # call) is NOT special-cased back onto the filesystem heuristic: that
    # heuristic is precisely the defect this AC removes, and reintroducing
    # it on one code path just makes it harder to find, not fixed.
    # `_resolve_declared_workflows_enabled(None)` deliberately returns
    # `(False, False)` — "no declaration supplied" is treated as
    # declared-disabled, matching `build_workflow_scripts()`'s own
    # documented default, never as "go check the filesystem instead."
    workflows_declared_enabled, workflows_declaration_malformed = (
        _resolve_declared_workflows_enabled(config)
    )
    skills_dir = output_root / "skills"
    registered_skills = (
        {p.name for p in skills_dir.iterdir() if p.is_dir()}
        if skills_dir.is_dir()
        else set()
    )

    verdicts: list[dict] = []
    command_paths = sorted(
        {p for d in command_dirs for p in d.rglob("*.md")}
    )
    for command_path in command_paths:
        try:
            text = command_path.read_text(encoding="utf-8")
        except OSError as exc:
            _bp._log.warning(
                "check_command_reachability: cannot read %s: %s",
                command_path,
                exc,
            )
            # Fail closed rather than `continue`. Skipping an unreadable
            # command silently meant a file the guard could not open counted
            # as a file with no problems: `chmod 000` on a command holding a
            # known-broken target produced zero verdicts and an exit-0 build.
            # A guard whose purpose is fail-closed enforcement must not report
            # "pass" for input it never read (BP-900g-1).
            verdicts.append(
                {
                    "command": command_path,
                    "target": "(unreadable)",
                    "kind": "scan",
                    "reason": (
                        f"cannot read deployed command {command_path.name}: "
                        f"{exc}. The reachability guard could not inspect it, "
                        "so its handoff targets are unverified."
                    ),
                }
            )
            continue

        for call, target in _HANDOFF_TARGET_RE.findall(text):
            kind = "workflow" if call == "Workflow" else "skill"

            # ``workflows.enabled`` is a documented opt-in toggle, and
            # build_workflow_scripts() writes nothing when it is false — but
            # the shipped command templates reference workflows by name
            # unconditionally. Path-form targets are still checked below
            # unconditionally: those can never resolve regardless of the
            # toggle, which is the case BP-900g-1 actually exists to catch.
            #
            # The skip decision for a name-form workflow reference is taken
            # from the DECLARED configuration value alone (BP-100n-2) — never
            # from whether output_root/workflows/ happens to exist. That
            # conflated two opposite states: deliberately disabled (skip is
            # correct) versus enabled but undeployed (every reference is now
            # broken, which is exactly when this guard must fire).
            if kind == "workflow" and "/" not in target:
                if workflows_declaration_malformed:
                    verdicts.append(
                        {
                            "command": command_path,
                            "target": target,
                            "kind": kind,
                            "reason": (
                                "cannot determine whether workflows are "
                                "enabled: config['workflows'] is malformed "
                                "(expected a dict with a boolean 'enabled' "
                                f"key), so workflow target {target!r} "
                                f"referenced by {command_path.name} is "
                                "unverified"
                            ),
                        }
                    )
                    continue
                elif not workflows_declared_enabled:
                    _bp._log.warning(
                        "check_command_reachability: %s references workflow "
                        "%r, but workflows are declared disabled "
                        "(config['workflows']['enabled'] is False); skipping "
                        "name-form resolution for this target because the "
                        "declared configuration authorises the skip.",
                        command_path.name,
                        target,
                    )
                    continue
                # workflows_declared_enabled is True: fall through to the
                # normal resolution below, which reports the target as
                # unresolvable when workflows.enabled=True but no matching
                # workflow was actually deployed — the case this guard
                # exists to catch.

            if _handoff_target_resolves(
                target, kind, output_root, registered_workflows, registered_skills
            ):
                continue
            verdicts.append(
                {
                    "command": command_path,
                    "target": target,
                    "kind": kind,
                    "reason": (
                        f"{kind} target {target!r} referenced by "
                        f"{command_path.name} does not resolve to a "
                        "deployed artifact post-deploy"
                    ),
                }
            )

    return verdicts


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved check_command_reachability,
#   _handoff_target_resolves, _resolve_declared_workflows_enabled, and
#   _HANDOFF_TARGET_RE verbatim from build_phases.py into this new sibling
#   module to bring build_phases.py under the 400-counted-line check-file-size
#   limit. Re-exported from build_phases.py so build.py and every test import
#   keeps working. (#refactor/build-phases-size-limit)
# - 2026-08-18 18:30 [python-coder/06_bp900g1_command_reachability_guard]: Added
#   command-reference reachability guardrail (BP-900g-1 / BP-900g-1-i). Two
#   new symbols: check_command_reachability() scans every deployed command
#   under output_root/commands/*.md, extracts Workflow(...)/Skill(...)
#   handoff targets via _HANDOFF_TARGET_RE, and resolves each against the
#   real post-deploy layout: name-form targets (no "/") via deployed-registry
#   membership (workflow .js stems / skill directory names), path-form
#   targets (containing "/") as a literal relative path against output_root.
#   _handoff_target_resolves() is the pure per-target resolution helper. This
#   replaces the previously phantom-done BP-900g-1 finding -- the name-based
#   Workflow("build-feature") workaround already applied to the real command
#   templates is now backed by a real guard that would catch a regression
#   back to the non-resolving path form. COMMAND-SIDE analogue of BP-811 (the
#   .claude/workflows shim); does not modify or re-parent BP-811.
#   (#EPIC-BuildPipelinePhantomRemediation/06)
# ===========================================================================
