"""
MODULE: test_bp_900g_6_paths
GOAL: Regression guard for the hardcoded-script-path defect in deployed
    workflow ``.js`` files — before this fix, ``build_workflow_scripts`` copied
    ``templates/workflows-js/*.js`` byte-verbatim (no ``inject_config`` call),
    so every ``{{config.output_root}}`` placeholder a workflow author wrote was
    shipped to consumers unresolved, and every OTHER workflow invocation was
    hardcoded to the literal ``scripts/...`` prefix — correct only when a
    consumer's configured ``output_root`` happens to be the default
    ``.leafcutter``.
BUSINESS CONTEXT: ``output_root`` is documented as "configurable per consumer
    project" in ``config/skills_config.schema.json``. ``.md`` templates already
    resolve ``{{config.output_root}}`` via ``inject_config`` (``build_workflows``,
    ``build_commands``, ``build_rules``); workflow ``.js`` scripts did not,
    because ``build_workflow_scripts`` was an identity byte-copy phase. AC
    BP-900g-6.
ARCHITECTURE: Behavioral tests only, following the style of
    ``test_bp_900g_4.py``: each test runs the REAL ``build.py --target-dir``
    into a fresh ``tmp_path``, then asserts against the DEPLOYED tree —
    resolving against the package source tree cannot detect a missing
    ``inject_config`` call, since the un-rendered ``{{config.output_root}}``
    token is present in the source either way. ``output_root`` is discovered
    dynamically (the directory under the target containing ``scripts/``) so
    the assertions hold regardless of the configured value, never hardcoding
    ``.leafcutter``.
"""
# @ac-tag: BP-900g-6

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup
import build_phases as _bp  # noqa: E402 — after sys.path setup


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the dir holding scripts/.

    Discovered dynamically rather than hardcoded to ``.leafcutter`` so the
    assertions in this file hold for any consumer-configured ``output_root``
    value (AC BP-900g-6 — output_root is documented as "configurable per
    consumer project").
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} (a directory "
        f"containing a 'scripts/' subdirectory); found {[p.name for p in candidates]}."
    )
    return candidates[0]


# ---------------------------------------------------------------------------
# Requirement 1 — every <output_root>/scripts/... path baked into a DEPLOYED
# .js workflow must resolve to a real file in that same deployed tree.
# ---------------------------------------------------------------------------


def test_deployed_workflow_js_script_paths_resolve(tmp_path: Path) -> None:
    """Every rendered ``<output_root>/scripts/...`` path in a deployed workflow
    ``.js`` file must exist in the DEPLOYED tree.

    Resolving against the package source tree cannot catch this class of
    defect: the source always contains the un-rendered
    ``{{config.output_root}}`` token, so a source-tree check would pass
    whether or not ``build_workflow_scripts`` ever called ``inject_config``.
    """
    # covers: BP-900g-6
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The deployed-tree "
        "assertions below cannot run against a failed build."
    )

    output_root = _find_output_root(target_dir)
    workflows_dir = output_root / "workflows"
    assert workflows_dir.is_dir(), (
        f"No workflows/ directory deployed under {output_root}. "
        "workflows.enabled defaults to true in skills_config.default.json, so a "
        "fresh build with no project config should always deploy .js workflows."
    )

    js_files = sorted(workflows_dir.glob("*.js"))
    assert js_files, (
        f"No .js files found under {workflows_dir}. Cannot test script-path "
        "resolution against an empty deployed workflow set."
    )

    # Matches "<output_root_name>/scripts/<...>.py" as a literal substring,
    # deliberately NOT anchored to a preceding "python3"/"python" keyword: the
    # source embeds many of these paths via a JS variable (e.g.
    # `const gateScript = "${worktreePath}/{{config.output_root}}/scripts/...py"`)
    # rather than as a direct command-line literal, and this test's job is to
    # verify the DEPLOYED, RENDERED path resolves — not to replicate the
    # narrower static-analysis reach of the pre-flight reference guard.
    invoke_re = re.compile(rf"{re.escape(output_root.name)}/scripts/[\w./\-]+\.py")

    seen: set[str] = set()
    unresolved: list[str] = []
    for js_file in js_files:
        text = js_file.read_text(encoding="utf-8")
        for rel_path in invoke_re.findall(text):
            seen.add(rel_path)
            if not (target_dir / rel_path).is_file():
                unresolved.append(f"{js_file.name} -> {rel_path}")

    # Non-vacuity guard: if the matcher silently stops matching (a template
    # rewrite, a changed output root, a regex regression) this test would pass
    # while checking nothing at all.
    expected = {
        f"{output_root.name}/scripts/pause_store.py",
        f"{output_root.name}/scripts/setup_ticket_worktree.py",
        f"{output_root.name}/scripts/build_orchestration/fast_lane.py",
    }
    missing_expected = expected - seen
    assert not missing_expected, (
        f"The deployed-tree scan found no reference to {sorted(missing_expected)!r}. "
        f"It found: {sorted(seen)!r}. plan-feature.js/finalize-feature.js invoke "
        "pause_store.py at every gate, setup_ticket_worktree.py bootstraps every "
        "AC-authoring and fast-lane worktree, and fast-lane-ship.js/fast-lane-build.js "
        "invoke fast_lane.py at every gate — their absence means this test is no "
        "longer checking anything (AC BP-900g-6)."
    )

    assert not unresolved, (
        f"{len(unresolved)} script reference(s) baked into the DEPLOYED .js "
        "workflows do not resolve to a file in that same deployed tree:\n  "
        + "\n  ".join(sorted(set(unresolved)))
        + "\nEach of these is a workflow that will die at that command in a "
        "consumer install, even though build.py exited 0 (AC BP-900g-6)."
    )


# ---------------------------------------------------------------------------
# Requirement 2 — no un-substituted {{config.*}} tokens survive into the
# deployed .js output (proves inject_config actually ran).
# ---------------------------------------------------------------------------


def test_deployed_workflow_js_has_no_leftover_config_placeholder(tmp_path: Path) -> None:
    """Deployed ``.js`` workflows must contain zero un-substituted ``{{config.``
    tokens.

    Before BP-900g-6, ``build_workflow_scripts`` never called ``inject_config``
    on ``.js`` content, so every ``{{config.output_root}}`` token a workflow
    author wrote would have shipped to the consumer verbatim, unresolved.
    """
    # covers: BP-900g-6
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_output_root(target_dir)
    workflows_dir = output_root / "workflows"

    leftovers: list[str] = []
    for js_file in sorted(workflows_dir.glob("*.js")):
        text = js_file.read_text(encoding="utf-8")
        if "{{config." in text:
            leftovers.append(js_file.name)

    assert not leftovers, (
        f"Deployed .js workflow(s) still contain an un-substituted '{{{{config.' "
        f"token: {leftovers}. inject_config() must run against workflow .js "
        "content BEFORE it is written, exactly as it already does for .md "
        "templates in build_workflows/build_commands/build_rules (AC BP-900g-6)."
    )


# ---------------------------------------------------------------------------
# Requirement 3 — the two newly-deployed agent-support scripts must IMPORT
# cleanly from the deployed tree (presence is not reachability).
# ---------------------------------------------------------------------------


def test_deployed_pause_store_and_injection_builders_import_cleanly(tmp_path: Path) -> None:
    """``pause_store.py`` and ``injection_builders.py`` must IMPORT from the
    deployed tree, not merely exist there.

    Both scripts became agent-support deploy targets under BP-900g-6 because
    ``plan-feature.js``/``finalize-feature.js`` invoke ``pause_store.py`` at
    every interactive gate and ``fast-lane-build.js`` invokes
    ``injection_builders.py`` to assemble the layered LLM context bundle, but
    no build phase shipped either script before this fix. Each is imported in
    a fresh subprocess (not merely stat'ed) with the deployed scripts
    directory as its own location, so a missing sibling-module dependency
    surfaces as the ImportError a consumer would actually hit — the lesson
    from ``ac_parent_id.py`` in BP-900g-4.
    """
    # covers: BP-900g-6
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_output_root(target_dir)
    scripts_dir = output_root / "scripts"

    targets = [
        ("pause_store.py", "pause_store"),
        ("injection_builders.py", "injection_builders"),
    ]

    failures: list[str] = []
    for rel, mod_name in targets:
        script_path = scripts_dir / rel
        if not script_path.is_file():
            failures.append(f"{rel}: not deployed")
            continue
        code = (
            "import importlib.util,sys;"
            f"s=importlib.util.spec_from_file_location({mod_name!r}, {str(script_path)!r});"
            "m=importlib.util.module_from_spec(s);"
            "sys.modules[s.name]=m;"
            "s.loader.exec_module(m)"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            failures.append(f"{rel}: {proc.stderr.strip().splitlines()[-1:]}")

    assert not failures, (
        "Deployed agent-support scripts that do not import cleanly:\n  "
        + "\n  ".join(failures)
        + "\nThe file being present is not enough — a module it imports at import "
        "time may be missing from the deployed tree. Add that module to "
        "AGENT_SUPPORT_SCRIPT_DIRS/FILES in build_phases.py (AC BP-900g-6)."
    )


# ---------------------------------------------------------------------------
# Requirement 4 (unit-level, not full-build) — the compare-before-write guard
# must survive the addition of inject_config() to build_workflow_scripts.
# ---------------------------------------------------------------------------


def test_build_workflow_scripts_injects_and_stays_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    """``build_workflow_scripts`` must render ``{{config.*}}`` placeholders and
    skip an unchanged second run (idempotency guard runs on the RENDERED
    content, not the raw template bytes).

    A synthetic single-file template tree keeps this test unit-scoped (no full
    package build), directly pinning the ordering requirement from the ticket:
    injection must happen BEFORE the compare-before-write guard so a
    rendered-but-unchanged file still counts as up-to-date.
    """
    # covers: BP-900g-6
    templates_dir = tmp_path / "templates"
    workflows_js_dir = templates_dir / "workflows-js"
    workflows_js_dir.mkdir(parents=True)
    (workflows_js_dir / "sample.js").write_text(
        'const gateScript = "{{config.output_root}}/scripts/foo.py";\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_bp, "TEMPLATES_DIR", templates_dir)
    # Deterministic version gate: bypass the `claude --version` subprocess probe.
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "9.9.9")

    target_root = tmp_path / "target"
    config = {"workflows": {"enabled": True, "engine": "e2"}, "output_root": ".leafcutter"}

    written_first = _bp.build_workflow_scripts(target_root, config, dry_run=False, force=True)
    assert written_first == 1, f"Expected 1 file written on first run, got {written_first}."

    deployed = target_root / "workflows" / "sample.js"
    rendered = deployed.read_text(encoding="utf-8")
    assert "{{config.output_root}}" not in rendered, (
        "build_workflow_scripts did not resolve {{config.output_root}} in the "
        f"written file. Content: {rendered!r} (AC BP-900g-6)."
    )
    assert ".leafcutter/scripts/foo.py" in rendered, (
        f"Expected the rendered output_root value inline. Content: {rendered!r} "
        "(AC BP-900g-6)."
    )

    written_second = _bp.build_workflow_scripts(target_root, config, dry_run=False, force=True)
    assert written_second == 0, (
        f"Expected 0 files written on an identical second run (compare-before-write "
        f"guard), got {written_second}. Injection must run BEFORE the guard so a "
        "rendered-but-unchanged file is recognised as up-to-date (AC BP-900g-6)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-14 [BrainCandy/BP-900g-6]: Initial implementation. Root cause:
#   build_workflow_scripts copied templates/workflows-js/*.js byte-verbatim
#   (_emit_workflow_variant is an identity transform for the only supported
#   engine, "e2"), and inject_config() was never called on the result, unlike
#   every other file-based artifact phase (build_workflows, build_commands,
#   build_rules, build_commit_guardian). Every {{config.output_root}} token a
#   workflow author wrote shipped to consumers unresolved, and every hardcoded
#   "scripts/..." invocation was silently wrong for any consumer who
#   customises output_root away from the default ".leafcutter"
#   (config/skills_config.schema.json documents it as "Configurable per
#   consumer project").
#   Design choice: behavioral-only, deployed-tree assertions — mirroring
#   test_bp_900g_4.py's Tier 2 rationale. A source-tree check cannot detect a
#   missing inject_config() call because the un-rendered token is present in
#   the source either way; only running the real build and reading the
#   rendered output can. output_root is discovered dynamically (the directory
#   under target_dir containing scripts/) in every test, never hardcoded to
#   ".leafcutter", so these tests hold under a customised output_root too.
#   (#BP-900g-6)
# ====================================================================
