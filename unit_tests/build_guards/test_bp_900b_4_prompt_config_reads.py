"""
MODULE: unit_tests/build_guards/test_bp_900b_4_prompt_config_reads.py
GOAL: Prove that every package config file a compiled prompt tells the agent to
    read exists at the path the prompt names, in a CONSUMER install (BP-900b-4).

    The shared reference layout is a DIRECTED build into an empty directory --
    the adopter shape: package config lands under ``<output_root>/config/`` and
    there is no package ``config/`` at the install root. A prompt that says
    "Read `config/doc_types.json`" therefore names a file that does not exist
    there, and the documentation-expert's mandatory pre-flight STOPs with a
    blocker (DIAGraph, leafcutter v15.0.9, INF-120c-3).

    Scope of the sweep: a config path on a line that reads/loads/opens it, whose
    file the build DOES deploy under ``<output_root>/config/`` but which the
    prompt names at a path where it does not exist. That is this defect's root
    cause (right file, wrong layout-specific path). A read of a config file the
    build never deploys at all is a different defect and is out of scope here.

    These tests only READ the deployed layout, so they request the shared
    session-scoped fixture rather than spawning their own build.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# A relative config-file path token: ``config/x.json``, ``leafcutter/config/x.yaml``,
# ``.leafcutter/config/x.json``. The look-behind rejects tokens that continue an
# anchored path (``<worktree-root>/.leafcutter/config/...``) or a longer word.
_CONFIG_PATH_RE = re.compile(
    r"(?<![\w./{}<>-])((?:[\w.-]+/)*config/[\w.-]+\.(?:json|ya?ml))"
)

# A line that instructs (or shows) a read of the file it names.
_READ_VERB_RE = re.compile(
    r"\b(?:read|reads|reading|load|loads|loading|load_json|open)\b", re.IGNORECASE
)

# (prompt parent directory, path token) pairs that deliberately name the
# PACKAGE SOURCE copy of a config file, not the deployed one: the skill edits
# the package's own registry when promoting a skill into the package, so the
# deployed copy would be the wrong target. Kept explicit and tiny on purpose.
_PACKAGE_SOURCE_EDITS = frozenset({
    ("add-skill-to-package", "leafcutter/config/skill_registry.json"),
})

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
    """Every compiled markdown prompt the build wrote under the output root."""
    out = _output_root(layout)
    found: list[Path] = []
    for rel in _PROMPT_DIRS:
        base = out / rel
        if base.is_dir():
            found.extend(sorted(base.rglob("*.md")))
    return found


def _config_reads(layout: Path) -> list[tuple[Path, int, str]]:
    """(prompt, line number, path token) for every config path on a read line."""
    reads: list[tuple[Path, int, str]] = []
    for prompt in _compiled_prompts(layout):
        lines = prompt.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if not _READ_VERB_RE.search(line):
                continue
            for match in _CONFIG_PATH_RE.finditer(line):
                reads.append((prompt, lineno, match.group(1)))
    return reads


@pytest.mark.shared_layout_reader
def test_documentation_expert_doc_types_read_resolves_in_consumer_install(
    shared_reference_layout,
):
    # covers: BP-900b-4
    # angle: deployed
    """The documentation-expert's mandatory doc_types.json read names a path
    that exists in a consumer install (the DIAGraph reproduction)."""
    layout = Path(shared_reference_layout)
    assert not (layout / "config" / "doc_types.json").exists(), (
        "control: the shared layout must be the consumer shape, with no package "
        "config/ at the install root"
    )
    prompt = _output_root(layout) / "agents" / "documentation-expert.md"
    assert prompt.is_file(), f"documentation-expert not deployed: {prompt}"
    text = prompt.read_text(encoding="utf-8")
    named = {m.group(1) for m in _CONFIG_PATH_RE.finditer(text)
             if m.group(1).endswith("doc_types.json")}
    assert named, "compiled documentation-expert names no doc_types.json path"
    missing = sorted(p for p in named if not (layout / p).is_file())
    assert not missing, (
        f"documentation-expert tells the agent to read {missing}, which does not "
        f"exist in a consumer install at {layout}"
    )


@pytest.mark.shared_layout_reader
def test_every_config_read_in_compiled_prompts_resolves_in_consumer_install(
    shared_reference_layout,
):
    # covers: BP-900b-4
    # angle: criterion
    """Every config path a compiled prompt names on a read/load/open line
    resolves, relative to the install root, to a file that exists there."""
    layout = Path(shared_reference_layout)
    prompts = _compiled_prompts(layout)
    assert prompts, f"0 compiled prompts found under {_output_root(layout)}"
    reads = _config_reads(layout)
    assert reads, f"{len(prompts)} prompts scanned, 0 config reads found -- empty population"
    assert any(
        p.name == "documentation-expert.md" and tok.endswith("doc_types.json")
        for p, _n, tok in reads
    ), "positive control: the documentation-expert doc_types.json read was not seen"

    deployed_config = _output_root(layout) / "config"
    broken = [
        f"{p.relative_to(layout)}:{n}: {tok}"
        for p, n, tok in reads
        if not (layout / tok).is_file()
        and (deployed_config / Path(tok).name).is_file()
        and (p.parent.name, tok) not in _PACKAGE_SOURCE_EDITS
    ]
    assert not broken, (
        f"{len(broken)} of {len(reads)} config reads in {len(prompts)} compiled "
        "prompts name a package config file the install HAS, at a path where it "
        "does not exist (write it as {{config.output_root}}/config/<file>):\n  "
        + "\n  ".join(broken)
    )
