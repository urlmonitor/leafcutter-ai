"""
MODULE: unit_tests/build_guards/test_bp_900b_5_prompt_references_deployed.py
GOAL: Prove that every package script or config file a compiled prompt tells
    the agent to run, import or read is actually deployed into a CONSUMER
    install (BP-900b-5).

    The shared reference layout is a DIRECTED build into an empty directory --
    the adopter shape: package scripts land under ``<output_root>/scripts/``,
    package config under ``<output_root>/config/``, and there is no package
    ``scripts/`` or ``config/`` at the install root.

    The reproduction (DIAGraph, leafcutter v21.0.93, pin 67a7b443): the
    documentation-verifier's step 6a told the agent to run
    ``sys.path.insert(0, '<worktree_root>/scripts'); from
    build_placeholder_detection import scan_for_placeholders``. The build never
    deployed that module, so the verifier failed closed with
    ModuleNotFoundError and every ticket with a documentation-verifier phase
    halted (INF-120c-3).

    Scope of the sweep -- the defect class, not the path spelling. BP-900b-4
    covers a config file the build DOES deploy, named at a path where it does
    not exist. This module covers a file the build does NOT deploy at all: a
    reference counts as satisfied when the named path exists in the install,
    or when the same package-relative file is present under the output root.
    A deployed file named by a package-clone path (``leafcutter/scripts/...``)
    or by a bare ``scripts/...`` path is therefore not reported here.

    These tests only READ the deployed layout, so they request the shared
    session-scoped fixture rather than spawning their own build.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Compiled prompt surfaces under the output root (every platform root).
_PROMPT_DIRS = (
    "agents",
    "commands",
    "skills",
    "workflows",
    "gemini/agents",
    "gemini/skills",
    "gemini/workflows",
)

# RUN: ``python3 <path>.py`` (also ``poetry run python`` / ``uv run python``).
_RUN_RE = re.compile(r"\bpython3?\s+[\"']?([^\s\"'`]+\.py)\b")

# IMPORT: ``sys.path.insert(N, '<dir>'); from <module> import`` on one line --
# the single-command ``python3 -c`` shape the prompts hand the agent.
_SYSPATH_IMPORT_RE = re.compile(
    r"sys\.path\.insert\(\s*\d+\s*,\s*[\"']([^\"']+)[\"']\s*\)\s*;\s*from\s+(\w+)\s+import"
)

# CALL: "call `<path>.py`'s <fn>" or "<fn>() from `<path>.py`".
_CALL_RE = re.compile(r"(?:\bcall\s+|\bfrom\s+)`([^`\s]+\.py)`", re.IGNORECASE)

# READ: a config path on a line that tells the agent to read it.
_CONFIG_PATH_RE = re.compile(
    r"(?<![\w./{}<>:-])((?:[\w.-]+/)*config/[\w.-]+\.(?:json|ya?ml))"
)
# The look-behind keeps compounds such as "auto-load decisions" out.
_READ_VERB_RE = re.compile(
    r"(?<![\w-])(?:read|reads|load|loads|open|fall back to|conform to)\b", re.IGNORECASE
)

# A worktree-root placeholder segment the prompt asks the agent to fill in:
# ``<worktree_root>/``, ``<absolute worktree path>/``, ``"$WORKTREE_ROOT"/``.
_ROOT_PLACEHOLDER_RE = re.compile(r"^(?:<[^>]+>/|\"?\$\{?\w+\}?\"?/)+")

# Package-clone directory names an adopter checks the package out under.
_PACKAGE_CLONE_DIRS = ("leafcutter/", "leafcutter-ai/")

# Package-relative references that are deliberately NOT deployed. Every entry
# says why; anything else that resolves nowhere fails the sweep.
_NOT_A_DEPLOY_GAP: dict[str, str] = {
    "scripts/build.py": (
        "the build engine itself; an adopter runs it from the package clone "
        "and it is never deployed (CLAUDE.md, Repository Structure)"
    ),
    "scripts/list_sql_helpers.py": (
        "a host-project helper the sql-coder's PROJECT_CONTEXT supplies; not "
        "a package file"
    ),
    "scripts/scaffold/new_arch_doc.py": (
        "a host-project scaffold; write-c4-diagram already says to surface it "
        "when unavailable"
    ),
    "scripts/epic_lock.py": (
        "not a package file; building-epics gives the fallback to use when it "
        "is not available"
    ),
    "scripts/inline_adr/append_entry.py": (
        "not a package file; doc-enforcer runs it only 'if present'"
    ),
}


def _output_root(layout: Path) -> Path:
    """Return the install's declared output root (``.leafcutter`` by default)."""
    for cand in (layout / ".claude" / "skills_config.json",
                 layout / "config" / "skills_config.default.json"):
        if cand.is_file():
            val = json.loads(cand.read_text(encoding="utf-8")).get("output_root")
            if val:
                return layout / val
    return layout / ".leafcutter"


def _compiled_prompts(layout: Path) -> list[Path]:
    """Every compiled prompt the build wrote under the output root: markdown
    agents/skills/commands/workflows, plus the JS workflow scripts whose
    agent() prompt strings carry the same instructions."""
    out = _output_root(layout)
    found: list[Path] = []
    for rel in _PROMPT_DIRS:
        base = out / rel
        if base.is_dir():
            found.extend(sorted(base.rglob("*.md")))
            found.extend(sorted(base.rglob("*.js")))
    return found


def _line_references(line: str) -> list[tuple[str, str]]:
    """(kind, path token) for every run/import/call/read reference on *line*."""
    refs = [("run", m.group(1)) for m in _RUN_RE.finditer(line)]
    for m in _SYSPATH_IMPORT_RE.finditer(line):
        if m.group(2) not in sys.stdlib_module_names:
            refs.append(("import", f"{m.group(1).rstrip('/')}/{m.group(2)}.py"))
    refs.extend(("call", m.group(1)) for m in _CALL_RE.finditer(line))
    if _READ_VERB_RE.search(line):
        refs.extend(("read", m.group(1)) for m in _CONFIG_PATH_RE.finditer(line))
    return refs


def _package_relative(token: str, out_name: str) -> tuple[str, str] | None:
    """Split *token* into (install-relative path, package-relative path).

    Returns None when the token is not a package scripts/ or config/ path at
    all (a host path such as ``debugging/scripts/...``, an absolute path).
    """
    rest = _ROOT_PLACEHOLDER_RE.sub("", token)
    if rest.startswith(f"{out_name}/"):
        return rest, rest[len(out_name) + 1:]
    pkg_rel = rest
    for clone in _PACKAGE_CLONE_DIRS:
        if rest.startswith(clone):
            pkg_rel = rest[len(clone):]
            break
    # templates/scripts/ is the package source of what deploys to scripts/.
    if pkg_rel.startswith("templates/scripts/"):
        pkg_rel = pkg_rel[len("templates/"):]
    if pkg_rel.startswith(("scripts/", "config/")):
        return rest, pkg_rel
    return None


def _is_present(layout: Path, out: Path, install_rel: str, pkg_rel: str) -> bool:
    """True when the referenced file is in the install, at its named path or
    under the output root. A path with an agent-filled segment
    (``scripts/commit_guardian/<hook>.py``) is present when the directory
    before that segment is deployed."""
    if "<" in pkg_rel or "{" in pkg_rel:
        fixed = re.split(r"[<{]", pkg_rel, maxsplit=1)[0].rsplit("/", 1)[0]
        return (out / fixed).is_dir()
    return (layout / install_rel).is_file() or (out / pkg_rel).is_file()


def _undeployed_references(layout: Path) -> tuple[list[str], int, list[str]]:
    """Scan every compiled prompt; return (broken, references seen, raw hits)."""
    out = _output_root(layout)
    broken: list[str] = []
    seen: list[str] = []
    for prompt in _compiled_prompts(layout):
        text = prompt.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for kind, token in _line_references(line):
                split = _package_relative(token, out.name)
                if split is None:
                    continue
                install_rel, pkg_rel = split
                where = f"{prompt.relative_to(layout)}:{lineno}"
                seen.append(f"{where}: {kind} {token}")
                if pkg_rel in _NOT_A_DEPLOY_GAP:
                    continue
                if _is_present(layout, out, install_rel, pkg_rel):
                    continue
                broken.append(f"{where}: {kind} {token}")
    return broken, len(seen), seen


def _placeholder_scan_command(prompt_text: str) -> str:
    """Return the Python source of the documentation-verifier's scan command."""
    for line in prompt_text.splitlines():
        if "from build_placeholder_detection import" in line and 'python3 -c "' in line:
            return line.split('python3 -c "', 1)[1].rsplit('"', 1)[0]
    pytest.fail(
        "compiled documentation-verifier gives no `python3 -c` command that "
        "imports build_placeholder_detection"
    )


@pytest.mark.shared_layout_reader
def test_documentation_verifier_placeholder_scan_runs_from_consumer_install(
    shared_reference_layout, tmp_path,
):
    # covers: BP-900b-5
    # angle: deployed
    """The exact step-6a command the compiled documentation-verifier hands the
    agent runs in a consumer install: it imports build_placeholder_detection
    from the deployed scripts directory and finds a marker (the DIAGraph
    reproduction failed here with ModuleNotFoundError)."""
    layout = Path(shared_reference_layout)
    assert not (layout / "scripts" / "build_placeholder_detection.py").exists(), (
        "control: the shared layout must be the consumer shape, with no package "
        "scripts/ at the install root"
    )
    prompt = _output_root(layout) / "agents" / "documentation-verifier.md"
    assert prompt.is_file(), f"documentation-verifier not deployed: {prompt}"
    code = _placeholder_scan_command(prompt.read_text(encoding="utf-8"))

    scanned = tmp_path / "doc.md"
    scanned.write_text("# Title\n\nTODO: write this section\n", encoding="utf-8")
    # The sys.path entry names the INSTALL; the scan root is the doc's project.
    code = re.sub(
        r"(sys\.path\.insert\(\s*0\s*,\s*')<worktree_root>",
        lambda m: m.group(1) + layout.as_posix(),
        code,
    )
    code = code.replace("<worktree_root>", tmp_path.as_posix())
    code = code.replace("<absolute_file_path>", scanned.as_posix())

    result = subprocess.run(  # noqa: S603 -- fixed interpreter, test-built code
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, (
        "the documentation-verifier placeholder scan fails in a consumer "
        f"install:\n{result.stderr.strip()}"
    )
    hits = json.loads(result.stdout)
    assert any("TODO" in hit.get("marker", "") for hit in hits), (
        f"the scan ran but did not report the TODO marker: {hits}"
    )


@pytest.mark.shared_layout_reader
def test_every_script_or_config_reference_in_compiled_prompts_is_deployed(
    shared_reference_layout,
):
    # covers: BP-900b-5
    # angle: criterion
    """Every package script or config file a compiled prompt tells the agent to
    run, import or read is present in the consumer install."""
    layout = Path(shared_reference_layout)
    prompts = _compiled_prompts(layout)
    assert prompts, f"0 compiled prompts found under {_output_root(layout)}"
    broken, count, seen = _undeployed_references(layout)
    assert count, f"{len(prompts)} prompts scanned, 0 references found -- empty population"
    assert any(
        "documentation-verifier.md" in hit and "import" in hit
        and hit.endswith("build_placeholder_detection.py")
        for hit in seen
    ), "positive control: the documentation-verifier import was not seen"
    assert not broken, (
        f"{len(broken)} of {count} run/import/read references in {len(prompts)} "
        "compiled prompts name a package file the build never deploys (deploy it, "
        "or point the prompt at a file that ships):\n  " + "\n  ".join(broken)
    )
