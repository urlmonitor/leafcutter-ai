"""
MODULE: unit_tests/_inf_600k_1_fixtures.py
GOAL: Shared fixture helpers for AC INF-600k-1's test suite (hand-driven
    build; the AC YAML is the spec -- see
    docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/
    INF-600k-1.yaml). Not a test file itself -- mirrors the existing
    unit_tests/commit_guardian/_ge_113c_1_vi_fixtures.py and
    unit_tests/build_orchestration/_bo2400a1iii_fixtures.py helper-module
    conventions already used in this repo for exercising a commit-time hook
    (or the build-time registry validator) as a real subprocess or direct
    call against real, on-disk fixture data.
ARCHITECTURE: Split out of the original unit_tests/test_inf_600k_1.py
    (check-file-size: a new file's flat 400-content-line cap was exceeded by
    the combined test_spec suite plus two rounds of pr-reviewer regression
    tests) into three files: this shared fixture module, test_inf_600k_1.py
    (keeping the AC's own test_spec-named 8 tests -- the AC's test_spec
    names this exact filename, so it must keep them), and
    test_inf_600k_1_regressions.py (the four regression tests added after
    review). This is a PURE MOVE: every helper below is byte-identical to
    its original definition in test_inf_600k_1.py, relocated only.

    Every test in both sibling test files invokes the REAL entry points,
    never an in-memory unit of either production file's internals:
      - registry_validator.validate_agent_registry(package_root) -- the
        build-time / check-agent-registry path -- called directly against a
        tmp package root (config/agent_registry.json +
        templates/workflows-js/*.js, real files copied from this repo where
        a real counterpart exists, per Fixture Authenticity Rule 2h.2).
      - scripts/commit_guardian/hooks/check_agent_spawn_consistency.py --
        the pre-commit hook -- run as a REAL subprocess against a tmp git
        repo standing in for a package root, with the registry staged via
        `git add`. The hook's own card<->registry mirror check
        (`_check_card_registry_mirror`, Direction 2b: "registry says X
        spawns me, but the card does not show it") is the observable
        channel through which an unrecognized spawned_by name is rejected,
        so every hook-side fixture ships a matching
        docs/agents/cards/<id>.card.md whose mermaid diagram deliberately
        omits a dispatch edge for the external name under test -- exactly
        how a REAL generated card looks, since workflows and the literal
        'user' trigger are never drawn as agent nodes.

DECISION HISTORY
- 2026-09-28 [test-writer/INF-600k-1]: Split out of test_inf_600k_1.py to
    satisfy check-file-size's flat 400-content-line cap on new files. Every
    helper is an unmodified relocation; no test name, body, `covers:`/
    `angle:` tag, or assertion changed anywhere in this split.
- 2026-09-30 [python-coder/INF-600k-1]: Merge-with-main and CI fix. Dropped three
    unused re-exported imports (ruff F401; test_inf_600k_1.py now imports them
    directly) and copy the new package_root_lookup.py sibling into the
    deployed-layout fixture. No assertion or test body changed.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HOOK_PATH = REPO_ROOT / "scripts" / "commit_guardian" / "hooks" / "check_agent_spawn_consistency.py"
TEMPLATE_HOOK_PATH = (
    REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "hooks" / "check_agent_spawn_consistency.py"
)
REAL_SCHEMA = REPO_ROOT / "config" / "agent_registry.schema.json"
REAL_WORKFLOWS_DIR = REPO_ROOT / "templates" / "workflows-js"
REAL_REGISTRY = REPO_ROOT / "config" / "agent_registry.json"

TEMPLATES_CG_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_RESOLVE_ROOT_SRC = TEMPLATES_CG_DIR / "_resolve_root.py"
_AGENT_SPAWN_EXTERNAL_CALLERS_SRC = TEMPLATES_CG_DIR / "agent_spawn_external_callers.py"
_CARD_MERMAID_PARSER_SRC = TEMPLATES_CG_DIR / "card_mermaid_parser.py"
_PACKAGE_ROOT_LOOKUP_SRC = TEMPLATES_CG_DIR / "package_root_lookup.py"
_CHECK_AGENT_REGISTRY_SRC = TEMPLATES_CG_DIR / "check_agent_registry.py"
_CHECK_AGENT_SPAWN_CONSISTENCY_SRC = TEMPLATES_CG_DIR / "hooks" / "check_agent_spawn_consistency.py"


def _write_schema(pkg_root: Path) -> None:
    """Copy the REAL agent_registry.schema.json into the fixture.

    check_step_kinds() (an unrelated validate_agent_registry() sub-check)
    hard-fails with its own error whenever this schema is unreadable, which
    would pollute every fixture's error list with noise unrelated to the
    spawned_by classification under test.
    """
    (pkg_root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL_SCHEMA, pkg_root / "config" / "agent_registry.schema.json")


def _write_registry(pkg_root: Path, agents: list[dict]) -> None:
    (pkg_root / "config").mkdir(parents=True, exist_ok=True)
    (pkg_root / "config" / "agent_registry.json").write_text(
        json.dumps({"agents": agents}), encoding="utf-8"
    )


def _make_agent(agent_id: str, **kwargs) -> dict:
    """Minimal agent entry: 'produces' is always set (validate_produces_field
    hard-fails on its absence, unrelated to the spawned_by classification
    under test); 'template_path' is deliberately omitted so
    _check_template_paths() resolves it to the package root itself (which
    always exists) rather than requiring real template files on disk.
    """
    agent = {"id": agent_id, "produces": "orchestration"}
    agent.update(kwargs)
    return agent


def _copy_real_workflow(dest_dir: Path, filename: str) -> None:
    """Materialize *filename* under dest_dir from the REAL on-disk workflow
    file when this repo really ships one (Fixture Authenticity Rule 2h.2).
    Callers representing a MISSING workflow simply never call this helper
    for that name -- there is no real counterpart to fall back to for a
    name invented purely for a fixture (e.g. 'brand-new-flow.js').
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = REAL_WORKFLOWS_DIR / filename
    if src.exists():
        shutil.copy(src, dest_dir / filename)
    else:
        (dest_dir / filename).write_text(
            "// fixture-only stub workflow (no real counterpart in this repo)\n"
            "module.exports = {};\n",
            encoding="utf-8",
        )


def _card_text(agent_id: str, dispatched_by: tuple[str, ...] = ()) -> str:
    """Minimal .card.md fixture: a mermaid block with only the requested
    -->|dispatches| edges. Workflows and the literal 'user' trigger are
    never drawn as dispatcher nodes in a REAL generated card, so omitting
    them here (the default) reproduces the real card shape exactly.
    """
    node = agent_id.replace("-", "_")
    lines = [
        "---",
        f"agent_id: {agent_id}",
        "type: card",
        "---",
        "",
        f"# {agent_id}",
        "",
        "## Spawn and Dependency",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for parent in dispatched_by:
        pnode = parent.replace("-", "_")
        lines.append(f'    {pnode}["{parent}"]:::supervisor')
    lines.append(f'    {node}["{agent_id}"]:::target')
    lines.append("")
    for parent in dispatched_by:
        pnode = parent.replace("-", "_")
        lines.append(f"    {pnode} -->|dispatches| {node}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@leafcutter.test"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "LeafcutterTest"],
        check=True, capture_output=True,
    )


def _stage_all(path: Path) -> None:
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, capture_output=True)


def _run_hook(cwd: Path, hook_path: Path = HOOK_PATH) -> subprocess.CompletedProcess:
    """Run the REAL spawn-consistency hook as a subprocess against *cwd*
    (a tmp git repo standing in for a package root) -- the reachability
    angle: a real entry point via subprocess, never an imported function
    call into the hook's internals.

    Args:
        cwd: Working directory to run the subprocess in (a fixture git repo).
        hook_path: Which on-disk hook copy to execute. Defaults to this
            repo's live `scripts/` copy; callers with their own deployed
            fixture copy (e.g. at a synthesized `commit_guardian/hooks/`
            depth) pass that path instead.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _has_unknown_agent_error(errors: list[str], name: str) -> bool:
    needle = f"unknown agent '{name}'"
    return any(needle in e for e in errors)


def _list_modified_tracked_files() -> list[str]:
    """Tracked files with uncommitted working-tree changes (relative paths)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _list_untracked_source_overlay() -> list[str]:
    """Untracked files that a real commit would add as production source.

    Restricted to scripts/ and templates/ (where production source lives),
    explicitly excluding:
      - scripts/commit_guardian/ -- GITIGNORED BUILD OUTPUT (see
        .gitignore's BP-016 note). A fresh clone never has this directory
        on disk; that absence is exactly the condition this fixture exists
        to reproduce, so it must never be overlaid in even though it is
        physically present in this dev worktree.
      - unit_tests/ -- test-writer's own output, irrelevant to build.py and
        never part of the production source tree.

    Returns:
        Relative paths (POSIX-style, as git reports them) of untracked
        production-source files to overlay on top of the `git archive`
        base.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    overlay: list[str] = []
    for line in result.stdout.splitlines():
        if not line.startswith("?? "):
            continue
        path = line[3:].strip()
        if path.startswith("scripts/commit_guardian/"):
            continue
        if path.startswith("unit_tests/"):
            continue
        if path.startswith("scripts/") or path.startswith("templates/"):
            overlay.append(path)
    return overlay


def _build_fresh_clone_fixture(dest: Path) -> list[str]:
    """Materialize "a fresh clone checked out at the commit this ticket is
    about to produce" at *dest*.

    APPROACH (documented per the coordinator's request):
      1. `git archive --format=zip HEAD`, extracted into *dest* -- this is
         HEAD's TRACKED tree only. Since `scripts/commit_guardian/` and
         `.leafcutter/` are both gitignored build output, neither is ever
         present in a `git archive` output -- exactly like a genuine fresh
         `git clone` that has never run `build.py`. (`--format=zip` is used
         instead of piping to `tar -x` so this fixture has no dependency on
         an external `tar` binary being on PATH; Python's stdlib `zipfile`
         extracts it directly.)
      2. Overlay the CURRENT WORKING-TREE content of every tracked file
         `git diff --name-only HEAD` reports as modified. `git archive`
         only ever materializes committed content, so without this step
         the fixture would silently test the LAST COMMIT's code, not the
         in-flight fix under review.
      3. Overlay every UNTRACKED production-source file under `scripts/` or
         `templates/` (excluding the gitignored `scripts/commit_guardian/`
         build output and this repo's own `unit_tests/`). A brand-new
         module introduced by this ticket (e.g. the shared external-caller
         classifier, or a loader module for it) is untracked while
         python-coder is still working, so a pure `git archive` + modified-
         file overlay would silently MISS it -- even though it is a real
         source file that WILL be included the moment this ticket's commit
         is made. See `_list_untracked_source_overlay()`.

    Args:
        dest: Empty directory to materialize the fixture tree into.

    Returns:
        The list of untracked overlay paths applied (step 3), included in
        assertion failure messages for diagnosability.
    """
    archive = subprocess.run(
        ["git", "archive", "--format=zip", "HEAD"],
        cwd=str(REPO_ROOT), capture_output=True, check=True,
    )
    zipfile.ZipFile(io.BytesIO(archive.stdout)).extractall(dest)

    for rel in _list_modified_tracked_files():
        src = REPO_ROOT / rel
        dst = dest / rel
        if not src.exists():
            # Working tree deleted a tracked file -- the fresh-clone fixture
            # must not resurrect it via the git-archive base.
            if dst.exists():
                dst.unlink()
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    overlay = _list_untracked_source_overlay()
    for rel in overlay:
        src = REPO_ROOT / rel
        if not src.is_file():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    return overlay


# Loads the DEPLOYED _resolve_root.py by file path (never this test process's
# own imported copy) in a fresh subprocess, and reports
# candidate_manifest_roots() / resolve_package_root() for the given hook file
# as JSON. A fresh subprocess (rather than an in-process importlib load) is
# used deliberately: find_project_root() caches its result in a module-level
# global, and its `git rev-parse --show-toplevel` call resolves relative to
# the CURRENT PROCESS's cwd -- a fresh subprocess with cwd set to the fixture
# repo is what makes it resolve the FIXTURE, never this actual dev worktree
# or a stale cached root left over from an earlier call in the same process.
_RESOLVE_ROOT_PROBE_SCRIPT = """
import importlib.util
import json
import sys
from pathlib import Path

resolve_root_path = Path(sys.argv[1])
hook_file = Path(sys.argv[2]).resolve()

spec = importlib.util.spec_from_file_location("_resolve_root_probe", resolve_root_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

roots = [str(p) for p in module.candidate_manifest_roots(hook_file)]
manifest_path, _tried_manifest = module.resolve_manifest_path(hook_file)
package_root, tried_package = module.resolve_package_root(hook_file)

print(json.dumps({
    "roots": roots,
    "manifest_path": str(manifest_path) if manifest_path else None,
    "package_root": str(package_root) if package_root else None,
    "tried_package": tried_package,
}))
"""


def _build_workspace_parent_fixture(workspace: Path) -> dict[str, Path]:
    """Build a real workspace-parent fixture:

        <workspace>/
          .build_manifest.json          {"package_root": "leafcutter-ai"}
          leafcutter-ai/                 the REAL vendored package -- a
                                          SIBLING of the git repo below, NOT
                                          nested inside it
            templates/workflows-js/fast-lane-ship.js
          consumer-project/               a REAL git repo (cwd during hook
                                          execution) -- deliberately a
                                          DIFFERENT directory than
                                          leafcutter-ai, so a fallback to
                                          bare Path.cwd() cannot accidentally
                                          find the real file and mask the
                                          manifest-resolution bug
            config/agent_registry.json    spawner-agent, spawned_by=["fast-lane-ship.js"]
            docs/agents/cards/spawner-agent.card.md
            scripts/commit_guardian/
              _resolve_root.py, agent_spawn_external_callers.py,
              card_mermaid_parser.py, package_root_lookup.py
                                            real, deployed sibling modules
              check_agent_registry.py       deployed at commit_guardian/ depth
                                             -- the REGRESSION CONTROL: not
                                             nested under hooks/, so its
                                             workspace-root arithmetic is
                                             unaffected by this defect
              hooks/check_agent_spawn_consistency.py   deployed at its REAL
                                             commit_guardian/hooks/ depth --
                                             the DEFECT under test

    Args:
        workspace: Empty tmp directory to build the fixture tree inside.

    Returns:
        Dict of the paths a test needs: "consumer", "hooks_hook",
        "registry_hook", "package_dir", "resolve_root_module".
    """
    consumer = workspace / "consumer-project"
    consumer.mkdir(parents=True)
    _init_git_repo(consumer)

    cg_dir = consumer / "scripts" / "commit_guardian"
    hooks_dir = cg_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    resolve_root_dest = cg_dir / "_resolve_root.py"
    shutil.copy(_RESOLVE_ROOT_SRC, resolve_root_dest)
    shutil.copy(_AGENT_SPAWN_EXTERNAL_CALLERS_SRC, cg_dir / "agent_spawn_external_callers.py")
    shutil.copy(_CARD_MERMAID_PARSER_SRC, cg_dir / "card_mermaid_parser.py")
    shutil.copy(_PACKAGE_ROOT_LOOKUP_SRC, cg_dir / "package_root_lookup.py")

    registry_hook = cg_dir / "check_agent_registry.py"
    shutil.copy(_CHECK_AGENT_REGISTRY_SRC, registry_hook)

    hooks_hook = hooks_dir / "check_agent_spawn_consistency.py"
    shutil.copy(_CHECK_AGENT_SPAWN_CONSISTENCY_SRC, hooks_hook)

    _write_registry(consumer, [_make_agent("spawner-agent", spawned_by=["fast-lane-ship.js"])])
    cards_dir = consumer / "docs" / "agents" / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "spawner-agent.card.md").write_text(_card_text("spawner-agent"), encoding="utf-8")
    _stage_all(consumer)

    (workspace / ".build_manifest.json").write_text(
        json.dumps({"package_root": "leafcutter-ai"}), encoding="utf-8"
    )
    package_dir = workspace / "leafcutter-ai"
    _copy_real_workflow(package_dir / "templates" / "workflows-js", "fast-lane-ship.js")

    return {
        "consumer": consumer,
        "hooks_hook": hooks_hook,
        "registry_hook": registry_hook,
        "package_dir": package_dir,
        "resolve_root_module": resolve_root_dest,
    }


def _run_resolve_root_probe(resolve_root_path: Path, hook_file: Path, cwd: Path) -> dict:
    """Run the probe subprocess described above and return its parsed JSON.

    Args:
        resolve_root_path: Path to the deployed `_resolve_root.py` to load.
        hook_file: The (deployed) hook path to compute candidate roots for.
        cwd: Working directory for the subprocess -- the fixture's git repo,
            exactly as pre-commit invokes a real hook.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c", _RESOLVE_ROOT_PROBE_SCRIPT, str(resolve_root_path), str(hook_file)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"_resolve_root probe crashed unexpectedly: exit={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return json.loads(result.stdout)
