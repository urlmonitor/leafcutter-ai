"""
MODULE: test_bp_900g_4
GOAL: Regression guard for the deploy-reachability blind spot in
    ``extract_script_path_refs`` — script references written in the output-root
    template form (``python3 {{config.output_root}}/scripts/...``) were silently
    skipped by the broken-reference guard, so build.py exited zero while shipping
    an agent template that dies at its first command.
BUSINESS CONTEXT: The build-ac agent's Step 2b.1 invokes
    ``{{config.output_root}}/scripts/build_orchestration/fast_lane.py``. No build
    phase deployed ``scripts/build_orchestration/``, so in a consumer install the
    command failed with "can't open file". The existing guard did not catch it:
    ``_PYTHON_INVOKE_RE`` requires whitespace immediately before ``scripts/``, and
    in the output-root form the preceding character is ``/``. Every such reference
    was invisible — ``test_guard_exits_0_on_clean_package`` passed green throughout.
    AC BP-900g-4.
ARCHITECTURE: Two tiers, deliberately. The extractor tests are unit-level and pin
    the specific regex blind spot. The deployed-tree test is behavioral: it runs the
    REAL ``build.py --target-dir`` into a temp root, then resolves every script path
    referenced by the DEPLOYED templates against that deployed tree. Only the second
    tier would have caught this class of defect — a test that resolves against the
    package source tree shares the exact bias that let the bug ship.
"""
# @ac-tag: BP-900g-4

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_referential_integrity as _bri  # noqa: E402 — after sys.path setup


def _load_build_module() -> Any:
    """Load scripts/build.py by path rather than ``import build``.

    ``scripts/build.py`` shares its module name with the installed PyPI
    ``build`` package (the PEP 517 build frontend). At runtime the
    ``sys.path.insert(0, ...)`` above makes the local script win, but mypy's
    static import resolution does not execute that sys.path mutation — it
    resolved ``import build`` to the installed package instead, so
    ``_build.main`` / ``_build._get_source_deployable_scripts`` looked like
    attribute errors against a module that never had them. Loading by path
    sidesteps the name collision entirely (and removes a real runtime
    footgun: this test no longer depends on sys.path ordering to avoid
    silently exercising the wrong package).
    """
    build_py_path = _SCRIPTS_DIR / "build.py"
    spec = importlib.util.spec_from_file_location("scripts_build_under_test", build_py_path)
    assert spec is not None and spec.loader is not None, f"could not load spec for {build_py_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_build = _load_build_module()

def _deployed_invoke_re(output_root_name: str) -> re.Pattern[str]:
    """Build the invocation matcher for a specific deployed output root.

    Matches only ``python3 <output_root>/scripts/<...>.py`` — the form an agent
    actually executes inside a consumer install.

    The output root is passed in rather than hardcoded, and the pattern is
    deliberately NOT widened to any leading segment: deployed docs legitimately
    discuss package-development paths (``python leafcutter/scripts/build.py``,
    ``debugging/scripts/...``) that are not expected to resolve in a consumer tree.
    Matching those would assert against prose instead of runtime behaviour.
    """
    return re.compile(
        rf"python3?\s+({re.escape(output_root_name)}/scripts/[\w./\-]+\.py)"
    )


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the dir holding scripts/.

    Keyed on ``scripts/`` rather than ``agents/`` deliberately: the build deploys
    agent markdown to more than one location (``.claude/`` and the output root),
    but the scripts land only under the output root, and the output root is the
    prefix the templates' invocations are written against.
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} (a directory "
        f"containing a 'scripts/' subdirectory); found {[p.name for p in candidates]}. "
        "The reference-prefix assumption below is only valid for a single output root."
    )
    return candidates[0]


def _write_template(templates_dir: Path, name: str, body: str) -> None:
    """Create ``templates_dir/agents/<name>`` containing ``body``."""
    agents = templates_dir / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / name).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tier 1 — the extractor must see the output-root template form
# ---------------------------------------------------------------------------


def test_extractor_sees_output_root_template_form(tmp_path: Path) -> None:
    """A ``{{config.output_root}}/scripts/...`` reference must be extracted.

    This is the literal form that lives in the tracked source templates, which is
    what the preflight guard scans. Before the fix the regex required whitespace
    immediately before ``scripts/``, so this reference produced no match at all.
    """
    # covers: BP-900g-4
    templates = tmp_path / "templates"
    _write_template(
        templates,
        "synthetic_output_root.md",
        "python3 {{config.output_root}}/scripts/build_orchestration/fast_lane.py "
        "select_connected --ac FOO-1\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/build_orchestration/fast_lane.py" in refs, (
        "extract_script_path_refs() did not extract "
        "'scripts/build_orchestration/fast_lane.py' from a reference written as "
        "'python3 {{config.output_root}}/scripts/build_orchestration/fast_lane.py'. "
        f"Extracted: {sorted(refs)!r}. "
        "Agent templates address deployed scripts through the output-root variable, "
        "so a pattern that only matches a bare 'scripts/...' path makes every such "
        "reference invisible to _check_script_reference_guard() (AC BP-900g-4)."
    )


def test_extractor_sees_rendered_output_root_form(tmp_path: Path) -> None:
    """An already-rendered ``.leafcutter/scripts/...`` reference must be extracted.

    Templates are scanned pre-render, but the rendered prefix also appears in
    hand-authored prose and in templates that hardcode the default output root.
    Both spellings must normalise to the same deploy-namespace key.
    """
    # covers: BP-900g-4
    templates = tmp_path / "templates"
    _write_template(
        templates,
        "synthetic_rendered.md",
        "python3 .leafcutter/scripts/build_orchestration/fast_lane.py --ac FOO-1\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/build_orchestration/fast_lane.py" in refs, (
        "extract_script_path_refs() did not extract "
        "'scripts/build_orchestration/fast_lane.py' from a reference written as "
        "'python3 .leafcutter/scripts/build_orchestration/fast_lane.py'. "
        f"Extracted: {sorted(refs)!r} (AC BP-900g-4)."
    )


def test_extractor_still_sees_bare_scripts_form(tmp_path: Path) -> None:
    """The pre-existing bare ``scripts/...`` form must keep working.

    Backward-compatibility invariant: widening the pattern must not drop the form
    the guard already relied on, which the majority of templates still use.
    """
    # covers: BP-900g-4
    templates = tmp_path / "templates"
    _write_template(
        templates,
        "synthetic_bare.md",
        "python scripts/feedback/submit_feedback.py --tag x\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/feedback/submit_feedback.py" in refs, (
        "extract_script_path_refs() stopped extracting the bare 'scripts/...' form. "
        f"Extracted: {sorted(refs)!r}. This is a backward-compatibility regression "
        "(AC BP-900g-4)."
    )


def test_extractor_does_not_capture_unrelated_prefixes(tmp_path: Path) -> None:
    """The widened pattern must not swallow arbitrary look-alike paths.

    EPIC-BuildGuardFalsePositive was caused by the guard flagging legitimate
    references. Widening the prefix must stay bounded to a single path segment so
    an unrelated vendored path does not become a phantom 'missing script' and fail
    the build for everyone.
    """
    # covers: BP-900g-4
    templates = tmp_path / "templates"
    _write_template(
        templates,
        "synthetic_unrelated.md",
        "python3 /usr/lib/vendor/deep/nested/scripts/other.py\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/other.py" not in refs, (
        "extract_script_path_refs() captured 'scripts/other.py' from a deep "
        "absolute vendor path. The prefix allowance must be bounded to a single "
        "leading segment (the output root), not any number of parent directories, "
        f"or the guard emits false-positive build failures. Extracted: {sorted(refs)!r} "
        "(AC BP-900g-4)."
    )


def test_extractor_does_not_capture_host_project_paths(tmp_path: Path) -> None:
    """Host-project paths containing a ``scripts/`` component must NOT be captured.

    Templates legitimately reference scripts belonging to the CONSUMER's project
    (``python debugging/scripts/check/prod_status_check.py`` in status-checker.md)
    and to the package-development tree (``python leafcutter/scripts/build.py``).
    Neither is a leafcutter deliverable. Normalising them into ``scripts/...``
    deploy keys would make the guard demand a deploy phase for a file that is not
    ours, failing the build for every consumer — the EPIC-BuildGuardFalsePositive
    failure mode. Only a dot-prefixed output root may precede ``scripts/``.
    """
    # covers: BP-900g-5
    templates = tmp_path / "templates"
    _write_template(
        templates,
        "synthetic_host_paths.md",
        "python debugging/scripts/check/prod_status_check.py --action all\n"
        "python leafcutter/scripts/build.py --target-dir .\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/check/prod_status_check.py" not in refs, (
        "extract_script_path_refs() captured 'scripts/check/prod_status_check.py' "
        "from the host-project path 'debugging/scripts/check/prod_status_check.py'. "
        f"Extracted: {sorted(refs)!r}. Only an output root (the "
        "'{{config.output_root}}/' token or a dot-prefixed root like '.leafcutter/') "
        "may precede 'scripts/' (AC BP-900g-5)."
    )
    assert "scripts/build.py" not in refs, (
        "extract_script_path_refs() captured 'scripts/build.py' from the "
        "package-development path 'leafcutter/scripts/build.py'. "
        f"Extracted: {sorted(refs)!r} (AC BP-900g-5)."
    )


# ---------------------------------------------------------------------------
# Tier 1b — fast_lane.py must be in the deployable manifest
# ---------------------------------------------------------------------------


def test_fast_lane_is_deployable() -> None:
    """``scripts/build_orchestration/fast_lane.py`` must be a deployable script.

    The build-ac agent shells out to it at Step 2b.1. Without a deploy phase the
    script never reaches a consumer install and the agent dies at its first command.
    """
    # covers: BP-900g-4
    deployable = _build._get_source_deployable_scripts(_REPO_ROOT)

    assert "scripts/build_orchestration/fast_lane.py" in deployable, (
        "_get_source_deployable_scripts() does not include "
        "'scripts/build_orchestration/fast_lane.py'. The build-ac agent invokes it "
        "at Step 2b.1, so it must be deployed by a build phase (mirroring "
        "build_knowledge_scripts, which closed the same Class B gap for "
        "harvest_learnings.py). (AC BP-900g-4)"
    )


# ---------------------------------------------------------------------------
# Tier 2 — behavioral: resolve against a REAL deployed tree
# ---------------------------------------------------------------------------


def test_deployed_templates_reference_only_deployed_scripts(tmp_path: Path) -> None:
    """Every script a DEPLOYED template invokes must exist in the deployed tree.

    This is the tier that matters. It runs the real ``build.py --target-dir`` into a
    fresh temp root, then walks the deployed ``.md`` files, extracts each rendered
    ``<output-root>/scripts/...`` invocation, and resolves it against that same temp
    root. Resolving against the package source tree — which is what every prior test
    did — cannot detect a missing deploy phase, because the source file is present
    either way. AC BP-900g-4.
    """
    # covers: BP-900g-4
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. "
        "The deployed-tree reachability assertion below cannot run against a "
        "failed build."
    )

    output_root = _find_output_root(target_dir)
    invoke_re = _deployed_invoke_re(output_root.name)

    unresolved: list[str] = []
    seen: set[str] = set()
    for md_file in sorted(target_dir.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for rel_path in invoke_re.findall(text):
            seen.add(rel_path)
            if not (target_dir / rel_path).is_file():
                unresolved.append(
                    f"{md_file.relative_to(target_dir).as_posix()} → {rel_path}"
                )

    # Non-vacuity guard: if the matcher silently stops matching (a template rewrite,
    # a changed output root, a regex regression) this test would pass while checking
    # nothing at all — the same false-green shape as the bug it exists to prevent.
    expected = f"{output_root.name}/scripts/build_orchestration/fast_lane.py"
    assert expected in seen, (
        f"The deployed-tree scan found no reference to {expected!r}. It found: "
        f"{sorted(seen)!r}. build-ac invokes fast_lane.py at Step 2b.1, so that "
        "reference must be present — its absence means this test is no longer "
        "checking anything (AC BP-900g-4)."
    )

    assert not unresolved, (
        f"{len(unresolved)} script reference(s) in the DEPLOYED tree do not resolve "
        f"to a file in that same tree:\n  " + "\n  ".join(sorted(set(unresolved))) + "\n"
        "Each of these is an agent template that will die at that command in a "
        "consumer install, even though build.py exited 0. Add a deploy phase for the "
        "missing script, or correct the path in the source template (AC BP-900g-4)."
    )


def test_build_ac_ac_root_targets_consumer_store() -> None:
    """build-ac's Step 2b.1 ``--ac-root`` must address the consumer's own AC store.

    The rest of the template reads the store as ``docs/acceptance-criteria``. Step
    2b.1 was authored with an output-root-prefixed path, which exists in no layout,
    so ``select_connected`` would fail even once fast_lane.py deploys.
    """
    # covers: BP-900g-4
    template = _REPO_ROOT / "templates" / "agents" / "build-ac.md"
    text = template.read_text(encoding="utf-8")

    # Restrict to actual shell invocations — lines that START with the interpreter.
    # Prose elsewhere in the file (notably a DECISION HISTORY entry that reads
    # "...corrected to scripts/build_orchestration/fast_lane.py select_connected;
    # added required --ac-root argument.") contains every keyword the command does,
    # so keyword filtering alone asserts against English rather than behaviour.
    select_lines = [
        line
        for line in text.splitlines()
        if line.lstrip().startswith(("python3 ", "python "))
        and "fast_lane.py" in line
        and "select_connected" in line
        and "--ac-root" in line
    ]
    assert select_lines, (
        "No fast_lane.py select_connected invocation with an --ac-root argument found "
        "in templates/agents/build-ac.md. Step 2b.1 must resolve the connected build "
        "set via that CLI (AC BP-900g-4)."
    )

    for line in select_lines:
        match = re.search(r"--ac-root\s+(\S+)", line)
        assert match, f"Could not parse --ac-root from: {line!r}"
        ac_root = match.group(1)
        assert ac_root == "docs/acceptance-criteria", (
            f"select_connected is invoked with --ac-root {ac_root!r}. Expected "
            "'docs/acceptance-criteria' — the consumer's own AC store, and the form "
            "this same template already uses at its other call sites. An "
            "output-root-prefixed path exists in no layout (AC BP-900g-4)."
        )


def test_deployed_fast_lane_actually_executes(tmp_path: Path) -> None:
    """The deployed fast_lane.py must RUN, not merely exist.

    Presence is not reachability. The first cut of this fix deployed
    ``scripts/build_orchestration/`` correctly and the file was present in the
    consumer tree — but ``ac_parent_id.py`` was absent from build_ac_store's
    deploy map, so the very first import raised ModuleNotFoundError and
    /build-ac still died at Step 2b.1. A file-presence assertion passes in that
    state; only executing the script catches it.

    This runs the real deployed entry point as a subprocess against the real AC
    store and asserts the documented GE-113c-3 connected set comes back.
    """
    # covers: BP-900g-4
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_output_root(target_dir)
    deployed = output_root / "scripts" / "build_orchestration" / "fast_lane.py"
    assert deployed.is_file(), f"fast_lane.py was not deployed to {deployed}."

    # The connected set is resolved against a FROZEN COPY of the GE-113c-3
    # records, not the live store. Pointing --ac-root at the real store made
    # this test depend on those ACs staying unbuilt: once GE-113c-3 and its
    # children were completed (work_status: done) the resolver correctly
    # returned [] and this test failed, even though the deployed script ran
    # perfectly — which is the only thing BP-900g-4 is actually about.
    # Copying the real records preserves schema fidelity; resetting
    # work_status pins the fixture so completing real work cannot break it.
    fixture_root = tmp_path / "ac-store"
    fixture_dir = fixture_root / "guardrail-engine" / "GE-113c-3-fixture"
    fixture_dir.mkdir(parents=True)
    source_dir = (
        _REPO_ROOT
        / "docs"
        / "acceptance-criteria"
        / "guardrail-engine"
        / "GE-113-artifacts-cant-land-in-the-wrong-place"
    )
    for ac_id in ("GE-113c", "GE-113c-3", "GE-113c-3-i", "GE-113c-3-ii",
                  "GE-113c-3-iii", "GE-113c-3-iv"):
        text = (source_dir / f"{ac_id}.yaml").read_text(encoding="utf-8")
        text = text.replace("work_status: done", "work_status: todo")
        (fixture_dir / f"{ac_id}.yaml").write_text(text, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(deployed),
            "select_connected",
            "--exclude-structural-parent",
            "--ac",
            "GE-113c-3",
            "--ac-root",
            str(fixture_root),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        "The DEPLOYED fast_lane.py failed to execute.\n"
        f"exit={result.returncode}\nstderr:\n{result.stderr}\n"
        "The script is present in the consumer tree but cannot run there — most "
        "likely one of its imports is not deployed. Add the missing module to the "
        "relevant deploy phase (AC BP-900g-4)."
    )

    ids = json.loads(result.stdout)
    assert ids == [
        "GE-113c-3",
        "GE-113c-3-i",
        "GE-113c-3-ii",
        "GE-113c-3-iii",
        "GE-113c-3-iv",
    ], (
        f"Deployed fast_lane.py returned {ids!r} for GE-113c-3. Expected the target "
        "plus its four L3 children, with the structural parent GE-113c excluded "
        "(AC BP-900g-4 / BO-2600a-4)."
    )


def test_known_undeployed_allowlist_is_empty() -> None:
    """KNOWN_UNDEPLOYED_ALLOWLIST must stay empty.

    BP-900g-5 emptied it. An entry means an agent or skill is shipping with a
    command it cannot run, suppressed rather than fixed — so re-parking anything
    here should be a visible, deliberate act that fails CI first.
    """
    # covers: BP-900g-5
    import build_propagation_audit as _bpa

    assert _bpa.KNOWN_UNDEPLOYED_ALLOWLIST == frozenset(), (
        "KNOWN_UNDEPLOYED_ALLOWLIST is not empty: "
        f"{sorted(_bpa.KNOWN_UNDEPLOYED_ALLOWLIST)!r}. Each entry is a leafcutter "
        "script that a deployed agent or skill invokes but no build phase ships, so "
        "that capability dies at its first command in a consumer install. Add the "
        "script to build_agent_support_scripts' deploy spec instead of parking it "
        "here (AC BP-900g-5)."
    )


def test_previously_undeployed_scripts_are_deployable() -> None:
    """The six formerly-dead agent-support scripts must be in the deployable set."""
    # covers: BP-900g-5
    deployable = _build._get_source_deployable_scripts(_REPO_ROOT)

    for expected in (
        "scripts/changelog/emit_entry.py",
        "scripts/next_diagram_seq.py",
        "scripts/retrospective/extract_epic_facts.py",
        "scripts/agent-health/generate_health_report.py",
        "scripts/roadmap_query.py",
        "scripts/package_audit.py",
        # Not referenced by any template, but roadmap_query.py execs it at import.
        "scripts/roadmap_query_audit.py",
    ):
        assert expected in deployable, (
            f"_get_source_deployable_scripts() does not include {expected!r}. It is "
            "invoked by a deployed agent or skill (or imported at module scope by one "
            "that is), so it must be deployed (AC BP-900g-5)."
        )


def test_deployed_agent_support_scripts_import_cleanly(tmp_path: Path) -> None:
    """Every newly-deployed agent-support script must IMPORT from the deployed tree.

    Presence is not reachability — the lesson from ac_parent_id.py. roadmap_query.py
    is the sharp case here: it execs roadmap_query_audit.py from its own directory at
    module scope, so it is importable only if that sibling was deployed too.

    Each script is imported in a fresh subprocess (not merely stat'ed), with the
    deployed scripts directory on sys.path, so a missing dependency surfaces as the
    ImportError a consumer would hit.
    """
    # covers: BP-900g-5
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()

    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, f"build.py --target-dir exited {exit_code!r}; expected 0."

    output_root = _find_output_root(target_dir)
    scripts_dir = output_root / "scripts"

    targets = [
        ("changelog/emit_entry.py", "emit_entry"),
        ("next_diagram_seq.py", "next_diagram_seq"),
        ("retrospective/extract_epic_facts.py", "extract_epic_facts"),
        ("agent-health/generate_health_report.py", "generate_health_report"),
        ("roadmap_query.py", "roadmap_query"),
        ("package_audit.py", "package_audit"),
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
        "time is missing from the deployed tree. Add that module to the deploy spec "
        "in build_phases.AGENT_SUPPORT_SCRIPT_DIRS/FILES (AC BP-900g-5)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-14 [BrainCandy/BP-900g-4]: Initial implementation. Root cause:
#   _PYTHON_INVOKE_RE in build_referential_integrity.py required whitespace
#   immediately before 'scripts/', so the output-root form used by agent templates
#   ({{config.output_root}}/scripts/...) never matched and the broken-reference
#   guard silently skipped every such reference. scripts/build_orchestration/
#   had no deploy phase, so the deployed build-ac agent failed at Step 2b.1 with
#   "can't open file .../fast_lane.py" while build.py exited 0 and
#   test_guard_exits_0_on_clean_package passed green.
#   Design choice: two tiers. Synthetic templates pin the regex behaviour
#   (including a negative control against over-widening, which is the
#   EPIC-BuildGuardFalsePositive failure mode). The deployed-tree test runs the
#   real build into tmp_path and resolves references against the DEPLOYED tree —
#   the only tier that can detect a missing deploy phase, since source-tree
#   resolution succeeds whether or not the script is ever deployed.
#   Added test_deployed_fast_lane_actually_executes after the first cut of the fix
#   proved insufficient: with scripts/build_orchestration/ deployed the file was
#   present in the consumer tree, the presence-based assertion passed, and the
#   script STILL failed at its first import because ac_parent_id.py was missing
#   from build_ac_store's deploy_map. Presence is not reachability — the execution
#   test runs the deployed entry point as a subprocess and asserts its output.
#   (#BP-900g-4)
# ====================================================================
