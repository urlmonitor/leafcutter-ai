"""
MODULE: build_helpers
GOAL: Optional build steps — manifest writing, diagram update, doc seeding, and shim install.
BUSINESS CONTEXT: Extracted from build.py to keep that module under the 400-line
    limit. These helpers are invoked by main() in build.py when the
    corresponding CLI flags (--update-diagrams, --seed-docs) are set or after
    the build phases complete (manifest write, shim install). They are standalone
    functions with no shared state; moving them here requires only an import
    change in build.py.
ARCHITECTURE: Each function is self-contained and safe to import independently.
    All exceptions are caught and surfaced as printed warnings — helpers never
    abort the build. write_build_manifest supports both Direction A (template
    hashes) and Direction B (output_mappings) manifest sections.

    BP-100k-1/-2 (2026-08-18): Direction A now records a fingerprint for
    every template family the drift gates actually scan — not just
    templates/agents/*.md — by mirroring check_build_drift.py's own scanned
    set (templates/agents/*.md + templates/scripts/commit_guardian/*.py).
    Direction B now records output_mappings keys at the CANONICAL,
    shim-resolved path (e.g. ``.claude/agents/README.md``,
    ``.agents/rules/foo.md``) that check_output_drift.py actually looks up,
    rather than the pre-shim ``output_root``-relative path — the earlier
    keys (e.g. ``agents/README.md``) never matched any real on-disk file, so
    every deployed output was permanently "not in output_mappings". The
    agents/commands/workflows/hooks families are derived from
    build_phases._compute_phase_mappings() (the same enumeration build.py's
    own collision guard uses) rather than a second hand-written inventory,
    and translated to their canonical path via ``shim_map`` — the same
    table install_shims() uses to create the shims — so a new deploy
    phase or a new shim entry extends coverage on both sides without a
    separate edit here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_colors import dry_run as _dry_run
from build_colors import error as _error
from build_colors import info as _info
from build_colors import success as _success
from build_colors import warn as _warn

# ---------------------------------------------------------------------------
# Canonical (shimmed) output directory table — the SINGLE source of truth for
# translating an output_root-relative deploy path (e.g. "agents/README.md")
# into the canonical tool path check_output_drift.py actually scans (e.g.
# ".claude/agents/README.md"). install_shims() uses this exact table (in
# place, not copied) to create the shims; _compute_output_mappings() reuses
# it to key output_mappings entries the same way — never a second,
# independently-maintained copy. Named ``shim_map`` (lowercase, matching
# install_shims()'s historical local-variable name) rather than an
# ALL_CAPS module constant so it stays the literal `tests/
# test_build_artifact_parity.py::TestShimMapCoversAllUserFacingCategories`
# AST-parses for — a structural parity test unrelated to this ticket.
# ---------------------------------------------------------------------------
shim_map: list[tuple[str, str]] = [
    (".claude/agents", "agents"),
    (".claude/skills", "skills"),
    (".claude/commands", "commands"),
    (".claude/hooks", "hooks"),
    (".claude/workflows", "workflows"),
    (".gemini", "gemini"),
    # Bridge pre-consolidation scripts/ paths to .leafcutter/scripts/ so that
    # tests and hooks that reference scripts/commit_guardian/,
    # scripts/doc_compliance/, and scripts/feedback/ still resolve after the
    # ADR-004 consolidation moved those directories under .leafcutter/scripts/.
    # Required for CI (fresh-clone) and for any test suite that adds these
    # directories to sys.path at the old location (ADR-016).
    ("scripts/commit_guardian", "scripts/commit_guardian"),
    ("scripts/doc_compliance", "scripts/doc_compliance"),
    ("scripts/feedback", "scripts/feedback"),
]

# Reverse lookup covering EVERY shim_map entry, single- or multi-segment
# (BP-100k-5 root cause fix). This used to be restricted to single-path-
# component output_rel entries under the theory that the multi-segment
# "scripts/commit_guardian" family was "copied verbatim, not rendered
# per-template-file by _compute_output_mappings" — but that filter is what
# made _canonicalize_output_path() return None for every file under
# scripts/commit_guardian/, scripts/doc_compliance/, and scripts/feedback/,
# silently dropping all of them from output_mappings with no record that
# they were dropped. Those three families ARE now rendered per-file below
# (see the "commit_guardian / doc_compliance / feedback" section), so the
# reverse lookup must resolve their multi-segment prefixes too.
_OUTPUT_REL_TO_CANONICAL: dict[str, str] = {
    output_rel: canonical_rel for canonical_rel, output_rel in shim_map
}


def _load_build_phases_module(package_root: Path):
    """Load ``build_phases.py`` fresh from ``package_root/scripts``.

    ``build_phases.py`` resolves its own module-level constants
    (``TEMPLATES_DIR``, ``PACKAGE_ROOT``, ``REGISTRY_PATH``,
    ``SKILLS_TEMPLATE_DIR``) from ``Path(__file__)`` at import time rather
    than accepting ``package_root`` as a parameter. A bare
    ``import build_phases`` would silently reuse whatever copy of the module
    a PRIOR call already cached in ``sys.modules`` under that bare name —
    reading the wrong package's templates whenever this function runs more
    than once against a different ``package_root`` within the same process
    (exactly the scenario this module's own test suite exercises with
    multiple temp-directory synthetic packages). Loading via
    ``importlib.util.spec_from_file_location`` under a name derived from
    ``package_root`` guarantees a fresh, correctly-rooted module every call.

    Args:
        package_root: Root of the leafcutter package to load
            ``build_phases.py`` from.

    Returns:
        The freshly executed ``build_phases`` module object.
    """
    module_path = package_root / "scripts" / "build_phases.py"
    unique_name = f"_build_helpers_dyn_build_phases_{abs(hash(str(module_path)))}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _template_family(source: Path, templates_dir: Path) -> str | None:
    """Return the top-level template family name for a source template path.

    E.g. ``<templates_dir>/agents/foo.md`` -> ``"agents"``. Used to pick the
    correct render step (compile_agent_template, inject_config, or a raw
    copy) for a ``(source, target)`` pair produced by
    ``build_phases._compute_phase_mappings``.

    Args:
        source: Absolute path to a template source file.
        templates_dir: Absolute path to the package's ``templates/`` root.

    Returns:
        The first path component of ``source`` relative to ``templates_dir``,
        or None if ``source`` is not under ``templates_dir``.
    """
    try:
        rel = source.relative_to(templates_dir)
    except ValueError:
        return None
    return rel.parts[0] if rel.parts else None


def _canonicalize_output_path(
    output_root_path: Path, output_root: Path, target_root: Path
) -> Path | None:
    """Translate an ``output_root``-relative deploy target into its canonical,
    shim-resolved path under ``target_root``.

    Deploy phases (build_agents, build_commands, build_workflows, build_hooks)
    write into ``output_root`` (``.leafcutter/`` by default); ``install_shims``
    then bridges each managed subdirectory to its canonical tool path (e.g.
    ``.claude/agents``). ``check_output_drift.py`` looks up deployed files at
    that canonical path, so ``output_mappings`` keys must use it too — this
    reuses ``shim_map``, the exact table ``install_shims`` uses to create the
    shims, rather than a second hardcoded translation.

    Args:
        output_root_path: Absolute path under ``output_root`` that a deploy
            phase would write to.
        output_root: Absolute path to the consolidated output directory.
        target_root: Absolute path to the target project root.

    Returns:
        The canonical absolute path under ``target_root``, or None when
        ``output_root_path`` is not under ``output_root`` or no prefix of its
        path (checked longest-first) has a canonical shim entry.
    """
    try:
        rel = output_root_path.relative_to(output_root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    # Longest-prefix-first match (BP-100k-5): a single-segment lookup alone
    # cannot resolve a multi-segment shim_map entry like
    # "scripts/commit_guardian" — rel.parts[0] there is just "scripts", which
    # has no canonical entry of its own. Trying the full path first and
    # shortening one segment at a time finds the correct (and most specific)
    # canonical prefix regardless of how many segments it spans.
    parts = rel.parts
    for length in range(len(parts), 0, -1):
        prefix = "/".join(parts[:length])
        canonical_dir = _OUTPUT_REL_TO_CANONICAL.get(prefix)
        if canonical_dir is not None:
            return target_root / canonical_dir / Path(*parts[length:])
    return None


def _compute_output_mappings(
    package_root: Path,
    target_root: Path,
    config: dict[str, Any],
    skipped_sections: list[str] | None = None,
    unwritten: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Compute expected output hashes for all template to output file mappings.

    For each template that build.py renders and writes to the target project,
    computes the SHA-256 of what build.py *actually would write* (i.e. after
    template compilation/injection) and records the template path alongside it.
    This gives check_output_drift.py a ground truth to compare against
    on-disk output files.

    Covers the same template directories that build_phases.py writes, keyed
    by the CANONICAL (post-shim) path check_output_drift.py scans:
    - agents:    templates/agents/*.md      to  .claude/agents/
    - commands:  templates/commands/*.md    to  .claude/commands/
    - workflows: templates/workflows/*.md   to  .claude/commands/
    - hooks:     templates/hooks/*.py       to  .claude/hooks/
    - skills:    templates/skills/**/*      to  .claude/skills/
    - rules:     templates/rules/*.md       to  <output_root>/.agents/rules/
    - workflow scripts: templates/workflows-js/*.js to .claude/workflows/

    The agents/commands/workflows/hooks families are derived from
    ``build_phases._compute_phase_mappings()`` — the same per-platform
    enumeration build.py's own deploy-collision guard uses — rather than a
    second hand-written inventory, then translated to their canonical path
    via ``shim_map`` (BP-100k-2).

    ticket-lifecycle templates are intentionally excluded because those output
    files are user-owned scaffolds (write-if-absent, expected to diverge from
    their template the moment a project customises them) and are therefore
    not subject to the edit-templates-not-built-copies guardrail.

    commit-guardian, doc-compliance, and feedback ARE now covered (BP-100k-5):
    they were previously excluded on the same "maintained by the project
    owner" theory, but unlike the scaffolds above they are agent-authored,
    build-produced, and deployed verbatim — including the drift gates'
    OWN deployed copies. Excluding them meant no manifest key's parent
    directory ever pointed at scripts/commit_guardian/, scripts/doc_compliance/,
    or scripts/feedback/, so check_output_drift.py's derived scan set never
    even walked those directories: 118 deployed files (including both drift
    gates themselves) were invisible to every gate, not merely uncomparable.
    A gate that cannot detect a hand-edit to its own deployed copy cannot be
    relied on to report a pass.

    Args:
        package_root: Root of the leafcutter package.
        target_root: Root of the target project (where outputs are written).
        config: Merged config dict used for placeholder injection.
        skipped_sections: Optional output list (appended to, never read) that
            ``write_build_manifest`` passes so a PARTIAL enumeration failure —
            one section's computation raising while the rest of the function
            completes normally — can be recorded as manifest DATA instead of
            only a build-time-only printed warning (BP-100k-5 follow-up). The
            agents/commands/workflows/hooks section below is currently the
            only one wrapped in a try/except that can leave a gap while the
            surrounding computation still returns a (partial) mappings dict;
            every other section below degrades per-file via an existence
            check, which cannot silently drop a whole family the way an
            uncaught exception from ``_load_build_phases_module`` can. ``None``
            (the default) preserves the pre-existing warn-only behaviour for
            any caller that does not pass it.
        unwritten: Optional output list (appended to, never read) recording
            every per-file existence-gate ``continue`` below as a short
            description (family + relative path) — adversarial review round
            2's B-1(b): "the phase did not write it" must reach the manifest
            as DATA, not vanish as a silent ``continue``. IMPORTANT LIMIT
            (documented rather than guessed away, per the ticket's own
            instruction): every one of these existence gates is, BY THE
            ORIGINAL DESIGN documented at each call site, expected to
            legitimately fire in two situations this function cannot tell
            apart from here — (a) a real, unmodified ``build.py`` run, where
            the check is provably always-true (the phase's own write always
            already happened before this computation runs) and this list
            stays empty, and (b) a deliberately narrow test fixture that
            calls this function after deploying only a subset of phases
            directly. It is also expected to fire for a THIRD, legitimate
            reason no call site currently distinguishes: a family disabled
            by config (e.g. a platform turned off) never gets its output
            written at all, by design. Because none of these three cases can
            be told apart from a fourth — "the phase should have run in a
            real build and silently did not" (e.g. a ``--target-dir``
            mismatch between the deploy phases and this computation) —
            ``unwritten`` is recorded as VISIBILITY DATA ONLY. Neither
            drift gate reads it or blocks on it; wiring it into the verdict
            without being able to make that distinction would false-block
            every narrow fixture and every legitimately-disabled platform
            combination. The ``verified == 0`` floor added to both gates by
            B-1(a) is what actually closes the exploitable case (a build
            that silently produced nothing at all); this field exists so a
            future, more precise gate has the raw material to do better.

    Returns:
        Dict mapping canonical output-relative-path strings to dicts with
        keys ``template`` (template rel-path) and ``expected_output_hash``
        (sha256). May be missing an entire section's entries when
        ``skipped_sections`` records that section as skipped, or individual
        per-file entries recorded in ``unwritten`` — callers that care must
        check both, not just inspect the returned dict for absence.
    """
    scripts_dir = package_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from template_compiler import (  # type: ignore[import]
        compile_agent_template,
        compile_skill_template,
        inject_config,
        _load_registry,
    )

    templates_dir = package_root / "templates"
    registry_path = package_root / "config" / "agent_registry.json"
    agents_list = _load_registry(registry_path)
    skills_root = templates_dir / "skills" if (templates_dir / "skills").exists() else None
    # repo_root == target_root: outputs are deployed into target_root by
    # construction (every output_path below is built from it), so it is the
    # only base every output_mappings key can be correctly relative to — in
    # self-host AND consumer-install alike. No layout detection needed (see
    # write_build_manifest()'s DECISION HISTORY below).
    repo_root = target_root

    output_root_name = config.get("output_root", ".leafcutter")
    output_root = target_root / output_root_name

    # Shared platform-activity table (BP-100k-5): reused below by the skills
    # (gemini/skills), antigravity-instructions, and any future per-platform
    # section, matching the exact default dict build_phases.py's own
    # per-phase functions (build_skills, build_antigravity_instructions) fall
    # back to when config["platforms"] is absent.
    platforms_cfg: dict[str, bool] = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False,
    })

    mappings: dict[str, dict[str, str]] = {}

    def _add(template_path: Path, output_path: Path, content: str | bytes) -> None:
        """Record an output mapping entry (relative paths, expected hash).

        Args:
            template_path: Absolute path to the source template file.
            output_path: Absolute path to the built output file.
            content: Rendered output content — a str for text families
                (template-compiled/config-injected) or raw bytes for a
                verbatim binary/non-text copy (e.g. a non-.md skill asset),
                matching whichever type the real deploy phase would write.
        """
        tpl_key = template_path.relative_to(repo_root).as_posix()
        out_key = output_path.relative_to(repo_root).as_posix()
        payload = content.encode("utf-8") if isinstance(content, str) else content
        mappings[out_key] = {
            "template": tpl_key,
            "expected_output_hash": hashlib.sha256(payload).hexdigest(),
        }

    # --- agents / commands / workflows(->commands) / hooks ---
    # Derived from the SAME (source, target) enumeration build.py's collision
    # guard uses, so a new deploy phase added there extends coverage here
    # automatically instead of requiring a parallel edit. Best-effort: a
    # package_root without a full scripts/ tree (e.g. a minimal fixture that
    # only exercises one of the other families below) degrades to skipping
    # just this section instead of aborting the whole computation.
    build_phases_mod = None
    phase_mappings: list[tuple[Path, Path]] = []
    try:
        build_phases_mod = _load_build_phases_module(package_root)
        phase_mappings = build_phases_mod._compute_phase_mappings(output_root, config)
    except (OSError, ImportError, AttributeError, ValueError) as exc:
        _warn(f"could not enumerate deploy-phase output mappings: {exc}")
        # Recorded as manifest DATA, not just a build-time-only printed
        # warning (this ticket's own fix): the agents/commands/workflows/
        # hooks section is silently empty from here on for THIS build, and
        # nothing downstream of this function can tell "genuinely zero
        # outputs in this family" apart from "the enumeration crashed and
        # every entry was dropped" unless the reason is written down
        # alongside the (now partial) output_mappings dict itself.
        if skipped_sections is not None:
            skipped_sections.append(
                "agents/commands/workflows/hooks (deploy-phase enumeration): "
                f"{type(exc).__name__}: {exc}"
            )

    def _render_phase_source(source: Path, family: str | None) -> str | None:
        """Render a phase-mapping source exactly as its deploy phase would.

        Args:
            source: Absolute path to the template source file.
            family: Top-level template family name (from ``_template_family``).

        Returns:
            The rendered content string, or None if ``family`` is not one of
            the families handled by this section (caller should skip it).
        """
        if family == "agents":
            content = compile_agent_template(
                source, config,
                registry_path=registry_path,
                agents=agents_list,
                skills_root=skills_root,
            )
            return build_phases_mod._inject_components_table(content, package_root)
        if family in ("commands", "workflows"):
            return inject_config(source.read_text(encoding="utf-8"), config)
        if family == "hooks":
            return source.read_text(encoding="utf-8")
        return None

    for source, target in phase_mappings:
        # ``target`` is the PRE-shim, output_root-relative path the real
        # deploy phase (build_agents/build_commands/build_workflows/
        # build_hooks) actually writes to. Gated on it existing (BP-100k-6
        # interaction fix): build.py's real sequence writes the manifest
        # BEFORE install_shims() runs, so on an untouched real build this
        # phase's own write always already happened by the time this
        # computation runs — the check changes nothing there. It matters
        # only for a fixture that computes a manifest after deploying a
        # narrower subset of phases directly (e.g. only build_agents) — a
        # key predicting an undeployed sibling family (commands/workflows/
        # hooks templates that exist in the SOURCE tree regardless of which
        # phase actually ran) would otherwise be recorded, and BP-100k-6's
        # missing-artifact verdict would then correctly, but unhelpfully,
        # BLOCK on a file that specific fixture never asked to deploy.
        if not target.exists():
            if unwritten is not None:
                unwritten.append(
                    "agents/commands/workflows/hooks: "
                    f"{target.relative_to(output_root).as_posix()} not found "
                    "(pre-shim; expected if this build/fixture did not "
                    "deploy this phase)"
                )
            continue

        canonical_output = _canonicalize_output_path(target, output_root, target_root)
        if canonical_output is None:
            continue  # no canonical shim for this family (e.g. cursor/copilot)

        content = _render_phase_source(source, _template_family(source, templates_dir))
        if content is None:
            continue

        _add(source, canonical_output, content)

    # --- skills (.md compiled; every other real file copied verbatim) ---
    # Mirrors build_skills()'s exact per-file branch (compile .md via
    # compile_skill_template; copy everything else byte-for-byte) over the
    # exact same per-skill file set — build_phases._skill_deploy_files()
    # (files only, __pycache__ excluded) — so a committed non-.md asset such
    # as a skill's own scripts/*.py is covered exactly when build_skills()
    # would also copy it, and a stray compiled .pyc cache is excluded on
    # BOTH sides rather than becoming an unstable, permanently-drifting
    # comparison target. Skips a deprecated skill via the SAME
    # build_phases._skill_is_deprecated() check build_skills() itself calls,
    # so the manifest can never predict a hash for a skill build_skills()
    # would not write (BP-100k-3: this previously made a deprecated skill's
    # stale manifest entry report as permanent drift, and silently omitted
    # every non-.md skill script from coverage entirely — both are the
    # "recorded set != real copy set" defect BP-100k-2 forbids).
    # Both platform output paths check_output_drift.py can reach are now
    # computed (BP-100k-5): build_skills() deploys the SAME per-skill file
    # set to both ``.claude/skills/`` (claude) and ``.gemini/skills/``
    # (antigravity) via its own ``platform_dirs`` table — recording only the
    # claude path left every real ``.gemini/skills/`` file unregistered (52
    # of the 174 files this AC's red baseline found).
    # Best-effort: degrades to the old .md-only, no-deprecated-check,
    # no-pycache-exclusion behaviour if build_phases_mod could not be loaded
    # (see the try/except above), rather than aborting the whole computation.
    skills_tpl_dir = templates_dir / "skills"
    if skills_tpl_dir.is_dir():
        # Each entry pairs the canonical (post-shim) directory with its
        # PRE-shim, output_root-relative equivalent — the existence check
        # below (BP-100k-6 interaction fix, same reasoning as the
        # phase_mappings loop above) must probe the latter, since the shim
        # bridging the former back up to target_root is not created until
        # install_shims() runs, which is AFTER the manifest is written even
        # on a real, fully-deployed build.
        skill_canonical_dirs: list[tuple[str, str]] = [(".claude/skills", "skills")]
        if platforms_cfg.get("antigravity", True):
            skill_canonical_dirs.append((".gemini/skills", "gemini/skills"))
        for skill_dir in sorted(skills_tpl_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if build_phases_mod is not None:
                if build_phases_mod._skill_is_deprecated(skill_dir):
                    continue
                skill_files = build_phases_mod._skill_deploy_files(skill_dir)
            else:
                skill_files = sorted(f for f in skill_dir.rglob("*") if f.is_file())
            for tpl in skill_files:
                rel = tpl.relative_to(skills_tpl_dir)
                content = (
                    compile_skill_template(tpl, config)
                    if tpl.suffix == ".md"
                    else tpl.read_bytes()
                )
                for canonical_dir, output_rel in skill_canonical_dirs:
                    if not (output_root / output_rel / rel).exists():
                        if unwritten is not None:
                            unwritten.append(
                                f"skills ({output_rel}): {rel.as_posix()} not "
                                "found (pre-shim; expected if this build/"
                                "fixture did not deploy this platform)"
                            )
                        continue
                    output = target_root / canonical_dir / rel
                    _add(tpl, output, content)

    # --- commit_guardian / doc_compliance / feedback (BP-100k-5) ---
    # build.py's internal_phases list (_run_phases()) calls
    # build_commit_guardian / build_doc_compliance / build_feedback with
    # ``output_root`` — despite each function's own parameter being named
    # ``target_root`` — so these three families land at
    # ``<output_root>/scripts/<family>/``, exactly like the artifact-phase
    # families above. install_shims() then bridges
    # ``<target_root>/scripts/<family>`` back to it via the MULTI-SEGMENT
    # shim_map entries ("scripts/commit_guardian", "scripts/doc_compliance",
    # "scripts/feedback") that _canonicalize_output_path()'s longest-prefix
    # match now resolves. Each family's per-file render rule below mirrors
    # its real build phase exactly (see build_phases.py):
    # - commit_guardian: .json/.py/.yaml/.yml/.md get inject_config; every
    #   other file is copied verbatim (build_commit_guardian).
    # - doc_compliance: EVERY file gets inject_config regardless of
    #   extension (build_doc_compliance).
    # - feedback: .py/.yaml/.yml/.json/.md get inject_config; every other
    #   file is copied verbatim (build_feedback).
    # __pycache__ is excluded on the source side, matching every other
    # section's exclusion and check_output_drift.py's own scan-side
    # exclusion, so neither side ever tries to compare a bytecode cache.
    _cg_text_suffixes = (".json", ".py", ".yaml", ".yml", ".md")
    _fb_text_suffixes = (".py", ".yaml", ".yml", ".json", ".md")

    def _register_direct_output_family(
        src_dir: Path, output_rel: str, text_suffixes: tuple[str, ...] | None
    ) -> None:
        """Register every file a directly-``output_root``-deployed family writes.

        Args:
            src_dir: Absolute path to the template source directory.
            output_rel: ``output_root``-relative deploy target directory
                (e.g. ``"scripts/commit_guardian"``) — matches the real
                internal_phase's own ``output_dir`` computation.
            text_suffixes: Extensions rendered via ``inject_config``; every
                other file is copied verbatim. ``None`` means every file is
                rendered via ``inject_config`` (doc_compliance's contract).

        Only registers an entry when ``output_root_path`` (the PRE-shim path
        the real deploy phase actually writes to) already exists on disk
        (BP-100k-2's own contract: "output_mappings must equal what the
        deploy phases write, in both directions" — a key naming a path
        nothing has written yet is a claim of coverage no gate can act on).
        Checked at the ``output_root``-relative path rather than the
        post-shim ``canonical_output`` path deliberately: build.py's real
        sequence writes the manifest BEFORE ``install_shims()`` runs (see
        ``main()``'s "Build manifest" heading preceding its "Shim install"
        heading), so the shim/symlink bridging ``canonical_output`` back up
        to ``target_root`` does not exist yet at THIS computation's own call
        time even on a real, fully-deployed build — only the underlying
        ``output_root`` write does. Checking the shimmed path here would
        make every shimmed family register nothing on a real build, which is
        the opposite of this section's purpose.
        In a real full ``build.py`` run this phase's own deploy step always
        runs before ``write_build_manifest()``, so ``output_root_path``
        is always already there and this changes nothing; it only matters
        for a test fixture that deploys a narrower subset of phases directly
        (BP-100k-2's own ``test_bp_100k_2.py`` fixtures do exactly this).
        """
        if not src_dir.is_dir():
            return
        for tpl in sorted(
            f for f in src_dir.rglob("*") if f.is_file() and "__pycache__" not in f.parts
        ):
            rel = tpl.relative_to(src_dir)
            output_root_path = output_root / output_rel / rel
            if not output_root_path.exists():
                if unwritten is not None:
                    unwritten.append(
                        f"{output_rel}: {rel.as_posix()} not found "
                        "(pre-shim; expected if this build/fixture did not "
                        "deploy this family)"
                    )
                continue
            canonical_output = _canonicalize_output_path(output_root_path, output_root, target_root)
            if canonical_output is None:
                continue
            if text_suffixes is None or tpl.suffix in text_suffixes:
                content = inject_config(tpl.read_text(encoding="utf-8"), config)
            else:
                content = tpl.read_bytes()
            _add(tpl, canonical_output, content)

    _register_direct_output_family(
        templates_dir / "scripts" / "commit_guardian", "scripts/commit_guardian", _cg_text_suffixes
    )
    _register_direct_output_family(
        templates_dir / "doc-compliance", "scripts/doc_compliance", None
    )
    _register_direct_output_family(
        templates_dir / "scripts" / "feedback", "scripts/feedback", _fb_text_suffixes
    )

    # --- antigravity instructions (.gemini/instructions.md) (BP-100k-5) ---
    # Mirrors build_antigravity_instructions() exactly: a single
    # inject_config()-rendered file, written only when the antigravity
    # platform is active. Gated on the PRE-shim output_root path existing —
    # not the post-shim ``.gemini/instructions.md`` canonical path — for the
    # same shim-timing reason documented on ``_register_direct_output_family``
    # above: build.py writes the manifest before install_shims() runs, so the
    # ``.gemini`` symlink is not there yet even on a real, fully-deployed
    # build; only ``output_root/gemini/instructions.md`` (this phase's own,
    # un-shimmed write target) is.
    antigravity_tpl = templates_dir / "ANTIGRAVITY.md.template"
    antigravity_output_root_path = output_root / "gemini" / "instructions.md"
    if (
        antigravity_tpl.is_file()
        and platforms_cfg.get("antigravity", True)
        and antigravity_output_root_path.exists()
    ):
        canonical_antigravity_output = _canonicalize_output_path(
            antigravity_output_root_path, output_root, target_root
        )
        if canonical_antigravity_output is not None:
            _add(
                antigravity_tpl,
                canonical_antigravity_output,
                inject_config(antigravity_tpl.read_text(encoding="utf-8"), config),
            )

    # --- claude settings.json (BP-100k-5) ---
    # Mirrors build_claude_settings(): a single raw (no config injection)
    # byte-for-byte copy, shimmed via install_shims()'s single-FILE
    # file_shims list (".claude/settings.json" -> "settings.json") rather
    # than the directory-shim shim_map table used everywhere else above.
    # Gated on the PRE-shim ``output_root/settings.json`` existing, for the
    # identical shim-timing reason as the antigravity section immediately
    # above — the ``.claude/settings.json`` file-shim is also created by
    # install_shims(), which runs after the manifest is written.
    settings_tpl = templates_dir / "settings.json"
    settings_output_root_path = output_root / "settings.json"
    if settings_tpl.is_file() and settings_output_root_path.exists():
        _add(
            settings_tpl,
            target_root / ".claude" / "settings.json",
            settings_tpl.read_bytes(),
        )

    # --- config scaffolds landing under .claude/ (BP-100k-5) ---
    # build_config_scaffolds() is a write-if-absent "scaffold" phase, but
    # unlike docs/vision.md or docs/roadmap.json (excluded above because they
    # sit outside the .claude//.gemini//scripts/ surface this gate scans),
    # its two ".claude/"-rooted outputs sit squarely inside it — so on a
    # FRESHLY built tree (the only scenario BP-100k-5-i's zero-unexamined
    # assertion covers) they must be registered like any other deterministic
    # output rather than left to fall out of every count. Reads the SAME
    # config keys and defaults build_config_scaffolds() itself reads, so a
    # project that overrides either path still gets the correctly-keyed entry.
    #
    # Registration is gated on TWO conditions, not just existence: the file
    # must exist AND its current on-disk bytes must still equal the fresh
    # scaffold render. Existence alone (like every other section above) skips
    # a fixture/run where the scaffold phase never ran; the content check
    # additionally protects a project that has legitimately customised the
    # scaffold after its first write (build_config_scaffolds()'s whole
    # purpose is to hand the file to the project once and never touch it
    # again) from being registered against a hash it can no longer match —
    # which would make every future build report the customisation itself as
    # drift and tell the user to "edit the template", the wrong advice for a
    # write-if-absent, user-owned file. A freshly built tree (what
    # BP-100k-5-i's zero-unexamined assertion actually covers) always passes
    # this check, since nothing has had the chance to customise it yet.
    def _register_scaffold_if_unmodified(
        template_path: Path, output_path: Path, content: str
    ) -> None:
        """Register a write-if-absent scaffold only if still pristine.

        Args:
            template_path: Source-of-truth path recorded as the manifest
                "template" key (a real template file, or the authoring
                script itself when the content has no template file of
                its own — see the changelog_categories.md call site).
            output_path: Absolute path the scaffold phase would have
                written to.
            content: The fresh scaffold content the phase would render today.
        """
        if not output_path.exists():
            if unwritten is not None:
                try:
                    rel_out = output_path.relative_to(target_root).as_posix()
                except ValueError:
                    rel_out = str(output_path)
                unwritten.append(
                    f"scaffolds: {rel_out} not found (expected if this "
                    "build/fixture did not run the scaffold phase)"
                )
            return
        try:
            on_disk = output_path.read_text(encoding="utf-8")
        except OSError as exc:
            _warn(f"could not read {output_path} to check scaffold staleness: {exc}")
            return
        if on_disk != content:
            return  # Customised by the project — not this build's to register.
        _add(template_path, output_path, content)

    precommit_autofix_tpl = templates_dir / "scripts" / "precommit-autofix.json"
    if precommit_autofix_tpl.is_file():
        precommit_autofix_rel = config.get(
            "precommit_autofix_config_path", ".claude/precommit-autofix.json"
        )
        _register_scaffold_if_unmodified(
            precommit_autofix_tpl,
            target_root / precommit_autofix_rel,
            precommit_autofix_tpl.read_text(encoding="utf-8"),
        )

    # changelog_categories.md has no template FILE of its own — its content
    # is a hardcoded string constant in build_config_scaffolds.py — so the
    # constant is imported (never duplicated as a second, driftable literal
    # here) and the source-of-truth script file itself is named as the
    # manifest "template" key. A pure string constant carries no filesystem
    # dependency, so importing it under whatever module-cache name is
    # already active is safe even though build_config_scaffolds.py, like
    # build_phases.py, resolves other (unused-here) constants from its own
    # ``__file__`` at import time.
    changelog_categories_rel = config.get(
        "changelog_categories_path", ".claude/changelog_categories.md"
    )
    build_config_scaffolds_src = package_root / "scripts" / "build_config_scaffolds.py"
    if build_config_scaffolds_src.is_file():
        try:
            from build_config_scaffolds import (  # type: ignore[import]
                _CHANGELOG_CATEGORIES_SCAFFOLD,
            )
        except ImportError as exc:
            _warn(f"could not import changelog categories scaffold content: {exc}")
        else:
            _register_scaffold_if_unmodified(
                build_config_scaffolds_src,
                target_root / changelog_categories_rel,
                _CHANGELOG_CATEGORIES_SCAFFOLD,
            )

    # --- committed .claude/ scaffold mirror (BP-100k-5-ii) ---
    # BP-100k-5's longest-prefix-first canonicalisation put ".claude" itself
    # into check_output_drift.py's scan set: ANY bare-".claude"-parented key
    # (settings.json, precommit-autofix.json, changelog_categories.md — all
    # registered above) makes _derive_scan_dirs() add ".claude" as a whole,
    # and the gate then walks EVERY file under it, not just the three
    # registered ones. That swept up a handful of files this repo commits at
    # a ".claude/"-rooted path with no CURRENT build phase writing to that
    # exact location — docs_root, tickets_inbox_path, and
    # testing_context.readme_path all default OUTSIDE .claude/ today, so
    # build_vision()/build_glossary_seed_files()/build_roadmap()/
    # build_ticket_lifecycle()/build_config_scaffolds() never produce a
    # ".claude/"-rooted docs/tickets/unit_tests/changelogs output for any
    # install using current defaults. The files are real, git-tracked,
    # human-relevant content in THIS repo, not orphaned build debris — they
    # just need a registration/exemption decision like anything else the
    # gate can see.
    #
    # Ten of them (every .gitkeep, tickets/README.md, ticket_lifecycle.json,
    # unit_tests/README.md) still render byte-identical to their real
    # template/constant source today, so the same still-matches-the-pristine
    # -render gate used above for precommit-autofix.json/
    # changelog_categories.md (_register_scaffold_if_unmodified) applies:
    # register while pristine, release the moment a project's copy diverges.
    # .gitkeep files are empty, build-determined placeholders that will never
    # be customised, so they fit this gate cleanly; tickets/README.md,
    # ticket_lifecycle.json, and unit_tests/README.md are generic structural/
    # process boilerplate — like changelog_categories.md above, not a
    # project-identity document — so the same treatment applies.
    #
    # CLAUDE.md, vision.md, roadmap.json, and glossary*.md are deliberately
    # NOT registered here — see the drift_gate_exemption_registry entries in
    # commit_guardian.json for why (the short version: they are "the
    # opposite" of a .gitkeep — seeded once and immediately, permanently
    # owned by the project, so a pristine-render comparison would only ever
    # buy one commit before flipping back to an unregistered gap).
    _claude_tickets_dir = target_root / ".claude" / "tickets"

    ticket_lifecycle_manifest_tpl = package_root / "config" / "ticket_lifecycle.json"
    if ticket_lifecycle_manifest_tpl.is_file():
        _register_scaffold_if_unmodified(
            ticket_lifecycle_manifest_tpl,
            _claude_tickets_dir / "ticket_lifecycle.json",
            ticket_lifecycle_manifest_tpl.read_text(encoding="utf-8"),
        )
        # 99_rejected/.gitkeep and 00_inbox/epics/.gitkeep have no template
        # FILE of their own — build_ticket_lifecycle() derives them from this
        # manifest's "folders" array (a per-folder .gitkeep, plus a nested
        # epics/.gitkeep when has_epics_subfolder is true) rather than
        # copying a file out of templates/ticket-lifecycle/. The manifest is
        # the real source of truth for both, so it is named as the
        # "template" key — the same import-the-real-source-not-a-second-copy
        # precedent as changelog_categories.md above.
        _register_scaffold_if_unmodified(
            ticket_lifecycle_manifest_tpl,
            _claude_tickets_dir / "99_rejected" / ".gitkeep",
            "",
        )
        _register_scaffold_if_unmodified(
            ticket_lifecycle_manifest_tpl,
            _claude_tickets_dir / "00_inbox" / "epics" / ".gitkeep",
            "",
        )

    ticket_lifecycle_tpl_dir = templates_dir / "ticket-lifecycle"
    if ticket_lifecycle_tpl_dir.is_dir():
        for _tl_tpl in sorted(f for f in ticket_lifecycle_tpl_dir.rglob("*") if f.is_file()):
            _tl_rel = _tl_tpl.relative_to(ticket_lifecycle_tpl_dir)
            _tl_content = inject_config(_tl_tpl.read_text(encoding="utf-8"), config)
            _register_scaffold_if_unmodified(_tl_tpl, _claude_tickets_dir / _tl_rel, _tl_content)

    # changelogs/.gitkeep and unit_tests/README.md: build_config_scaffolds()
    # is their real source (a changelog_folder-derived empty .gitkeep, and
    # the _TESTS_README_SCAFFOLD constant — imported, never duplicated,
    # mirroring the changelog_categories.md import above).
    if build_config_scaffolds_src.is_file():
        _register_scaffold_if_unmodified(
            build_config_scaffolds_src,
            target_root / ".claude" / "changelogs" / ".gitkeep",
            "",
        )
        try:
            from build_config_scaffolds import (  # type: ignore[import]
                _TESTS_README_SCAFFOLD,
            )
        except ImportError as exc:
            _warn(f"could not import tests README scaffold content: {exc}")
        else:
            _register_scaffold_if_unmodified(
                build_config_scaffolds_src,
                target_root / ".claude" / "unit_tests" / "README.md",
                _TESTS_README_SCAFFOLD,
            )

    # --- rules ---
    # build_rules() is registered in build.py's ``internal_phases`` list, and
    # that loop invokes every phase with ``output_root`` — NOT ``target_root``,
    # despite the phase function's parameter being named ``target_root``. Rules
    # therefore land at ``<output_root>/.agents/rules/``, and there is no
    # ``.agents`` entry in ``shim_map`` to bridge them back up to
    # ``target_root`` (deliberately: build.py documents internal_phases as
    # "internal-only outputs into .leafcutter/ (no shim needed)").
    #
    # Recording ``target_root / ".agents" / "rules"`` here made the manifest
    # name 16 paths the build never produces while the 16 it does produce went
    # unrecorded — and because _collect_output_files() skips directories that
    # do not exist, neither a GAP nor an EXEMPT line was ever emitted for them.
    # 16 real deployed files sat outside the gate entirely and the run reported
    # clean: the exact phantom-done shape BP-100k-2 forbids (BP-100k-2).
    rules_tpl_dir = templates_dir / "rules"
    if rules_tpl_dir.is_dir():
        for tpl in sorted(rules_tpl_dir.glob("*.md")):
            output = output_root / ".agents" / "rules" / tpl.name
            # Gated on existence (BP-100k-6 interaction fix, same reasoning
            # as the sections above) — this path has no shim involved (no
            # timing concern), so the check purely protects a fixture that
            # never calls build_rules() from getting a phantom MISSING
            # verdict for a family it never asked to deploy.
            if not output.exists():
                if unwritten is not None:
                    unwritten.append(
                        f"rules: {tpl.name} not found (expected if this "
                        "build/fixture did not run build_rules())"
                    )
                continue
            text = inject_config(tpl.read_text(encoding="utf-8"), config)
            _add(tpl, output, text)

    # --- workflow scripts (JS) ---
    # Applies the exact two-step render build_workflow_scripts() (the real
    # deploy phase) applies before writing — _emit_workflow_variant() (engine
    # transform) THEN inject_config() (config-placeholder resolution), via
    # the shared build_phases_mod reference — rather than a raw byte-for-byte
    # copy of the unrendered template. Before this fix the manifest recorded
    # the hash of the TEMPLATE's own bytes, which can never match what
    # build_workflow_scripts() actually writes once either step changes
    # anything, permanently reporting drift on a correctly-built tree
    # (BP-100k-3 finding: 4 workflow scripts were consistently reported as
    # drifted because the manifest never ran either transform).
    # Also respects the same enabled gate build_workflow_scripts() itself
    # checks first: when workflows are not enabled, that phase writes
    # nothing, so the manifest must not predict output for files that will
    # never exist — the same "recorded set != real copy set" defect,
    # in the opposite direction. The Claude Code version-floor gate is NOT
    # replicated here: it is a runtime CLI probe with a subprocess timeout,
    # not a structural property of what SHOULD be deployed, and duplicating
    # it would make manifest computation racy against the same probe the
    # real phase already ran moments earlier in the same build.
    # Best-effort: falls back to the pre-fix raw-copy rendering (rather than
    # omitting the family) if build_phases_mod could not be loaded.
    workflows_js_dir = templates_dir / "workflows-js"
    workflows_config = config.get("workflows", {})
    workflows_enabled = (
        workflows_config.get("enabled", False) if isinstance(workflows_config, dict) else False
    )
    engine = workflows_config.get("engine", "auto") if isinstance(workflows_config, dict) else "auto"
    if workflows_js_dir.is_dir() and workflows_enabled:
        for tpl in sorted(workflows_js_dir.glob("*.js")):
            # Gated on the PRE-shim ``output_root/workflows/`` path existing
            # (BP-100k-6 interaction fix, same shim-timing reasoning as the
            # phase_mappings and skills sections above) — the canonical
            # ``.claude/workflows`` symlink this family also relies on is not
            # created until install_shims() runs, after the manifest is
            # written, even on a real, fully-deployed build.
            if not (output_root / "workflows" / tpl.name).exists():
                if unwritten is not None:
                    unwritten.append(
                        f"workflows-js: {tpl.name} not found (pre-shim; "
                        "expected if this build/fixture did not run "
                        "build_workflow_scripts())"
                    )
                continue
            output = target_root / ".claude" / "workflows" / tpl.name
            if build_phases_mod is None:
                _add(tpl, output, tpl.read_text(encoding="utf-8"))
                continue
            emitted = build_phases_mod._emit_workflow_variant(tpl.read_bytes(), engine)
            try:
                emitted = inject_config(emitted.decode("utf-8"), config).encode("utf-8")
            except UnicodeDecodeError:
                pass  # Non-UTF-8 content: injection skipped, matching the real phase's fallback.
            _add(tpl, output, emitted)

    return mappings


def write_build_manifest(
    package_root: Path,
    dry_run: bool = False,
    target_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    """Write .build_manifest.json with template hashes and expected output hashes.

    The ``templates`` section records the SHA-256 content hash of every .md file
    under ``package_root/templates/agents/`` AND every .py file under
    ``package_root/templates/scripts/commit_guardian/`` (backward-compatible
    with, and mirroring the exact scope of, check_build_drift.py's own two
    scanned template trees — Direction A detection). Without the second tree,
    every commit-guardian hook template is permanently "not in manifest" and
    can never be drift-checked (BP-100k-1).

    The ``output_mappings`` section records, for each template to output pair managed
    by build.py, the expected SHA-256 of what build.py would write to the output
    path given the current template and config. check_output_drift.py reads this
    section to detect Direction B drift (direct edits to built outputs).

    When ``target_root`` and ``config`` are both provided, output_mappings are
    computed and written. When either is absent, the section is omitted (the
    manifest degrades gracefully to the ticket-37 format).

    Also always writes ``output_mappings_error`` (whole-computation failure)
    and ``output_mappings_skipped_sections`` (partial, per-section failure —
    e.g. the agents/commands/workflows/hooks family could not be enumerated
    because ``package_root`` lacks a full ``scripts/`` tree). Both drift gates
    (check_output_drift.py, check_build_drift.py) read BOTH fields and refuse
    to report a clean run while either is non-empty — a manifest that cannot
    fully describe the tree must say so, not degrade silently to "nothing to
    report" (adversarial review round 2, H-5: check_build_drift.py previously
    read only ``output_mappings_skipped_sections``, contradicting this exact
    claim; the code has been fixed to match it).

    Also always writes ``output_mappings_unwritten`` — a per-file, human-
    readable diagnostic list recording every family whose PRE-shim output did
    not exist at manifest-write time (adversarial review round 2, B-1(b)).
    Unlike the two fields above, this one is VISIBILITY DATA ONLY: NEITHER
    drift gate reads it or blocks on it, because a per-file existence gate
    firing is, by design, expected on a narrow test fixture or a
    config-disabled family, and this module cannot tell those apart from "a
    real build silently wrote nothing for a family it should have deployed"
    at this call site — see ``_compute_output_mappings()``'s ``unwritten``
    parameter docstring for the full reasoning. The ``verified == 0`` floor
    in both gates (B-1(a)) is what actually closes the exploitable case (a
    build whose Direction B computation produced nothing comparable at all).

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``templates/`` and ``scripts/``).
        dry_run: When True, prints what would be written but writes nothing.
        target_root: Root of the target project. Required for output_mappings.
        config: Merged config dict used for placeholder injection. Required
            for output_mappings.
    """
    templates_dir = package_root / "templates" / "agents"
    # The manifest lives in target_root (the actual project/deploy root — the
    # SAME base every key below is computed relative to), falling back to
    # package_root only when target_root is not supplied (e.g. the ticket-37
    # backward-compat call shape with no output_mappings). This is what lets
    # check_build_drift.py / check_output_drift.py use manifest_path.parent
    # directly as their base with zero layout detection — see DECISION
    # HISTORY below.
    repo_root = target_root if target_root is not None else package_root
    manifest_path = repo_root / ".build_manifest.json"

    if not templates_dir.is_dir():
        _warn(f"templates/agents/ not found at {templates_dir}; skipping.")
        return

    # --- Direction A: template hashes (flat dict, backward-compatible) ---
    # relative_to(repo_root) is wrapped per-file: repo_root is target_root,
    # which is correct for both real supported layouts (self-host:
    # package_root == target_root; consumer-install: package_root nested one
    # level under target_root as "leafcutter-ai/") but has no guaranteed
    # relationship to package_root for an arbitrary caller-supplied
    # target_root (e.g. a build-into-a-scratch-dir smoke test) — skip such a
    # template with a warning rather than let one bad key crash the entire
    # manifest write (matches Direction B's existing warn-and-degrade
    # pattern below).
    template_hashes: dict[str, str] = {}
    for tpl_path in sorted(templates_dir.rglob("*.md")):
        try:
            key = tpl_path.relative_to(repo_root).as_posix()
        except ValueError:
            _warn(f"{tpl_path} is not under {repo_root}; omitting from manifest.")
            continue
        template_hashes[key] = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

    # Commit-guardian hook templates: check_build_drift.py scans this second
    # template tree independently (its own _collect_py_template_files()), so
    # its fingerprints must live in the same manifest or every hook script
    # edit is permanently reported "not in manifest" (BP-100k-1). Mirrors
    # that collector exactly: all .py files, __pycache__ excluded.
    cg_templates_dir = package_root / "templates" / "scripts" / "commit_guardian"
    if cg_templates_dir.is_dir():
        for tpl_path in sorted(cg_templates_dir.rglob("*.py")):
            if "__pycache__" in tpl_path.parts:
                continue
            try:
                key = tpl_path.relative_to(repo_root).as_posix()
            except ValueError:
                _warn(f"{tpl_path} is not under {repo_root}; omitting from manifest.")
                continue
            template_hashes[key] = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

    # --- Direction B: expected output hashes (new output_mappings section) ---
    output_mappings: dict[str, dict[str, str]] = {}
    output_mappings_error: str = ""
    output_mappings_skipped_sections: list[str] = []
    output_mappings_unwritten: list[str] = []
    if target_root is not None and config is not None:
        try:
            output_mappings = _compute_output_mappings(
                package_root,
                target_root,
                config,
                skipped_sections=output_mappings_skipped_sections,
                unwritten=output_mappings_unwritten,
            )
        except Exception as exc:  # noqa: BLE001
            output_mappings_error = f"{type(exc).__name__}: {exc}"
            import warnings
            warnings.warn(
                f"could not compute output_mappings: {exc}. "
                "Direction B detection will be unavailable until next build.",
                stacklevel=2,
            )
            _warn(
                f"could not compute output_mappings: {exc}. "
                "Direction B detection will be unavailable until next build."
            )

    # Merge into final manifest structure
    manifest: dict[str, Any] = dict(template_hashes)
    manifest["output_mappings"] = output_mappings

    # Record the failure as DATA rather than leaving the gates to infer it from
    # an empty mapping set. An empty output_mappings is ambiguous — it can mean
    # "this build genuinely produced no outputs" or "the computation raised and
    # every mapping was discarded" — and the two demand opposite verdicts. The
    # warning above is emitted at BUILD time and is long gone by the time a
    # pre-commit hook runs on a consumer machine, so without this key the gate
    # sees a well-formed manifest claiming zero managed outputs and reports a
    # clean run. That is the phantom-pass shape BP-100k-3 forbids: a gate that
    # could not check anything must not exit as though it checked everything.
    manifest["output_mappings_error"] = output_mappings_error

    # Record a PARTIAL enumeration failure as manifest DATA too — the
    # per-section analogue of ``output_mappings_error`` above. A whole-
    # computation exception (caught above) discards every mapping and is
    # unambiguous; but ``_compute_output_mappings`` can also catch an
    # exception INTERNALLY (e.g. ``build_phases.py`` missing from a
    # ``package_root`` without a full ``scripts/`` tree) for just one section
    # — such as the agents/commands/workflows/hooks family — while every
    # other section still runs and returns a normal-looking, non-empty dict.
    # Without recording which section was skipped, a reader has no way to
    # distinguish "this build genuinely has no workflow-JS/agents/commands/
    # hooks outputs" from "that whole family silently failed to enumerate" —
    # exactly the ambiguity ``output_mappings_error`` exists to remove for
    # the whole-manifest case, one level down. Empty list means every section
    # of ``_compute_output_mappings`` completed without incident.
    manifest["output_mappings_skipped_sections"] = output_mappings_skipped_sections

    # Record every per-file existence-gate skip as DATA too (adversarial
    # review round 2, B-1(b)): "the phase did not write it" must reach the
    # manifest, not vanish as a silent ``continue``. VISIBILITY ONLY —
    # deliberately NOT read by either drift gate. Every one of these
    # existence gates is, by design, expected to fire legitimately for a
    # narrow test fixture or a config-disabled family, and this function has
    # no way to distinguish those from "a real build silently wrote nothing
    # for a family it should have deployed" — see _compute_output_mappings()'s
    # own ``unwritten`` parameter docstring for the full reasoning. The
    # ``verified == 0`` floor added to both gates (B-1(a)) is what actually
    # closes the exploitable case (a build whose Direction B computation
    # produced nothing at all); this field is raw material for a future,
    # more precise gate, not itself gate-blocking.
    manifest["output_mappings_unwritten"] = output_mappings_unwritten

    # Record where the package sits relative to the manifest's own directory, as
    # DATA rather than something a reader has to infer (BP-100k-3).
    #
    # The gates resolve their comparison base as manifest_path.parent. That is
    # correct for deployed OUTPUTS, which the build writes under target_root. It
    # is NOT where TEMPLATES live: on a consumer install the package is a
    # subdirectory (leafcutter-ai/) of the deploy root, so a gate that assumed
    # "<manifest dir>/templates" scanned a path that does not exist and reported
    # zero templates — an empty comparison set, indistinguishable from a clean
    # run. Self-host hid this because package_root and target_root coincide.
    #
    # Recording the offset avoids re-deriving it from a directory name or a git
    # probe, either of which fails open when the guess is wrong. Empty string
    # means the package root and the manifest directory are the same directory.
    try:
        package_offset = package_root.relative_to(manifest_path.parent).as_posix()
    except ValueError:
        package_offset = ""
    manifest["package_root"] = "" if package_offset == "." else package_offset

    if dry_run:
        _dry_run(
            f"would write build manifest ({len(template_hashes)} template "
            f"+ {len(output_mappings)} output_mappings entries) -> {manifest_path}"
        )
        return

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _success(
        f"build manifest ({len(template_hashes)} template "
        f"+ {len(output_mappings)} output_mappings entries) -> {manifest_path}"
    )


def seed_docs(target_root: Path, dry_run: bool) -> None:
    """Seed missing architecture-doc scaffolds into the project's docs/architecture/.

    Delegates to ``seed_project_docs.seed_architecture_scaffolds``.  Only missing
    files are copied — existing project content is never overwritten.

    Args:
        target_root: Absolute path to the target project root.
        dry_run: When True, prints intent but writes nothing.
    """
    try:
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from seed_project_docs import seed_architecture_scaffolds  # type: ignore[import]
        dry_label = " (dry-run)" if dry_run else ""
        print(f"\nSeeding architecture scaffolds{dry_label}:")
        result = seed_architecture_scaffolds(target_root, dry_run=dry_run)
        print(
            f"  Done: {len(result['copied'])} copied, {len(result['skipped'])} skipped."
        )
    except Exception as exc:  # noqa: BLE001
        print()
        _warn(
            f"Scaffold seeding failed: {exc}. "
            "Run manually: python leafcutter/scripts/seed_project_docs.py"
        )


def update_diagrams(package_root: Path) -> None:
    """Regenerate Mermaid diagrams from registry and embed into target docs.

    Args:
        package_root: Root of the leafcutter package (contains
            config/ and docs/ subdirectories).
    """
    try:
        import importlib.util
        diagram_script = package_root / "scripts" / "generate_agent_diagram.py"
        spec = importlib.util.spec_from_file_location("generate_agent_diagram", diagram_script)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            agents = mod.load_registry()
            updated = mod.embed_diagrams(agents)
            print("\nDiagram update:")
            for path, was_updated in updated.items():
                status = "updated" if was_updated else "no change"
                print(f"  {path}: {status}")
    except Exception as exc:  # noqa: BLE001
        print()
        _warn(f"Diagram update failed: {exc}. "
              "Run manually: python leafcutter/scripts/generate_agent_diagram.py --output-format embed")


def install_shims(
    target_root: Path,
    output_root: Path | None = None,
    config: dict[str, Any] | None = None,
    dry_run: bool = False,
    force: bool = True,
) -> list[dict[str, str]]:
    """Create shims at canonical tool paths pointing into the consolidated output root.

    Tools like Claude Code expect files at `.claude/agents/`, pre-commit reads
    `.pre-commit-config.yaml` from the repo root, and Gemini reads `.gemini/`.
    After build phases write everything into `<output_root>/`, this function
    bridges those canonical paths via symlinks (preferred) or file copies
    (Windows fallback).

    The strategy is controlled by ``config["shim_strategy"]``:
    - ``"symlink"``: always use symlinks; fail loudly on PermissionError.
    - ``"copy"``: always use file copies (safe on all platforms).
    - ``"auto"`` (default): try symlinks first, fall back to copies on error.

    Args:
        target_root: Absolute path to the target project root.
        output_root: Absolute path to the consolidated output directory
            (e.g. ``target_root / ".leafcutter"``). When None, reads from
            ``config["output_root"]`` or defaults to ``target_root / ".leafcutter"``.
        config: Build config dict. Used to read ``shim_strategy``.
        dry_run: When True, prints the shim plan but writes nothing.
        force: When True, overwrites existing shims.

    Returns:
        List of dicts describing each shim: {canonical, target, method}.
    """
    if config is None:
        config = {}

    strategy = config.get("shim_strategy", "auto")
    if output_root is None:
        output_root = target_root / config.get("output_root", ".leafcutter")

    # Uses the module-level shim_map directly (single source of truth,
    # shared with _compute_output_mappings' canonical-path translation) —
    # never a second, independently-maintained copy of this table.
    results: list[dict[str, str]] = []

    for canonical_rel, output_rel in shim_map:
        canonical_path = target_root / canonical_rel
        source_path = output_root / output_rel

        if not source_path.exists():
            _warn(f"shim source missing: {output_rel}/ — "
                  f"no build phase populated it. Skipping {canonical_rel} shim.")
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            if not force:
                results.append({
                    "canonical": canonical_rel,
                    "target": output_rel,
                    "method": "skipped (exists)",
                })
                continue
            if not dry_run:
                if canonical_path.is_symlink() or canonical_path.is_file():
                    canonical_path.unlink()
                elif canonical_path.is_dir():
                    import shutil
                    shutil.rmtree(canonical_path)

        if dry_run:
            method = "symlink" if strategy != "copy" else "copy"
            _dry_run(f"would shim {canonical_rel} -> {output_rel} ({method})")
            results.append({
                "canonical": canonical_rel,
                "target": output_rel,
                "method": f"dry-run ({method})",
            })
            continue

        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        method = _create_shim(canonical_path, source_path, strategy)
        results.append({
            "canonical": canonical_rel,
            "target": output_rel,
            "method": method,
        })
        _info(f"shim: {canonical_rel} -> {output_rel} ({method})")

    # Single-file shims (these are files, not directories)
    file_shims: list[tuple[str, str]] = [
        (".pre-commit-config.yaml", "pre-commit-config.yaml"),
        (".claude/settings.json", "settings.json"),
    ]

    for canonical_rel, output_rel in file_shims:
        canonical_path = target_root / canonical_rel
        source_path = output_root / output_rel

        if not source_path.exists():
            continue

        if canonical_path.exists() or canonical_path.is_symlink():
            if not force:
                results.append({
                    "canonical": canonical_rel,
                    "target": output_rel,
                    "method": "skipped (exists)",
                })
                continue
            if not dry_run:
                canonical_path.unlink()

        if dry_run:
            method = "symlink" if strategy != "copy" else "copy"
            _dry_run(f"would shim {canonical_rel} -> {output_rel} ({method})")
            results.append({
                "canonical": canonical_rel,
                "target": output_rel,
                "method": f"dry-run ({method})",
            })
            continue

        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        method = _create_file_shim(canonical_path, source_path, strategy)
        results.append({
            "canonical": canonical_rel,
            "target": output_rel,
            "method": method,
        })
        _info(f"shim: {canonical_rel} -> {output_rel} ({method})")

    return results


def _relative_symlink_target(canonical: Path, source: Path) -> str:
    """Return the symlink target to record for ``canonical`` -> ``source``.

    Computed relative to ``canonical``'s own parent directory (ADR-004 /
    ADR-016) — not the process's working directory — so a rebuild from any
    cwd, and a relocation/copy of the whole tree, still resolves. Falls back
    to an absolute target when no relative path can be expressed (e.g. the
    canonical location and the output root sit on different drives/mounts
    with no common ancestor); the caller still completes in that case.

    Args:
        canonical: Absolute path where the shim link will be created.
        source: Absolute path inside the output root the link must resolve to.

    Returns:
        The string to pass to ``Path.symlink_to()`` — a relative path when
        one can be expressed, otherwise the absolute ``source`` path.
    """
    try:
        return os.path.relpath(str(source), str(canonical.parent))
    except ValueError:
        return str(source)


def _create_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a directory shim (symlink or copy) at canonical pointing to source.

    Args:
        canonical: Absolute path where the shim is created (e.g. `.claude/agents`).
        source: Absolute path inside the output root the shim must resolve to.
        strategy: ``"symlink"``, ``"copy"``, or ``"auto"`` (see ``install_shims``).

    Returns:
        The method used: ``"symlink"``, ``"copy"``, or ``"copy (symlink failed)"``.
    """
    import shutil

    if strategy == "copy":
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy"

    target = _relative_symlink_target(canonical, source)
    try:
        canonical.symlink_to(target, target_is_directory=True)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy (symlink failed)"
    else:
        return "symlink"


def _create_file_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a file shim (symlink or copy) at canonical pointing to source.

    Args:
        canonical: Absolute path where the shim is created (e.g. `.gemini`).
        source: Absolute path inside the output root the shim must resolve to.
        strategy: ``"symlink"``, ``"copy"``, or ``"auto"`` (see ``install_shims``).

    Returns:
        The method used: ``"symlink"``, ``"copy"``, or ``"copy (symlink failed)"``.
    """
    import shutil

    if strategy == "copy":
        shutil.copy2(source, canonical)
        return "copy"

    target = _relative_symlink_target(canonical, source)
    try:
        canonical.symlink_to(target)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copy2(source, canonical)
        return "copy (symlink failed)"
    else:
        return "symlink"


def _resolve_precommit_cmd():
    """Return the command list to invoke pre-commit, or None if unavailable.

    Three-tier detection:
    1. ``shutil.which("pre-commit")`` — binary on PATH.
    2. ``importlib.util.find_spec("pre_commit")`` — installed as a Python
       package in the same environment running build.py (handles the common
       case where pip installed it but the Scripts/ dir isn't on PATH).
    3. Probe known pip/pipx install locations — handles non-interactive shells
       where ~/.local/bin or Scripts/ aren't in PATH.
    """
    if shutil.which("pre-commit"):
        return ["pre-commit"]
    if importlib.util.find_spec("pre_commit"):
        return [sys.executable, "-m", "pre_commit"]
    for candidate in _precommit_known_paths():
        if not candidate.is_file():
            continue
        try:
            probe = subprocess.run(
                [str(candidate), "--version"],
                capture_output=True,
                timeout=5,
            )
            if probe.returncode == 0:
                return [str(candidate)]
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def _precommit_known_paths():
    """Yield common install locations for the pre-commit binary."""
    home = Path.home()
    yield home / ".local" / "bin" / "pre-commit"
    exe_dir = Path(sys.executable).parent
    yield exe_dir / "pre-commit"
    if sys.platform == "win32":
        yield exe_dir / "Scripts" / "pre-commit.exe"
    else:
        yield exe_dir / "Scripts" / "pre-commit"


def install_hooks(target_root, dry_run=False):
    """Run ``pre-commit install`` after build.py writes .pre-commit-config.yaml.

    Closes the "last mile" gap: the generated config exists on disk but
    ``pre-commit install`` must be run to wire ``.git/hooks/pre-commit`` to it.
    This function is idempotent — calling it multiple times on the same project
    is safe.

    Args:
        target_root: Absolute path to the target project root.
        dry_run: When True, prints the action but does not run any subprocess.

    Returns:
        One of "installed", "dry-run", "failed",
        "skipped (pre-commit not found)", "skipped (custom hooksPath)",
        or "skipped (not a git repo)".
    """
    # 1. Resolve pre-commit binary (PATH lookup, then Python module fallback).
    precommit_cmd = _resolve_precommit_cmd()
    if precommit_cmd is None:
        _warn("pre-commit not found; skipping hook install")
        _info("         Pre-commit runs code-quality checks automatically before")
        _info("         each commit. Install it with:")
        _info("")
        _info("           pip install pre-commit")
        _info("")
        _info("         Then re-run this build to complete hook setup.")
        return "skipped (pre-commit not found)"

    # 2. Dry-run guard (before any subprocess calls that mutate state).
    if dry_run:
        _dry_run("would run pre-commit install")
        return "dry-run"

    # 3. Check core.hooksPath git config.
    try:
        hooks_path_result = subprocess.run(
            ["git", "-C", str(target_root), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not read core.hooksPath (git not found): {exc}")
        hooks_path_result = None
    if hooks_path_result is not None and hooks_path_result.returncode == 0:
        hooks_path_value = hooks_path_result.stdout.strip()
        default_hooks = Path(target_root) / ".git" / "hooks"
        is_default = (
            hooks_path_value.lower() in (".git/hooks", ".git\\hooks")
            or Path(hooks_path_value).resolve() == default_hooks.resolve()
        )
        if is_default:
            try:
                subprocess.run(
                    ["git", "-C", str(target_root), "config", "--unset", "core.hooksPath"],
                    capture_output=True,
                )
            except OSError as exc:
                _warn(f"hooks: could not unset core.hooksPath (git not found): {exc}")
            else:
                _info("hooks: cleared redundant core.hooksPath (.git/hooks)")
        elif hooks_path_value:
            _warn(
                f"core.hooksPath is set to '{hooks_path_value}' "
                "(non-default); skipping pre-commit install"
            )
            return "skipped (custom hooksPath)"

    # 3.5. Guard: verify target_root is inside a git working tree.
    # Using `git rev-parse --git-dir` is more robust than checking for a .git
    # directory directly: it also handles worktrees and nested repos correctly.
    try:
        git_check = subprocess.run(
            ["git", "-C", str(target_root), "rev-parse", "--git-dir"],
            capture_output=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not verify git repo (git not found): {exc}")
        git_check = None

    if git_check is not None and git_check.returncode != 0:
        _info("hooks: skipping pre-commit install (target is not a git repo)")
        return "skipped (not a git repo)"

    # 4. Run pre-commit install.
    try:
        subprocess.run(
            [*precommit_cmd, "install"],
            cwd=str(target_root),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        _error(f"pre-commit install failed: {stderr.strip()}")
        return "failed"

    _success("hooks: pre-commit install OK")
    return "installed"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [python-coder/EPIC-BuildPipelinePhantomRemediation, adversarial
#   review round 2, B-1(b)]: Every per-file existence gate this round added to
#   _compute_output_mappings() (phase_mappings, skills, direct-output
#   families, the scaffold registrar, rules, workflows-js) recorded NOTHING
#   when it fired — not a mapping, not an error, not a skipped-section entry,
#   just a bare `continue`. Combined with B-1(a)'s finding that an empty
#   output_mappings used to skip the `verified == 0` floor entirely, this made
#   "the build silently produced nothing to compare" structurally invisible.
#   Fix: each existence gate now appends a short description to an optional
#   `unwritten` list threaded through to `write_build_manifest()`, which
#   records it as `output_mappings_unwritten` manifest DATA. Deliberately NOT
#   wired into either gate's verdict — every one of these existence checks is
#   ALSO the expected, legitimate path for a narrow test fixture or a
#   config-disabled platform/family, and this function has no way to
#   distinguish that from a genuine build failure at this call site (see the
#   `unwritten` parameter's own docstring). B-1(a)'s tightened `verified == 0`
#   floor is what actually closes the exploitable case; this field is
#   diagnostic material for a future, more precise gate.
# - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation, post-merge
#   defect fix]: _compute_output_mappings()'s try/except around
#   _load_build_phases_module()/_compute_phase_mappings() warned and
#   continued on failure, but the enumeration failure itself was never
#   recorded anywhere the drift gates could read — a partial manifest looked
#   identical to a genuinely-complete one, so both gates reported a clean run
#   against a manifest that never described the agents/commands/workflows/
#   hooks section at all. This is the per-SECTION analogue of the
#   whole-computation `output_mappings_error` field BP-100k-5 already added.
#   Fix: `_compute_output_mappings()` takes an optional `skipped_sections`
#   out-param it appends a reason string to on this exception;
#   `write_build_manifest()` passes a list and writes it into the manifest as
#   `output_mappings_skipped_sections` (empty list when nothing was skipped).
#   `check_output_drift.py` and `check_build_drift.py` both read the new
#   field in `main()` and return 2 (BLOCKED, not clean) when it is non-empty,
#   mirroring exactly how they already honour `output_mappings_error`. The
#   warning at build time is retained unchanged — this only adds the
#   persistent, gate-readable record.
# - 2026-08-19 [python-coder/EPIC-BuildPipelinePhantomRemediation/08, round 2]:
#   BP-100k-3-i caught a second manifest-keying defect after the round-1 fix:
#   both _compute_output_mappings() and write_build_manifest()'s Direction A
#   section used `repo_root = package_root.parent` unconditionally — correct
#   only for consumer-install (package_root nested one level below the real
#   project root); wrong for self-host, where package_root already IS the
#   project root, giving every key a spurious leading path component (a
#   worktree's own build.py --target-dir <worktree> run produced keys like
#   "EPIC-Name/.claude/workflows/x.js" — 0 verified / 170 uncomparable on a
#   tree that had just been built). A git-based layout-detection heuristic
#   (mirroring setup_ticket_worktree.py's _resolve_installed_layout()) was
#   tried first and reverted: it failed open for any layout where git errors
#   (tarball install, CI checkout without git, vendored copy), silently
#   taking the wrong branch — exactly the "gate that cannot compare" defect
#   this epic exists to remove — and it broke 4 pre-existing test fixtures
#   that fake a consumer layout inside a bare non-git tmp dir, which have
#   nothing to do with git at all.
#   Fixed instead with the actual invariant, no detection required:
#   target_root — already an explicit parameter to both functions, supplied
#   by build.py's own --target-dir — is BY CONSTRUCTION the root outputs are
#   deployed into and the root templates sit relative to (self-host:
#   target_root == package_root; consumer-install: package_root is nested
#   one level below target_root). _compute_output_mappings() now uses
#   target_root directly as repo_root. write_build_manifest() now writes
#   .build_manifest.json INTO target_root (falling back to package_root only
#   when target_root is absent — the ticket-37 backward-compat call shape)
#   and uses that same repo_root for Direction A keys, so
#   check_build_drift.py / check_output_drift.py can use manifest_path.parent
#   directly as their base with zero layout detection on the read side too.
# - 2026-08-18 [python-coder/EPIC-BuildPipelinePhantomRemediation/07]: (#BP-100k-1/-2)
#   Fixed two blind spots that made the drift gates report every non-agent
#   template and every real deployed output as absent/unregistered while
#   exiting clean. (1) Direction A (template_hashes) only hashed
#   templates/agents/*.md; check_build_drift.py separately scans
#   templates/scripts/commit_guardian/*.py and looked those keys up in the
#   same manifest, so every commit-guardian hook template was permanently
#   "not in manifest". write_build_manifest() now also hashes that tree,
#   mirroring check_build_drift.py's own two-directory scan exactly.
#   (2) Direction B (output_mappings) keyed entries by the pre-shim,
#   output_root-relative path (e.g. "agents/README.md"), but
#   check_output_drift.py looks up the CANONICAL, post-shim path (e.g.
#   ".claude/agents/README.md") — no real deployed file ever matched.
#   _compute_output_mappings() now derives the agents/commands/workflows/
#   hooks families from build_phases._compute_phase_mappings() (the same
#   enumeration build.py's own collision guard uses) and translates each
#   target through the module-level shim_map — the exact table
#   install_shims() uses to create the shims (both now read the SAME
#   module-level list; install_shims() previously defined its own local
#   copy) — rather than a second hardcoded inventory. skills/rules/
#   workflow-js entries were also re-keyed onto their
#   canonical path (.claude/skills, .agents/rules, .claude/workflows).
#   Added _load_build_phases_module() to load build_phases.py by file path
#   under a name derived from package_root: build_phases.py resolves
#   TEMPLATES_DIR/PACKAGE_ROOT from its own __file__ at import time, so a
#   bare `import build_phases` would silently reuse a stale module cached
#   under a different package_root within the same process.
# - 2026-05-15 10:15 [python-coder/EPIC-PortableSQLAgents/ticket-01]: (#EPIC-LeafcutterMVP/01)
#   Created this module by extracting write_build_manifest, _seed_docs,
#   _update_diagrams, and _install_shims from build.py. The extraction
#   was required to keep build.py under the 400-line limit enforced by
#   the check-file-size pre-commit hook. All functions are self-contained
#   utility helpers with no shared state; the move requires only an import
#   change in build.py (from build_helpers import ...). All callers
#   continue to access these functions via build.py's re-exports for
#   backward compatibility.
# - 2026-05-15 10:30 [python-coder/TICKET-20260515]: Merged Direction B (#EPIC-LeafcutterMVP/01)
#   manifest support into write_build_manifest() here (conflict resolution:
#   adopted build_helpers.py as canonical module; ported _compute_output_mappings
#   and the output_mappings manifest section from build_manifest.py). Signature
#   extended with optional target_root and config parameters. When provided,
#   the manifest's output_mappings section records expected SHA-256 of each
#   rendered output so check_output_drift.py can detect Direction B drift.
#   build_manifest.py and build_extras.py (my branch's separate modules) are
#   superseded by this consolidated module.
# - 2026-05-30 10:15 [python-coder/TICKET-20260530-AutoInstallPrecommitHooks]: Added (#TICKET-20260530)
#   install_hooks(target_root, dry_run) to close the "last mile" gap between
#   generating .pre-commit-config.yaml and activating it. Handles: pre-commit
#   not on PATH (non-fatal warning), dry-run mode (returns early before any
#   subprocess), core.hooksPath redundant default (auto-unset), core.hooksPath
#   custom path (warn+skip), and CalledProcessError (non-fatal, returns "failed").
#   Called from build.py main() under the same --no-shims guard as install_shims().
#   Idempotent. Added shutil and subprocess to module-level imports.
# - 2026-06-04 00:00 [python-coder/TICKET-20260604-PrecommitBinaryResolution]: (#TICKET-20260604)
#   Added --version probe to _resolve_precommit_cmd() tier-3 (known-paths) loop.
#   Tier 3 previously accepted any .is_file() candidate, allowing stale or
#   non-executable binaries on WSL2 / broken pip installs to slip through and
#   cause [ERROR] pre-commit install failed: instead of the correct graceful
#   "skipped (pre-commit not found)" warning. Probe uses subprocess.run with
#   capture_output=True and timeout=5; OSError and TimeoutExpired both continue
#   to the next candidate. Zero performance cost on the common happy path (tier 1
#   succeeds before tier 3 runs). Added BLE001 noqa on unavoidable broad-except
#   blocks in seed_docs() and update_diagrams(). Refactored try/except in
#   _create_shim() and _create_file_shim() to use else clause (Ruff compliance).
# - 2026-06-17 [python-coder/quick-fix]: Added step 3.5 git-repo guard to (#BP-007)
#   install_hooks(). Before this change, calling install_hooks() against a
#   target_root that has no reachable .git caused `pre-commit install` to run
#   unconditionally, exit non-zero (no git repo), and surface a misleading
#   [ERROR] with empty stderr while returning "failed". The fix inserts a
#   `git -C <target_root> rev-parse --git-dir` probe between step 3 (custom
#   hooksPath guard) and step 4 (`pre-commit install`). Non-zero return code
#   triggers a graceful _info() message and returns "skipped (not a git repo)"
#   instead of reaching pre-commit. The subprocess call is wrapped in
#   try/except OSError so that a missing git binary degrades safely. When
#   target_root IS a real git repo the probe succeeds and execution falls
#   through to step 4 unchanged, preserving the loud-failure path for genuine
#   install errors. Docstring Returns: section updated to list the new status.
# ====================================================================
